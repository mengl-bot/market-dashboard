"""Reusable market interpretation helpers for rates and snapshot cards."""

from __future__ import annotations

from dataclasses import dataclass

from config.labels import SNAPSHOT_STATUS_LABELS
from services.analytics import IndexMetrics


@dataclass
class RateInterpretation:
    """Interpret the current rate environment for equity investors."""

    ten_year_direction: str
    two_year_direction: str
    spread_state: str
    summary: str


def snapshot_status(metric: IndexMetrics | None, kind: str = "equity") -> str:
    """Map daily movement into concise Chinese status labels."""

    change = metric.day_change_pct if kind in {"equity", "vol"} and metric else metric.day_change if metric else None
    if change is None:
        return "待确认"
    if kind == "vol":
        return SNAPSHOT_STATUS_LABELS["vol_up"] if change > 3 else SNAPSHOT_STATUS_LABELS["vol_down"] if change < -3 else SNAPSHOT_STATUS_LABELS["flat"]
    if kind == "rate":
        return SNAPSHOT_STATUS_LABELS["rate_up"] if change > 0.005 else SNAPSHOT_STATUS_LABELS["rate_down"] if change < -0.005 else SNAPSHOT_STATUS_LABELS["flat"]
    if change >= 1.0:
        return SNAPSHOT_STATUS_LABELS["strong_up"]
    if change > 0.1:
        return SNAPSHOT_STATUS_LABELS["mild_up"]
    if change <= -1.0:
        return SNAPSHOT_STATUS_LABELS["strong_down"]
    if change < -0.1:
        return SNAPSHOT_STATUS_LABELS["mild_down"]
    return SNAPSHOT_STATUS_LABELS["flat"]


def interpret_rates(us10y: IndexMetrics | None, us2y: IndexMetrics | None) -> RateInterpretation:
    """Explain 2Y, 10Y and 2Y-10Y spread with equity implications."""

    ten_change = us10y.day_change if us10y else None
    two_change = us2y.day_change if us2y else None
    spread = us2y.current - us10y.current if us2y and us10y and us2y.current is not None and us10y.current is not None else None

    ten_direction = "长端利率上行，高估值成长股承压" if ten_change is not None and ten_change > 0.005 else "长端利率下行，成长股估值压力缓解" if ten_change is not None and ten_change < -0.005 else "长端利率横盘，估值压力变化有限"
    two_direction = "短端利率上行，政策紧缩预期升温" if two_change is not None and two_change > 0.005 else "短端利率下行，降息预期增强" if two_change is not None and two_change < -0.005 else "短端利率横盘，政策预期暂稳"

    if spread is None:
        spread_state = "利差缺失，曲线状态待确认"
    elif spread < -0.25:
        spread_state = "倒挂加深，衰退预期增强"
    elif spread < 0:
        spread_state = "曲线仍倒挂，增长担忧未完全解除"
    elif spread < 0.5:
        spread_state = "利差修复，经济预期改善或通胀预期回升"
    else:
        spread_state = "曲线正常化，增长预期相对健康"

    return RateInterpretation(
        ten_year_direction=ten_direction,
        two_year_direction=two_direction,
        spread_state=spread_state,
        summary=f"{ten_direction}；{spread_state}",
    )

