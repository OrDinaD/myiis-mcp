"""Auth, OAuth 2.1, and session management module."""

from .models import (
    AuthenticationRequired,
    IISAPIError,
    InsufficientScope,
    MoodleAPIError,
    MoodleSesskeyExpired,
    MyIISError,
    OAuthClient,
    OAuthToken,
    ReconnectRequired,
    ResourceNotFound,
    ServiceNotLinked,
    UpstreamAuthenticationFailed,
    UpstreamConnection,
    UpstreamSessionExpired,
    UpstreamUnavailable,
    User,
)
from .oauth import OAuthServer
from .session import UpstreamSessionManager
from .storage import StorageRepository

__all__ = [
    "AuthenticationRequired",
    "IISAPIError",
    "InsufficientScope",
    "MoodleAPIError",
    "MoodleSesskeyExpired",
    "MyIISError",
    "OAuthClient",
    "OAuthServer",
    "OAuthToken",
    "ReconnectRequired",
    "ResourceNotFound",
    "ServiceNotLinked",
    "StorageRepository",
    "UpstreamAuthenticationFailed",
    "UpstreamConnection",
    "UpstreamSessionExpired",
    "UpstreamSessionManager",
    "UpstreamUnavailable",
    "User",
]
