"""OpenRouter AI client for text transformations.

Uses the openai Python package pointed at https://openrouter.ai/api/v1.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a text transformation assistant. "
    "Return ONLY the transformed text, with no explanations, "
    "no surrounding quotes, and no additional commentary."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class AIClientError(Exception):
    """Raised when an AI API call fails."""


def _build_client(api_key: str):
    """Create an OpenAI client configured for OpenRouter."""
    from openai import OpenAI

    if not api_key:
        raise AIClientError("OpenRouter API key is not configured")
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
    )


def _build_messages(command_prompt: str, text: str) -> list[dict[str, str]]:
    """Build the chat messages for the AI request."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{command_prompt}\n\n---\n\n{text}"},
    ]


def transform_text(
    text: str,
    command_prompt: str,
    api_key: str,
    model: str,
    timeout: int = 30,
) -> str:
    """Send text to OpenRouter for transformation and return the result.

    Args:
        text: The source text to transform.
        command_prompt: The instruction for the AI (e.g., "Fix punctuation").
        api_key: OpenRouter API key.
        model: Model identifier (e.g., "google/gemini-2.0-flash-001").
        timeout: Request timeout in seconds.

    Returns:
        The transformed text from the AI.

    Raises:
        AIClientError: If the API call fails or returns empty.
    """
    client = _build_client(api_key)
    messages = _build_messages(command_prompt, text)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=timeout,
        )
    except Exception as exc:
        raise AIClientError(f"API request failed: {exc}") from exc

    if not response.choices:
        raise AIClientError("API returned no choices")

    content = response.choices[0].message.content
    if not content:
        raise AIClientError("API returned empty content")

    return content.strip()
