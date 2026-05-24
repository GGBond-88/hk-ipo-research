# Changes: Task-004

## Files
- [mod] src/hk_ipo/l1_sectioning.py
- [mod] tests/test_l1_sectioning.py

## Summary
Extended `l1_sectioning.py` with: (a) `ticker_from_filename` deriving zero-padded 5-digit HK ticker from filename; (b) `detect_language` using langdetect with 80%/20% thresholds; (c) Chinese-language PDF detection producing `skipped=true` stub records without text/table extraction; (d) `process_all` now accepts `limit`, `force`, and `all_files` parameters; (e) argparse-based CLI with `--all`, `--limit`, `--force` flags.

Second pass (review fixes): Removed `_cjk_ratio`/`_hangul_ratio` helper functions and CJK/Hangul heuristic block from `detect_language` (feature creep per SR-001). Updated Chinese test text from Traditional to Simplified Chinese (SR-002, TI-001). Added `language` and `skipped` to `_REQUIRED_FIELDS` (CR-001).

Third pass (review fixes): (CR-004) Reused `head_md` for ticker/date extraction via `_ticker_from_markdown`/`_date_from_markdown`, eliminating 2 redundant pymupdf4llm calls. (CR-005) Added `--force` check to single-file CLI path for consistency with batch mode. (CR-006) Added stem fallback in `process_all` when `ticker_from_filename` returns None, preventing `None.json` output collision. Added 4 new tests: `test_cover_metadata_uses_head_md_not_separate_reads`, `test_force_false_skips_existing_output`, `test_force_true_overwrites_existing_output`, `test_all_files_false_uses_stem_fallback_not_none_json`.

Fourth pass (review fix): (CR-007) Removed dead code `_extract_ticker` and `_extract_document_date` from `l1_sectioning.py`. Both had been replaced by direct `_ticker_from_markdown(head_md)` and `_date_from_markdown(head_md, ...)` calls in `extract_use_of_proceeds` per CR-004 consolidation. Verified via grep that no code in src/ or tests/ imports or calls either function. All 166 tests pass.

Fifth pass (review fix): (CR-008) Added `test_langdetect_exception_returns_unknown` to `TestDetectLanguage` class. The test patches `hk_ipo.l1_sectioning.detect_langs` with `side_effect=LangDetectException(999, "test error")` and asserts `detect_language(...)` returns `"unknown"`, covering the previously untested error-recovery path. All 167 tests pass.

Sixth pass (review fix): (CR-009) Fixed inconsistent output streams in `process_all` — the `[WARN] No PDF files to process` and `[SKIP] ... exists` messages were going to stdout via bare `print()` instead of stderr. Changed both to `print(..., file=sys.stderr)`. Added two tests (`test_diagnostic_messages_go_to_stderr_not_stdout`, `test_warn_no_pdfs_goes_to_stderr_not_stdout`) that capture stdout/stderr separately via StringIO monkeypatching and assert diagnostics land on stderr only. All 169 tests pass.

Seventh pass (review fix): (CR-010) Added `test_extract_exception_continues_to_next_pdf` to `TestProcessAllLimit` class. The test creates 3 fake PDFs, monkeypatches `extract_use_of_proceeds` to raise `RuntimeError` for the middle PDF, and verifies that: (a) all 3 PDFs are attempted despite the error, (b) `[ERROR]` diagnostic appears on stderr with the failing filename, (c) successful PDFs still produce output files, and (d) the failing PDF produces no output file. Covers the previously untested batch error-recovery path in `process_all`. All 170 tests pass.

Eighth pass (review fix): (CR-011) Removed dead mock patches for `_extract_text` and `_extract_tables` from `TestExtractZhStub.test_chinese_pdf_emits_stub_record`. These functions are never called during the zh-language stub path due to the early return, so their patches were dead code that could silently mask regressions if the code structure changed. All 170 tests pass.
