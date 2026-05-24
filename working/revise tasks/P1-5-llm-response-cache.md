# P1-5 — Disk cache for LLM responses

Status: done
Priority: P1
Effort: S (45 min)

## Goal
Add a content-addressed disk cache to `LLMClient.chat()` so re-running the pipeline doesn't re-pay for identical prompts.

## Why
Coarse skip (`if out_path.exists(): skip`) prevents any partial reuse when a prompt is tweaked. With caching keyed on `(model, prompt, temperature)`, you can edit downstream code or rerun stages cheaply. See revise_plan.md §P1-5.

## Files touched
- Modify: `src/hk_ipo/llm_client.py` (extend `chat` method)
- (Optional) test: `tests/test_llm_client.py`

## Design
```python
# Inside LLMClient.chat(), before calling self._client.chat.completions.create:
import hashlib, json
from pathlib import Path

def _cache_key(self, model: str, messages: list[dict], **kw: Any) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": kw.get("temperature"),
        "response_format": kw.get("response_format"),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _cache_path(self, key: str) -> Path:
    root = Path(os.environ.get("LLM_CACHE_DIR", "data/llm_cache"))
    return root / key[:2] / f"{key}.json"
```

In `chat()`:
1. Compute `key`, `path`.
2. If `path.exists()` and `os.environ.get("LLM_CACHE_DISABLE") != "1"`:
   - Load cached response, log a `cache_hit=True` line, return reconstructed `ChatCompletion`-like object (or use `openai.types.chat.ChatCompletion.model_validate(...)` if you stored as dict).
3. Else: call API, write `{"_cached_at": time.time(), "response": resp.model_dump()}` to `path`, log `cache_hit=False`.

## Steps
1. Implement helpers + cache lookup in `LLMClient.chat()` (depends on [P1-4](P1-4-llm-client-unification.md) merging first).
2. Make cache reconstruction return the right type — easiest: store and reload with `ChatCompletion.model_validate_json(...)` from the `openai` SDK so callers see no API difference.
3. Add unit tests:
   - First call hits API (mocked); second identical call returns cached value without hitting API.
   - Different `temperature` ⇒ different key.
   - `LLM_CACHE_DISABLE=1` forces a fresh call.
4. Update `.gitignore` to ignore `data/llm_cache/`:
   ```
   data/llm_cache/
   ```
5. Run full unit test suite.

## Resolution

**Status:** done

**What was changed:**
- `src/hk_ipo/llm_client.py`: Added `_cache_key()`, `_cache_path()`, and `_serialize_response_format()` helpers. Extended `chat()` to check disk cache (keyed on model, messages, temperature, response_format via SHA-256) before API call. Cache hits reconstruct via `ChatCompletion.model_validate_json()` so callers see the same type as a fresh response. Cache files are stored at `data/llm_cache/<first-2-hex>/<key>.json` (overridable via `LLM_CACHE_DIR` env var). `LLM_CACHE_DISABLE=1` bypasses cache.
- `.gitignore`: Added `data/llm_cache/` entry.
- `tests/test_llm_client.py`: 8 new tests covering key determinism, cache hit/miss, temperature-based key difference, LLM_CACHE_DISABLE bypass, and cache file format validation.

**Test results:**
- `tests/test_llm_client.py`: 8 passed (new)
- `python -m pytest -m "not e2e" -q`: 503 passed, 1 failed (the single failure is pre-existing in `test_schema_review.py::test_report_includes_recommendation_for_multi_file_cluster`, unrelated to this change).
