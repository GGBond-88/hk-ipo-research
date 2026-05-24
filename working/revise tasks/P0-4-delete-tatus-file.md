# P0-4 — Delete stray `tatus` file at repo root

Status: done
Priority: P0
Effort: XS (2 min)

## Goal
Remove the accidental `tatus` file (a `git status` typo'd into `git log > tatus` redirect dump).

## Why
Untracked clutter at repo root. File contains git log text from a 2026-05-17 commit. See revise_plan.md §P0-4.

## Files touched
- Delete: `tatus` (repo root, untracked)

## Steps
1. Confirm it's untracked and not something else important:
   ```powershell
   git status -- tatus
   Get-Content tatus -TotalCount 3
   ```
2. Delete:
   ```powershell
   Remove-Item tatus
   ```
3. Verify gone:
   ```powershell
   Test-Path tatus
   ```
   Should return `False`.

## Acceptance
- [ ] `tatus` no longer exists at repo root.
- [ ] `git status` no longer lists it under untracked files.
- [ ] No `.gitignore` change (file is untracked, deletion suffices).

## Out of scope
- Adding `tatus` to `.gitignore` is unnecessary; the right fix is to not run `git status > tatus` again.
- Do not commit standalone — bundle into the same chore commit as [P0-3](P0-3-git-rm-deleted-spec.md) when user approves.

## Dependencies
None.

---
## Resolution
Status: done
Deleted untracked file `tatus` from repo root. File contained git log output from 2026-05-17.
