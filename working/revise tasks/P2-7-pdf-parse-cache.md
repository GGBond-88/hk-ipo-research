# P2-7 — Cache PDF parse output in L1

Status: done
Priority: P2
Effort: S (30 min)

## Resolution

The content-hash cache was already fully implemented in `src/hk_ipo/l1_sectioning.py`:

- `_pdf_content_hash()` (line 315-318): computes `sha256(pdf_bytes)[:16]` (first 16 hex chars)
- `_load_from_cache()` (line 325-333): checks `data/l1_cache/<hash>.json`, returns cached result on hit, returns None on miss or corrupt file
- `_save_to_cache()` (line 336-342): writes result to cache file
- `extract_use_of_proceeds()` (lines 368-373): checks cache at function entry, reads cached result if available
- Cache is saved for both Chinese-stub results (line 402) and normal parsed results (line 437)
- `force=True` bypasses the cache entirely

`.gitignore` already lists `data/l1_cache/` (line 8).

`L1_CACHE_DIR` is defined in `src/hk_ipo/config.py` (line 19) as `DATA_DIR / "l1_cache"`.

### What was changed

**Test fixes only** -- the production code needed no changes. The cache implementation introduced a file-read at the top of `extract_use_of_proceeds` (to compute the content hash), and `process_all` was updated to use `logging` instead of `print(..., file=sys.stderr)`. This broke 11 pre-existing tests. Fixed:

1. `TestExtractUsOfProceedsSchema` (8 tests) -- all `"fake.pdf"` paths replaced with real temp files via `tmp_path` fixture
2. `TestExtractZhStub` (1 test) -- `/tmp/03690.pdf` replaced with temp file
3. `TestProcessAllLimit` fake functions (5 tests) -- added `**kwargs` to accept `force` kwarg
4. 3 stderr-capture tests -- rewritten to use `caplog` fixture since messages now go through `logging` framework

### Test results

All 65 tests pass in 6.86s:
```
tests/test_l1_sectioning.py::TestContentHashCache::test_second_call_skips_pdf_library PASSED
tests/test_l1_sectioning.py::TestContentHashCache::test_force_true_bypasses_cache PASSED
tests/test_l1_sectioning.py::TestContentHashCache::test_cache_file_written_after_parse PASSED
tests/test_l1_sectioning.py::TestContentHashCache::test_corrupt_cache_file_falls_through_to_parse PASSED
============================= 65 passed in 6.86s ==============================
```

The key cache test (`test_second_call_skips_pdf_library`) verifies: same PDF bytes run twice => `pymupdf.open` call count is exactly 1 (second call returns cached result).

## Acceptance
- [x] Cache skips parser on hash hit (verified by `test_second_call_skips_pdf_library`)
- [x] Test demonstrates cache-hit path skips parser (mock + assert call count == 1)
