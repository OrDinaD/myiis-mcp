import pytest
import httpx
from myiis_mcp.bsuir import (
    BSUIRClient,
    GroupNotFoundError,
    TeacherNotFoundError,
    BSUIRApiError,
    BSUIRTimeoutError,
)

@pytest.mark.asyncio
async def test_bsuir_client_404_group():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        with pytest.raises(GroupNotFoundError) as exc_info:
            await client.get_group_schedule("999999")
        assert "999999" in str(exc_info.value)

@pytest.mark.asyncio
async def test_bsuir_client_404_teacher():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        with pytest.raises(TeacherNotFoundError) as exc_info:
            await client.get_employee_schedule("nobody")
        assert "nobody" in str(exc_info.value)

@pytest.mark.asyncio
async def test_bsuir_client_current_week_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/schedule/current-week":
            return httpx.Response(200, text="2\n")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        week = await client.get_current_week()
        assert week == 2

@pytest.mark.asyncio
async def test_bsuir_client_find_groups():
    groups_data = [
        {"name": "310101", "facultyAbbrev": "ФКП", "facultyName": "Факультет КП", "course": 3, "specialityAbbrev": "ИСиТ"},
        {"name": "310102", "facultyAbbrev": "ФКП", "facultyName": "Факультет КП", "course": 3, "specialityAbbrev": "ИСиТ"},
        {"name": "250501", "facultyAbbrev": "ФКСИС", "facultyName": "Факультет КСИС", "course": 2, "specialityAbbrev": "ПОИТ"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/student-groups":
            import json
            return httpx.Response(200, json=groups_data)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        matches = await client.find_groups(query="3101")
        assert len(matches) == 2
        assert matches[0].name == "310101"

        matches_course = await client.find_groups(query="ИСиТ", course=3)
        assert len(matches_course) == 2

        matches_empty = await client.find_groups(query="nonexistent")
        assert len(matches_empty) == 0

@pytest.mark.asyncio
async def test_bsuir_client_find_employees():
    employees_data = [
        {
            "id": 1,
            "firstName": "Иван",
            "lastName": "Иванов",
            "middleName": "Иванович",
            "fio": "Иванов И. И.",
            "urlId": "i-ivanov",
            "academicDepartment": ["Каф. ПОИТ"],
        },
        {
            "id": 2,
            "firstName": "Петр",
            "lastName": "Петров",
            "middleName": "Петрович",
            "fio": "Петров П. П.",
            "urlId": "p-petrov",
            "academicDepartment": ["Каф. ИРТ"],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/employees/all":
            return httpx.Response(200, json=employees_data)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        res = await client.find_employees("Иванов")
        assert len(res) == 1
        assert res[0].url_id == "i-ivanov"

        res_dep = await client.find_employees("ПОИТ")
        assert len(res_dep) == 1

        # Fuzzy typo match
        res_fuzzy = await client.find_employees("ивановв")
        assert len(res_fuzzy) == 1
        assert res_fuzzy[0].url_id == "i-ivanov"


@pytest.mark.asyncio
async def test_bsuir_client_get_employee_details():
    details_data = {
        "id": 506004,
        "firstName": "Юлия",
        "lastName": "Герман",
        "middleName": "Олеговна",
        "degree": "к.т.н.",
        "rank": "доцент",
        "email": "jgerman@bsuir.by",
        "urlId": "iu-german",
        "jobPositions": [
            {
                "employeeDepartmentId": 32605,
                "jobPosition": "доцент",
                "department": "Каф.ИТАС",
                "contacts": [
                    {
                        "phoneNumber": "+375172938904",
                        "auditory": "605а",
                        "buildingNumber": "5 к.",
                    }
                ],
            }
        ],
        "readingCourses": ["Мобильные приложения для информационных систем"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/employees/details-url" and request.url.params.get("urlId") == "iu-german":
            return httpx.Response(200, json=details_data)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://iis.bsuir.by/api/v1") as http_client:
        client = BSUIRClient(client=http_client)
        det = await client.get_employee_details("iu-german")
        assert det.first_name == "Юлия"
        assert det.email == "jgerman@bsuir.by"
        assert len(det.job_positions) == 1
        assert det.job_positions[0].contacts[0].auditory == "605а"
        assert "Мобильные приложения для информационных систем" in det.reading_courses

