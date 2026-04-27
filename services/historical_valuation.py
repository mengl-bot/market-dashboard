"""Historical PE map and return-source decomposition."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from providers.base import IndexDataset
from services.valuation import ValuationMetrics


ANNUAL_EPS_GROWTH = 0.065
ANNUAL_DIVIDEND_YIELD = 0.013


@dataclass(frozen=True)
class ReturnSourceBreakdown:
    """Approximate six-month S&P 500 return source attribution."""

    earnings_contribution_pct: float | None
    valuation_expansion_pct: float | None
    dividend_contribution_pct: float | None
    total_price_return_pct: float | None


@dataclass(frozen=True)
class HistoricalValuationMap:
    """Data needed by the PE vs index module."""

    history: pd.DataFrame
    current_pe: float | None
    historical_percentile: float | None
    valuation_label: str
    breakdown: ReturnSourceBreakdown
    source_note: str


def build_historical_valuation_map(
    datasets: dict[str, IndexDataset],
    valuation: ValuationMetrics,
) -> HistoricalValuationMap:
    """Build a 10Y-capable valuation map from S&P 500 history and PE inputs.

    The current data stack has index prices but not a paid forward-EPS history
    feed. We anchor the latest configured Forward PE to the latest index level
    and model forward EPS backward with a conservative smooth growth rate.
    """

    sp500 = datasets.get("sp500")
    history = _clean_history(sp500.history if sp500 else pd.DataFrame())
    current_pe = valuation.forward_pe
    if history.empty or current_pe is None:
        return HistoricalValuationMap(
            history=pd.DataFrame(columns=["date", "index", "forward_pe", "forward_eps"]),
            current_pe=current_pe,
            historical_percentile=valuation.historical_percentile,
            valuation_label=valuation_bucket(current_pe),
            breakdown=ReturnSourceBreakdown(None, None, None, None),
            source_note="估值地图需要 S&P 500 历史价格和当前 Forward PE。",
        )

    latest_index = float(history.iloc[-1]["close"])
    latest_eps = latest_index / current_pe
    years_from_latest = (history["date"] - history.iloc[-1]["date"]).dt.days / 365.25
    history["forward_eps"] = latest_eps * ((1 + ANNUAL_EPS_GROWTH) ** years_from_latest)
    history["forward_pe"] = history["close"] / history["forward_eps"]
    history = history.rename(columns={"close": "index"})[["date", "index", "forward_pe", "forward_eps"]]

    percentile = _percentile_rank(history["forward_pe"], current_pe)
    return HistoricalValuationMap(
        history=history,
        current_pe=current_pe,
        historical_percentile=percentile,
        valuation_label=valuation_bucket(current_pe),
        breakdown=_six_month_breakdown(history),
        source_note="Forward PE 历史为当前 PE 锚定的估算序列；接入真实 Forward EPS 后可直接替换。",
    )


def valuation_bucket(pe: float | None) -> str:
    """Return the requested valuation label by PE range."""

    if pe is None:
        return "未知"
    if pe < 16:
        return "低估"
    if pe < 20:
        return "合理"
    if pe < 24:
        return "偏贵"
    return "高估"


def _clean_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty or "date" not in history or "close" not in history:
        return pd.DataFrame(columns=["date", "close"])
    frame = history[["date", "close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    return frame


def _percentile_rank(series: pd.Series, value: float | None) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if value is None or clean.empty:
        return None
    return float((clean <= value).mean() * 100)


def _six_month_breakdown(history: pd.DataFrame) -> ReturnSourceBreakdown:
    if len(history) < 2:
        return ReturnSourceBreakdown(None, None, None, None)

    end = history.iloc[-1]
    start_date = end["date"] - pd.DateOffset(months=6)
    window = history[history["date"] >= start_date]
    start = window.iloc[0] if not window.empty else history.iloc[max(0, len(history) - 126)]

    index_start = _float(start["index"])
    index_end = _float(end["index"])
    eps_start = _float(start["forward_eps"])
    eps_end = _float(end["forward_eps"])
    pe_start = _float(start["forward_pe"])
    pe_end = _float(end["forward_pe"])
    if None in {index_start, index_end, eps_start, eps_end, pe_start, pe_end}:
        return ReturnSourceBreakdown(None, None, None, None)

    price_return = (index_end / index_start - 1) * 100
    earnings = (eps_end / eps_start - 1) * 100
    valuation = (pe_end / pe_start - 1) * 100
    dividend = ANNUAL_DIVIDEND_YIELD / 2 * 100
    return ReturnSourceBreakdown(earnings, valuation, dividend, price_return)


def _float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
