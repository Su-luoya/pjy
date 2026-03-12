"""Command line entrypoint for local analysis/report export."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.analysis import build_analysis
from src.exports import write_csv_exports, write_excel_export
from src.io_parser import parse_excel_file
from src.reporting import generate_brief_pdf, generate_full_pdf


def _resolve_export_flags(args: argparse.Namespace) -> tuple[bool, bool, bool, bool]:
    explicit = args.brief or args.full or args.excel or args.csv
    if not explicit:
        return True, True, True, True
    return args.brief, args.full, args.excel, args.csv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="supplier-analysis", description="供应商分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser = subparsers.add_parser("report", help="读取 Excel 并导出报告与表格")
    report_parser.add_argument("--input", required=True, type=Path, help="输入 Excel 文件路径")
    report_parser.add_argument("--output", required=True, type=Path, help="输出目录")
    report_parser.add_argument("--brief", action="store_true", help="仅导出简报 PDF")
    report_parser.add_argument("--full", action="store_true", help="仅导出完整 PDF")
    report_parser.add_argument("--excel", action="store_true", help="导出 Excel")
    report_parser.add_argument("--csv", action="store_true", help="导出 CSV")

    return parser


def _run_report(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"输入文件不存在: {args.input}", file=sys.stderr)
        return 2

    detail_df = parse_excel_file(str(args.input))
    bundle = build_analysis(detail_df)

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    output_brief, output_full, output_excel, output_csv = _resolve_export_flags(args)
    written: list[Path] = []

    if output_brief:
        brief_path = output_dir / "供应商年度分析简报.pdf"
        brief_path.write_bytes(generate_brief_pdf(bundle))
        written.append(brief_path)

    if output_full:
        full_path = output_dir / "供应商年度分析完整报告.pdf"
        full_path.write_bytes(generate_full_pdf(bundle))
        written.append(full_path)

    if output_excel:
        written.append(write_excel_export(bundle, output_dir))

    if output_csv:
        written.extend(write_csv_exports(bundle, output_dir))

    print("导出完成：")
    for path in written:
        print(f"- {path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        return _run_report(args)

    parser.error(f"不支持的命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
