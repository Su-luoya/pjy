from __future__ import annotations

import pandas as pd

from src.io_parser import clean_product_name, parse_sheet_rows
from src.transform import (
    compute_annual_summary,
    compute_filtered_annual_amount_yoy,
    compute_supplier_year_summary,
)


def test_clean_product_name_supports_closed_and_unclosed_suffix() -> None:
    assert clean_product_name("输液卡{塑料}[20250102-21021212]") == "输液卡{塑料}"
    assert clean_product_name("输液卡{塑料}[20250102-21021212") == "输液卡{塑料}"
    assert clean_product_name("腕带（打印）☆国产中裕") == "腕带（打印）☆国产中裕"


def test_parse_sheet_rows_extracts_supplier_and_alias_and_skips_totals() -> None:
    sheet_df = pd.DataFrame(
        [
            {"Unnamed: 0": "供应商 : 柳辉", "开单日期": None, "单据号": None, "品名规格": None, "金额": None},
            {
                "Unnamed: 0": None,
                "开单日期": "2025-01-02",
                "单据号": "20258112000001",
                "品名规格": "腕带（打印）☆国产中裕[20250102-21021212]",
                "金额": "100",
            },
            {"Unnamed: 0": None, "开单日期": "小计", "单据号": None, "品名规格": None, "金额": None},
            {"Unnamed: 0": "供应商 : 郁小梅", "开单日期": None, "单据号": None, "品名规格": None, "金额": None},
            {
                "Unnamed: 0": None,
                "开单日期": "2025-01-03",
                "单据号": "20258112000002",
                "品名规格": "输液卡{塑料}[20250103-21021212",
                "金额": "200",
            },
        ]
    )

    rows = parse_sheet_rows(year=2025, sheet_df=sheet_df)

    assert len(rows) == 2
    assert rows[0]["供应商"] == "柳辉"
    assert rows[1]["供应商"] == "柳辉"
    assert rows[1]["品名清洗"] == "输液卡{塑料}"


def test_compute_supplier_year_summary_uses_row_count_and_yoy_rules() -> None:
    detail_df = pd.DataFrame(
        [
            {"年份": 2020, "供应商": "A", "品名清洗": "P1", "金额": 100},
            {"年份": 2020, "供应商": "A", "品名清洗": "P2", "金额": 200},
            {"年份": 2021, "供应商": "A", "品名清洗": "P3", "金额": 150},
            {"年份": 2020, "供应商": "B", "品名清洗": "P1", "金额": 0},
            {"年份": 2021, "供应商": "B", "品名清洗": "P1", "金额": 50},
        ]
    )

    result = compute_supplier_year_summary(detail_df)

    a_2020 = result[(result["供应商"] == "A") & (result["年份"] == 2020)].iloc[0]
    a_2021 = result[(result["供应商"] == "A") & (result["年份"] == 2021)].iloc[0]
    b_2021 = result[(result["供应商"] == "B") & (result["年份"] == 2021)].iloc[0]

    assert a_2020["项目数"] == 2
    assert pd.isna(a_2020["项目数环比%"])
    assert a_2021["项目数"] == 1
    assert a_2021["项目数环比%"] == -50
    assert pd.isna(b_2021["金额环比%"])  # 上一年为 0，环比应为空


def test_annual_summary_and_filtered_yoy_respect_exclusion_scope() -> None:
    detail_df = pd.DataFrame(
        [
            {"年份": 2020, "供应商": "普通供应商", "品名清洗": "A", "金额": 100},
            {"年份": 2020, "供应商": "武汉市思尔康医疗器械有限", "品名清洗": "B", "金额": 900},
            {"年份": 2021, "供应商": "普通供应商", "品名清洗": "A", "金额": 200},
            {"年份": 2021, "供应商": "武汉市思尔康医疗器械有限", "品名清洗": "C", "金额": 100},
        ]
    )

    annual_all = compute_annual_summary(detail_df)
    annual_filtered = compute_filtered_annual_amount_yoy(detail_df)

    assert annual_all["总金额"].tolist() == [1000, 300]
    assert annual_filtered["总金额"].tolist() == [100, 200]
    assert pd.isna(annual_filtered.iloc[0]["金额环比%"])
    assert annual_filtered.iloc[1]["金额环比%"] == 100
