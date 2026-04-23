"""Valuation model inputs and scoring thresholds.

Fallback valuation inputs are deliberately centralized here because the current
data pipeline does not yet ingest a paid fundamentals API.
"""

VALUATION_FALLBACKS = {
    "forward_pe": 21.5,
    "trailing_pe": 26.0,
    "cape": None,
    "historical_percentile": 72.0,
    "source": "mock_config",
}

VALUATION_SCORE_RANGES = [
    {"min": 0, "max": 25, "label": "低估"},
    {"min": 26, "max": 50, "label": "合理"},
    {"min": 51, "max": 75, "label": "偏贵"},
    {"min": 76, "max": 100, "label": "高估"},
]

VALUATION_SCORING = {
    "forward_pe": [
        {"max": 16, "score": 15},
        {"max": 19, "score": 35},
        {"max": 23, "score": 60},
        {"max": 28, "score": 80},
        {"max": 999, "score": 95},
    ],
    "erp": [
        {"min": 4.0, "score": 15},
        {"min": 3.0, "score": 35},
        {"min": 2.0, "score": 55},
        {"min": 1.0, "score": 75},
        {"min": -999, "score": 92},
    ],
    "historical_percentile_weight": 0.30,
    "forward_pe_weight": 0.45,
    "erp_weight": 0.25,
}

