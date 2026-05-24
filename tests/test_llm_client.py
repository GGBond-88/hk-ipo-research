"""Unit tests for LLMClient cache behaviour (src/hk_ipo/llm_client.py)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from hk_ipo.llm_client import LLMClient


def _make_fake_completion(content: str = "cached response") -> ChatCompletion:
    """Build a minimal realistic ChatCompletion for testing."""
    return ChatCompletion(
        id="chatcmpl-fake",
        created=0,
        model="test-model",
        object="chat.completion",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content=content,
                    role="assistant",
                ),
            )
        ],
        usage=CompletionUsage(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
    )


# We reset the singleton between tests so cache state does not leak.
@pytest.fixture(autouse=True)
def reset_singleton():
    LLMClient._instance = None
    yield
    LLMClient._instance = None


class TestCacheKeyDeterminism:
    def test_same_params_produce_same_key(self):
        client = LLMClient()
        msgs = [{"role": "user", "content": "hello"}]
        k1 = client._cache_key("gpt-4o", msgs, temperature=0.0)
        k2 = client._cache_key("gpt-4o", msgs, temperature=0.0)
        assert k1 == k2

    def test_different_temperature_produces_different_key(self):
        client = LLMClient()
        msgs = [{"role": "user", "content": "hello"}]
        k1 = client._cache_key("gpt-4o", msgs, temperature=0.0)
        k2 = client._cache_key("gpt-4o", msgs, temperature=0.7)
        assert k1 != k2

    def test_different_model_produces_different_key(self):
        client = LLMClient()
        msgs = [{"role": "user", "content": "hello"}]
        k1 = client._cache_key("gpt-4o", msgs, temperature=0.0)
        k2 = client._cache_key("gpt-4o-mini", msgs, temperature=0.0)
        assert k1 != k2


class TestCachePath:
    def test_cache_path_uses_first_two_hex_chars(self):
        client = LLMClient()
        key = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        path = client._cache_path(key)
        assert path.parts[-2] == "ab"
        assert path.name == f"{key}.json"


class TestCacheHit:
    def test_second_call_returns_cached_and_does_not_call_api(self):
        """First call hits the (mocked) API; second identical call returns cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "llm_cache"
            with patch.dict(os.environ, {"LLM_CACHE_DIR": str(cache_dir)}):
                client = LLMClient()
                fake_resp = _make_fake_completion("hello world")
                client._client = MagicMock()
                client._client.chat.completions.create.return_value = fake_resp

                resp1 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )
                assert resp1.choices[0].message.content == "hello world"
                assert client._client.chat.completions.create.call_count == 1

                # Second call: should be cache hit, no additional API call.
                resp2 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )
                assert resp2.choices[0].message.content == "hello world"
                assert client._client.chat.completions.create.call_count == 1

    def test_different_temperature_is_cache_miss(self):
        """Different temperature => different key => fresh API call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "llm_cache"
            with patch.dict(os.environ, {"LLM_CACHE_DIR": str(cache_dir)}):
                client = LLMClient()
                client._client = MagicMock()
                client._client.chat.completions.create.side_effect = [
                    _make_fake_completion("cold"),
                    _make_fake_completion("hot"),
                ]

                r1 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )
                assert r1.choices[0].message.content == "cold"
                assert client._client.chat.completions.create.call_count == 1

                r2 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.7,
                )
                assert r2.choices[0].message.content == "hot"
                assert client._client.chat.completions.create.call_count == 2

    def test_llm_cache_disable_forces_fresh_call(self):
        """LLM_CACHE_DISABLE=1 ignores existing cache and calls API."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "llm_cache"
            with patch.dict(os.environ, {
                "LLM_CACHE_DIR": str(cache_dir),
                "LLM_CACHE_DISABLE": "1",
            }):
                client = LLMClient()
                client._client = MagicMock()
                client._client.chat.completions.create.side_effect = [
                    _make_fake_completion("first"),
                    _make_fake_completion("second"),
                ]

                r1 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )
                assert r1.choices[0].message.content == "first"

                # Even though cache file was written, disable forces new call.
                r2 = client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )
                assert r2.choices[0].message.content == "second"
                assert client._client.chat.completions.create.call_count == 2

    def test_cache_file_content_is_valid_json(self):
        """Cache file on disk contains a serialized ChatCompletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "llm_cache"
            with patch.dict(os.environ, {"LLM_CACHE_DIR": str(cache_dir)}):
                client = LLMClient()
                fake_resp = _make_fake_completion("persisted")
                client._client = MagicMock()
                client._client.chat.completions.create.return_value = fake_resp

                client.chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    stage="test",
                    temperature=0.0,
                )

                # Find the cache file.
                json_files = list(cache_dir.rglob("*.json"))
                assert len(json_files) == 1
                raw = json.loads(json_files[0].read_text(encoding="utf-8"))
                assert "_cached_at" in raw
                assert "response" in raw
                # Reconstruct via model_validate_json to confirm format.
                reconstructed = ChatCompletion.model_validate_json(raw["response"])
                assert reconstructed.choices[0].message.content == "persisted"
