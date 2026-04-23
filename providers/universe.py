"""Dashboard symbol universe."""

from __future__ import annotations

from providers.base import IndexConfig


DEFAULT_SERIES = [
    IndexConfig(key="nasdaq", name="NASDAQ Composite", ticker="^IXIC", category="index", alpha_ticker="QQQ"),
    IndexConfig(key="sp500", name="S&P 500", ticker="^GSPC", category="index", alpha_ticker="SPY"),
    IndexConfig(key="vix", name="VIX", ticker="^VIX", category="macro", alpha_ticker="VIXY"),
    IndexConfig(key="us10y", name="US 10Y Yield", ticker="^TNX", category="macro"),
    IndexConfig(key="us2y", name="US 2Y Yield", ticker="^UST2Y", category="macro"),
    IndexConfig(key="xlk", name="Technology", ticker="XLK", category="sector"),
    IndexConfig(key="xlf", name="Financials", ticker="XLF", category="sector"),
    IndexConfig(key="xle", name="Energy", ticker="XLE", category="sector"),
    IndexConfig(key="xlv", name="Health Care", ticker="XLV", category="sector"),
    IndexConfig(key="xli", name="Industrials", ticker="XLI", category="sector"),
    IndexConfig(key="xly", name="Consumer Discretionary", ticker="XLY", category="sector"),
    IndexConfig(key="xlp", name="Consumer Staples", ticker="XLP", category="sector"),
    IndexConfig(key="xlu", name="Utilities", ticker="XLU", category="sector"),
    IndexConfig(key="xlre", name="Real Estate", ticker="XLRE", category="sector"),
    IndexConfig(key="aapl", name="AAPL", ticker="AAPL", category="mega_cap"),
    IndexConfig(key="msft", name="MSFT", ticker="MSFT", category="mega_cap"),
    IndexConfig(key="nvda", name="NVDA", ticker="NVDA", category="mega_cap"),
    IndexConfig(key="amzn", name="AMZN", ticker="AMZN", category="mega_cap"),
    IndexConfig(key="googl", name="GOOGL", ticker="GOOGL", category="mega_cap"),
    IndexConfig(key="meta", name="META", ticker="META", category="mega_cap"),
    IndexConfig(key="tsla", name="TSLA", ticker="TSLA", category="mega_cap"),
    IndexConfig(key="equal_weight", name="S&P 500 Equal Weight", ticker="RSP", category="breadth"),
    IndexConfig(key="cap_weight", name="S&P 500 Cap Weight", ticker="SPY", category="breadth"),
]
