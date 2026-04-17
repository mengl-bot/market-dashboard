"""Alpha Vantage provider used as the secondary real-data fallback."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from providers.base import IndexConfig, IndexDataset, ProviderResult


class AlphaVantageProvider:
    """Fetch daily series from Alpha Vantage."""

    source_name = "Alpha Vantage"
    base_url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("MARKET_API_KEY")

    def fetch_indices(self, indices: list[IndexConfig]) -> ProviderResult:
        if not self.api_key:
            raise RuntimeError("Missing ALPHA_VANTAGE_API_KEY or MARKET_API_KEY")

        datasets: dict[str, IndexDataset] = {}
        errors: dict[str, str] = {}

        for config in indices:
            try:
                history = self._fetch_treasury_yield(config) if config.key in {"us10y", "us2y"} else self._fetch_daily(config)
                if history.empty:
                    raise RuntimeError(f"{config.name} returned empty data")
                datasets[config.key] = IndexDataset(config=config, history=history, provider=self.source_name)
            except Exception as exc:
                errors[config.key] = str(exc)

        return ProviderResult(datasets=datasets, source_name=self.source_name, errors=errors)

    def _fetch_daily(self, config: IndexConfig) -> pd.DataFrame:
        payload = self._request(
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": config.alpha_ticker or config.ticker,
                "outputsize": "full",
            }
        )
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            message = payload.get("Note") or payload.get("Information") or payload.get("Error Message") or "missing series"
            raise RuntimeError(str(message))

        rows = [
            {
                "date": pd.to_datetime(date_text),
                "open": values.get("1. open"),
                "high": values.get("2. high"),
                "low": values.get("3. low"),
                "close": values.get("4. close"),
                "volume": values.get("5. volume", 0),
            }
            for date_text, values in series.items()
        ]
        return self._normalize(pd.DataFrame(rows)).tail(380).reset_index(drop=True)

    def _fetch_treasury_yield(self, config: IndexConfig) -> pd.DataFrame:
        payload = self._request(
            {
                "function": "TREASURY_YIELD",
                "interval": "daily",
                "maturity": "10year" if config.key == "us10y" else "2year",
            }
        )
        records = payload.get("data")
        if not isinstance(records, list):
            message = payload.get("Note") or payload.get("Information") or payload.get("Error Message") or "missing yield data"
            raise RuntimeError(str(message))

        rows = []
        for item in records:
            value = pd.to_numeric(item.get("value"), errors="coerce")
            if pd.isna(value):
                continue
            rows.append(
                {
                    "date": pd.to_datetime(item.get("date")),
                    "open": value,
                    "high": value,
                    "low": value,
                    "close": value,
                    "volume": 0,
                }
            )
        return self._normalize(pd.DataFrame(rows)).tail(380).reset_index(drop=True)

    def _request(self, params: dict[str, str]) -> dict:
        query = urlencode({**params, "apikey": self.api_key})
        with urlopen(f"{self.base_url}?{query}", timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        frame = frame[["date", "open", "high", "low", "close", "volume"]].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
        for col in ["open", "high", "low", "close", "volume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame.dropna(subset=["date", "close"]).sort_values("date")
