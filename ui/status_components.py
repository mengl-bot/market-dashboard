"""Status-aware Streamlit components and morning review mode."""

from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from services.analytics import IndexMetrics, MarketAnalytics
from services.interpretation import interpret_rates, snapshot_status
from ui.formatters import delta_class, fmt_number, fmt_pct, fmt_plain_pct


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
ET_TZ = ZoneInfo("America/New_York")


def is_morning_review_mode(now: datetime | None = None) -> bool:
    """Return True when Beijing time is in the morning review window."""

    current = now.astimezone(BEIJING_TZ) if now else datetime.now(BEIJING_TZ)
    return 6 <= current.hour < 12


def normalized_status(source_state: str | None) -> str:
    """Map repository source states into user-facing status buckets."""

    if source_state in {"realtime", "cached", "mock", "error"}:
        return source_state
    if source_state == "live":
        return "realtime"
    if source_state in {"cache", "stale_cache"}:
        return "cached"
    if source_state == "mock":
        return "mock"
    return "error"


def status_badge(
    source_state: str | None,
    cache_saved_at: float | None = None,
    provider: str | None = None,
    cache_label: str = "缓存",
) -> str:
    """Return a small absolute-positioned status badge."""

    status = normalized_status(source_state)
    labels = {
        "realtime": "实时",
        "cached": "缓存",
        "mock": "模拟",
        "error": "异常",
    }
    return f'<span class="status-badge status-{status}">{labels[status]}</span>{status_meta(status, cache_saved_at, provider, cache_label)}'


def status_meta(status: str, cache_saved_at: float | None, provider: str | None, cache_label: str) -> str:
    """Render concise provider/cache detail below the badge."""

    provider_text = provider_label(provider)
    if status == "realtime":
        return f'<div class="status-meta">{provider_text} 当前接口成功获取</div>' if provider_text else ""
    if status == "mock":
        return '<div class="status-meta">占位数据，等待真实接口接入</div>'
    if status == "error":
        return '<div class="status-meta">当前获取失败</div>'
    if cache_saved_at is None:
        return '<div class="status-meta">最近一次有效数据</div>'

    saved_at = datetime.fromtimestamp(cache_saved_at)
    minutes = max(0, int((datetime.now() - saved_at).total_seconds() // 60))
    if minutes < 1:
        age = "最近一次有效数据：刚刚"
    elif minutes < 60:
        age = f"最近一次有效数据：{minutes}分钟前"
    else:
        age = f"最近一次有效数据：{minutes // 60}小时{minutes % 60}分钟前"
    return f'<div class="status-meta">{age}<br>更新时间 {saved_at:%H:%M}</div>'


def provider_label(provider: str | None) -> str:
    """Normalize provider names for compact UI status text."""

    if not provider:
        return ""
    lower = provider.lower()
    if "yfinance" in lower or "yahoo" in lower:
        return "yfinance"
    if "alpha" in lower:
        return "Alpha Vantage"
    if "mock" in lower:
        return "模拟数据"
    if "wikipedia" in lower:
        return "Wikipedia"
    return provider


def aggregate_status(states: list[str | None]) -> str:
    """Collapse several source states into one conservative module status."""

    normalized = [normalized_status(state) for state in states]
    for status in ["error", "mock", "cached", "realtime"]:
        if status in normalized:
            return status
    return "error"


def health_counts(analytics: MarketAnalytics) -> dict[str, int]:
    """Count status buckets across core dashboard modules."""

    states = [metric.data_state for metric in analytics.metrics.values()]
    states.extend([analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source])
    states.append(aggregate_status(states))
    counts = {"realtime": 0, "cached": 0, "mock": 0, "error": 0}
    for state in states:
        counts[normalized_status(state)] += 1
    return counts


def render_terminal_status_bar(
    analytics: MarketAnalytics,
    source_name: str,
    is_mock: bool,
    morning_mode: bool = False,
) -> None:
    """Render top status bar with data health overview."""

    counts = health_counts(analytics)
    st.markdown(
        f"""
        <div class="health-strip">
            <span class="health-title">数据状态总览</span>
            <span class="health-chip status-realtime" title="实时数据：当前接口成功获取">实时数据：{counts["realtime"]}项</span>
            <span class="health-chip status-cached" title="缓存数据：最近一次有效数据">缓存数据：{counts["cached"]}项</span>
            <span class="health-chip status-mock" title="模拟数据：占位数据，等待真实接口接入">模拟数据：{counts["mock"]}项</span>
            <span class="health-chip status-error" title="异常数据：当前获取失败">异常数据：{counts["error"]}项</span>
            <span class="health-help">实时数据：当前接口成功获取；缓存数据：最近一次有效数据；模拟数据：占位数据，等待真实接口接入；异常数据：当前获取失败。</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    now_et = datetime.now(ET_TZ).strftime("%Y-%m-%d %H:%M:%S ET")
    title = "昨夜美股收盘总结" if morning_mode else "美股投资决策终端 V4"
    live_text = "晨间复盘模式" if morning_mode else ("模拟数据" if is_mock else "实时数据")
    live_class = "terminal-chip" if morning_mode else ("terminal-chip warn" if is_mock else "terminal-chip live")
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    breadth_text = f"龙头宽度 M7 A/D {analytics.breadth.advances}/{analytics.breadth.declines}"
    risk_class = "risk-off" if "Risk OFF" in analytics.decision.risk_mode else "risk-on"

    st.markdown(
        f"""
        <div class="terminal-topbar">
            <div class="terminal-brand">
                <div>
                    <span class="terminal-title">{title}</span>
                    <span class="terminal-subtitle">Market Intelligence Dashboard</span>
                </div>
                <span class="terminal-subtitle">数据链路：{html.escape(_display_source_name(source_name))}</span>
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


def render_morning_recap(analytics: MarketAnalytics) -> None:
    """Render a compact Beijing-morning close review block."""

    nasdaq = analytics.index_metrics.get("nasdaq")
    sp500 = analytics.index_metrics.get("sp500")
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    breadth = analytics.breadth
    risk_text = analytics.decision.risk
    conclusion = morning_conclusion(analytics)

    cards = [
        (
            "纳指 / 标普收盘",
            f"{fmt_pct(nasdaq.day_change_pct if nasdaq else None)} / {fmt_pct(sp500.day_change_pct if sp500 else None)}",
            "昨夜主线强弱",
            aggregate_status([nasdaq.data_state if nasdaq else None, sp500.data_state if sp500 else None]),
            max_cache_time([nasdaq, sp500]),
        ),
        (
            "七巨头表现",
            fmt_pct(analytics.mega_cap_average),
            "龙头股平均涨跌",
            aggregate_status([metric.data_state for metric in analytics.mega_cap_metrics.values()]),
            max_cache_time(list(analytics.mega_cap_metrics.values())),
        ),
        (
            "市场宽度",
            format_ad(breadth.sp500_advances, breadth.sp500_declines, breadth.sp500_unchanged),
            "S&P 500 A/D",
            breadth.sp500_source,
            breadth.sp500_cache_saved_at,
        ),
        (
            "风险指标",
            f"VIX {fmt_number(vix.current if vix else None, 2)} / 10Y {fmt_number(us10y.current if us10y else None, 2)}%",
            risk_text,
            aggregate_status([vix.data_state if vix else None, us10y.data_state if us10y else None]),
            max_cache_time([vix, us10y]),
        ),
    ]

    st.markdown('<div class="morning-panel"><div class="morning-title">晨间复盘重点</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (title, value, note, state, cache_saved_at) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {status_badge(state, cache_saved_at, cache_label="缓存")}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown(
        f"""
        <div class="morning-conclusion">
            <span>今日一句话结论</span>
            <strong>{html.escape(conclusion)}</strong>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def morning_conclusion(analytics: MarketAnalytics) -> str:
    """Create one concise morning conclusion from existing decisions."""

    nasdaq = analytics.index_metrics.get("nasdaq")
    sp500 = analytics.index_metrics.get("sp500")
    avg_index = average([nasdaq.day_change_pct if nasdaq else None, sp500.day_change_pct if sp500 else None])
    if "Risk OFF" in analytics.decision.risk_mode:
        return "风险偏防守，先看波动和美债方向，再判断成长股能否修复。"
    if avg_index is not None and avg_index > 0.35 and analytics.mega_cap_average is not None and analytics.mega_cap_average > 0:
        return "昨夜由指数和龙头共同支撑，今日重点看上涨能否扩散到更宽板块。"
    if avg_index is not None and avg_index < -0.35:
        return "昨夜指数承压，今日优先观察开盘风险偏好和VIX是否继续抬升。"
    return "市场处在观察区，今日重点看成交量、宽度和龙头延续性。"


def render_overview(metrics: dict[str, IndexMetrics]) -> None:
    """Render index cards with status badges."""

    cols = st.columns(2)
    for col, key in zip(cols, ["nasdaq", "sp500"]):
        metric = metrics.get(key)
        if not metric:
            continue
        returns_html = "".join(f'<span class="return-pill">{label} {fmt_pct(value)}</span>' for label, value in metric.returns.items())
        with col:
            st.markdown(
                f"""
                <div class="card index-card">
                    {status_badge(metric.data_state, metric.cache_saved_at, metric.data_provider)}
                    <div class="card-title">{html.escape(metric.name)}</div>
                    <div class="metric-value">{fmt_number(metric.current)}</div>
                    <div class="{delta_class(metric.day_change)}">{fmt_number(metric.day_change)} / {fmt_pct(metric.day_change_pct)}</div>
                    <div class="return-row">{returns_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_market_snapshot(analytics: MarketAnalytics) -> None:
    """Render V4 market snapshot cards with concise status labels."""

    cards = [
        ("S&P 500", analytics.index_metrics.get("sp500"), "equity"),
        ("Nasdaq Composite", analytics.index_metrics.get("nasdaq"), "equity"),
        ("Nasdaq 100", analytics.index_metrics.get("nasdaq100"), "equity"),
        ("VIX", analytics.macro_metrics.get("vix"), "vol"),
        ("2Y Treasury", analytics.macro_metrics.get("us2y"), "rate"),
        ("10Y Treasury", analytics.macro_metrics.get("us10y"), "rate"),
    ]
    us2y = analytics.macro_metrics.get("us2y")
    us10y = analytics.macro_metrics.get("us10y")
    spread = us2y.current - us10y.current if us2y and us10y and us2y.current is not None and us10y.current is not None else None

    st.markdown('<div class="layer-title">第一层 · Market Snapshot / 行情层</div>', unsafe_allow_html=True)
    for start in range(0, len(cards), 3):
        cols = st.columns(3)
        for col, (title, metric, kind) in zip(cols, cards[start : start + 3]):
            value_text = f"{fmt_number(metric.current if metric else None, 2)}%" if kind == "rate" else fmt_number(metric.current if metric else None, 2)
            delta_text = fmt_pct(metric.day_change_pct if metric else None) if kind in {"equity", "vol"} else fmt_bp(metric.day_change if metric else None)
            status = snapshot_status(metric, kind)
            with col:
                st.markdown(
                    f"""
                    <div class="card snapshot-card">
                        {status_badge(metric.data_state if metric else None, metric.cache_saved_at if metric else None, metric.data_provider if metric else None)}
                        <div class="card-title">{title}</div>
                        <span class="snapshot-status">{status}</span>
                        <div class="metric-value">{value_text}</div>
                        <div class="{delta_class(metric.day_change_pct if kind in {'equity', 'vol'} and metric else metric.day_change if metric else None)}">{delta_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown(
        f"""
        <div class="card snapshot-card spread-card">
            <div class="card-title">2Y10Y Spread</div>
            <span class="snapshot-status">{_spread_status_text(spread)}</span>
            <div class="macro-value">{fmt_number(spread * 100, 0) if spread is not None else "N/A"} bp</div>
            <div class="card-explain">{interpret_rates(us10y, us2y).summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_valuation_health(valuation) -> None:
    """Render S&P 500 valuation health check."""

    st.markdown('<div class="layer-title">第二层 · Valuation / 估值层</div>', unsafe_allow_html=True)
    metrics = [
        ("预期市盈率（Forward PE）", fmt_number(valuation.forward_pe, 1)),
        ("市盈率TTM（Trailing PE）", fmt_number(valuation.trailing_pe, 1)),
        ("盈利收益率（Earnings Yield）", fmt_plain_pct(valuation.earnings_yield)),
        ("10年美债收益率（10Y Yield）", fmt_plain_pct(valuation.ten_year_yield)),
        ("股权风险溢价（ERP）", fmt_plain_pct(valuation.erp)),
        ("周期调整市盈率（CAPE）", fmt_number(valuation.cape, 1)),
        ("历史估值分位", fmt_plain_pct(valuation.historical_percentile)),
    ]
    st.markdown(
        f"""
        <div class="valuation-panel">
            <div class="valuation-score">
                <span>估值评分</span>
                <strong>{valuation.valuation_score}</strong>
                <em>{valuation.valuation_label}</em>
                <div class="valuation-score-note">估值评分：{valuation.valuation_score} / 100</div>
                <div class="valuation-score-note">{_valuation_score_explanation(valuation.valuation_label)}</div>
            </div>
            <div class="valuation-grid">
                {"".join(f'<div class="valuation-item"><span>{label}</span><strong>{value}</strong></div>' for label, value in metrics)}
            </div>
            <div class="valuation-summary">{html.escape(valuation.valuation_summary)}</div>
            <div class="card-note">估值模型已启用（基于当前数据框架）</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_driver_breakdown(analytics: MarketAnalytics, contribution) -> None:
    """Render V4 market driver decomposition."""

    st.markdown('<div class="layer-title">第三层 · Drivers / 驱动层</div>', unsafe_allow_html=True)
    mega_width = _pct_width(contribution.mega_cap_share)
    other_width = _pct_width(contribution.other_share)
    st.markdown(
        f"""
        <div class="driver-panel">
            <div class="driver-title">七巨头 vs Other 493 贡献拆解</div>
            <div class="driver-bar">
                <span class="driver-bar-mega" style="width:{mega_width}%;">M7 {fmt_plain_pct(_to_pct(contribution.mega_cap_share))}</span>
                <span class="driver-bar-other" style="width:{other_width}%;">Other {fmt_plain_pct(_to_pct(contribution.other_share))}</span>
            </div>
            <div class="driver-grid">
                <div><span>七巨头贡献</span><strong>{fmt_pct(contribution.mega_cap_contribution)}</strong></div>
                <div><span>Other 493</span><strong>{fmt_pct(contribution.other_contribution)}</strong></div>
                <div><span>集中度</span><strong>{contribution.concentration_label}</strong></div>
            </div>
            <div class="card-explain">{html.escape(contribution.summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_sector_contribution_map(analytics)


def render_regime_panel(regime) -> None:
    """Render market regime state and evidence."""

    badges = "".join(f'<span class="regime-chip">{html.escape(item)}</span>' for item in regime.active_states)
    evidence = "".join(f"<li>{html.escape(item)}</li>" for item in regime.evidence)
    st.markdown(
        f"""
        <div class="regime-panel">
            <div class="terminal-note-title">Risk Regime / 市场状态引擎</div>
            <div class="regime-primary">{html.escape(regime.primary)}</div>
            <div class="regime-description">{html.escape(regime.description)}</div>
            <div class="regime-chip-row">{badges}</div>
            <ul>{evidence}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_actionable_insights(dca, valuation, regime) -> None:
    """Render long-term investor advice and DCA multiplier."""

    rationale = "".join(f"<li>{html.escape(item)}</li>" for item in dca.rationale)
    st.markdown('<div class="layer-title">第四层 · Actionable Insights / 决策层</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="action-panel">
            <div>
                <div class="terminal-note-title">长期投资者建议引擎</div>
                <div class="action-title">{html.escape(dca.action)}</div>
                <div class="action-summary">{html.escape(dca.summary)}</div>
                <ul>{rationale}</ul>
            </div>
            <div class="dca-box">
                <span>定投倍率建议</span>
                <strong>{dca.multiplier:.1f}x</strong>
                <em>{html.escape(valuation.valuation_label)} / {html.escape(regime.primary)}</em>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_macro_strip(metrics: dict[str, IndexMetrics]) -> None:
    """Render macro cards with status badges and Treasury insights."""

    us10y = metrics.get("us10y")
    us2y = metrics.get("us2y")
    vix = metrics.get("vix")
    spread = us2y.current - us10y.current if us2y and us10y and us2y.current is not None and us10y.current is not None else None

    cols = st.columns(4)

    with cols[0]:
        st.markdown(
            f"""
            <div class="card compact-card">
                {status_badge(vix.data_state if vix else None, vix.cache_saved_at if vix else None, vix.data_provider if vix else None)}
                <div class="card-title">VIX</div>
                <div class="macro-value">{fmt_number(vix.current if vix else None, 2)}</div>
                <div class="{delta_class(vix.day_change_pct if vix else None)}">{fmt_pct(vix.day_change_pct if vix else None)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    treasury_items = [
        (
            "US 10Y",
            us10y,
            us10y.current if us10y else None,
            us10y.day_change if us10y else None,
            "%",
            _treasury_10y_explanation(us10y),
            _yield_direction_badge(us10y.day_change if us10y else None, "10Y"),
        ),
        (
            "US 2Y",
            us2y,
            us2y.current if us2y else None,
            us2y.day_change if us2y else None,
            "%",
            _treasury_2y_explanation(us2y),
            _yield_direction_badge(us2y.day_change if us2y else None, "2Y"),
        ),
        (
            "2Y-10Y Spread",
            us10y or us2y,
            spread,
            None,
            "bp",
            _spread_explanation(spread),
            _spread_status_badge(spread),
        ),
    ]

    for col, (title, metric, value, delta, unit, explanation, insight_badge) in zip(cols[1:], treasury_items):
        value_text = f"{fmt_number(value, 2)}%" if unit == "%" else f"{fmt_number(value * 100, 0)} bp" if value is not None and unit == "bp" else fmt_number(value, 2)
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {status_badge(metric.data_state if metric else None, metric.cache_saved_at if metric else None, metric.data_provider if metric else None)}
                    <div class="card-title">{title}</div>
                    {insight_badge}
                    <div class="macro-value">{value_text}</div>
                    <div class="{delta_class(delta)}">{fmt_bp(delta)}</div>
                    <div class="card-explain treasury-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
        <div class="macro-summary-line">
            <span class="macro-summary-label">Treasury Insight</span>
            <strong>{html.escape(_treasury_macro_summary(us10y, us2y, spread))}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _treasury_10y_explanation(metric: IndexMetrics | None) -> str:
    if metric is None or metric.current is None:
        return "长端利率缺失，暂无法判断估值压力。"
    if metric.day_change is None or abs(metric.day_change) < 0.005:
        return "10Y代表长期贴现率，当前变动有限，股市估值影响中性。"
    if metric.day_change > 0:
        return "10Y上行代表贴现率抬升，成长股估值更容易承压。"
    return "10Y回落代表长期利率缓和，有利于成长股估值修复。"


def _treasury_2y_explanation(metric: IndexMetrics | None) -> str:
    if metric is None or metric.current is None:
        return "短端利率缺失，暂无法判断政策预期。"
    if metric.day_change is None or abs(metric.day_change) < 0.005:
        return "2Y反映联储政策预期，当前波动有限，市场在等待新指引。"
    if metric.day_change > 0:
        return "2Y上行显示紧缩预期抬头，权益风险偏好通常受压。"
    return "2Y回落显示降息预期升温，权益风险偏好通常改善。"


def _spread_explanation(spread: float | None) -> str:
    if spread is None:
        return "期限利差缺失，暂无法判断曲线形态。"
    if spread < 0:
        return "利差倒挂，市场仍在定价增长放缓或衰退风险。"
    if spread < 0.5:
        return "利差已转正但仍偏窄，曲线处于初步正常化阶段。"
    return "利差明显转正，曲线趋于正常，衰退担忧通常回落。"


def _yield_direction_badge(day_change: float | None, label: str) -> str:
    if day_change is None or abs(day_change) < 0.005:
        return '<span class="macro-insight-badge macro-insight-neutral">持平</span>'
    if day_change > 0:
        text = "估值承压" if label == "10Y" else "偏紧"
        return f'<span class="macro-insight-badge macro-insight-warn">{text}</span>'
    text = "估值缓和" if label == "10Y" else "偏松"
    return f'<span class="macro-insight-badge macro-insight-good">{text}</span>'


def _spread_status_badge(spread: float | None) -> str:
    if spread is None:
        return '<span class="macro-insight-badge macro-insight-neutral">待确认</span>'
    if spread < 0:
        return '<span class="macro-insight-badge macro-insight-risk">倒挂</span>'
    if spread < 0.5:
        return '<span class="macro-insight-badge macro-insight-warn">修复中</span>'
    return '<span class="macro-insight-badge macro-insight-good">正常化</span>'


def _treasury_macro_summary(us10y: IndexMetrics | None, us2y: IndexMetrics | None, spread: float | None) -> str:
    ten_year_text = "10Y持平，估值影响有限"
    if us10y and us10y.day_change is not None:
        if us10y.day_change > 0.005:
            ten_year_text = "10Y上行，成长股估值承压"
        elif us10y.day_change < -0.005:
            ten_year_text = "10Y回落，成长股估值缓和"

    two_year_text = ""
    if us2y and us2y.day_change is not None:
        if us2y.day_change > 0.005:
            two_year_text = "2Y上行，紧缩预期抬头"
        elif us2y.day_change < -0.005:
            two_year_text = "2Y回落，降息预期升温"

    spread_text = "利差状态待确认"
    if spread is not None:
        if spread < 0:
            spread_text = "利差倒挂，衰退担忧仍存"
        elif spread < 0.5:
            spread_text = "利差修复，衰退担忧下降"
        else:
            spread_text = "利差正常化，增长预期改善"

    parts = [ten_year_text]
    if two_year_text:
        parts.append(two_year_text)
    parts.append(spread_text)
    return "；".join(parts)


def render_mega_cap_section(metrics: dict[str, IndexMetrics], average_value: float | None) -> None:
    """Render M7 heatmap cards with status badges."""

    section_status = aggregate_status([metric.data_state for metric in metrics.values()])
    st.markdown(
        f"""
        <div class="section-kpi">
            <span>七巨头平均表现（M7 Avg）</span>
            <strong class="{delta_class(average_value)}">{fmt_pct(average_value)}</strong>
            {status_badge(section_status)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = sorted(metrics.values(), key=lambda metric: metric.strength_rank or 99)
    for start in range(0, len(rows), 4):
        cols = st.columns(min(4, len(rows) - start))
        for col, metric in zip(cols, rows[start : start + 4]):
            with col:
                st.markdown(
                    f"""
                    <div class="heat-cell {heat_class(metric.day_change_pct)}">
                        {status_badge(metric.data_state, metric.cache_saved_at, metric.data_provider)}
                        <div class="heat-rank">强弱排名 #{metric.strength_rank or '-'}</div>
                        <div class="heat-ticker">{html.escape(metric.name)}</div>
                        <div class="heat-change">{fmt_pct(metric.day_change_pct)}</div>
                        <div class="heat-meta">权重 {fmt_plain_pct(metric.weight)} · 贡献 {fmt_pct(metric.contribution)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_sector_contribution_map(analytics: MarketAnalytics) -> None:
    """Render sector proxy return and estimated S&P 500 contribution map."""

    sectors = analytics.sector_contributions
    if not sectors:
        st.markdown(
            """
            <div class="card compact-card">
                <div class="card-title">板块贡献图</div>
                <div class="card-explain">暂无 sector ETF 数据，无法估算标普板块贡献。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    top_positive = next((sector for sector in sectors if (sector.est_contribution_pct or 0) > 0), None)
    total_positive = sum(max(sector.est_contribution_pct or 0, 0) for sector in sectors)
    total_negative = sum(min(sector.est_contribution_pct or 0, 0) for sector in sectors)
    status = aggregate_status([sector.data_state for sector in sectors])

    lead_text = "暂无明显正向主驱动"
    if top_positive and top_positive.est_contribution_pct is not None:
        lead_text = f"{top_positive.label}领涨，估算贡献 {top_positive.est_contribution_pct:+.2f} pct"

    st.markdown(
        f"""
        <div class="section-kpi">
            <span>板块贡献图 / Sector Contribution Map</span>
            <strong>{lead_text}</strong>
            {status_badge(status)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="sector-summary-line">
            <span class="sector-summary-chip sector-summary-up">正向贡献 {total_positive:+.2f} pct</span>
            <span class="sector-summary-chip sector-summary-down">负向贡献 {total_negative:+.2f} pct</span>
            <span class="sector-summary-chip sector-summary-neutral">标签：主驱动 / 支撑 / 防御 / 拖累</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for start in range(0, len(sectors), 3):
        cols = st.columns(min(3, len(sectors) - start))
        for col, sector in zip(cols, sectors[start : start + 3]):
            metric_class = delta_class(sector.day_change_pct)
            contribution_class = delta_class(sector.est_contribution_pct)
            badge_class = _sector_role_class(sector.role)
            contribution_text = fmt_pct(sector.est_contribution_pct)
            if sector.est_contribution_pct is None:
                contribution_text = "--"
            with col:
                st.markdown(
                    f"""
                    <div class="card sector-card">
                        {status_badge(sector.data_state, sector.cache_saved_at, sector.data_provider)}
                        <div class="sector-card-top">
                            <div class="card-title">#{sector.rank or '--'} · {html.escape(sector.label)}</div>
                            <span class="sector-role-badge {badge_class}">{sector.role}</span>
                        </div>
                        <div class="{metric_class} sector-return">{fmt_pct(sector.day_change_pct)}</div>
                        <div class="sector-meta-row">
                            <span class="sector-meta-label">估算贡献</span>
                            <span class="{contribution_class}">{contribution_text}</span>
                        </div>
                        <div class="sector-meta-row">
                            <span class="sector-meta-label">代理ETF</span>
                            <span class="sector-meta-value">{sector.key.upper()}</span>
                        </div>
                        <div class="sector-meta-row">
                            <span class="sector-meta-label">估算权重</span>
                            <span class="sector-meta-value">{fmt_plain_pct(sector.weight)}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_breadth_section(analytics: MarketAnalytics) -> None:
    """Render leadership and full-market breadth with status badges."""

    breadth = analytics.breadth
    m7_state = aggregate_status([metric.data_state for metric in analytics.mega_cap_metrics.values()])
    equal_state = aggregate_status(
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
                    {status_badge(state)}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{note}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    market_items = [
        ("标普500涨跌比", format_ad(breadth.sp500_advances, breadth.sp500_declines, breadth.sp500_unchanged), breadth.sp500_message, "覆盖S&P 500成分股，用最近两个交易日收盘价计算上涨、下跌和持平家数。", breadth.sp500_source, breadth.sp500_cache_saved_at),
        ("纳指100涨跌比", format_ad(breadth.nasdaq100_advances, breadth.nasdaq100_declines, breadth.nasdaq100_unchanged), breadth.nasdaq100_message, "覆盖Nasdaq-100成分股，用最近两个交易日收盘价衡量科技权重内部扩散情况。", breadth.nasdaq100_source, breadth.nasdaq100_cache_saved_at),
    ]

    st.markdown('<div class="breadth-caption market">全市场宽度：成分股级别 A/D，失败时优先使用最近缓存。</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for col, (title, value, message, explanation, state, cache_saved_at) in zip(cols, market_items):
        with col:
            st.markdown(
                f"""
                <div class="card compact-card">
                    {status_badge(state, cache_saved_at, cache_label="上次计算")}
                    <div class="card-title">{title}</div>
                    <div class="breadth-value">{value}</div>
                    <div class="card-note">{message}</div>
                    <div class="card-explain">{explanation}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_decision_matrix(analytics: MarketAnalytics) -> None:
    """Render five-dimensional decision cards with AI data status."""

    ai_state = aggregate_status([metric.data_state for metric in analytics.metrics.values()] + [analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source])
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
                    {status_badge(ai_state)}
                    <div class="decision-label">{label}</div>
                    <div class="decision-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_summary(sections: dict[str, list[str]], analytics: MarketAnalytics | None = None) -> None:
    """Render Summary / Driver / Watchlist with AI data status."""

    title_map = {"Summary": "摘要（Summary）", "Driver": "驱动（Driver）", "Watchlist": "观察清单（Watchlist）"}
    ai_state = aggregate_status([metric.data_state for metric in analytics.metrics.values()] + [analytics.breadth.sp500_source, analytics.breadth.nasdaq100_source]) if analytics else None
    cols = st.columns(3)
    for col, key in zip(cols, ["Summary", "Driver", "Watchlist"]):
        with col:
            notes = "".join(f"<li>{html.escape(str(item))}</li>" for item in sections.get(key, []))
            st.markdown(
                f"""
                <div class="terminal-note">
                    {status_badge(ai_state) if ai_state else ""}
                    <div class="terminal-note-title">{title_map[key]}</div>
                    <ul>{notes}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _sector_role_class(role: str) -> str:
    if role == "主驱动":
        return "sector-role-driver"
    if role == "支撑":
        return "sector-role-support"
    if role == "防御":
        return "sector-role-defensive"
    if role == "拖累":
        return "sector-role-drag"
    return "sector-role-neutral"


def _spread_status_text(spread: float | None) -> str:
    if spread is None:
        return "待确认"
    if spread < 0:
        return "倒挂"
    if spread < 0.5:
        return "修复中"
    return "正常化"


def _valuation_score_explanation(label: str) -> str:
    if label == "低估":
        return "当前处于低估区间，长期赔率相对更具吸引力。"
    if label == "合理":
        return "当前处于合理区间，更适合长期定投而非激进追高。"
    if label == "偏贵":
        return "当前处于偏贵区间，未来长期回报预期可能低于历史平均。"
    if label == "高估":
        return "当前处于高估区间，应降低追高冲动并等待更好赔率。"
    return "估值区间待确认。"


def _display_source_name(source_name: str) -> str:
    if "mock" in source_name.lower():
        return "模拟数据链路"
    return source_name


def _pct_width(value: float | None) -> int:
    if value is None:
        return 50
    return int(max(8, min(92, value * 100)))


def _to_pct(value: float | None) -> float | None:
    return value * 100 if value is not None else None


def format_ad(advances: int | None, declines: int | None, unchanged: int | None) -> str:
    """Format A/D counts."""

    if advances is None or declines is None:
        return "暂无数据"
    return f"上涨{advances}家 / 下跌{declines}家 / 持平{unchanged or 0}家"


def fmt_bp(value: float | None) -> str:
    """Format yield changes in basis points."""

    if value is None:
        return "--"
    return f"{value * 100:+.0f}bp"


def heat_class(value: float | None) -> str:
    """Return heatmap class from percentage change."""

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


def average(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def max_cache_time(metrics: list[IndexMetrics | None]) -> float | None:
    values = [metric.cache_saved_at for metric in metrics if metric and metric.cache_saved_at is not None]
    return max(values) if values else None
