"""Authentication and session domain models and exceptions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class MyIISError(Exception):
    """Base exception for MyIIS MCP Server."""
    def __init__(self, message: str, error_code: str = "internal_error"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.error_code, "message": self.message}


class AuthenticationRequired(MyIISError):
    """Raised when an unauthenticated request attempts to call a protected tool."""
    def __init__(self, message: str = "Требуется авторизация через OAuth 2.1 (ChatGPT / Codex)."):
        super().__init__(message, error_code="authentication_required")


class ServiceNotLinked(MyIISError):
    """Raised when a user hasn't linked the required service (IIS or LMS)."""
    def __init__(self, service: str, message: str | None = None):
        if not message:
            service_title = "ИИС БГУИР" if service == "iis" else "СЭО Moodle"
            message = f"Сервис {service_title} не подключен. Пожалуйста, подключите его на странице личного кабинета /account."
        super().__init__(message, error_code="service_not_linked")
        self.service = service

    def to_dict(self) -> dict[str, Any]:
        res = super().to_dict()
        res["service"] = self.service
        return res


class UpstreamAuthenticationFailed(MyIISError):
    """Raised when credentials rejected by upstream service (wrong login/pass)."""
    def __init__(self, service: str, message: str | None = None):
        if not message:
            message = f"Неверный логин или пароль для {service.upper()}."
        super().__init__(message, error_code="upstream_auth_failed")
        self.service = service


class UpstreamSessionExpired(MyIISError):
    """Raised when upstream session cookie has expired."""
    def __init__(self, service: str, message: str | None = None):
        if not message:
            message = f"Сессия {service.upper()} истекла."
        super().__init__(message, error_code="upstream_session_expired")
        self.service = service


class ReconnectRequired(MyIISError):
    """Raised when session expired and automatic relogin is not possible."""
    def __init__(self, service: str, message: str | None = None):
        if not message:
            service_title = "ИИС БГУИР" if service == "iis" else "СЭО Moodle"
            message = f"Сессия {service_title} истекла. Необходимо повторно подключить аккаунт в личном кабинете /account."
        super().__init__(message, error_code="reconnect_required")
        self.service = service

    def to_dict(self) -> dict[str, Any]:
        res = super().to_dict()
        res["service"] = self.service
        return res


class InsufficientScope(MyIISError):
    """Raised when token lacks required OAuth scope."""
    def __init__(self, required_scope: str):
        super().__init__(
            f"Недостаточно прав. Требуется scope: {required_scope}",
            error_code="insufficient_scope",
        )
        self.required_scope = required_scope


class IISAPIError(MyIISError):
    """Generic error from IIS BSUIR API."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message, error_code="iis_api_error")
        self.status_code = status_code


class MoodleAPIError(MyIISError):
    """Generic error from Moodle LMS API / AJAX."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message, error_code="moodle_api_error")
        self.status_code = status_code


class MoodleSesskeyExpired(MyIISError):
    """Raised when Moodle sesskey is invalid or out-of-date."""
    def __init__(self, message: str = "Moodle sesskey expired"):
        super().__init__(message, error_code="moodle_sesskey_expired")


class ResourceNotFound(MyIISError):
    """Requested resource or course was not found."""
    def __init__(self, message: str = "Ресурс не найден."):
        super().__init__(message, error_code="not_found")


class UpstreamUnavailable(MyIISError):
    """BSUIR service is temporarily down or unreachable."""
    def __init__(self, service: str, message: str | None = None):
        if not message:
            message = f"Сервер {service.upper()} БГУИР временно недоступен. Попробуйте позже."
        super().__init__(message, error_code="upstream_unavailable")
        self.service = service


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class User:
    """Registered MyIIS MCP user account."""
    id: str
    created_at: float = field(default_factory=time.time)


@dataclass
class OAuthClient:
    """Registered OAuth 2.1 client (e.g. ChatGPT, Codex, local client)."""
    client_id: str
    client_secret_hash: str = ""
    redirect_uris: list[str] = field(default_factory=list)
    allowed_scopes: list[str] = field(
        default_factory=lambda: ["iis:read", "iis:write", "lms:read", "lms:write", "account:manage"]
    )
    name: str = "Client"


@dataclass
class AuthCode:
    """Temporary PKCE authorization code."""
    code: str
    user_id: str
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str
    code_challenge_method: str  # Must be S256
    expires_at: float
    used: bool = False


@dataclass
class OAuthToken:
    """OAuth 2.1 Access & Refresh Token record."""
    access_token_hash: str
    refresh_token_hash: str
    user_id: str
    client_id: str
    scope: str
    expires_at: float
    revoked_at: float | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and time.time() < self.expires_at


@dataclass
class UpstreamConnection:
    """Encrypted upstream credentials or session for IIS or LMS."""
    id: str
    user_id: str
    service: str  # "iis" | "lms"
    username: str
    encrypted_secret: str
    secret_type: str = "session"  # "session" (cookies only) or "credentials" (opt-in relogin)
    crypto_version: str = "v1"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_validated_at: float | None = None
    status: str = "active"  # "active" | "reconnect_required" | "revoked"
    extra_json: str = "{}"  # Sanitized profile summary (FIO, group, etc.)
