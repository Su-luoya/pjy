"""PDF reporting and chart image export utilities."""

from __future__ import annotations

import datetime as dt
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.analysis import AnalysisBundle
from src.charts import create_annual_amount_chart, create_supplier_chart
from src.config import supplier_filter_description
from src.transform import supplier_options_for_charts

PRIMARY_COLOR = colors.HexColor("#0F4C81")
SECONDARY_COLOR = colors.HexColor("#2E86AB")
MUTED_TEXT = colors.HexColor("#4B5563")
BORDER_COLOR = colors.HexColor("#D1D5DB")
SURFACE_COLOR = colors.HexColor("#F6F9FC")

# The alias used by reportlab styles.
REPORT_FONT_NAME = "ReportSans"
PLOTLY_FONT_FAMILY = "Microsoft YaHei, PingFang SC, SimHei, Arial Unicode MS, Noto Sans CJK SC, sans-serif"

# (path, subfont_index)
FONT_CANDIDATES = [
    (Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf", 0),
    (Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansSC-Regular.otf", 0),
    (Path(__file__).resolve().parents[1] / "assets" / "fonts" / "NotoSansSC-Regular.ttf", 0),
    (Path("C:/Windows/Fonts/msyh.ttc"), 0),
    (Path("C:/Windows/Fonts/msyh.ttf"), 0),
    (Path("C:/Windows/Fonts/simhei.ttf"), 0),
    (Path("C:/Windows/Fonts/simsun.ttc"), 0),
    (Path("/System/Library/Fonts/Supplemental/Songti.ttc"), 0),
    (Path("/System/Library/Fonts/PingFang.ttc"), 0),
    (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 0),
]

INTEGER_COLUMNS = {"年份", "项目数", "供货品种"}
MONEY_COLUMNS = {"供货金额", "总金额", "累计供货金额"}
PERCENT_COLUMNS = {"项目数环比%", "金额环比%"}


def _register_font() -> str:
    if REPORT_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return REPORT_FONT_NAME

    for font_path, subfont_index in FONT_CANDIDATES:
        if not font_path.exists():
            continue
        try:
            pdfmetrics.registerFont(
                TTFont(REPORT_FONT_NAME, str(font_path), subfontIndex=subfont_index)
            )
            return REPORT_FONT_NAME
        except Exception:  # noqa: BLE001
            continue

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:  # noqa: BLE001
        return "Helvetica"


def _build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName=font_name,
            fontSize=29,
            leading=35,
            textColor=PRIMARY_COLOR,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=sample["Normal"],
            fontName=font_name,
            fontSize=12,
            leading=18,
            textColor=MUTED_TEXT,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "HeadingOne",
            parent=sample["Heading1"],
            fontName=font_name,
            fontSize=17,
            leading=22,
            textColor=PRIMARY_COLOR,
            spaceBefore=7,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "HeadingTwo",
            parent=sample["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=17,
            textColor=PRIMARY_COLOR,
            spaceBefore=6,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName=font_name,
            fontSize=10.5,
            leading=16,
            textColor=colors.black,
            spaceAfter=4,
        ),
        "muted": ParagraphStyle(
            "Muted",
            parent=sample["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=13,
            textColor=MUTED_TEXT,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=sample["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=12,
            textColor=MUTED_TEXT,
            spaceAfter=3,
        ),
    }


def _header_footer(font_name: str):
    def draw(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(MUTED_TEXT)
        canvas.drawString(doc.leftMargin, A4[1] - 14, "供应商年度分析报告")
        canvas.line(doc.leftMargin, A4[1] - 18, A4[0] - doc.rightMargin, A4[1] - 18)
        canvas.drawRightString(A4[0] - doc.rightMargin, 14, f"第 {doc.page} 页")
        canvas.restoreState()

    return draw


def _format_table_cell(column: str, value: object) -> str:
    if pd.isna(value):
        return "-"

    if column == "年份":
        try:
            return str(int(round(float(value))))
        except Exception:  # noqa: BLE001
            return str(value)

    if column in INTEGER_COLUMNS:
        try:
            return f"{int(round(float(value))):,d}"
        except Exception:  # noqa: BLE001
            return str(value)

    if column in MONEY_COLUMNS:
        try:
            return f"{float(value):,.2f}"
        except Exception:  # noqa: BLE001
            return str(value)

    if column in PERCENT_COLUMNS:
        try:
            return f"{float(value):.2f}%"
        except Exception:  # noqa: BLE001
            return str(value)

    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,d}"

    return str(value)


def _column_widths(columns: list[str], page_width: float) -> list[float]:
    # Semantic defaults first, then proportional shrink to fit page width.
    mapping = {
        "供应商": 4.9 * cm,
        "年份": 1.4 * cm,
        "项目数": 1.5 * cm,
        "供货金额": 2.5 * cm,
        "总金额": 2.7 * cm,
        "供货品种": 2.0 * cm,
        "项目数环比%": 2.1 * cm,
        "金额环比%": 2.1 * cm,
    }
    fallback = 2.2 * cm
    widths = [mapping.get(column, fallback) for column in columns]

    total_width = sum(widths)
    if total_width > page_width:
        scale = page_width / total_width
        widths = [max(width * scale, 1.25 * cm) for width in widths]

    return widths


def _numeric_column_indexes(columns: list[str]) -> list[int]:
    targets = INTEGER_COLUMNS | MONEY_COLUMNS | PERCENT_COLUMNS
    indexes: list[int] = []
    for index, column in enumerate(columns):
        if column in targets:
            indexes.append(index)
    return indexes


def _build_table_flowables(
    df: pd.DataFrame,
    title: str,
    styles: dict[str, ParagraphStyle],
    font_name: str,
    *,
    rows_per_chunk: int = 30,
) -> list:
    if df.empty:
        return [
            Paragraph(title, styles["h2"]),
            Paragraph("无可展示数据。", styles["muted"]),
            Spacer(1, 0.35 * cm),
        ]

    table_df = df.copy().reset_index(drop=True)
    columns = table_df.columns.tolist()
    page_width = A4[0] - 2 * 1.8 * cm
    widths = _column_widths(columns, page_width)
    numeric_columns = _numeric_column_indexes(columns)

    flowables: list = [Paragraph(title, styles["h2"])]

    chunk_count = (len(table_df) + rows_per_chunk - 1) // rows_per_chunk
    for chunk_index in range(chunk_count):
        start = chunk_index * rows_per_chunk
        end = start + rows_per_chunk
        chunk_df = table_df.iloc[start:end]

        if chunk_index > 0:
            flowables.append(Paragraph(f"{title}（续 {chunk_index + 1}）", styles["small"]))

        rows = [[str(column) for column in columns]]
        for _, record in chunk_df.iterrows():
            rows.append(
                [
                    _format_table_cell(columns[idx], value)
                    for idx, value in enumerate(record.tolist())
                ]
            )

        report_table = Table(rows, colWidths=widths, repeatRows=1)
        table_style = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8.2),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
            ("GRID", (0, 0), (-1, -1), 0.25, BORDER_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

        for body_row in range(1, len(rows)):
            if body_row % 2 == 0:
                table_style.append(("BACKGROUND", (0, body_row), (-1, body_row), SURFACE_COLOR))

        for column_index in numeric_columns:
            table_style.append(("ALIGN", (column_index, 1), (column_index, -1), "RIGHT"))

        report_table.setStyle(TableStyle(table_style))
        flowables.append(report_table)
        flowables.append(Spacer(1, 0.24 * cm))

        if chunk_index < chunk_count - 1:
            flowables.append(PageBreak())

    return flowables


def _image_flowable(image_bytes: bytes, max_width_cm: float = 16.8, max_height_cm: float = 9.2) -> Image:
    image = Image(BytesIO(image_bytes))
    image._restrictSize(max_width_cm * cm, max_height_cm * cm)  # noqa: SLF001
    return image


def _style_chart_for_pdf(figure) -> None:  # type: ignore[no-untyped-def]
    figure.update_layout(
        template="plotly_white",
        font={"family": PLOTLY_FONT_FAMILY, "size": 19, "color": "#1F2937"},
        title={"x": 0, "xanchor": "left", "font": {"size": 24}},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0, "font": {"size": 14}},
        margin={"l": 80, "r": 80, "t": 120, "b": 80},
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    figure.update_xaxes(
        tickfont={"size": 13},
        title_font={"size": 14},
        showgrid=False,
    )
    figure.update_yaxes(
        tickfont={"size": 13},
        title_font={"size": 14},
        gridcolor="#E5E7EB",
        zerolinecolor="#CBD5E1",
    )


def _figure_to_png_bytes(figure) -> bytes:  # type: ignore[no-untyped-def]
    _style_chart_for_pdf(figure)
    try:
        return figure.to_image(format="png", width=1700, height=980, scale=2)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "图表导出失败。请确认已安装 kaleido，且当前环境支持图像导出。"
        ) from exc


def export_chart_pngs(
    bundle: AnalysisBundle,
    *,
    include_supplier_charts: bool = True,
) -> dict[str, bytes]:
    """Export annual and supplier charts as PNG images."""
    images: dict[str, bytes] = {}
    images["annual_amount_yoy"] = _figure_to_png_bytes(
        create_annual_amount_chart(bundle.table_c)
    )

    if include_supplier_charts:
        supplier_names = supplier_options_for_charts(bundle.table_a)
        for index, supplier in enumerate(supplier_names, start=1):
            supplier_chart = create_supplier_chart(
                supplier_year_df=bundle.table_a,
                supplier_name=supplier,
                metric_col="供货金额",
                yoy_col="金额环比%",
                metric_label="供货金额",
            )
            images[f"supplier_{index:04d}"] = _figure_to_png_bytes(supplier_chart)

    return images


def _insights(bundle: AnalysisBundle) -> list[str]:
    if bundle.detail.empty:
        return ["当前数据为空，未生成有效统计结论。"]

    lines: list[str] = []
    years = sorted(bundle.detail["年份"].dropna().astype(int).unique().tolist())
    lines.append(f"数据覆盖 {years[0]} 年至 {years[-1]} 年，共 {len(years)} 个年份。")

    supplier_totals = (
        bundle.table_a.groupby("供应商", as_index=False)
        .agg(累计供货金额=("供货金额", "sum"))
        .sort_values("累计供货金额", ascending=False)
    )
    if not supplier_totals.empty:
        top = supplier_totals.iloc[0]
        lines.append(
            f"累计供货金额最高供应商为 {top['供应商']}，累计金额 {top['累计供货金额']:,.2f}。"
        )

    if not bundle.table_c.empty:
        latest = bundle.table_c.sort_values("年份").iloc[-1]
        yoy = latest["金额环比%"]
        if pd.isna(yoy):
            lines.append(f"{int(latest['年份'])} 年环比为空（上一年基数为 0 或缺失）。")
        elif yoy >= 0:
            lines.append(f"{int(latest['年份'])} 年金额环比增长 {float(yoy):.2f}%。")
        else:
            lines.append(f"{int(latest['年份'])} 年金额环比下降 {abs(float(yoy)):.2f}%。")

    return lines


def _kpi_table(bundle: AnalysisBundle, font_name: str) -> Table:
    total_amount = 0.0
    if not bundle.table_b.empty and "总金额" in bundle.table_b.columns:
        total_amount = float(bundle.table_b["总金额"].sum())

    rows = [
        ["有效明细行", f"{bundle.row_count:,d}", "供应商数量", f"{bundle.supplier_count:,d}"],
        ["年份数量", f"{bundle.year_count:,d}", "累计总金额", f"{total_amount:,.2f}"],
    ]
    table = Table(rows, colWidths=[3.2 * cm, 4.7 * cm, 3.2 * cm, 5.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_COLOR),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER_COLOR),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_cover(
    story: list,
    styles: dict[str, ParagraphStyle],
    report_title: str,
    *,
    full: bool,
) -> None:
    now_text = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    story.extend(
        [
            Spacer(1, 2.8 * cm),
            Paragraph(report_title, styles["title"]),
            Paragraph("供应商年度分析报告", styles["subtitle"]),
            Paragraph("模板：通用专业版（后续可叠加品牌元素）", styles["subtitle"]),
            Spacer(1, 0.9 * cm),
            Paragraph(f"生成时间：{now_text}", styles["muted"]),
            Spacer(1, 2.2 * cm),
            Paragraph("目录", styles["h1"]),
            Paragraph("1. 核心 KPI", styles["body"]),
            Paragraph("2. 年度趋势图", styles["body"]),
            Paragraph("3. 自动摘要结论", styles["body"]),
        ]
    )

    if full:
        story.append(Paragraph("4. 年度明细与供应商结构", styles["body"]))
        story.append(Paragraph("5. 供应商分节分析", styles["body"]))


def _build_common_sections(
    story: list,
    bundle: AnalysisBundle,
    styles: dict[str, ParagraphStyle],
    font_name: str,
    chart_images: dict[str, bytes],
) -> None:
    story.append(PageBreak())
    story.append(Paragraph("核心 KPI", styles["h1"]))
    story.append(_kpi_table(bundle, font_name))
    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph("年度趋势图", styles["h1"]))
    annual_img = chart_images.get("annual_amount_yoy")
    if annual_img is not None:
        story.append(_image_flowable(annual_img))
    else:
        story.append(Paragraph("年度趋势图生成失败。", styles["muted"]))
    story.append(Spacer(1, 0.22 * cm))

    story.append(Paragraph("关键结论（自动摘要）", styles["h1"]))
    for item in _insights(bundle):
        story.append(Paragraph(f"• {item}", styles["body"]))
    story.append(Spacer(1, 0.25 * cm))


def _build_full_sections(
    story: list,
    bundle: AnalysisBundle,
    styles: dict[str, ParagraphStyle],
    font_name: str,
    chart_images: dict[str, bytes],
) -> None:
    story.append(PageBreak())
    story.append(Paragraph("年度明细与供应商结构", styles["h1"]))
    filter_description = supplier_filter_description()
    story.extend(
        _build_table_flowables(bundle.table_b, "年度总览（表 B）", styles, font_name, rows_per_chunk=26)
    )
    story.extend(
        _build_table_flowables(
            bundle.table_c,
            f"年度金额环比（表 C，{filter_description}）",
            styles,
            font_name,
            rows_per_chunk=26,
        )
    )

    supplier_total = (
        bundle.table_a.groupby("供应商", as_index=False)
        .agg(累计供货金额=("供货金额", "sum"), 累计项目数=("项目数", "sum"))
        .sort_values("累计供货金额", ascending=False)
        .head(20)
        .reset_index(drop=True)
    )
    story.extend(
        _build_table_flowables(
            supplier_total,
            "供应商累计供货金额 Top 20",
            styles,
            font_name,
            rows_per_chunk=20,
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("供应商分节分析", styles["h1"]))

    supplier_names = supplier_options_for_charts(bundle.table_a)
    if not supplier_names:
        story.append(Paragraph(f"无可展示供应商（图表口径：{filter_description}）。", styles["muted"]))
        return

    for index, supplier in enumerate(supplier_names, start=1):
        story.append(Paragraph(f"{supplier}", styles["h2"]))
        image_key = f"supplier_{index:04d}"
        supplier_img = chart_images.get(image_key)
        if supplier_img is not None:
            story.append(_image_flowable(supplier_img, max_width_cm=16.0, max_height_cm=8.0))
            story.append(Spacer(1, 0.12 * cm))
        else:
            story.append(Paragraph("该供应商图表生成失败。", styles["muted"]))

        supplier_df = (
            bundle.table_a.loc[bundle.table_a["供应商"] == supplier]
            .sort_values("年份")
            .reset_index(drop=True)
        )
        story.extend(
            _build_table_flowables(
                supplier_df,
                f"{supplier} 年度明细",
                styles,
                font_name,
                rows_per_chunk=18,
            )
        )

        if index != len(supplier_names):
            story.append(PageBreak())


def _render_pdf(bundle: AnalysisBundle, full: bool) -> bytes:
    font_name = _register_font()
    styles = _build_styles(font_name)
    chart_images = export_chart_pngs(bundle, include_supplier_charts=full)

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.9 * cm,
        bottomMargin=1.55 * cm,
        title="供应商年度分析报告",
        author="supplier-analysis",
    )

    story: list = []
    title = "供应商年度分析完整报告" if full else "供应商年度分析简报"
    _build_cover(story, styles, title, full=full)
    _build_common_sections(story, bundle, styles, font_name, chart_images)
    if full:
        _build_full_sections(story, bundle, styles, font_name, chart_images)

    draw_header = _header_footer(font_name)
    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header)
    return output.getvalue()


def generate_brief_pdf(bundle: AnalysisBundle) -> bytes:
    """Generate concise briefing report PDF."""
    return _render_pdf(bundle, full=False)


def generate_full_pdf(bundle: AnalysisBundle) -> bytes:
    """Generate full report PDF including table and supplier sections."""
    return _render_pdf(bundle, full=True)
