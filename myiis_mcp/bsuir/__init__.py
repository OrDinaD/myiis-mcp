"""BSUIR IIS API integration package."""

from .client import BSUIRClient
from .exceptions import (
    BSUIRApiError,
    BSUIRError,
    BSUIRTimeoutError,
    GroupNotFoundError,
    TeacherNotFoundError,
)
from .models import (
    BSUIRLesson,
    BSUIRScheduleResponse,
    Employee,
    StudentGroup,
)

__all__ = [
    "BSUIRClient",
    "BSUIRError",
    "GroupNotFoundError",
    "TeacherNotFoundError",
    "BSUIRApiError",
    "BSUIRTimeoutError",
    "StudentGroup",
    "Employee",
    "BSUIRLesson",
    "BSUIRScheduleResponse",
]
