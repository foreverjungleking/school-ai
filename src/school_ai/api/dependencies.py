"""FastAPI dependency wiring for database-backed application services."""

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from school_ai.repositories import (
    ScheduleRepository,
    SchoolDataRepository,
    SchedulingDataRepository,
)
from school_ai.services import SchoolDataService, SchedulingService


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def get_school_data_service(
    session: Session = Depends(get_session),
) -> SchoolDataService:
    return SchoolDataService(SchoolDataRepository(session))


def get_scheduling_service(
    session: Session = Depends(get_session),
) -> SchedulingService:
    return SchedulingService(
        ScheduleRepository(session), SchedulingDataRepository(session)
    )
