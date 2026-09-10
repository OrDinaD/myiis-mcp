"""Storage repository for OAuth grants, tokens, and upstream connections.

Works with SQLite in local/test environments and provides Cloudflare D1 compatibility.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from .models import AuthCode, OAuthClient, OAuthToken, UpstreamConnection, User

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_secret_hash TEXT NOT NULL,
    redirect_uris TEXT NOT NULL,
    allowed_scopes TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_auth_codes (
    code TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    scope TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    code_challenge_method TEXT NOT NULL,
    expires_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    access_token_hash TEXT PRIMARY KEY,
    refresh_token_hash TEXT NOT NULL,
    user_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);

CREATE TABLE IF NOT EXISTS upstream_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    service TEXT NOT NULL,
    username TEXT NOT NULL,
    encrypted_secret TEXT NOT NULL,
    secret_type TEXT NOT NULL,
    crypto_version TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_validated_at REAL,
    status TEXT NOT NULL,
    extra_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (user_id, service)
);
"""


class StorageRepository:
    """SQLite-based storage repository for users, tokens, and upstream connections."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)

    # -----------------------------------------------------------------------
    # Users
    # -----------------------------------------------------------------------

    def get_or_create_user(self, user_id: str) -> User:
        with self._conn:
            cur = self._conn.execute("SELECT id, created_at FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return User(id=row["id"], created_at=row["created_at"])
            now = time.time()
            self._conn.execute("INSERT INTO users (id, created_at) VALUES (?, ?)", (user_id, now))
            return User(id=user_id, created_at=now)

    # -----------------------------------------------------------------------
    # OAuth Clients
    # -----------------------------------------------------------------------

    def register_client(self, client: OAuthClient) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO oauth_clients (client_id, client_secret_hash, redirect_uris, allowed_scopes, name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    client.client_secret_hash,
                    json.dumps(client.redirect_uris),
                    json.dumps(client.allowed_scopes),
                    client.name,
                ),
            )

    def get_client(self, client_id: str) -> OAuthClient | None:
        cur = self._conn.execute(
            "SELECT client_id, client_secret_hash, redirect_uris, allowed_scopes, name FROM oauth_clients WHERE client_id = ?",
            (client_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return OAuthClient(
            client_id=row["client_id"],
            client_secret_hash=row["client_secret_hash"],
            redirect_uris=json.loads(row["redirect_uris"]),
            allowed_scopes=json.loads(row["allowed_scopes"]),
            name=row["name"],
        )

    # -----------------------------------------------------------------------
    # Auth Codes
    # -----------------------------------------------------------------------

    def save_auth_code(self, auth_code: AuthCode) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO oauth_auth_codes (
                    code, user_id, client_id, redirect_uri, scope,
                    code_challenge, code_challenge_method, expires_at, used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    auth_code.code,
                    auth_code.user_id,
                    auth_code.client_id,
                    auth_code.redirect_uri,
                    auth_code.scope,
                    auth_code.code_challenge,
                    auth_code.code_challenge_method,
                    auth_code.expires_at,
                    1 if auth_code.used else 0,
                ),
            )

    def get_auth_code(self, code: str) -> AuthCode | None:
        cur = self._conn.execute(
            """
            SELECT code, user_id, client_id, redirect_uri, scope,
                   code_challenge, code_challenge_method, expires_at, used
            FROM oauth_auth_codes WHERE code = ?
            """,
            (code,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return AuthCode(
            code=row["code"],
            user_id=row["user_id"],
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            scope=row["scope"],
            code_challenge=row["code_challenge"],
            code_challenge_method=row["code_challenge_method"],
            expires_at=row["expires_at"],
            used=bool(row["used"]),
        )

    def consume_auth_code(self, code: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE oauth_auth_codes SET used = 1 WHERE code = ?", (code,))

    # -----------------------------------------------------------------------
    # OAuth Tokens
    # -----------------------------------------------------------------------

    def save_token(self, token: OAuthToken) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO oauth_tokens (
                    access_token_hash, refresh_token_hash, user_id, client_id, scope, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token.access_token_hash,
                    token.refresh_token_hash,
                    token.user_id,
                    token.client_id,
                    token.scope,
                    token.expires_at,
                    token.revoked_at,
                ),
            )

    def get_token_by_access_hash(self, token_hash: str) -> OAuthToken | None:
        cur = self._conn.execute(
            """
            SELECT access_token_hash, refresh_token_hash, user_id, client_id, scope, expires_at, revoked_at
            FROM oauth_tokens WHERE access_token_hash = ?
            """,
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return OAuthToken(
            access_token_hash=row["access_token_hash"],
            refresh_token_hash=row["refresh_token_hash"],
            user_id=row["user_id"],
            client_id=row["client_id"],
            scope=row["scope"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )

    def get_token_by_refresh_hash(self, token_hash: str) -> OAuthToken | None:
        cur = self._conn.execute(
            """
            SELECT access_token_hash, refresh_token_hash, user_id, client_id, scope, expires_at, revoked_at
            FROM oauth_tokens WHERE refresh_token_hash = ?
            """,
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return OAuthToken(
            access_token_hash=row["access_token_hash"],
            refresh_token_hash=row["refresh_token_hash"],
            user_id=row["user_id"],
            client_id=row["client_id"],
            scope=row["scope"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )

    def revoke_token(self, token_hash: str) -> None:
        now = time.time()
        with self._conn:
            self._conn.execute(
                "UPDATE oauth_tokens SET revoked_at = ? WHERE access_token_hash = ? OR refresh_token_hash = ?",
                (now, token_hash, token_hash),
            )

    # -----------------------------------------------------------------------
    # Upstream Connections (IIS / LMS per User)
    # -----------------------------------------------------------------------

    def save_upstream_connection(self, conn: UpstreamConnection) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO upstream_connections (
                    id, user_id, service, username, encrypted_secret,
                    secret_type, crypto_version, created_at, updated_at,
                    last_validated_at, status, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conn.id,
                    conn.user_id,
                    conn.service,
                    conn.username,
                    conn.encrypted_secret,
                    conn.secret_type,
                    conn.crypto_version,
                    conn.created_at,
                    conn.updated_at,
                    conn.last_validated_at,
                    conn.status,
                    conn.extra_json,
                ),
            )

    def get_upstream_connection(self, user_id: str, service: str) -> UpstreamConnection | None:
        cur = self._conn.execute(
            """
            SELECT id, user_id, service, username, encrypted_secret,
                   secret_type, crypto_version, created_at, updated_at,
                   last_validated_at, status, extra_json
            FROM upstream_connections
            WHERE user_id = ? AND service = ?
            """,
            (user_id, service),
        )
        row = cur.fetchone()
        if not row:
            return None
        return UpstreamConnection(
            id=row["id"],
            user_id=row["user_id"],
            service=row["service"],
            username=row["username"],
            encrypted_secret=row["encrypted_secret"],
            secret_type=row["secret_type"],
            crypto_version=row["crypto_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_validated_at=row["last_validated_at"],
            status=row["status"],
            extra_json=row["extra_json"],
        )

    def list_upstream_connections(self, user_id: str) -> list[UpstreamConnection]:
        cur = self._conn.execute(
            """
            SELECT id, user_id, service, username, encrypted_secret,
                   secret_type, crypto_version, created_at, updated_at,
                   last_validated_at, status, extra_json
            FROM upstream_connections
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conns = []
        for row in cur.fetchall():
            conns.append(
                UpstreamConnection(
                    id=row["id"],
                    user_id=row["user_id"],
                    service=row["service"],
                    username=row["username"],
                    encrypted_secret=row["encrypted_secret"],
                    secret_type=row["secret_type"],
                    crypto_version=row["crypto_version"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_validated_at=row["last_validated_at"],
                    status=row["status"],
                    extra_json=row["extra_json"],
                )
            )
        return conns

    def delete_upstream_connection(self, user_id: str, service: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM upstream_connections WHERE user_id = ? AND service = ?",
                (user_id, service),
            )
