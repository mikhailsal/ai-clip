"""Tests for the AI client module."""

from unittest.mock import MagicMock, patch

import pytest
from openai import OpenAIError

from ai_clip.ai_client import (
    OPENROUTER_BASE_URL,
    SYSTEM_PROMPT,
    AIClientError,
    _build_client,
    _build_messages,
    transform_text,
)


class TestBuildClient:
    def test_creates_client_with_key(self):
        with patch("openai.OpenAI") as mock_cls:
            _build_client("sk-test")
            mock_cls.assert_called_once_with(
                base_url=OPENROUTER_BASE_URL,
                api_key="sk-test",
            )

    def test_raises_on_empty_key(self):
        with pytest.raises(AIClientError, match="not configured"):
            _build_client("")

    def test_raises_on_none_key(self):
        with pytest.raises(AIClientError, match="not configured"):
            _build_client("")


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


class TestTransformText:
    def _mock_response(self, content: str | None = "Transformed"):
        choice = MagicMock()
        choice.message.content = content
        response = MagicMock()
        response.choices = [choice] if content is not None else []
        return response

    def test_success(self):
        mock_response = self._mock_response("  Fixed text  ")
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_build.return_value = mock_client

            result = transform_text(
                text="broken text",
                command_prompt="Fix it",
                api_key="sk-test",
                model="test-model",
                timeout=10,
            )
            assert result == "Fixed text"

            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["timeout"] == 10
            assert len(call_kwargs["messages"]) == 2

    def test_api_error(self):
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = OpenAIError("fail")
            mock_build.return_value = mock_client

            with pytest.raises(AIClientError, match="API request failed"):
                transform_text("text", "prompt", "sk-test", "model")

    def test_no_choices(self):
        mock_response = MagicMock()
        mock_response.choices = []
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_build.return_value = mock_client

            with pytest.raises(AIClientError, match="no choices"):
                transform_text("text", "prompt", "sk-test", "model")

    def test_empty_content(self):
        mock_response = self._mock_response("")
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_build.return_value = mock_client

            with pytest.raises(AIClientError, match="empty content"):
                transform_text("text", "prompt", "sk-test", "model")

    def test_default_timeout(self):
        mock_response = self._mock_response("result")
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_build.return_value = mock_client

            transform_text("text", "prompt", "sk-test", "model")
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["timeout"] == 30

    def test_strips_whitespace(self):
        mock_response = self._mock_response("\n  result\n  ")
        with patch("ai_clip.ai_client._build_client") as mock_build:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_build.return_value = mock_client

            result = transform_text("text", "prompt", "sk-test", "model")
            assert result == "result"
