"""L3 验证层：对 L2 提取结果做数值校验和格式规范化。

11 项检查（按 check_id 标识）：

  [required_fields]       必须字段存在且非 null                → ERROR
  [ticker_format]         hk_ticker 为 4-5 位纯数字           → ERROR
  [percentage_sum]        顶层用途百分比之和≈100%             → ERROR
                            （任一百分比为 null 时降级为 WARNING）
  [amount_sum]            顶层金额之和≈总募资额（±1%）        → ERROR
                            （任一金额或总额为 null 时降级为 WARNING）
  [item_consistency]      单项 amount ≈ total×pct/100（±2%）  → ERROR
  [no_duplicate_use_id]   use_id 唯一性                        → ERROR
  [category_vocab]        category 在预定义词表中              → WARNING（不影响 passed）
  [category_l1]           category 可映射到 L1 类别             → ERROR
  [category_raw_present]  every use must have non-empty category_raw → ERROR
  [total_proceeds_present] total_net_proceeds must be non-null  → ERROR
  [schema_version]        schema_version presence/mismatch     → WARNING（不影响 passed）

输入：data/extracted/<stem>.json
输出：data/extracted/<stem>.validated.json  （带 "validation" 块）
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hk_ipo.logging_setup import get_logger
from hk_ipo.schema import CATEGORY_L1_MAP, CATEGORY_L2, SCHEMA_VERSION

logger = get_logger(__name__)

# ── Allowed category vocabulary (imported from schema — single source of truth)

_CATEGORY_VOCAB: frozenset[str] = frozenset(CATEGORY_L2)

# ── Required top-level fields ─────────────────────────────────────────────────

_REQUIRED_TOP_FIELDS = [
    "company_file",
    "hk_ticker",
    "document_date",
    "total_net_proceeds_hkd_million",
    "uses",
]

_TICKER_RE = re.compile(r"^\d{4,5}$")


# ── Core validation logic ─────────────────────────────────────────────────────


def validate_record(
    extracted: dict[str, Any],
    tolerance_pct: float = 1.0,
) -> tuple[bool, list[str], list[str]]:
    """Validate a single L2 extraction dict.

    Parameters
    ----------
    extracted:      The dict loaded from a <stem>.json file.
    tolerance_pct:  Maximum allowed absolute deviation of the percentage sum
                    from 100.0 before it is flagged as an ERROR (default 1.0).

    Returns
    -------
    (passed, errors, warnings)
        ``passed`` is True when ``errors`` is empty.
        ``warnings`` are informational and never affect ``passed``.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── [required_fields] ────────────────────────────────────────────────────
    missing = [f for f in _REQUIRED_TOP_FIELDS if f not in extracted or extracted[f] is None]
    if missing:
        errors.append(f"[required_fields] Missing or null fields: {', '.join(missing)}")

    # ── [ticker_format] ──────────────────────────────────────────────────────
    ticker = extracted.get("hk_ticker")
    if ticker is not None:
        if not _TICKER_RE.match(str(ticker)):
            errors.append(f"[ticker_format] hk_ticker {ticker!r} is not a 4-5 digit code")
    # If ticker is None it was already flagged by [required_fields].

    # ── Collect uses for subsequent checks ───────────────────────────────────
    uses = extracted.get("uses", [])
    if not isinstance(uses, list):
        errors.append("[required_fields] 'uses' must be a list")
        return False, errors, warnings

    top_uses = [u for u in uses if u.get("parent_id") is None]

    # ── [no_duplicate_use_id] ────────────────────────────────────────────────
    seen_ids: set[str] = set()
    dupes: list[str] = []
    for u in uses:
        uid = str(u.get("use_id", ""))
        if uid in seen_ids:
            dupes.append(uid)
        else:
            seen_ids.add(uid)
    if dupes:
        errors.append(f"[no_duplicate_use_id] Duplicate use_id(s): {', '.join(dupes)}")

    # ── [percentage_sum] ─────────────────────────────────────────────────────
    pcts = [u.get("percentage") for u in top_uses]
    if any(p is None for p in pcts):
        warnings.append(
            "[percentage_sum] Some top-level uses have null percentage; "
            "cannot verify percentage sum"
        )
    elif top_uses:
        pct_sum = round(sum(float(p) for p in pcts), 4)
        if abs(pct_sum - 100.0) > tolerance_pct:
            errors.append(
                f"[percentage_sum] Top-level percentage sum {pct_sum:.2f}% deviates "
                f"from 100% by more than {tolerance_pct}%"
            )

    # ── [amount_sum] ─────────────────────────────────────────────────────────
    total = extracted.get("total_net_proceeds_hkd_million")
    amounts = [u.get("amount_hkd_million") for u in top_uses]
    if any(a is None for a in amounts) or total is None:
        warnings.append(
            "[amount_sum] Some top-level uses or total proceeds have null amount; "
            "cannot verify amount sum"
        )
    elif top_uses and float(total) != 0:
        amt_sum = sum(float(a) for a in amounts)
        if abs(amt_sum - float(total)) / float(total) > 0.01:
            errors.append(
                f"[amount_sum] Top-level amount sum HK${amt_sum:.1f}M deviates "
                f"from total HK${total:.1f}M by more than 1%"
            )

    # ── [item_consistency] ───────────────────────────────────────────────────
    if total is not None and float(total) != 0:
        for u in top_uses:
            amt = u.get("amount_hkd_million")
            pct = u.get("percentage")
            if amt is not None and pct is not None:
                expected = float(total) * float(pct) / 100.0
                if abs(float(amt) - expected) / float(total) > 0.02:
                    errors.append(
                        f"[item_consistency] use_id={u.get('use_id')!r}: "
                        f"amount HK${float(amt):.1f}M vs expected HK${expected:.1f}M "
                        f"(pct={pct}% × total={total}M) differs by more than 2% of total"
                    )

    # ── [category_vocab] ─────────────────────────────────────────────────────
    for u in top_uses:
        cat = u.get("category", "")
        category_proposed = u.get("category_proposed")
        # Skip the vocab check when category_proposed is set — this signals an
        # intentional "no standard match" item where the LLM chose the closest
        # label but flagged it as imprecise via category_proposed.
        if category_proposed:
            continue
        # v2 pipeline: L2 sets category=None because classification is deferred
        # to L4. None is not a vocab gap — it is intentional.
        if cat is None:
            continue
        if cat not in _CATEGORY_VOCAB:
            warnings.append(
                f"[category_vocab] use_id={u.get('use_id')!r}: "
                f"category {cat!r} is not in the allowed vocabulary"
            )

    # ── [category_l1] ────────────────────────────────────────────────────────
    for u in top_uses:
        cat = u.get("category")
        category_proposed = u.get("category_proposed")
        # Exempt when category_proposed is set (same exemption as [category_vocab])
        if category_proposed:
            continue
        # Exempt when category is None (already caught by [required_fields] or
        # [category_vocab] — no useful L1 check possible).
        if cat is None:
            continue
        # Exempt when category is not in the allowed vocabulary — [category_vocab]
        # already warns about it; we avoid double-reporting.
        if cat not in _CATEGORY_VOCAB:
            continue
        if cat not in CATEGORY_L1_MAP:
            errors.append(
                f"[category_l1] use_id={u.get('use_id')!r}: "
                f"category {cat!r} does not map to any L1 category"
            )

    # ── [schema_version] ─────────────────────────────────────────────────────
    record_schema_version = extracted.get("schema_version")
    if record_schema_version is None:
        warnings.append(
            f"[schema_version] schema_version absent from record "
            f"(validated against SCHEMA_VERSION={SCHEMA_VERSION!r})"
        )
    elif str(record_schema_version) != SCHEMA_VERSION:
        warnings.append(
            f"[schema_version] record schema_version={record_schema_version!r} "
            f"differs from current SCHEMA_VERSION={SCHEMA_VERSION!r}; "
            "old data is still processable"
        )

    # ── [category_raw_present] — v2: every use must have non-empty category_raw ──
    for u in uses:
        cat_raw_val = u.get("category_raw", "")
        if cat_raw_val is None or not str(cat_raw_val).strip():
            errors.append(
                f"[category_raw_present] use_id={u.get('use_id')!r}: "
                "category_raw is empty or missing; L2 must provide a raw label"
            )

    # ── [total_proceeds_present] — v2: total_net_proceeds must be non-null ──────
    tp = extracted.get("total_net_proceeds_hkd_million")
    if tp is None:
        errors.append("[total_proceeds_present] total_net_proceeds_hkd_million is missing or null")
    elif float(tp) < 0:
        errors.append("[total_proceeds_present] total_net_proceeds_hkd_million is negative")

    passed = len(errors) == 0
    return passed, errors, warnings


# ── File I/O ──────────────────────────────────────────────────────────────────


def validate_file(
    extracted_file: Path,
    validated_dir: Path,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Validate one extracted JSON file; write <stem>.validated.json.

    Returns the augmented dict (original data + "validation" block).
    """
    validated_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, Any] = json.loads(extracted_file.read_text(encoding="utf-8"))
    stem = extracted_file.stem  # e.g. "ltn20180907011"
    out_path = validated_dir / f"{stem}.validated.json"

    passed, errors, warnings = validate_record(extracted, tolerance_pct)

    result = dict(extracted)
    result["validation"] = {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "tolerance_pct": tolerance_pct,
        "schema_version_validated_against": SCHEMA_VERSION,
        "validated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def process_all(
    extracted_dir: Path,
    validated_dir: Path,
    tolerance_pct: float = 1.0,
    workers: int = 4,
) -> dict[str, Any]:
    """Validate every *.json (excluding *.validated.json and *.error.json) in
    extracted_dir, write results to validated_dir, using a thread pool.

    Returns a summary dict: {"passed": int, "failed": int, "total": int}.
    """
    jsons = sorted(
        p
        for p in extracted_dir.glob("*.json")
        if ".validated" not in p.name and ".error" not in p.name
    )
    if not jsons:
        logger.warning("No extracted JSON files found in %s", extracted_dir)
        return {"passed": 0, "failed": 0, "total": 0}

    passed_count = 0
    failed_count = 0

    def _process_one(jf: Path) -> tuple[str, bool, str]:
        """Process one file; return (filename, passed, log_output)."""
        buf = io.StringIO()
        buf.write(f"-> {jf.name}\n")
        try:
            result = validate_file(jf, validated_dir, tolerance_pct)
            v = result["validation"]
            status = "PASS" if v["passed"] else "FAIL"
            buf.write(
                f"  {status}  (ticker={result.get('hk_ticker')}, "
                f"date={result.get('document_date')})\n"
            )
            for e in v["errors"]:
                buf.write(f"  ERROR: {e}\n")
            for w in v["warnings"]:
                buf.write(f"  WARN:  {w}\n")
            return jf.name, v["passed"], buf.getvalue()
        except Exception as exc:
            buf.write(f"  [ERROR] {exc}\n")
            return jf.name, False, buf.getvalue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_one, jf): jf for jf in jsons}
        for future in concurrent.futures.as_completed(futures):
            filename, ok, log_output = future.result()
            logger.info(log_output.strip())
            if ok:
                passed_count += 1
            else:
                failed_count += 1

    total = passed_count + failed_count
    logger.info(
        "L3 complete: %s passed, %s failed (of %s total)",
        passed_count, failed_count, total,
    )
    return {"passed": passed_count, "failed": failed_count, "total": total}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L3: validate L2 extracted JSON files")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--single",
        metavar="FILENAME",
        help="Validate one file from data/extracted/ by name",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Validate all files in data/extracted/",
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=1.0,
        metavar="PCT",
        help="Max allowed deviation of percentage sum from 100%% (default 1.0)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on any validation failure",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Number of parallel worker threads for --all (default 4)",
    )
    args = parser.parse_args()

    from hk_ipo.config import EXTRACTED_DIR

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.single:
        sf = EXTRACTED_DIR / args.single
        if not sf.exists():
            logger.error("Not found: %s", sf)
            sys.exit(1)
        res = validate_file(sf, EXTRACTED_DIR, args.tolerance_pct)
        v = res["validation"]
        print("PASS" if v["passed"] else "FAIL")  # intentional stdout
        for e in v["errors"]:
            print(f"ERROR: {e}")  # intentional stdout
        for w in v["warnings"]:
            print(f"WARN:  {w}")  # intentional stdout
        if args.strict and not v["passed"]:
            sys.exit(1)
    elif args.all:
        summary = process_all(EXTRACTED_DIR, EXTRACTED_DIR, args.tolerance_pct, workers=args.workers)
        if args.strict and summary["failed"] > 0:
            sys.exit(1)
    else:
        parser.error(
            "Specify --single <filename.json> or --all. "
            "Explicit choice required to avoid unintended writes."
        )
