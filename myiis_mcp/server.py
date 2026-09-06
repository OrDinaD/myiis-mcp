"""MyIIS MCP Server implementation for ChatGPT, Claude, Cursor and universal MCP clients.

Pure Python — no pydantic, no native extensions. Runs cleanly on Cloudflare Python Workers (Pyodide).
"""

from __future__ import annotations

import inspect
import json
import uuid
from typing import Any, Callable, Coroutine, get_type_hints

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

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
    TeacherProfileResponse,
    TeacherSearchResponse,
)
from .schedule_service import ScheduleService

SERVER_INSTRUCTIONS = """
Сервер MyIIS MCP предоставляет актуальные данные о расписании занятий, учебных неделях, группах и преподавателях
Белорусского государственного университета информатики и радиоэлектроники (БГУИР / BSUIR) через официальный API ИИС БГУИР.

Основные возможности:
1. get_group_schedule: получение расписания группы (на сегодня, завтра, конкретную дату или всю неделю).
2. get_teacher_schedule: получение расписания преподавателя по фамилии или urlId (где найти преподавателя, аудитории занятий и контакты кафедры).
3. get_teacher_profile: получение контактов преподавателя (email, телефон кафедры, кабинет/аудитория, читаемые курсы/дисциплины, ссылки на профиль и репозиторий публикаций БГУИР).
4. search_groups: поиск учебной группы по номеру или специальности.
5. search_teachers: поиск преподавателя по фамилии, имени или кафедре.
6. get_current_week: получение номера текущей учебной недели (1-4) и сегодняшней даты.

Правила работы:
- В БГУИР действует 4-недельный учебный цикл (недели 1, 2, 3, 4).
- Если пользователь спрашивает расписание на 'сегодня' или 'завтра', передавайте в date значение 'today' или 'tomorrow'.
- Даты также можно передавать в формате 'ГГГГ-ММ-ДД' (например, '2026-09-07').
- Чтобы узнать контакты преподавателя (email, телефон, аудиторию кафедры, читаемые предметы), используйте get_teacher_profile.
- Чтобы узнать, где найти преподавателя в определенный день (аудитории пар, группы), используйте get_teacher_schedule.
- Если фамилия преподавателя введена с возможной опечаткой (например, 'лапо' вместо 'Лаппо'), сервер автоматически подберет наиболее подходящего сотрудника.
""".strip()


# ---------------------------------------------------------------------------
# JSON Schema helpers (no pydantic)
# ---------------------------------------------------------------------------

_PY_TO_JSON_TYPE: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}

# NoneType
_NoneType = type(None)


def _annotation_to_json_schema(annotation: Any, description: str = "") -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema fragment."""
    import typing

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Optional[X] → Union[X, None]
    if origin is typing.Union:
        non_none = [a for a in args if a is not _NoneType]
        if len(non_none) == 1:
            schema = _annotation_to_json_schema(non_none[0], description)
            if description:
                schema["description"] = description
            return schema
        # true union (rare in our codebase)
        schema = {"anyOf": [_annotation_to_json_schema(a) for a in non_none]}
        if description:
            schema["description"] = description
        return schema

    # list[X]
    if origin is list:
        schema: dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _annotation_to_json_schema(args[0])
        if description:
            schema["description"] = description
        return schema

    # Primitive
    json_type = _PY_TO_JSON_TYPE.get(annotation)
    if json_type:
        schema = {"type": json_type}
        if description:
            schema["description"] = description
        return schema

    # Fallback
    schema = {}
    if description:
        schema["description"] = description
    return schema


def _build_json_schema(func: Callable) -> dict[str, Any]:
    """Build a JSON Schema inputSchema dict from a function's signature + docstring."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        annotation = hints.get(name, Any)

        # Extract description from default if it has one (Field-style)
        description = ""
        default = param.default

        # Check if default carries a 'description' attr (our simple Field wrapper)
        if hasattr(default, "description"):
            description = default.description or ""
            # Treat this as "no actual default" — required
            has_default = hasattr(default, "default") and default.default is not _MISSING
        else:
            has_default = param.default is not inspect.Parameter.empty

        schema_fragment = _annotation_to_json_schema(annotation, description)
        properties[name] = schema_fragment

        if not has_default:
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


_MISSING = object()


class _FieldDescriptor:
    """Lightweight replacement for pydantic.Field — carries description + optional default."""

    def __init__(self, description: str = "", default: Any = _MISSING):
        self.description = description
        self.default = default

    def __repr__(self) -> str:
        return f"Field(description={self.description!r})"


def Field(description: str = "", default: Any = _MISSING) -> Any:  # noqa: N802
    """Simple drop-in for pydantic.Field used as function parameter default."""
    return _FieldDescriptor(description=description, default=default)


# ---------------------------------------------------------------------------
# Core MCP classes
# ---------------------------------------------------------------------------


class ToolAnnotations:
    """MCP tool annotations."""

    def __init__(
        self,
        read_only_hint: bool = True,
        destructive_hint: bool = False,
        open_world_hint: bool = False,
    ):
        self.read_only_hint = read_only_hint
        self.destructive_hint = destructive_hint
        self.open_world_hint = open_world_hint

    def to_mcp_dict(self) -> dict[str, bool]:
        return {
            "readOnlyHint": self.read_only_hint,
            "destructiveHint": self.destructive_hint,
            "openWorldHint": self.open_world_hint,
        }


class Tool:
    """Registered MCP tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Coroutine[Any, Any, Any]],
        annotations: ToolAnnotations,
        title: str | None = None,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.annotations = annotations
        self.title = title

    def to_mcp_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.annotations:
            data["annotations"] = self.annotations.to_mcp_dict()
        return data


class TransportSecuritySettings:
    """Security configuration placeholder for MCP server compatibility."""

    def __init__(
        self,
        enable_dns_rebinding_protection: bool = False,
        allowed_hosts: list[str] | None = None,
        allowed_origins: list[str] | None = None,
    ):
        self.enable_dns_rebinding_protection = enable_dns_rebinding_protection
        self.allowed_hosts = allowed_hosts or ["*"]
        self.allowed_origins = allowed_origins or ["*"]


def _serialize_result(raw_result: Any) -> str:
    """Serialize a tool result to a JSON string."""
    if hasattr(raw_result, "model_dump_json"):
        return raw_result.model_dump_json(indent=2)
    if hasattr(raw_result, "to_dict"):
        return json.dumps(raw_result.to_dict(), indent=2, ensure_ascii=False)
    if isinstance(raw_result, (dict, list)):
        return json.dumps(raw_result, indent=2, ensure_ascii=False)
    return str(raw_result)


def _coerce_arg(value: Any, annotation: Any) -> Any:
    """Best-effort coercion for a single argument value to match expected type."""
    import typing

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Optional[X]
    if origin is typing.Union:
        non_none = [a for a in args if a is not _NoneType]
        if value is None:
            return None
        if len(non_none) == 1:
            return _coerce_arg(value, non_none[0])
        return value

    if annotation is int or annotation == int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if annotation is float or annotation == float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if annotation is str or annotation == str:
        return str(value) if value is not None else value
    if annotation is bool or annotation == bool:
        if isinstance(value, str):
            return value.lower() not in ("false", "0", "no", "")
        return bool(value)
    return value


class MCPServer:
    """Model Context Protocol server with Streamable HTTP transport."""

    def __init__(self, name: str, instructions: str = "", version: str = "0.1.0"):
        self.name = name
        self.instructions = instructions
        self.version = version
        self.tools: dict[str, Tool] = {}
        self._custom_routes: list[Route] = []

    def tool(
        self,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
    ):
        """Decorator to register an async function as an MCP tool."""

        def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
            tool_name = name or func.__name__
            tool_desc = (description or func.__doc__ or "").strip()
            tool_annotations = annotations or ToolAnnotations()
            input_schema = _build_json_schema(func)

            registered_tool = Tool(
                name=tool_name,
                description=tool_desc,
                input_schema=input_schema,
                handler=func,
                annotations=tool_annotations,
                title=title,
            )
            self.tools[tool_name] = registered_tool
            return func

        return decorator

    def custom_route(self, path: str, methods: list[str] | None = None):
        """Register a custom Starlette route on the MCP application."""

        def decorator(handler: Callable[..., Coroutine[Any, Any, Any]]):
            self._custom_routes.append(
                Route(path, handler, methods=methods or ["GET"])
            )
            return handler

        return decorator

    async def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self.tools.values())

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> Any:
        """Call a registered tool directly (for tests)."""
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' not found")
        tool = self.tools[name]
        coerced = _coerce_tool_args(tool.handler, arguments or {})
        return await tool.handler(**coerced)

    async def _handle_jsonrpc_request(
        self, req: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Execute a single JSON-RPC 2.0 message."""
        jsonrpc = req.get("jsonrpc", "2.0")
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {}) or {}

        is_notification = req_id is None

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    }
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
                "instructions": self.instructions,
            }
            return {"jsonrpc": jsonrpc, "id": req_id, "result": result}

        if method == "notifications/initialized":
            return None

        if method == "ping":
            return {"jsonrpc": jsonrpc, "id": req_id, "result": {}}

        if method == "tools/list":
            result = {
                "tools": [t.to_mcp_dict() for t in self.tools.values()]
            }
            return {"jsonrpc": jsonrpc, "id": req_id, "result": result}

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {}) or {}
            if tool_name not in self.tools:
                return {
                    "jsonrpc": jsonrpc,
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found",
                    },
                }

            tool = self.tools[tool_name]
            try:
                coerced_args = _coerce_tool_args(tool.handler, tool_args)
                raw_result = await tool.handler(**coerced_args)
                text_content = _serialize_result(raw_result)
                result = {
                    "content": [{"type": "text", "text": text_content}],
                    "isError": False,
                }
            except Exception as exc:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error executing tool '{tool_name}': {exc}",
                        }
                    ],
                    "isError": True,
                }

            return {"jsonrpc": jsonrpc, "id": req_id, "result": result}

        if is_notification:
            return None

        return {
            "jsonrpc": jsonrpc,
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }

    def streamable_http_app(
        self,
        streamable_http_path: str = "/mcp",
        transport_security: TransportSecuritySettings | None = None,
        stateless_http: bool = True,
    ) -> Starlette:
        """Create Starlette ASGI application with Streamable HTTP and CORS."""

        async def mcp_endpoint(request: Request) -> Response:
            if request.method == "OPTIONS":
                return Response(
                    status_code=204,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id, Last-Event-ID, X-Requested-With",
                        "Access-Control-Max-Age": "86400",
                    },
                )

            accept_header = request.headers.get("accept", "")
            session_id = request.headers.get("mcp-session-id") or uuid.uuid4().hex

            cors_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id, Last-Event-ID, X-Requested-With",
                "Access-Control-Expose-Headers": "Mcp-Session-Id",
                "Mcp-Session-Id": session_id,
            }

            if request.method == "GET":
                if "text/event-stream" in accept_header:
                    stream_content = f"event: endpoint\ndata: {streamable_http_path}\n\n"
                    return Response(
                        stream_content,
                        media_type="text/event-stream; charset=utf-8",
                        headers=cors_headers,
                    )
                return JSONResponse(
                    {
                        "status": "ok",
                        "transport": "streamable-http",
                        "protocolVersion": "2024-11-05",
                        "server": self.name,
                        "session": session_id,
                    },
                    headers=cors_headers,
                )

            if request.method == "POST":
                try:
                    payload = await request.json()
                except Exception:
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32700,
                                "message": "Parse error: invalid JSON",
                            },
                        },
                        status_code=400,
                        headers=cors_headers,
                    )

                if isinstance(payload, list):
                    responses = []
                    for single_req in payload:
                        resp = await self._handle_jsonrpc_request(single_req)
                        if resp is not None:
                            responses.append(resp)
                    if not responses:
                        return Response(status_code=202, headers=cors_headers)
                    resp_data = responses
                elif isinstance(payload, dict):
                    resp = await self._handle_jsonrpc_request(payload)
                    if resp is None:
                        return Response(status_code=202, headers=cors_headers)
                    resp_data = resp
                else:
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32600,
                                "message": "Invalid request format",
                            },
                        },
                        status_code=400,
                        headers=cors_headers,
                    )

                if "text/event-stream" in accept_header:
                    sse_message = (
                        f"event: message\ndata: {json.dumps(resp_data, separators=(',', ':'), ensure_ascii=False)}\n\n"
                    )
                    return Response(
                        sse_message,
                        media_type="text/event-stream; charset=utf-8",
                        headers=cors_headers,
                    )

                return JSONResponse(resp_data, headers=cors_headers)

            return Response(status_code=405, headers=cors_headers)

        routes = [
            Route(
                streamable_http_path,
                mcp_endpoint,
                methods=["GET", "POST", "OPTIONS"],
            )
        ]
        routes.extend(self._custom_routes)

        return Starlette(routes=routes)


# ---------------------------------------------------------------------------
# Argument coercion helper (replaces pydantic model validation)
# ---------------------------------------------------------------------------

def _coerce_tool_args(func: Callable, arguments: dict[str, Any]) -> dict[str, Any]:
    """Coerce tool call arguments to match function signature types."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    result: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        annotation = hints.get(param_name)

        if param_name in arguments:
            value = arguments[param_name]
            if annotation is not None:
                value = _coerce_arg(value, annotation)
            result[param_name] = value
        elif param.default is not inspect.Parameter.empty:
            default = param.default
            # Unwrap our Field descriptor
            if isinstance(default, _FieldDescriptor):
                if default.default is not _MISSING:
                    result[param_name] = default.default
                # else: required param not provided — skip, let Python raise
            else:
                result[param_name] = default
        # else: required param missing — will raise TypeError on call

    return result


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="myiis",
    instructions=SERVER_INSTRUCTIONS,
    version="0.1.0",
)

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
    date: str | None = Field(
        default=None,
        description="Дата в формате ГГГГ-ММ-ДД или 'today' / 'сегодня', 'tomorrow' / 'завтра'",
    ),
    days: int = Field(
        default=1,
        description="Количество дней расписания начиная с указанной даты (от 1 до 14, по умолчанию 1)",
    ),
    subgroup: int | None = Field(
        default=None,
        description="Номер подгруппы (1 или 2). Если не указан — выводятся все занятия",
    ),
) -> ScheduleResult:
    """Get schedule for a student group with date and subgroup filtering."""
    try:
        return await _service.get_group_schedule(
            group=group, date_query=date, days=days, subgroup=subgroup
        )
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
    teacher: str = Field(
        description="Фамилия преподавателя (например, 'Василькова') или urlId (например, 'a-vasilkova')"
    ),
    date: str | None = Field(
        default=None,
        description="Дата в формате ГГГГ-ММ-ДД или 'today' / 'сегодня', 'tomorrow' / 'завтра'",
    ),
    days: int = Field(
        default=1,
        description="Количество дней расписания начиная с указанной даты (от 1 до 14, по умолчанию 1)",
    ),
) -> ScheduleResult:
    """Get schedule for a university teacher."""
    try:
        return await _service.get_teacher_schedule(
            teacher=teacher, date_query=date, days=days
        )
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
    name="get_teacher_profile",
    title="Get Teacher Profile and Contacts",
    description=(
        "Получить подробную карточку преподавателя БГУИР: контактные данные (email, телефон кафедры, "
        "номер аудитории и корпус), должность, ученую степень и звание, читаемые курсы/дисциплины, "
        "а также прямые ссылки на расписание, страницу сотрудника и репозиторий публикаций БГУИР. "
        "Принимает фамилию преподавателя (например, 'Герман', 'Лаппо', 'Василькова'), ФИО или urlId (например, 'iu-german')."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
)
async def get_teacher_profile(
    teacher: str = Field(
        description="Фамилия преподавателя (например, 'Герман', 'Лаппо'), ФИО или urlId (например, 'iu-german')"
    ),
) -> TeacherProfileResponse:
    """Get detailed profile and contacts for a university teacher."""
    try:
        return await _service.get_teacher_details(teacher=teacher)
    except TeacherNotFoundError as exc:
        return TeacherProfileResponse(
            fio=teacher,
            url_id=teacher,
            summary=f"Ошибка: {exc.message} Проверьте правильность написания фамилии или используйте search_teachers.",
        )
    except ValueError as exc:
        return TeacherProfileResponse(
            fio=teacher,
            url_id=teacher,
            summary=f"Ошибка: {exc}",
        )
    except (BSUIRTimeoutError, BSUIRApiError, BSUIRError) as exc:
        return TeacherProfileResponse(
            fio=teacher,
            url_id=teacher,
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
    query: str = Field(
        description="Поисковый запрос (номер группы, специальность или факультет, например '3101' или 'ИСиТ')"
    ),
    course: int | None = Field(default=None, description="Номер курса (1-5)"),
    faculty: str | None = Field(
        default=None, description="Аббревиатура факультета (например, 'ФКП', 'ФКСИС')"
    ),
) -> GroupSearchResponse:
    """Search student groups in BSUIR."""
    try:
        return await _service.search_groups(
            query=query, course=course, faculty=faculty
        )
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
    query: str = Field(
        description="Фамилия или имя преподавателя (например, 'Василькова', 'Иванов')"
    ),
    department: str | None = Field(
        default=None, description="Кафедра (например, 'Каф. ИРТ')"
    ),
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


# Custom routes
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
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
async def root_info(request: Request) -> JSONResponse:
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


# Build the Starlette app
security_settings = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["*"],
    allowed_origins=["*"],
)

app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    transport_security=security_settings,
    stateless_http=True,
)
