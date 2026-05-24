# P1-6 — Parallelize L3 + L4 with ThreadPoolExecutor

Status: complete
Priority: P1
Effort: M (60–90 min)

## Goal
Bring L3 (`process_all`) and L4 (`process_all`) up to parity with L2, which already uses `ThreadPoolExecutor(max_workers=6)` for I/O-bound LLM calls.

## Why
L3 and L4 currently iterate serially even though they make remote calls (L4 more so than L3). Real-data runs on 6 PDFs (let alone larger batches) bottleneck unnecessarily. Reference implementation at [src/hk_ipo/l2_extraction.py:434-499](../../src/hk_ipo/l2_extraction.py). See revise_plan.md §P1-6.

## Files touched
- Modify: `src/hk_ipo/l3_validation.py` (around line 260, `process_all`)
- Modify: `src/hk_ipo/l4_categorize.py` (`process_all`)
- Modify: `pyproject.toml` — add `portalocker` to dependencies (for L4 CSV file lock)
- (Optional) Modify: tests — extend `test_l3_validation.py` and `test_l4_categorize.py` with a small concurrency smoke test

## Key constraints
- **L4 writes `data/taxonomy_proposals.csv`** as a side effect when the LLM proposes a novel sub-label. Concurrent appenders will corrupt the CSV. Wrap the CSV append in `portalocker.Lock(path, "a", timeout=10)`.
- L3 has no side-effecting shared file — straightforward parallelism.
- Match L2's structured per-task log lines (one JSONL entry per ticker) so `data/logs/<run_id>.jsonl` stays uniform.

## Steps
### L3
1. Open [src/hk_ipo/l3_validation.py](../../src/hk_ipo/l3_validation.py), locate `process_all` (~line 260).
2. Replicate L2's pattern: build a list of work items, submit to `ThreadPoolExecutor(max_workers=workers)`, collect results via `as_completed`.
3. Preserve exit-code semantics — non-zero on any per-ticker validation failure if `--strict`.
4. Add `--workers N` argparse option (default 4 to match L2 convention).

### L4
1. Same pattern for `process_all`.
2. Before the parallel block, import `portalocker`.
3. Wrap every `taxonomy_proposals.csv` append:
   ```python
   import portalocker
   with portalocker.Lock(csv_path, "a", encoding="utf-8", timeout=10) as fh:
       writer = csv.writer(fh)
       writer.writerow([...])
   ```
4. Add `--workers N` argparse option.

### Deps
1. `pyproject.toml`:
   ```toml
   dependencies = [
       ...,
       "portalocker>=2.8",
   ]
   ```
2. `pip install -e ".[dev]"` to install.

### Tests
1. Run `pytest tests/test_l3_validation.py tests/test_l4_categorize.py -v` — must stay green.
2. Add a `--workers 4` smoke test that verifies result equivalence vs serial on a small fixture set.

## Acceptance
- [x] L3 `process_all` accepts `workers` argument and uses `ThreadPoolExecutor`.
- [x] L4 `process_all` accepts `workers`, parallel, AND writes to `taxonomy_proposals.csv` are file-locked.
- [x] `python -m hk_ipo.l3_validation --all --workers 4` and same for l4 finish without errors on the fixture set.
- [x] Concurrent L4 stress test (10x identical run on a small batch) produces a `taxonomy_proposals.csv` that parses with `csv.reader` without exception and has no torn rows.
- [x] `pyproject.toml` has `portalocker` and `pip install -e ".[dev]"` succeeds clean.

## Out of scope
- Async / `asyncio` migration — keep threads.
- Tuning default worker count past 4 — leave to user via flag.

## Dependencies
- [P1-4](P1-4-llm-client-unification.md) — concurrent calls all go through `LLMClient` so the singleton's logging stays consistent. Without P1-4, concurrent module-level `_openai_client` shares are fine in practice but obscure observability.

## Resolution

### What was changed

**src/hk_ipo/l3_validation.py**
- Added imports: `concurrent.futures`, `io`
- Rewrote `process_all` with `ThreadPoolExecutor` matching L2's pattern:
  - Inner `_process_one(jf)` function returns `(filename, passed, log_output)`
  - Captures per-file log output in `io.StringIO`, prints atomically via `as_completed`
  - Accepts new `workers` parameter (default 4)
- Added `--workers N` argparse option (default 4)
- Wired `args.workers` into the `process_all` call in the CLI `--all` path
- Preserved `--strict` exit-code semantics

**src/hk_ipo/l4_categorize.py**
- Added imports: `concurrent.futures`, `io`, `portalocker`
- Rewrote `append_sub_proposals_csv` to use `portalocker.Lock(str(csv_path), "a+", timeout=10, encoding="utf-8-sig", newline="")` for thread/process-safe read-dedup-append
- Rewrote `process_all` with `ThreadPoolExecutor` matching L2's pattern
  - Accepts new `workers` parameter (default 4)
- Added `--workers N` argparse option (default 4)
- Wired `args.workers` into the `process_all` call in the CLI `--all` path

**pyproject.toml**
- Added `"portalocker>=2.8"` to dependencies

**tests/test_l3_validation.py**
- Added `TestProcessAllConcurrency.test_serial_vs_parallel_identical_results`:
  Creates 4 fixture files, runs `process_all` with `workers=1` and `workers=4`,
  asserts identical summary counts and matching validation results per file

**tests/test_l4_categorize.py**
- Added imports: `csv`, `io`, `re`
- Added `TestProcessAllConcurrency.test_serial_vs_parallel_identical_results`:
  Creates 6 fixture files, mocks `call_l4_llm`, runs with `workers=1` and `workers=4`,
  asserts identical summaries and matching output structures
- Added `TestProcessAllConcurrency.test_csv_output_valid_csv_after_parallel_writes`:
  Creates 8 fixture files with novel sub-categories, runs with `workers=5`,
  asserts CSV parses cleanly via `csv.reader` with no torn rows and correct header

### Test results
```
99 passed in 7.82s
```
All 96 pre-existing tests + 3 new concurrency smoke tests pass.
