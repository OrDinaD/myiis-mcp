"""Schedule normalization and date calculation service."""

from datetime import date, datetime, timedelta
import re
from typing import Any

from .bsuir.client import BSUIRClient
from .bsuir.models import BSUIRLesson, BSUIRScheduleResponse
from .models import (
    CurrentWeekResponse,
    DaySchedule,
    GroupSearchItem,
    GroupSearchResponse,
    NormalizedLesson,
    ScheduleResult,
    TeacherDepartmentContact,
    TeacherProfileResponse,
    TeacherSearchItem,
    TeacherSearchResponse,
)

RU_WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

BUILDING_REGEX = re.compile(r"(\d+)-(\d+)(?:\s*к\.?)?", re.IGNORECASE)


def parse_date_query(query: str | None, base_date: date | None = None) -> date | None:
    """Parse user/LLM date query string into a datetime.date object."""
    if not query or not query.strip():
        return None

    if base_date is None:
        base_date = date.today()

    q = query.strip().lower()
    if q in ("today", "сегодня"):
        return base_date
    if q in ("tomorrow", "завтра"):
        return base_date + timedelta(days=1)
    if q in ("yesterday", "вчера"):
        return base_date - timedelta(days=1)

    # Try ISO YYYY-MM-DD
    try:
        return datetime.strptime(q, "%Y-%m-%d").date()
    except ValueError:
        pass

    # Try Russian DD.MM.YYYY
    try:
        return datetime.strptime(q, "%d.%m.%Y").date()
    except ValueError:
        pass

    # Try Russian DD.MM (append current year to avoid deprecation warning)
    try:
        return datetime.strptime(f"{q}.{base_date.year}", "%d.%m.%Y").date()
    except ValueError:
        pass

    raise ValueError(f"Не удалось распознать формат даты: '{query}'. Используйте формат ГГГГ-ММ-ДД или 'сегодня'/'завтра'.")


def calculate_week_for_date(target_date: date, current_week: int, base_date: date | None = None) -> int:
    """Calculate the BSUIR instructional week number (1-4) for any target date."""
    if base_date is None:
        base_date = date.today()

    # Find Mondays of both weeks
    base_monday = base_date - timedelta(days=base_date.weekday())
    target_monday = target_date - timedelta(days=target_date.weekday())

    delta_weeks = (target_monday - base_monday).days // 7
    return (current_week - 1 + delta_weeks) % 4 + 1


def parse_auditory_building(auditory_str: str) -> tuple[str, str | None]:
    """Parse auditory and building number from string (e.g., '112-3 к.' -> ('112-3 к.', '3'))."""
    match = BUILDING_REGEX.search(auditory_str)
    if match:
        return auditory_str, match.group(2)
    return auditory_str, None


def normalize_lesson(
    raw: BSUIRLesson,
    day_of_week: str,
    target_date: date | None = None,
) -> NormalizedLesson:
    """Convert raw BSUIRLesson to normalized domain representation."""
    building = None
    if raw.auditories:
        _, building = parse_auditory_building(raw.auditories[0])

    teachers = [emp.display_name for emp in raw.employees]
    groups = [g.get("name", "") for g in raw.student_groups if isinstance(g, dict) and g.get("name")]

    date_str = target_date.strftime("%Y-%m-%d") if target_date else None

    return NormalizedLesson(
        subject=raw.subject or "Без названия",
        subject_full_name=raw.subject_full_name,
        lesson_type=raw.lesson_type_abbrev or "Занятие",
        start_time=raw.start_lesson_time or "",
        end_time=raw.end_lesson_time or "",
        date=date_str,
        day_of_week=day_of_week,
        week_numbers=raw.week_number,
        subgroup=raw.num_subgroup,
        auditories=raw.auditories,
        building=building,
        teachers=teachers,
        groups=groups,
        note=raw.note,
    )


def is_lesson_active_on_date(
    raw: BSUIRLesson,
    target_date: date,
    target_week: int,
    subgroup: int | None = None,
) -> bool:
    """Check whether a lesson takes place on a specific date and week."""
    # Subgroup filter
    if subgroup in (1, 2) and raw.num_subgroup != 0 and raw.num_subgroup != subgroup:
        return False

    # Specific date override
    if raw.date_lesson:
        try:
            d = datetime.strptime(raw.date_lesson.strip(), "%d.%m.%Y").date()
            if d != target_date:
                return False
        except ValueError:
            pass

    # Date boundaries
    if raw.start_lesson_date:
        try:
            start_d = datetime.strptime(raw.start_lesson_date.strip(), "%d.%m.%Y").date()
            if target_date < start_d:
                return False
        except ValueError:
            pass

    if raw.end_lesson_date:
        try:
            end_d = datetime.strptime(raw.end_lesson_date.strip(), "%d.%m.%Y").date()
            if target_date > end_d:
                return False
        except ValueError:
            pass

    # Week cycle check (if lesson specifies weeks)
    if raw.week_number and target_week not in raw.week_number:
        return False

    return True


class ScheduleService:
    """High-level service coordinating BSUIR client and normalization."""

    def __init__(self, client: BSUIRClient | None = None) -> None:
        self.client = client or BSUIRClient()

    async def get_current_week_info(self, today: date | None = None) -> CurrentWeekResponse:
        """Get current instructional week and today's date."""
        if today is None:
            today = date.today()
        current_week = await self.client.get_current_week()
        day_name = RU_WEEKDAYS[today.weekday()]
        return CurrentWeekResponse(
            current_week=current_week,
            today=today.strftime("%Y-%m-%d"),
            day_of_week=day_name,
            summary=f"Сегодня {today.strftime('%d.%m.%Y')} ({day_name}), идет {current_week}-я учебная неделя БГУИР.",
        )

    async def get_group_schedule(
        self,
        group: str,
        date_query: str | None = None,
        days: int = 1,
        subgroup: int | None = None,
        base_date: date | None = None,
    ) -> ScheduleResult:
        """Fetch and filter schedule for a student group."""
        if base_date is None:
            base_date = date.today()

        target_date = parse_date_query(date_query, base_date=base_date)
        current_week = await self.client.get_current_week()
        raw_schedule = await self.client.get_group_schedule(group)

        target_name = f"Группа {group}"
        if raw_schedule.student_group_dto and raw_schedule.student_group_dto.speciality_name:
            target_name += f" ({raw_schedule.student_group_dto.speciality_name})"

        return self._build_schedule_result(
            raw_schedule=raw_schedule,
            target=target_name,
            target_type="group",
            target_date=target_date,
            days=days,
            subgroup=subgroup,
            current_week=current_week,
            base_date=base_date,
        )

    async def get_teacher_schedule(
        self,
        teacher: str,
        date_query: str | None = None,
        days: int = 1,
        subgroup: int | None = None,
        base_date: date | None = None,
    ) -> ScheduleResult:
        """Fetch and filter schedule for a teacher."""
        if base_date is None:
            base_date = date.today()

        clean_t = teacher.strip()
        url_id = clean_t

        # If clean_t does not look like a url_id (contains Cyrillic or spaces), resolve it
        if any("\u0400" <= c <= "\u04ff" for c in clean_t) or " " in clean_t:
            matches = await self.client.find_employees(clean_t)
            if not matches:
                raise ValueError(f"Преподаватель '{clean_t}' не найден. Проверьте правильность написания фамилии.")
            if len(matches) > 1:
                exact = [m for m in matches if m.last_name and m.last_name.lower() == clean_t.lower()]
                if len(exact) == 1:
                    matched_emp = exact[0]
                else:
                    options = ", ".join([f"{m.display_name} ({', '.join(m.academic_department) or m.url_id})" for m in matches[:5]])
                    raise ValueError(f"Найдено несколько преподавателей по запросу '{clean_t}': {options}. Уточните ФИО.")
            else:
                matched_emp = matches[0]

            url_id = matched_emp.url_id or clean_t
            display_teacher = matched_emp.display_name
        else:
            display_teacher = url_id

        target_date = parse_date_query(date_query, base_date=base_date)
        current_week = await self.client.get_current_week()
        raw_schedule = await self.client.get_employee_schedule(url_id)

        if raw_schedule.employee_dto:
            display_teacher = raw_schedule.employee_dto.display_name

        # Try to fetch teacher department contacts from details
        teacher_contacts: list[TeacherDepartmentContact] = []
        try:
            details = await self.client.get_employee_details(url_id)
            for job in details.job_positions:
                for c in job.contacts:
                    teacher_contacts.append(
                        TeacherDepartmentContact(
                            department=c.department or job.department,
                            job_position=job.job_position,
                            phone=c.phone_number,
                            auditory=c.auditory,
                            building=c.building_number,
                            address=c.address,
                        )
                    )
        except Exception:
            pass

        return self._build_schedule_result(
            raw_schedule=raw_schedule,
            target=display_teacher,
            target_type="teacher",
            target_date=target_date,
            days=days,
            subgroup=subgroup,
            current_week=current_week,
            base_date=base_date,
            teacher_contacts=teacher_contacts,
        )

    def _build_schedule_result(
        self,
        raw_schedule: BSUIRScheduleResponse,
        target: str,
        target_type: str,
        target_date: date | None,
        days: int,
        subgroup: int | None,
        current_week: int,
        base_date: date,
        teacher_contacts: list[TeacherDepartmentContact] | None = None,
    ) -> ScheduleResult:
        contacts = teacher_contacts or []
        schedules = raw_schedule.schedules or {}
        days_result: list[DaySchedule] = []
        total_lessons = 0

        if target_date is not None:
            # Filter for specific date or date range
            days_count = max(1, min(days, 14))  # Cap to 14 days
            for d_idx in range(days_count):
                curr_date = target_date + timedelta(days=d_idx)
                curr_week = calculate_week_for_date(curr_date, current_week, base_date)
                day_name = RU_WEEKDAYS[curr_date.weekday()]
                raw_lessons = schedules.get(day_name, [])

                day_lessons: list[NormalizedLesson] = []
                for l in raw_lessons:
                    if is_lesson_active_on_date(l, curr_date, curr_week, subgroup):
                        norm = normalize_lesson(l, day_name, curr_date)
                        day_lessons.append(norm)

                # Sort by start_time
                day_lessons.sort(key=lambda x: x.start_time)
                total_lessons += len(day_lessons)

                days_result.append(
                    DaySchedule(
                        date=curr_date.strftime("%Y-%m-%d"),
                        day_of_week=day_name,
                        week_number=curr_week,
                        lessons=day_lessons,
                    )
                )
            query_date_str = target_date.strftime("%Y-%m-%d")
        else:
            # Full weekly schedule timetable
            for day_name in RU_WEEKDAYS[:6]:  # Mon-Sat
                raw_lessons = schedules.get(day_name, [])
                if not raw_lessons:
                    continue

                day_lessons = []
                for l in raw_lessons:
                    if subgroup in (1, 2) and l.num_subgroup != 0 and l.num_subgroup != subgroup:
                        continue
                    day_lessons.append(normalize_lesson(l, day_name))

                day_lessons.sort(key=lambda x: (x.start_time, x.week_numbers))
                total_lessons += len(day_lessons)

                days_result.append(
                    DaySchedule(
                        date=None,
                        day_of_week=day_name,
                        week_number=None,
                        lessons=day_lessons,
                    )
                )
            query_date_str = None

        # Build summary
        if target_date is not None:
            if total_lessons == 0:
                summary = f"На {query_date_str} для {target} занятий не запланировано (выходной или нет пар)."
                if contacts and (contacts[0].auditory or contacts[0].phone):
                    c = contacts[0]
                    c_info = []
                    if c.auditory:
                        c_info.append(f"кабинет ауд. {c.auditory} {c.building or ''}".strip())
                    if c.phone:
                        c_info.append(f"телефон {c.phone}")
                    if c.department:
                        c_info.append(f"кафедра {c.department}")
                    if c_info:
                        summary += f" Контакты кафедры ({', '.join(c_info)})."
            else:
                summary = f"Расписание для {target} на {query_date_str}: найдено {total_lessons} занятий."
                if contacts and contacts[0].auditory:
                    c = contacts[0]
                    summary += f" Кафедра: {c.department or ''} (ауд. {c.auditory} {c.building or ''}, тел. {c.phone or ''}).".replace("  ", " ")
        else:
            summary = f"Полное недельное расписание для {target}: {total_lessons} занятий в течение недели (текущая неделя: {current_week})."

        return ScheduleResult(
            target=target,
            target_type=target_type,
            current_week=current_week,
            query_date=query_date_str,
            days=days_result,
            total_lessons=total_lessons,
            summary=summary,
            teacher_contacts=contacts,
        )

    async def get_teacher_details(self, teacher: str) -> TeacherProfileResponse:
        """Fetch full details, contacts, reading courses, and links for a teacher."""
        clean_t = teacher.strip()
        url_id = clean_t

        if any("\u0400" <= c <= "\u04ff" for c in clean_t) or " " in clean_t:
            matches = await self.client.find_employees(clean_t)
            if not matches:
                raise ValueError(f"Преподаватель '{clean_t}' не найден. Проверьте правильность написания фамилии.")
            if len(matches) > 1:
                exact = [m for m in matches if m.last_name and m.last_name.lower() == clean_t.lower()]
                if len(exact) == 1:
                    matched_emp = exact[0]
                    url_id = matched_emp.url_id or clean_t
                elif 1 < len(exact) <= 3:
                    # Multiple teachers share the exact surname (e.g. 'Герман')!
                    # Fetch details for all of them and return a comprehensive response
                    all_details = []
                    for e in exact:
                        if e.url_id:
                            try:
                                all_details.append(await self.client.get_employee_details(e.url_id))
                            except Exception:
                                pass

                    if all_details:
                        summaries = []
                        all_courses: list[str] = []
                        all_contacts: list[TeacherDepartmentContact] = []
                        all_emails: list[str] = []
                        departments_set: list[str] = []

                        for d in all_details:
                            if d.email and d.email not in all_emails:
                                all_emails.append(d.email)
                            for c in d.reading_courses:
                                if c not in all_courses:
                                    all_courses.append(c)

                            d_contacts_desc = []
                            for job in d.job_positions:
                                if job.department and job.department not in departments_set:
                                    departments_set.append(job.department)
                                for c in job.contacts:
                                    tc = TeacherDepartmentContact(
                                        department=c.department or job.department,
                                        job_position=job.job_position,
                                        phone=c.phone_number,
                                        auditory=c.auditory,
                                        building=c.building_number,
                                        address=c.address,
                                    )
                                    all_contacts.append(tc)
                                    aud = f"ауд. {tc.auditory}" if tc.auditory else ""
                                    bld = f"({tc.building})" if tc.building else ""
                                    ph = f"тел. {tc.phone}" if tc.phone else ""
                                    part = " ".join(filter(None, [aud, bld, ph]))
                                    if part:
                                        d_contacts_desc.append(part)

                            c_info = f" Кабинет: {'; '.join(d_contacts_desc)}." if d_contacts_desc else ""
                            courses_info = f" Читает: {', '.join(d.reading_courses[:3])}." if d.reading_courses else ""
                            email_info = f" Email: {d.email}." if d.email else ""
                            rank_info = f" ({d.rank})" if d.rank else ""
                            summaries.append(f"{d.display_name}{rank_info}.{email_info}{c_info}{courses_info}")

                        combined_summary = (
                            f"По фамилии '{clean_t}' найдено {len(all_details)} преподавателя: "
                            + " | ".join(summaries)
                        )

                        first_d = all_details[0]
                        return TeacherProfileResponse(
                            fio=" / ".join([d.display_name for d in all_details]),
                            url_id=first_d.url_id or clean_t,
                            summary=combined_summary,
                            first_name=first_d.first_name,
                            middle_name=first_d.middle_name,
                            last_name=first_d.last_name,
                            email="; ".join(all_emails) if all_emails else None,
                            degree=first_d.degree,
                            rank=first_d.rank,
                            photo_url=f"https://iis.bsuir.by/api/v1/employees/photo/{first_d.id}" if first_d.id else None,
                            profile_url=f"https://iis.bsuir.by/employees/{first_d.url_id}" if first_d.url_id else None,
                            schedule_url=f"https://iis.bsuir.by/schedule/{first_d.url_id}" if first_d.url_id else None,
                            repository_url=None,
                            departments=departments_set,
                            reading_courses=all_courses,
                            contacts=all_contacts,
                            profile_links=[],
                            additional_info={},
                        )
                else:
                    options = ", ".join([f"{m.display_name} ({', '.join(m.academic_department) or m.url_id})" for m in matches[:5]])
                    raise ValueError(f"Найдено несколько преподавателей по запросу '{clean_t}': {options}. Уточните ФИО.")
            else:
                matched_emp = matches[0]
                url_id = matched_emp.url_id or clean_t

        raw = await self.client.get_employee_details(url_id)

        contacts: list[TeacherDepartmentContact] = []
        departments: list[str] = []
        for job in raw.job_positions:
            if job.department and job.department not in departments:
                departments.append(job.department)
            for c in job.contacts:
                contacts.append(
                    TeacherDepartmentContact(
                        department=c.department or job.department,
                        job_position=job.job_position,
                        phone=c.phone_number,
                        auditory=c.auditory,
                        building=c.building_number,
                        address=c.address,
                    )
                )

        profile_url = f"https://iis.bsuir.by/employees/{raw.url_id}" if raw.url_id else None
        schedule_url = f"https://iis.bsuir.by/schedule/{raw.url_id}" if raw.url_id else None
        photo_url = f"https://iis.bsuir.by/api/v1/employees/photo/{raw.id}" if raw.id else None

        import urllib.parse

        initials = f"{(raw.first_name or '')[:1]}. {(raw.middle_name or '')[:1]}.".strip()
        repo_author = f"{raw.last_name or ''} {initials}".strip()
        repo_url = (
            f"https://libeldoc.bsuir.by/simple-search?filterquery={urllib.parse.quote(repo_author)}&filtername=author&filtertype=equals"
            if raw.last_name
            else None
        )

        profile_links = [{"type": l.link_type or "external", "url": l.link} for l in raw.profile_links if l.link]

        additional_info: dict[str, str] = {}
        for info in raw.additional_information:
            if info.name_type and info.content:
                additional_info[info.name_type] = info.content

        # Human summary
        fio = raw.display_name
        summary_parts = [fio]
        rank_deg = ", ".join([p for p in [raw.rank, raw.degree] if p])
        if rank_deg:
            summary_parts.append(f"({rank_deg})")
        if departments:
            summary_parts.append(f"— {', '.join(departments)}")
        if raw.email:
            summary_parts.append(f"Email: {raw.email}")
        if contacts:
            c_desc = []
            for c in contacts:
                aud = f"ауд. {c.auditory}" if c.auditory else ""
                bld = f"({c.building})" if c.building else ""
                ph = f"тел. {c.phone}" if c.phone else ""
                part = " ".join([p for p in [aud, bld, ph] if p])
                if part:
                    c_desc.append(part)
            if c_desc:
                summary_parts.append(f"Кабинет: {'; '.join(c_desc)}")
        if raw.reading_courses:
            summary_parts.append(f"Читаемые курсы: {', '.join(raw.reading_courses)}")

        summary = ". ".join(summary_parts) + "."

        return TeacherProfileResponse(
            fio=fio,
            url_id=raw.url_id or url_id,
            summary=summary,
            first_name=raw.first_name,
            middle_name=raw.middle_name,
            last_name=raw.last_name,
            email=raw.email,
            degree=raw.degree,
            rank=raw.rank,
            photo_url=photo_url,
            profile_url=profile_url,
            schedule_url=schedule_url,
            repository_url=repo_url,
            departments=departments,
            reading_courses=raw.reading_courses,
            contacts=contacts,
            profile_links=profile_links,
            additional_info=additional_info,
        )

    async def search_groups(
        self,
        query: str,
        course: int | None = None,
        faculty: str | None = None,
        limit: int = 20,
    ) -> GroupSearchResponse:
        """Search student groups."""
        groups = await self.client.find_groups(query=query, course=course, faculty=faculty, limit=limit)
        items = [
            GroupSearchItem(
                name=g.name,
                course=g.course,
                faculty=g.faculty_abbrev,
                speciality=g.speciality_name or g.speciality_abbrev,
            )
            for g in groups
        ]
        return GroupSearchResponse(
            query=query,
            count=len(items),
            groups=items,
            summary=f"Найдено групп: {len(items)} по запросу '{query}'." if items else f"Групп по запросу '{query}' не найдено.",
        )

    async def search_teachers(
        self,
        query: str,
        department: str | None = None,
        limit: int = 20,
    ) -> TeacherSearchResponse:
        """Search teachers."""
        employees = await self.client.find_employees(query=query, department=department, limit=limit)
        items = [
            TeacherSearchItem(
                fio=e.display_name,
                url_id=e.url_id or "",
                departments=e.academic_department,
                degree=e.degree,
                rank=e.rank,
                photo_link=e.photo_link,
            )
            for e in employees
        ]
        return TeacherSearchResponse(
            query=query,
            count=len(items),
            teachers=items,
            summary=f"Найдено преподавателей: {len(items)} по запросу '{query}'." if items else f"Преподавателей по запросу '{query}' не найдено.",
        )
