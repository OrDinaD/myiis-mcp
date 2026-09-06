"""Data models for raw and intermediate BSUIR IIS API representations."""

from pydantic import BaseModel, Field, ConfigDict


class StudentGroup(BaseModel):
    """BSUIR student group information."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str
    course: int | None = None
    faculty_id: int | None = Field(default=None, alias="facultyId")
    faculty_name: str | None = Field(default=None, alias="facultyName")
    faculty_abbrev: str | None = Field(default=None, alias="facultyAbbrev")
    speciality_name: str | None = Field(default=None, alias="specialityName")
    speciality_abbrev: str | None = Field(default=None, alias="specialityAbbrev")
    calendar_id: str | None = Field(default=None, alias="calendarId")
    education_degree: int | None = Field(default=None, alias="educationDegree")


class Employee(BaseModel):
    """BSUIR employee / teacher information."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    middle_name: str | None = Field(default=None, alias="middleName")
    fio: str | None = None
    url_id: str | None = Field(default=None, alias="urlId")
    degree: str | None = None
    degree_abbrev: str | None = Field(default=None, alias="degreeAbbrev")
    rank: str | None = None
    photo_link: str | None = Field(default=None, alias="photoLink")
    calendar_id: str | None = Field(default=None, alias="calendarId")
    academic_department: list[str] = Field(default_factory=list, alias="academicDepartment")
    email: str | None = None

    @property
    def display_name(self) -> str:
        """Returns best display name (fio or full name)."""
        if self.fio:
            return self.fio
        parts = [p for p in [self.last_name, self.first_name, self.middle_name] if p]
        return " ".join(parts) if parts else (self.url_id or "Неизвестный преподаватель")


class BSUIRLesson(BaseModel):
    """Raw lesson item from BSUIR schedule payload."""

    model_config = ConfigDict(extra="ignore")

    subject: str | None = None
    subject_full_name: str | None = Field(default=None, alias="subjectFullName")
    lesson_type_abbrev: str | None = Field(default=None, alias="lessonTypeAbbrev")
    start_lesson_time: str | None = Field(default=None, alias="startLessonTime")
    end_lesson_time: str | None = Field(default=None, alias="endLessonTime")
    auditories: list[str] = Field(default_factory=list)
    num_subgroup: int = Field(default=0, alias="numSubgroup")
    week_number: list[int] = Field(default_factory=list, alias="weekNumber")
    date_lesson: str | None = Field(default=None, alias="dateLesson")
    start_lesson_date: str | None = Field(default=None, alias="startLessonDate")
    end_lesson_date: str | None = Field(default=None, alias="endLessonDate")
    note: str | None = None
    announcement: bool = False
    split: bool = False
    employees: list[Employee] = Field(default_factory=list)
    student_groups: list[dict] = Field(default_factory=list, alias="studentGroups")


class BSUIRScheduleResponse(BaseModel):
    """Raw response from /api/v1/schedule or /api/v1/employees/schedule."""

    model_config = ConfigDict(extra="ignore")

    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    start_exams_date: str | None = Field(default=None, alias="startExamsDate")
    end_exams_date: str | None = Field(default=None, alias="endExamsDate")
    student_group_dto: StudentGroup | None = Field(default=None, alias="studentGroupDto")
    employee_dto: Employee | None = Field(default=None, alias="employeeDto")
    schedules: dict[str, list[BSUIRLesson]] = Field(default_factory=dict)
    next_schedules: dict[str, list[BSUIRLesson]] | None = Field(default=None, alias="nextSchedules")
    exams: list[BSUIRLesson] = Field(default_factory=list)
    current_term: str | None = Field(default=None, alias="currentTerm")
    next_term: str | None = Field(default=None, alias="nextTerm")
    current_period: int | str | None = Field(default=None, alias="currentPeriod")
    is_zaoch_or_dist: bool = Field(default=False, alias="isZaochOrDist")
