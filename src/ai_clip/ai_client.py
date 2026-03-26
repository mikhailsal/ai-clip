"""OpenRouter AI client for text transformations.

Uses raw urllib3 + SSE streaming instead of the heavy openai package.
This saves ~1.2s of import overhead per invocation — critical since each
hotkey press spawns a fresh Python process.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a text transformation assistant. "
    "Return ONLY the transformed text, with no explanations, "
    "no surrounding quotes, and no additional commentary."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
HTTP_OK = 200


class AIClientError(Exception):
    """Raised when an AI API call fails."""


def _build_messages(command_prompt: str, text: str) -> list[dict[str, str]]:
    """Build the chat messages for the AI request."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{command_prompt}\n\n---\n\n{text}"},
    ]


def _parse_sse_line(line: str) -> str | None:
    """Extract content from a Server-Sent Events data line.

    Returns the delta content string, or None if the line is not a data chunk.
    """
    if not line.startswith("data: "):
        return None
    payload = line[6:]
    if payload.strip() == "[DONE]":
        return None
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return None
    choices = obj.get("choices", [])
    if not choices:
        return None
    delta = choices[0].get("delta", {})
    return delta.get("content")


def transform_text(
    text: str,
    command_prompt: str,
    api_key: str,
    model: str,
    timeout: int = 30,
) -> str:
    """Send text to OpenRouter for transformation and return the result.

    Uses raw urllib.request with SSE streaming instead of the openai package
    to avoid its ~1.2s import overhead (each hotkey press spawns a new process).

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
    if not api_key:
        raise AIClientError("OpenRouter API key is not configured")

    import urllib.request

    messages = _build_messages(command_prompt, text)
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        CHAT_COMPLETIONS_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except Exception as exc:
        raise AIClientError(f"API request failed: {exc}") from exc

    if resp.status != HTTP_OK:
        raise AIClientError(f"API returned HTTP {resp.status}")

    chunks: list[str] = []
    try:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            if not line:
                continue
            content = _parse_sse_line(line)
            if content:
                chunks.append(content)
    except Exception as exc:
        raise AIClientError(f"Streaming failed: {exc}") from exc
    finally:
        resp.close()

    result = "".join(chunks)
    if not result:
        raise AIClientError("API returned empty content")

    return result.strip()
