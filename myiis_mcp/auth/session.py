"""Multi-user upstream session lifecycle manager for IIS and LMS."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from ..iis.client import IISAuthenticatedClient
from ..iis.models import IISProfile
from ..lms.client import MoodleClient
from .crypto import decrypt_secret, encrypt_secret
from .models import (
    ReconnectRequired,
    ServiceNotLinked,
    UpstreamAuthenticationFailed,
    UpstreamConnection,
    UpstreamSessionExpired,
)
from .storage import StorageRepository

logger = logging.getLogger(__name__)


class UpstreamSessionManager:
    """Manages encrypted upstream sessions, cookies, and automatic re-login."""

    def __init__(self, storage: StorageRepository):
        self.storage = storage

    # -----------------------------------------------------------------------
    # IIS Client Management
    # -----------------------------------------------------------------------

    async def get_iis_client(self, user_id: str) -> IISAuthenticatedClient:
        """Load and decrypt student IIS session, returning an authenticated client."""
        conn = self.storage.get_upstream_connection(user_id, "iis")
        if not conn or conn.status == "revoked":
            raise ServiceNotLinked("iis")
        if conn.status == "reconnect_required":
            raise ReconnectRequired("iis")

        try:
            decrypted_json = decrypt_secret(conn.encrypted_secret, user_id, "iis")
            secret_data = json.loads(decrypted_json)
        except Exception as exc:
            logger.error(f"Failed to decrypt IIS session for user {user_id}: {exc}")
            raise ReconnectRequired("iis", "Не удалось расшифровать сессию. Требуется повторный вход.")

        cookies = secret_data.get("cookies", {})
        client = IISAuthenticatedClient(cookies=cookies)
        return client

    async def link_iis(
        self,
        user_id: str,
        username: str,
        password: str,
        keep_signed_in: bool = False,
    ) -> IISProfile:
        """Authenticate with BSUIR IIS, encrypt session/credentials and persist connection."""
        client = IISAuthenticatedClient()
        try:
            cookies, _ = await client.login(username=username, password=password)
            profile = await client.get_profile()
        finally:
            await client.aclose()

        secret_data: dict[str, Any] = {"cookies": cookies}
        secret_type = "session"
        if keep_signed_in:
            secret_data["username"] = username
            secret_data["password"] = password
            secret_type = "credentials"

        encrypted_secret = encrypt_secret(
            json.dumps(secret_data),
            user_id=user_id,
            service="iis",
        )

        extra_info = {
            "fio": profile.fio,
            "group": profile.group,
            "faculty": profile.faculty,
            "rating": profile.rating,
        }

        conn = UpstreamConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            service="iis",
            username=username,
            encrypted_secret=encrypted_secret,
            secret_type=secret_type,
            created_at=time.time(),
            updated_at=time.time(),
            last_validated_at=time.time(),
            status="active",
            extra_json=json.dumps(extra_info, ensure_ascii=False),
        )
        self.storage.save_upstream_connection(conn)
        return profile

    async def unlink_iis(self, user_id: str) -> None:
        """Log out from IIS and delete stored session."""
        try:
            client = await self.get_iis_client(user_id)
            await client.logout()
            await client.aclose()
        except Exception:
            pass
        self.storage.delete_upstream_connection(user_id, "iis")

    # -----------------------------------------------------------------------
    # LMS Moodle Client Management
    # -----------------------------------------------------------------------

    async def get_lms_client(self, user_id: str) -> MoodleClient:
        """Load and decrypt student LMS Moodle session, returning an authenticated client."""
        conn = self.storage.get_upstream_connection(user_id, "lms")
        if not conn or conn.status == "revoked":
            raise ServiceNotLinked("lms")
        if conn.status == "reconnect_required":
            raise ReconnectRequired("lms")

        try:
            decrypted_json = decrypt_secret(conn.encrypted_secret, user_id, "lms")
            secret_data = json.loads(decrypted_json)
        except Exception as exc:
            logger.error(f"Failed to decrypt LMS session for user {user_id}: {exc}")
            raise ReconnectRequired("lms", "Не удалось расшифровать сессию СЭО. Требуется повторный вход.")

        cookies = secret_data.get("cookies", {})
        sesskey = secret_data.get("sesskey")
        client = MoodleClient(cookies=cookies, sesskey=sesskey)
        return client

    async def link_lms(
        self,
        user_id: str,
        username: str,
        password: str,
        keep_signed_in: bool = False,
    ) -> None:
        """Authenticate with BSUIR LMS Moodle, encrypt session/credentials and persist connection."""
        client = MoodleClient()
        try:
            cookies, sesskey = await client.login(username=username, password=password)
        finally:
            await client.aclose()

        secret_data: dict[str, Any] = {
            "cookies": cookies,
            "sesskey": sesskey,
        }
        secret_type = "session"
        if keep_signed_in:
            secret_data["username"] = username
            secret_data["password"] = password
            secret_type = "credentials"

        encrypted_secret = encrypt_secret(
            json.dumps(secret_data),
            user_id=user_id,
            service="lms",
        )

        conn = UpstreamConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            service="lms",
            username=username,
            encrypted_secret=encrypted_secret,
            secret_type=secret_type,
            created_at=time.time(),
            updated_at=time.time(),
            last_validated_at=time.time(),
            status="active",
            extra_json="{}",
        )
        self.storage.save_upstream_connection(conn)

    async def unlink_lms(self, user_id: str) -> None:
        """Unlink and delete stored Moodle session."""
        self.storage.delete_upstream_connection(user_id, "lms")

    # -----------------------------------------------------------------------
    # Status Summary
    # -----------------------------------------------------------------------

    def get_account_status(self, user_id: str) -> dict[str, Any]:
        """Summary of user's connected services for get_account_status MCP tool."""
        iis_conn = self.storage.get_upstream_connection(user_id, "iis")
        lms_conn = self.storage.get_upstream_connection(user_id, "lms")

        iis_meta = json.loads(iis_conn.extra_json) if iis_conn and iis_conn.extra_json else {}

        return {
            "user_id": user_id,
            "iis": {
                "connected": bool(iis_conn and iis_conn.status == "active"),
                "status": iis_conn.status if iis_conn else "not_connected",
                "username": iis_conn.username if iis_conn else None,
                "fio": iis_meta.get("fio"),
                "group": iis_meta.get("group"),
                "last_validated": iis_conn.last_validated_at if iis_conn else None,
            },
            "lms": {
                "connected": bool(lms_conn and lms_conn.status == "active"),
                "status": lms_conn.status if lms_conn else "not_connected",
                "username": lms_conn.username if lms_conn else None,
                "last_validated": lms_conn.last_validated_at if lms_conn else None,
            },
        }
