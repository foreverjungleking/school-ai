"""Deterministic, network-free provider for tests and local smoke checks."""

from typing import Any

from pydantic import ValidationError

from school_ai.ai.models import ChatMessage, ProviderTurn, ToolDefinition
from school_ai.ai.providers.base import ProviderResponseError


class FakeProvider:
    """Return a scripted sequence of provider turns without network access."""

    name = "fake"

    def __init__(self, *turns: ProviderTurn | dict[str, Any]) -> None:
        self._turns = list(turns)
        self.calls: list[tuple[tuple[ChatMessage, ...], tuple[ToolDefinition, ...]]] = []

    async def generate(
        self,
        messages: tuple[ChatMessage, ...],
        tools: tuple[ToolDefinition, ...],
    ) -> ProviderTurn:
        self.calls.append((messages, tools))
        if not self._turns:
            raise ProviderResponseError("FakeProvider has no scripted response left")
        try:
            return ProviderTurn.model_validate(self._turns.pop(0))
        except (ValidationError, TypeError) as exc:
            raise ProviderResponseError("FakeProvider scripted response is invalid") from exc
