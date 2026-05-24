"""Batch pipeline entry script: L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7.

Usage:
    python scripts/run_pipeline.py [--pdf-dir PATH] [--workers N]
        [--skip L1,L2,...] [--only L4,L5.geo]
        [--force] [--limit N] [--dry-run-cost]
        [--db PATH] [--build-frontend]
"""
from __future__ import annotations

import argparse
import importlib
import json
import sqlite3 as _sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hk_ipo import config  # noqa: E402

# ── Price table (USD per 1k tokens, approximate) ──────────────────────────

_PRICE_PER_1K: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4-pro": (0.0002, 0.0004),
    "openai/gpt-4o": (0.0025, 0.01),
    "openai/gpt-4o-mini": (0.00015, 0.0006),
    "anthropic/claude-sonnet-4-20250514": (0.003, 0.015),
    "google/gemini-2.5-flash-preview-05-20": (0.00015, 0.0006),
}


def _estimate_cost(pdf_count: int, n_uses_per_pdf: int = 5) -> dict[str, Any]:
    model = config.L2_TEXT_MODEL
    input_price, output_price = _PRICE_PER_1K.get(model, (0, 0))

    # L2: ~4000 input tokens + ~800 output per use = 4000 + 800*5 = 8000 tokens per pdf
    l2_input = pdf_count * 4000
    l2_output = pdf_count * n_uses_per_pdf * 800

    # L4: ~3000 input + ~300 output per pdf
    l4_input = pdf_count * 3000
    l4_output = pdf_count * 500

    total_input = l2_input + l4_input
    total_output = l2_output + l4_output

    cost_input = total_input / 1000 * input_price
    cost_output = total_output / 1000 * output_price

    return {
        "model": model,
        "pdf_count": pdf_count,
        "estimated_tokens": {"input": total_input, "output": total_output},
        "estimated_cost_usd": round(cost_input + cost_output, 4),
    }


# ── Pipeline_runs SQLite helpers ────────────────────────────────────────────────

def _ensure_pipeline_runs_table(db_path: Path) -> None:
    """Ensure the pipeline_runs table exists (idempotent via IF NOT EXISTS)."""
    from hk_ipo.storage.schema_sql import create_tables
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        create_tables(conn)
        conn.commit()
    finally:
        conn.close()


def _record_stage_run(db_path: Path, run_id: str, stage: str,
                      hk_ticker: str, status: str,
                      error_message: str | None = None,
                      output_path: str | None = None) -> None:
    """Insert a single pipeline_runs row for one ticker+stage."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_runs "
            "(run_id, hk_ticker, stage, status, error_message, output_path, "
            " started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, hk_ticker, stage, status, error_message, output_path,
             now, now),
        )
        conn.commit()
    finally:
        conn.close()


def _tickers_from_dir(d: Path) -> set[str]:
    """Return the set of ticker stems from a directory of <ticker>.json files."""
    if not d.exists():
        return set()
    return {p.stem for p in d.glob("*.json") if not p.name.startswith(".")}


def _record_stage_sweep(db_path: Path, run_id: str, stage: str,
                        attempted: set[str], succeeded: set[str]) -> None:
    """Record pipeline_runs: 'ok' for each succeeded ticker,
    'failed' for each attempted-but-missing ticker."""
    for tk in sorted(attempted):
        if tk in succeeded:
            _record_stage_run(db_path, run_id, stage, tk, "ok")
        else:
            _record_stage_run(db_path, run_id, stage, tk, "failed",
                              error_message=f"{stage}: no output for {tk}")


_LOG_FILE: Path | None = None  # set by main(), written by _log_stage


def _log_stage(stage: str, status: str, tickers: list[str] | None = None,
               error: str | None = None) -> None:
    """Write one JSONL line per ticker per stage to the run log file.

    If tickers is None or empty, writes a single aggregate line with
    hk_ticker = '*'.
    """
    if _LOG_FILE is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    targets = tickers if tickers else ["*"]
    for tk in targets:
        entry = {
            "stage": stage, "hk_ticker": tk, "status": status,
            "logged_at": now,
        }
        if error:
            entry["error"] = error
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _stat_ok(s: dict[str, Any]) -> int:
    """Extract ok/succeeded count from a stage stats dict."""
    return s.get("succeeded", s.get("passed", s.get("loaded", s.get("ok", 0))))


def _stat_fail(s: dict[str, Any]) -> int:
    """Extract failed count from a stage stats dict."""
    return s.get("failed", 0)


def _log_stage_result(stage: str, stats: dict[str, Any]) -> None:
    """Log stage completion based on stats dict from process_all."""
    ok = _stat_ok(stats)
    fail = _stat_fail(stats)
    status = "failed" if fail > 0 and ok == 0 else ("skipped" if ok == 0 else "ok")
    _log_stage(stage, status)
    if fail > 0:
        _log_stage(stage, "failed", error=f"{fail} ticker(s) failed")


def _print_summary(stats: dict[str, Any]) -> None:
    print(f"\n{'='*70}")
    print("  Pipeline summary")
    print(f"{'='*70}")
    for stage, s in stats.items():
        if not isinstance(s, dict):
            continue
        ok = _stat_ok(s)
        fail = _stat_fail(s)
        total = s.get("total", 0)
        print(f"  {stage:<10}  ok={ok}  failed={fail}  total={total}")
    print(f"{'='*70}\n")


def main() -> None:
    global _LOG_FILE

    parser = argparse.ArgumentParser(
        description="Batch pipeline: L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7"
    )
    parser.add_argument("--pdf-dir", default=str(config.RAW_PDFS_DIR))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip", default="",
                       help="Comma-separated stages to skip (e.g. L1,L3,L5.geo)")
    parser.add_argument("--only", default="",
                       help="Comma-separated stages; only these run")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run-cost", action="store_true")
    parser.add_argument("--db", default="data/ipo.db")
    parser.add_argument("--build-frontend", action="store_true")
    parser.add_argument("--json", action="store_true",
                       help="Emit structured run report to stdout")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir).resolve()
    # ── Derive data root from --pdf-dir so every stage writes/reads under
    #    the same data tree (critical for E2E tests that use tmp_path).
    #    PR-013 fix: do NOT hard-code config.SECTIONS_DIR etc. — those
    #    resolve to the project's real data/ and break test isolation.
    data_root = pdf_dir.parent
    sections_dir = data_root / "sections"
    extracted_dir = data_root / "extracted"
    categorized_dir = data_root / "categorized"
    enriched_dir = data_root / "enriched"

    # --db is honoured as-given; default is "data/ipo.db" but when callers
    # pass --pdf-dir <tmp>/data/raw_pdfs they typically also pass --db
    # <tmp>/data/ipo.db. If --db is the default and data_root differs from
    # config.DATA_DIR, redirect --db to data_root/ipo.db for consistency.
    if args.db == "data/ipo.db" and data_root != config.DATA_DIR:
        db_path = data_root / "ipo.db"
    else:
        db_path = Path(args.db).resolve()

    # ── Dry-run cost mode ─────────────────────────────────────────────────
    if args.dry_run_cost:
        pdfs = list(pdf_dir.glob("*.pdf"))
        estimate = _estimate_cost(len(pdfs))
        print(json.dumps(estimate, indent=2))
        sys.exit(0)

    # ── Setup run log ─────────────────────────────────────────────────────
    run_id = str(uuid.uuid4())
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _LOG_FILE = log_dir / f"{run_id}.jsonl"
    print(f"[RUN] Run ID:   {run_id}")
    print(f"[RUN] Data:     {data_root}")
    print(f"[RUN] DB:       {db_path}")
    print(f"[RUN] Log:      {_LOG_FILE}")

    # ── Ensure pipeline_runs table exists ─────────────────────────────────
    _ensure_pipeline_runs_table(db_path)

    # ── Determine which stages to run ─────────────────────────────────────
    all_stages = [
        "L1", "L2", "L3", "L4",
        "L5.geo", "L5.country", "L5.industry", "L5.specificity",
        "L5.timeline", "L5.capex_opex", "L5.esg_tag", "L5.commitment",
        "L6", "L7",
    ]
    skip_set = {s.strip() for s in args.skip.split(",") if s.strip()}
    only_set = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None
    stages_to_run = [s for s in all_stages
                     if (only_set is None or s in only_set)
                     and s not in skip_set]

    stats: dict[str, Any] = {}

    # ── L1 ────────────────────────────────────────────────────────────────
    if "L1" in stages_to_run:
        print(f"\n[L1] Sectioning PDFs in {pdf_dir} ...")
        sections_dir.mkdir(parents=True, exist_ok=True)
        from hk_ipo.l1_sectioning import process_all as l1_process_all
        l1_process_all(pdf_dir, sections_dir,
                       limit=args.limit, force=args.force, all_files=True)
        n_sections = len(list(sections_dir.glob("*.json")))
        l1_attempted = {p.stem for p in pdf_dir.glob("*.pdf")}
        l1_succeeded = _tickers_from_dir(sections_dir)
        l1_failed_count = len(l1_attempted - l1_succeeded)
        stats["L1"] = {"ok": n_sections, "failed": l1_failed_count, "total": n_sections}
        _log_stage_result("L1", stats["L1"])
        _record_stage_sweep(db_path, run_id, "L1", l1_attempted, l1_succeeded)

    # ── L2 ────────────────────────────────────────────────────────────────
    if "L2" in stages_to_run:
        print(f"\n[L2] Extracting with {args.workers} workers ...")
        extracted_dir.mkdir(parents=True, exist_ok=True)
        from hk_ipo.l2_extraction import process_all as l2_process_all
        stats["L2"] = l2_process_all(
            sections_dir, extracted_dir,
            max_workers=args.workers, force=args.force,
        )
        _log_stage_result("L2", stats["L2"])
        l2_attempted = _tickers_from_dir(sections_dir)
        l2_succeeded = _tickers_from_dir(extracted_dir)
        _record_stage_sweep(db_path, run_id, "L2", l2_attempted, l2_succeeded)

    # ── L3 ────────────────────────────────────────────────────────────────
    if "L3" in stages_to_run:
        print("\n[L3] Validating ...")
        from hk_ipo.l3_validation import process_all as l3_process_all
        stats["L3"] = l3_process_all(extracted_dir, extracted_dir)
        _log_stage_result("L3", stats["L3"])
        # PR-018 fix: L3 doesn't fail tickers — it flips needs_human_review.
        # Inspect each validated record and record 'review' when the flag
        # is set, 'ok' otherwise. This matches spec §5 pipeline_runs.status
        # values {'ok','skipped','failed','review'} and lets downstream
        # consumers (dashboard A8.6 "needs review" badge) query
        # pipeline_runs WHERE status = 'review'.
        l3_attempted = _tickers_from_dir(extracted_dir)
        for tk in sorted(l3_attempted):
            extracted_file = extracted_dir / f"{tk}.json"
            try:
                rec = json.loads(extracted_file.read_text(encoding="utf-8"))
            except Exception as exc:
                _record_stage_run(db_path, run_id, "L3", tk, "failed",
                                  error_message=f"L3: cannot read {tk}: {exc}")
                continue
            meta = rec.get("extraction_metadata", {}) or {}
            needs_review = bool(
                rec.get("needs_human_review")
                or meta.get("needs_human_review")
            )
            status = "review" if needs_review else "ok"
            _record_stage_run(db_path, run_id, "L3", tk, status)

    # ── L4 ────────────────────────────────────────────────────────────────
    if "L4" in stages_to_run:
        print("\n[L4] Hierarchical categorisation ...")
        categorized_dir.mkdir(parents=True, exist_ok=True)
        from hk_ipo.l4_categorize import process_all as l4_process_all
        # PR-017 fix: propagate --force to L4 so re-running with --force
        # actually re-categorises tickers (default is False which skips
        # tickers whose output already exists). Also forward the model
        # arg and a per-run proposals_csv path under the run's data_root
        # so taxonomy proposals accumulate per pipeline run, not in the
        # project-fixed location.
        proposals_csv = data_root / "taxonomy_proposals.csv"
        stats["L4"] = l4_process_all(
            extracted_dir, categorized_dir,
            limit=args.limit,
            force=args.force,
            model=getattr(args, "model", None),
            proposals_csv=proposals_csv,
        )
        _log_stage_result("L4", stats["L4"])
        l4_attempted = _tickers_from_dir(extracted_dir)
        l4_succeeded = _tickers_from_dir(categorized_dir)
        _record_stage_sweep(db_path, run_id, "L4", l4_attempted, l4_succeeded)

    # ── L5 enrichments ───────────────────────────────────────────────────
    enriched_dir.mkdir(parents=True, exist_ok=True)

    enrichment_modules = {
        "L5.geo": ("geo", "hk_ipo.enrichments.geo"),
        "L5.country": ("country", "hk_ipo.enrichments.country"),
        "L5.industry": ("industry", "hk_ipo.enrichments.industry"),
        "L5.specificity": ("specificity", "hk_ipo.enrichments.specificity"),
        "L5.timeline": ("timeline", "hk_ipo.enrichments.timeline"),
        "L5.capex_opex": ("capex_opex", "hk_ipo.enrichments.capex_opex"),
        "L5.esg_tag": ("esg_tag", "hk_ipo.enrichments.esg_tag"),
        "L5.commitment": ("commitment", "hk_ipo.enrichments.commitment"),
    }

    for stage_key in stages_to_run:
        if not stage_key.startswith("L5."):
            continue
        dim, module_name = enrichment_modules[stage_key]
        print(f"\n[L5] {dim} enrichment ...")
        try:
            mod = importlib.import_module(module_name)
            results = mod.run(categorized_dir, enriched_dir, all_files=True, force=args.force)
        except Exception as exc:
            print(f"[L5] {dim} enrichment failed: {exc}", file=sys.stderr)
            l5_attempted = _tickers_from_dir(categorized_dir)
            stats[stage_key] = {"ok": 0, "failed": len(l5_attempted), "total": len(l5_attempted)}
            _log_stage_result(stage_key, stats[stage_key])
            _log_stage(stage_key, "failed", error=str(exc))
            _record_stage_sweep(db_path, run_id, stage_key, l5_attempted, set())
            continue
        l5_attempted = _tickers_from_dir(categorized_dir)
        # PR-019 fix: capture run() return value (dict keyed by ticker) to
        # derive accurate ok/failed counts instead of hardcoding failed=0.
        # CR-012 fix: use results keys as the succeeded set instead of
        # _tickers_from_dir(enriched_dir), which conflates output from all
        # enrichment sub-stages sharing the same enriched_dir.
        if results and isinstance(results, dict):
            n_ok = len(results)
            n_failed = len(l5_attempted - set(results.keys()))
            l5_succeeded = set(results.keys())
        else:
            n_ok = len(list(enriched_dir.glob("*.json")))
            n_failed = 0
            l5_succeeded = _tickers_from_dir(enriched_dir)
        stats[stage_key] = {"ok": n_ok, "failed": n_failed, "total": n_ok + n_failed}
        _log_stage_result(stage_key, stats[stage_key])
        _record_stage_sweep(db_path, run_id, stage_key, l5_attempted, l5_succeeded)

    # ── L6 ────────────────────────────────────────────────────────────────
    if "L6" in stages_to_run:
        print("\n[L6] Loading to SQLite ...")
        from hk_ipo.storage.loader import process_all as l6_process_all
        results = l6_process_all(enriched_dir, db_path)
        loaded = results.get("loaded", results.get("ok", results.get("succeeded", 0)))
        total = results.get("total", 0)
        l6_attempted = _tickers_from_dir(enriched_dir)
        # CR-010 fix: query the DB for actually-loaded tickers instead of
        # passing the same set for both attempted and succeeded.
        if loaded >= total:
            l6_succeeded = l6_attempted
        else:
            conn_chk = _sqlite3.connect(str(db_path))
            try:
                rows = conn_chk.execute(
                    "SELECT hk_ticker FROM companies WHERE hk_ticker IN "
                    f"({','.join('?' * len(l6_attempted))})",
                    tuple(l6_attempted),
                ).fetchall()
                l6_succeeded = {r[0] for r in rows}
            except Exception:
                l6_succeeded = l6_attempted  # fallback: assume all loaded
            finally:
                conn_chk.close()
        # CR-013 fix: derive actual failed from per-ticker DB success,
        # not from l6_process_all which never returns a "failed" key.
        failed = len(l6_attempted - l6_succeeded)
        stats["L6"] = {"ok": loaded, "failed": failed, "total": total}
        _log_stage_result("L6", stats["L6"])
        _record_stage_sweep(db_path, run_id, "L6", l6_attempted, l6_succeeded)

    # ── L7 ────────────────────────────────────────────────────────────────
    if "L7" in stages_to_run:
        print("\n[L7] Exporting dashboard JSON ...")
        from hk_ipo.analysis.export import export_all as l7_export
        # L7 intentionally uses PROJECT_ROOT rather than data_root because
        # the frontend dev server (npm run dev) serves from this static path
        # and hot-reloads when new JSON appears. All other stages (L1-L6)
        # derive their paths from data_root for test isolation.
        OUT_DIR = config.PROJECT_ROOT / "frontend" / "public" / "data"
        conn = _sqlite3.connect(str(db_path))
        try:
            l7_export(conn, OUT_DIR)
            stats["L7"] = {"ok": 1, "failed": 0, "total": 1}
        finally:
            conn.close()
        _log_stage("L7", "ok")
        _record_stage_run(db_path, run_id, "L7", "*", "ok")

    # ── Build frontend ───────────────────────────────────────────────────
    if args.build_frontend:
        print("\n[BUILD] Building frontend (npm install && npm run build) ...")
        frontend = config.PROJECT_ROOT / "frontend"
        install_ok = True
        build_ok = True
        for cmd in (["npm", "install"], ["npm", "run", "build"]):
            result = subprocess.run(cmd, cwd=frontend, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[ERROR] {cmd}: {result.stderr}", file=sys.stderr)
                if cmd == ["npm", "install"]:
                    install_ok = False
                    break
                else:
                    build_ok = False
            else:
                print(f"  OK: {' '.join(cmd)}")
        all_ok = install_ok and build_ok
        stats["frontend"] = {"ok": 1 if all_ok else 0, "failed": 0 if all_ok else 1}
        _log_stage("frontend", "ok" if all_ok else "failed")

    _print_summary(stats)

    if args.json:
        report = {
            "run_id": run_id,
            "log_file": str(_LOG_FILE),
            "stages": stats,
        }
        print(json.dumps(report, indent=2))

    # ── PR-012 fix: A9.2 requires non-zero exit when any stage had failures.
    # Per-ticker failures are non-blocking (other tickers continue), but the
    # process must report failure via exit code so callers (E2E tests, CI)
    # detect partial failure.
    any_failed = any(
        isinstance(s, dict) and s.get("failed", 0) > 0
        for s in stats.values()
    )
    if any_failed:
        print("[RUN] At least one ticker failed — exiting 1", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
