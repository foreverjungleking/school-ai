"""Public AI harness request and response contracts."""

from typing import Any

from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AIToolCallResponse(BaseModel):
    name: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str | None = None


class AIChatResponse(BaseModel):
    assistant_text: str
    tool_calls: tuple[AIToolCallResponse, ...]
    metadata: dict[str, Any]
