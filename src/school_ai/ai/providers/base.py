"""Provider abstraction independent of application capabilities."""

from typing import Protocol

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolDefinition


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderResponseError(RuntimeError):
    pass


class LLMProvider(Protocol):
    async def generate(
        self,
        messages: tuple[ChatMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> ProviderTurn: ...
