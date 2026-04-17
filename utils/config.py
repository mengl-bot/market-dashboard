"""Application configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings read from environment variables."""

    provider_name: str
    alpha_vantage_api_key: str | None
    market_api_key: str | None
    cache_dir: Path
    log_dir: Path
    cache_ttl_quote: int
    cache_ttl_macro: int
    cache_ttl_stats: int
    debug_data: bool


def load_config() -> AppConfig:
    """Read all supported environment variables in one place."""

    return AppConfig(
        provider_name=os.getenv("MARKET_DATA_PROVIDER", "yfinance"),
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
        market_api_key=os.getenv("MARKET_API_KEY"),
        cache_dir=Path(os.getenv("CACHE_DIR", "cache")),
        log_dir=Path(os.getenv("LOG_DIR", "logs")),
        cache_ttl_quote=_get_int("CACHE_TTL_QUOTE", 300),
        cache_ttl_macro=_get_int("CACHE_TTL_MACRO", 900),
        cache_ttl_stats=_get_int("CACHE_TTL_STATS", 86400),
        debug_data=os.getenv("DEBUG_DATA", "0").lower() in {"1", "true", "yes", "on"},
    )


def get_provider_name() -> str:
    """Read provider selection from environment variables."""

    return load_config().provider_name


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
