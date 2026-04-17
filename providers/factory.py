"""Backward-compatible provider factory entrypoint.

New code should use data_repository.DataRepository directly.
"""

from __future__ import annotations

from providers.base import ProviderResult
from providers.universe import DEFAULT_SERIES


def load_market_data(provider_name: str | None = None) -> ProviderResult:
    """Delegate legacy callers to the repository-backed data layer."""

    from data_repository import DataRepository
    from utils.config import load_config

    config = load_config()
    if provider_name:
        config = config.__class__(
            provider_name=provider_name,
            alpha_vantage_api_key=config.alpha_vantage_api_key,
            market_api_key=config.market_api_key,
            cache_dir=config.cache_dir,
            log_dir=config.log_dir,
            cache_ttl_quote=config.cache_ttl_quote,
            cache_ttl_macro=config.cache_ttl_macro,
            cache_ttl_stats=config.cache_ttl_stats,
            debug_data=config.debug_data,
        )
    result = DataRepository(config).load_market_data(DEFAULT_SERIES)
    return ProviderResult(
        datasets=result.datasets,
        source_name=result.source_name,
        is_mock=result.is_mock,
        warning=result.warning,
    )
