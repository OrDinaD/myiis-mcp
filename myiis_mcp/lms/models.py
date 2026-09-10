"""Domain models for LMS Moodle BSUIR courses and modules."""

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
class MoodleCourse:
    """Enrolled Moodle course summary."""
    id: int
    fullname: str
    shortname: str | None = None
    url: str = ""
    category: str | None = None
    progress: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MoodleModule:
    """Activity or resource module inside a course section."""
    id: int
    name: str
    modname: str  # "page", "assign", "resource", "forum", "url", "quiz", etc.
    url: str | None = None
    uservisible: bool = True
    section_id: int | None = None
    section_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MoodleSection:
    """Course section / topic."""
    id: int
    number: int
    title: str
    section_url: str | None = None
    modules: list[MoodleModule] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MoodleCourseState:
    """Full course content tree (sections, topics, modules)."""
    course_id: int
    fullname: str
    sections: list[MoodleSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MoodlePage:
    """Content of a Moodle Page (mod/page)."""
    module_id: int
    title: str
    clean_text: str
    body_html: str
    links: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class MoodleResourceMetadata:
    """Metadata of an authenticated file or resource in Moodle."""
    url: str
    filename: str
    mime_type: str
    size_bytes: int = 0
    course_id: int | None = None
    module_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)
