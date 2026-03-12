"""Tabular export helpers shared by UI and CLI."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from src.analysis import AnalysisBundle


CSV_FILE_NAMES = {
    "table_a": "表A_供应商年度汇总.csv",
    "table_b": "表B_年度总览.csv",
    "table_c": "表C_年度金额环比.csv",
}


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def build_excel_download(table_a: pd.DataFrame, table_b: pd.DataFrame, table_c: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        table_a.to_excel(writer, index=False, sheet_name="供应商年度汇总")
        table_b.to_excel(writer, index=False, sheet_name="年度总览")
        table_c.to_excel(writer, index=False, sheet_name="年度金额环比")
    return output.getvalue()


def write_csv_exports(bundle: AnalysisBundle, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    mapping = {
        "table_a": bundle.table_a,
        "table_b": bundle.table_b,
        "table_c": bundle.table_c,
    }
    for key, table in mapping.items():
        destination = output_dir / CSV_FILE_NAMES[key]
        destination.write_bytes(to_csv_bytes(table))
        outputs.append(destination)
    return outputs


def write_excel_export(bundle: AnalysisBundle, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "供应商年度分析结果.xlsx"
    destination.write_bytes(build_excel_download(bundle.table_a, bundle.table_b, bundle.table_c))
    return destination
