"""Manual, opt-in Ollama smoke test through the public AI API."""

import os

import httpx


PROMPTS = (
    "What can you help me with?",
    "List the teachers.",
    "Show me the current published schedule.",
    "Generate a new draft for the current schedule.",
)


def main() -> None:
    base_url = os.getenv("SCHOOL_AI_API_URL", "http://127.0.0.1:8000").rstrip("/")
    with httpx.Client(base_url=base_url, timeout=180) as client:
        for prompt in PROMPTS:
            print(f"\nUSER: {prompt}")
            response = client.post("/ai/chat", json={"message": prompt})
            response.raise_for_status()
            result = response.json()
            print(f"ASSISTANT: {result['assistant_text']}")
            print(
                "TOOLS:",
                [
                    {
                        "name": call["name"],
                        "success": call["success"],
                        "arguments": call["arguments"],
                    }
                    for call in result["tool_calls"]
                ],
            )
            print("METADATA:", result["metadata"])


if __name__ == "__main__":
    main()
