"""AI harness presentation adapter."""

from fastapi import APIRouter, Depends

from school_ai.ai.harness import AIHarness
from school_ai.api.dependencies import get_ai_harness
from school_ai.api.schemas.ai import AIChatRequest, AIChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    request: AIChatRequest,
    harness: AIHarness = Depends(get_ai_harness),
):
    return await harness.chat(request.message)
