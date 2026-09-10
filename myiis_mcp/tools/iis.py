"""Protected MCP tools for personal student data from BSUIR IIS."""

from __future__ import annotations

from typing import Any

from ..auth.models import AuthenticationRequired, User
from ..auth.session import UpstreamSessionManager
from ..iis.models import (
    IISCertificateItem,
    IISDormitoryInfo,
    IISGradeBook,
    IISGroupInfo,
    IISLibraryBookItem,
    IISMarkbook,
    IISMarkSheetItem,
    IISOmissions,
    IISProfile,
)


def create_iis_tools(session_manager: UpstreamSessionManager):
    """Factory creating authenticated personal IIS tools."""

    async def iis_get_profile(user: User | None = None) -> IISProfile:
        """Получить личный профиль авторизованного студента в ИИС БГУИР.

        Возвращает: ФИО, группу, курс, факультет, специальность, учебный рейтинг и фото.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_profile()

    async def iis_get_markbook(user: User | None = None) -> IISMarkbook:
        """Получить электронную зачётную книжку авторизованного студента.

        Возвращает: номер зачетки, средний балл, оценки по всем семестрам и предметам (экзамены, зачеты, курсовые).
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_markbook()

    async def iis_get_grade_book(user: User | None = None) -> IISGradeBook:
        """Получить текущий журнал отметок студента за текущий семестр.

        Возвращает: список дисциплин и последние выставленные отметки на занятиях.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_grade_book()

    async def iis_get_omissions(
        term: int | None = None,
        user: User | None = None,
    ) -> IISOmissions:
        """Получить статистику пропусков занятий студента.

        Поддерживает фильтрацию по номеру семестра (параметр term, например term=6).
        Возвращает: общее число часов пропусков, пропуски по неуважительной причине и помесячную статистику.
        """
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_omissions(term=term)

    async def iis_get_mark_sheets(user: User | None = None) -> list[IISMarkSheetItem]:
        """Получить экзаменационные ведомости и направления студента (пересдачи, задолженности, допуски)."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_mark_sheets()

    async def iis_get_certificates(user: User | None = None) -> list[IISCertificateItem]:
        """Получить историю и текущие статусы заказанных справок об обучении в БГУИР."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_certificates()

    async def iis_get_library_books(user: User | None = None) -> list[IISLibraryBookItem]:
        """Получить список книг, взятых студентом в библиотеке БГУИР, и сроки их сдачи."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_library_books()

    async def iis_get_dormitory_info(user: User | None = None) -> IISDormitoryInfo:
        """Получить информацию об общежитии студента: номер в очереди, льготы, поощрения и взыскания."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_dormitory_info()

    async def iis_get_group_info(user: User | None = None) -> IISGroupInfo:
        """Получить контакты куратора группы, старосты и список одногруппников."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_group_info()

    async def iis_get_notifications(
        page: int = 0,
        user: User | None = None,
    ) -> dict[str, Any]:
        """Получить количество непрочитанных уведомлений и список уведомлений из ИИС БГУИР."""
        if not user:
            raise AuthenticationRequired()
        client = await session_manager.get_iis_client(user.id)
        return await client.get_notifications(page_number=page)

    return {
        "iis_get_profile": iis_get_profile,
        "iis_get_markbook": iis_get_markbook,
        "iis_get_grade_book": iis_get_grade_book,
        "iis_get_omissions": iis_get_omissions,
        "iis_get_mark_sheets": iis_get_mark_sheets,
        "iis_get_certificates": iis_get_certificates,
        "iis_get_library_books": iis_get_library_books,
        "iis_get_dormitory_info": iis_get_dormitory_info,
        "iis_get_group_info": iis_get_group_info,
        "iis_get_notifications": iis_get_notifications,
    }
