"""Excel parsing utilities for supplier detail workbooks."""

from __future__ import annotations

from typing import BinaryIO

import pandas as pd

from src.config import (
    CLOSED_TRAILING_ID_PATTERN,
    INVALID_OPEN_DATE_MARKERS,
    REQUIRED_COLUMNS,
    SUPPLIER_ALIAS_MAP,
    SUPPLIER_MARKER_PATTERN,
    UNCLOSED_TRAILING_ID_PATTERN,
    YEAR_PATTERN,
)


def parse_year_from_sheet(sheet_name: str) -> int | None:
    """Extract year from a sheet name like '2024年'."""
    match = YEAR_PATTERN.search(str(sheet_name))
    if not match:
        return None
    return int(match.group(1))


def normalize_supplier_name(name: str) -> str:
    """Apply supplier alias mapping and trim spaces."""
    cleaned = str(name or "").strip()
    return SUPPLIER_ALIAS_MAP.get(cleaned, cleaned)


def normalize_cell_value(value: object) -> str:
    """Convert cell value to stripped string, keeping empty for NaN-like values."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def parse_amount(value: object) -> float:
    """Parse amount field into float; invalid values become 0."""
    text = normalize_cell_value(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def clean_product_name(name: str) -> str:
    """Strip trailing source-id suffix from product name."""
    text = normalize_cell_value(name)
    text = CLOSED_TRAILING_ID_PATTERN.sub("", text)
    text = UNCLOSED_TRAILING_ID_PATTERN.sub("", text)
    return text.strip()


def validate_required_columns(df: pd.DataFrame, sheet_name: str) -> None:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        missing_text = "、".join(missing)
        raise ValueError(f"工作表 {sheet_name} 缺少必要列: {missing_text}")


def parse_sheet_rows(year: int, sheet_df: pd.DataFrame) -> list[dict[str, object]]:
    """Extract valid detail rows from one sheet."""
    rows: list[dict[str, object]] = []
    current_supplier = ""

    for _, record in sheet_df.iterrows():
        supplier_marker = normalize_cell_value(record.get("Unnamed: 0"))
        if supplier_marker:
            marker_match = SUPPLIER_MARKER_PATTERN.match(supplier_marker)
            if marker_match:
                supplier_name = normalize_supplier_name(marker_match.group(1))
                if supplier_name:
                    current_supplier = supplier_name
                continue

        open_date = normalize_cell_value(record.get("开单日期"))
        if open_date in INVALID_OPEN_DATE_MARKERS:
            continue
        if not current_supplier:
            continue

        doc_no = normalize_cell_value(record.get("单据号"))
        product_raw = normalize_cell_value(record.get("品名规格"))
        product_clean = clean_product_name(product_raw)

        rows.append(
            {
                "年份": year,
                "供应商": current_supplier,
                "开单日期": open_date,
                "单据号": doc_no,
                "品名规格": product_raw,
                "品名清洗": product_clean,
                "金额": parse_amount(record.get("金额")),
            }
        )

    return rows


def parse_excel_file(file_obj: str | BinaryIO) -> pd.DataFrame:
    """Parse all eligible sheets and return normalized detail rows."""
    workbook = pd.ExcelFile(file_obj)
    all_rows: list[dict[str, object]] = []

    for sheet_name in workbook.sheet_names:
        year = parse_year_from_sheet(sheet_name)
        if year is None:
            continue
        sheet_df = pd.read_excel(workbook, sheet_name=sheet_name, dtype=str)
        validate_required_columns(sheet_df, sheet_name)
        all_rows.extend(parse_sheet_rows(year=year, sheet_df=sheet_df))

    detail_df = pd.DataFrame(all_rows)
    if detail_df.empty:
        return pd.DataFrame(
            columns=["年份", "供应商", "开单日期", "单据号", "品名规格", "品名清洗", "金额"]
        )

    detail_df["年份"] = detail_df["年份"].astype(int)
    detail_df["金额"] = detail_df["金额"].astype(float)
    return detail_df.sort_values(["年份", "供应商", "开单日期"]).reset_index(drop=True)
