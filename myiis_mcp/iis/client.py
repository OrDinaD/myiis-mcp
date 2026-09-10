"""Authenticated HTTP client for BSUIR IIS personal student cabinet."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..auth.models import (
    IISAPIError,
    UpstreamAuthenticationFailed,
    UpstreamSessionExpired,
    UpstreamUnavailable,
)
from .models import (
    GradeBookLesson,
    IISCertificateItem,
    IISDormitoryInfo,
    IISGradeBook,
    IISGroupInfo,
    IISLibraryBookItem,
    IISMarkbook,
    IISMarkSheetItem,
    IISOmissions,
    IISProfile,
    MarkItem,
    OmissionRecord,
    TermMarkPage,
)

logger = logging.getLogger(__name__)

IIS_BASE_URL = "https://iis.bsuir.by/api/v1"
DEFAULT_TIMEOUT = 15.0


class IISAuthenticatedClient:
    """Session-based HTTP client for personal IIS BSUIR student account."""

    def __init__(
        self,
        cookies: dict[str, str] | None = None,
        base_url: str = IIS_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies=cookies or {},
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru,en;q=0.9",
            },
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Close underlying HTTP client session."""
        await self._client.aclose()

    async def __aenter__(self) -> IISAuthenticatedClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def export_cookies(self) -> dict[str, str]:
        """Export session cookies dictionary."""
        return {k: v for k, v in self._client.cookies.items()}

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute request with session expiration and error handling."""
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise UpstreamUnavailable("iis", f"Таймаут обращения к ИИС БГУИР: {exc}") from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailable("iis", f"Ошибка соединения с ИИС БГУИР: {exc}") from exc

        if resp.status_code in (401, 403):
            raise UpstreamSessionExpired("iis", "Сессия ИИС истекла или не авторизована.")
        if resp.status_code >= 500:
            raise IISAPIError(f"Ошибка сервера ИИС: HTTP {resp.status_code}", resp.status_code)
        return resp

    # -----------------------------------------------------------------------
    # Authentication & Session Verification
    # -----------------------------------------------------------------------

    async def login(
        self,
        username: str,
        password: str,
        remember_device: bool = True,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        """Log in to IIS BSUIR using username and password.

        Returns tuple of (session_cookies, profile_dict).
        Raises UpstreamAuthenticationFailed on invalid credentials.
        """
        payload = {
            "username": username.strip(),
            "password": password,
            "rememberDevice": remember_device,
        }
        try:
            resp = await self._client.post("/auth/login", json=payload)
        except httpx.RequestError as exc:
            raise UpstreamUnavailable("iis", f"Не удалось подключиться к серверу входа ИИС: {exc}") from exc

        if resp.status_code in (400, 401, 403):
            raise UpstreamAuthenticationFailed("iis", "Неверный логин или пароль для ИИС БГУИР.")
        if resp.status_code != 200:
            raise IISAPIError(f"Неожиданный ответ сервера при входе: {resp.status_code}", resp.status_code)

        try:
            login_data = resp.json()
        except Exception:
            login_data = {}

        # Perform control check to verify session cookies are valid
        control_resp = await self._request("GET", "/profiles/personal-profile")
        if control_resp.status_code != 200:
            raise UpstreamAuthenticationFailed("iis", "Контрольный запрос профиля не удался после входа.")

        return self.export_cookies(), login_data

    async def logout(self) -> None:
        """Log out from IIS session."""
        try:
            await self._client.get("/auth/logout")
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Student Profile
    # -----------------------------------------------------------------------

    async def get_profile(self) -> IISProfile:
        """Fetch student personal profile, contact info, and group."""
        resp = await self._request("GET", "/profiles/personal-profile")
        p_data = resp.json()

        # Try to enrich with contacts and academic info
        info_data: dict[str, Any] = {}
        try:
            i_resp = await self._request("GET", "/personal-information")
            if i_resp.status_code == 200:
                info_data = i_resp.json()
        except Exception:
            pass

        fio = " ".join(
            filter(
                None,
                [p_data.get("lastName"), p_data.get("firstName"), p_data.get("middleName")],
            )
        )
        bel_fio = " ".join(
            filter(
                None,
                [
                    p_data.get("belarusianLastName"),
                    p_data.get("belarusianFirstName"),
                    p_data.get("belarusianMiddleName"),
                ],
            )
        )

        return IISProfile(
            fio=fio,
            username=p_data.get("username", ""),
            email=info_data.get("email") or p_data.get("email"),
            phone=info_data.get("phone") or p_data.get("phone"),
            group=p_data.get("studentGroupDto", {}).get("name") if isinstance(p_data.get("studentGroupDto"), dict) else p_data.get("group"),
            course=info_data.get("course") or (p_data.get("studentGroupDto", {}).get("course") if isinstance(p_data.get("studentGroupDto"), dict) else None),
            faculty=p_data.get("faculty") or (p_data.get("studentGroupDto", {}).get("faculty") if isinstance(p_data.get("studentGroupDto"), dict) else None),
            speciality=p_data.get("speciality"),
            rating=p_data.get("rating"),
            photo_url=p_data.get("photoUrl"),
            birth_date=p_data.get("birthDate"),
            is_group_head=bool(p_data.get("isGroupHead")),
            belarusian_fio=bel_fio if bel_fio else None,
        )

    # -----------------------------------------------------------------------
    # Markbook (Электронная зачётка)
    # -----------------------------------------------------------------------

    async def get_markbook(self) -> IISMarkbook:
        """Fetch complete electronic markbook with semesters, subjects and marks."""
        resp = await self._request("GET", "/markbook")
        data = resp.json()

        number = str(data.get("number", ""))
        avg_mark = float(data.get("averageMark", 0.0) or 0.0)
        mark_pages = data.get("markPages", {})

        terms: list[TermMarkPage] = []
        if isinstance(mark_pages, dict):
            for term_str, page in sorted(mark_pages.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
                term_num = int(term_str) if term_str.isdigit() else 0
                term_avg = page.get("averageMark")
                raw_marks = page.get("marks", [])
                marks_list: list[MarkItem] = []
                for m in raw_marks:
                    marks_list.append(
                        MarkItem(
                            subject=m.get("subject", ""),
                            form_of_control=m.get("formOfControl", ""),
                            mark=m.get("mark"),
                            hours=m.get("hours"),
                            teacher=m.get("teacher"),
                            date=m.get("date"),
                            retakes_count=int(m.get("retakesCount", 0) or 0),
                        )
                    )
                terms.append(
                    TermMarkPage(
                        term_number=term_num,
                        average_mark=float(term_avg) if term_avg is not None else None,
                        marks=marks_list,
                    )
                )

        return IISMarkbook(
            number=number,
            average_mark=avg_mark,
            terms=terms,
        )

    # -----------------------------------------------------------------------
    # Grade Book (Журнал текущих оценок)
    # -----------------------------------------------------------------------

    async def get_grade_book(self) -> IISGradeBook:
        """Fetch current term journal subjects and recent marks."""
        subjects: list[str] = []
        recent_marks: list[GradeBookLesson] = []

        try:
            s_resp = await self._request("GET", "/grade-book/subjects")
            if s_resp.status_code == 200:
                raw_s = s_resp.json()
                if isinstance(raw_s, list):
                    subjects = [str(s) for s in raw_s]
                elif isinstance(raw_s, dict):
                    subjects = list(raw_s.keys())
        except Exception:
            pass

        try:
            g_resp = await self._request("GET", "/grade-book")
            if g_resp.status_code == 200:
                raw_g = g_resp.json()
                # Grade-book returns lessons or students structure
                if isinstance(raw_g, list):
                    for item in raw_g:
                        if isinstance(item, dict):
                            for lesson in item.get("lessons", []):
                                recent_marks.append(
                                    GradeBookLesson(
                                        date=lesson.get("date", ""),
                                        subject=lesson.get("subject", ""),
                                        lesson_type=lesson.get("lessonType", ""),
                                        mark=lesson.get("mark"),
                                        note=lesson.get("note"),
                                    )
                                )
        except Exception:
            pass

        return IISGradeBook(subjects=subjects, recent_marks=recent_marks)

    # -----------------------------------------------------------------------
    # Omissions (Пропуски занятий)
    # -----------------------------------------------------------------------

    async def get_omissions(self, term: int | None = None) -> IISOmissions:
        """Fetch student absence statistics and detailed omission records."""
        path = f"/omissions-by-student?term={term}" if term else "/omissions-by-student"
        resp = await self._request("GET", path)
        data = resp.json()

        records: list[OmissionRecord] = []
        raw_list = data.get("omissionDtoList", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        total_hours = 0
        disrespectful_hours = 0

        for item in raw_list:
            hours = int(item.get("hours", 0) or 0)
            total_hours += hours
            records.append(
                OmissionRecord(
                    date=item.get("date", ""),
                    subject=item.get("subject", ""),
                    lesson_type=item.get("lessonTypeAbbrev", ""),
                    hours=hours,
                    is_disrespectful=False,
                    term=item.get("term"),
                )
            )

        # Disrespectful omissions
        try:
            d_resp = await self._request("GET", "/disrespectful-omissions-by-student")
            if d_resp.status_code == 200:
                d_list = d_resp.json()
                if isinstance(d_list, list):
                    for item in d_list:
                        hours = int(item.get("hours", 0) or 0)
                        disrespectful_hours += hours
                        records.append(
                            OmissionRecord(
                                date=item.get("date", ""),
                                subject=item.get("subject", ""),
                                lesson_type=item.get("lessonTypeAbbrev", ""),
                                hours=hours,
                                is_disrespectful=True,
                                term=item.get("term"),
                            )
                        )
        except Exception:
            pass

        # Monthly summary
        monthly_counts: list[dict[str, Any]] = []
        try:
            m_resp = await self._request("GET", "/omission-count-by-student-for-semester")
            if m_resp.status_code == 200:
                m_data = m_resp.json()
                if isinstance(m_data, list):
                    monthly_counts = m_data
        except Exception:
            pass

        return IISOmissions(
            total_hours=total_hours + disrespectful_hours,
            disrespectful_hours=disrespectful_hours,
            records=records,
            monthly_counts=monthly_counts,
        )

    # -----------------------------------------------------------------------
    # Examination Mark Sheets (Ведомости и направления)
    # -----------------------------------------------------------------------

    async def get_mark_sheets(self) -> list[IISMarkSheetItem]:
        """Fetch examination mark sheets / directions."""
        resp = await self._request("GET", "/mark-sheet")
        data = resp.json()
        items: list[IISMarkSheetItem] = []
        if isinstance(data, list):
            for row in data:
                items.append(
                    IISMarkSheetItem(
                        id=row.get("id", ""),
                        subject=row.get("subject", ""),
                        sheet_type=row.get("markSheetTypeDto", {}).get("fullName", "") if isinstance(row.get("markSheetTypeDto"), dict) else "",
                        term=int(row.get("term", 0) or 0),
                        teacher=row.get("employeeDto", {}).get("fio") if isinstance(row.get("employeeDto"), dict) else None,
                        status=row.get("status"),
                        price=row.get("price"),
                    )
                )
        return items

    # -----------------------------------------------------------------------
    # Certificates (Заказ справок)
    # -----------------------------------------------------------------------

    async def get_certificates(self) -> list[IISCertificateItem]:
        """Fetch student official certificate requests and their statuses."""
        resp = await self._request("GET", "/certificate")
        data = resp.json()
        items: list[IISCertificateItem] = []
        if isinstance(data, list):
            for row in data:
                items.append(
                    IISCertificateItem(
                        id=row.get("id", ""),
                        number=str(row.get("number", "")),
                        provision_place=row.get("provisionPlace", ""),
                        date_order=row.get("dateOrder"),
                        issue_date=row.get("issueDate"),
                        certificate_type=row.get("certificateType"),
                        status=row.get("status"),
                        rejection_reason=row.get("rejectionReason"),
                    )
                )
        return items

    # -----------------------------------------------------------------------
    # Library Books (Библиотека БГУИР)
    # -----------------------------------------------------------------------

    async def get_library_books(self) -> list[IISLibraryBookItem]:
        """Fetch student borrowed library books."""
        resp = await self._request("GET", "/library/books")
        data = resp.json()
        items: list[IISLibraryBookItem] = []
        if isinstance(data, list):
            for row in data:
                items.append(
                    IISLibraryBookItem(
                        title=row.get("name", "") or row.get("title", ""),
                        author=row.get("author"),
                        take_date=row.get("takeDate"),
                        return_date=row.get("returnDate"),
                        is_overdue=bool(row.get("isOverdue")),
                    )
                )
        return items

    # -----------------------------------------------------------------------
    # Dormitory (Общежитие)
    # -----------------------------------------------------------------------

    async def get_dormitory_info(self) -> IISDormitoryInfo:
        """Fetch dormitory application, queue position, privileges and status."""
        resp = await self._request("GET", "/dormitory-queue-application")
        data = resp.json()

        has_app = False
        queue_num = None
        status = None
        app_date = None
        settled_date = None

        if isinstance(data, list) and data:
            row = data[0]
            has_app = True
            queue_num = row.get("numberInQueue") or row.get("number")
            status = row.get("status")
            app_date = row.get("applicationDate")
            settled_date = row.get("settledDate")
        elif isinstance(data, dict) and data:
            has_app = True
            queue_num = data.get("numberInQueue") or data.get("number")
            status = data.get("status")
            app_date = data.get("applicationDate")
            settled_date = data.get("settledDate")

        privileges: list[str] = []
        try:
            p_resp = await self._request("GET", "/dormitory-queue-application/privileges")
            if p_resp.status_code == 200:
                p_list = p_resp.json()
                if isinstance(p_list, list):
                    privileges = [
                        item.get("dormitoryPrivilegeCategoryName", "")
                        for item in p_list
                        if isinstance(item, dict) and item.get("dormitoryPrivilegeCategoryName")
                    ]
        except Exception:
            pass

        penalties_premiums: list[str] = []
        try:
            pp_resp = await self._request("GET", "/dormitory-queue-application/premium-penalty")
            if pp_resp.status_code == 200:
                pp_list = pp_resp.json()
                if isinstance(pp_list, list):
                    penalties_premiums = [
                        item.get("reason", "")
                        for item in pp_list
                        if isinstance(item, dict) and item.get("reason")
                    ]
        except Exception:
            pass

        return IISDormitoryInfo(
            has_application=has_app,
            queue_number=queue_num,
            status=status,
            application_date=app_date,
            settled_date=settled_date,
            privileges=privileges,
            penalties_premiums=penalties_premiums,
        )

    # -----------------------------------------------------------------------
    # Group Info (Учебная группа)
    # -----------------------------------------------------------------------

    async def get_group_info(self) -> IISGroupInfo:
        """Fetch academic group curator, headman and classmates."""
        resp = await self._request("GET", "/student-groups/user-group-info")
        data = resp.json()

        group_num = str(data.get("numberOfGroup", ""))
        curator = data.get("studentGroupCuratorDto") or {}
        curator_fio = curator.get("fio")
        curator_phone = curator.get("phone")
        curator_email = curator.get("email")
        curator_dept = curator.get("academicDepartment")

        students: list[str] = []
        raw_students = data.get("groupInfoStudentDto", [])
        if isinstance(raw_students, list):
            for s in raw_students:
                if isinstance(s, dict) and s.get("fio"):
                    role = f" ({s.get('userRole')})" if s.get("userRole") else ""
                    students.append(f"{s.get('fio')}{role}")

        return IISGroupInfo(
            group_number=group_num,
            curator_fio=curator_fio,
            curator_phone=curator_phone,
            curator_email=curator_email,
            curator_department=curator_dept,
            students_count=len(students),
            students=students,
        )

    # -----------------------------------------------------------------------
    # Notifications (Уведомления)
    # -----------------------------------------------------------------------

    async def get_notifications(self, page_number: int = 0) -> dict[str, Any]:
        """Fetch student unread notification count and notifications page."""
        count = 0
        try:
            c_resp = await self._request("GET", "/notifications/notViewed/count")
            if c_resp.status_code == 200:
                count = int(c_resp.text.strip() or 0)
        except Exception:
            pass

        notifications_list: list[dict[str, Any]] = []
        try:
            n_resp = await self._request("GET", f"/notifications?pageNumber={page_number}&pageSize=15")
            if n_resp.status_code == 200:
                n_data = n_resp.json()
                notifications_list = n_data.get("notifications", []) if isinstance(n_data, dict) else []
        except Exception:
            pass

        return {
            "unviewed_count": count,
            "notifications": notifications_list,
        }
