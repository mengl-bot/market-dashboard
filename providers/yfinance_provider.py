"""Real market-data provider backed by yfinance."""

from __future__ import annotations

import pandas as pd

from providers.base import IndexConfig, IndexDataset, ProviderResult


class YFinanceProvider:
    """Fetch market data from Yahoo Finance through yfinance."""

    source_name = "Yahoo Finance / yfinance"

    def fetch_indices(self, indices: list[IndexConfig]) -> ProviderResult:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("Missing yfinance dependency. Install requirements.txt first.") from exc

        datasets: dict[str, IndexDataset] = {}
        errors: dict[str, str] = {}
        ticker_map = {config.ticker: config for config in indices}

        try:
            raw = yf.download(
                tickers=list(ticker_map),
                period="1y",
                interval="1d",
                auto_adjust=False,
                group_by="ticker",
                threads=True,
                progress=False,
            )
        except Exception as exc:
            return ProviderResult(
                datasets={},
                source_name=self.source_name,
                errors={config.key: str(exc) for config in indices},
            )

        for ticker, config in ticker_map.items():
            try:
                ticker_raw = self._slice_ticker(raw, ticker, len(ticker_map) == 1)
                history = self._normalize_history(ticker_raw, config)
                if history.empty:
                    raise RuntimeError("empty history")
                datasets[config.key] = IndexDataset(config=config, history=history, provider=self.source_name)
            except Exception as exc:
                errors[config.key] = str(exc)

        return ProviderResult(datasets=datasets, source_name=self.source_name, errors=errors)

    @staticmethod
    def _slice_ticker(raw: pd.DataFrame, ticker: str, single: bool) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame()
        if single or not isinstance(raw.columns, pd.MultiIndex):
            return raw
        if ticker not in raw.columns.get_level_values(0):
            return pd.DataFrame()
        return raw[ticker]

    @staticmethod
    def _normalize_history(raw: pd.DataFrame, config: IndexConfig) -> pd.DataFrame:
        """Convert provider-specific columns into the app's canonical schema."""

        if raw is None or raw.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        frame = raw.reset_index()
        frame = frame.rename(
            columns={
                "Date": "date",
                "Datetime": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        required = ["date", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in frame.columns:
                frame[col] = 0 if col == "volume" else pd.NA

        frame = frame[required].copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)

        for col in ["open", "high", "low", "close", "volume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

        if config.key in {"us10y", "us2y"}:
            for col in ["open", "high", "low", "close"]:
                frame.loc[frame[col] > 20, col] = frame.loc[frame[col] > 20, col] / 10

        frame = frame.dropna(subset=["date", "close"]).sort_values("date")
        return frame.reset_index(drop=True)
