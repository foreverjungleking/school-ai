from fastapi import APIRouter, Depends, Path

from school_ai.api.dependencies import get_school_data_service
from school_ai.api.schemas.school_data import (
    ActivityResponse,
    AvailabilityResponse,
    RoomResponse,
    StudentGroupResponse,
    TeacherResponse,
)
from school_ai.services import SchoolDataService

router = APIRouter()


@router.get("/teachers", response_model=tuple[TeacherResponse, ...], tags=["teachers"])
def list_teachers(
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.list_teachers()


@router.get("/teachers/{teacher_id}", response_model=TeacherResponse, tags=["teachers"])
def get_teacher(
    teacher_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_teacher(teacher_id)


@router.get(
    "/teachers/{teacher_id}/availability",
    response_model=tuple[AvailabilityResponse, ...],
    tags=["teachers"],
)
def get_teacher_availability(
    teacher_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_teacher(teacher_id).availability


@router.get("/rooms", response_model=tuple[RoomResponse, ...], tags=["rooms"])
def list_rooms(service: SchoolDataService = Depends(get_school_data_service)):
    return service.list_rooms()


@router.get("/rooms/{room_id}", response_model=RoomResponse, tags=["rooms"])
def get_room(
    room_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_room(room_id)


@router.get(
    "/rooms/{room_id}/availability",
    response_model=tuple[AvailabilityResponse, ...],
    tags=["rooms"],
)
def get_room_availability(
    room_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_room(room_id).availability


@router.get(
    "/student-groups",
    response_model=tuple[StudentGroupResponse, ...],
    tags=["student groups"],
)
def list_student_groups(
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.list_student_groups()


@router.get(
    "/student-groups/{group_id}",
    response_model=StudentGroupResponse,
    tags=["student groups"],
)
def get_student_group(
    group_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_student_group(group_id)


@router.get(
    "/activities", response_model=tuple[ActivityResponse, ...], tags=["activities"]
)
def list_activities(
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.list_activities()


@router.get(
    "/activities/{activity_id}",
    response_model=ActivityResponse,
    tags=["activities"],
)
def get_activity(
    activity_id: int = Path(gt=0),
    service: SchoolDataService = Depends(get_school_data_service),
):
    return service.get_activity(activity_id)
