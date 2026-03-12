"""Business transformations for supplier/annual summaries."""

from __future__ import annotations

import pandas as pd

from src.config import EXCLUDED_SUPPLIER_KEYWORDS


def _safe_pct_change(series: pd.Series) -> pd.Series:
    prev = series.shift(1)
    ratio = (series - prev) / prev
    ratio = ratio.where(prev != 0)
    return ratio * 100


def compute_supplier_year_summary(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Build table A: supplier-year summary with project and amount YoY."""
    if detail_df.empty:
        return pd.DataFrame(
            columns=["供应商", "年份", "项目数", "供货金额", "项目数环比%", "金额环比%"]
        )

    grouped = (
        detail_df.groupby(["供应商", "年份"], as_index=False)
        .agg(项目数=("供应商", "size"), 供货金额=("金额", "sum"))
        .sort_values(["供应商", "年份"])
        .reset_index(drop=True)
    )

    grouped["项目数环比%"] = (
        grouped.groupby("供应商", group_keys=False)["项目数"].apply(_safe_pct_change)
    )
    grouped["金额环比%"] = (
        grouped.groupby("供应商", group_keys=False)["供货金额"].apply(_safe_pct_change)
    )
    return grouped


def compute_annual_summary(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Build table B: yearly projects, product varieties, and total amount."""
    if detail_df.empty:
        return pd.DataFrame(columns=["年份", "项目数", "供货品种", "总金额"])

    annual = (
        detail_df.groupby("年份", as_index=False)
        .agg(
            项目数=("供应商", "size"),
            供货品种=("品名清洗", lambda s: s[s.ne("")].nunique()),
            总金额=("金额", "sum"),
        )
        .sort_values("年份")
        .reset_index(drop=True)
    )
    return annual


def exclude_suppliers_for_charts(
    detail_df: pd.DataFrame,
    excluded_keywords: list[str] | None = None,
) -> pd.DataFrame:
    """Remove excluded suppliers for chart and annual YoY calculations."""
    if detail_df.empty:
        return detail_df.copy()

    keywords = excluded_keywords or EXCLUDED_SUPPLIER_KEYWORDS
    mask = pd.Series(False, index=detail_df.index)
    for keyword in keywords:
        mask = mask | detail_df["供应商"].str.contains(keyword, na=False)
    return detail_df.loc[~mask].copy()


def compute_filtered_annual_amount_yoy(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Build table C from filtered dataset: yearly amount and YoY."""
    if detail_df.empty:
        return pd.DataFrame(columns=["年份", "总金额", "金额环比%"])

    filtered_df = exclude_suppliers_for_charts(detail_df)
    annual_amount = (
        filtered_df.groupby("年份", as_index=False)
        .agg(总金额=("金额", "sum"))
        .sort_values("年份")
        .reset_index(drop=True)
    )
    annual_amount["金额环比%"] = _safe_pct_change(annual_amount["总金额"])
    return annual_amount


def supplier_options_for_charts(
    supplier_year_df: pd.DataFrame,
    excluded_keywords: list[str] | None = None,
) -> list[str]:
    """List suppliers available for charting after exclusions."""
    if supplier_year_df.empty:
        return []

    keywords = excluded_keywords or EXCLUDED_SUPPLIER_KEYWORDS
    supplier_list = supplier_year_df["供应商"].dropna().unique().tolist()
    result = []
    for supplier in sorted(supplier_list):
        if any(keyword in supplier for keyword in keywords):
            continue
        result.append(supplier)
    return result
