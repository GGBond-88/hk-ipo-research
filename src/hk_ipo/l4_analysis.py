"""L4 分析层：汇总多份招股书的 L3 校验结果，执行跨公司统计分析，
生成可视化报告（图表 + CSV 摘要）写入 data/reports/。

典型分析维度：
  - 各行业资金用途分布（研发 / 营销 / 运营 / 补充流动资金等）
  - 募资规模 vs 用途结构相关性
  - 时序趋势（按 IPO 日期）
"""

from __future__ import annotations  # noqa: I001

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # headless — must be called before matplotlib.pyplot is imported
import matplotlib.pyplot as plt  # noqa: I001
import pandas as pd  # noqa: I001

from hk_ipo.schema import CATEGORY_L1_MAP, CATEGORY_L1_TREE  # noqa: I001


# All L1 category names, in a stable order derived from schema
_L1_CATEGORIES: list[str] = list(CATEGORY_L1_TREE.keys())


def _load_validated_files(extracted_dir: str) -> tuple[list[dict[str, Any]], int]:
    """Read all *.validated.json files; return (valid_records, skipped_count)."""
    dirpath = Path(extracted_dir)
    valid_records: list[dict[str, Any]] = []
    skipped = 0

    for fp in sorted(dirpath.glob("*.validated.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] Could not read {fp.name}: {exc} — skipping")
            skipped += 1
            continue

        validation = data.get("validation", {})
        if not validation.get("passed", False):
            reasons = validation.get("errors", [])
            print(
                f"[SKIP] {fp.name}: validation.passed=False "
                f"({len(reasons)} error(s): "
                f"{'; '.join(reasons[:2])}"
                f"{'…' if len(reasons) > 2 else ''})"
            )
            skipped += 1
            continue

        valid_records.append(data)

    return valid_records, skipped


def _build_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten all use items across records into a single DataFrame."""
    rows = []
    for rec in records:
        ticker = rec.get("hk_ticker")
        doc_date = rec.get("document_date")
        uses = rec.get("uses", [])
        for u in uses:
            cat_l2 = u.get("category")
            cat_l1 = CATEGORY_L1_MAP.get(cat_l2, "Unknown") if cat_l2 else "Unknown"
            rows.append({
                "ticker": ticker,
                "document_date": doc_date,
                "category_l1": cat_l1,
                "category_l2": cat_l2,
                "percentage": u.get("percentage"),
                "amount_hkd_million": u.get("amount_hkd_million"),
                "is_top_level": u.get("parent_id") is None,
                "geo_scope": u.get("geo_scope"),
                "target_industries": u.get("target_industries"),
                "asset_type": u.get("asset_type"),
                "headcount_plan": u.get("headcount_plan"),
            })

    if not rows:
        return pd.DataFrame(columns=[
            "ticker", "document_date", "category_l1", "category_l2",
            "percentage", "amount_hkd_million", "is_top_level",
            "geo_scope", "target_industries", "asset_type", "headcount_plan",
        ])

    df = pd.DataFrame(rows)
    # Convert numeric columns
    df["percentage"] = pd.to_numeric(df["percentage"], errors="coerce")
    df["amount_hkd_million"] = pd.to_numeric(df["amount_hkd_million"], errors="coerce")
    return df


def _plot_allocation_by_l1(df: pd.DataFrame, reports_dir: Path) -> None:
    """Horizontal bar chart: mean % allocation by L1 category across all companies."""
    top = df[df["is_top_level"]].copy()
    agg = top.groupby("category_l1")["percentage"].mean().reindex(_L1_CATEGORIES).dropna()
    if agg.empty:
        print("[L4] No percentage data for allocation_by_l1.png — skipping chart")
        return

    fig, ax = plt.subplots(figsize=(8, 4))
    agg.plot.barh(ax=ax, color="steelblue")
    ax.set_xlabel("Mean allocation (%)")
    ax.set_title("Mean IPO Proceeds Allocation by L1 Category")
    ax.legend(["Mean %"])
    fig.tight_layout()
    fig.savefig(reports_dir / "allocation_by_l1.png", dpi=100)
    plt.close(fig)


def _plot_allocation_by_company_l1(df: pd.DataFrame, reports_dir: Path) -> None:
    """Stacked bar chart: % allocation by L1 category per ticker."""
    top = df[df["is_top_level"]].copy()
    pivot = (
        top.groupby(["ticker", "category_l1"])["percentage"]
        .mean()
        .unstack(fill_value=0)
        .reindex(columns=_L1_CATEGORIES, fill_value=0)
    )
    if pivot.empty:
        print("[L4] No data for allocation_by_company_l1.png — skipping chart")
        return

    fig, ax = plt.subplots(figsize=(max(6, len(pivot) * 1.5), 5))
    pivot.plot.bar(ax=ax, stacked=True)
    ax.set_xlabel("Ticker")
    ax.set_ylabel("Mean allocation (%)")
    ax.set_title("IPO Proceeds Allocation by L1 Category per Company")
    ax.legend(title="L1 Category", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(reports_dir / "allocation_by_company_l1.png", dpi=100)
    plt.close(fig)


def _plot_timeseries_l1(
    df: pd.DataFrame,
    reports_dir: Path,
    n_tickers: int,
) -> bool:
    """Time-series chart: mean % by L1 category over document_date.

    Returns True if the chart was produced, False if skipped.
    """
    top = df[df["is_top_level"]].copy()
    top["document_date"] = pd.to_datetime(top["document_date"], errors="coerce")
    top = top.dropna(subset=["document_date"])

    distinct_dates = top["document_date"].nunique()

    if distinct_dates < 2:
        print(
            f"[L4] Skipping timeseries_l1.png: only {distinct_dates} distinct date(s) "
            "(need 2+)"
        )
        return False
    if n_tickers < 2:
        print(
            f"[L4] Skipping timeseries_l1.png: only {n_tickers} ticker(s) (need 2+)"
        )
        return False

    pivot = (
        top.groupby(["document_date", "category_l1"])["percentage"]
        .mean()
        .unstack(fill_value=0)
        .reindex(columns=_L1_CATEGORIES, fill_value=0)
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    for col in pivot.columns:
        ax.plot(pivot.index, pivot[col], marker="o", label=col)
    ax.set_xlabel("Document Date")
    ax.set_ylabel("Mean allocation (%)")
    ax.set_title("IPO Proceeds Allocation by L1 Category over Time")
    ax.legend(title="L1 Category")
    fig.tight_layout()
    fig.savefig(reports_dir / "timeseries_l1.png", dpi=100)
    plt.close(fig)
    return True


def _write_summary_md(
    reports_dir: Path,
    df: pd.DataFrame,
    n_companies: int,
    timeseries_produced: bool,
) -> None:
    """Write reports_dir/summary.md with key cross-company findings."""
    top = df[df["is_top_level"]].copy()

    total_items = len(df)

    # Top L1 by mean percentage
    l1_mean = top.groupby("category_l1")["percentage"].mean()
    top_l1 = l1_mean.idxmax() if not l1_mean.empty else "N/A"
    top_l1_pct = f"{l1_mean.max():.1f}" if not l1_mean.empty else "N/A"

    # Top L2 by mean percentage
    l2_mean = top.groupby("category_l2")["percentage"].mean()
    top_l2 = l2_mean.idxmax() if not l2_mean.empty else "N/A"
    top_l2_pct = f"{l2_mean.max():.1f}" if not l2_mean.empty else "N/A"

    # Date range
    dates = pd.to_datetime(df["document_date"], errors="coerce").dropna()
    if len(dates) > 0:
        date_range = f"{dates.min().date()} to {dates.max().date()}"
    else:
        date_range = "N/A"

    lines = [
        "# HK IPO Use-of-Proceeds Analysis",
        "",
        "## Summary",
        "",
        f"- **Companies analysed**: {n_companies}",
        f"- **Total use items**: {total_items}",
        f"- **Top L1 category** (by mean allocation): {top_l1} ({top_l1_pct}%)",
        f"- **Top L2 category** (by mean allocation): {top_l2} ({top_l2_pct}%)",
        f"- **Date range**: {date_range}",
        "",
        "## Charts",
        "",
        "![Mean allocation by L1 category](allocation_by_l1.png)",
        "",
        "![Allocation by company and L1 category](allocation_by_company_l1.png)",
        "",
    ]

    if timeseries_produced:
        lines.append("![Time-series of allocation by L1 category](timeseries_l1.png)")
        lines.append("")
    else:
        note = (
            "Time-series chart was skipped (requires 2+ companies and 2+ distinct dates)."
            if n_companies < 2
            else "Time-series chart was skipped (insufficient date variation)."
        )
        lines.append(f"*{note}*")
        lines.append("")

    (reports_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_analysis(extracted_dir: str, reports_dir: str | None = None) -> None:
    """Read all validated JSON files, generate analysis reports.

    Parameters
    ----------
    extracted_dir:  Directory containing *.validated.json files.
    reports_dir:    Output directory for reports. Defaults to config.REPORTS_DIR.
    """
    if reports_dir is None:
        from hk_ipo import config
        _reports_dir = config.REPORTS_DIR
    else:
        _reports_dir = Path(reports_dir)

    _reports_dir.mkdir(parents=True, exist_ok=True)

    records, skipped = _load_validated_files(extracted_dir)
    n_companies = len(records)

    print(
        f"[L4] Loaded {n_companies} valid record(s), skipped {skipped} "
        f"(failed validation or unreadable)"
    )

    if n_companies == 0:
        print("[L4] No valid files to analyse — exiting early.")
        return

    df = _build_dataframe(records)
    print(f"[L4] DataFrame: {len(df)} rows, {len(df.columns)} columns")

    # ── CSVs ─────────────────────────────────────────────────────────────────
    df.to_csv(_reports_dir / "uses_by_company.csv", index=False)

    top = df[df["is_top_level"]].copy()
    agg_l1 = (
        top.groupby("category_l1")["percentage"]
        .agg(mean_percentage="mean", count="count")
        .reset_index()
    )
    agg_l1.to_csv(_reports_dir / "allocation_by_l1.csv", index=False)

    print(f"[L4] CSVs written to {_reports_dir}")

    # ── Charts ────────────────────────────────────────────────────────────────
    _plot_allocation_by_l1(df, _reports_dir)
    _plot_allocation_by_company_l1(df, _reports_dir)
    timeseries_produced = _plot_timeseries_l1(df, _reports_dir, n_tickers=n_companies)

    print(f"[L4] Charts written to {_reports_dir}")

    # ── Summary markdown ──────────────────────────────────────────────────────
    _write_summary_md(_reports_dir, df, n_companies, timeseries_produced)
    print(f"[L4] Summary written to {_reports_dir / 'summary.md'}")
