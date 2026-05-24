# Revise Tasks — Index

Bite-size, handoff-ready task files derived from [working/revise_plan.md](../revise_plan.md).
Each file is **self-contained**: paths, commands, acceptance criteria, dependencies.
A fresh agent should be able to pick up any task by reading only that file + the cited code.

**Reading order convention**: P0 first (parallel-safe within P0), then P1 (some intra-P1 deps), then P2.
**Repo root** in every task = `C:\Users\Administrator\Documents\github\hk-ipo-research`.

---

## P0 — Urgent (1–2 days)

| # | File | Title | Depends on |
|---|------|-------|------------|
| P0-1a | [P0-1a-readme-rewrite.md](P0-1a-readme-rewrite.md) | Rewrite README.md to v2.0 | — |
| P0-1b | [P0-1b-ruff-and-pytest.md](P0-1b-ruff-and-pytest.md) | Run ruff + pytest, capture counts | — |
| P0-1c | [P0-1c-task027-meta-files.md](P0-1c-task027-meta-files.md) | Write task-027 changes/test-results/review meta files | P0-1a, P0-1b |
| P0-2a | [P0-2a-task026-doc-alignment.md](P0-2a-task026-doc-alignment.md) | Mark CR-001/002/003 Resolved + decide SR-001 | — |
| P0-2b | [P0-2b-prior-enrichment-regression-tests.md](P0-2b-prior-enrichment-regression-tests.md) | Add 4 prior-enrichment regression tests | — |
| P0-3 | [P0-3-git-rm-deleted-spec.md](P0-3-git-rm-deleted-spec.md) | Finalize spec copy deletion in git | — |
| P0-4 | [P0-4-delete-tatus-file.md](P0-4-delete-tatus-file.md) | Delete stray `tatus` file at repo root | — |

## P1 — Important (1–2 weeks)

| # | File | Title | Depends on |
|---|------|-------|------------|
| P1-1 | [P1-1-real-e2e-validation.md](P1-1-real-e2e-validation.md) | Real end-to-end run on 6 PDFs + A-checks | P0 all (recommended); `.env` API key |
| P1-2 | [P1-2-frontend-oom-rootfix.md](P1-2-frontend-oom-rootfix.md) | Root-fix EI-001 OOM (Node mem + LRU + GC) | — |
| P1-3 | [P1-3-github-actions-ci.md](P1-3-github-actions-ci.md) | Add GitHub Actions CI workflow | P1-2 |
| P1-4 | [P1-4-llm-client-unification.md](P1-4-llm-client-unification.md) | Unified `LLMClient` with token/cost logging | (recommend P1-1 first) |
| P1-5 | [P1-5-llm-response-cache.md](P1-5-llm-response-cache.md) | Disk cache for LLM responses | P1-4 |
| P1-6 | [P1-6-l3-l4-concurrency.md](P1-6-l3-l4-concurrency.md) | Add ThreadPoolExecutor to L3 + L4 | P1-4 |

## P2 — Optimization (later)

| # | File | Title |
|---|------|-------|
| P2-1 | [P2-1-narrow-except-exception.md](P2-1-narrow-except-exception.md) | Narrow `except Exception:` to specific types |
| P2-2 | [P2-2-print-to-logger.md](P2-2-print-to-logger.md) | Replace `print()` with logger |
| P2-3 | [P2-3-centralize-sql-queries.md](P2-3-centralize-sql-queries.md) | Move raw SQL from export.py to storage/queries.py |
| P2-4 | [P2-4-l4-keyword-branch-refactor.md](P2-4-l4-keyword-branch-refactor.md) | Refactor `assign_parent()` keyword branches |
| P2-5 | [P2-5-l4-schema-version-import.md](P2-5-l4-schema-version-import.md) | Replace `"2.0"` literal with `SCHEMA_VERSION` import |
| P2-6 | [P2-6-enrichment-base-template.md](P2-6-enrichment-base-template.md) | Extract shared `_enrich_template` CLI scaffold (also covers P2-12) |
| P2-7 | [P2-7-pdf-parse-cache.md](P2-7-pdf-parse-cache.md) | Cache PDF parse output in L1 |
| P2-8 | [P2-8-enrichment-version-validation.md](P2-8-enrichment-version-validation.md) | Auto-validate enrichment `version` bumps on schema change |
| P2-9 | [P2-9-golden-pdfs-fixture-scope.md](P2-9-golden-pdfs-fixture-scope.md) | Tighten `golden_pdfs` fixture scope |
| P2-10 | [P2-10-frontend-error-boundary-skeleton.md](P2-10-frontend-error-boundary-skeleton.md) | Add ErrorBoundary + skeleton loading |
| P2-11 | [P2-11-cleanup-working-test-scripts.md](P2-11-cleanup-working-test-scripts.md) | Consolidate `working/_test_cn*.py` + relocate dev scripts |

---

## Task file template

Every task file follows this layout:
1. **Goal** — one sentence outcome
2. **Why** — context / link to revise_plan section
3. **Files touched** — explicit paths
4. **Steps** — numbered, with exact commands
5. **Acceptance** — concrete pass criteria
6. **Out of scope** — what NOT to do
7. **Dependencies** — task IDs that must finish first
8. **Estimated effort** — XS/S/M/L

---

## Status convention

Each task file starts with `Status: pending | in-progress | done`. Update inline as work progresses, or
append `done.md` next to the task file with a short outcome note (commit SHA, test counts, links).
