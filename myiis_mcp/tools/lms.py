"""Protected MCP tools for personal LMS Moodle courses and materials."""

from __future__ import annotations

from typing import Any

from ..auth.models import AuthenticationRequired, User
from ..auth.session import UpstreamSessionManager
from ..lms.models import (
    MoodleCourse,
    MoodleCourseState,
    MoodlePage,
    MoodleResourceMetadata,
)


def create_lms_tools(session_manager: UpstreamSessionManager):
    """Factory creating authenticated personal LMS Moodle tools."""

    async def lms_get_courses(user: User | None = None) -> list[MoodleCourse]:
        """Получить список доступных учебных курсов студента в СЭО БГУИР (Moodle).

        Возвращает: названия курсов, их ID в системе СЭО и ссылки.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_lms_client(user.id)
        return await client.get_enrolled_courses()

    async def lms_get_course(
        course_id: int,
        user: User | None = None,
    ) -> MoodleCourseState:
        """Получить подробную структуру курса в СЭО: темы, разделы, модули, задания и лекции.

        Использует структурированный AJAX API Moodle (core_courseformat_get_state).
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_lms_client(user.id)
        return await client.get_course_state(course_id=course_id)

    async def lms_get_page(
        module_id: int,
        user: User | None = None,
    ) -> MoodlePage:
        """Прочитать текстовый материал или страницу лекции в СЭО (mod/page) по ID модуля.

        Возвращает: очищенный структурированный текст страницы и ссылки на прикрепленные файлы.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_lms_client(user.id)
        return await client.get_page(module_id=module_id)

    async def lms_get_resource(
        url: str,
        user: User | None = None,
    ) -> dict[str, Any]:
        """Безопасно скачать и получить метаданные учебного файла/документа из СЭО Moodle.

        Проверяет URL по белому списку хостов (SSRF protection) и скачивает файл через авторизованную сессию.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_lms_client(user.id)
        content, meta = await client.download_resource(url=url)
        return {
            "filename": meta.filename,
            "mime_type": meta.mime_type,
            "size_bytes": meta.size_bytes,
            "url": meta.url,
            "downloaded": True,
        }

    return {
        "lms_get_courses": lms_get_courses,
        "lms_get_course": lms_get_course,
        "lms_get_page": lms_get_page,
        "lms_get_resource": lms_get_resource,
    }
