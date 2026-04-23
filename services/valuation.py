"""Valuation calculations for the V4 decision terminal."""

from __future__ import annotations

from dataclasses import dataclass

from config.valuation import VALUATION_FALLBACKS, VALUATION_SCORE_RANGES, VALUATION_SCORING
from services.analytics import IndexMetrics


@dataclass
class ValuationMetrics:
    """S&P 500 valuation health metrics."""

    forward_pe: float | None
    trailing_pe: float | None
    earnings_yield: float | None
    ten_year_yield: float | None
    erp: float | None
    cape: float | None
    historical_percentile: float | None
    valuation_score: int
    valuation_label: str
    valuation_summary: str
    source: str


def calculate_valuation(us10y: IndexMetrics | None) -> ValuationMetrics:
    """Build valuation metrics from configured fundamentals and live 10Y yield."""

    forward_pe = _float_or_none(VALUATION_FALLBACKS.get("forward_pe"))
    trailing_pe = _float_or_none(VALUATION_FALLBACKS.get("trailing_pe"))
    ten_year = us10y.current if us10y else None
    earnings_yield = 100 / forward_pe if forward_pe else None
    erp = earnings_yield - ten_year if earnings_yield is not None and ten_year is not None else None
    percentile = _float_or_none(VALUATION_FALLBACKS.get("historical_percentile"))

    score = _valuation_score(forward_pe, erp, percentile)
    label = _valuation_label(score)
    return ValuationMetrics(
        forward_pe=forward_pe,
        trailing_pe=trailing_pe,
        earnings_yield=earnings_yield,
        ten_year_yield=ten_year,
        erp=erp,
        cape=_float_or_none(VALUATION_FALLBACKS.get("cape")),
        historical_percentile=percentile,
        valuation_score=score,
        valuation_label=label,
        valuation_summary=_valuation_summary(label, erp),
        source=str(VALUATION_FALLBACKS.get("source", "mock_config")),
    )


def _valuation_score(forward_pe: float | None, erp: float | None, percentile: float | None) -> int:
    pe_score = _bucket_score(forward_pe, VALUATION_SCORING["forward_pe"], mode="max")
    erp_score = _bucket_score(erp, VALUATION_SCORING["erp"], mode="min")
    percentile_score = percentile if percentile is not None else 50
    score = (
        pe_score * VALUATION_SCORING["forward_pe_weight"]
        + erp_score * VALUATION_SCORING["erp_weight"]
        + percentile_score * VALUATION_SCORING["historical_percentile_weight"]
    )
    return int(max(0, min(100, round(score))))


def _bucket_score(value: float | None, rules: list[dict], mode: str) -> float:
    if value is None:
        return 50
    for rule in rules:
        if mode == "max" and value <= rule["max"]:
            return float(rule["score"])
        if mode == "min" and value >= rule["min"]:
            return float(rule["score"])
    return 50


def _valuation_label(score: int) -> str:
    for item in VALUATION_SCORE_RANGES:
        if item["min"] <= score <= item["max"]:
            return str(item["label"])
    return "待确认"


def _valuation_summary(label: str, erp: float | None) -> str:
    if label in {"高估", "偏贵"}:
        return "当前估值处于历史中高位，长期预期回报率可能低于均值，更适合控制追高节奏。"
    if label == "合理":
        return "当前估值尚可接受，更适合长期定投而非激进追高。"
    if label == "低估":
        return "当前估值具备较好赔率，若基本面未恶化，长期资金可提高投入力度。"
    if erp is not None and erp < 1:
        return "股债风险溢价偏低，权益资产需要更强盈利增长来支撑估值。"
    return "估值数据不足，建议结合盈利预期和利率环境继续观察。"


def _float_or_none(value: object) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None

