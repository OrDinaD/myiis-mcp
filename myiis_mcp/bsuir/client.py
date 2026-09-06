"""Asynchronous HTTP client for the official BSUIR IIS API."""

import time
import httpx
from typing import Any

from .exceptions import (
    BSUIRApiError,
    BSUIRTimeoutError,
    GroupNotFoundError,
    TeacherNotFoundError,
)
from .models import (
    BSUIRScheduleResponse,
    Employee,
    EmployeeDetails,
    StudentGroup,
)

BSUIR_API_BASE = "https://iis.bsuir.by/api/v1"
DEFAULT_TIMEOUT = 10.0
CACHE_TTL = 300  # 5 minutes


class BSUIRClient:
    """Async client for querying BSUIR IIS API endpoints."""

    def __init__(
        self,
        base_url: str = BSUIR_API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._external_client = client
        self._internal_client: httpx.AsyncClient | None = None

        # Lightweight in-memory cache
        self._groups_cache: list[StudentGroup] | None = None
        self._groups_cache_time: float = 0.0
        self._employees_cache: list[Employee] | None = None
        self._employees_cache_time: float = 0.0
        self._details_cache: dict[str, tuple[float, EmployeeDetails]] = {}
        self._client_loop: Any = None

    async def _get_client(self) -> httpx.AsyncClient:
        import asyncio

        if self._external_client is not None:
            return self._external_client

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._internal_client is None
            or self._internal_client.is_closed
            or self._client_loop is not current_loop
        ):
            self._internal_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"User-Agent": "MyIIS-MCP-Server/1.0 (+https://github.com/OrDinaD/myiis-mcp)"},
            )
            self._client_loop = current_loop
        return self._internal_client

    async def close(self) -> None:
        """Close internal HTTP client if created."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()
            self._internal_client = None

    async def __aenter__(self) -> "BSUIRClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = await self._get_client()
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            response = await client.request(method, url, **kwargs)
            return response
        except httpx.TimeoutException as exc:
            raise BSUIRTimeoutError(f"Таймаут запроса к BSUIR API ({path}): {exc}") from exc
        except httpx.RequestError as exc:
            raise BSUIRApiError(f"Сетевая ошибка при запросе к BSUIR API ({path}): {exc}") from exc

    async def get_current_week(self) -> int:
        """Fetch the current instructional week number (1, 2, 3, or 4)."""
        response = await self._request("GET", "/schedule/current-week")
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Не удалось получить текущую неделю от BSUIR API (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            return int(response.text.strip())
        except ValueError as exc:
            raise BSUIRApiError(f"Некорректный ответ текущей недели от BSUIR API: '{response.text}'") from exc

    async def get_student_groups(self, force_refresh: bool = False) -> list[StudentGroup]:
        """Fetch all registered student groups from BSUIR."""
        now = time.time()
        if not force_refresh and self._groups_cache is not None and (now - self._groups_cache_time) < CACHE_TTL:
            return self._groups_cache

        response = await self._request("GET", "/student-groups")
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Не удалось получить список групп от BSUIR API (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        data = response.json()
        groups = [StudentGroup.from_dict(item) for item in data if isinstance(item, dict)]
        self._groups_cache = groups
        self._groups_cache_time = now
        return groups

    async def get_employees(self, force_refresh: bool = False) -> list[Employee]:
        """Fetch all registered university employees / teachers."""
        now = time.time()
        if not force_refresh and self._employees_cache is not None and (now - self._employees_cache_time) < CACHE_TTL:
            return self._employees_cache

        response = await self._request("GET", "/employees/all")
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Не удалось получить список преподавателей от BSUIR API (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        data = response.json()
        employees = [Employee.from_dict(item) for item in data if isinstance(item, dict)]
        self._employees_cache = employees
        self._employees_cache_time = now
        return employees

    async def get_group_schedule(self, group: str) -> BSUIRScheduleResponse:
        """Fetch schedule for a specific student group number."""
        clean_group = group.strip()
        response = await self._request("GET", "/schedule", params={"studentGroup": clean_group})
        if response.status_code == 404:
            raise GroupNotFoundError(clean_group)
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Ошибка API БГУИР при получении расписания группы {clean_group} (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        data = response.json()
        return BSUIRScheduleResponse.from_dict(data)

    async def get_employee_schedule(self, url_id: str) -> BSUIRScheduleResponse:
        """Fetch schedule for a specific employee by their urlId."""
        clean_url_id = url_id.strip()
        response = await self._request("GET", f"/employees/schedule/{clean_url_id}")
        if response.status_code == 404:
            raise TeacherNotFoundError(clean_url_id)
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Ошибка API БГУИР при получении расписания преподавателя {clean_url_id} (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        data = response.json()
        return BSUIRScheduleResponse.from_dict(data)

    async def get_employee_details(self, url_id: str, force_refresh: bool = False) -> EmployeeDetails:
        """Fetch detailed profile information for an employee by urlId."""
        clean_url_id = url_id.strip()
        now = time.time()
        if not force_refresh and clean_url_id in self._details_cache:
            cache_time, cached_val = self._details_cache[clean_url_id]
            if (now - cache_time) < CACHE_TTL:
                return cached_val

        response = await self._request("GET", "/employees/details-url", params={"urlId": clean_url_id})
        if response.status_code == 404:
            raise TeacherNotFoundError(clean_url_id)
        if response.status_code != 200:
            raise BSUIRApiError(
                f"Ошибка API БГУИР при получении деталей преподавателя {clean_url_id} (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        data = response.json()
        details = EmployeeDetails.from_dict(data)
        self._details_cache[clean_url_id] = (now, details)
        return details

    async def find_groups(
        self,
        query: str,
        course: int | None = None,
        faculty: str | None = None,
        limit: int = 20,
    ) -> list[StudentGroup]:
        """Search student groups by query (name, speciality, faculty)."""
        all_groups = await self.get_student_groups()
        q = query.strip().lower()

        results: list[StudentGroup] = []
        for g in all_groups:
            if course is not None and g.course != course:
                continue
            if faculty is not None:
                fac = faculty.strip().lower()
                g_fac_abbrev = (g.faculty_abbrev or "").lower()
                g_fac_name = (g.faculty_name or "").lower()
                if fac not in g_fac_abbrev and fac not in g_fac_name:
                    continue

            name_match = q in g.name.lower()
            spec_match = (
                (g.speciality_name and q in g.speciality_name.lower())
                or (g.speciality_abbrev and q in g.speciality_abbrev.lower())
            )
            fac_match = (
                (g.faculty_name and q in g.faculty_name.lower())
                or (g.faculty_abbrev and q in g.faculty_abbrev.lower())
            )

            if name_match or spec_match or fac_match:
                results.append(g)
                if len(results) >= limit:
                    break

        return results

    async def find_employees(
        self,
        query: str,
        department: str | None = None,
        limit: int = 20,
    ) -> list[Employee]:
        """Search employees by name / surname / FIO / department, with token and typo tolerance."""
        all_employees = await self.get_employees()
        q = query.strip().lower()
        tokens = [t for t in q.split() if t]
        if not tokens:
            return []

        results: list[Employee] = []
        for emp in all_employees:
            if department is not None:
                dep_q = department.strip().lower()
                has_dep = any(dep_q in d.lower() for d in emp.academic_department)
                if not has_dep:
                    continue

            # Check department match
            dep_match = any(q in d.lower() for d in emp.academic_department)

            # Combined string for token matching
            full_text = " ".join(
                filter(
                    None,
                    [
                        emp.last_name,
                        emp.first_name,
                        emp.middle_name,
                        emp.fio,
                        emp.url_id,
                    ],
                )
            ).lower()

            name_match = all(t in full_text for t in tokens)

            if name_match or dep_match:
                results.append(emp)

        if results:
            # Sort by best match (exact surname/fio first)
            def rank(e: Employee) -> int:
                ln = (e.last_name or "").lower()
                fio = (e.fio or "").lower()
                if ln == q or fio == q or (e.url_id or "").lower() == q:
                    return 0
                if ln.startswith(tokens[0]):
                    return 1
                return 2

            results.sort(key=rank)
            return results[:limit]

        # Fuzzy matching fallback for typos (e.g. "лапо" -> "Лаппо")
        import difflib

        ln_map: dict[str, list[Employee]] = {}
        for emp in all_employees:
            if department is not None:
                dep_q = department.strip().lower()
                if not any(dep_q in d.lower() for d in emp.academic_department):
                    continue
            ln = (emp.last_name or "").lower()
            if ln:
                ln_map.setdefault(ln, []).append(emp)

        close_last_names = difflib.get_close_matches(tokens[0], list(ln_map.keys()), n=min(limit, 5), cutoff=0.65)
        fuzzy_results: list[Employee] = []
        for matched_ln in close_last_names:
            for emp in ln_map[matched_ln]:
                if emp not in fuzzy_results:
                    fuzzy_results.append(emp)
                    if len(fuzzy_results) >= limit:
                        break
            if len(fuzzy_results) >= limit:
                break

        return fuzzy_results
