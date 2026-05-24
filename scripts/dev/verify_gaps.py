"""Quick ad-hoc verification of edge cases for timeline black-box testing.

Exercises the hk_ipo.enrichments.timeline module against 15 hand-crafted
records covering: keyword variants, numeric spellings, hyphenated forms,
whitespace, malformed JSON, and enrichment-key preservation.

Usage
-----
    python scripts/dev/verify_gaps.py
    python scripts/dev/verify_gaps.py --help
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PKG = PROJECT_ROOT / "src" / "hk_ipo"
REAL_CONFIG = SRC_PKG / "config.py"


def make_config_override(tmp_path: Path) -> str:
    override_root = tmp_path / "config_override"
    pkg = override_root / "hk_ipo"
    pkg.mkdir(parents=True)
    shutil.copy(SRC_PKG / "__init__.py", pkg / "__init__.py")
    enrich_src = SRC_PKG / "enrichments"
    enrich_dst = pkg / "enrichments"
    enrich_dst.mkdir()
    shutil.copy(enrich_src / "__init__.py", enrich_dst / "__init__.py")
    shutil.copy(enrich_src / "base.py", enrich_dst / "base.py")
    shutil.copy(enrich_src / "timeline.py", enrich_dst / "timeline.py")
    real_text = REAL_CONFIG.read_text(encoding="utf-8")
    data_dir = tmp_path / "data"
    custom_cfg = real_text.replace(
        'DATA_DIR: Path = PROJECT_ROOT / "data"',
        f'DATA_DIR: Path = Path(r"{data_dir}")',
    )
    (pkg / "config.py").write_text(custom_cfg, encoding="utf-8")
    return str(override_root)


def run_timeline(prefix: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = prefix + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "hk_ipo.enrichments.timeline", *args],
        capture_output=True, text=True, timeout=30, env=env, check=False,
    )


def main() -> None:
    results: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prefix = make_config_override(tmp)
        data_dir = tmp / "data"
        cat_dir = data_dir / "categorized"
        cat_dir.mkdir(parents=True)
        enr_dir = data_dir / "enriched"

        # Test 1: 'within 1 year'
        record = {
            "hk_ticker": "T001", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Complete within 1 year.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": "Within 1 year."}],
            "enrichments": {},
        }
        (cat_dir / "T001.json").write_text(json.dumps(record), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T001.json"))
        loaded = json.loads((enr_dir / "T001.json").read_text(encoding="utf-8"))
        results.append(f"Test 1 (within 1 year): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 2: multiple numerics - longest wins (12 months + 3 years)
        record2 = {
            "hk_ticker": "T002", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1",
                       "description": "Phase 1 in 6 months, phase 2 over 3 years.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": "6-month start, 3-year full deployment."}],
            "enrichments": {},
        }
        (cat_dir / "T002.json").write_text(json.dumps(record2), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T002.json"))
        loaded = json.loads((enr_dir / "T002.json").read_text(encoding="utf-8"))
        results.append(f"Test 2 (6 months + 3 years): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 24-36m)")

        # Test 3: 'extended period'
        record3 = {
            "hk_ticker": "T003", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Extended period deployment.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T003.json").write_text(json.dumps(record3), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T003.json"))
        loaded = json.loads((enr_dir / "T003.json").read_text(encoding="utf-8"))
        results.append(f"Test 3 (extended period): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 36m+)")

        # Test 4: hyphenated 'very-long'
        record4 = {
            "hk_ticker": "T004", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Very-long term strategy.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T004.json").write_text(json.dumps(record4), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T004.json"))
        loaded = json.loads((enr_dir / "T004.json").read_text(encoding="utf-8"))
        results.append(f"Test 4 (very-long): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 36m+)")

        # Test 5: preservation of other enrichment dimensions
        record5 = {
            "hk_ticker": "T005", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Deploy in 12 months.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {"country": {"version": 1, "countries": ["HK"],
                                         "by_use_id": {"u1": ["HK"]}}},
        }
        (cat_dir / "T005.json").write_text(json.dumps(record5), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T005.json"))
        loaded = json.loads((enr_dir / "T005.json").read_text(encoding="utf-8"))
        results.append(f"Test 5a (country preserved): {'country' in loaded['enrichments']} (expected: True)")
        results.append(f"Test 5b (timeline added): {'timeline' in loaded['enrichments']} (expected: True)")
        results.append(f"Test 5c (country countries): {loaded['enrichments']['country']['countries']} (expected: ['HK'])")

        # Test 6: 'short term' with space
        record6 = {
            "hk_ticker": "T006", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Short term working capital needs.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T006.json").write_text(json.dumps(record6), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T006.json"))
        loaded = json.loads((enr_dir / "T006.json").read_text(encoding="utf-8"))
        results.append(f"Test 6 (short term with space): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 7: 'five years' spelled out
        record7 = {
            "hk_ticker": "T007", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Five years strategic plan.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T007.json").write_text(json.dumps(record7), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T007.json"))
        loaded = json.loads((enr_dir / "T007.json").read_text(encoding="utf-8"))
        results.append(f"Test 7 (five years): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 36m+)")

        # Test 8: '12 mo' abbreviation
        record8 = {
            "hk_ticker": "T008", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Complete in 12 mo.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T008.json").write_text(json.dumps(record8), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T008.json"))
        loaded = json.loads((enr_dir / "T008.json").read_text(encoding="utf-8"))
        results.append(f"Test 8 (12 mo): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 9: malformed JSON
        bad_file = cat_dir / "T009.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        r = run_timeline(prefix, str(bad_file))
        results.append(f"Test 9 (malformed JSON exit): {r.returncode} (expected: non-zero)")

        # Test 10: 'extended-horizon' hyphenated
        record10 = {
            "hk_ticker": "T010", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Extended-horizon strategic investment.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T010.json").write_text(json.dumps(record10), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T010.json"))
        loaded = json.loads((enr_dir / "T010.json").read_text(encoding="utf-8"))
        results.append(f"Test 10 (extended-horizon): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 36m+)")

        # Test 11: '37+ months' with plus sign
        record11 = {
            "hk_ticker": "T011", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Deployment over 37+ months.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T011.json").write_text(json.dumps(record11), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T011.json"))
        loaded = json.loads((enr_dir / "T011.json").read_text(encoding="utf-8"))
        results.append(f"Test 11 (37+ months): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 36m+)")

        # Test 12: 'within-year' hyphenated variant
        record12 = {
            "hk_ticker": "T012", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Completion within-year.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T012.json").write_text(json.dumps(record12), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T012.json"))
        loaded = json.loads((enr_dir / "T012.json").read_text(encoding="utf-8"))
        results.append(f"Test 12 (within-year): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 13: record with no enrichments key at all
        record13 = {
            "hk_ticker": "T013", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Deploy in 12 months.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
        }
        (cat_dir / "T013.json").write_text(json.dumps(record13), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T013.json"))
        loaded = json.loads((enr_dir / "T013.json").read_text(encoding="utf-8"))
        results.append(f"Test 13 (no enrichments key): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 14: whitespace variation - multiple spaces
        record14 = {
            "hk_ticker": "T014", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1", "description": "Deploy in 12   months.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": ""}],
            "enrichments": {},
        }
        (cat_dir / "T014.json").write_text(json.dumps(record14), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T014.json"))
        loaded = json.loads((enr_dir / "T014.json").read_text(encoding="utf-8"))
        results.append(f"Test 14 (12   months): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 0-12m)")

        # Test 15: numeric in description, qualitative in source_text only (numeric wins)
        record15 = {
            "hk_ticker": "T015", "company_name_en": "Test", "schema_version": "2.0",
            "uses": [{"use_id": "u1",
                       "description": "Deploy over 18 months.",
                       "category_raw": "expansion", "percentage": 100.0,
                       "source_text": "Long-term strategic initiative."}],
            "enrichments": {},
        }
        (cat_dir / "T015.json").write_text(json.dumps(record15), encoding="utf-8")
        run_timeline(prefix, str(cat_dir / "T015.json"))
        loaded = json.loads((enr_dir / "T015.json").read_text(encoding="utf-8"))
        results.append(f"Test 15 (18 months + long-term qualitative): {loaded['enrichments']['timeline']['by_use_id']['u1']} (expected: 12-24m)")

    for r in results:
        print(r)

    print("\nAll checks complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # No positional args needed; argparse gives --help for free.
    parser.parse_args()
    main()
