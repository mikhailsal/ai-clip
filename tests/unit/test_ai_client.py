"""Tests for the AI client module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_clip.ai_client import (
    SYSTEM_PROMPT,
    AIClientError,
    _build_messages,
    _parse_sse_line,
    transform_text,
)


class TestBuildMessages:
    def test_message_structure(self):
        messages = _build_messages("Fix it", "hello world")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert "Fix it" in messages[1]["content"]
        assert "hello world" in messages[1]["content"]
        assert "---" in messages[1]["content"]


class TestParseSSELine:
    def test_data_with_content(self):
        data = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
        assert _parse_sse_line(f"data: {data}") == "hello"

    def test_done_signal(self):
        assert _parse_sse_line("data: [DONE]") is None

    def test_empty_line(self):
        assert _parse_sse_line("") is None

    def test_non_data_line(self):
        assert _parse_sse_line("event: message") is None

    def test_no_choices(self):
        assert _parse_sse_line("data: {}") is None

    def test_no_delta_content(self):
        data = json.dumps({"choices": [{"delta": {}}]})
        assert _parse_sse_line(f"data: {data}") is None

    def test_invalid_json(self):
        assert _parse_sse_line("data: {invalid") is None


def _make_sse_response(chunks: list[str], status: int = 200):
    """Build a mock HTTP response with SSE data lines."""
    lines = []
    for chunk in chunks:
        data = json.dumps({"choices": [{"delta": {"content": chunk}}]})
        lines.append(f"data: {data}\n".encode())
    lines.append(b"data: [DONE]\n")
    resp = MagicMock()
    resp.status = status
    resp.__iter__ = lambda self: iter(lines)
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    resp.close = MagicMock()
    return resp


class TestTransformText:
    def test_success(self):
        resp = _make_sse_response(["  Fixed", " text  "])
        with patch("urllib.request.urlopen", return_value=resp):
            result = transform_text(
                text="broken text",
                command_prompt="Fix it",
                api_key="sk-test",
                model="test-model",
                timeout=10,
            )
            assert result == "Fixed text"

    def test_raises_on_empty_key(self):
        with pytest.raises(AIClientError, match="not configured"):
            transform_text("text", "prompt", "", "model")

    def test_api_error(self):
        with (
            patch("urllib.request.urlopen", side_effect=Exception("connection refused")),
            pytest.raises(AIClientError, match="API request failed"),
        ):
            transform_text("text", "prompt", "sk-test", "model")

    def test_http_error_status(self):
        resp = _make_sse_response([], status=500)
        with (
            patch("urllib.request.urlopen", return_value=resp),
            pytest.raises(AIClientError, match="HTTP 500"),
        ):
            transform_text("text", "prompt", "sk-test", "model")

    def test_empty_content(self):
        resp = _make_sse_response([])
        with (
            patch("urllib.request.urlopen", return_value=resp),
            pytest.raises(AIClientError, match="empty content"),
        ):
            transform_text("text", "prompt", "sk-test", "model")

    def test_default_timeout(self):
        resp = _make_sse_response(["result"])
        with patch("urllib.request.urlopen", return_value=resp) as mock_open:
            transform_text("text", "prompt", "sk-test", "model")
            assert mock_open.call_args[1]["timeout"] == 30

    def test_strips_whitespace(self):
        resp = _make_sse_response(["\n  result\n  "])
        with patch("urllib.request.urlopen", return_value=resp):
            result = transform_text("text", "prompt", "sk-test", "model")
            assert result == "result"

    def test_streaming_error_during_iteration(self):
        def failing_iter():
            data = json.dumps({"choices": [{"delta": {"content": "partial"}}]})
            yield f"data: {data}\n".encode()
            raise ConnectionError("stream broken")

        resp = MagicMock()
        resp.status = 200
        resp.__iter__ = lambda self: failing_iter()
        resp.close = MagicMock()

        with (
            patch("urllib.request.urlopen", return_value=resp),
            pytest.raises(AIClientError, match="Streaming failed"),
        ):
            transform_text("text", "prompt", "sk-test", "model")

    def test_sends_correct_request(self):
        resp = _make_sse_response(["ok"])
        with patch("urllib.request.urlopen", return_value=resp) as mock_open:
            transform_text("hello", "Fix it", "sk-key", "my-model", timeout=15)
            req = mock_open.call_args[0][0]
            body = json.loads(req.data)
            assert body["model"] == "my-model"
            assert body["stream"] is True
            assert len(body["messages"]) == 2
            assert req.get_header("Authorization") == "Bearer sk-key"
            assert req.get_header("Content-type") == "application/json"
