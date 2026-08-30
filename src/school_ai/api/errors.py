"""Stable HTTP error responses for application-service failures."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from school_ai.ai.harness import HarnessError
from school_ai.ai.providers import ProviderConfigurationError
from school_ai.services.dto import GenerateScheduleResult
from school_ai.services.school_data import SchoolDataNotFoundError
from school_ai.services.scheduling import (
    InvalidScheduleTransitionError,
    ScheduleNotFoundError,
    ScheduleVersionNotFoundError,
    SchedulingDataIncompleteError,
)
from school_ai.solver import SolveStatus

logger = logging.getLogger(__name__)


class ScheduleGenerationFailed(Exception):
    def __init__(self, result: GenerateScheduleResult) -> None:
        self.result = result


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProviderConfigurationError)
    async def provider_not_configured(
        request: Request, exc: ProviderConfigurationError
    ) -> JSONResponse:
        return _error(503, "AI_PROVIDER_NOT_CONFIGURED", str(exc))

    @app.exception_handler(HarnessError)
    async def invalid_ai_response(
        request: Request, exc: HarnessError
    ) -> JSONResponse:
        return _error(502, "AI_RESPONSE_INVALID", str(exc))

    @app.exception_handler(SchoolDataNotFoundError)
    async def school_data_not_found(
        request: Request, exc: SchoolDataNotFoundError
    ) -> JSONResponse:
        return _error(404, "RESOURCE_NOT_FOUND", str(exc))

    @app.exception_handler(ScheduleNotFoundError)
    async def schedule_not_found(
        request: Request, exc: ScheduleNotFoundError
    ) -> JSONResponse:
        return _error(404, "SCHEDULE_NOT_FOUND", str(exc))

    @app.exception_handler(ScheduleVersionNotFoundError)
    async def version_not_found(
        request: Request, exc: ScheduleVersionNotFoundError
    ) -> JSONResponse:
        return _error(404, "SCHEDULE_VERSION_NOT_FOUND", str(exc))

    @app.exception_handler(InvalidScheduleTransitionError)
    async def invalid_transition(
        request: Request, exc: InvalidScheduleTransitionError
    ) -> JSONResponse:
        return _error(409, "INVALID_SCHEDULE_TRANSITION", str(exc))

    @app.exception_handler(SchedulingDataIncompleteError)
    async def scheduling_data_incomplete(
        request: Request, exc: SchedulingDataIncompleteError
    ) -> JSONResponse:
        missing = ", ".join(exc.missing)
        return _error(
            409,
            "SCHEDULING_DATA_INCOMPLETE",
            f"Cannot generate a schedule until demo data is loaded. Missing: {missing}.",
        )

    @app.exception_handler(ScheduleGenerationFailed)
    async def schedule_generation_failed(
        request: Request, exc: ScheduleGenerationFailed
    ) -> JSONResponse:
        result = exc.result
        if result.solver_status is SolveStatus.INFEASIBLE:
            status_code = 409
            code = "SCHEDULE_INFEASIBLE"
        elif result.solver_status is SolveStatus.UNKNOWN:
            status_code = 503
            code = "SOLVER_STATUS_UNKNOWN"
        else:
            status_code = 500
            code = "INVALID_SOLVER_RESULT"
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": {
                    "code": code,
                    "message": result.message,
                    "solver_status": result.solver_status.value,
                    "solve_duration_seconds": result.solve_duration_seconds,
                    "solver_metadata": result.solver_metadata,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def invalid_operation(request: Request, exc: ValueError) -> JSONResponse:
        return _error(400, "INVALID_REQUEST", "request could not be processed")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error")
        return _error(500, "INTERNAL_SERVER_ERROR", "internal server error")
