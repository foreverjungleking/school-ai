from fastapi import APIRouter, Request

from school_ai.api.schemas.common import HealthResponse
from school_ai.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok", environment=settings.environment, version=settings.app_version
    )
