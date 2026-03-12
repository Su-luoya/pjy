"""Shared analysis bundle used by UI, CLI, and reporting."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.transform import (
    compute_annual_summary,
    compute_filtered_annual_amount_yoy,
    compute_supplier_year_summary,
)


@dataclass(slots=True)
class AnalysisBundle:
    """Reusable analytics outputs derived from parsed detail rows."""

    detail: pd.DataFrame
    table_a: pd.DataFrame
    table_b: pd.DataFrame
    table_c: pd.DataFrame

    @property
    def row_count(self) -> int:
        return int(len(self.detail))

    @property
    def supplier_count(self) -> int:
        if self.detail.empty:
            return 0
        return int(self.detail["供应商"].nunique())

    @property
    def year_count(self) -> int:
        if self.detail.empty:
            return 0
        return int(self.detail["年份"].nunique())


def build_analysis(detail_df: pd.DataFrame) -> AnalysisBundle:
    """Compute all summary tables from normalized detail data."""
    detail = detail_df.copy()
    return AnalysisBundle(
        detail=detail,
        table_a=compute_supplier_year_summary(detail),
        table_b=compute_annual_summary(detail),
        table_c=compute_filtered_annual_amount_yoy(detail),
    )
