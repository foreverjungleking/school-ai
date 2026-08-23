from fastapi import APIRouter, Depends, Path, Query, status

from school_ai.api.dependencies import get_scheduling_service
from school_ai.api.errors import ScheduleGenerationFailed
from school_ai.api.schemas.schedules import (
    CreateScheduleRequest,
    GenerateDraftRequest,
    GenerateDraftResponse,
    ScheduleComparisonResponse,
    ScheduleResponse,
    ScheduleVersionResponse,
)
from school_ai.services import SchedulingService
from school_ai.solver import TimeSlot

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    request: CreateScheduleRequest,
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.create_schedule(request.name)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.get_schedule(schedule_id)


@router.post(
    "/{schedule_id}/drafts",
    response_model=GenerateDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_schedule_draft(
    request: GenerateDraftRequest,
    schedule_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    result = service.generate_schedule_draft(
        schedule_id,
        tuple(TimeSlot.model_validate(item.model_dump()) for item in request.time_slots),
        request.max_solve_seconds,
    )
    if result.version is None:
        raise ScheduleGenerationFailed(result)
    return result


@router.get(
    "/{schedule_id}/versions", response_model=tuple[ScheduleVersionResponse, ...]
)
def list_schedule_versions(
    schedule_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.list_schedule_versions(schedule_id)


@router.get(
    "/{schedule_id}/published", response_model=ScheduleVersionResponse
)
def get_published_schedule_version(
    schedule_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.get_published_schedule_version(schedule_id)


@router.get(
    "/{schedule_id}/versions/{version_id}", response_model=ScheduleVersionResponse
)
def get_schedule_version(
    schedule_id: int = Path(gt=0),
    version_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.get_schedule_version(version_id, schedule_id)


@router.post(
    "/{schedule_id}/versions/{version_id}/publish",
    response_model=ScheduleVersionResponse,
)
def publish_schedule_version(
    schedule_id: int = Path(gt=0),
    version_id: int = Path(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.publish_schedule_version(version_id, schedule_id)


@router.get("/{schedule_id}/compare", response_model=ScheduleComparisonResponse)
def compare_schedule_versions(
    schedule_id: int = Path(gt=0),
    from_version_id: int = Query(gt=0),
    to_version_id: int = Query(gt=0),
    service: SchedulingService = Depends(get_scheduling_service),
):
    return service.compare_schedule_versions(
        from_version_id, to_version_id, schedule_id
    )
