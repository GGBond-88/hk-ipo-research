# P0-1a — Rewrite README.md to v2.0

Status: done
Priority: P0
Effort: S (30–60 min)

## Goal
Replace the v1 four-layer README with the v2.0 eight-stage README that matches the actual codebase.

## Why
[README.md](../../README.md) currently describes a four-layer L1–L4 pipeline, claims "130 unit tests", and lists `schema_version 1.0`. The real codebase has L1→L7 + frontend, 472+ unit tests, schema 2.0. This is the single most user-visible documentation drift in the repo. See revise_plan.md §P0-1.

## Files touched
- Modify: [README.md](../../README.md) — full replacement

## Steps
1. Open [working/plan/task-027/task.md](../plan/task-027/task.md), find **Step 3** which contains the complete v2.0 README markdown (starts with `# HK IPO Use-of-Proceeds Research`).
2. Copy that markdown block verbatim into `README.md`, replacing the entire current content.
3. In the **Spec** area (or add a new short section after **Architecture**), add a one-line reference: `> Canonical spec: [working/spec.md](working/spec.md) (671 lines).`
4. Skim the rendered file in your editor — confirm no stray backticks, no broken markdown code fences.

## Acceptance
- [ ] `README.md` opens with `# HK IPO Use-of-Proceeds Research` and contains the L1→L7 ASCII architecture diagram from task-027 Step 3.
- [ ] No occurrence of `"四层架构"`, `"130 个单元测试"`, or `"schema_version 1.0"` anywhere in README.md.
- [ ] README.md contains the section headings: `Architecture (v2.0)`, `Quickstart`, `Per-Stage CLI`, `Taxonomy`, `Enrichment Dimensions`, `Dashboard Views`, `Testing`, `Environment`, `Data Layout`.
- [ ] One line in README references `working/spec.md` as the canonical spec.
- [ ] `python -c "open('README.md').read()"` exits 0 (no encoding errors).

## Out of scope
- Do NOT run ruff/pytest here — that is [P0-1b](P0-1b-ruff-and-pytest.md).
- Do NOT create task-027 meta files here — that is [P0-1c](P0-1c-task027-meta-files.md).
- Do NOT add a CI badge — depends on P1-3.

## Dependencies
None.

---
## Resolution
Status: done
README.md rewritten. Old v1 content replaced with v2.0 (8-stage architecture). Spec reference added.
