"""Tests for protected LMS Moodle tools and security protections."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from myiis_mcp.auth.models import OAuthToken, User
from myiis_mcp.auth.tokens import hash_token
from myiis_mcp.security.redaction import validate_upstream_url
from myiis_mcp.server import app, storage


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_ssrf_protection_allowlist():
    # Valid allowed hosts
    assert validate_upstream_url("https://iis.bsuir.by/api/v1/profiles") is True
    assert validate_upstream_url("https://lms.bsuir.by/mod/page/view.php?id=123") is True

    # Invalid / disallowed hosts (SSRF attempts)
    with pytest.raises(ValueError, match="is not in the allowed upstream domains"):
        validate_upstream_url("https://evil.com/hack")

    with pytest.raises(ValueError, match="is not in the allowed upstream domains"):
        validate_upstream_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="is not in the allowed upstream domains"):
        validate_upstream_url("http://localhost:8080/admin")


def test_lms_tool_unauthenticated_returns_helpful_error(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "lms_get_courses", "arguments": {}},
    }
    resp = client.post("/mcp", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["isError"] is True
    err_text = data["result"]["content"][0]["text"]
    assert "требуется авторизация" in err_text.lower() or "личный кабинет" in err_text.lower()


def test_lms_tool_service_not_linked(client):
    user_id = "usr_test_no_lms"
    storage.get_or_create_user(user_id)

    raw_token = "valid_token_lms_123"
    tok = OAuthToken(
        access_token_hash=hash_token(raw_token),
        refresh_token_hash=hash_token("refresh_lms_123"),
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
        "params": {"name": "lms_get_courses", "arguments": {}},
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
    assert "СЭО Moodle" in err_text
    assert "/account/link/lms" in err_text
