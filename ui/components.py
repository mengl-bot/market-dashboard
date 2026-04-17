"""Reusable Streamlit UI components."""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_repository.repository import DebugRow
from providers.base import IndexDataset
from services.analytics import IndexMetrics, MarketAnalytics, filter_history
from ui.formatters import delta_class, fmt_number, fmt_pct, fmt_plain_pct, fmt_volume


def render_terminal_status_bar(analytics: MarketAnalytics, source_name: str, is_mock: bool) -> None:
    """Render Bloomberg-like top status bar."""

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")
    live_text = "模拟数据（MOCK）" if is_mock else "实时数据（LIVE）"
    live_class = "terminal-chip warn" if is_mock else "terminal-chip live"
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    breadth = analytics.breadth
    breadth_text = f"龙头宽度（M7 A/D）{breadth.advances}/{breadth.declines}"
    risk_class = "risk-off" if "Risk OFF" in analytics.decision.risk_mode else "risk-on"

    st.markdown(
        f"""
        <div class="terminal-topbar">
            <div class="terminal-brand">
                <span class="terminal-title">美股指数专业看板 V3</span>
                <span class="terminal-subtitle">{source_name}</span>
            </div>
            <div class="terminal-strip">
                <span class="terminal-chip">{now_et}</span>
                <span class="{live_class}">{live_text}</span>
                <span class="terminal-chip {risk_class}">{analytics.decision.risk_mode}</span>
                <span class="terminal-chip">VIX {fmt_number(vix.current if vix else None, 2)} / {fmt_pct(vix.day_change_pct if vix else None)}</span>
                <span class="terminal-chip">10年美债 {fmt_number(us10y.current if us10y else None, 2)}%</span>
                <span class="terminal-chip">{breadth_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(metrics: dict[str, IndexMetrics]) -> None:
    """Render top index metric cards."""

    cols = st.columns(2)
    for col, key in zip(cols, ["nasdaq", "sp500"]):
        metric = metrics.get(key)
        if not metric:
            continue
        returns_html = "".join(
            f'<span class="return-pill">{label} {fmt_pct(value)}</span>'
            for label, value in metric.returns.items()
        )
        delta_html = f"{fmt_number(metric.day_change)} / {fmt_pct(metric.day_change_pct)}"
        with col:
            st.markdown(
                f"""
                <div class="card index-card">
                    <div class="card-title">{metric.name}</div>
                    <div class="metric-value">{fmt_number(metric.current)}</div>
                    <div class="{delta_class(metric.day_change)}">{delta_html}</div>
                    <div class="return-row">{returns_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_macro_strip(metrics: dict[str, IndexMetrics]) -> None:
    """Render VIX and US yield cards."""

    us10y = metrics.get("us10y")
    us2y = metrics.get("us2y")
    spread = None
    if us2y and us10y and us2y.current is not None and us10y.current is not None:
        spread = us2y.current - us10y.current

    items = [
        ("VIX", metrics.get("vix").current if metrics.get("vix") else None, metrics.get("vix").day_change_pct if metrics.get("vix") else None, ""),
        ("US 10Y", us10y.current if us10y else None, us10y.day_change if us10y else None, "%"),
        ("US 2Y", us2y.current if us2y else None, us2y.day_change if us2y else None, "%"),
        ("2Y-10Y", spread, None, "bp"),
    ]

    cols = st.columns(4)
    for col, (title, value, delta, unit) in zip(cols, items):
        value_text = f"{fmt_number(value, 2)}%" if unit == "%" else f"{fmt_number(value * 100, 0)} bp" if value is not None and unit == "bp" else fmt_number(value, 2)
        delta_text = fmt_pct(delta) if title == "VIX" else fmt_number(delta, 2)
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{title}</div>
                    <div class="macro-value">{value_text}</div>
                    <div class="{delta_class(delta)}">{delta_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_price_chart(
    datasets: dict[str, IndexDataset],
    period: str,
    mode: str,
    chart_style: str,
    show_drawdown: bool,
) -> None:
    """Render the dual-index Plotly chart with crosshair, markers, and drawdown."""

    fig = go.Figure()
    normalized = mode == "归一化对比（起点=100）"
    use_area = chart_style == "面积图"
    prepared = _prepare_index_chart_data(datasets, period, normalized)

    for name, frame in prepared.items():
        if frame.empty:
            continue
        fill = "tozeroy" if use_area else None
        fig.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame["y"],
                mode="lines",
                name=name,
                customdata=frame[["close_text", "pct_text", "volume_text", "range_text", "spread_text"]],
                hovertemplate=(
                    "%{x|%Y-%m-%d}<br>"
                    f"{name}<br>"
                    "收盘: %{customdata[0]}<br>"
                    "区间涨跌: %{customdata[1]}<br>"
                    "双指数差: %{customdata[4]}<br>"
                    "成交量: %{customdata[2]}<br>"
                    "日内振幅: %{customdata[3]}<extra></extra>"
                ),
                line={"width": 2.2},
                fill=fill,
                fillcolor="rgba(56, 189, 248, 0.10)" if "NASDAQ" in name else "rgba(245, 158, 11, 0.10)",
            )
        )
        _add_recent_high_low_markers(fig, name, frame)

        if show_drawdown:
            drawdown = (frame["close"] / frame["close"].cummax() - 1) * 100
            fig.add_trace(
                go.Scatter(
                    x=frame["date"],
                    y=drawdown,
                    mode="lines",
                    name=f"{name} 回撤",
                    yaxis="y2",
                    line={"width": 0.8, "color": "rgba(255, 95, 87, 0.35)"},
                    fill="tozeroy",
                    fillcolor="rgba(255, 95, 87, 0.10)",
                    hovertemplate="%{x|%Y-%m-%d}<br>回撤: %{y:.2f}%<extra></extra>",
                )
            )

    fig.update_layout(
        height=480,
        margin={"l": 8, "r": 8, "t": 24, "b": 8},
        paper_bgcolor="#05070b",
        plot_bgcolor="#090f17",
        font={"color": "#d8e1ec"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={
            "gridcolor": "#182233",
            "showspikes": True,
            "spikemode": "across",
            "spikesnap": "cursor",
            "spikethickness": 1,
            "spikecolor": "#94a3b8",
        },
        yaxis={
            "gridcolor": "#182233",
            "title": "归一化指数" if normalized else "指数点位",
            "showspikes": True,
            "spikemode": "across",
            "spikecolor": "#94a3b8",
        },
        yaxis2={
            "overlaying": "y",
            "side": "right",
            "range": [-35, 5],
            "showgrid": False,
            "title": "回撤%",
            "visible": show_drawdown,
        },
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_mega_cap_section_legacy(metrics: dict[str, IndexMetrics], average: float | None) -> None:
    """Render Magnificent Seven heatmap table."""

    st.markdown(
        f"""
        <div class="section-kpi">
            <span>M7 AVERAGE</span>
            <strong class="{delta_class(average)}">{fmt_pct(average)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = sorted(metrics.values(), key=lambda metric: metric.strength_rank or 99)
    html = ['<div class="heatmap-grid">']
    for metric in rows:
        heat_class = _heat_class(metric.day_change_pct)
        html.append(
            f"""
            <div class="heat-cell {heat_class}">
                <div class="heat-rank">#{metric.strength_rank or '-'}</div>
                <div class="heat-ticker">{metric.name}</div>
                <div class="heat-change">{fmt_pct(metric.day_change_pct)}</div>
                <div class="heat-meta">WGT {fmt_plain_pct(metric.weight)} · CONTR {fmt_pct(metric.contribution)}</div>
            </div>
            """
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Render market breadth cards."""

    breadth = analytics.breadth
    leadership_items = [
        ("M7 A/D", f"{breadth.advances} / {breadth.declines}", "龙头宽度", "衡量七巨头内部上涨与下跌家数。"),
        ("M7 NH/NL", f"{breadth.new_highs} / {breadth.new_lows}", "52W extremes", "观察龙头股是否接近一年高低位。"),
        ("Equal Wgt", fmt_pct(breadth.equal_weight_return), "RSP", "等权指数更能反映普通成分股表现。"),
        ("Cap Wgt", fmt_pct(breadth.cap_weight_return), "SPY", "市值加权指数更受大型权重股影响。"),
        ("EW-CW", fmt_pct(breadth.equal_vs_cap_spread), "spread", "正值说明行情扩散，负值说明权重股主导。"),
    ]

    st.markdown(
        '<div class="breadth-caption">龙头宽度：M7 A/D 反映七巨头（Mega Cap Leaders）内部上涨/下跌家数的广度情况，不代表整个市场宽度。</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for col, (title, value, note, explanation) in zip(cols, leadership_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Final breadth renderer with transparent data-source badges."""

    breadth = analytics.breadth
    m7_state = _aggregate_status([metric.data_state for metric in analytics.mega_cap_metrics.values()])
    equal_state = _aggregate_status(
        [
            analytics.metrics.get("equal_weight").data_state if analytics.metrics.get("equal_weight") else None,
            analytics.metrics.get("cap_weight").data_state if analytics.metrics.get("cap_weight") else None,
        ]
    )
    leadership_items = [
        ("龙头宽度（M7 A/D）", f"上涨{breadth.advances} / 下跌{breadth.declines} / 持平{breadth.unchanged}", "七巨头内部结构", "仅衡量七巨头内部涨跌分布，不代表全市场宽度。", m7_state),
        ("龙头新高/新低（M7 NH/NL）", f"{breadth.new_highs} / {breadth.new_lows}", "52周位置", "观察龙头股是否接近52周高位或低位，用于判断领导力质量。", m7_state),
        ("等权表现（Equal Weight）", fmt_pct(breadth.equal_weight_return), "RSP", "等权指数更能反映普通成分股表现，弱于市值加权时说明上涨较集中。", equal_state),
        ("市值加权表现（Cap Weight）", fmt_pct(breadth.cap_weight_return), "SPY", "市值加权指数受大型权重股影响更大，用于观察龙头拉动强度。", equal_state),
        ("等权-市值差（EW-CW）", fmt_pct(breadth.equal_vs_cap_spread), "扩散/集中", "差值为正说明上涨扩散更好，差值为负说明权重股主导更强。", equal_state),
    ]

    st.markdown(
        '<div class="breadth-caption">龙头宽度：M7 A/D 反映七巨头（Mega Cap Leaders）内部上涨/下跌家数的广度情况，不代表整个市场宽度。</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for col, (title, value, note, explanation, state) in zip(cols, leadership_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {_status_badge(state)}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    market_items = [
        (
            "标普500涨跌比",
            _fmt_full_ad(breadth.sp500_advances, breadth.sp500_declines, breadth.sp500_unchanged),
            _breadth_source_label(breadth.sp500_source),
            breadth.sp500_message,
            "覆盖S&P 500成分股，用最近两个交易日收盘价计算上涨、下跌和持平家数。",
            breadth.sp500_source,
            breadth.sp500_cache_saved_at,
        ),
        (
            "纳指100涨跌比",
            _fmt_full_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines, breadth.nasdaq100_unchanged),
            _breadth_source_label(breadth.nasdaq100_source),
            breadth.nasdaq100_message,
            "覆盖Nasdaq-100成分股，用最近两个交易日收盘价衡量科技权重内部扩散情况。",
            breadth.nasdaq100_source,
            breadth.nasdaq100_cache_saved_at,
        ),
    ]

    st.markdown('<div class="breadth-caption market">全市场宽度：成分股级别 A/D，失败时优先使用最近缓存。</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, (title, value, note, message, explanation, state, cache_saved_at) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {_status_badge(state, cache_saved_at)}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note} · {message}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="breadth-caption market">全市场宽度 · 预留接口</div>', unsafe_allow_html=True)
    market_items = [
        ("S&P 500 A/D", _fmt_ad(breadth.sp500_advances, breadth.sp500_declines), "pending constituent feed", "预留全标普成分股涨跌家数接口。"),
        ("Nasdaq 100 A/D", _fmt_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines), "pending constituent feed", "预留纳指100成分股涨跌家数接口。"),
    ]
    cols = st.columns(2)
    for col, (title, value, note, explanation) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card reserved-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_decision_matrix_legacy(analytics: MarketAnalytics) -> None:
    """Render five-dimensional decision output."""

    items = [
        ("趋势", analytics.decision.trend),
        ("宽度", analytics.decision.breadth),
        ("波动", analytics.decision.volatility),
        ("驱动", analytics.decision.driver),
        ("风险", analytics.decision.risk),
    ]
    html = ['<div class="decision-grid">']
    for label, value in items:
        html.append(
            f"""
            <div class="decision-cell">
                <div class="decision-label">{label}</div>
                <div class="decision-value">{value}</div>
            </div>
            """
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_badges(analytics: MarketAnalytics) -> None:
    """Render rule-based market judgment badges."""

    html = "".join(f'<span class="badge">{label}</span>' for label in analytics.labels)
    st.markdown(html or '<span class="badge">NO SIGNAL</span>', unsafe_allow_html=True)


def render_summary(sections: dict[str, list[str]]) -> None:
    """Render Summary / Driver / Watchlist notes."""

    cols = st.columns(3)
    for col, title in zip(cols, ["Summary", "Driver", "Watchlist"]):
        with col:
            notes = "".join(f"<li>{item}</li>" for item in sections.get(title, []))
            st.markdown(
                f"""
                <div class="terminal-note">
                    <div class="terminal-note-title">{title}</div>
                    <ul>{notes}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_stats(metrics: dict[str, IndexMetrics]) -> None:
    """Render volume and range statistics."""

    rows = []
    for metric in metrics.values():
        rows.append(
            {
                "指数": metric.name,
                "当日成交量": fmt_volume(metric.volume),
                "3个月均量": fmt_volume(metric.avg_volume_3m),
                "Volume Ratio": fmt_number(metric.volume_ratio, 2),
                "日内区间": f"{fmt_number(metric.day_low)} - {fmt_number(metric.day_high)}",
                "52周区间": f"{fmt_number(metric.low_52w)} - {fmt_number(metric.high_52w)}",
                "52周位置": fmt_plain_pct(metric.position_52w * 100 if metric.position_52w is not None else None),
                "20日年化波动": fmt_plain_pct(metric.volatility_20d),
                "20日平均振幅": fmt_plain_pct(metric.avg_range_20d),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_data_debug(debug_rows: list[DebugRow]) -> None:
    """Render repository diagnostics for local debugging."""

    rows = [
        {
            "module": row.category,
            "key": row.key,
            "ticker": row.ticker,
            "provider": row.provider,
            "state": row.state,
            "cache": row.cache_layer,
            "rows": row.rows,
            "note": row.message,
        }
        for row in sorted(debug_rows, key=lambda item: (item.category, item.key))
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_mega_cap_section(metrics: dict[str, IndexMetrics], average: float | None) -> None:
    """Render Magnificent Seven heatmap cards with Streamlit columns."""

    st.markdown(
        f"""
        <div class="section-kpi">
            <span>M7 AVERAGE</span>
            <strong class="{delta_class(average)}">{fmt_pct(average)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = sorted(metrics.values(), key=lambda metric: metric.strength_rank or 99)
    for start in range(0, len(rows), 4):
        cols = st.columns(min(4, len(rows) - start))
        for col, metric in zip(cols, rows[start : start + 4]):
            heat_class = _heat_class(metric.day_change_pct)
            with col:
                st.markdown(
                    f"""
                    <div class="heat-cell {heat_class}">
                        <div class="heat-rank">#{metric.strength_rank or '-'}</div>
                        <div class="heat-ticker">{metric.name}</div>
                        <div class="heat-change">{fmt_pct(metric.day_change_pct)}</div>
                        <div class="heat-meta">WGT {fmt_plain_pct(metric.weight)} · CONTR {fmt_pct(metric.contribution)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_decision_matrix(analytics: MarketAnalytics) -> None:
    """Render five-dimensional decision cards with Streamlit columns."""

    items = [
        ("趋势", analytics.decision.trend),
        ("宽度", analytics.decision.breadth),
        ("波动", analytics.decision.volatility),
        ("驱动", analytics.decision.driver),
        ("风险", analytics.decision.risk),
    ]
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="decision-cell">
                    <div class="decision-label">{label}</div>
                    <div class="decision-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _prepare_index_chart_data(datasets: dict[str, IndexDataset], period: str, normalized: bool) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    pct_frames: list[pd.DataFrame] = []
    for dataset in datasets.values():
        if dataset.config.category != "index":
            continue
        history = filter_history(dataset.history, period)
        if history.empty:
            continue
        values = history["close"].astype(float)
        pct = (values / values.iloc[0] - 1) * 100
        frame = pd.DataFrame(
            {
                "date": history["date"],
                "close": values,
                "pct": pct,
                "volume": history["volume"],
                "range": (history["high"] - history["low"]) / history["close"] * 100,
                "y": values / values.iloc[0] * 100 if normalized else values,
            }
        )
        frame["close_text"] = frame["close"].map(_fmt_hover_price)
        frame["pct_text"] = frame["pct"].map(lambda value: _fmt_hover_signed(value, "%"))
        frame["volume_text"] = frame["volume"].map(_fmt_hover_volume)
        frame["range_text"] = frame["range"].map(lambda value: _fmt_hover_signed(value, "%", signed=False))
        frames[dataset.config.name] = frame
        pct_frames.append(frame[["date", "pct"]].rename(columns={"pct": dataset.config.key}))

    if len(pct_frames) >= 2:
        merged = pct_frames[0]
        for frame in pct_frames[1:]:
            merged = merged.merge(frame, on="date", how="outer")
        keys = [col for col in merged.columns if col != "date"]
        merged["spread"] = merged[keys[0]] - merged[keys[1]]
        for name, frame in frames.items():
            frame = frame.merge(merged[["date", "spread"]], on="date", how="left")
            frame["spread_text"] = frame["spread"].map(lambda value: _fmt_hover_signed(value, " pct"))
            frames[name] = frame
    else:
        for name, frame in frames.items():
            frame["spread"] = 0.0
            frame["spread_text"] = "0.00 pct"
            frames[name] = frame
    return frames


def _fmt_hover_price(value: object) -> str:
    if pd.isna(value):
        return "--"
    return f"{float(value):,.2f}"


def _fmt_hover_signed(value: object, suffix: str, signed: bool = True) -> str:
    if pd.isna(value):
        return "--"
    number = float(value)
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number:.2f}{suffix}"


def _fmt_hover_volume(value: object) -> str:
    if pd.isna(value):
        return "--"
    number = float(value)
    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:.2f}B"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    return f"{number:,.0f}"


def _add_recent_high_low_markers(fig: go.Figure, name: str, frame: pd.DataFrame) -> None:
    high_idx = frame["y"].idxmax()
    low_idx = frame["y"].idxmin()
    marker_frame = frame.loc[[high_idx, low_idx]]
    fig.add_trace(
        go.Scatter(
            x=marker_frame["date"],
            y=marker_frame["y"],
            mode="markers+text",
            name=f"{name} H/L",
            text=["高点", "低点"],
            textposition=["top center", "bottom center"],
            marker={"size": 8, "symbol": "diamond", "line": {"width": 1, "color": "#f8fafc"}},
            hovertemplate="%{x|%Y-%m-%d}<br>%{text}: %{y:,.2f}<extra></extra>",
            showlegend=False,
        )
    )


def _heat_class(value: float | None) -> str:
    if value is None:
        return "heat-flat"
    if value >= 2:
        return "heat-up-strong"
    if value > 0:
        return "heat-up"
    if value <= -2:
        return "heat-down-strong"
    if value < 0:
        return "heat-down"
    return "heat-flat"


def _fmt_ad(advances: int | None, declines: int | None) -> str:
    if advances is None or declines is None:
        return "预留"
    return f"{advances} / {declines}"


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Render localized market breadth cards."""

    breadth = analytics.breadth
    leadership_items = [
        ("龙头涨跌比（M7 A/D）", f"{breadth.advances} / {breadth.declines}", "七巨头内部宽度", "衡量七巨头内部上涨与下跌家数。"),
        ("龙头新高/新低（M7 NH/NL）", f"{breadth.new_highs} / {breadth.new_lows}", "52周极值", "观察龙头股是否接近一年高低位。"),
        ("等权表现（Equal Weight）", fmt_pct(breadth.equal_weight_return), "RSP", "等权指数更能反映普通成分股表现。"),
        ("市值权重表现（Cap Weight）", fmt_pct(breadth.cap_weight_return), "SPY", "市值加权指数更受大型权重股影响。"),
        ("等权-权重差（EW-CW）", fmt_pct(breadth.equal_vs_cap_spread), "扩散/集中度", "正值说明行情扩散，负值说明权重股主导。"),
    ]

    st.markdown(
        '<div class="breadth-caption">龙头宽度：M7 A/D 反映七巨头（Mega Cap Leaders）内部上涨/下跌家数的广度情况，不代表整个市场宽度。</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for col, (title, value, note, explanation) in zip(cols, leadership_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="breadth-caption market">全市场宽度 · 预留接口</div>', unsafe_allow_html=True)
    market_items = [
        ("标普500涨跌比（S&P 500 A/D）", _fmt_ad(breadth.sp500_advances, breadth.sp500_declines), "等待成分股数据源", "预留全标普成分股涨跌家数接口。"),
        ("纳指100涨跌比（Nasdaq 100 A/D）", _fmt_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines), "等待成分股数据源", "预留纳指100成分股涨跌家数接口。"),
    ]
    cols = st.columns(2)
    for col, (title, value, note, explanation) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card reserved-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_badges(analytics: MarketAnalytics) -> None:
    """Render localized rule-based market judgment badges."""

    html = "".join(f'<span class="badge">{label}</span>' for label in analytics.labels)
    st.markdown(html or '<span class="badge">暂无信号</span>', unsafe_allow_html=True)


def render_summary(sections: dict[str, list[str]]) -> None:
    """Render localized Summary / Driver / Watchlist notes."""

    title_map = {"Summary": "摘要（Summary）", "Driver": "驱动（Driver）", "Watchlist": "观察清单（Watchlist）"}
    cols = st.columns(3)
    for col, key in zip(cols, ["Summary", "Driver", "Watchlist"]):
        with col:
            notes = "".join(f"<li>{item}</li>" for item in sections.get(key, []))
            st.markdown(
                f"""
                <div class="terminal-note">
                    <div class="terminal-note-title">{title_map[key]}</div>
                    <ul>{notes}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_stats(metrics: dict[str, IndexMetrics]) -> None:
    """Render localized volume and range statistics."""

    rows = []
    for metric in metrics.values():
        rows.append(
            {
                "指数": metric.name,
                "当日成交量": fmt_volume(metric.volume),
                "3个月均量": fmt_volume(metric.avg_volume_3m),
                "量比（成交量/3月均量）": fmt_number(metric.volume_ratio, 2),
                "日内区间": f"{fmt_number(metric.day_low)} - {fmt_number(metric.day_high)}",
                "52周区间": f"{fmt_number(metric.low_52w)} - {fmt_number(metric.high_52w)}",
                "52周位置": fmt_plain_pct(metric.position_52w * 100 if metric.position_52w is not None else None),
                "20日年化波动": fmt_plain_pct(metric.volatility_20d),
                "20日平均振幅": fmt_plain_pct(metric.avg_range_20d),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_stats(metrics: dict[str, IndexMetrics]) -> None:
    """Render volume and statistics as data plus interpretation."""

    rows = list(metrics.values())
    st.markdown(f'<div class="stats-summary">{_stats_summary(rows)}</div>', unsafe_allow_html=True)

    headers = [
        ("指数", ""),
        ("当日成交量", "今日成交规模"),
        ("3个月均量", "近期平均成交规模"),
        ("量比", "今日成交量 / 3个月均量"),
        ("日内区间", "今日最高-最低范围"),
        ("52周位置", "当前价格在一年区间中的位置"),
        ("20日年化波动", "近期风险波动水平"),
        ("20日平均振幅", "日均波动幅度"),
    ]
    header_html = "".join(f"<th>{title}<span class=\"th-sub\">{subtitle}</span></th>" for title, subtitle in headers)
    body_html = []
    for metric in rows:
        body_html.append(
            "<tr>"
            f"<td>{html.escape(metric.name)}</td>"
            f"<td>{fmt_volume(metric.volume)}</td>"
            f"<td>{fmt_volume(metric.avg_volume_3m)}</td>"
            f"<td>{_volume_ratio_badge(metric.volume_ratio)}</td>"
            f"<td>{fmt_number(metric.day_low)} - {fmt_number(metric.day_high)}</td>"
            f"<td>{fmt_plain_pct(metric.position_52w * 100 if metric.position_52w is not None else None)}</td>"
            f"<td>{fmt_plain_pct(metric.volatility_20d)}</td>"
            f"<td>{fmt_plain_pct(metric.avg_range_20d)}</td>"
            "</tr>"
        )

    st.markdown(
        f"""
        <table class="stats-table">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{''.join(body_html)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def _stats_summary(metrics: list[IndexMetrics]) -> str:
    nasdaq = next((metric for metric in metrics if metric.key == "nasdaq"), None)
    sp500 = next((metric for metric in metrics if metric.key == "sp500"), None)
    parts = []
    for label, metric in [("纳指", nasdaq), ("标普", sp500)]:
        if not metric:
            continue
        volume_state = _volume_state(metric.volume_ratio)
        direction = "上行" if (metric.day_change_pct or 0) > 0 else "下行" if (metric.day_change_pct or 0) < 0 else "持平"
        parts.append(f"{label}{volume_state}{direction}")

    position_values = [metric.position_52w for metric in [nasdaq, sp500] if metric and metric.position_52w is not None]
    if position_values:
        avg_position = sum(position_values) / len(position_values)
        if avg_position >= 0.8:
            position_text = "指数接近年内高位"
        elif avg_position <= 0.25:
            position_text = "指数仍处一年区间低位"
        else:
            position_text = "指数处于一年区间中部"
    else:
        position_text = "52周位置数据待确认"

    activity = "，".join(parts) if parts else "成交活跃度数据待确认"
    return f"市场活跃度：{activity}，{position_text}。"


def _volume_state(volume_ratio: float | None) -> str:
    if volume_ratio is None:
        return "量能待确认"
    if volume_ratio > 1.2:
        return "放量"
    if volume_ratio < 0.8:
        return "缩量"
    return "量能正常"


def _volume_ratio_badge(volume_ratio: float | None) -> str:
    if volume_ratio is None:
        return '<span class="ratio-badge ratio-normal">--</span>'
    if volume_ratio > 1.2:
        cls, label = "ratio-high", "放量"
    elif volume_ratio < 0.8:
        cls, label = "ratio-low", "缩量"
    else:
        cls, label = "ratio-normal", "正常"
    return f'<span class="ratio-badge {cls}">{volume_ratio:.2f} {label}</span>'


def render_terminal_status_bar(analytics: MarketAnalytics, source_name: str, is_mock: bool) -> None:
    """Render localized terminal-style top status bar."""

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")
    live_text = "模拟数据（MOCK）" if is_mock else "实时数据（LIVE）"
    live_class = "terminal-chip warn" if is_mock else "terminal-chip live"
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    breadth = analytics.breadth
    breadth_text = f"龙头宽度（M7 A/D）{breadth.advances}/{breadth.declines}"
    risk_class = "risk-off" if "Risk OFF" in analytics.decision.risk_mode else "risk-on"

    st.markdown(
        f"""
        <div class="terminal-topbar">
            <div class="terminal-brand">
                <span class="terminal-title">美股指数专业看板 V3</span>
                <span class="terminal-subtitle">数据源：{source_name}</span>
            </div>
            <div class="terminal-strip">
                <span class="terminal-chip">{now_et}</span>
                <span class="{live_class}">{live_text}</span>
                <span class="terminal-chip {risk_class}">{analytics.decision.risk_mode}</span>
                <span class="terminal-chip">VIX {fmt_number(vix.current if vix else None, 2)} / {fmt_pct(vix.day_change_pct if vix else None)}</span>
                <span class="terminal-chip">10年美债 {fmt_number(us10y.current if us10y else None, 2)}%</span>
                <span class="terminal-chip">{breadth_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mega_cap_section(metrics: dict[str, IndexMetrics], average: float | None) -> None:
    """Render localized Magnificent Seven heatmap cards with Streamlit columns."""

    st.markdown(
        f"""
        <div class="section-kpi">
            <span>七巨头平均表现（M7 Avg）</span>
            <strong class="{delta_class(average)}">{fmt_pct(average)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = sorted(metrics.values(), key=lambda metric: metric.strength_rank or 99)
    for start in range(0, len(rows), 4):
        cols = st.columns(min(4, len(rows) - start))
        for col, metric in zip(cols, rows[start : start + 4]):
            heat_class = _heat_class(metric.day_change_pct)
            with col:
                st.markdown(
                    f"""
                    <div class="heat-cell {heat_class}">
                        <div class="heat-rank">强弱排名 #{metric.strength_rank or '-'}</div>
                        <div class="heat-ticker">{metric.name}</div>
                        <div class="heat-change">{fmt_pct(metric.day_change_pct)}</div>
                        <div class="heat-meta">权重 {fmt_plain_pct(metric.weight)} · 贡献 {fmt_pct(metric.contribution)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_decision_matrix(analytics: MarketAnalytics) -> None:
    """Render localized five-dimensional decision cards with Streamlit columns."""

    items = [
        ("趋势", analytics.decision.trend),
        ("宽度", analytics.decision.breadth),
        ("波动", analytics.decision.volatility),
        ("驱动", analytics.decision.driver),
        ("风险", analytics.decision.risk),
    ]
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="decision-cell">
                    <div class="decision-label">{label}</div>
                    <div class="decision-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _fmt_full_ad(advances: int | None, declines: int | None, unchanged: int | None) -> str:
    if advances is None or declines is None:
        return "暂无数据"
    unchanged_value = 0 if unchanged is None else unchanged
    return f"上涨{advances}家 / 下跌{declines}家 / 持平{unchanged_value}家"


def _breadth_source_label(source_state: str) -> str:
    if source_state == "live":
        return "实时数据"
    if source_state in {"cache", "stale_cache"}:
        return "使用缓存数据"
    return "暂无实时数据"


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Render leadership breadth and real broad-market A/D cards."""

    breadth = analytics.breadth
    leadership_items = [
        (
            "龙头宽度（M7 A/D）",
            f"上涨{breadth.advances} / 下跌{breadth.declines} / 持平{breadth.unchanged}",
            "七巨头内部结构",
            "仅衡量七巨头内部涨跌分布，不代表全市场宽度。",
        ),
        (
            "龙头新高/新低（M7 NH/NL）",
            f"{breadth.new_highs} / {breadth.new_lows}",
            "52周位置",
            "观察龙头股是否接近52周高位或低位，用于判断领导力质量。",
        ),
        (
            "等权表现（Equal Weight）",
            fmt_pct(breadth.equal_weight_return),
            "RSP",
            "等权指数更能反映普通成分股表现，弱于市值加权时说明上涨较集中。",
        ),
        (
            "市值加权表现（Cap Weight）",
            fmt_pct(breadth.cap_weight_return),
            "SPY",
            "市值加权指数受大型权重股影响更大，用于观察龙头拉动强度。",
        ),
        (
            "等权-市值差（EW-CW）",
            fmt_pct(breadth.equal_vs_cap_spread),
            "扩散/集中",
            "差值为正说明上涨扩散更好，差值为负说明权重股主导更强。",
        ),
    ]

    st.markdown(
        '<div class="breadth-caption">龙头宽度：M7 A/D 反映七巨头（Mega Cap Leaders）内部上涨/下跌家数的广度情况，不代表整个市场宽度。</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for col, (title, value, note, explanation) in zip(cols, leadership_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _normalized_status(source_state: str | None) -> str:
    if source_state in {"realtime", "cached", "mock", "error"}:
        return source_state
    if source_state == "live":
        return "realtime"
    if source_state in {"cache", "stale_cache"}:
        return "cached"
    if source_state == "mock":
        return "mock"
    return "error"


def _status_badge(source_state: str | None, cache_saved_at: float | None = None) -> str:
    status = _normalized_status(source_state)
    labels = {
        "realtime": "🟢 实时",
        "cached": "🟡 缓存",
        "mock": "🔵 Mock",
        "error": "🔴 错误",
    }
    meta = _cache_meta(status, cache_saved_at)
    return f'<span class="status-badge status-{status}">{labels[status]}</span>{meta}'


def _cache_meta(status: str, cache_saved_at: float | None) -> str:
    if status != "cached" or cache_saved_at is None:
        return ""
    saved_at = datetime.fromtimestamp(cache_saved_at)
    minutes = max(0, int((datetime.now() - saved_at).total_seconds() // 60))
    if minutes < 1:
        age = "缓存刚刚"
    elif minutes < 60:
        age = f"缓存 {minutes}分钟"
    else:
        age = f"缓存 {minutes // 60}小时{minutes % 60}分钟"
    return f'<div class="status-meta">{age}<br>缓存于 {saved_at:%H:%M}</div>'


def _aggregate_status(states: list[str | None]) -> str:
    normalized = [_normalized_status(state) for state in states]
    for status in ["error", "mock", "cached", "realtime"]:
        if status in normalized:
            return status
    return "error"


def _health_counts(analytics: MarketAnalytics) -> dict[str, int]:
    states = [metric.data_state for metric in analytics.metrics.values()]
    states.extend([analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source])
    states.append(_aggregate_status(states))
    counts = {"realtime": 0, "cached": 0, "mock": 0, "error": 0}
    for state in states:
        counts[_normalized_status(state)] += 1
    return counts


def _health_strip(analytics: MarketAnalytics) -> str:
    counts = _health_counts(analytics)
    return f"""
    <div class="health-strip">
        <span class="health-title">数据健康度</span>
        <span class="health-chip status-realtime">🟢 {counts["realtime"]}实时</span>
        <span class="health-chip status-cached">🟡 {counts["cached"]}缓存</span>
        <span class="health-chip status-mock">🔵 {counts["mock"]}模拟</span>
        <span class="health-chip status-error">🔴 {counts["error"]}错误</span>
    </div>
    """


def _metric_badge(metric: IndexMetrics | None) -> str:
    if metric is None:
        return _status_badge("error")
    return _status_badge(metric.data_state, metric.cache_saved_at)


def render_terminal_status_bar(analytics: MarketAnalytics, source_name: str, is_mock: bool) -> None:
    """Render localized terminal-style top status bar with data health."""

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")
    live_text = "模拟数据（MOCK）" if is_mock else "实时链路（LIVE）"
    live_class = "terminal-chip warn" if is_mock else "terminal-chip live"
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    breadth = analytics.breadth
    breadth_text = f"龙头宽度 M7 A/D {breadth.advances}/{breadth.declines}"
    risk_class = "risk-off" if "Risk OFF" in analytics.decision.risk_mode else "risk-on"

    st.markdown(_health_strip(analytics), unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="terminal-topbar">
            <div class="terminal-brand">
                <span class="terminal-title">美股指数专业看板 V3</span>
                <span class="terminal-subtitle">数据源：{html.escape(source_name)}</span>
            </div>
            <div class="terminal-strip">
                <span class="terminal-chip">{now_et}</span>
                <span class="{live_class}">{live_text}</span>
                <span class="terminal-chip {risk_class}">{analytics.decision.risk_mode}</span>
                <span class="terminal-chip">VIX {fmt_number(vix.current if vix else None, 2)} / {fmt_pct(vix.day_change_pct if vix else None)}</span>
                <span class="terminal-chip">10年美债 {fmt_number(us10y.current if us10y else None, 2)}%</span>
                <span class="terminal-chip">{breadth_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(metrics: dict[str, IndexMetrics]) -> None:
    """Render top index metric cards with source status."""

    cols = st.columns(2)
    for col, key in zip(cols, ["nasdaq", "sp500"]):
        metric = metrics.get(key)
        if not metric:
            continue
        returns_html = "".join(
            f'<span class="return-pill">{label} {fmt_pct(value)}</span>'
            for label, value in metric.returns.items()
        )
        delta_html = f"{fmt_number(metric.day_change)} / {fmt_pct(metric.day_change_pct)}"
        with col:
            st.markdown(
                f"""
                <div class="card index-card">
                    {_metric_badge(metric)}
                    <div class="card-title">{html.escape(metric.name)}</div>
                    <div class="metric-value">{fmt_number(metric.current)}</div>
                    <div class="{delta_class(metric.day_change)}">{delta_html}</div>
                    <div class="return-row">{returns_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_macro_strip(metrics: dict[str, IndexMetrics]) -> None:
    """Render VIX and US yield cards with source status."""

    us10y = metrics.get("us10y")
    us2y = metrics.get("us2y")
    spread = None
    if us2y and us10y and us2y.current is not None and us10y.current is not None:
        spread = us2y.current - us10y.current

    items = [
        ("VIX", metrics.get("vix"), metrics.get("vix").current if metrics.get("vix") else None, metrics.get("vix").day_change_pct if metrics.get("vix") else None, ""),
        ("10年美债收益率", us10y, us10y.current if us10y else None, us10y.day_change if us10y else None, "%"),
        ("2年美债收益率", us2y, us2y.current if us2y else None, us2y.day_change if us2y else None, "%"),
        ("2Y-10Y 利差", us10y or us2y, spread, None, "bp"),
    ]

    cols = st.columns(4)
    for col, (title, metric, value, delta, unit) in zip(cols, items):
        value_text = f"{fmt_number(value, 2)}%" if unit == "%" else f"{fmt_number(value * 100, 0)} bp" if value is not None and unit == "bp" else fmt_number(value, 2)
        delta_text = fmt_pct(delta) if title == "VIX" else fmt_number(delta, 2)
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {_metric_badge(metric)}
                    <div class="card-title">{title}</div>
                    <div class="macro-value">{value_text}</div>
                    <div class="{delta_class(delta)}">{delta_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_mega_cap_section(metrics: dict[str, IndexMetrics], average: float | None) -> None:
    """Render localized Magnificent Seven heatmap cards with source status."""

    section_status = _aggregate_status([metric.data_state for metric in metrics.values()])
    st.markdown(
        f"""
        <div class="section-kpi">
            <span>七巨头平均表现（M7 Avg）</span>
            <strong class="{delta_class(average)}">{fmt_pct(average)}</strong>
            {_status_badge(section_status)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = sorted(metrics.values(), key=lambda metric: metric.strength_rank or 99)
    for start in range(0, len(rows), 4):
        cols = st.columns(min(4, len(rows) - start))
        for col, metric in zip(cols, rows[start : start + 4]):
            heat_class = _heat_class(metric.day_change_pct)
            with col:
                st.markdown(
                    f"""
                    <div class="heat-cell {heat_class}">
                        {_metric_badge(metric)}
                        <div class="heat-rank">强弱排名 #{metric.strength_rank or '-'}</div>
                        <div class="heat-ticker">{html.escape(metric.name)}</div>
                        <div class="heat-change">{fmt_pct(metric.day_change_pct)}</div>
                        <div class="heat-meta">权重 {fmt_plain_pct(metric.weight)} · 贡献 {fmt_pct(metric.contribution)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_decision_matrix(analytics: MarketAnalytics) -> None:
    """Render localized five-dimensional decision cards with source status."""

    ai_state = _aggregate_status([metric.data_state for metric in analytics.metrics.values()] + [analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source])
    items = [
        ("趋势", analytics.decision.trend),
        ("宽度", analytics.decision.breadth),
        ("波动", analytics.decision.volatility),
        ("驱动", analytics.decision.driver),
        ("风险", analytics.decision.risk),
    ]
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="decision-cell">
                    {_status_badge(ai_state)}
                    <div class="decision-label">{label}</div>
                    <div class="decision-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_summary(sections: dict[str, list[str]], analytics: MarketAnalytics | None = None) -> None:
    """Render localized Summary / Driver / Watchlist notes with source status."""

    title_map = {"Summary": "摘要（Summary）", "Driver": "驱动（Driver）", "Watchlist": "观察清单（Watchlist）"}
    ai_state = None
    if analytics is not None:
        ai_state = _aggregate_status([metric.data_state for metric in analytics.metrics.values()] + [analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source])
    cols = st.columns(3)
    for col, key in zip(cols, ["Summary", "Driver", "Watchlist"]):
        with col:
            notes = "".join(f"<li>{html.escape(str(item))}</li>" for item in sections.get(key, []))
            st.markdown(
                f"""
                <div class="terminal-note">
                    {_status_badge(ai_state) if ai_state else ""}
                    <div class="terminal-note-title">{title_map[key]}</div>
                    <ul>{notes}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Render leadership breadth and broad-market A/D cards with source status."""

    breadth = analytics.breadth
    m7_state = _aggregate_status([metric.data_state for metric in analytics.mega_cap_metrics.values()])
    equal_state = _aggregate_status(
        [
            analytics.metrics.get("equal_weight").data_state if analytics.metrics.get("equal_weight") else None,
            analytics.metrics.get("cap_weight").data_state if analytics.metrics.get("cap_weight") else None,
        ]
    )
    leadership_items = [
        ("龙头宽度（M7 A/D）", f"上涨{breadth.advances} / 下跌{breadth.declines} / 持平{breadth.unchanged}", "七巨头内部结构", "仅衡量七巨头内部涨跌分布，不代表全市场宽度。", m7_state),
        ("龙头新高/新低（M7 NH/NL）", f"{breadth.new_highs} / {breadth.new_lows}", "52周位置", "观察龙头股是否接近52周高位或低位，用于判断领导力质量。", m7_state),
        ("等权表现（Equal Weight）", fmt_pct(breadth.equal_weight_return), "RSP", "等权指数更能反映普通成分股表现，弱于市值加权时说明上涨较集中。", equal_state),
        ("市值加权表现（Cap Weight）", fmt_pct(breadth.cap_weight_return), "SPY", "市值加权指数受大型权重股影响更大，用于观察龙头拉动强度。", equal_state),
        ("等权-市值差（EW-CW）", fmt_pct(breadth.equal_vs_cap_spread), "扩散/集中", "差值为正说明上涨扩散更好，差值为负说明权重股主导更强。", equal_state),
    ]

    st.markdown(
        '<div class="breadth-caption">龙头宽度：M7 A/D 反映七巨头（Mega Cap Leaders）内部上涨/下跌家数的广度情况，不代表整个市场宽度。</div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for col, (title, value, note, explanation, state) in zip(cols, leadership_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {_status_badge(state)}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    market_items = [
        (
            "标普500涨跌比",
            _fmt_full_ad(breadth.sp500_advances, breadth.sp500_declines, breadth.sp500_unchanged),
            _breadth_source_label(breadth.sp500_source),
            breadth.sp500_message,
            "覆盖S&P 500成分股，用最近两个交易日收盘价计算上涨、下跌和持平家数。",
            breadth.sp500_source,
            breadth.sp500_cache_saved_at,
        ),
        (
            "纳指100涨跌比",
            _fmt_full_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines, breadth.nasdaq100_unchanged),
            _breadth_source_label(breadth.nasdaq100_source),
            breadth.nasdaq100_message,
            "覆盖Nasdaq-100成分股，用最近两个交易日收盘价衡量科技权重内部扩散情况。",
            breadth.nasdaq100_source,
            breadth.nasdaq100_cache_saved_at,
        ),
    ]

    st.markdown('<div class="breadth-caption market">全市场宽度：成分股级别 A/D，失败时优先使用最近缓存。</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, (title, value, note, message, explanation, state, cache_saved_at) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {_status_badge(state, cache_saved_at)}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note} · {message}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    market_items = [
        (
            "标普500涨跌比",
            _fmt_full_ad(breadth.sp500_advances, breadth.sp500_declines, breadth.sp500_unchanged),
            _breadth_source_label(breadth.sp500_source),
            breadth.sp500_message,
            "覆盖S&P 500成分股，用最近两个交易日收盘价计算上涨、下跌和持平家数。",
        ),
        (
            "纳指100涨跌比",
            _fmt_full_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines, breadth.nasdaq100_unchanged),
            _breadth_source_label(breadth.nasdaq100_source),
            breadth.nasdaq100_message,
            "覆盖Nasdaq-100成分股，用最近两个交易日收盘价衡量科技权重内部扩散情况。",
        ),
    ]

    st.markdown('<div class="breadth-caption market">全市场宽度：成分股级别 A/D，失败时优先使用最近缓存。</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, (title, value, note, message, explanation) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note} · {message}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
