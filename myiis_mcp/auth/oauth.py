"""OAuth 2.1 Authorization Server and Resource Server implementation for ChatGPT/Codex."""

from __future__ import annotations

import base64
import html
import json
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from .models import (
    AuthCode,
    AuthenticationRequired,
    InsufficientScope,
    OAuthClient,
    OAuthToken,
    User,
)
from .storage import StorageRepository
from .tokens import (
    ACCESS_TOKEN_LIFETIME,
    AUTH_CODE_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    generate_access_token,
    generate_auth_code,
    generate_refresh_token,
    hash_token,
    verify_code_challenge,
)


async def _parse_form_data(request: Request) -> dict[str, str]:
    """Safely parse form data without requiring external python-multipart."""
    try:
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
    except Exception:
        pass
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {k: v[0] if v else "" for k, v in parsed.items()}


SERVER_BASE_URL = "https://myiis-mcp.vlad-vasilevskiy-07.workers.dev"


class OAuthServer:
    """OAuth 2.1 server handling authorization-code flow, PKCE S256, and tokens."""

    def __init__(self, storage: StorageRepository, base_url: str = SERVER_BASE_URL):
        self.storage = storage
        self.base_url = base_url.rstrip("/")

    # -----------------------------------------------------------------------
    # Metadata Endpoints (RFC 8414 & Protected Resource Metadata)
    # -----------------------------------------------------------------------

    def get_protected_resource_metadata(self) -> dict[str, Any]:
        """RFC 8414 OAuth 2.0 Protected Resource Metadata."""
        return {
            "resource": f"{self.base_url}/mcp",
            "authorization_servers": [self.base_url],
            "scopes_supported": [
                "iis:read",
                "iis:write",
                "lms:read",
                "lms:write",
                "account:manage",
            ],
            "bearer_methods_supported": ["header"],
        }

    def get_authorization_server_metadata(self) -> dict[str, Any]:
        """RFC 8414 OAuth 2.0 Authorization Server Metadata."""
        return {
            "issuer": self.base_url,
            "authorization_endpoint": f"{self.base_url}/oauth/authorize",
            "token_endpoint": f"{self.base_url}/oauth/token",
            "revocation_endpoint": f"{self.base_url}/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            "scopes_supported": [
                "iis:read",
                "iis:write",
                "lms:read",
                "lms:write",
                "account:manage",
            ],
        }

    # -----------------------------------------------------------------------
    # Token Authentication Helper
    # -----------------------------------------------------------------------

    def authenticate_bearer(
        self,
        auth_header: str | None,
        required_scope: str | None = None,
    ) -> User:
        """Validate incoming Bearer token, check expiry, and return User.

        Raises AuthenticationRequired or InsufficientScope.
        """
        if not auth_header or not auth_header.strip():
            raise AuthenticationRequired("Требуется заголовок Authorization: Bearer <TOKEN>.")

        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationRequired("Неверный формат заголовка Authorization. Ожидается 'Bearer <TOKEN>'.")

        raw_token = parts[1]
        t_hash = hash_token(raw_token)
        token_record = self.storage.get_token_by_access_hash(t_hash)

        if not token_record or not token_record.is_active:
            raise AuthenticationRequired("Недействительный или истекший токен доступа.")

        if required_scope:
            granted_scopes = set(token_record.scope.split())
            if required_scope not in granted_scopes:
                raise InsufficientScope(required_scope)

        return self.storage.get_or_create_user(token_record.user_id)

    # -----------------------------------------------------------------------
    # Authorization Endpoint (/oauth/authorize)
    # -----------------------------------------------------------------------

    async def handle_authorize(self, request: Request) -> Response:
        """Handle GET/POST /oauth/authorize with PKCE S256."""
        params = request.query_params
        response_type = params.get("response_type")
        client_id = params.get("client_id")
        redirect_uri = params.get("redirect_uri")
        code_challenge = params.get("code_challenge")
        code_challenge_method = params.get("code_challenge_method", "S256")
        state = params.get("state", "")
        scope = params.get("scope", "iis:read lms:read account:manage")

        # Validate mandatory OAuth 2.1 params
        if response_type != "code":
            return JSONResponse({"error": "unsupported_response_type", "message": "Only 'code' is supported."}, status_code=400)
        if not client_id or not redirect_uri:
            return JSONResponse({"error": "invalid_request", "message": "client_id and redirect_uri are required."}, status_code=400)
        if not code_challenge:
            return JSONResponse({"error": "invalid_request", "message": "code_challenge is required (PKCE S256)."}, status_code=400)
        if code_challenge_method != "S256":
            return JSONResponse({"error": "invalid_request", "message": "Only code_challenge_method 'S256' is supported."}, status_code=400)

        # Ensure or get user session from browser cookie
        user_session = request.cookies.get("myiis_session")
        if not user_session:
            user_session = f"usr_{secrets.token_urlsafe(16)}"

        user = self.storage.get_or_create_user(user_session)

        # If user submitted the approval form
        if request.method == "POST":
            form = await _parse_form_data(request)
            action = form.get("action")
            if action == "approve":
                auth_code = AuthCode(
                    code=generate_auth_code(),
                    user_id=user.id,
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    scope=scope,
                    code_challenge=code_challenge,
                    code_challenge_method=code_challenge_method,
                    expires_at=time.time() + AUTH_CODE_LIFETIME,
                )
                self.storage.save_auth_code(auth_code)

                # RFC 9207: include 'iss'
                redirect_params = {
                    "code": auth_code.code,
                    "state": state,
                    "iss": self.base_url,
                }
                sep = "&" if "?" in redirect_uri else "?"
                target_url = f"{redirect_uri}{sep}{urlencode(redirect_params)}"

                resp = RedirectResponse(target_url, status_code=302)
                resp.set_cookie("myiis_session", user.id, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
                return resp
            else:
                sep = "&" if "?" in redirect_uri else "?"
                return RedirectResponse(f"{redirect_uri}{sep}error=access_denied&state={html.escape(state)}", status_code=302)

        # GET: Render approval page
        html_page = self._render_authorize_page(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            state=state,
            code_challenge=code_challenge,
            user=user,
        )
        resp = HTMLResponse(html_page)
        resp.set_cookie("myiis_session", user.id, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
        return resp

    def _render_authorize_page(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str,
        user: User,
    ) -> str:
        """Render modern, user-friendly OAuth consent and account linking page."""
        iis_conn = self.storage.get_upstream_connection(user.id, "iis")
        lms_conn = self.storage.get_upstream_connection(user.id, "lms")

        iis_status = "✅ Подключен" if iis_conn and iis_conn.status == "active" else "⚠️ Не подключен"
        lms_status = "✅ Подключен" if lms_conn and lms_conn.status == "active" else "⚠️ Не подключен"

        scopes_list = "".join(f"<li><code>{html.escape(s)}</code></li>" for s in scope.split())

        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подключение MyIIS к ChatGPT • Авторизация</title>
  <style>
    :root {{
      --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #f8fafc;
      --muted: #94a3b8; --primary: #0284c7; --primary-hover: #0369a1;
      --green: #10b981; --amber: #f59e0b;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); margin: 0; padding: 24px;
      display: flex; justify-content: center; align-items: center; min-height: 100vh;
    }}
    .card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      max-width: 480px; width: 100%; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }}
    .badge-icon {{ background: var(--primary); color: white; border-radius: 10px; padding: 8px 12px; font-weight: bold; }}
    h1 {{ font-size: 20px; font-weight: 700; margin: 0; }}
    p {{ color: var(--muted); font-size: 14px; line-height: 1.5; margin: 8px 0 20px; }}
    .status-box {{
      background: #0f172a; border: 1px solid var(--border); border-radius: 12px;
      padding: 16px; margin-bottom: 20px; font-size: 13px;
    }}
    .service-row {{ display: flex; justify-content: space-between; padding: 6px 0; }}
    .btn {{
      display: inline-block; width: 100%; box-sizing: border-box; text-align: center;
      padding: 12px 20px; border-radius: 10px; font-size: 14px; font-weight: 600;
      cursor: pointer; text-decoration: none; border: none; transition: 0.15s;
    }}
    .btn-primary {{ background: var(--primary); color: white; margin-top: 10px; }}
    .btn-primary:hover {{ background: var(--primary-hover); }}
    .btn-secondary {{ background: transparent; color: var(--muted); margin-top: 8px; border: 1px solid var(--border); }}
    .btn-link {{ background: transparent; color: var(--primary); font-size: 13px; padding: 6px 0; text-decoration: underline; }}
    ul {{ margin: 8px 0; padding-left: 20px; font-size: 13px; color: var(--muted); }}
    code {{ color: #38bdf8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <div class="badge-icon">БГУИР</div>
      <div>
        <h1>Подключение к ChatGPT</h1>
        <div style="font-size:12px;color:var(--muted)">MyIIS MCP Server • OAuth 2.1</div>
      </div>
    </div>

    <p>Приложение <strong>{html.escape(client_id)}</strong> запрашивает доступ к вашим персональным учебным данным БГУИР:</p>

    <ul>{scopes_list}</ul>

    <div class="status-box">
      <div style="font-weight:600;margin-bottom:8px;color:#e2e8f0;">Статус аккаунтов БГУИР:</div>
      <div class="service-row">
        <span>ИИС БГУИР:</span>
        <span>{iis_status}</span>
      </div>
      <div class="service-row">
        <span>СЭО Moodle:</span>
        <span>{lms_status}</span>
      </div>
      <div style="margin-top:10px;text-align:right;">
        <a href="/account" class="btn-link" target="_blank">⚙️ Настроить связывание аккаунтов &rarr;</a>
      </div>
    </div>

    <form method="POST">
      <input type="hidden" name="action" value="approve" />
      <button type="submit" class="btn btn-primary">Разрешить доступ</button>
    </form>
    <form method="POST">
      <input type="hidden" name="action" value="deny" />
      <button type="submit" class="btn btn-secondary">Отклонить</button>
    </form>
  </div>
</body>
</html>"""

    # -----------------------------------------------------------------------
    # Token Endpoint (/oauth/token)
    # -----------------------------------------------------------------------

    async def handle_token(self, request: Request) -> Response:
        """Handle POST /oauth/token for authorization_code and refresh_token grants."""
        if request.method != "POST":
            return JSONResponse({"error": "invalid_request", "message": "Method must be POST."}, status_code=405)

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
            except Exception:
                body = {}
        else:
            body = await _parse_form_data(request)

        grant_type = body.get("grant_type")

        # 1. Authorization Code Grant
        if grant_type == "authorization_code":
            code = body.get("code")
            redirect_uri = body.get("redirect_uri")
            client_id = body.get("client_id")
            code_verifier = body.get("code_verifier")

            if not code or not code_verifier:
                return JSONResponse({"error": "invalid_request", "error_description": "code and code_verifier required."}, status_code=400)

            auth_code = self.storage.get_auth_code(code)
            if not auth_code or auth_code.used or time.time() > auth_code.expires_at:
                return JSONResponse({"error": "invalid_grant", "error_description": "Invalid, expired or already used code."}, status_code=400)

            if redirect_uri and auth_code.redirect_uri != redirect_uri:
                return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}, status_code=400)

            # Verify PKCE S256
            if not verify_code_challenge(code_verifier, auth_code.code_challenge, auth_code.code_challenge_method):
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE code_verifier verification failed."}, status_code=400)

            self.storage.consume_auth_code(code)

            raw_access = generate_access_token()
            raw_refresh = generate_refresh_token()

            token = OAuthToken(
                access_token_hash=hash_token(raw_access),
                refresh_token_hash=hash_token(raw_refresh),
                user_id=auth_code.user_id,
                client_id=auth_code.client_id,
                scope=auth_code.scope,
                expires_at=time.time() + ACCESS_TOKEN_LIFETIME,
            )
            self.storage.save_token(token)

            return JSONResponse(
                {
                    "access_token": raw_access,
                    "token_type": "Bearer",
                    "expires_in": ACCESS_TOKEN_LIFETIME,
                    "refresh_token": raw_refresh,
                    "scope": auth_code.scope,
                },
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )

        # 2. Refresh Token Grant
        if grant_type == "refresh_token":
            refresh_token = body.get("refresh_token")
            if not refresh_token:
                return JSONResponse({"error": "invalid_request", "error_description": "refresh_token is required."}, status_code=400)

            rf_hash = hash_token(refresh_token)
            old_token = self.storage.get_token_by_refresh_hash(rf_hash)
            if not old_token or not old_token.is_active:
                return JSONResponse({"error": "invalid_grant", "error_description": "Invalid or revoked refresh_token."}, status_code=400)

            # Revoke old token
            self.storage.revoke_token(old_token.access_token_hash)

            raw_access = generate_access_token()
            raw_refresh = generate_refresh_token()

            new_token = OAuthToken(
                access_token_hash=hash_token(raw_access),
                refresh_token_hash=hash_token(raw_refresh),
                user_id=old_token.user_id,
                client_id=old_token.client_id,
                scope=old_token.scope,
                expires_at=time.time() + ACCESS_TOKEN_LIFETIME,
            )
            self.storage.save_token(new_token)

            return JSONResponse(
                {
                    "access_token": raw_access,
                    "token_type": "Bearer",
                    "expires_in": ACCESS_TOKEN_LIFETIME,
                    "refresh_token": raw_refresh,
                    "scope": old_token.scope,
                },
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )

        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    # -----------------------------------------------------------------------
    # Revocation Endpoint (/oauth/revoke)
    # -----------------------------------------------------------------------

    async def handle_revoke(self, request: Request) -> Response:
        """Handle POST /oauth/revoke (RFC 7009)."""
        form = await _parse_form_data(request)
        token = form.get("token")
        if token:
            t_hash = hash_token(token)
            self.storage.revoke_token(t_hash)
        return JSONResponse({"status": "revoked"})
