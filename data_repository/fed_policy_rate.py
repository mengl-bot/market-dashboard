"""Fed Funds target rate repository with FRED, cache, and mock fallback."""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


FRED_LOWER_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARL"
FRED_UPPER_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"
DEFAULT_NEXT_FOMC_DATE = date(2026, 4, 29)


@dataclass
class FedPolicyRate:
    """Current Fed Funds target range and policy interpretation."""

    lower_bound: float | None
    upper_bound: float | None
    policy_status: str
    last_action: str
    next_fomc_date: date | None
    source_state: str
    provider: str
    cache_saved_at: float | None = None
    message: str = ""

    @property
    def midpoint(self) -> float | None:
        if self.lower_bound is None or self.upper_bound is None:
            return None
        return (self.lower_bound + self.upper_bound) / 2


class FedPolicyRateRepository:
    """Load Fed policy rate data without coupling it to market quotes."""

    cache_key = "fed_policy_rate.pkl"

    def __init__(self, cache_dir: Path, logger, ttl_seconds: int = 3600) -> None:
        self.cache_dir = cache_dir
        self.logger = logger
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> FedPolicyRate:
        """Return Fed Funds target data from fresh cache, FRED, stale cache, or mock."""

        cached = self._read_cache(fresh_only=True)
        if cached:
            cached.source_state = "cache"
            return cached

        try:
            live = self._fetch_fred()
            self._write_cache(live)
            return live
        except Exception as exc:
            self.logger.warning("fed policy rate fetch failed error=%s", exc)

        stale = self._read_cache(fresh_only=False)
        if stale:
            stale.source_state = "stale_cache"
            stale.message = "FRED 获取失败，使用最近一次缓存。"
            return stale

        return self._mock_policy_rate()

    def _fetch_fred(self) -> FedPolicyRate:
        lower = self._read_fred_series(FRED_LOWER_URL, "DFEDTARL")
        upper = self._read_fred_series(FRED_UPPER_URL, "DFEDTARU")
        frame = lower.merge(upper, on="DATE", how="inner").dropna()
        if frame.empty:
            raise ValueError("empty FRED Fed target range")

        latest = frame.iloc[-1]
        previous = self._previous_distinct_range(frame)
        lower_bound = float(latest["DFEDTARL"])
        upper_bound = float(latest["DFEDTARU"])
        last_action = self._last_action(lower_bound, upper_bound, previous)

        return FedPolicyRate(
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            policy_status=self._policy_status(lower_bound, upper_bound),
            last_action=last_action,
            next_fomc_date=DEFAULT_NEXT_FOMC_DATE,
            source_state="live",
            provider="FRED",
            message="下次 FOMC 日期为预留 fallback 字段。",
        )

    def _read_fred_series(self, url: str, column: str) -> pd.DataFrame:
        frame = pd.read_csv(url)
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["DATE"] = pd.to_datetime(frame["observation_date"])
        return frame[["DATE", column]]

    def _previous_distinct_range(self, frame: pd.DataFrame) -> tuple[float, float] | None:
        latest = frame.iloc[-1]
        latest_pair = (float(latest["DFEDTARL"]), float(latest["DFEDTARU"]))
        for _, row in frame.iloc[:-1].iloc[::-1].iterrows():
            pair = (float(row["DFEDTARL"]), float(row["DFEDTARU"]))
            if pair != latest_pair:
                return pair
        return None

    def _last_action(self, lower: float, upper: float, previous: tuple[float, float] | None) -> str:
        if previous is None:
            return "暂停"
        midpoint = (lower + upper) / 2
        previous_midpoint = (previous[0] + previous[1]) / 2
        if midpoint > previous_midpoint:
            return "加息"
        if midpoint < previous_midpoint:
            return "降息"
        return "暂停"

    def _policy_status(self, lower: float | None, upper: float | None) -> str:
        if lower is None or upper is None:
            return "中性"
        midpoint = (lower + upper) / 2
        if midpoint < 2.5:
            return "宽松"
        if midpoint <= 3.5:
            return "中性"
        return "限制性"

    def _read_cache(self, fresh_only: bool) -> FedPolicyRate | None:
        path = self.cache_dir / self.cache_key
        if not path.exists():
            return None
        try:
            with path.open("rb") as handle:
                policy_rate = pickle.load(handle)
        except Exception as exc:
            self.logger.warning("fed policy cache read failed error=%s", exc)
            return None

        if fresh_only and policy_rate.cache_saved_at is not None:
            age = time.time() - policy_rate.cache_saved_at
            if age > self.ttl_seconds:
                return None
        return policy_rate

    def _write_cache(self, policy_rate: FedPolicyRate) -> None:
        policy_rate.cache_saved_at = time.time()
        try:
            with (self.cache_dir / self.cache_key).open("wb") as handle:
                pickle.dump(policy_rate, handle)
        except Exception as exc:
            self.logger.warning("fed policy cache write failed error=%s", exc)

    def _mock_policy_rate(self) -> FedPolicyRate:
        return FedPolicyRate(
            lower_bound=4.25,
            upper_bound=4.50,
            policy_status="限制性",
            last_action="暂停",
            next_fomc_date=DEFAULT_NEXT_FOMC_DATE,
            source_state="mock",
            provider="mock",
            message="FRED 暂不可用，使用 fallback/mock 数据。",
        )

