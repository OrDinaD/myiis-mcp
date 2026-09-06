"""Custom exceptions for BSUIR API integration."""


class BSUIRError(Exception):
    """Base exception for BSUIR API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GroupNotFoundError(BSUIRError):
    """Raised when the specified student group is not found in BSUIR."""

    def __init__(self, group_name: str) -> None:
        super().__init__(f"Учебная группа '{group_name}' не найдена в ИИС БГУИР.", status_code=404)
        self.group_name = group_name


class TeacherNotFoundError(BSUIRError):
    """Raised when the specified teacher is not found in BSUIR."""

    def __init__(self, teacher_identifier: str) -> None:
        super().__init__(f"Преподаватель '{teacher_identifier}' не найден в ИИС БГУИР.", status_code=404)
        self.teacher_identifier = teacher_identifier


class BSUIRApiError(BSUIRError):
    """Raised when BSUIR API returns an unexpected status code or corrupt payload."""

    pass


class BSUIRTimeoutError(BSUIRError):
    """Raised when BSUIR API request times out."""

    def __init__(self, message: str = "Таймаут соединения с API ИИС БГУИР.") -> None:
        super().__init__(message, status_code=504)
