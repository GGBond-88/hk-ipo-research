"""Singleton OpenAI client with per-call token/cost logging."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, ClassVar, Optional

import openai
from openai.types.chat import ChatCompletion

# USD per 1K tokens for common models (input/output).
# Unknown models log cost_usd=null.
_PRICING: dict[str, dict[str, float]] = {
    "openai/gpt-4o":              {"in": 0.0025,  "out": 0.01},
    "openai/gpt-4o-mini":         {"in": 0.00015, "out": 0.0006},
    "deepseek/deepseek-v4-pro":   {"in": 0.00027, "out": 0.0011},
    "deepseek/deepseek-chat":     {"in": 0.00014, "out": 0.00028},
}


class LLMClient:
    _instance: ClassVar[Optional["LLMClient"]] = None
    _class_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._client = openai.OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY", "placeholder-not-set"),
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
        log_path = os.environ.get("LLM_LOG_PATH", "data/logs/llm_calls.jsonl")
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_lock = threading.Lock()

    @classmethod
    def get(cls) -> "LLMClient":
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def chat(self, *, model: str, messages: list[dict[str, Any]], stage: str, **kw: Any) -> Any:
        cache_key = self._cache_key(model, messages, **kw)
        cache_path = self._cache_path(cache_key)
        if cache_path.exists() and os.environ.get("LLM_CACHE_DISABLE") != "1":
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            resp = ChatCompletion.model_validate_json(cached["response"])
            self._append_log(
                stage=stage, model=model, cache_hit=True, cache_key=cache_key,
                in_tok=None, out_tok=None, cost_usd=None, latency_s=None,
            )
            return resp

        t0 = time.monotonic()
        resp = self._client.chat.completions.create(model=model, messages=messages, **kw)
        latency = time.monotonic() - t0
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", None) if usage else None
        out_tok = getattr(usage, "completion_tokens", None) if usage else None
        cost = self._compute_cost(model, in_tok, out_tok)
        self._append_log(
            stage=stage, model=model, cache_hit=False,
            in_tok=in_tok, out_tok=out_tok,
            cost_usd=cost, latency_s=round(latency, 3),
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "_cached_at": time.time(),
            "response": resp.model_dump_json(),
        }, ensure_ascii=False), encoding="utf-8")
        return resp

    # ---- cache helpers ----

    def _cache_key(self, model: str, messages: list[dict[str, Any]], **kw: Any) -> str:
        """Build a content-addressed SHA-256 key from request params."""
        rf = self._serialize_response_format(kw.get("response_format"))
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": kw.get("temperature"),
            "response_format": rf,
        }, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        root = Path(os.environ.get("LLM_CACHE_DIR", "data/llm_cache"))
        return root / key[:2] / f"{key}.json"

    @staticmethod
    def _serialize_response_format(rf: Any) -> Any:
        """Convert response_format to a JSON-serializable form for consistent hashing."""
        if rf is None:
            return None
        if isinstance(rf, dict):
            return rf
        if isinstance(rf, type):
            return {"__pydantic_model__": rf.__name__}
        if hasattr(rf, "model_dump"):
            return rf.model_dump()
        return str(rf)

    # ---- helpers ----

    def _compute_cost(self, model: str, in_tok: int | None, out_tok: int | None) -> float | None:
        p = _PRICING.get(model)
        if p is None or in_tok is None or out_tok is None:
            return None
        return round((in_tok / 1000) * p["in"] + (out_tok / 1000) * p["out"], 6)

    def _append_log(self, **fields: Any) -> None:
        line = json.dumps({"ts": time.time(), **fields}, ensure_ascii=False)
        with self._log_lock, self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
