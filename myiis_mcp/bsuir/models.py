"""Data models for raw BSUIR IIS API responses.

Uses stdlib dataclasses — no pydantic — for full Pyodide/Cloudflare Workers compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _str_or_none(v: Any) -> str | None:
    return str(v) if v is not None else None


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bool_or_false(v: Any) -> bool:
    if v is None:
        return False
    return bool(v)


def _coerce_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(item) for item in v if item is not None]
    return [str(v)]


def _coerce_int_list(v: Any) -> list[int]:
    if v is None:
        return []
    if isinstance(v, list):
        result = []
        for item in v:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                pass
        return result
    return []


@dataclass
class StudentGroup:
    """BSUIR student group information."""

    name: str
    id: int | None = None
    course: int | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    faculty_abbrev: str | None = None
    speciality_name: str | None = None
    speciality_abbrev: str | None = None
    calendar_id: str | None = None
    education_degree: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StudentGroup":
        return cls(
            name=str(data.get("name", "")),
            id=_int_or_none(data.get("id")),
            course=_int_or_none(data.get("course")),
            faculty_id=_int_or_none(data.get("facultyId")),
            faculty_name=_str_or_none(data.get("facultyName")),
            faculty_abbrev=_str_or_none(data.get("facultyAbbrev")),
            speciality_name=_str_or_none(data.get("specialityName")),
            speciality_abbrev=_str_or_none(data.get("specialityAbbrev")),
            calendar_id=_str_or_none(data.get("calendarId")),
            education_degree=_int_or_none(data.get("educationDegree")),
        )


@dataclass
class Employee:
    """BSUIR employee / teacher information."""

    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    fio: str | None = None
    url_id: str | None = None
    id: int | None = None
    degree: str | None = None
    degree_abbrev: str | None = None
    rank: str | None = None
    photo_link: str | None = None
    calendar_id: str | None = None
    academic_department: list[str] = field(default_factory=list)
    email: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Employee":
        return cls(
            id=_int_or_none(data.get("id")),
            first_name=_str_or_none(data.get("firstName")),
            last_name=_str_or_none(data.get("lastName")),
            middle_name=_str_or_none(data.get("middleName")),
            fio=_str_or_none(data.get("fio")),
            url_id=_str_or_none(data.get("urlId")),
            degree=_str_or_none(data.get("degree")),
            degree_abbrev=_str_or_none(data.get("degreeAbbrev")),
            rank=_str_or_none(data.get("rank")),
            photo_link=_str_or_none(data.get("photoLink")),
            calendar_id=_str_or_none(data.get("calendarId")),
            academic_department=_coerce_str_list(data.get("academicDepartment")),
            email=_str_or_none(data.get("email")),
        )

    @property
    def display_name(self) -> str:
        """Returns best display name (fio or full name)."""
        if self.fio:
            return self.fio
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        return " ".join(parts) if parts else (self.url_id or "Неизвестный преподаватель")


@dataclass
class BSUIRLesson:
    """Raw lesson item from BSUIR schedule payload."""

    subject: str | None = None
    subject_full_name: str | None = None
    lesson_type_abbrev: str | None = None
    start_lesson_time: str | None = None
    end_lesson_time: str | None = None
    auditories: list[str] = field(default_factory=list)
    num_subgroup: int = 0
    week_number: list[int] = field(default_factory=list)
    date_lesson: str | None = None
    start_lesson_date: str | None = None
    end_lesson_date: str | None = None
    note: str | None = None
    announcement: bool = False
    split: bool = False
    employees: list[Employee] = field(default_factory=list)
    student_groups: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BSUIRLesson":
        employees_raw = data.get("employees") or []
        employees = [Employee.from_dict(e) for e in employees_raw if isinstance(e, dict)]

        student_groups_raw = data.get("studentGroups") or []
        student_groups = [g for g in student_groups_raw if isinstance(g, dict)]

        return cls(
            subject=_str_or_none(data.get("subject")),
            subject_full_name=_str_or_none(data.get("subjectFullName")),
            lesson_type_abbrev=_str_or_none(data.get("lessonTypeAbbrev")),
            start_lesson_time=_str_or_none(data.get("startLessonTime")),
            end_lesson_time=_str_or_none(data.get("endLessonTime")),
            auditories=_coerce_str_list(data.get("auditories")),
            num_subgroup=_int_or_none(data.get("numSubgroup")) or 0,
            week_number=_coerce_int_list(data.get("weekNumber")),
            date_lesson=_str_or_none(data.get("dateLesson")),
            start_lesson_date=_str_or_none(data.get("startLessonDate")),
            end_lesson_date=_str_or_none(data.get("endLessonDate")),
            note=_str_or_none(data.get("note")),
            announcement=_bool_or_false(data.get("announcement")),
            split=_bool_or_false(data.get("split")),
            employees=employees,
            student_groups=student_groups,
        )


@dataclass
class BSUIRScheduleResponse:
    """Raw response from /api/v1/schedule or /api/v1/employees/schedule."""

    start_date: str | None = None
    end_date: str | None = None
    start_exams_date: str | None = None
    end_exams_date: str | None = None
    student_group_dto: StudentGroup | None = None
    employee_dto: Employee | None = None
    schedules: dict[str, list[BSUIRLesson]] = field(default_factory=dict)
    next_schedules: dict[str, list[BSUIRLesson]] | None = None
    exams: list[BSUIRLesson] = field(default_factory=list)
    current_term: str | None = None
    next_term: str | None = None
    current_period: int | str | None = None
    is_zaoch_or_dist: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BSUIRScheduleResponse":
        # Parse schedules dict: {day_name: [lesson, ...]}
        raw_schedules = data.get("schedules") or {}
        schedules: dict[str, list[BSUIRLesson]] = {}
        if isinstance(raw_schedules, dict):
            for day, lessons in raw_schedules.items():
                if isinstance(lessons, list):
                    schedules[day] = [BSUIRLesson.from_dict(l) for l in lessons if isinstance(l, dict)]

        # Parse next_schedules similarly
        raw_next = data.get("nextSchedules")
        next_schedules = None
        if isinstance(raw_next, dict):
            next_schedules = {}
            for day, lessons in raw_next.items():
                if isinstance(lessons, list):
                    next_schedules[day] = [BSUIRLesson.from_dict(l) for l in lessons if isinstance(l, dict)]

        # Parse exams
        raw_exams = data.get("exams") or []
        exams = [BSUIRLesson.from_dict(e) for e in raw_exams if isinstance(e, dict)]

        # Parse nested objects
        sg_raw = data.get("studentGroupDto")
        student_group_dto = StudentGroup.from_dict(sg_raw) if isinstance(sg_raw, dict) and sg_raw.get("name") else None

        emp_raw = data.get("employeeDto")
        employee_dto = Employee.from_dict(emp_raw) if isinstance(emp_raw, dict) else None

        return cls(
            start_date=_str_or_none(data.get("startDate")),
            end_date=_str_or_none(data.get("endDate")),
            start_exams_date=_str_or_none(data.get("startExamsDate")),
            end_exams_date=_str_or_none(data.get("endExamsDate")),
            student_group_dto=student_group_dto,
            employee_dto=employee_dto,
            schedules=schedules,
            next_schedules=next_schedules,
            exams=exams,
            current_term=_str_or_none(data.get("currentTerm")),
            next_term=_str_or_none(data.get("nextTerm")),
            current_period=data.get("currentPeriod"),
            is_zaoch_or_dist=_bool_or_false(data.get("isZaochOrDist")),
        )


@dataclass
class EmployeeContact:
    """Contact details for an employee within a department."""

    phone_id: int | None = None
    phone_number: str | None = None
    address: str | None = None
    auditory: str | None = None
    building_number: str | None = None
    department: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmployeeContact":
        return cls(
            phone_id=_int_or_none(data.get("phoneId")),
            phone_number=_str_or_none(data.get("phoneNumber")),
            address=_str_or_none(data.get("address")),
            auditory=_str_or_none(data.get("auditory")),
            building_number=_str_or_none(data.get("buildingNumber")),
            department=_str_or_none(data.get("department")),
        )


@dataclass
class JobPosition:
    """Job position and department of an employee."""

    employee_department_id: int | None = None
    job_position: str | None = None
    department: str | None = None
    contacts: list[EmployeeContact] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobPosition":
        raw_contacts = data.get("contacts") or []
        contacts = [EmployeeContact.from_dict(c) for c in raw_contacts if isinstance(c, dict)]
        return cls(
            employee_department_id=_int_or_none(data.get("employeeDepartmentId")),
            job_position=_str_or_none(data.get("jobPosition")),
            department=_str_or_none(data.get("department")),
            contacts=contacts,
        )


@dataclass
class AdditionalInfo:
    """Additional information block (Education, Career, Publications, etc.)."""

    id: int | None = None
    id_type: int | None = None
    name_type: str | None = None
    content: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdditionalInfo":
        raw_content = _str_or_none(data.get("content"))
        clean_content = None
        if raw_content:
            import re

            cleaned = re.sub(r"<[^>]+>", " ", raw_content)
            clean_content = " ".join(cleaned.split()) or None

        return cls(
            id=_int_or_none(data.get("id")),
            id_type=_int_or_none(data.get("idType")),
            name_type=_str_or_none(data.get("nameType")),
            content=clean_content,
        )


@dataclass
class ProfileLink:
    """External profile link (Google Scholar, etc.)."""

    link: str
    link_type: str | None = None
    id: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileLink":
        return cls(
            link=str(data.get("link", "")),
            link_type=_str_or_none(data.get("profileLinkType")),
            id=_int_or_none(data.get("profileLinkEmployeeId")),
        )


@dataclass
class EmployeeDetails:
    """Detailed employee / teacher information from /api/v1/employees/details-url."""

    id: int | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    degree: str | None = None
    degree_abbrev: str | None = None
    rank: str | None = None
    email: str | None = None
    url_id: str | None = None
    calendar_id: str | None = None
    chief: bool = False
    job_positions: list[JobPosition] = field(default_factory=list)
    reading_courses: list[str] = field(default_factory=list)
    additional_information: list[AdditionalInfo] = field(default_factory=list)
    profile_links: list[ProfileLink] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmployeeDetails":
        raw_jobs = data.get("jobPositions") or []
        job_positions = [JobPosition.from_dict(j) for j in raw_jobs if isinstance(j, dict)]

        raw_info = data.get("additionalInformation") or []
        additional_info = [AdditionalInfo.from_dict(i) for i in raw_info if isinstance(i, dict)]

        raw_links = data.get("profileLinks") or []
        profile_links = [ProfileLink.from_dict(l) for l in raw_links if isinstance(l, dict)]

        return cls(
            id=_int_or_none(data.get("id")),
            first_name=_str_or_none(data.get("firstName")),
            middle_name=_str_or_none(data.get("middleName")),
            last_name=_str_or_none(data.get("lastName")),
            degree=_str_or_none(data.get("degree")),
            degree_abbrev=_str_or_none(data.get("degreeAbbrev")),
            rank=_str_or_none(data.get("rank")),
            email=_str_or_none(data.get("email")),
            url_id=_str_or_none(data.get("urlId")),
            calendar_id=_str_or_none(data.get("calendarId")),
            chief=_bool_or_false(data.get("chief")),
            job_positions=job_positions,
            reading_courses=_coerce_str_list(data.get("readingCourses")),
            additional_information=additional_info,
            profile_links=profile_links,
        )

    @property
    def display_name(self) -> str:
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        return " ".join(parts) if parts else (self.url_id or "Преподаватель")

