"""OAuth 2.1 PKCE, token generation, and hashing utilities."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time

ACCESS_TOKEN_LIFETIME = 3600  # 1 hour
REFRESH_TOKEN_LIFETIME = 30 * 86400  # 30 days
AUTH_CODE_LIFETIME = 600  # 10 minutes


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of a token for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_auth_code() -> str:
    """Generate cryptographically secure authorization code."""
    return f"myiis_code_{secrets.token_urlsafe(32)}"


def generate_access_token() -> str:
    """Generate cryptographically secure OAuth access token."""
    return f"myiis_at_{secrets.token_urlsafe(32)}"


def generate_refresh_token() -> str:
    """Generate cryptographically secure OAuth refresh token."""
    return f"myiis_rt_{secrets.token_urlsafe(32)}"


def generate_code_verifier() -> str:
    """Generate PKCE code_verifier (43-128 chars)."""
    return secrets.token_urlsafe(64)


def compute_code_challenge(code_verifier: str) -> str:
    """Compute PKCE S256 code_challenge from code_verifier."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


create_code_challenge = compute_code_challenge


def verify_code_challenge(
    code_verifier: str,
    code_challenge: str,
    method: str = "S256",
) -> bool:
    """Verify PKCE code_verifier against expected code_challenge using S256."""
    if method != "S256":
        return False
    computed = compute_code_challenge(code_verifier)
    return secrets.compare_digest(computed, code_challenge.rstrip("="))
