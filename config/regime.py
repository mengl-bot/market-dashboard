"""Rule thresholds for V4 market regime classification."""

REGIME_THRESHOLDS = {
    "vix_risk_off": 22.0,
    "vix_risk_on": 16.0,
    "rate_pressure_daily_change": 0.04,
    "leader_concentration_high": 0.65,
    "leader_concentration_low": 0.45,
    "sector_positive_count": 5,
    "breadth_adv_decl_ratio": 1.15,
    "index_uptrend_return": 0.35,
    "earnings_driver_valuation_score_max": 60,
}

DCA_MULTIPLIERS = {
    "低估": 1.5,
    "合理": 1.0,
    "偏贵": 0.7,
    "高估": 0.5,
}

