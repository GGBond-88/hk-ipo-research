"""L3 验证层：对 L2 提取结果做数值校验和格式规范化。

7 项检查（按 check_id 标识）：

  [required_fields]     必须字段存在且非 null                → ERROR
  [ticker_format]       hk_ticker 为 4-5 位纯数字           → ERROR
  [percentage_sum]      顶层用途百分比之和≈100%             → ERROR
                          （任一百分比为 null 时降级为 WARNING）
  [amount_sum]          顶层金额之和≈总募资额（±1%）        → ERROR
                          （任一金额或总额为 null 时降级为 WARNING）
  [item_consistency]    单项 amount ≈ total×pct/100（±2%）  → ERROR
  [no_duplicate_use_id] use_id 唯一性                        → ERROR
  [category_vocab]      category 在预定义词表中              → WARNING（不影响 passed）

输入：data/extracted/<stem>.json
输出：data/extracted/<stem>.validated.json  （带 "validation" 块）
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hk_ipo.schema import CATEGORY_L2

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
    missing = [
        f for f in _REQUIRED_TOP_FIELDS
        if f not in extracted or extracted[f] is None
    ]
    if missing:
        errors.append(
            f"[required_fields] Missing or null fields: {', '.join(missing)}"
        )

    # ── [ticker_format] ──────────────────────────────────────────────────────
    ticker = extracted.get("hk_ticker")
    if ticker is not None:
        if not _TICKER_RE.match(str(ticker)):
            errors.append(
                f"[ticker_format] hk_ticker {ticker!r} is not a 4-5 digit code"
            )
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
        errors.append(
            f"[no_duplicate_use_id] Duplicate use_id(s): {', '.join(dupes)}"
        )

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
        if cat not in _CATEGORY_VOCAB:
            warnings.append(
                f"[category_vocab] use_id={u.get('use_id')!r}: "
                f"category {cat!r} is not in the allowed vocabulary"
            )

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
    extracted: dict[str, Any] = json.loads(
        extracted_file.read_text(encoding="utf-8")
    )
    stem = extracted_file.stem          # e.g. "ltn20180907011"
    out_path = validated_dir / f"{stem}.validated.json"

    passed, errors, warnings = validate_record(extracted, tolerance_pct)

    result = dict(extracted)
    result["validation"] = {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "tolerance_pct": tolerance_pct,
        "validated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def process_all(
    extracted_dir: Path,
    validated_dir: Path,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Validate every *.json (excluding *.validated.json and *.error.json) in
    extracted_dir; write results to validated_dir.

    Returns a summary dict: {"passed": int, "failed": int, "total": int}.
    """
    jsons = sorted(
        p
        for p in extracted_dir.glob("*.json")
        if ".validated" not in p.name and ".error" not in p.name
    )
    if not jsons:
        print(f"[WARN] No extracted JSON files found in {extracted_dir}")
        return {"passed": 0, "failed": 0, "total": 0}

    passed_count = failed_count = 0
    for jf in jsons:
        print(f"\n→ {jf.name}")
        try:
            result = validate_file(jf, validated_dir, tolerance_pct)
        except Exception as exc:
            failed_count += 1
            print(f"  [ERROR] Could not validate: {exc}")
            continue

        v = result["validation"]
        status = "PASS" if v["passed"] else "FAIL"
        print(
            f"  {status}  (ticker={result.get('hk_ticker')}, "
            f"date={result.get('document_date')})"
        )
        for e in v["errors"]:
            print(f"  ERROR: {e}")
        for w in v["warnings"]:
            print(f"  WARN:  {w}")

        if v["passed"]:
            passed_count += 1
        else:
            failed_count += 1

    total = passed_count + failed_count
    print(
        f"\nL3 complete: {passed_count} passed, {failed_count} failed "
        f"(of {total} total)"
    )
    return {"passed": passed_count, "failed": failed_count, "total": total}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="L3: validate L2 extracted JSON files"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--single", metavar="FILENAME",
        help="Validate one file from data/extracted/ by name",
    )
    group.add_argument(
        "--all", action="store_true",
        help="Validate all files in data/extracted/",
    )
    parser.add_argument(
        "--tolerance-pct", type=float, default=1.0, metavar="PCT",
        help="Max allowed deviation of percentage sum from 100%% (default 1.0)",
    )
    args = parser.parse_args()

    from hk_ipo.config import EXTRACTED_DIR

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.single:
        import sys

        sf = EXTRACTED_DIR / args.single
        if not sf.exists():
            print(f"[ERROR] Not found: {sf}")
            sys.exit(1)
        res = validate_file(sf, EXTRACTED_DIR, args.tolerance_pct)
        v = res["validation"]
        print("PASS" if v["passed"] else "FAIL")
        for e in v["errors"]:
            print(f"ERROR: {e}")
        for w in v["warnings"]:
            print(f"WARN:  {w}")
    elif args.all:
        process_all(EXTRACTED_DIR, EXTRACTED_DIR, args.tolerance_pct)
    else:
        parser.error(
            "Specify --single <filename.json> or --all. "
            "Explicit choice required to avoid unintended writes."
        )
