"""Tests for user session isolation and AEAD encryption security."""

from __future__ import annotations

import pytest

from myiis_mcp.auth.crypto import decrypt_secret, encrypt_secret
from myiis_mcp.auth.models import ReconnectRequired, ServiceNotLinked
from myiis_mcp.auth.session import UpstreamSessionManager
from myiis_mcp.auth.storage import StorageRepository


def test_crypto_user_and_service_isolation():
    secret_payload = '{"cookies": {"SESSIONID": "secret_session_cookie_123"}}'

    user_a = "usr_alice"
    user_b = "usr_bob"

    # User A encrypts for service 'iis'
    ciphertext_a_iis = encrypt_secret(secret_payload, user_id=user_a, service="iis")

    # User A can decrypt User A's ciphertext for service 'iis'
    decrypted = decrypt_secret(ciphertext_a_iis, user_id=user_a, service="iis")
    assert decrypted == secret_payload

    # User B CANNOT decrypt User A's ciphertext (cross-user isolation)
    with pytest.raises(ValueError, match="HMAC tag mismatch"):
        decrypt_secret(ciphertext_a_iis, user_id=user_b, service="iis")

    # User A CANNOT decrypt User A's IIS ciphertext under service 'lms' (cross-service isolation)
    with pytest.raises(ValueError, match="HMAC tag mismatch"):
        decrypt_secret(ciphertext_a_iis, user_id=user_a, service="lms")

    # Tampered ciphertext fails HMAC verification
    tampered = ciphertext_a_iis[:-4] + "AAAA"
    with pytest.raises(ValueError, match="HMAC tag mismatch"):
        decrypt_secret(tampered, user_id=user_a, service="iis")


@pytest.mark.asyncio
async def test_session_manager_unlinked_and_isolation():
    storage = StorageRepository(":memory:")
    manager = UpstreamSessionManager(storage=storage)

    user_1 = "usr_one"
    user_2 = "usr_two"

    # Initially neither is linked
    status_1 = manager.get_account_status(user_1)
    assert status_1["iis"]["connected"] is False
    assert status_1["lms"]["connected"] is False

    with pytest.raises(ServiceNotLinked):
        await manager.get_iis_client(user_1)

    with pytest.raises(ServiceNotLinked):
        await manager.get_lms_client(user_1)
