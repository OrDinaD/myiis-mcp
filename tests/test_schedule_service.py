from datetime import date
import pytest
from myiis_mcp.schedule_service import (
    ScheduleService,
    calculate_week_for_date,
    parse_auditory_building,
    parse_date_query,
)
from myiis_mcp.bsuir.models import BSUIRLesson, BSUIRScheduleResponse, StudentGroup, Employee

def test_parse_date_query():
    base = date(2026, 9, 7) # Monday
    assert parse_date_query("today", base_date=base) == date(2026, 9, 7)
    assert parse_date_query("сегодня", base_date=base) == date(2026, 9, 7)
    assert parse_date_query("tomorrow", base_date=base) == date(2026, 9, 8)
    assert parse_date_query("завтра", base_date=base) == date(2026, 9, 8)
    assert parse_date_query("2026-09-15", base_date=base) == date(2026, 9, 15)
    assert parse_date_query("15.09.2026", base_date=base) == date(2026, 9, 15)
    assert parse_date_query(None) is None

    with pytest.raises(ValueError):
        parse_date_query("not-a-date")

def test_calculate_week_for_date():
    # Base: 2026-09-07 (Monday), week 1
    base = date(2026, 9, 7)
    assert calculate_week_for_date(date(2026, 9, 7), current_week=1, base_date=base) == 1
    assert calculate_week_for_date(date(2026, 9, 11), current_week=1, base_date=base) == 1
    # Next week: 2026-09-14
    assert calculate_week_for_date(date(2026, 9, 14), current_week=1, base_date=base) == 2
    # Week 3: 2026-09-21
    assert calculate_week_for_date(date(2026, 9, 21), current_week=1, base_date=base) == 3
    # Week 4: 2026-09-28
    assert calculate_week_for_date(date(2026, 9, 28), current_week=1, base_date=base) == 4
    # Week 1 again: 2026-10-05
    assert calculate_week_for_date(date(2026, 10, 5), current_week=1, base_date=base) == 1

def test_parse_auditory_building():
    aud, bld = parse_auditory_building("112-3 к.")
    assert aud == "112-3 к."
    assert bld == "3"

    aud2, bld2 = parse_auditory_building("401-4")
    assert bld2 == "4"

    aud3, bld3 = parse_auditory_building("303")
    assert bld3 is None

@pytest.mark.asyncio
async def test_schedule_service_date_filter(monkeypatch):
    raw_schedule = BSUIRScheduleResponse(
        schedules={
            "Понедельник": [
                BSUIRLesson(
                    subject="Математика",
                    lesson_type_abbrev="ЛК",
                    start_lesson_time="09:00",
                    end_lesson_time="10:20",
                    week_number=[1, 3],
                    num_subgroup=0,
                    auditories=["101-2 к."],
                ),
                BSUIRLesson(
                    subject="Физика",
                    lesson_type_abbrev="ЛР",
                    start_lesson_time="10:35",
                    end_lesson_time="11:55",
                    week_number=[2, 4],
                    num_subgroup=1,
                    auditories=["202-2 к."],
                ),
            ]
        }
    )

    class MockBSUIRClient:
        async def get_current_week(self):
            return 1
        async def get_group_schedule(self, group):
            return raw_schedule

    service = ScheduleService(client=MockBSUIRClient())

    # Query for Monday of week 1 (2026-09-07)
    base = date(2026, 9, 7)
    result = await service.get_group_schedule("123456", date_query="2026-09-07", base_date=base)
    assert result.total_lessons == 1
    assert result.days[0].lessons[0].subject == "Математика"
    assert result.days[0].lessons[0].building == "2"

    # Query for Monday of week 2 (2026-09-14)
    result_w2 = await service.get_group_schedule("123456", date_query="2026-09-14", base_date=base)
    assert result_w2.total_lessons == 1
    assert result_w2.days[0].lessons[0].subject == "Физика"

    # Query for Monday of week 2 with subgroup 2 (should be 0 lessons since Physics is for subgroup 1)
    result_sub2 = await service.get_group_schedule("123456", date_query="2026-09-14", subgroup=2, base_date=base)
    assert result_sub2.total_lessons == 0


@pytest.mark.asyncio
async def test_schedule_service_teacher_details():
    from myiis_mcp.bsuir.models import EmployeeDetails, JobPosition, EmployeeContact

    mock_details = EmployeeDetails(
        id=506004,
        first_name="Юлия",
        middle_name="Олеговна",
        last_name="Герман",
        degree="к.т.н.",
        rank="доцент",
        email="jgerman@bsuir.by",
        url_id="iu-german",
        job_positions=[
            JobPosition(
                job_position="доцент",
                department="Каф.ИТАС",
                contacts=[
                    EmployeeContact(
                        phone_number="+375172938904",
                        auditory="605а",
                        building_number="5 к.",
                    )
                ],
            )
        ],
        reading_courses=["Мобильные приложения"],
    )

    class MockBSUIRClient:
        async def find_employees(self, query):
            return [Employee(first_name="Юлия", last_name="Герман", url_id="iu-german")]

        async def get_employee_details(self, url_id):
            return mock_details

    service = ScheduleService(client=MockBSUIRClient())
    profile = await service.get_teacher_details("Герман")
    assert profile.email == "jgerman@bsuir.by"
    assert profile.fio == "Герман Юлия Олеговна"
    assert "Мобильные приложения" in profile.reading_courses
    assert len(profile.contacts) == 1
    assert profile.contacts[0].auditory == "605а"
    assert "https://libeldoc.bsuir.by" in profile.repository_url
    assert "https://iis.bsuir.by/employees/iu-german" == profile.profile_url


@pytest.mark.asyncio
async def test_schedule_service_multiple_teachers_surname_aggregation():
    from myiis_mcp.bsuir.models import EmployeeDetails, JobPosition, EmployeeContact

    details_yu = EmployeeDetails(
        id=506004,
        first_name="Юлия",
        middle_name="Олеговна",
        last_name="Герман",
        rank="доцент",
        email="jgerman@bsuir.by",
        url_id="iu-german",
        job_positions=[JobPosition(job_position="доцент", department="Каф.ИТАС", contacts=[EmployeeContact(auditory="605а", building_number="5 к.")])],
        reading_courses=["Мобильные приложения"],
    )
    details_ov = EmployeeDetails(
        id=500331,
        first_name="Олег",
        middle_name="Витольдович",
        last_name="Герман",
        rank="доцент",
        email="german@bsuir.by",
        url_id="o-german",
        job_positions=[JobPosition(job_position="доцент", department="Каф.ИТАС", contacts=[EmployeeContact(auditory="605-5", building_number="5 к.")])],
        reading_courses=["Интеллектуальные системы"],
    )

    class MockBSUIRClient:
        async def find_employees(self, query):
            return [
                Employee(first_name="Юлия", middle_name="Олеговна", last_name="Герман", url_id="iu-german"),
                Employee(first_name="Олег", middle_name="Витольдович", last_name="Герман", url_id="o-german"),
            ]

        async def get_employee_details(self, url_id):
            if url_id == "iu-german":
                return details_yu
            return details_ov

    service = ScheduleService(client=MockBSUIRClient())
    profile = await service.get_teacher_details("Герман")
    assert "jgerman@bsuir.by" in profile.email
    assert "german@bsuir.by" in profile.email
    assert "Юлия" in profile.fio and "Олег" in profile.fio
    assert "Мобильные приложения" in profile.reading_courses
    assert "Интеллектуальные системы" in profile.reading_courses
    assert len(profile.contacts) == 2

