"""Constituent-level market breadth with cache-first fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from data_repository.cache import MarketDataCache
from utils.config import AppConfig


CONSTITUENT_TTL_SECONDS = 86400
WIKIPEDIA_SOURCES = {
    "sp500": {
        "label": "标普500涨跌比",
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "columns": ("Symbol", "Ticker"),
        "min_count": 450,
    },
    "nasdaq100": {
        "label": "纳指100涨跌比",
        "url": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "columns": ("Ticker", "Symbol"),
        "min_count": 90,
    },
}


@dataclass
class MarketBreadthSnapshot:
    """A/D snapshot for one broad-market universe."""

    key: str
    label: str
    advances: int | None = None
    declines: int | None = None
    unchanged: int | None = None
    total_count: int | None = None
    sampled_count: int | None = None
    provider: str = "Unavailable"
    source_state: str = "unavailable"
    cache_hit: bool = False
    message: str = "暂无可用数据"


class MarketBreadthRepository:
    """Load S&P 500 and Nasdaq-100 A/D through yfinance batch requests."""

    def __init__(self, cache: MarketDataCache, logger, config: AppConfig) -> None:
        self.cache = cache
        self.logger = logger
        self.config = config
        self.quote_ttl = min(max(int(config.cache_ttl_quote or 300), 300), 900)

    def load_all(self) -> dict[str, MarketBreadthSnapshot]:
        """Return breadth snapshots for all supported broad-market universes."""

        return {key: self.load_universe(key) for key in WIKIPEDIA_SOURCES}

    def load_universe(self, key: str) -> MarketBreadthSnapshot:
        """Load one market breadth universe with fresh cache, live, stale fallback."""

        source = WIKIPEDIA_SOURCES[key]
        label = source["label"]
        cached_counts = self._get_cached_counts(key, label)
        if cached_counts:
            return cached_counts

        tickers, constituent_state = self._load_constituents(key)
        if not tickers:
            stale = self._get_stale_counts(key, label, "成分股列表不可用，使用最近缓存数据")
            if stale:
                return stale
            return MarketBreadthSnapshot(key=key, label=label, message="成分股列表暂不可用")

        try:
            snapshot = self._fetch_counts(key, label, tickers)
            snapshot.message = self._message(snapshot, constituent_state)
            self._cache_counts(snapshot)
            return snapshot
        except Exception as exc:
            self.logger.warning("market breadth live failed key=%s error=%s", key, exc)
            stale = self._get_stale_counts(key, label, "实时获取失败，使用缓存数据")
            if stale:
                return stale
            return MarketBreadthSnapshot(key=key, label=label, total_count=len(tickers), message="实时获取失败，暂无缓存")

    def _load_constituents(self, key: str) -> tuple[list[str], str]:
        cache_key = f"market-breadth:constituents:{key}"
        entry, layer = self.cache.get(cache_key, CONSTITUENT_TTL_SECONDS)
        if entry is not None:
            tickers = self._tickers_from_frame(entry.history)
            self.logger.info("market breadth constituents cache hit key=%s layer=%s count=%s", key, layer, len(tickers))
            return tickers, "成分股列表来自缓存"

        try:
            tickers = self._fetch_constituents(key)
            frame = pd.DataFrame({"ticker": tickers})
            self.cache.set(cache_key, frame, "Wikipedia")
            self.logger.info("market breadth constituents live key=%s count=%s", key, len(tickers))
            return tickers, "成分股列表已更新"
        except Exception as exc:
            self.logger.warning("market breadth constituents failed key=%s error=%s", key, exc)
            stale = self.cache.get_stale(cache_key)
            if stale is None:
                return [], "成分股列表不可用"
            tickers = self._tickers_from_frame(stale.history)
            return tickers, "成分股列表使用缓存"

    def _fetch_constituents(self, key: str) -> list[str]:
        source = WIKIPEDIA_SOURCES[key]
        tables = pd.read_html(source["url"])
        candidates: list[str] = []
        for table in tables:
            columns = {str(column).strip(): column for column in table.columns}
            matched_column = next((columns[name] for name in source["columns"] if name in columns), None)
            if matched_column is None:
                continue
            tickers = self._normalize_tickers(table[matched_column].dropna().astype(str).tolist())
            if len(tickers) > len(candidates):
                candidates = tickers
        if len(candidates) < int(source["min_count"]):
            raise RuntimeError(f"constituent source returned {len(candidates)} tickers")
        return candidates

    def _fetch_counts(self, key: str, label: str, tickers: list[str]) -> MarketBreadthSnapshot:
        closes = self._download_recent_closes(tickers)
        advances = declines = unchanged = sampled = 0
        for ticker in tickers:
            if ticker not in closes.columns:
                continue
            values = pd.to_numeric(closes[ticker], errors="coerce").dropna()
            if len(values) < 2:
                continue
            sampled += 1
            previous = float(values.iloc[-2])
            latest = float(values.iloc[-1])
            if latest > previous:
                advances += 1
            elif latest < previous:
                declines += 1
            else:
                unchanged += 1

        if sampled == 0:
            raise RuntimeError("no valid close pairs for breadth calculation")

        return MarketBreadthSnapshot(
            key=key,
            label=label,
            advances=advances,
            declines=declines,
            unchanged=unchanged,
            total_count=len(tickers),
            sampled_count=sampled,
            provider="Yahoo Finance / yfinance",
            source_state="live",
            cache_hit=False,
        )

    def _download_recent_closes(self, tickers: list[str]) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("Missing yfinance dependency") from exc

        frames: list[pd.Series] = []
        for chunk in self._chunks(tickers, 90):
            raw = yf.download(
                tickers=chunk,
                period="5d",
                interval="1d",
                auto_adjust=False,
                group_by="ticker",
                threads=True,
                progress=False,
            )
            if raw is None or raw.empty:
                continue
            frames.extend(self._close_series_from_raw(raw, chunk))

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1)

    def _close_series_from_raw(self, raw: pd.DataFrame, tickers: list[str]) -> list[pd.Series]:
        frames: list[pd.Series] = []
        single = len(tickers) == 1 or not isinstance(raw.columns, pd.MultiIndex)
        for ticker in tickers:
            if single:
                close = raw.get("Close")
            elif ticker in raw.columns.get_level_values(0):
                close = raw[ticker].get("Close")
            else:
                close = None
            if close is None:
                continue
            series = pd.to_numeric(close, errors="coerce").dropna().tail(2)
            if not series.empty:
                series.name = ticker
                frames.append(series)
        return frames

    def _get_cached_counts(self, key: str, label: str) -> MarketBreadthSnapshot | None:
        entry, layer = self.cache.get(self._counts_cache_key(key), self.quote_ttl)
        if entry is None:
            return None
        snapshot = self._snapshot_from_frame(key, label, entry.history, entry.provider, "cache", True)
        snapshot.message = f"使用缓存数据，有效样本 {snapshot.sampled_count or 0}/{snapshot.total_count or 0}"
        self.logger.info("market breadth counts cache hit key=%s layer=%s", key, layer)
        return snapshot

    def _get_stale_counts(self, key: str, label: str, message: str) -> MarketBreadthSnapshot | None:
        entry = self.cache.get_stale(self._counts_cache_key(key))
        if entry is None:
            return None
        snapshot = self._snapshot_from_frame(key, label, entry.history, entry.provider, "stale_cache", True)
        snapshot.message = f"{message}，有效样本 {snapshot.sampled_count or 0}/{snapshot.total_count or 0}"
        return snapshot

    def _cache_counts(self, snapshot: MarketBreadthSnapshot) -> None:
        frame = pd.DataFrame(
            [
                {
                    "advances": snapshot.advances,
                    "declines": snapshot.declines,
                    "unchanged": snapshot.unchanged,
                    "total_count": snapshot.total_count,
                    "sampled_count": snapshot.sampled_count,
                    "message": snapshot.message,
                }
            ]
        )
        self.cache.set(self._counts_cache_key(snapshot.key), frame, snapshot.provider)

    def _snapshot_from_frame(
        self,
        key: str,
        label: str,
        frame: pd.DataFrame,
        provider: str,
        source_state: str,
        cache_hit: bool,
    ) -> MarketBreadthSnapshot:
        row = frame.iloc[-1] if not frame.empty else {}
        return MarketBreadthSnapshot(
            key=key,
            label=label,
            advances=self._int_or_none(row.get("advances")),
            declines=self._int_or_none(row.get("declines")),
            unchanged=self._int_or_none(row.get("unchanged")),
            total_count=self._int_or_none(row.get("total_count")),
            sampled_count=self._int_or_none(row.get("sampled_count")),
            provider=provider,
            source_state=source_state,
            cache_hit=cache_hit,
            message=str(row.get("message") or "使用缓存数据"),
        )

    def _message(self, snapshot: MarketBreadthSnapshot, constituent_state: str) -> str:
        sampled = snapshot.sampled_count or 0
        total = snapshot.total_count or 0
        return f"实时数据，{constituent_state}，有效样本 {sampled}/{total}"

    def _counts_cache_key(self, key: str) -> str:
        return f"market-breadth:counts:{key}:2d-close"

    @staticmethod
    def _tickers_from_frame(frame: pd.DataFrame) -> list[str]:
        if frame.empty or "ticker" not in frame.columns:
            return []
        return MarketBreadthRepository._normalize_tickers(frame["ticker"].dropna().astype(str).tolist())

    @staticmethod
    def _normalize_tickers(values: Iterable[str]) -> list[str]:
        tickers: list[str] = []
        seen: set[str] = set()
        for value in values:
            ticker = value.strip().upper().replace(".", "-")
            if not ticker or ticker in seen or " " in ticker:
                continue
            seen.add(ticker)
            tickers.append(ticker)
        return tickers

    @staticmethod
    def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
        for index in range(0, len(values), size):
            yield values[index : index + size]

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        try:
            if pd.isna(value):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
