"""Plotly chart builders for supplier and annual analysis views."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_metric_with_yoy_chart(
    df: pd.DataFrame,
    x_col: str,
    metric_col: str,
    yoy_col: str,
    title: str,
    metric_label: str,
) -> go.Figure:
    """Create a bar + line combo chart with secondary axis for YoY."""
    figure = make_subplots(specs=[[{"secondary_y": True}]])

    figure.add_trace(
        go.Bar(
            x=df[x_col],
            y=df[metric_col],
            name=metric_label,
            marker_color="#2E86AB",
        ),
        secondary_y=False,
    )

    figure.add_trace(
        go.Scatter(
            x=df[x_col],
            y=df[yoy_col],
            mode="lines+markers",
            name="环比%",
            line={"color": "#E07A5F", "width": 3},
            marker={"size": 8},
        ),
        secondary_y=True,
    )

    figure.update_layout(
        title={"text": title, "x": 0, "xanchor": "left"},
        template="plotly_white",
        font={
            "family": "Microsoft YaHei, PingFang SC, SimHei, Arial Unicode MS, sans-serif",
            "size": 13,
            "color": "#1F2937",
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"size": 12}},
        margin={"l": 30, "r": 24, "t": 68, "b": 28},
        bargap=0.22,
    )
    figure.update_xaxes(showgrid=False, tickfont={"size": 11})
    figure.update_yaxes(
        title_text=metric_label,
        secondary_y=False,
        tickfont={"size": 11},
        gridcolor="#E5E7EB",
    )
    figure.update_yaxes(
        title_text="环比%",
        ticksuffix="%",
        secondary_y=True,
        tickfont={"size": 11},
        gridcolor="#E5E7EB",
    )
    return figure


def create_supplier_chart(
    supplier_year_df: pd.DataFrame,
    supplier_name: str,
    metric_col: str,
    yoy_col: str,
    metric_label: str,
) -> go.Figure:
    """Build supplier-specific chart from summary table."""
    supplier_df = (
        supplier_year_df.loc[supplier_year_df["供应商"] == supplier_name]
        .sort_values("年份")
        .reset_index(drop=True)
    )
    return create_metric_with_yoy_chart(
        df=supplier_df,
        x_col="年份",
        metric_col=metric_col,
        yoy_col=yoy_col,
        title=f"{supplier_name} 年度{metric_label}与环比",
        metric_label=metric_label,
    )


def create_annual_amount_chart(annual_amount_yoy_df: pd.DataFrame) -> go.Figure:
    """Build annual amount + YoY chart for filtered dataset."""
    annual_df = annual_amount_yoy_df.sort_values("年份").reset_index(drop=True)
    return create_metric_with_yoy_chart(
        df=annual_df,
        x_col="年份",
        metric_col="总金额",
        yoy_col="金额环比%",
        title="年度供货金额与环比（已排除指定供应商）",
        metric_label="总金额",
    )
