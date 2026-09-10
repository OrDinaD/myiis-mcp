"""Domain models for authenticated IIS BSUIR personal data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _to_dict(obj: Any) -> Any:
    """Recursively serialize dataclass to dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj


@dataclass
class IISProfile:
    """Student personal profile."""
    fio: str
    username: str
    email: str | None = None
    phone: str | None = None
    group: str | None = None
    course: int | None = None
    faculty: str | None = None
    speciality: str | None = None
    rating: float | int | None = None
    photo_url: str | None = None
    birth_date: str | None = None
    is_group_head: bool = False
    belarusian_fio: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MarkItem:
    """Individual subject mark from electronic record book."""
    subject: str
    form_of_control: str
    mark: str | int | None
    hours: int | str | None = None
    teacher: str | None = None
    date: str | None = None
    retakes_count: int = 0


@dataclass
class TermMarkPage:
    """Marks for a single academic semester."""
    term_number: int
    average_mark: float | None = None
    marks: list[MarkItem] = field(default_factory=list)


@dataclass
class IISMarkbook:
    """Student electronic markbook (зачётка)."""
    number: str
    average_mark: float
    terms: list[TermMarkPage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class GradeBookLesson:
    """Current lesson mark entry in grade book."""
    date: str
    subject: str
    lesson_type: str
    mark: str | None = None
    note: str | None = None


@dataclass
class IISGradeBook:
    """Current academic term journal (электронный журнал)."""
    subjects: list[str] = field(default_factory=list)
    recent_marks: list[GradeBookLesson] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class OmissionRecord:
    """Absence record (пропуск занятия)."""
    date: str
    subject: str
    lesson_type: str
    hours: int
    is_disrespectful: bool = False
    term: int | None = None


@dataclass
class IISOmissions:
    """Absence statistics for a student."""
    total_hours: int = 0
    disrespectful_hours: int = 0
    records: list[OmissionRecord] = field(default_factory=list)
    monthly_counts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class IISMarkSheetItem:
    """Examination / test sheet (экзаменационная ведомость / направление)."""
    id: int | str
    subject: str
    sheet_type: str
    term: int
    teacher: str | None = None
    status: str | None = None
    price: float | int | None = None


@dataclass
class IISCertificateItem:
    """Official student certificate (справка об обучении)."""
    id: int | str
    number: str
    provision_place: str
    date_order: str | None = None
    issue_date: str | None = None
    certificate_type: str | None = None
    status: str | None = None
    rejection_reason: str | None = None


@dataclass
class IISLibraryBookItem:
    """Library book item (книга в библиотеке БГУИР)."""
    title: str
    author: str | None = None
    take_date: str | None = None
    return_date: str | None = None
    is_overdue: bool = False


@dataclass
class IISDormitoryInfo:
    """Dormitory queue and accommodation status."""
    has_application: bool
    queue_number: int | None = None
    status: str | None = None
    application_date: str | None = None
    settled_date: str | None = None
    privileges: list[str] = field(default_factory=list)
    penalties_premiums: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class IISGroupInfo:
    """Student study group info with curator, headman, and classmates."""
    group_number: str
    curator_fio: str | None = None
    curator_phone: str | None = None
    curator_email: str | None = None
    curator_department: str | None = None
    students_count: int = 0
    students: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)
