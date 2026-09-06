"""Normalized data models returned by MyIIS MCP tools.

Uses stdlib dataclasses (no pydantic) for Pyodide/Cloudflare Workers compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to plain dicts for JSON serialization."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj


@dataclass
class NormalizedLesson:
    """Normalized representation of a single class / lesson."""

    subject: str
    lesson_type: str
    start_time: str
    end_time: str
    day_of_week: str
    subject_full_name: str | None = None
    date: str | None = None
    week_numbers: list[int] = field(default_factory=list)
    subgroup: int = 0
    auditories: list[str] = field(default_factory=list)
    building: str | None = None
    teachers: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class DaySchedule:
    """Schedule for a single day."""

    day_of_week: str
    date: str | None = None
    week_number: int | None = None
    lessons: list[NormalizedLesson] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class TeacherDepartmentContact:
    """Department contact details for a teacher."""

    department: str | None = None
    job_position: str | None = None
    phone: str | None = None
    auditory: str | None = None
    building: str | None = None
    address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class ScheduleResult:
    """Comprehensive schedule result for a group or teacher."""

    target: str
    target_type: str
    current_week: int
    summary: str
    query_date: str | None = None
    days: list[DaySchedule] = field(default_factory=list)
    total_lessons: int = 0
    teacher_contacts: list[TeacherDepartmentContact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    def model_dump_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class GroupSearchItem:
    """Found student group item."""

    name: str
    course: int | None = None
    faculty: str | None = None
    speciality: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class GroupSearchResponse:
    """Result of searching student groups."""

    query: str
    count: int
    summary: str
    groups: list[GroupSearchItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    def model_dump_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class TeacherSearchItem:
    """Found teacher item."""

    fio: str
    url_id: str
    departments: list[str] = field(default_factory=list)
    degree: str | None = None
    rank: str | None = None
    photo_link: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class TeacherSearchResponse:
    """Result of searching teachers."""

    query: str
    count: int
    summary: str
    teachers: list[TeacherSearchItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    def model_dump_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class CurrentWeekResponse:
    """Information about current instructional week."""

    current_week: int
    today: str
    day_of_week: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    def model_dump_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class TeacherProfileResponse:
    """Full teacher profile with contacts, departments, reading courses, and links."""

    fio: str
    url_id: str
    summary: str
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    degree: str | None = None
    rank: str | None = None
    photo_url: str | None = None
    profile_url: str | None = None
    schedule_url: str | None = None
    repository_url: str | None = None
    departments: list[str] = field(default_factory=list)
    reading_courses: list[str] = field(default_factory=list)
    contacts: list[TeacherDepartmentContact] = field(default_factory=list)
    profile_links: list[dict[str, str]] = field(default_factory=list)
    additional_info: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    def model_dump_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

