"""Authenticated HTTP client for BSUIR LMS Moodle (СЭО БГУИР)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from ..auth.models import (
    MoodleAPIError,
    MoodleSesskeyExpired,
    ResourceNotFound,
    UpstreamAuthenticationFailed,
    UpstreamSessionExpired,
    UpstreamUnavailable,
)
from ..security.redaction import validate_upstream_url
from .models import (
    MoodleCourse,
    MoodleCourseState,
    MoodleModule,
    MoodlePage,
    MoodleResourceMetadata,
    MoodleSection,
)

logger = logging.getLogger(__name__)

LMS_BASE_URL = "https://lms.bsuir.by"
DEFAULT_TIMEOUT = 15.0


def _extract_sesskey(html: str) -> str | None:
    """Extract Moodle sesskey from HTML M.cfg script block."""
    m = re.search(r'\"sesskey\":\s*\"([a-zA-Z0-9]+)\"', html)
    if m:
        return m.group(1)
    m = re.search(r'name=\"sesskey\"\s+value=\"([a-zA-Z0-9]+)\"', html)
    if m:
        return m.group(1)
    return None


def _clean_html(html: str) -> str:
    """Convert HTML content to clean readable plain/markdown text."""
    if not html:
        return ""
    # Replace breaks and paragraphs with newlines
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n### \1\n', text, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining tags
    text = re.sub(r'<[^<]+?>', '', text)
    # Normalize whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class MoodleClient:
    """Session-based HTTP client for personal LMS Moodle BSUIR account."""

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        sesskey: str | None = None,
        base_url: str = LMS_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sesskey = sesskey
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies=cookies or {},
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ru,en;q=0.9",
            },
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Close underlying HTTP client session."""
        await self._client.aclose()

    async def __aenter__(self) -> MoodleClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def export_cookies(self) -> dict[str, str]:
        """Export session cookies dictionary."""
        return {k: v for k, v in self._client.cookies.items()}

    # -----------------------------------------------------------------------
    # Authentication & Session Verification
    # -----------------------------------------------------------------------

    async def login(
        self,
        username: str,
        password: str,
    ) -> tuple[dict[str, str], str]:
        """Log in to LMS Moodle using web session credentials.

        Returns tuple of (session_cookies, sesskey).
        Raises UpstreamAuthenticationFailed on invalid login/password.
        """
        data = {
            "username": username.strip(),
            "password": password,
        }
        try:
            resp = await self._client.post("/login/index.php", data=data)
        except httpx.RequestError as exc:
            raise UpstreamUnavailable("lms", f"Не удалось подключиться к серверу СЭО: {exc}") from exc

        html = resp.text

        # Check for authentication failure
        if "Неверный логин или пароль" in html or "Invalid login" in html:
            raise UpstreamAuthenticationFailed("lms", "Неверный логин или пароль для СЭО БГУИР.")

        # If redirected back to login page
        if "/login/index.php" in str(resp.url) and "loginbox" in html:
            raise UpstreamAuthenticationFailed("lms", "Не удалось войти в СЭО БГУИР (проверьте логин/пароль).")

        sesskey = _extract_sesskey(html)
        if not sesskey:
            # Try fetching homepage to extract sesskey
            home_resp = await self._client.get("/")
            sesskey = _extract_sesskey(home_resp.text)

        if not sesskey:
            raise UpstreamAuthenticationFailed("lms", "Сессия создана, но sesskey Moodle не обнаружен.")

        self.sesskey = sesskey
        return self.export_cookies(), sesskey

    async def refresh_sesskey(self) -> str:
        """Fetch fresh homepage to renew sesskey."""
        resp = await self._client.get("/")
        new_sess = _extract_sesskey(resp.text)
        if not new_sess:
            raise UpstreamSessionExpired("lms", "Сессия СЭО устарела. Требуется повторный вход.")
        self.sesskey = new_sess
        return new_sess

    # -----------------------------------------------------------------------
    # Moodle AJAX RPC Service
    # -----------------------------------------------------------------------

    async def call_ajax(
        self,
        methodname: str,
        args: dict[str, Any],
        retry_on_sesskey: bool = True,
    ) -> Any:
        """Call structured Moodle AJAX service (lib/ajax/service.php)."""
        if not self.sesskey:
            await self.refresh_sesskey()

        url = f"/lib/ajax/service.php?sesskey={self.sesskey}&info={methodname}"
        payload = [{"index": 0, "methodname": methodname, "args": args}]

        try:
            resp = await self._client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        except httpx.RequestError as exc:
            raise UpstreamUnavailable("lms", f"Ошибка AJAX-запроса к СЭО: {exc}") from exc

        if resp.status_code in (401, 403):
            raise UpstreamSessionExpired("lms", "Сессия СЭО истекла.")

        try:
            data = resp.json()
        except Exception as exc:
            raise MoodleAPIError(f"Некорректный JSON от СЭО AJAX: {exc}") from exc

        if isinstance(data, list) and data:
            item = data[0]
            if item.get("error"):
                exc_info = item.get("exception", {})
                error_msg = exc_info.get("message", "Неизвестная ошибка Moodle")

                # If sesskey expired, refresh and retry once
                if "sesskey" in error_msg.lower() and retry_on_sesskey:
                    await self.refresh_sesskey()
                    return await self.call_ajax(methodname, args, retry_on_sesskey=False)

                raise MoodleAPIError(f"Ошибка Moodle API: {error_msg}")

            raw_result = item.get("data")
            if isinstance(raw_result, str):
                try:
                    return json.loads(raw_result)
                except Exception:
                    return raw_result
            return raw_result

        return data

    # -----------------------------------------------------------------------
    # Courses
    # -----------------------------------------------------------------------

    async def get_enrolled_courses(self) -> list[MoodleCourse]:
        """Fetch list of user enrolled courses from Moodle dashboard/homepage."""
        resp = await self._client.get("/")
        html = resp.text

        if "/login/index.php" in str(resp.url) and "loginbox" in html:
            raise UpstreamSessionExpired("lms", "Сессия СЭО истекла.")

        courses_map: dict[int, str] = {}

        # Parse course links and titles
        pattern = re.compile(r'<a[^>]+href=[\"\'\`](https://lms\.bsuir\.by/course/view\.php\?id=(\d+)|/course/view\.php\?id=(\d+))[\"\'\`][^>]*>(.*?)</a>', re.DOTALL)
        for m in pattern.finditer(html):
            cid_str = m.group(2) or m.group(3)
            if not cid_str:
                continue
            cid = int(cid_str)
            raw_title = m.group(4)
            clean_title = re.sub(r'<[^<]+?>', '', raw_title).strip()
            # Filter out non-course button texts
            if clean_title and len(clean_title) > 3 and not clean_title.startswith("Перейти к"):
                if cid not in courses_map or len(clean_title) > len(courses_map[cid]):
                    courses_map[cid] = clean_title

        courses: list[MoodleCourse] = []
        for cid, title in sorted(courses_map.items()):
            courses.append(
                MoodleCourse(
                    id=cid,
                    fullname=title,
                    url=f"{self.base_url}/course/view.php?id={cid}",
                )
            )
        return courses

    async def get_course_state(self, course_id: int) -> MoodleCourseState:
        """Fetch full course structure (sections and modules) using core_courseformat_get_state."""
        data = await self.call_ajax("core_courseformat_get_state", {"courseid": course_id})
        if not isinstance(data, dict):
            raise MoodleAPIError("Не удалось получить структуру курса от СЭО.")

        raw_course = data.get("course", {})
        raw_sections = data.get("section", [])
        raw_cms = data.get("cm", [])

        # Build module mapping by section id
        modules_by_section: dict[int, list[MoodleModule]] = {}
        for cm in raw_cms:
            sec_id = cm.get("sectionid")
            mod = MoodleModule(
                id=int(cm.get("id", 0)),
                name=cm.get("name", "Без названия"),
                modname=cm.get("modname", "unknown"),
                url=cm.get("url"),
                uservisible=bool(cm.get("uservisible", True)),
                section_id=sec_id,
                section_number=cm.get("sectionnumber"),
            )
            modules_by_section.setdefault(sec_id, []).append(mod)

        sections: list[MoodleSection] = []
        for sec in raw_sections:
            sec_id = int(sec.get("id", 0))
            sections.append(
                MoodleSection(
                    id=sec_id,
                    number=int(sec.get("number", 0) or 0),
                    title=sec.get("title") or sec.get("rawtitle") or f"Тема {sec.get('number', '')}",
                    section_url=sec.get("sectionurl"),
                    modules=modules_by_section.get(sec_id, []),
                )
            )

        course_name = raw_course.get("fullname") or f"Курс #{course_id}"
        return MoodleCourseState(
            course_id=course_id,
            fullname=course_name,
            sections=sections,
        )

    # -----------------------------------------------------------------------
    # Course Page & Text Materials (mod_page)
    # -----------------------------------------------------------------------

    async def get_page(self, module_id: int) -> MoodlePage:
        """Fetch and parse content of a Moodle text page (mod/page/view.php?id=...)."""
        url = f"/mod/page/view.php?id={module_id}"
        resp = await self._client.get(url)
        if resp.status_code == 404:
            raise ResourceNotFound(f"Страница #{module_id} не найдена в СЭО.")
        if "/login/index.php" in str(resp.url):
            raise UpstreamSessionExpired("lms", "Сессия СЭО истекла.")

        html = resp.text

        title_m = re.search(r'<title>(.*?)</title>', html)
        title = title_m.group(1).split('|')[0].strip() if title_m else f"Страница #{module_id}"

        # Extract main content container
        content_html = ""
        main_m = re.search(r'<div role=\"main\"[^>]*>(.*?)</div>\s*</section>', html, re.DOTALL)
        if main_m:
            content_html = main_m.group(1)
        else:
            gen_m = re.search(r'<div class=\"box py-3 generalbox\"[^>]*>(.*?)</div>', html, re.DOTALL)
            if gen_m:
                content_html = gen_m.group(1)
            else:
                content_html = html

        clean_text = _clean_html(content_html)

        # Extract links in the page
        links: list[dict[str, str]] = []
        for lm in re.finditer(r'<a[^>]+href=[\"\'\`]([^\"\'\`]+)[\"\'\`][^>]*>(.*?)</a>', content_html, re.DOTALL):
            href = lm.group(1)
            link_text = re.sub(r'<[^<]+?>', '', lm.group(2)).strip()
            if href.startswith("/") or "bsuir.by" in href:
                links.append({"title": link_text or href, "url": href})

        return MoodlePage(
            module_id=module_id,
            title=title,
            clean_text=clean_text,
            body_html=content_html,
            links=links,
        )

    # -----------------------------------------------------------------------
    # Authenticated File / Resource Download with SSRF Protection
    # -----------------------------------------------------------------------

    async def download_resource(
        self,
        url: str,
        max_bytes: int = 15 * 1024 * 1024,
    ) -> tuple[bytes, MoodleResourceMetadata]:
        """Safely download file or document from Moodle with strict SSRF checks."""
        # Normalize relative URLs
        if url.startswith("/"):
            url = f"{self.base_url}{url}"

        if not validate_upstream_url(url, raise_error=False):
            raise ValueError(f"URL не прошел проверку безопасности (SSRF): {url}")

        parsed = urlparse(url)
        if parsed.hostname != "lms.bsuir.by":
            raise ValueError("Разрешено скачивание ресурсов только с lms.bsuir.by.")

        try:
            resp = await self._client.get(url)
        except httpx.RequestError as exc:
            raise UpstreamUnavailable("lms", f"Ошибка скачивания файла: {exc}") from exc

        if resp.status_code == 404:
            raise ResourceNotFound(f"Файл не найден: {url}")
        if resp.status_code in (401, 403) or "/login/index.php" in str(resp.url):
            raise UpstreamSessionExpired("lms", "Сессия истекла при попытке скачать файл.")

        content = resp.content
        if len(content) > max_bytes:
            raise ValueError(f"Размер файла превышает лимит ({len(content)} > {max_bytes} байт).")

        # Extract filename
        cd = resp.headers.get("Content-Disposition", "")
        fn_match = re.search(r'filename=[\"\']?([^\"\';]+)', cd)
        filename = fn_match.group(1) if fn_match else parsed.path.split("/")[-1] or "downloaded_file"

        mime = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()

        meta = MoodleResourceMetadata(
            url=url,
            filename=filename,
            mime_type=mime,
            size_bytes=len(content),
        )
        return content, meta
