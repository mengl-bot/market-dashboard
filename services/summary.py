"""Chinese market summary generator."""

from __future__ import annotations

from services.analytics import MarketAnalytics


def generate_chinese_summary(analytics: MarketAnalytics) -> dict[str, list[str]]:
    """Generate localized Summary / Driver / Watchlist notes."""

    nasdaq = analytics.index_metrics.get("nasdaq")
    sp500 = analytics.index_metrics.get("sp500")
    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    top = _top_mega(analytics)
    weak = _weak_mega(analytics)

    summary: list[str] = []
    driver: list[str] = []
    watchlist: list[str] = []

    if nasdaq and sp500 and nasdaq.day_change_pct is not None and sp500.day_change_pct is not None:
        spread = nasdaq.day_change_pct - sp500.day_change_pct
        summary.append(f"{analytics.decision.risk_mode}。纳指 {nasdaq.day_change_pct:+.2f}%，标普 {sp500.day_change_pct:+.2f}%，相对差 {spread:+.2f}pct。")
    else:
        summary.append(f"{analytics.decision.risk_mode}。指数数据不完整，先看可用信号。")
    summary.append(f"趋势：{analytics.decision.trend}。宽度：{analytics.decision.breadth}。")

    if top and top.day_change_pct is not None:
        driver.append(f"主驱动：{top.name} {top.day_change_pct:+.2f}%，贡献约 {top.contribution:+.2f}pct。")
    if analytics.mega_cap_average is not None:
        driver.append(f"七巨头平均 {analytics.mega_cap_average:+.2f}%。{analytics.decision.driver}。")
    if vix and vix.day_change_pct is not None:
        driver.append(f"波动：VIX {vix.current:.2f}，日变动 {vix.day_change_pct:+.2f}%。")

    if us10y and us10y.current is not None:
        watchlist.append(f"10年美债收益率 {us10y.current:.2f}%。若继续上行，成长股估值承压。")
    if weak and weak.day_change_pct is not None:
        watchlist.append(f"弱项：{weak.name} {weak.day_change_pct:+.2f}%。观察是否扩散到权重股。")
    breadth = analytics.breadth
    if breadth.equal_vs_cap_spread is not None:
        watchlist.append(f"宽度阈值：龙头宽度 {breadth.advances}/{breadth.declines}，等权-权重差 {breadth.equal_vs_cap_spread:+.2f}%。")
    else:
        watchlist.append(f"宽度阈值：龙头宽度 {breadth.advances}/{breadth.declines}。")

    return {
        "Summary": summary[:3],
        "Driver": driver[:3] or ["暂无单一主驱动，等待价格和宽度确认。"],
        "Watchlist": watchlist[:3],
    }


def _top_mega(analytics: MarketAnalytics):
    values = [metric for metric in analytics.mega_cap_metrics.values() if metric.day_change_pct is not None]
    return max(values, key=lambda metric: metric.day_change_pct or 0, default=None)


def _weak_mega(analytics: MarketAnalytics):
    values = [metric for metric in analytics.mega_cap_metrics.values() if metric.day_change_pct is not None]
    return min(values, key=lambda metric: metric.day_change_pct or 0, default=None)
