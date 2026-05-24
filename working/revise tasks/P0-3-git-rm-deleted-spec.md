# P0-3 — Finalize deletion of docs/superpowers/specs/ copy in git

Status: done
Priority: P0
Effort: XS (5 min)

## Goal
Clean up the dangling `D` (deleted-unstaged) status on the obsolete spec copy so `git status` is tidy.

## Why
`docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md` was added in commit `1133437` then deleted from the working tree. The deletion isn't staged yet. The canonical spec lives in [working/spec.md](../spec.md) (671 lines) — confirmed by user. See revise_plan.md §P0-3.

## Files touched
- Stage deletion: `docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md`
- The empty `docs/superpowers/specs/` and `docs/superpowers/` directories vanish automatically once the file is removed.

## Steps
1. Confirm the file is the only thing under `docs/superpowers/specs/`:
   ```powershell
   Get-ChildItem -Recurse docs/superpowers/specs/
   ```
   (If empty / not-found, that is fine — the working tree already lacks the file.)
2. Stage the deletion:
   ```powershell
   git rm docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md
   ```
3. Verify `git status` no longer shows the `D` line for that path:
   ```powershell
   git status
   ```
4. **Do not commit standalone.** Bundle this stage into the same commit as [P0-4](P0-4-delete-tatus-file.md) and any other P0 cleanup work, with a message like `chore: remove stale spec copy and stray status dump (canonical spec lives in working/spec.md)`. Commit only when the user explicitly says to.

## Acceptance
- [ ] `git status` shows no `D` or `??` entry for `docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md`.
- [ ] `git diff --cached` shows the file deletion staged.
- [ ] No new files created elsewhere.

## Out of scope
- Do NOT commit autonomously. Wait for user instruction (project policy: only commit when explicitly asked).
- Do NOT recreate the spec under `docs/` — `working/spec.md` is canonical.
- Do NOT touch `working/spec.md`.

## Dependencies
None. The README cross-link to `working/spec.md` is handled in [P0-1a](P0-1a-readme-rewrite.md).

---
## Resolution
Status: done
Ran: git rm docs/superpowers/specs/2026-05-19-hkex-uop-platform-design.md
File deletion staged (not committed — awaiting bundled chore commit with P0-4).
