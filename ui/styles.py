"""CSS styles for the Streamlit dashboard."""

import streamlit as st


def apply_dark_theme() -> None:
    """Inject a compact terminal-style dark theme."""

    st.markdown(
        """
        <style>
        .stApp { background: #05070b; color: #e5edf7; }
        [data-testid="stHeader"] {
            background: rgba(5, 7, 11, 0.92);
            height: 2.75rem;
        }
        [data-testid="collapsedControl"] {
            top: 0.45rem;
            left: 0.5rem;
            z-index: 999;
        }
        .block-container {
            max-width: 1440px;
            padding-top: 3.35rem;
            padding-bottom: 2rem;
        }
        .terminal-topbar {
            border: 1px solid #263244;
            background: linear-gradient(180deg, #0d1420 0%, #080d14 100%);
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 10px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        }
        .terminal-brand {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
        }
        .terminal-title {
            color: #f8fafc;
            font-size: 25px;
            font-weight: 780;
            line-height: 1.25;
            letter-spacing: 0;
        }
        .terminal-subtitle { color: #94a3b8; font-size: 12px; }
        .terminal-strip { display: flex; flex-wrap: wrap; gap: 6px; }
        .terminal-chip {
            border: 1px solid #334155;
            background: #0b111a;
            color: #cbd5e1;
            border-radius: 4px;
            padding: 4px 7px;
            font-size: 12px;
            font-weight: 720;
            line-height: 1.2;
        }
        .terminal-chip.live { color: #04130b; background: #32d583; border-color: #32d583; }
        .terminal-chip.warn { color: #180a06; background: #f97316; border-color: #f97316; }
        .terminal-chip.risk-on { color: #32d583; border-color: #166534; background: #07140d; }
        .terminal-chip.risk-off { color: #ff5f57; border-color: #7f1d1d; background: #160909; }
        .card {
            position: relative;
            border: 1px solid #243244;
            background: #0b111a;
            border-radius: 6px;
            padding: 11px;
            min-height: 92px;
        }
        .index-card { min-height: 108px; }
        .compact-card { min-height: 78px; }
        .card-title {
            color: #94a3b8;
            font-size: 11px;
            padding-right: 82px;
            margin-bottom: 5px;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .card-note { color: #64748b; font-size: 11px; margin-top: 4px; }
        .card-explain {
            color: #cbd5e1;
            font-size: 11px;
            line-height: 1.35;
            margin-top: 7px;
        }
        .breadth-caption {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 720;
            margin: 2px 0 8px 0;
            letter-spacing: 0.01em;
        }
        .breadth-caption.market { margin-top: 10px; color: #fbbf24; }
        .reserved-card {
            border-style: dashed;
            background: #070b11;
        }
        .metric-value { color: #f8fafc; font-size: 24px; font-weight: 760; line-height: 1.1; }
        .macro-value, .breadth-value { color: #f8fafc; font-size: 19px; font-weight: 740; line-height: 1.15; }
        .metric-delta-pos { color: #32d583; font-size: 13px; font-weight: 720; margin-top: 5px; }
        .metric-delta-neg { color: #ff5f57; font-size: 13px; font-weight: 720; margin-top: 5px; }
        .return-row, .ticker-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .return-pill, .ticker-pill {
            border: 1px solid #2b394d;
            background: #070b11;
            border-radius: 4px;
            padding: 3px 7px;
            font-size: 11px;
            font-weight: 680;
        }
        .return-pill { color: #cbd5e1; }
        .badge {
            display: inline-block;
            border: 1px solid #334155;
            background: #0b111a;
            color: #e5edf7;
            border-radius: 4px;
            padding: 5px 8px;
            margin: 5px 5px 3px 0;
            font-size: 12px;
            font-weight: 760;
        }
        .status-badge {
            position: absolute;
            top: 8px;
            right: 8px;
            border: 1px solid #334155;
            background: #070b11;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            line-height: 1.2;
            font-weight: 800;
            white-space: nowrap;
        }
        .status-realtime { color: #32d583; border-color: #166534; }
        .status-cached { color: #fbbf24; border-color: #854d0e; }
        .status-mock { color: #60a5fa; border-color: #1d4ed8; }
        .status-error { color: #ff5f57; border-color: #7f1d1d; }
        .status-meta {
            color: #64748b;
            font-size: 10px;
            line-height: 1.25;
            margin-top: 4px;
        }
        .health-strip {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 6px;
            border: 1px solid #243244;
            background: #070b11;
            border-radius: 6px;
            padding: 7px 9px;
            margin: 0 0 10px 0;
        }
        .health-title {
            color: #cbd5e1;
            font-size: 12px;
            font-weight: 800;
            margin-right: 4px;
        }
        .health-chip {
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 3px 7px;
            font-size: 11px;
            font-weight: 760;
            background: #0b111a;
        }
        .morning-panel {
            border: 1px solid #243244;
            background: #070b11;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .morning-title {
            color: #fbbf24;
            font-size: 12px;
            font-weight: 820;
            margin-bottom: 8px;
            letter-spacing: 0.02em;
        }
        .morning-conclusion {
            border: 1px solid #334155;
            background: #0b111a;
            border-radius: 6px;
            padding: 9px 11px;
            margin-top: 8px;
        }
        .morning-conclusion span {
            display: block;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 760;
            margin-bottom: 4px;
        }
        .morning-conclusion strong {
            color: #f8fafc;
            font-size: 14px;
            line-height: 1.35;
        }
        .stats-summary {
            border: 1px solid #243244;
            background: #070b11;
            border-radius: 6px;
            padding: 9px 11px;
            margin-bottom: 8px;
            color: #e5edf7;
            font-size: 13px;
            font-weight: 720;
        }
        .stats-table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #243244;
            background: #080d14;
            border-radius: 6px;
            overflow: hidden;
            font-size: 12px;
        }
        .stats-table th {
            color: #94a3b8;
            background: #0b111a;
            border-bottom: 1px solid #243244;
            padding: 8px 7px;
            text-align: left;
            font-weight: 780;
            vertical-align: bottom;
        }
        .stats-table td {
            color: #d8e1ec;
            border-bottom: 1px solid #182233;
            padding: 8px 7px;
            white-space: nowrap;
        }
        .stats-table tr:last-child td { border-bottom: 0; }
        .th-sub {
            display: block;
            color: #64748b;
            font-size: 10px;
            font-weight: 620;
            margin-top: 2px;
            line-height: 1.25;
        }
        .ratio-badge {
            display: inline-block;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 800;
            border: 1px solid #334155;
            background: #070b11;
        }
        .ratio-high { color: #32d583; border-color: #166534; }
        .ratio-normal { color: #cbd5e1; border-color: #334155; }
        .ratio-low { color: #fbbf24; border-color: #854d0e; }
        .section-kpi {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid #243244;
            background: #080d14;
            border-radius: 6px;
            padding: 9px 11px;
            margin-bottom: 8px;
            color: #cbd5e1;
            font-size: 12px;
            letter-spacing: 0.02em;
        }
        .section-kpi strong { font-size: 18px; }
        .heatmap-grid {
            display: grid;
            grid-template-columns: repeat(7, minmax(120px, 1fr));
            gap: 6px;
        }
        .heat-cell {
            position: relative;
            border: 1px solid #243244;
            border-radius: 6px;
            padding: 10px;
            min-height: 92px;
        }
        .heat-rank { color: #cbd5e1; font-size: 11px; font-weight: 760; }
        .heat-ticker { color: #f8fafc; font-size: 18px; font-weight: 780; margin-top: 4px; }
        .heat-change { font-size: 16px; font-weight: 780; margin-top: 2px; }
        .heat-meta { color: #cbd5e1; font-size: 11px; margin-top: 6px; }
        .heat-up-strong { background: #063d24; border-color: #15803d; }
        .heat-up { background: #082817; border-color: #166534; }
        .heat-down-strong { background: #4c0b0b; border-color: #991b1b; }
        .heat-down { background: #2b0e0e; border-color: #7f1d1d; }
        .heat-flat { background: #0b111a; border-color: #334155; }
        .decision-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(150px, 1fr));
            gap: 6px;
        }
        .decision-cell {
            position: relative;
            border: 1px solid #243244;
            background: #080d14;
            border-radius: 6px;
            padding: 10px;
            min-height: 86px;
        }
        .decision-label {
            color: #94a3b8;
            font-size: 11px;
            font-weight: 760;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .decision-value {
            color: #f8fafc;
            font-size: 14px;
            font-weight: 760;
            line-height: 1.35;
        }
        .terminal-note {
            position: relative;
            border: 1px solid #243244;
            background: #080d14;
            border-radius: 6px;
            padding: 11px 13px;
            min-height: 142px;
        }
        .terminal-note-title {
            color: #fbbf24;
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .terminal-note ul {
            margin: 0;
            padding-left: 17px;
            color: #d8e1ec;
            font-size: 13px;
            line-height: 1.45;
        }
        h2, h3 { color: #f3f6fa; letter-spacing: 0; margin-top: 0.65rem; }
        div[data-testid="stDataFrame"] { font-size: 12px; }
        .stRadio > div { gap: 10px; }
        @media (max-width: 900px) {
            .heatmap-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .decision-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
            .terminal-brand { display: block; }
            .terminal-subtitle { display: block; margin-top: 3px; }
        }
        @media (max-width: 760px) {
            .block-container { padding-top: 3.7rem; padding-left: 0.75rem; padding-right: 0.75rem; }
            .terminal-title { font-size: 21px; line-height: 1.32; }
            .terminal-chip { font-size: 11px; }
            .metric-value { font-size: 22px; }
            .macro-value, .breadth-value { font-size: 18px; }
            .card { padding: 10px; min-height: auto; }
            .heatmap-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
