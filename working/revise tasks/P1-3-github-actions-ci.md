# P1-3 — Add GitHub Actions CI workflow

Status: done
Priority: P1
Effort: S (45 min)

## Goal
Run ruff + Python unit tests + frontend build + vitest on every PR and push to `main`.

## Why
No `.github/workflows/` exists. 472+ Python tests + 181+ vitest tests run only on the developer's box. See revise_plan.md §P1-3.

## Files touched
- Create: `.github/workflows/ci.yml`
- Modify: [README.md](../../README.md) — add CI status badge near the top

## Steps
1. Create the workflow:
   ```yaml
   name: CI
   on:
     pull_request:
     push:
       branches: [main]

   jobs:
     python:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.10'
         - name: Install
           run: pip install -e ".[dev]"
         - name: Lint
           run: ruff check src tests scripts
         - name: Unit tests
           run: pytest -m "not e2e" -q

     frontend:
       runs-on: ubuntu-latest
       defaults:
         run:
           working-directory: frontend
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with:
             node-version: '20'
             cache: 'npm'
             cache-dependency-path: frontend/package-lock.json
         - name: Install
           run: npm ci
         - name: Build
           run: npm run build
         - name: Test
           run: npm test
   ```
2. Push a throwaway branch and PR to verify both jobs pass. If `npm ci` complains about lockfile drift, regenerate `frontend/package-lock.json` locally and commit.
3. Once the workflow passes, copy the badge markdown from the GitHub Actions UI and paste at the top of [README.md](../../README.md) right after the H1:
   ```markdown
   [![CI](https://github.com/<owner>/hk-ipo-research/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/hk-ipo-research/actions/workflows/ci.yml)
   ```
   Replace `<owner>` with the real GitHub org / user.

## Acceptance
- [ ] `.github/workflows/ci.yml` exists and is valid YAML (`yamllint` or just GH parsing).
- [ ] On a sample PR, both `python` and `frontend` jobs go green within ~5 min total.
- [ ] README badge renders green.
- [ ] No new secret required (workflow has no LLM key access — e2e is excluded with `-m "not e2e"`).

## Out of scope
- E2E tests in CI — they require the API key and golden PDFs; track as separate follow-up.
- Caching pip wheels — optimize later.
- Setting up branch protection rules — repo admin task, outside Claude scope.

## Dependencies
- [P1-2](P1-2-frontend-oom-rootfix.md) — without the Node memory cap, frontend build may OOM (GitHub Actions ubuntu-latest has ≥ 7 GB so practically fine, but local CI runners might not).

---
## Resolution
Status: done (file created — not yet pushed; push requires user approval)
Created: .github/workflows/ci.yml
Added CI badge to README.md line 2.
Note: push to GitHub and branch protection setup are manual steps pending user approval.
