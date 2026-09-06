"""Normalized data models returned by MyIIS MCP tools."""

from pydantic import BaseModel, Field


class NormalizedLesson(BaseModel):
    """Normalized representation of a single class / lesson."""

    subject: str = Field(description="Краткое название предмета (например, 'ЭМП')")
    subject_full_name: str | None = Field(default=None, description="Полное название предмета")
    lesson_type: str = Field(description="Тип занятия: ЛК (лекция), ПЗ (практика), ЛР (лабораторная) и т.д.")
    start_time: str = Field(description="Время начала в формате ЧЧ:ММ (например, '08:30')")
    end_time: str = Field(description="Время окончания в формате ЧЧ:ММ (например, '09:55')")
    date: str | None = Field(default=None, description="Конкретная дата занятия в формате ГГГГ-ММ-ДД")
    day_of_week: str = Field(description="День недели на русском ('Понедельник', 'Вторник'...)")
    week_numbers: list[int] = Field(default_factory=list, description="Номера учебных недель (1-4), когда проводится занятие")
    subgroup: int = Field(default=0, description="Номер подгруппы (0 - вся группа, 1 - 1-я подгруппа, 2 - 2-я подгруппа)")
    auditories: list[str] = Field(default_factory=list, description="Список аудиторий (например, ['112-3 к.'])")
    building: str | None = Field(default=None, description="Номер учебного корпуса")
    teachers: list[str] = Field(default_factory=list, description="Преподаватели занятия (ФИО)")
    groups: list[str] = Field(default_factory=list, description="Учебные группы на занятии")
    note: str | None = Field(default=None, description="Примечание к занятию")


class DaySchedule(BaseModel):
    """Schedule for a single day."""

    date: str | None = Field(default=None, description="Дата в формате ГГГГ-ММ-ДД")
    day_of_week: str = Field(description="Название дня недели ('Понедельник', 'Вторник'...)")
    week_number: int | None = Field(default=None, description="Номер учебной недели (1-4)")
    lessons: list[NormalizedLesson] = Field(default_factory=list, description="Список занятий в этот день")


class ScheduleResult(BaseModel):
    """Comprehensive schedule result for a group or teacher."""

    target: str = Field(description="Название группы или ФИО преподавателя")
    target_type: str = Field(description="Тип субъекта: 'group' или 'teacher'")
    current_week: int = Field(description="Текущая учебная неделя БГУИР (1-4)")
    query_date: str | None = Field(default=None, description="Запрошенная дата (если был фильтр по дате)")
    days: list[DaySchedule] = Field(default_factory=list, description="Расписание по дням")
    total_lessons: int = Field(default=0, description="Общее количество найденных занятий")
    summary: str = Field(description="Краткая текстовая сводка расписания для удобства LLM")


class GroupSearchItem(BaseModel):
    """Found student group item."""

    name: str = Field(description="Номер группы (например, '310101')")
    course: int | None = Field(default=None, description="Курс (1-5)")
    faculty: str | None = Field(default=None, description="Аббревиатура факультета (например, 'ФКП')")
    speciality: str | None = Field(default=None, description="Специальность")


class GroupSearchResponse(BaseModel):
    """Result of searching student groups."""

    query: str = Field(description="Поисковый запрос")
    count: int = Field(description="Количество найденных групп")
    groups: list[GroupSearchItem] = Field(default_factory=list, description="Список найденных групп")
    summary: str = Field(description="Краткое описание результатов поиска")


class TeacherSearchItem(BaseModel):
    """Found teacher item."""

    fio: str = Field(description="ФИО преподавателя")
    url_id: str = Field(description="Уникальный идентификатор преподавателя для API (urlId)")
    departments: list[str] = Field(default_factory=list, description="Кафедры преподавателя")
    degree: str | None = Field(default=None, description="Ученая степень")
    rank: str | None = Field(default=None, description="Ученое звание")
    photo_link: str | None = Field(default=None, description="Ссылка на фото")


class TeacherSearchResponse(BaseModel):
    """Result of searching teachers."""

    query: str = Field(description="Поисковый запрос")
    count: int = Field(description="Количество найденных преподавателей")
    teachers: list[TeacherSearchItem] = Field(default_factory=list, description="Список найденных преподавателей")
    summary: str = Field(description="Краткое описание результатов поиска")


class CurrentWeekResponse(BaseModel):
    """Information about current instructional week and semester dates."""

    current_week: int = Field(description="Текущая учебная неделя (1, 2, 3 или 4)")
    today: str = Field(description="Сегодняшняя дата в формате ГГГГ-ММ-ДД")
    day_of_week: str = Field(description="Текущий день недели на русском")
    summary: str = Field(description="Краткое текстовое пояснение")
