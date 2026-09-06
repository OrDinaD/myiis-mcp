"""MyIIS MCP Server implementation for ChatGPT and MCP clients."""

from starlette.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from .bsuir.client import BSUIRClient
from .bsuir.exceptions import (
    BSUIRApiError,
    BSUIRError,
    BSUIRTimeoutError,
    GroupNotFoundError,
    TeacherNotFoundError,
)
from .models import (
    CurrentWeekResponse,
    GroupSearchResponse,
    ScheduleResult,
    TeacherSearchResponse,
)
from .schedule_service import ScheduleService

SERVER_INSTRUCTIONS = """
Сервер MyIIS MCP предоставляет актуальные данные о расписании занятий, учебных неделях, группах и преподавателях
Белорусского государственного университета информатики и радиоэлектроники (БГУИР / BSUIR) через официальный API ИИС БГУИР.

Основные возможности:
1. get_group_schedule: получение расписания группы (на сегодня, завтра, конкретную дату или всю неделю).
2. get_teacher_schedule: получение расписания преподавателя по фамилии или urlId.
3. search_groups: поиск учебной группы по номеру или специальности.
4. search_teachers: поиск преподавателя по фамилии или кафедре.
5. get_current_week: получение номера текущей учебной недели (1-4) и сегодняшней даты.

Правила работы с расписанием:
- В БГУИР действует 4-недельный учебный цикл (недели 1, 2, 3, 4).
- Если пользователь спрашивает расписание на 'сегодня' или 'завтра', передавайте в date значение 'today' или 'tomorrow'.
- Даты также можно передавать в формате 'ГГГГ-ММ-ДД' (например, '2026-09-07').
- Для фильтрации по подгруппе передавайте subgroup=1 или subgroup=2.
- Если номер группы или фамилия преподавателя неизвестны, сначала используйте инструменты поиска.
""".strip()

# Initialize MCPServer
mcp = MCPServer(
    name="myiis",
    instructions=SERVER_INSTRUCTIONS,
    version="0.1.0",
)

# Shared service
_service = ScheduleService()


@mcp.tool(
    name="get_group_schedule",
    title="Get Student Group Schedule",
    description=(
        "Получить расписание занятий учебной группы БГУИР. "
        "Поддерживает фильтрацию на конкретную дату ('today', 'tomorrow', '2026-09-07'), "
        "диапазон дат (параметр days) и номер подгруппы (1 или 2). "
        "Если дата не указана, возвращается полное недельное расписание по дням."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def get_group_schedule(
    group: str = Field(description="Номер учебной группы (например, '310101')"),
    date: str | None = Field(default=None, description="Дата в формате ГГГГ-ММ-ДД или 'today' / 'сегодня', 'tomorrow' / 'завтра'"),
    days: int = Field(default=1, description="Количество дней расписания начиная с указанной даты (от 1 до 14, по умолчанию 1)"),
    subgroup: int | None = Field(default=None, description="Номер подгруппы (1 или 2). Если не указан — выводятся все занятия"),
) -> ScheduleResult:
    """Get schedule for a student group with date and subgroup filtering."""
    try:
        return await _service.get_group_schedule(group=group, date_query=date, days=days, subgroup=subgroup)
    except GroupNotFoundError as exc:
        return ScheduleResult(
            target=f"Группа {group}",
            target_type="group",
            current_week=0,
            query_date=date,
            summary=f"Ошибка: {exc.message} Проверьте правильность номера через search_groups.",
        )
    except ValueError as exc:
        return ScheduleResult(
            target=f"Группа {group}",
            target_type="group",
            current_week=0,
            query_date=date,
            summary=f"Ошибка параметров запроса: {exc}",
        )
    except (BSUIRTimeoutError, BSUIRApiError, BSUIRError) as exc:
        return ScheduleResult(
            target=f"Группа {group}",
            target_type="group",
            current_week=0,
            query_date=date,
            summary=f"Ошибка сервиса БГУИР: {exc}. Попробуйте повторить запрос позже.",
        )


@mcp.tool(
    name="get_teacher_schedule",
    title="Get Teacher Schedule",
    description=(
        "Получить расписание занятий преподавателя БГУИР. "
        "Принимает фамилию преподавателя (например, 'Василькова'), ФИО или urlId (например, 'a-vasilkova'). "
        "Поддерживает фильтрацию на конкретную дату ('today', 'tomorrow', '2026-09-07') и диапазон дней."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def get_teacher_schedule(
    teacher: str = Field(description="Фамилия преподавателя (например, 'Василькова') или urlId (например, 'a-vasilkova')"),
    date: str | None = Field(default=None, description="Дата в формате ГГГГ-ММ-ДД или 'today' / 'сегодня', 'tomorrow' / 'завтра'"),
    days: int = Field(default=1, description="Количество дней расписания начиная с указанной даты (от 1 до 14, по умолчанию 1)"),
) -> ScheduleResult:
    """Get schedule for a university teacher."""
    try:
        return await _service.get_teacher_schedule(teacher=teacher, date_query=date, days=days)
    except TeacherNotFoundError as exc:
        return ScheduleResult(
            target=teacher,
            target_type="teacher",
            current_week=0,
            query_date=date,
            summary=f"Ошибка: {exc.message} Найдите преподавателя через search_teachers.",
        )
    except ValueError as exc:
        return ScheduleResult(
            target=teacher,
            target_type="teacher",
            current_week=0,
            query_date=date,
            summary=f"Ошибка: {exc}",
        )
    except (BSUIRTimeoutError, BSUIRApiError, BSUIRError) as exc:
        return ScheduleResult(
            target=teacher,
            target_type="teacher",
            current_week=0,
            query_date=date,
            summary=f"Ошибка сервиса БГУИР: {exc}. Попробуйте повторить запрос позже.",
        )


@mcp.tool(
    name="search_groups",
    title="Search Student Groups",
    description="Поиск учебных групп БГУИР по номеру, специальности, курсу или факультету.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def search_groups(
    query: str = Field(description="Поисковый запрос (номер группы, специальность или факультет, например '3101' или 'ИСиТ')"),
    course: int | None = Field(default=None, description="Номер курса (1-5)"),
    faculty: str | None = Field(default=None, description="Аббревиатура факультета (например, 'ФКП', 'ФКСИС')"),
) -> GroupSearchResponse:
    """Search student groups in BSUIR."""
    try:
        return await _service.search_groups(query=query, course=course, faculty=faculty)
    except Exception as exc:
        return GroupSearchResponse(
            query=query,
            count=0,
            groups=[],
            summary=f"Не удалось выполнить поиск групп: {exc}",
        )


@mcp.tool(
    name="search_teachers",
    title="Search Teachers",
    description="Поиск преподавателей БГУИР по фамилии, имени или кафедре.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def search_teachers(
    query: str = Field(description="Фамилия или имя преподавателя (например, 'Василькова', 'Иванов')"),
    department: str | None = Field(default=None, description="Кафедра (например, 'Каф. ИРТ')"),
) -> TeacherSearchResponse:
    """Search teachers in BSUIR."""
    try:
        return await _service.search_teachers(query=query, department=department)
    except Exception as exc:
        return TeacherSearchResponse(
            query=query,
            count=0,
            teachers=[],
            summary=f"Не удалось выполнить поиск преподавателей: {exc}",
        )


@mcp.tool(
    name="get_current_week",
    title="Get Current Instructional Week",
    description="Получить номер текущей учебной недели в БГУИР (1, 2, 3 или 4) и сегодняшнюю дату.",
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def get_current_week() -> CurrentWeekResponse:
    """Get current instructional week in BSUIR."""
    try:
        return await _service.get_current_week_info()
    except Exception as exc:
        return CurrentWeekResponse(
            current_week=0,
            today="",
            day_of_week="",
            summary=f"Не удалось получить текущую неделю от БГУИР: {exc}",
        )


# Custom Health Check and Discovery Routes
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Production health check endpoint."""
    bsuir_status = "ok"
    current_week = None
    try:
        current_week = await _service.client.get_current_week()
    except Exception as exc:
        bsuir_status = f"unreachable: {exc}"

    status_code = 200 if bsuir_status == "ok" else 503
    return JSONResponse(
        {
            "status": "ok" if bsuir_status == "ok" else "degraded",
            "version": "0.1.0",
            "server": "MyIIS MCP",
            "mcp_endpoint": "/mcp",
            "bsuir_api": bsuir_status,
            "current_week": current_week,
        },
        status_code=status_code,
    )


@mcp.custom_route("/", methods=["GET"])
async def root_info(request):
    """Server discovery and information endpoint."""
    return JSONResponse(
        {
            "name": "MyIIS MCP Server",
            "version": "0.1.0",
            "description": "Model Context Protocol server connecting ChatGPT to BSUIR IIS API",
            "repository": "https://github.com/OrDinaD/myiis-mcp",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
            },
            "status": "running",
        }
    )


# Configure Streamable HTTP app
security_settings = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["*"],
    allowed_origins=["*"],
)

_raw_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    transport_security=security_settings,
    stateless_http=True,
)


class PathRewriteMiddleware:
    """Ensure paths like /api/mcp and /api/health are routed transparently on Vercel."""

    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path in ("/api/mcp", "/api/mcp/"):
                scope["path"] = "/mcp"
                scope["raw_path"] = b"/mcp"
            elif path in ("/api/health", "/api/health/"):
                scope["path"] = "/health"
                scope["raw_path"] = b"/health"
            elif path in ("/api", "/api/"):
                scope["path"] = "/"
                scope["raw_path"] = b"/"
        await self.inner_app(scope, receive, send)


app = PathRewriteMiddleware(_raw_app)
