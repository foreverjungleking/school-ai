"""Provider-neutral AI and tool-call models."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AIModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChatMessage(AIModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ToolDefinition(AIModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(AIModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProviderTurn(AIModel):
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class ToolExecution(AIModel):
    name: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str | None = None


class ChatResult(AIModel):
    assistant_text: str
    tool_calls: tuple[ToolExecution, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
