"""Provider interface definitions.

UI code should depend on this module instead of concrete data sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Protocol

import pandas as pd


@dataclass(frozen=True)
class IndexConfig:
    """Basic configuration for one index."""

    key: str
    name: str
    ticker: str
    category: str = "index"
    alpha_ticker: str | None = None


@dataclass
class IndexDataset:
    """Normalized dataset returned by every provider."""

    config: IndexConfig
    history: pd.DataFrame
    provider: str = "unknown"
    source_state: str = "live"
    cache_hit: bool = False
    cache_saved_at: float | None = None
    error: str | None = None


@dataclass
class ProviderResult:
    """Container returned to the Streamlit app."""

    datasets: Dict[str, IndexDataset]
    source_name: str
    is_mock: bool = False
    warning: str | None = None
    source_trail: list[str] | None = None
    errors: dict[str, str] = field(default_factory=dict)


class MarketDataProvider(Protocol):
    """Common contract for market-data providers."""

    source_name: str

    def fetch_indices(self, indices: list[IndexConfig]) -> ProviderResult:
        """Fetch normalized historical market data for the requested indices."""
