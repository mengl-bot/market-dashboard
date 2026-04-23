"""Long-term investing advice engine for V4."""

from __future__ import annotations

from dataclasses import dataclass

from config.regime import DCA_MULTIPLIERS
from services.contributions import ContributionMetrics
from services.market_regime import MarketRegime
from services.valuation import ValuationMetrics


@dataclass
class DcaSuggestion:
    """Long-term allocation suggestion without buy/sell trading language."""

    action: str
    multiplier: float
    summary: str
    rationale: list[str]


def generate_dca_suggestion(
    valuation: ValuationMetrics,
    regime: MarketRegime,
    contribution: ContributionMetrics,
) -> DcaSuggestion:
    """Generate a long-term DCA suggestion from valuation and regime inputs."""

    multiplier = float(DCA_MULTIPLIERS.get(valuation.valuation_label, 1.0))
    rationale = [f"估值标签：{valuation.valuation_label}", f"市场状态：{regime.primary}", f"结构：{contribution.concentration_label}"]

    if valuation.valuation_label == "低估" and regime.primary != "Risk Off":
        action = "可积极加仓"
        summary = "估值赔率较好，若基本面未恶化，长期资金可提高投入力度。"
    elif valuation.valuation_label == "合理":
        action = "正常定投"
        summary = "适合继续定投，重点放在长期纪律而非短期择时。"
    elif valuation.valuation_label == "偏贵":
        action = "谨慎定投"
        summary = "适合继续定投，但需下调未来收益预期，并避免情绪化追涨。"
    else:
        action = "减少追高冲动 / 等待更好赔率"
        summary = "当前估值偏高，持有优质资产比追涨更重要；若出现明显回撤，可再提高投入力度。"

    if regime.primary == "Rate Pressure":
        rationale.append("利率上行压制估值")
    if contribution.mega_cap_share is not None and contribution.mega_cap_share >= 0.65:
        rationale.append("龙头集中度偏高")

    return DcaSuggestion(action=action, multiplier=multiplier, summary=summary, rationale=rationale)

