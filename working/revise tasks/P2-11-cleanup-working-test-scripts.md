# P2-11 — Consolidate `working/_test_cn*.py` + relocate dev scripts

Status: complete
Priority: P2
Effort: XS (15 min)

## Goal
Reduce clutter in `working/`. Three near-identical `_test_cn*.py` scripts + `_verify_gaps.py` should be consolidated or moved to `scripts/dev/`.

## Why
`working/` is supposed to be planning/spec material. Throwaway debugging scripts mixed in obscure the signal. See revise_plan.md §P2-11.

## Files touched
- Inspect: `working/_test_cn.py`, `working/_test_cn2.py`, `working/_test_cn3.py`, `working/_verify_gaps.py`
- Likely create: `scripts/dev/` directory with consolidated counterpart(s)
- Delete originals when superseded

## Steps
1. Read all three `_test_cn*.py` — figure out the diff.
2. If they target the same flow with minor variations, merge into one `scripts/dev/verify_chinese_handling.py` with CLI flags for the variants.
3. Move `_verify_gaps.py` to `scripts/dev/verify_gaps.py`.
4. Delete the originals from `working/`.
5. Update any documentation that referenced them (likely none).

## Acceptance
- [ ] `working/` no longer contains `_test_cn*.py` or `_verify_gaps.py`.
- [ ] `scripts/dev/` contains the consolidated equivalents.
- [ ] Running each new script with `--help` prints usage cleanly.

## Out of scope
- Adding these to the test suite (they're ad-hoc, not regression tests).

## Dependencies
None.

## Resolution

**Date:** 2026-05-21

**What changed:**

- Merged `working/_test_cn.py`, `_test_cn2.py`, `_test_cn3.py` into `scripts/dev/verify_chinese_handling.py`. The three originals differed only in what Chinese text sample they tested:
  - `_test_cn.py` -- Simplified Chinese with variable repetition counts (n=20/50/100/200) to check length sensitivity.
  - `_test_cn2.py` -- Traditional Chinese HK prospectus-style block (single sample).
  - `_test_cn3.py` -- Simplified vs Traditional side-by-side comparison.
  - The consolidated script exposes each variant via `--variant {1,2,3}`; omitting the flag runs all three.

- Moved `working/_verify_gaps.py` to `scripts/dev/verify_gaps.py`. The only required change was adjusting `PROJECT_ROOT` from `parents[1]` to `parents[2]` since the script is now two levels deep instead of one. The script exercises 15 edge cases against the timeline enrichment module.

- Created `scripts/dev/__init__.py`.

- Deleted all four originals from `working/`.

- Both scripts produce clean `--help` output via argparse.

**Acceptance checklist:**
- [x] `working/` no longer contains `_test_cn*.py` or `_verify_gaps.py`.
- [x] `scripts/dev/` contains the consolidated equivalents.
- [x] Running each new script with `--help` prints usage cleanly.
