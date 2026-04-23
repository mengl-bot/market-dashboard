"""Contribution calculations for market drivers."""

from __future__ import annotations

from dataclasses import dataclass

from services.analytics import IndexMetrics, MarketAnalytics


@dataclass
class ContributionMetrics:
    """Mega-cap versus rest-of-market contribution estimate."""

    mega_cap_contribution: float | None
    other_contribution: float | None
    mega_cap_share: float | None
    other_share: float | None
    concentration_label: str
    summary: str


def calculate_contribution_metrics(analytics: MarketAnalytics) -> ContributionMetrics:
    """Estimate how much of S&P 500 movement is from M7 versus the rest."""

    sp500 = analytics.index_metrics.get("sp500")
    mega_contribution = _sum_metric_contributions(analytics.mega_cap_metrics.values())
    sp500_return = sp500.day_change_pct if sp500 else None
    other = sp500_return - mega_contribution if sp500_return is not None and mega_contribution is not None else None
    abs_total = abs(mega_contribution or 0) + abs(other or 0)
    mega_share = abs(mega_contribution or 0) / abs_total if abs_total else None
    other_share = abs(other or 0) / abs_total if abs_total else None

    if mega_share is None:
        label = "待确认"
        summary = "贡献数据不足，暂无法判断上涨是否集中。"
    elif mega_share >= 0.65:
        label = "龙头集中"
        summary = "当前指数波动主要由七巨头驱动，市场广度仍需确认。"
    elif mega_share <= 0.45:
        label = "扩散改善"
        summary = "其他成分股贡献提升，上涨正在向更广泛市场扩散。"
    else:
        label = "结构均衡"
        summary = "七巨头与其他成分股共同影响指数，结构相对均衡。"

    return ContributionMetrics(
        mega_cap_contribution=mega_contribution,
        other_contribution=other,
        mega_cap_share=mega_share,
        other_share=other_share,
        concentration_label=label,
        summary=summary,
    )


def _sum_metric_contributions(metrics) -> float | None:
    values = [metric.contribution for metric in metrics if isinstance(metric, IndexMetrics) and metric.contribution is not None]
    return sum(values) if values else None

