"""Deterministic mock data provider used as a safe fallback."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from providers.base import IndexConfig, IndexDataset, ProviderResult


class MockMarketDataProvider:
    """Generate realistic-looking market data when real providers fail."""

    source_name = "Mock Data"

    def fetch_indices(self, indices: list[IndexConfig]) -> ProviderResult:
        datasets: dict[str, IndexDataset] = {}
        today = pd.Timestamp(date.today())
        dates = pd.bdate_range(end=today, periods=2600)

        for idx, config in enumerate(indices):
            rng = np.random.default_rng(20260416 + idx)
            history = _mock_history(config, dates, rng)
            datasets[config.key] = IndexDataset(
                config=config,
                history=history,
                provider=self.source_name,
                source_state="mock",
            )

        return ProviderResult(
            datasets=datasets,
            source_name=self.source_name,
            is_mock=True,
            warning="真实行情数据不可用，当前展示 Mock 演示数据。",
        )


def _mock_history(config: IndexConfig, dates: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    profile = {
        "nasdaq": (14500, 0.00045, 0.014, 5_300_000_000),
        "nasdaq100": (430, 0.00044, 0.013, 48_000_000),
        "sp500": (5000, 0.00032, 0.009, 3_900_000_000),
        "vix": (16.5, -0.00005, 0.035, 0),
        "us10y": (4.35, 0.00002, 0.010, 0),
        "us2y": (4.78, -0.00001, 0.009, 0),
        "equal_weight": (165, 0.00022, 0.010, 8_000_000),
        "cap_weight": (505, 0.00032, 0.009, 72_000_000),
        "aapl": (195, 0.00028, 0.018, 62_000_000),
        "msft": (430, 0.00035, 0.017, 24_000_000),
        "nvda": (890, 0.00062, 0.031, 45_000_000),
        "amzn": (182, 0.00034, 0.020, 38_000_000),
        "googl": (155, 0.00030, 0.018, 28_000_000),
        "meta": (505, 0.00042, 0.022, 18_000_000),
        "tsla": (175, 0.00010, 0.033, 96_000_000),
        "xlk": (235, 0.00042, 0.014, 9_000_000),
        "xlf": (43, 0.00024, 0.011, 34_000_000),
        "xle": (92, 0.00012, 0.015, 16_000_000),
        "xlv": (148, 0.00018, 0.009, 8_000_000),
        "xli": (126, 0.00025, 0.010, 8_000_000),
        "xly": (190, 0.00030, 0.013, 5_000_000),
        "xlc": (87, 0.00036, 0.014, 6_000_000),
        "xlp": (78, 0.00010, 0.007, 10_000_000),
        "xlu": (70, 0.00008, 0.008, 11_000_000),
        "xlre": (40, 0.00008, 0.012, 7_000_000),
    }
    start_price, drift, volatility, volume_base = profile.get(config.key, (100, 0.0002, 0.012, 1_000_000))

    daily_returns = rng.normal(drift, volatility, len(dates))
    close = start_price * np.cumprod(1 + daily_returns)
    high = close * (1 + rng.uniform(0.001, 0.018, len(dates)))
    low = close * (1 - rng.uniform(0.001, 0.018, len(dates)))
    open_ = close / (1 + daily_returns)
    volume = volume_base * rng.uniform(0.72, 1.38, len(dates)) if volume_base else np.zeros(len(dates))

    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume.astype("int64"),
        }
    )
