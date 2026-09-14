"""AI presentation adapter; context state belongs to application services."""
from fastapi import APIRouter, Depends, Header, Response
from uuid import UUID

from school_ai.ai.harness import AIHarness
from school_ai.api.dependencies import get_ai_harness, get_conversation_service
from school_ai.api.schemas.ai import AIChatRequest, AIChatResponse
from school_ai.services.conversations import ConversationService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/conversations", status_code=201)
def create_conversation(response: Response, conversations: ConversationService = Depends(get_conversation_service)):
    response.headers["Cache-Control"] = "no-store"
    return conversations.create()


@router.get("/conversations/{conversation_id}")
def read_conversation(conversation_id: UUID, response: Response,
                      x_conversation_token: str | None = Header(default=None, max_length=200),
                      conversations: ConversationService = Depends(get_conversation_service)):
    response.headers["Cache-Control"] = "no-store"
    return conversations.read(str(conversation_id), x_conversation_token)


@router.post("/conversations/{conversation_id}/reset")
def reset_conversation(conversation_id: UUID,
                       x_conversation_token: str | None = Header(default=None, max_length=200),
                       conversations: ConversationService = Depends(get_conversation_service)):
    return conversations.reset(str(conversation_id), x_conversation_token)


@router.post("/chat", response_model=AIChatResponse)
async def chat(request: AIChatRequest, response: Response,
               x_conversation_token: str | None = Header(default=None, max_length=200),
               harness: AIHarness = Depends(get_ai_harness),
               conversations: ConversationService = Depends(get_conversation_service)):
    response.headers["Cache-Control"] = "no-store"
    if request.conversation_id is None:
        return await harness.chat(request.message)
    return await conversations.chat(str(request.conversation_id), x_conversation_token, request.message, harness)
