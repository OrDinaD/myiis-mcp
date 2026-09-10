"""Web routes for user account management and BSUIR service linking."""

from __future__ import annotations

import html
import json
import secrets
from typing import Any
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from ..auth.models import UpstreamAuthenticationFailed, UpstreamUnavailable
from ..auth.session import UpstreamSessionManager
from ..auth.storage import StorageRepository


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



class AccountRoutes:
    """Manages /account, /account/link/iis, /account/link/lms endpoints."""

    def __init__(self, session_manager: UpstreamSessionManager, storage: StorageRepository):
        self.session_manager = session_manager
        self.storage = storage

    def _get_or_set_user_id(self, request: Request) -> tuple[str, Response | None]:
        user_id = request.cookies.get("myiis_session")
        if not user_id:
            user_id = f"usr_{secrets.token_urlsafe(16)}"
            self.storage.get_or_create_user(user_id)
            return user_id, None
        return user_id, None

    # -----------------------------------------------------------------------
    # Account Dashboard (/account)
    # -----------------------------------------------------------------------

    async def handle_dashboard(self, request: Request) -> Response:
        """Render user account status dashboard."""
        user_id, _ = self._get_or_set_user_id(request)
        status = self.session_manager.get_account_status(user_id)

        csrf_token = secrets.token_urlsafe(16)

        msg = request.query_params.get("msg", "")
        err = request.query_params.get("err", "")

        banner_html = ""
        if msg:
            banner_html = f'<div class="banner banner-success">✅ {html.escape(msg)}</div>'
        elif err:
            banner_html = f'<div class="banner banner-error">⚠️ {html.escape(err)}</div>'

        iis = status["iis"]
        lms = status["lms"]

        iis_badge = '<span class="badge badge-green">Подключен</span>' if iis["connected"] else '<span class="badge badge-gray">Не подключен</span>'
        lms_badge = '<span class="badge badge-green">Подключен</span>' if lms["connected"] else '<span class="badge badge-gray">Не подключен</span>'

        iis_info = f"<p>👤 {html.escape(iis['fio'] or iis['username'] or '')} ({html.escape(iis['group'] or 'Студент')})</p>" if iis["connected"] else "<p style='color:var(--muted);'>Доступ к зачетке, журналу, пропускам и справкам.</p>"
        lms_info = f"<p>👤 {html.escape(lms['username'] or '')}</p>" if lms["connected"] else "<p style='color:var(--muted);'>Доступ к курсам, темам, модулям и лекциям СЭО.</p>"

        iis_action = """
            <form method="POST" action="/account/unlink/iis" style="display:inline;">
                <input type="hidden" name="csrf" value=""" + f'"{csrf_token}"' + """ />
                <button type="submit" class="btn btn-danger">Отключить</button>
            </form>
        """ if iis["connected"] else '<a href="/account/link/iis" class="btn btn-primary">Подключить ИИС</a>'

        lms_action = """
            <form method="POST" action="/account/unlink/lms" style="display:inline;">
                <input type="hidden" name="csrf" value=""" + f'"{csrf_token}"' + """ />
                <button type="submit" class="btn btn-danger">Отключить</button>
            </form>
        """ if lms["connected"] else '<a href="/account/link/lms" class="btn btn-primary">Подключить СЭО</a>'

        page_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Личный кабинет • MyIIS MCP</title>
  <style>
    :root {{
      --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #f8fafc;
      --muted: #94a3b8; --primary: #0284c7; --primary-hover: #0369a1;
      --green: #10b981; --red: #ef4444;
    }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 32px 16px; display: flex; justify-content: center; }}
    .container {{ max-width: 640px; width: 100%; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }}
    h1 {{ font-size: 24px; font-weight: 700; margin: 0; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; margin-bottom: 20px; }}
    .card-title {{ font-size: 16px; font-weight: 600; display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
    .badge {{ padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; }}
    .badge-green {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .badge-gray {{ background: #334155; color: #94a3b8; }}
    .btn {{ padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; text-decoration: none; border: none; cursor: pointer; display: inline-block; }}
    .btn-primary {{ background: var(--primary); color: white; }}
    .btn-primary:hover {{ background: var(--primary-hover); }}
    .btn-danger {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
    .btn-danger:hover {{ background: rgba(239, 68, 68, 0.3); }}
    .banner {{ padding: 12px 16px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; }}
    .banner-success {{ background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; }}
    .banner-error {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }}
    .footer-note {{ font-size: 12px; color: var(--muted); text-align: center; margin-top: 30px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>Личный кабинет MyIIS</h1>
        <div style="font-size:13px;color:var(--muted)">Связывание аккаунтов БГУИР с ChatGPT / Codex</div>
      </div>
      <a href="/logs" style="color:var(--muted);font-size:12px;text-decoration:none;">📡 Логи</a>
    </div>

    {banner_html}

    <div class="card">
      <div class="card-title">
        <span>🏛️ ИИС БГУИР (iis.bsuir.by)</span>
        {iis_badge}
      </div>
      {iis_info}
      <div style="margin-top:16px;">
        {iis_action}
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>📚 СЭО Moodle (lms.bsuir.by)</span>
        {lms_badge}
      </div>
      {lms_info}
      <div style="margin-top:16px;">
        {lms_action}
      </div>
    </div>

    <div class="footer-note">
      🔒 <strong>Безопасность:</strong> Ваши пароли никогда не передаются в ChatGPT/OpenAI.<br/>
      Сессионные cookies хранятся в зашифрованном виде (AEAD AES-256-GCM) с привязкой к вашему аккаунту.<br/>
      При отключении аккаунта сохраненные сессии немедленно удаляются.
    </div>
  </div>
</body>
</html>"""
        resp = HTMLResponse(page_html)
        resp.set_cookie("myiis_session", user_id, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
        resp.set_cookie("myiis_csrf", csrf_token, max_age=3600, httponly=True, samesite="lax", secure=True)
        return resp

    # -----------------------------------------------------------------------
    # Link IIS (/account/link/iis)
    # -----------------------------------------------------------------------

    async def handle_link_iis(self, request: Request) -> Response:
        """Form and POST handler to link personal IIS account."""
        user_id, _ = self._get_or_set_user_id(request)

        if request.method == "POST":
            form = await _parse_form_data(request)
            csrf = form.get("csrf")
            expected_csrf = request.cookies.get("myiis_csrf")
            if not csrf or csrf != expected_csrf:
                return RedirectResponse("/account?err=Ошибка+проверки+CSRF.+Попробуйте+снова.", status_code=302)

            username = str(form.get("username", "")).strip()
            password = str(form.get("password", ""))
            keep_signed_in = bool(form.get("keep_signed_in"))

            if not username or not password:
                return RedirectResponse("/account/link/iis?err=Заполните+логин+и+пароль.", status_code=302)

            try:
                profile = await self.session_manager.link_iis(
                    user_id=user_id,
                    username=username,
                    password=password,
                    keep_signed_in=keep_signed_in,
                )
                return RedirectResponse(f"/account?msg=ИИС+успешно+подключен!+Добро+пожаловать,+{html.escape(profile.fio)}", status_code=302)
            except UpstreamAuthenticationFailed as exc:
                return RedirectResponse(f"/account/link/iis?err={html.escape(exc.message)}", status_code=302)
            except UpstreamUnavailable as exc:
                return RedirectResponse(f"/account/link/iis?err={html.escape(exc.message)}", status_code=302)
            except Exception as exc:
                return RedirectResponse(f"/account/link/iis?err=Ошибка+подключения:+{html.escape(str(exc))}", status_code=302)

        # GET: render form
        csrf_token = secrets.token_urlsafe(16)
        err = request.query_params.get("err", "")
        err_html = f'<div class="banner banner-error">⚠️ {html.escape(err)}</div>' if err else ""

        html_page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подключение ИИС БГУИР • MyIIS</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; max-width: 440px; width: 100%; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 6px; }}
    p {{ color: #94a3b8; font-size: 13px; line-height: 1.5; margin-bottom: 20px; }}
    .form-group {{ margin-bottom: 16px; }}
    label {{ display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #cbd5e1; }}
    input[type="text"], input[type="password"] {{
      width: 100%; box-sizing: border-box; padding: 10px 14px; background: #0f172a; border: 1px solid #334155;
      border-radius: 8px; color: white; font-size: 14px; outline: none;
    }}
    input:focus {{ border-color: #0284c7; }}
    .checkbox-group {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; margin: 16px 0; }}
    .btn {{ width: 100%; padding: 12px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; background: #0284c7; color: white; }}
    .btn:hover {{ background: #0369a1; }}
    .banner {{ padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }}
    .banner-error {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🏛️ Подключение ИИС БГУИР</h1>
    <p>Введите логин и пароль от личного кабинета <code>iis.bsuir.by</code>. Пароль проверяется сервером БГУИР и не попадает в модель ChatGPT.</p>

    {err_html}

    <form method="POST">
      <input type="hidden" name="csrf" value="{csrf_token}" />
      <div class="form-group">
        <label>Логин в ИИС (номер студ. билета или логин)</label>
        <input type="text" name="username" required autocomplete="username" placeholder="Например: 42060301" />
      </div>
      <div class="form-group">
        <label>Пароль от ИИС</label>
        <input type="password" name="password" required autocomplete="current-password" placeholder="••••••••" />
      </div>
      <div class="checkbox-group">
        <input type="checkbox" name="keep_signed_in" id="keep" value="1" />
        <label for="keep" style="margin:0;cursor:pointer;">Запомнить для автоматического продления сессии</label>
      </div>
      <button type="submit" class="btn">Войти и подключить</button>
      <div style="text-align:center;margin-top:14px;">
        <a href="/account" style="color:#94a3b8;font-size:13px;text-decoration:none;">&larr; Назад в кабинет</a>
      </div>
    </form>
  </div>
</body>
</html>"""
        resp = HTMLResponse(html_page)
        resp.set_cookie("myiis_session", user_id, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
        resp.set_cookie("myiis_csrf", csrf_token, max_age=3600, httponly=True, samesite="lax", secure=True)
        return resp

    # -----------------------------------------------------------------------
    # Link LMS (/account/link/lms)
    # -----------------------------------------------------------------------

    async def handle_link_lms(self, request: Request) -> Response:
        """Form and POST handler to link personal LMS Moodle account."""
        user_id, _ = self._get_or_set_user_id(request)

        if request.method == "POST":
            form = await _parse_form_data(request)
            csrf = form.get("csrf")
            expected_csrf = request.cookies.get("myiis_csrf")
            if not csrf or csrf != expected_csrf:
                return RedirectResponse("/account?err=Ошибка+проверки+CSRF.", status_code=302)

            username = str(form.get("username", "")).strip()
            password = str(form.get("password", ""))
            keep_signed_in = bool(form.get("keep_signed_in"))

            if not username or not password:
                return RedirectResponse("/account/link/lms?err=Заполните+логин+и+пароль.", status_code=302)

            try:
                await self.session_manager.link_lms(
                    user_id=user_id,
                    username=username,
                    password=password,
                    keep_signed_in=keep_signed_in,
                )
                return RedirectResponse("/account?msg=СЭО+Moodle+успешно+подключен!", status_code=302)
            except UpstreamAuthenticationFailed as exc:
                return RedirectResponse(f"/account/link/lms?err={html.escape(exc.message)}", status_code=302)
            except UpstreamUnavailable as exc:
                return RedirectResponse(f"/account/link/lms?err={html.escape(exc.message)}", status_code=302)
            except Exception as exc:
                return RedirectResponse(f"/account/link/lms?err=Ошибка+подключения:+{html.escape(str(exc))}", status_code=302)

        csrf_token = secrets.token_urlsafe(16)
        err = request.query_params.get("err", "")
        err_html = f'<div class="banner banner-error">⚠️ {html.escape(err)}</div>' if err else ""

        html_page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Подключение СЭО Moodle • MyIIS</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; max-width: 440px; width: 100%; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 6px; }}
    p {{ color: #94a3b8; font-size: 13px; line-height: 1.5; margin-bottom: 20px; }}
    .form-group {{ margin-bottom: 16px; }}
    label {{ display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: #cbd5e1; }}
    input[type="text"], input[type="password"] {{
      width: 100%; box-sizing: border-box; padding: 10px 14px; background: #0f172a; border: 1px solid #334155;
      border-radius: 8px; color: white; font-size: 14px; outline: none;
    }}
    input:focus {{ border-color: #0284c7; }}
    .checkbox-group {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; margin: 16px 0; }}
    .btn {{ width: 100%; padding: 12px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; background: #0284c7; color: white; }}
    .btn:hover {{ background: #0369a1; }}
    .banner {{ padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }}
    .banner-error {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>📚 Подключение СЭО Moodle</h1>
    <p>Введите логин и пароль от системы дистанционного обучения <code>lms.bsuir.by</code>.</p>

    {err_html}

    <form method="POST">
      <input type="hidden" name="csrf" value="{csrf_token}" />
      <div class="form-group">
        <label>Логин в СЭО Moodle</label>
        <input type="text" name="username" required autocomplete="username" placeholder="Ваш логин в СЭО" />
      </div>
      <div class="form-group">
        <label>Пароль от СЭО Moodle</label>
        <input type="password" name="password" required autocomplete="current-password" placeholder="••••••••" />
      </div>
      <div class="checkbox-group">
        <input type="checkbox" name="keep_signed_in" id="keep_lms" value="1" />
        <label for="keep_lms" style="margin:0;cursor:pointer;">Запомнить для автоматического продления сессии</label>
      </div>
      <button type="submit" class="btn">Войти и подключить</button>
      <div style="text-align:center;margin-top:14px;">
        <a href="/account" style="color:#94a3b8;font-size:13px;text-decoration:none;">&larr; Назад в кабинет</a>
      </div>
    </form>
  </div>
</body>
</html>"""
        resp = HTMLResponse(html_page)
        resp.set_cookie("myiis_session", user_id, max_age=86400 * 30, httponly=True, samesite="lax", secure=True)
        resp.set_cookie("myiis_csrf", csrf_token, max_age=3600, httponly=True, samesite="lax", secure=True)
        return resp

    # -----------------------------------------------------------------------
    # Unlink Actions
    # -----------------------------------------------------------------------

    async def handle_unlink_iis(self, request: Request) -> Response:
        """Unlink IIS account."""
        user_id, _ = self._get_or_set_user_id(request)
        await self.session_manager.unlink_iis(user_id)
        return RedirectResponse("/account?msg=ИИС+отключен.", status_code=302)

    async def handle_unlink_lms(self, request: Request) -> Response:
        """Unlink LMS account."""
        user_id, _ = self._get_or_set_user_id(request)
        await self.session_manager.unlink_lms(user_id)
        return RedirectResponse("/account?msg=СЭО+отключено.", status_code=302)
