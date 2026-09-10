"""Tests for protected student IIS tools."""

from __future__ import annotations

import json
import pytest
from starlette.testclient import TestClient

from myiis_mcp.auth.models import OAuthToken, UpstreamConnection, User
from myiis_mcp.auth.tokens import hash_token
from myiis_mcp.server import app, mcp, storage


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_iis_tool_unauthenticated_returns_helpful_error(client):
    # Calling iis_get_profile without Bearer token
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "iis_get_profile", "arguments": {}},
    }
    resp = client.post("/mcp", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["isError"] is True
    err_text = data["result"]["content"][0]["text"]
    assert "требуется авторизация" in err_text.lower() or "личный кабинет" in err_text.lower()


def test_iis_tool_service_not_linked(client):
    # Create valid user with active token, but no linked IIS account
    user_id = "usr_test_no_iis"
    storage.get_or_create_user(user_id)

    raw_token = "valid_token_test_123"
    tok = OAuthToken(
        access_token_hash=hash_token(raw_token),
        refresh_token_hash=hash_token("refresh_123"),
        user_id=user_id,
        client_id="chatgpt",
        scope="iis:read lms:read",
        expires_at=9999999999,
    )
    storage.save_token(tok)

    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "iis_get_profile", "arguments": {}},
    }
    resp = client.post(
        "/mcp",
        json=payload,
        headers={"Authorization": f"Bearer {raw_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["isError"] is True
    err_text = data["result"]["content"][0]["text"]
    assert "ИИС БГУИР" in err_text
    assert "/account/link/iis" in err_text
