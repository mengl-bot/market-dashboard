"""Repository layer that owns caching, fallback, and data-source diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field

from providers.alpha_vantage_provider import AlphaVantageProvider
from providers.base import IndexConfig, IndexDataset, ProviderResult
from providers.mock_provider import MockMarketDataProvider
from providers.universe import DEFAULT_SERIES
from providers.yfinance_provider import YFinanceProvider
from utils.config import AppConfig, load_config
from utils.logging_config import setup_logging

from data_repository.cache import MarketDataCache
from data_repository.market_breadth import MarketBreadthRepository, MarketBreadthSnapshot


@dataclass
class DebugRow:
    """Per-symbol diagnostics surfaced by the debug panel."""

    key: str
    ticker: str
    category: str
    provider: str
    state: str
    cache_layer: str
    rows: int
    message: str = ""


@dataclass
class RepositoryResult:
    """Result returned to the app after repository processing."""

    datasets: dict[str, IndexDataset]
    source_name: str
    is_mock: bool
    warning: str | None
    market_breadth: dict[str, MarketBreadthSnapshot] = field(default_factory=dict)
    debug_rows: list[DebugRow] = field(default_factory=list)
    status_messages: list[str] = field(default_factory=list)


class DataRepository:
    """Single entry point for all market data used by UI and services."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self.logger = setup_logging(self.config.log_dir)
        self.cache = MarketDataCache(self.config.cache_dir, self.logger)
        self.yahoo = YFinanceProvider()
        self.alpha = AlphaVantageProvider(self.config.alpha_vantage_api_key or self.config.market_api_key)
        self.mock = MockMarketDataProvider()
        self.market_breadth = MarketBreadthRepository(self.cache, self.logger, self.config)

    def load_market_data(self, series: list[IndexConfig] | None = None) -> RepositoryResult:
        """Load all dashboard data with cache and per-symbol fallback."""

        configs = series or DEFAULT_SERIES
        datasets: dict[str, IndexDataset] = {}
        debug_rows: list[DebugRow] = []
        missing: list[IndexConfig] = []

        for config in configs:
            cache_key = self._cache_key(config)
            cached, layer = self.cache.get(cache_key, self._ttl_for(config))
            if cached is None:
                missing.append(config)
                continue
            dataset = IndexDataset(
                config=config,
                history=cached.history.copy(),
                provider=cached.provider,
                source_state="cache",
                cache_hit=True,
                cache_saved_at=cached.saved_at,
            )
            datasets[config.key] = dataset
            debug_rows.append(self._debug_row(dataset, layer or "memory"))

        if missing:
            live_result = self._fetch_primary(missing)
            self._merge_provider_result(live_result, datasets, debug_rows, "live")
            missing = [config for config in missing if config.key not in datasets]

        if missing and self.alpha.api_key and self.config.provider_name.lower() != "mock":
            alpha_result = self._fetch_alpha(missing)
            self._merge_provider_result(alpha_result, datasets, debug_rows, "live")
            missing = [config for config in missing if config.key not in datasets]

        if missing:
            for config in missing[:]:
                cache_key = self._cache_key(config)
                stale = self._stats_cache(config) or self.cache.get_stale(cache_key)
                if not stale:
                    continue
                dataset = IndexDataset(
                    config=config,
                    history=stale.history.copy(),
                    provider=stale.provider,
                    source_state="stale_cache",
                    cache_hit=True,
                    cache_saved_at=stale.saved_at,
                )
                datasets[config.key] = dataset
                debug_rows.append(self._debug_row(dataset, "stale"))
            missing = [config for config in missing if config.key not in datasets]

        if missing:
            mock_result = self.mock.fetch_indices(missing)
            for key, dataset in mock_result.datasets.items():
                dataset.provider = self.mock.source_name
                dataset.source_state = "mock"
                dataset.cache_hit = False
                datasets[key] = dataset
                debug_rows.append(self._debug_row(dataset, "none", "provider fallback"))
                self.logger.info("mock fallback key=%s ticker=%s", key, dataset.config.ticker)

        market_breadth = self.market_breadth.load_all()
        self._append_market_breadth_debug(market_breadth, debug_rows)

        status_messages = self._status_messages(configs, datasets)
        status_messages.extend(self._market_breadth_status(market_breadth))
        warning = "；".join(status_messages) if status_messages else None
        source_name = self._source_name(datasets)
        is_mock = all(dataset.source_state == "mock" for dataset in datasets.values()) if datasets else True
        return RepositoryResult(
            datasets=datasets,
            source_name=source_name,
            is_mock=is_mock,
            warning=warning,
            market_breadth=market_breadth,
            debug_rows=debug_rows,
            status_messages=status_messages,
        )

    def _fetch_primary(self, configs: list[IndexConfig]) -> ProviderResult:
        selected = self.config.provider_name.lower()
        if selected in {"mock", "demo"}:
            return ProviderResult(datasets={}, source_name="disabled")
        provider = self.alpha if selected in {"alpha", "alpha_vantage", "alphavantage"} and self.alpha.api_key else self.yahoo
        try:
            self.logger.info("provider request provider=%s symbols=%s", provider.source_name, [item.ticker for item in configs])
            return provider.fetch_indices(configs)
        except Exception as exc:
            self.logger.warning("provider batch failed provider=%s error=%s", provider.source_name, exc)
            return ProviderResult(datasets={}, source_name=provider.source_name, errors={item.key: str(exc) for item in configs})

    def _fetch_alpha(self, configs: list[IndexConfig]) -> ProviderResult:
        try:
            self.logger.info("provider fallback request provider=%s symbols=%s", self.alpha.source_name, [item.ticker for item in configs])
            return self.alpha.fetch_indices(configs)
        except Exception as exc:
            self.logger.warning("alpha fallback failed error=%s", exc)
            return ProviderResult(datasets={}, source_name=self.alpha.source_name, errors={item.key: str(exc) for item in configs})

    def _merge_provider_result(
        self,
        result: ProviderResult,
        datasets: dict[str, IndexDataset],
        debug_rows: list[DebugRow],
        state: str,
    ) -> None:
        for key, dataset in result.datasets.items():
            dataset.provider = result.source_name
            dataset.source_state = state
            dataset.cache_hit = False
            datasets[key] = dataset
            self.cache.set(self._cache_key(dataset.config), dataset.history, result.source_name)
            if dataset.config.category != "macro":
                self.cache.set(self._stats_cache_key(dataset.config), dataset.history, result.source_name)
            debug_rows.append(self._debug_row(dataset, "none"))

        for key, message in result.errors.items():
            self.logger.warning("symbol failed provider=%s key=%s error=%s", result.source_name, key, message)

    def _debug_row(self, dataset: IndexDataset, cache_layer: str, message: str = "") -> DebugRow:
        return DebugRow(
            key=dataset.config.key,
            ticker=dataset.config.ticker,
            category=dataset.config.category,
            provider=dataset.provider,
            state=dataset.source_state,
            cache_layer=cache_layer,
            rows=len(dataset.history),
            message=message,
        )

    def _cache_key(self, config: IndexConfig) -> str:
        return f"daily:1y:{config.key}:{config.ticker}:{config.category}"

    def _stats_cache_key(self, config: IndexConfig) -> str:
        return f"stats:1y:{config.key}:{config.ticker}:{config.category}"

    def _stats_cache(self, config: IndexConfig):
        if config.category == "macro":
            return None
        entry, layer = self.cache.get(self._stats_cache_key(config), self.config.cache_ttl_stats)
        if entry is not None:
            self.logger.info("stats cache fallback key=%s layer=%s", config.key, layer)
        return entry

    def _ttl_for(self, config: IndexConfig) -> int:
        if config.category == "macro":
            return self.config.cache_ttl_macro
        if config.category == "stats":
            return self.config.cache_ttl_stats
        return self.config.cache_ttl_quote

    def _status_messages(self, configs: list[IndexConfig], datasets: dict[str, IndexDataset]) -> list[str]:
        messages: list[str] = []
        states = {dataset.source_state for dataset in datasets.values()}
        if any(state in states for state in {"live", "cache", "stale_cache"}) and "mock" in states:
            messages.append("实时数据部分可用")
            messages.append("部分标的获取失败，已使用缓存或降级数据")
        elif "mock" in states:
            messages.append("实时数据不可用，当前使用 mock 数据")
        elif any(dataset.source_state in {"cache", "stale_cache"} for dataset in datasets.values()):
            messages.append("部分数据来自缓存")

        mock_modules = sorted({dataset.config.category for dataset in datasets.values() if dataset.source_state == "mock"})
        if mock_modules:
            messages.append(f"当前使用 mock 数据的模块：{', '.join(mock_modules)}")

        missing = [config.key for config in configs if config.key not in datasets]
        if missing:
            messages.append(f"部分模块暂无数据：{', '.join(missing)}")

        return messages

    def _append_market_breadth_debug(
        self,
        snapshots: dict[str, MarketBreadthSnapshot],
        debug_rows: list[DebugRow],
    ) -> None:
        for key, snapshot in snapshots.items():
            debug_rows.append(
                DebugRow(
                    key=f"breadth_{key}",
                    ticker=snapshot.label,
                    category="market_breadth",
                    provider=snapshot.provider,
                    state=snapshot.source_state,
                    cache_layer="cache" if snapshot.cache_hit else "none",
                    rows=snapshot.sampled_count or 0,
                    message=snapshot.message,
                )
            )

    def _market_breadth_status(self, snapshots: dict[str, MarketBreadthSnapshot]) -> list[str]:
        messages: list[str] = []
        cached = [snapshot.label for snapshot in snapshots.values() if snapshot.source_state in {"cache", "stale_cache"}]
        unavailable = [snapshot.label for snapshot in snapshots.values() if snapshot.source_state == "unavailable"]
        if cached:
            messages.append(f"全市场宽度使用缓存数据：{', '.join(cached)}")
        if unavailable:
            messages.append(f"全市场宽度暂不可用：{', '.join(unavailable)}")
        return messages

    def _source_name(self, datasets: dict[str, IndexDataset]) -> str:
        providers = sorted({dataset.provider for dataset in datasets.values()})
        return " / ".join(providers) if providers else "No Data"


def get_market_data() -> RepositoryResult:
    """Convenience function used by the Streamlit app."""

    return DataRepository().load_market_data()
