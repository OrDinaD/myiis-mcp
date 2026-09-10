"""Account status MCP tool."""

from __future__ import annotations

from typing import Any

from ..auth.models import AuthenticationRequired, User
from ..auth.session import UpstreamSessionManager


def create_account_tool(session_manager: UpstreamSessionManager):
    """Factory creating get_account_status tool."""

    async def get_account_status(user: User | None = None) -> dict[str, Any]:
        """Получить статус подключения персональных аккаунтов ИИС БГУИР и СЭО Moodle.

        Показывает, связаны ли аккаунты, статус сессии и имя пользователя. Никаких паролей и секретов.
        """
        if not user:
            raise AuthenticationRequired("Для проверки статуса аккаунта требуется авторизация.")
        return session_manager.get_account_status(user.id)

    return get_account_status
