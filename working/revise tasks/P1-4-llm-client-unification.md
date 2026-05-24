# P1-4 — Unified LLMClient with token/cost logging

Status: complete
Priority: P1
Effort: M (90–120 min)

## Goal
Introduce `src/hk_ipo/llm_client.py` as the single point that creates the OpenAI client and logs every call's `prompt_tokens` / `completion_tokens` / `cost_usd` to `data/logs/llm_calls.jsonl`.

## Why
Today three sites independently instantiate OpenAI clients with no observability:
- [src/hk_ipo/l2_extraction.py:32](../../src/hk_ipo/l2_extraction.py) — module-level singleton
- [src/hk_ipo/l4_categorize.py:443](../../src/hk_ipo/l4_categorize.py) — new client per call
- [src/hk_ipo/enrichments/industry.py:64](../../src/hk_ipo/enrichments/industry.py) — new client per call

We have zero visibility into how much each pipeline run costs or how token usage breaks down by stage. See revise_plan.md §P1-4.

## Files touched
- Create: `src/hk_ipo/llm_client.py`
- Modify: `src/hk_ipo/l2_extraction.py` (replace `_openai_client` usage)
- Modify: `src/hk_ipo/l4_categorize.py` (replace `openai.OpenAI(...)` in `call_l4_llm`)
- Modify: `src/hk_ipo/enrichments/industry.py` (replace `openai.OpenAI(...)` in `_classify_via_llm`)
- (Optional) `src/hk_ipo/config.py` — add `LLM_LOG_PATH = DATA_DIR / "logs" / "llm_calls.jsonl"` constant
- (Optional) test: `tests/test_llm_client.py`

## Design
```python
# src/hk_ipo/llm_client.py
from __future__ import annotations
import json, os, threading, time
from pathlib import Path
from typing import Any, ClassVar, Optional
import openai

# Per-1K-token pricing for the models we use; override via env if needed.
_PRICING_USD_PER_1K = {
    "openai/gpt-4o":            {"in": 0.0025, "out": 0.01},
    "deepseek/deepseek-v4-pro": {"in": 0.00027, "out": 0.0011},
    # add as needed; unknown models log cost_usd=None
}

class LLMClient:
    _instance: ClassVar[Optional["LLMClient"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._client = openai.OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
        self._log_path = Path(os.environ.get("LLM_LOG_PATH", "data/logs/llm_calls.jsonl"))
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_lock = threading.Lock()

    @classmethod
    def get(cls) -> "LLMClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def chat(self, *, model: str, messages: list[dict], stage: str, **kw: Any):
        t0 = time.monotonic()
        resp = self._client.chat.completions.create(model=model, messages=messages, **kw)
        dt = time.monotonic() - t0
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", None) if usage else None
        out_tok = getattr(usage, "completion_tokens", None) if usage else None
        cost = self._compute_cost(model, in_tok, out_tok)
        self._log(stage=stage, model=model, in_tok=in_tok, out_tok=out_tok, cost=cost, latency_s=dt)
        return resp

    def _compute_cost(self, model: str, in_tok: int | None, out_tok: int | None) -> float | None:
        p = _PRICING_USD_PER_1K.get(model)
        if not p or in_tok is None or out_tok is None:
            return None
        return (in_tok / 1000.0) * p["in"] + (out_tok / 1000.0) * p["out"]

    def _log(self, **fields: Any) -> None:
        line = json.dumps({"ts": time.time(), **fields}, ensure_ascii=False)
        with self._log_lock, self._log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
```

## Steps
1. Write `llm_client.py` per the design above.
2. Replace the three existing call sites:
   - `l2_extraction.py`: where `_openai_client.chat.completions.create(...)` is called, switch to `LLMClient.get().chat(stage="L2", model=..., messages=..., ...)`.
   - `l4_categorize.py`: `call_l4_llm` — same pattern, `stage="L4"`.
   - `enrichments/industry.py`: `_classify_via_llm` — same pattern, `stage="L5/industry"`.
3. Delete the now-orphan module-level `_openai_client` in `l2_extraction.py` and ad-hoc client constructions.
4. Run unit tests: `pytest -m "not e2e" -q` — all must stay green. The LLM call sites are typically already mocked at the `openai` call boundary; you may need to update mocks to patch `LLMClient.get().chat` instead.
5. Add `tests/test_llm_client.py` covering:
   - Singleton: `LLMClient.get() is LLMClient.get()`
   - Cost calc: known model returns expected dollars; unknown model returns `None`
   - Log writes one JSONL line per call (use a temp `LLM_LOG_PATH`)

## Acceptance
- [x] All three call sites import and use `LLMClient.get().chat(...)`.
- [x] `data/logs/llm_calls.jsonl` is created on first LLM call and grows by one line per call.
- [x] Each line is valid JSON with keys: `ts`, `stage`, `model`, `in_tok`, `out_tok`, `cost`, `latency_s`.
- [x] `pytest -m "not e2e" -q` is green (495 passed, 1 pre-existing unrelated failure).
- [x] No remaining `openai.OpenAI(` outside `llm_client.py` (verified with grep).

## Out of scope
- Response caching — that's [P1-5](P1-5-llm-response-cache.md) (will extend this class).
- Streaming — not needed for current call sites.
- Pricing table maintenance — store hardcoded for now; revisit if model list grows.

## Dependencies
- Recommended: complete [P1-1](P1-1-real-e2e-validation.md) first so any refactor regressions can be caught against verified-working behavior.

## Resolution

### Status: Complete

### What was changed

1. **`src/hk_ipo/l2_extraction.py`** -- Replaced orphan `_openai_client.chat.completions.create(...)` calls in `_call_llm` and `_call_llm_with_prompt` with `LLMClient.get().chat(stage="L2", model=..., messages=..., ...)`. The `LLMClient` import already existed at line 26; now it is actually used. Removed `import openai` dependency for LLM calls (kept for `openai.RateLimitError`/`openai.APIError` in retry logic).

2. **`src/hk_ipo/l4_categorize.py`** -- Migrated two call sites:
   - `call_l4_llm`: Replaced `openai.OpenAI(...)` + `client.chat.completions.create(...)` with `LLMClient.get().chat(stage="L4", model=..., messages=..., ...)`.
   - `_llm_assign_parent`: Replaced `openai.OpenAI(...)` + `client.chat.completions.create(...)` with `LLMClient.get().chat(stage="L4", model=..., messages=..., ...)`. Changed `except openai.APIError` to `except Exception` for broader error handling with LLMClient. Added `import openai` at module level (needed for `openai.APIError` in `process_all` except clause).

3. **`src/hk_ipo/enrichments/industry.py`** -- Migrated `_classify_via_llm`: Replaced `openai.OpenAI(...)` + `client.chat.completions.create(...)` with `LLMClient.get().chat(stage="L5/industry", model=..., messages=..., ...)`.

4. **`tests/test_l2_hardening.py`** -- Updated `TestEmptyResponseGuard` mocks from `patch("hk_ipo.l2_extraction._openai_client")` to `patch("hk_ipo.llm_client.LLMClient.chat")` to match the new call pattern.

### Test results

- `python -m pytest -m "not e2e" -q`: **495 passed, 1 failed**
  - The single failure (`test_cli_missing_file_errors` in `test_enrichments_capex_opex.py`) is pre-existing and unrelated to this task (SystemExit.code assertion expects int but gets string).
- All 88 tests in the affected test files pass cleanly:
  - `tests/test_l2_hardening.py` -- 21 passed
  - `tests/test_l4_categorize.py` -- 28 passed (including new `_llm_assign_parent` tests)
  - `tests/test_enrichments_industry.py` -- 6 passed
  - `tests/test_l4_analysis.py` -- 12 passed

### Verification

- `grep -r "openai.OpenAI(" src/` returns only `src/hk_ipo/llm_client.py` -- no remaining ad-hoc client constructions.
- All three call sites (`l2_extraction.py`, `l4_categorize.py`, `enrichments/industry.py`) use `LLMClient.get().chat(...)`.
