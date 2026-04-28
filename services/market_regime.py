"""Market regime engine for V4."""

from __future__ import annotations

from dataclasses import dataclass

from config.labels import MARKET_REGIME_LABELS
from config.regime import REGIME_THRESHOLDS
from services.analytics import MarketAnalytics
from services.contributions import ContributionMetrics
from services.valuation import ValuationMetrics


@dataclass
class MarketRegime:
    """Primary and secondary market state labels."""

    primary: str
    active_states: list[str]
    description: str
    evidence: list[str]


def classify_market_regime(
    analytics: MarketAnalytics,
    valuation: ValuationMetrics,
    contribution: ContributionMetrics,
) -> MarketRegime:
    """Classify market state from volatility, rates, breadth and leadership."""

    vix = analytics.macro_metrics.get("vix")
    us10y = analytics.macro_metrics.get("us10y")
    sp500 = analytics.index_metrics.get("sp500")
    fed_policy_rate = analytics.fed_policy_rate
    active: list[str] = []
    evidence: list[str] = []

    if us10y and us10y.day_change is not None and us10y.day_change >= REGIME_THRESHOLDS["rate_pressure_daily_change"]:
        active.append("Rate Pressure")
        evidence.append("10Y收益率快速上行")

    if fed_policy_rate and fed_policy_rate.policy_status == "限制性" and fed_policy_rate.last_action != "降息":
        if "Rate Pressure" not in active:
            active.append("Rate Pressure")
        evidence.append("政策利率仍处限制性区间")

    if contribution.mega_cap_share is not None and contribution.mega_cap_share >= REGIME_THRESHOLDS["leader_concentration_high"]:
        active.append("Narrow Leadership")
        evidence.append("七巨头贡献占比偏高")

    positive_sectors = sum(1 for sector in analytics.sector_contributions if (sector.day_change_pct or 0) > 0)
    breadth_ratio = _safe_ratio(analytics.breadth.advances, analytics.breadth.declines)
    if positive_sectors >= REGIME_THRESHOLDS["sector_positive_count"] and breadth_ratio >= REGIME_THRESHOLDS["breadth_adv_decl_ratio"]:
        active.append("Broadening Rally")
        evidence.append("板块与市场宽度同步扩散")

    if vix and vix.current is not None and vix.current >= REGIME_THRESHOLDS["vix_risk_off"]:
        active.append("Risk Off")
        evidence.append("VIX处于高波动区间")
    elif vix and vix.current is not None and vix.current <= REGIME_THRESHOLDS["vix_risk_on"] and sp500 and (sp500.day_change_pct or 0) >= 0:
        active.append("Risk On")
        evidence.append("低波动且指数保持正收益")

    if valuation.valuation_score <= REGIME_THRESHOLDS["earnings_driver_valuation_score_max"] and sp500 and (sp500.day_change_pct or 0) > 0:
        active.append("Earnings Driven")
        evidence.append("估值压力可控且指数上涨")

    if not active:
        active.append("Risk On" if sp500 and (sp500.day_change_pct or 0) >= 0 else "Risk Off")
        evidence.append("使用指数方向作为默认状态")

    primary = active[0]
    return MarketRegime(
        primary=primary,
        active_states=active,
        description=MARKET_REGIME_LABELS.get(primary, "市场状态待确认。"),
        evidence=evidence,
    )


def _safe_ratio(left: int | None, right: int | None) -> float:
    if left is None or right in (None, 0):
        return 0.0
    return left / right
