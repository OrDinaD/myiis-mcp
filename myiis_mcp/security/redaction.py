"""Security utilities: secret redaction and SSRF URL validation."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# Patterns for sensitive keys that should never appear in logs or error traces
_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|secret|token|cookie|sesskey|authorization|code_verifier|code_challenge|credentials)",
    re.IGNORECASE,
)

# Common regex patterns for secret values
_SECRET_VALUE_PATTERNS = [
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(sesskey=)[a-zA-Z0-9]+", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"'])[^\"']+", re.IGNORECASE),
]

_ALLOWED_HOSTS = {
    "iis.bsuir.by",
    "lms.bsuir.by",
    "libeldoc.bsuir.by",
}


def redact_string(val: str) -> str:
    """Mask known sensitive patterns in arbitrary strings."""
    if not val:
        return val
    res = val
    for pattern in _SECRET_VALUE_PATTERNS:
        res = pattern.sub(r"\1[REDACTED]", res)
    return res


def redact_dict(data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Recursively redact sensitive keys and values in dictionaries."""
    if depth > 10:
        return {"...": "[TRUNCATED]"}
    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        if _SENSITIVE_KEY_PATTERNS.search(str(k)):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = redact_dict(v, depth + 1)
        elif isinstance(v, list):
            sanitized[k] = [
                redact_dict(item, depth + 1) if isinstance(item, dict)
                else redact_string(str(item)) if isinstance(item, str)
                else item
                for item in v
            ]
        elif isinstance(v, str):
            sanitized[k] = redact_string(v)
        else:
            sanitized[k] = v
    return sanitized


def validate_upstream_url(url: str, raise_error: bool = True) -> bool:
    """Validate that a URL is safe to fetch and points to an allowed BSUIR host.

    Protects against SSRF (Server-Side Request Forgery).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            if raise_error:
                raise ValueError(f"Scheme '{parsed.scheme}' is not in the allowed upstream domains")
            return False
        # Disallow IP addresses, localhost, internal network, cloud metadata
        host = (parsed.hostname or "").lower()
        if not host:
            if raise_error:
                raise ValueError(f"Host '{host}' is not in the allowed upstream domains")
            return False
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"):
            if raise_error:
                raise ValueError(f"Host '{host}' is not in the allowed upstream domains")
            return False
        if host.startswith("10.") or host.startswith("192.168."):
            if raise_error:
                raise ValueError(f"Host '{host}' is not in the allowed upstream domains")
            return False
        if re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", host):
            if raise_error:
                raise ValueError(f"Host '{host}' is not in the allowed upstream domains")
            return False
        # Must be in explicitly allowed hosts
        if host not in _ALLOWED_HOSTS:
            if raise_error:
                raise ValueError(f"Host '{host}' is not in the allowed upstream domains: {_ALLOWED_HOSTS}")
            return False
        return True
    except ValueError:
        if raise_error:
            raise
        return False
    except Exception as exc:
        if raise_error:
            raise ValueError(f"URL is not in the allowed upstream domains: {exc}") from exc
        return False

