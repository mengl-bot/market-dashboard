"""Streamlit renderer for the historical PE vs index map."""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.historical_valuation import HistoricalValuationMap
from ui.formatters import delta_class, fmt_number, fmt_pct, fmt_plain_pct


def render_historical_valuation_map(model: HistoricalValuationMap) -> None:
    """Render the PE vs S&P 500 historical valuation module."""

    st.markdown('<div class="layer-title">历史估值地图 PE vs Index</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="valuation-map-copy">指数点位本身无意义，需结合盈利与估值判断。'
        "同样的 5,000 点，在盈利上修且 PE 合理时是健康上涨；在盈利停滞且 PE 高估时，回撤风险会更高。</div>",
        unsafe_allow_html=True,
    )

    horizon = st.radio("观察周期", ["5Y", "10Y"], horizontal=True, index=0, key="historical_pe_horizon")
    _render_state_cards(model)
    _render_chart(model, horizon)
    _render_breakdown(model)
    st.caption(model.source_note)


def _render_state_cards(model: HistoricalValuationMap) -> None:
    cards = [
        ("当前PE", fmt_number(model.current_pe, 2), "Forward PE"),
        ("历史分位", fmt_plain_pct(model.historical_percentile, 2), "相对当前样本"),
        ("估值标签", model.valuation_label, _label_note(model.valuation_label)),
    ]
    cols = st.columns(3)
    for col, (title, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="card valuation-map-card valuation-label-{_label_class(model.valuation_label)}">
                    <div class="card-title">{html.escape(title)}</div>
                    <div class="valuation-map-value">{html.escape(value)}</div>
                    <div class="card-note">{html.escape(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_chart(model: HistoricalValuationMap, horizon: str) -> None:
    frame = _filter_horizon(model.history, horizon)
    if frame.empty:
        st.info("暂无足够历史数据绘制 PE vs Index。")
        return

    fig = go.Figure()
    pe_min = max(10.0, float(frame["forward_pe"].min()) - 1.5)
    pe_max = max(28.0, float(frame["forward_pe"].max()) + 1.5)
    _add_pe_background(fig, pe_min, pe_max)

    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["index"],
            mode="lines",
            name="S&P 500 指数",
            line={"width": 2.2, "color": "#7dd3fc"},
            hovertemplate="%{x|%Y-%m-%d}<br>S&P 500: %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["forward_pe"],
            mode="lines",
            name="Forward PE",
            yaxis="y2",
            line={"width": 2.1, "color": "#fbbf24"},
            hovertemplate="%{x|%Y-%m-%d}<br>Forward PE: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=430,
        margin={"l": 8, "r": 8, "t": 24, "b": 8},
        paper_bgcolor="#05070b",
        plot_bgcolor="#090f17",
        font={"color": "#d8e1ec"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"gridcolor": "#182233"},
        yaxis={"title": "S&P 500 指数点位", "gridcolor": "#182233"},
        yaxis2={
            "title": "Forward PE",
            "overlaying": "y",
            "side": "right",
            "range": [pe_min, pe_max],
            "gridcolor": "#182233",
            "showgrid": False,
        },
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        """
        <div class="pe-legend">
            <span class="pe-low">PE &lt; 16 低估</span>
            <span class="pe-fair">16-20 合理</span>
            <span class="pe-rich">20-24 偏贵</span>
            <span class="pe-high">PE &gt; 24 高估</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_breakdown(model: HistoricalValuationMap) -> None:
    breakdown = model.breakdown
    items = [
        ("盈利贡献", breakdown.earnings_contribution_pct, "EPS 上修带来的价格支撑"),
        ("估值扩张", breakdown.valuation_expansion_pct, "PE 上升或下降带来的重估"),
        ("股息贡献", breakdown.dividend_contribution_pct, "按年度股息率估算的 6 个月贡献"),
    ]
    st.markdown('<div class="valuation-map-subtitle">收益来源拆解（近6个月）</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (title, value, note) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{html.escape(title)}</div>
                    <div class="macro-value {delta_class(value)}">{fmt_pct(value, 2)}</div>
                    <div class="card-note">{html.escape(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown(
        f'<div class="valuation-map-total">近6个月指数价格回报：'
        f'<strong>{fmt_pct(breakdown.total_price_return_pct, 2)}</strong></div>',
        unsafe_allow_html=True,
    )


def _filter_horizon(frame, horizon: str):
    if frame.empty:
        return frame
    years = 10 if horizon == "10Y" else 5
    cutoff = frame["date"].max() - pd.DateOffset(years=years)
    return frame[frame["date"] >= cutoff]


def _add_pe_background(fig: go.Figure, pe_min: float, pe_max: float) -> None:
    bands = [
        (pe_min, min(16, pe_max), "rgba(50, 213, 131, 0.10)"),
        (max(16, pe_min), min(20, pe_max), "rgba(125, 211, 252, 0.10)"),
        (max(20, pe_min), min(24, pe_max), "rgba(251, 191, 36, 0.12)"),
        (max(24, pe_min), pe_max, "rgba(255, 95, 87, 0.12)"),
    ]
    for y0, y1, color in bands:
        if y1 <= y0:
            continue
        fig.add_hrect(y0=y0, y1=y1, yref="y2", line_width=0, fillcolor=color, layer="below")


def _label_class(label: str) -> str:
    return {"低估": "low", "合理": "fair", "偏贵": "rich", "高估": "high"}.get(label, "fair")


def _label_note(label: str) -> str:
    return {
        "低估": "PE < 16",
        "合理": "16 <= PE < 20",
        "偏贵": "20 <= PE < 24",
        "高估": "PE >= 24",
    }.get(label, "数据不足")
