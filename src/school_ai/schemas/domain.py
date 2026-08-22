"""Validation and serialization schemas for core domain entities."""

from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeacherCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TeacherRead(TeacherCreate, ORMModel):
    id: int


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    capacity: int = Field(gt=0)
    room_type: str = Field(min_length=1, max_length=100)


class RoomRead(RoomCreate, ORMModel):
    id: int


class StudentGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    size: int = Field(gt=0)


class StudentGroupRead(StudentGroupCreate, ORMModel):
    id: int


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    student_group_id: int
    teacher_id: int
    sessions_per_week: int = Field(gt=0)
    duration_minutes: int = Field(gt=0)
    required_room_type: str = Field(min_length=1, max_length=100)


class ActivityRead(ActivityCreate, ORMModel):
    id: int


class TeacherAvailabilityCreate(BaseModel):
    teacher_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    available: bool = True

    @model_validator(mode="after")
    def validate_time_range(self) -> "TeacherAvailabilityCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class TeacherAvailabilityRead(TeacherAvailabilityCreate, ORMModel):
    id: int
