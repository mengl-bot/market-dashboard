"""Analytics calculations for the index dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict

import numpy as np
import pandas as pd

from data_repository.fed_policy_rate import FedPolicyRate
from data_repository.market_breadth import MarketBreadthSnapshot
from providers.base import IndexDataset


MEGA_CAP_WEIGHTS = {
    "aapl": 7.0,
    "msft": 7.2,
    "nvda": 6.4,
    "amzn": 3.8,
    "googl": 3.9,
    "meta": 2.6,
    "tsla": 1.4,
}

SECTOR_WEIGHTS = {
    "xlk": 31.5,
    "xlf": 13.4,
    "xle": 3.7,
    "xlv": 12.6,
    "xli": 8.7,
    "xly": 10.2,
    "xlc": 8.8,
    "xlp": 6.1,
    "xlu": 2.5,
    "xlre": 2.3,
}

SECTOR_LABELS_ZH = {
    "xlk": "科技",
    "xlf": "金融",
    "xle": "能源",
    "xlv": "医疗保健",
    "xli": "工业",
    "xly": "可选消费",
    "xlc": "通信服务",
    "xlp": "必选消费",
    "xlu": "公用事业",
    "xlre": "房地产",
}

DEFENSIVE_SECTORS = {"xlv", "xlp", "xlu", "xlre"}


@dataclass
class IndexMetrics:
    """Computed market metrics for one tradable series."""

    key: str
    name: str
    category: str
    current: float | None
    previous_close: float | None
    day_change: float | None
    day_change_pct: float | None
    returns: dict[str, float | None]
    volume: float | None
    avg_volume_3m: float | None
    volume_ratio: float | None
    day_low: float | None
    day_high: float | None
    low_52w: float | None
    high_52w: float | None
    position_52w: float | None
    volatility_20d: float | None
    avg_range_20d: float | None
    latest_date: pd.Timestamp | None
    weight: float | None = None
    contribution: float | None = None
    strength_rank: int | None = None
    data_state: str = "error"
    data_provider: str = "unknown"
    cache_saved_at: float | None = None


@dataclass
class BreadthMetrics:
    """Breadth metrics.

    M7 A/D is a leadership breadth proxy only. Full-market fields are reserved
    for future constituent-level data.
    """

    advances: int
    declines: int
    unchanged: int
    new_highs: int
    new_lows: int
    equal_weight_return: float | None
    cap_weight_return: float | None
    equal_vs_cap_spread: float | None
    sp500_advances: int | None = None
    sp500_declines: int | None = None
    sp500_unchanged: int | None = None
    sp500_source: str = "unavailable"
    sp500_message: str = "暂无可用数据"
    sp500_cache_saved_at: float | None = None
    nasdaq100_advances: int | None = None
    nasdaq100_declines: int | None = None
    nasdaq100_unchanged: int | None = None
    nasdaq100_source: str = "unavailable"
    nasdaq100_message: str = "暂无可用数据"
    nasdaq100_cache_saved_at: float | None = None


@dataclass
class DecisionView:
    """Five-dimensional market judgment."""

    trend: str
    breadth: str
    volatility: str
    driver: str
    risk: str
    risk_mode: str


@dataclass
class SectorContribution:
    """Estimated S&P 500 daily sector contribution from ETF proxies."""

    key: str
    label: str
    day_change_pct: float | None
    est_contribution_pct: float | None
    weight: float | None
    rank: int | None
    role: str
    data_state: str = "error"
    data_provider: str = "unknown"
    cache_saved_at: float | None = None


@dataclass
class MarketAnalytics:
    """Aggregated analytics needed by all UI sections."""

    metrics: Dict[str, IndexMetrics]
    index_metrics: Dict[str, IndexMetrics]
    macro_metrics: Dict[str, IndexMetrics]
    mega_cap_metrics: Dict[str, IndexMetrics]
    sector_metrics: Dict[str, IndexMetrics]
    sector_contributions: list[SectorContribution]
    breadth: BreadthMetrics
    decision: DecisionView
    fed_policy_rate: FedPolicyRate | None
    mega_cap_average: float | None
    labels: list[str]
    leader_key: str | None


PERIOD_DAYS = {"5D": 5, "1M": 21, "6M": 126, "1Y": 252}


def calculate_market_analytics(
    datasets: Dict[str, IndexDataset],
    market_breadth: dict[str, MarketBreadthSnapshot] | None = None,
    fed_policy_rate: FedPolicyRate | None = None,
) -> MarketAnalytics:
    """Compute metrics and rule-based market labels."""

    metrics = {key: calculate_index_metrics(dataset) for key, dataset in datasets.items()}
    index_metrics = _by_category(metrics, "index")
    macro_metrics = _by_category(metrics, "macro")
    mega_cap_metrics = _rank_mega_caps(_by_category(metrics, "mega_cap"))
    sector_metrics = _rank_sectors(_by_category(metrics, "sector"))
    metrics.update(mega_cap_metrics)
    metrics.update(sector_metrics)
    breadth = calculate_breadth(metrics, market_breadth)
    sector_contributions = calculate_sector_contributions(sector_metrics)
    mega_cap_average = _average([metric.day_change_pct for metric in mega_cap_metrics.values()])
    labels, leader_key = generate_market_labels(index_metrics, macro_metrics, mega_cap_average, breadth, fed_policy_rate)
    decision = generate_decision_view(index_metrics, macro_metrics, mega_cap_metrics, breadth, mega_cap_average, leader_key, fed_policy_rate)

    return MarketAnalytics(
        metrics=metrics,
        index_metrics=index_metrics,
        macro_metrics=macro_metrics,
        mega_cap_metrics=mega_cap_metrics,
        sector_metrics=sector_metrics,
        sector_contributions=sector_contributions,
        breadth=breadth,
        decision=decision,
        fed_policy_rate=fed_policy_rate,
        mega_cap_average=mega_cap_average,
        labels=labels,
        leader_key=leader_key,
    )


def calculate_index_metrics(dataset: IndexDataset) -> IndexMetrics:
    """Calculate return, volume, range, and volatility metrics for one series."""

    history = dataset.history.copy().sort_values("date").reset_index(drop=True)
    if history.empty:
        return _empty_metrics(dataset)

    latest = history.iloc[-1]
    previous = history.iloc[-2] if len(history) >= 2 else latest
    current = _safe_float(latest.get("close"))
    previous_close = _safe_float(previous.get("close"))
    day_change = _safe_sub(current, previous_close)
    day_change_pct = _safe_pct(day_change, previous_close)

    returns = {
        "5D": _period_return(history, PERIOD_DAYS["5D"]),
        "1M": _period_return(history, PERIOD_DAYS["1M"]),
        "6M": _period_return(history, PERIOD_DAYS["6M"]),
        "YTD": _ytd_return(history),
    }

    volume = _safe_float(latest.get("volume"))
    avg_volume_3m = _safe_float(history.tail(63)["volume"].mean())
    volume_ratio = _safe_div(volume, avg_volume_3m)

    low_52w = _safe_float(history["low"].tail(252).min())
    high_52w = _safe_float(history["high"].tail(252).max())
    day_low = _safe_float(latest.get("low"))
    day_high = _safe_float(latest.get("high"))
    position_52w = _range_position(current, low_52w, high_52w)

    daily_returns = history["close"].pct_change()
    volatility_20d = _safe_float(daily_returns.tail(20).std() * np.sqrt(252) * 100)
    avg_range_20d = _safe_float(((history["high"] - history["low"]) / history["close"]).tail(20).mean() * 100)

    return IndexMetrics(
        key=dataset.config.key,
        name=dataset.config.name,
        category=dataset.config.category,
        current=current,
        previous_close=previous_close,
        day_change=day_change,
        day_change_pct=day_change_pct,
        returns=returns,
        volume=volume,
        avg_volume_3m=avg_volume_3m,
        volume_ratio=volume_ratio,
        day_low=day_low,
        day_high=day_high,
        low_52w=low_52w,
        high_52w=high_52w,
        position_52w=position_52w,
        volatility_20d=volatility_20d,
        avg_range_20d=avg_range_20d,
        latest_date=pd.to_datetime(latest.get("date")) if pd.notna(latest.get("date")) else None,
        data_state=dataset.source_state,
        data_provider=dataset.provider,
        cache_saved_at=dataset.cache_saved_at,
    )


def calculate_breadth(
    metrics: Dict[str, IndexMetrics],
    market_breadth: dict[str, MarketBreadthSnapshot] | None = None,
) -> BreadthMetrics:
    """Build M7 leadership breadth and reserve full-market breadth fields."""

    basket = [metric for metric in metrics.values() if metric.category == "mega_cap" and metric.day_change_pct is not None]
    advances = sum(1 for metric in basket if metric.day_change_pct and metric.day_change_pct > 0)
    declines = sum(1 for metric in basket if metric.day_change_pct and metric.day_change_pct < 0)
    unchanged = max(0, len(basket) - advances - declines)
    new_highs = sum(1 for metric in basket if metric.position_52w is not None and metric.position_52w >= 0.97)
    new_lows = sum(1 for metric in basket if metric.position_52w is not None and metric.position_52w <= 0.03)

    equal_weight = metrics.get("equal_weight")
    cap_weight = metrics.get("cap_weight")
    equal_weight_return = equal_weight.day_change_pct if equal_weight else None
    cap_weight_return = cap_weight.day_change_pct if cap_weight else None
    equal_vs_cap_spread = _safe_sub(equal_weight_return, cap_weight_return)

    sp500 = (market_breadth or {}).get("sp500")
    nasdaq100 = (market_breadth or {}).get("nasdaq100")

    return BreadthMetrics(
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        new_highs=new_highs,
        new_lows=new_lows,
        equal_weight_return=equal_weight_return,
        cap_weight_return=cap_weight_return,
        equal_vs_cap_spread=equal_vs_cap_spread,
        sp500_advances=sp500.advances if sp500 else None,
        sp500_declines=sp500.declines if sp500 else None,
        sp500_unchanged=sp500.unchanged if sp500 else None,
        sp500_source=sp500.source_state if sp500 else "unavailable",
        sp500_message=sp500.message if sp500 else "暂无可用数据",
        sp500_cache_saved_at=sp500.cache_saved_at if sp500 else None,
        nasdaq100_advances=nasdaq100.advances if nasdaq100 else None,
        nasdaq100_declines=nasdaq100.declines if nasdaq100 else None,
        nasdaq100_unchanged=nasdaq100.unchanged if nasdaq100 else None,
        nasdaq100_source=nasdaq100.source_state if nasdaq100 else "unavailable",
        nasdaq100_message=nasdaq100.message if nasdaq100 else "暂无可用数据",
        nasdaq100_cache_saved_at=nasdaq100.cache_saved_at if nasdaq100 else None,
    )


def filter_history(history: pd.DataFrame, period: str) -> pd.DataFrame:
    """Filter history for the selected chart period."""

    if history.empty:
        return history

    frame = history.sort_values("date").copy()
    period = period.upper()
    if period == "YTD":
        return frame[frame["date"] >= pd.Timestamp(date.today().year, 1, 1)]

    days = {"1D": 2, "5D": 5, "1M": 21, "6M": 126, "1Y": 252}.get(period, 252)
    return frame.tail(days)


def calculate_sector_contributions(sector_metrics: Dict[str, IndexMetrics]) -> list[SectorContribution]:
    """Estimate sector contribution and role labels from ETF proxy returns."""

    ranked = sorted(
        sector_metrics.values(),
        key=lambda metric: metric.contribution if metric.contribution is not None else float("-inf"),
        reverse=True,
    )

    strongest_positive = next((metric.key for metric in ranked if (metric.contribution or 0) > 0), None)
    results: list[SectorContribution] = []
    for rank, metric in enumerate(ranked, start=1):
        results.append(
            SectorContribution(
                key=metric.key,
                label=SECTOR_LABELS_ZH.get(metric.key, metric.name),
                day_change_pct=metric.day_change_pct,
                est_contribution_pct=metric.contribution,
                weight=metric.weight,
                rank=rank if metric.contribution is not None else None,
                role=_sector_role(metric, strongest_positive),
                data_state=metric.data_state,
                data_provider=metric.data_provider,
                cache_saved_at=metric.cache_saved_at,
            )
        )
    return results


def generate_market_labels(
    index_metrics: Dict[str, IndexMetrics],
    macro_metrics: Dict[str, IndexMetrics],
    mega_cap_average: float | None,
    breadth: BreadthMetrics,
    fed_policy_rate: FedPolicyRate | None = None,
) -> tuple[list[str], str | None]:
    """Create rule-based badges for relative strength, macro, and breadth."""

    nasdaq = index_metrics.get("nasdaq")
    sp500 = index_metrics.get("sp500")
    vix = macro_metrics.get("vix")
    labels: list[str] = []
    leader_key: str | None = None

    if nasdaq and sp500 and nasdaq.day_change_pct is not None and sp500.day_change_pct is not None:
        diff = nasdaq.day_change_pct - sp500.day_change_pct
        if diff > 0.25:
            labels.append("纳指领先")
            leader_key = "nasdaq"
        elif diff < -0.25:
            labels.append("标普领先")
            leader_key = "sp500"
        else:
            labels.append("指数同步")

    if vix and vix.day_change_pct is not None:
        labels.append("波动升温" if vix.day_change_pct > 3 else "波动回落" if vix.day_change_pct < -3 else "波动稳定")

    if mega_cap_average is not None:
        if mega_cap_average > 0:
            labels.append(f"七巨头均涨 {mega_cap_average:+.2f}%")
        elif mega_cap_average < 0:
            labels.append(f"七巨头均跌 {mega_cap_average:+.2f}%")
        else:
            labels.append("七巨头持平")

    if breadth.advances + breadth.declines:
        labels.append(f"龙头宽度 {breadth.advances}/{breadth.declines}")

    if breadth.equal_vs_cap_spread is not None:
        labels.append("等权领先" if breadth.equal_vs_cap_spread > 0 else "权重领先")

    if fed_policy_rate and fed_policy_rate.policy_status:
        labels.append(f"政策利率{fed_policy_rate.policy_status}")

    return labels, leader_key


def generate_decision_view(
    index_metrics: Dict[str, IndexMetrics],
    macro_metrics: Dict[str, IndexMetrics],
    mega_cap_metrics: Dict[str, IndexMetrics],
    breadth: BreadthMetrics,
    mega_cap_average: float | None,
    leader_key: str | None,
    fed_policy_rate: FedPolicyRate | None = None,
) -> DecisionView:
    """Generate five-dimensional terminal-style market judgment."""

    nasdaq = index_metrics.get("nasdaq")
    sp500 = index_metrics.get("sp500")
    vix = macro_metrics.get("vix")
    us10y = macro_metrics.get("us10y")

    avg_index = _average([nasdaq.day_change_pct if nasdaq else None, sp500.day_change_pct if sp500 else None])
    trend = "上行趋势，回调偏买（Uptrend / Buy Dips）" if avg_index is not None and avg_index > 0.35 else "下行趋势，反弹偏卖（Downtrend / Sell Rips）" if avg_index is not None and avg_index < -0.35 else "区间震荡，等待突破（Range / Wait for Break）"

    breadth_text = "参与面扩散，市场宽度改善（Broad Participation）" if breadth.advances > breadth.declines and (breadth.equal_vs_cap_spread or 0) >= 0 else "领涨集中，市场偏窄（Narrow Leadership）" if breadth.advances <= breadth.declines else "宽度分化，信号混合（Mixed Breadth）"

    volatility = "波动扩张，避险升温（Vol Expanding）" if vix and vix.day_change_pct is not None and vix.day_change_pct > 3 else "波动收敛，风险偏好改善（Vol Compressing）" if vix and vix.day_change_pct is not None and vix.day_change_pct < -3 else "波动受控，情绪稳定（Vol Contained）"

    top_driver = _top_abs_metric(mega_cap_metrics.values())
    driver = "七巨头支撑（M7 Basket Support）" if mega_cap_average is not None and mega_cap_average > 0 else "七巨头拖累（M7 Basket Drag）" if mega_cap_average is not None and mega_cap_average < 0 else "暂无明确主驱动（No Clear Driver）"
    if top_driver and top_driver.day_change_pct is not None:
        driver = f"{driver}，{top_driver.name} {top_driver.day_change_pct:+.2f}%"

    risk_pressure = 0
    if avg_index is not None and avg_index < 0:
        risk_pressure += 1
    if vix and vix.day_change_pct is not None and vix.day_change_pct > 3:
        risk_pressure += 1
    if us10y and us10y.day_change is not None and us10y.day_change > 0.04:
        risk_pressure += 1
    if fed_policy_rate and fed_policy_rate.policy_status == "限制性" and fed_policy_rate.last_action != "降息":
        risk_pressure += 1
    if breadth.advances < breadth.declines:
        risk_pressure += 1

    risk_mode = "风险偏好关闭（Risk OFF）" if risk_pressure >= 2 else "风险偏好开启（Risk ON）"
    risk = "风险抬升（Elevated）" if risk_pressure >= 2 else "风险可控（Controlled）"
    if leader_key == "nasdaq" and risk_pressure < 2:
        risk = "成长股获得买盘（Growth Bid）"

    return DecisionView(
        trend=trend,
        breadth=breadth_text,
        volatility=volatility,
        driver=driver,
        risk=risk,
        risk_mode=risk_mode,
    )


def _empty_metrics(dataset: IndexDataset) -> IndexMetrics:
    return IndexMetrics(
        key=dataset.config.key,
        name=dataset.config.name,
        category=dataset.config.category,
        current=None,
        previous_close=None,
        day_change=None,
        day_change_pct=None,
        returns={"5D": None, "1M": None, "6M": None, "YTD": None},
        volume=None,
        avg_volume_3m=None,
        volume_ratio=None,
        day_low=None,
        day_high=None,
        low_52w=None,
        high_52w=None,
        position_52w=None,
        volatility_20d=None,
        avg_range_20d=None,
        latest_date=None,
        data_state=dataset.source_state,
        data_provider=dataset.provider,
        cache_saved_at=dataset.cache_saved_at,
    )


def _rank_mega_caps(metrics: Dict[str, IndexMetrics]) -> Dict[str, IndexMetrics]:
    ranked = sorted(
        [metric for metric in metrics.values() if metric.day_change_pct is not None],
        key=lambda metric: metric.day_change_pct or 0,
        reverse=True,
    )
    total_weight = sum(MEGA_CAP_WEIGHTS.values())
    for rank, metric in enumerate(ranked, start=1):
        metric.strength_rank = rank
    for metric in metrics.values():
        weight = MEGA_CAP_WEIGHTS.get(metric.key)
        metric.weight = weight
        if weight is not None and metric.day_change_pct is not None and total_weight:
            metric.contribution = metric.day_change_pct * weight / total_weight
    return metrics


def _rank_sectors(metrics: Dict[str, IndexMetrics]) -> Dict[str, IndexMetrics]:
    ranked = sorted(
        [metric for metric in metrics.values() if metric.day_change_pct is not None],
        key=lambda metric: metric.day_change_pct or 0,
        reverse=True,
    )
    for rank, metric in enumerate(ranked, start=1):
        metric.strength_rank = rank
    for metric in metrics.values():
        weight = SECTOR_WEIGHTS.get(metric.key)
        metric.weight = weight
        if weight is not None and metric.day_change_pct is not None:
            metric.contribution = metric.day_change_pct * weight / 100
    return metrics


def _sector_role(metric: IndexMetrics, strongest_positive: str | None) -> str:
    contribution = metric.contribution
    if contribution is None or metric.day_change_pct is None:
        return "待确认"
    if contribution < 0:
        return "拖累"
    if metric.key == strongest_positive:
        return "主驱动"
    if metric.key in DEFENSIVE_SECTORS:
        return "防御"
    return "支撑"


def _top_abs_metric(metrics) -> IndexMetrics | None:
    clean = [metric for metric in metrics if metric.day_change_pct is not None]
    return max(clean, key=lambda metric: abs(metric.day_change_pct or 0), default=None)


def _by_category(metrics: Dict[str, IndexMetrics], category: str) -> Dict[str, IndexMetrics]:
    return {key: metric for key, metric in metrics.items() if metric.category == category}


def _average(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _period_return(history: pd.DataFrame, days: int) -> float | None:
    if len(history) < 2:
        return None
    start_index = max(0, len(history) - days - 1)
    start = _safe_float(history.iloc[start_index]["close"])
    end = _safe_float(history.iloc[-1]["close"])
    return _safe_pct(_safe_sub(end, start), start)


def _ytd_return(history: pd.DataFrame) -> float | None:
    current_year = date.today().year
    ytd = history[history["date"].dt.year == current_year]
    if ytd.empty:
        return None
    start = _safe_float(ytd.iloc[0]["close"])
    end = _safe_float(history.iloc[-1]["close"])
    return _safe_pct(_safe_sub(end, start), start)


def _range_position(value: float | None, low: float | None, high: float | None) -> float | None:
    if value is None or low is None or high is None or high == low:
        return None
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _safe_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_sub(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _safe_div(left: float | None, right: float | None) -> float | None:
    if left is None or right in (None, 0):
        return None
    return left / right


def _safe_pct(change: float | None, base: float | None) -> float | None:
    if change is None or base in (None, 0):
        return None
    return change / base * 100
