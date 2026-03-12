"""Streamlit app UI."""

from __future__ import annotations

import hashlib
from io import BytesIO

import streamlit as st

from src.analysis import build_analysis
from src.charts import create_annual_amount_chart, create_supplier_chart
from src.config import EXCLUDED_SUPPLIER_KEYWORDS
from src.exports import build_excel_download, to_csv_bytes
from src.io_parser import parse_excel_file
from src.reporting import generate_brief_pdf, generate_full_pdf
from src.transform import supplier_options_for_charts


st.set_page_config(page_title="供应商年度分析", page_icon="📊", layout="wide")


@st.cache_data(show_spinner=False)
def _parse_and_analyze(uploaded_bytes: bytes):
    detail_df = parse_excel_file(BytesIO(uploaded_bytes))
    return build_analysis(detail_df)


def _dataframe_config() -> dict[str, st.column_config.Column]:
    return {
        "项目数": st.column_config.NumberColumn("项目数", format="%d"),
        "供货金额": st.column_config.NumberColumn("供货金额", format="%.2f"),
        "总金额": st.column_config.NumberColumn("总金额", format="%.2f"),
        "项目数环比%": st.column_config.NumberColumn("项目数环比%", format="%.2f%%"),
        "金额环比%": st.column_config.NumberColumn("金额环比%", format="%.2f%%"),
        "年份": st.column_config.NumberColumn("年份", format="%d"),
        "供货品种": st.column_config.NumberColumn("供货品种", format="%d"),
    }


def _ensure_pdf_cache(key: str, bundle) -> None:  # type: ignore[no-untyped-def]
    if st.session_state.get("pdf_key") == key:
        return

    try:
        with st.spinner("正在生成 PDF 报告，请稍候..."):
            st.session_state["pdf_brief"] = generate_brief_pdf(bundle)
            st.session_state["pdf_full"] = generate_full_pdf(bundle)
            st.session_state["pdf_error"] = None
            st.session_state["pdf_key"] = key
    except Exception as exc:  # noqa: BLE001
        st.session_state["pdf_brief"] = None
        st.session_state["pdf_full"] = None
        st.session_state["pdf_error"] = str(exc)
        st.session_state["pdf_key"] = key


def run() -> None:
    st.title("供应商年度分析本地系统")
    st.caption("上传与原始模板同格式的 Excel 文件，自动生成汇总、环比和图表。")

    uploaded_file = st.file_uploader("上传 Excel 文件（.xlsx）", type=["xlsx"])

    if uploaded_file is None:
        st.info("请先上传文件。")
        return

    file_bytes = uploaded_file.getvalue()
    file_key = hashlib.md5(file_bytes).hexdigest()  # noqa: S324

    try:
        with st.spinner("正在处理数据，请稍候..."):
            bundle = _parse_and_analyze(file_bytes)
    except ValueError as exc:
        st.error(f"处理失败：{exc}")
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"处理失败：{exc}")
        return

    if bundle.detail.empty:
        st.warning("未识别到可用明细数据，请检查文件格式是否与模板一致。")
        return

    _ensure_pdf_cache(file_key, bundle)

    st.success("处理完成。")

    col1, col2, col3 = st.columns(3)
    col1.metric("有效明细行", f"{bundle.row_count:,}")
    col2.metric("供应商数量", f"{bundle.supplier_count:,}")
    col3.metric("年份数量", f"{bundle.year_count:,}")

    st.subheader("表 A：供应商-年份项目数/供货金额汇总 + 环比")
    st.dataframe(bundle.table_a, use_container_width=True, column_config=_dataframe_config())

    st.download_button(
        "下载表 A（CSV）",
        data=to_csv_bytes(bundle.table_a),
        file_name="表A_供应商年度汇总.csv",
        mime="text/csv",
    )

    st.caption(
        "图表和年度金额环比已排除供应商关键词："
        + "、".join(EXCLUDED_SUPPLIER_KEYWORDS)
        + "。"
    )

    st.subheader("供应商图表（仅展示非排除供应商）")
    options = supplier_options_for_charts(bundle.table_a)
    if not options:
        st.info("无可展示的供应商图表数据。")
    else:
        supplier_col, metric_col = st.columns(2)
        selected_supplier = supplier_col.selectbox("选择供应商", options=options)

        metric_option = metric_col.selectbox("柱状图指标", options=["供货金额", "项目数"], index=0)
        if metric_option == "供货金额":
            figure = create_supplier_chart(
                supplier_year_df=bundle.table_a,
                supplier_name=selected_supplier,
                metric_col="供货金额",
                yoy_col="金额环比%",
                metric_label="供货金额",
            )
        else:
            figure = create_supplier_chart(
                supplier_year_df=bundle.table_a,
                supplier_name=selected_supplier,
                metric_col="项目数",
                yoy_col="项目数环比%",
                metric_label="项目数",
            )

        st.plotly_chart(figure, use_container_width=True)

    st.subheader("表 B：年度项目数/供货品种/总金额汇总")
    st.dataframe(bundle.table_b, use_container_width=True, column_config=_dataframe_config())
    st.download_button(
        "下载表 B（CSV）",
        data=to_csv_bytes(bundle.table_b),
        file_name="表B_年度总览.csv",
        mime="text/csv",
    )

    st.subheader("表 C：年度供货金额环比（排除指定供应商）")
    st.dataframe(bundle.table_c, use_container_width=True, column_config=_dataframe_config())
    st.download_button(
        "下载表 C（CSV）",
        data=to_csv_bytes(bundle.table_c),
        file_name="表C_年度金额环比_排除指定供应商.csv",
        mime="text/csv",
    )

    annual_chart = create_annual_amount_chart(bundle.table_c)
    st.plotly_chart(annual_chart, use_container_width=True)

    pdf_error = st.session_state.get("pdf_error")
    if pdf_error:
        st.warning(f"PDF 生成失败：{pdf_error}")
    else:
        pdf_col1, pdf_col2 = st.columns(2)
        pdf_col1.download_button(
            "下载简报 PDF",
            data=st.session_state["pdf_brief"],
            file_name="供应商年度分析简报.pdf",
            mime="application/pdf",
        )
        pdf_col2.download_button(
            "下载完整 PDF",
            data=st.session_state["pdf_full"],
            file_name="供应商年度分析完整报告.pdf",
            mime="application/pdf",
        )

    excel_bytes = build_excel_download(bundle.table_a, bundle.table_b, bundle.table_c)
    st.download_button(
        "下载全部结果（Excel）",
        data=excel_bytes,
        file_name="供应商年度分析结果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    run()
