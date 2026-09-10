"""Tests for OAuth 2.1 Authorization Server, RFC 8414 metadata, and Bearer authentication."""

from __future__ import annotations

import base64
import hashlib
import time
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from myiis_mcp.auth.models import AuthCode, OAuthToken, User
from myiis_mcp.auth.oauth import OAuthServer
from myiis_mcp.auth.storage import StorageRepository
from myiis_mcp.auth.tokens import create_code_challenge, generate_code_verifier, hash_token
from myiis_mcp.server import app, mcp, oauth_server, storage


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_rfc8414_protected_resource_metadata(client):
    resp = client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    data = resp.json()
    assert "/mcp" in data["resource"]
    assert "scopes_supported" in data
    assert "iis:read" in data["scopes_supported"]
    assert "lms:read" in data["scopes_supported"]
    assert "account:manage" in data["scopes_supported"]
    assert data["bearer_methods_supported"] == ["header"]


def test_rfc8414_authorization_server_metadata(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    data = resp.json()
    assert "/oauth/authorize" in data["authorization_endpoint"]
    assert "/oauth/token" in data["token_endpoint"]
    assert "/oauth/revoke" in data["revocation_endpoint"]
    assert "S256" in data["code_challenge_methods_supported"]
    assert "authorization_code" in data["grant_types_supported"]

    # Also test OpenID config alias
    resp_oidc = client.get("/.well-known/openid-configuration")
    assert resp_oidc.status_code == 200
    assert resp_oidc.json()["token_endpoint"] == data["token_endpoint"]


def test_pkce_s256_verification():
    verifier = generate_code_verifier()
    challenge = create_code_challenge(verifier)

    from myiis_mcp.auth.tokens import verify_code_challenge

    assert verify_code_challenge(verifier, challenge, "S256") is True
    assert verify_code_challenge("wrong_verifier", challenge, "S256") is False


def test_oauth_authorize_and_token_flow(client):
    verifier = generate_code_verifier()
    challenge = create_code_challenge(verifier)

    # 1. GET /oauth/authorize shows consent page
    auth_params = {
        "response_type": "code",
        "client_id": "chatgpt",
        "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
        "scope": "iis:read lms:read account:manage",
        "state": "test_state_123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    resp = client.get("/oauth/authorize", params=auth_params)
    assert resp.status_code == 200
    assert "Подключение к ChatGPT" in resp.text
    assert "Разрешить доступ" in resp.text

    # 2. POST /oauth/authorize approves and returns redirect with code
    post_resp = client.post(
        "/oauth/authorize",
        params=auth_params,
        data={"action": "approve"},
        follow_redirects=False,
    )
    assert post_resp.status_code == 302
    redirect_url = post_resp.headers["location"]
    assert redirect_url.startswith("https://chatgpt.com/aip/oauth/callback")

    parsed = urlparse(redirect_url)
    qs = parse_qs(parsed.query)
    assert qs["state"][0] == "test_state_123"
    assert "code" in qs
    code = qs["code"][0]

    # 3. POST /oauth/token exchanges code + verifier for access & refresh tokens
    token_resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://chatgpt.com/aip/oauth/callback",
            "client_id": "chatgpt",
            "code_verifier": verifier,
        },
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "Bearer"
    assert token_data["expires_in"] > 0
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # 4. Use access_token on /mcp
    mcp_call = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {"name": "get_account_status", "arguments": {}},
    }
    call_resp = client.post(
        "/mcp",
        json=mcp_call,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert call_resp.status_code == 200
    result = call_resp.json()
    assert "result" in result
    status_content = result["result"]["content"][0]["text"]
    assert "connected" in status_content or "user_id" in status_content

    # 5. Refresh token exchange
    refresh_resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    assert refresh_resp.status_code == 200
    new_token_data = refresh_resp.json()
    assert "access_token" in new_token_data
    assert new_token_data["access_token"] != access_token

    # 6. Revocation
    revoke_resp = client.post(
        "/oauth/revoke",
        data={"token": new_token_data["access_token"]},
    )
    assert revoke_resp.status_code == 200


def test_mcp_unauthorized_token_returns_401(client):
    mcp_call = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {"name": "get_account_status", "arguments": {}},
    }
    resp = client.post(
        "/mcp",
        json=mcp_call,
        headers={"Authorization": "Bearer bad_invalid_token_xyz"},
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert "invalid_token" in resp.headers["WWW-Authenticate"]
