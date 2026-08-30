"""Environment-driven provider construction."""

import os

from school_ai.ai.providers.base import LLMProvider, ProviderConfigurationError
from school_ai.ai.providers.fake import FakeProvider
from school_ai.ai.providers.ollama import OllamaProvider
from school_ai.ai.providers.openai import OpenAIProvider


def create_provider() -> LLMProvider:
    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    if provider == "fake":
        return FakeProvider(
            {"text": "FakeProvider is configured; no tool response was scripted."}
        )
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "").strip()
        if not model:
            raise ProviderConfigurationError("OLLAMA_MODEL is required")
        return OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), model)
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "").strip()
        if not api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required when AI_PROVIDER=openai"
            )
        if not model:
            raise ProviderConfigurationError(
                "OPENAI_MODEL is required when AI_PROVIDER=openai"
            )
        return OpenAIProvider(api_key, model)
    raise ProviderConfigurationError(
        "AI_PROVIDER must be 'fake', 'ollama', or 'openai'"
    )
