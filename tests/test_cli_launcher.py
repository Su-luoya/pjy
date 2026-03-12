from __future__ import annotations

import socket
from pathlib import Path

import pandas as pd
import pytest

from src.cli import main as cli_main
from src.launcher import find_available_port


def _build_sample_excel(path: Path) -> None:
    sheet = pd.DataFrame(
        [
            {
                "Unnamed: 0": "供应商 : 普通供应商A",
                "开单日期": "",
                "单据号": "",
                "品名规格": "",
                "金额": "",
            },
            {
                "Unnamed: 0": "",
                "开单日期": "2022-01-01",
                "单据号": "001",
                "品名规格": "项目A[20250102-21021212]",
                "金额": "100",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sheet.to_excel(writer, index=False, sheet_name="2022年")


def test_cli_default_exports_all_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_excel = tmp_path / "input.xlsx"
    output_dir = tmp_path / "outputs"
    _build_sample_excel(input_excel)

    monkeypatch.setattr("src.cli.generate_brief_pdf", lambda _bundle: b"%PDF-1.4\nbrief")
    monkeypatch.setattr("src.cli.generate_full_pdf", lambda _bundle: b"%PDF-1.4\nfull")

    result = cli_main(["report", "--input", str(input_excel), "--output", str(output_dir)])
    assert result == 0

    assert (output_dir / "供应商年度分析简报.pdf").exists()
    assert (output_dir / "供应商年度分析完整报告.pdf").exists()
    assert (output_dir / "供应商年度分析结果.xlsx").exists()
    assert (output_dir / "表A_供应商年度汇总.csv").exists()
    assert (output_dir / "表B_年度总览.csv").exists()
    assert (output_dir / "表C_年度金额环比_排除指定供应商.csv").exists()


def test_find_available_port_skips_occupied_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)

    try:
        occupied_port = sock.getsockname()[1]
        chosen_port = find_available_port(preferred_port=occupied_port, max_tries=10)
    finally:
        sock.close()

    assert chosen_port != occupied_port
    assert chosen_port > occupied_port
