"""Streamlit entrypoint for the US index comparison dashboard."""

from __future__ import annotations

import os
import traceback

import streamlit as st


def main() -> None:
    """Build the dashboard page or a minimal deployment test page."""

    st.set_page_config(
        page_title="美股指数专业看板 V3",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    if os.getenv("DEPLOY_TEST_MODE", "0").lower() in {"1", "true", "yes", "on"}:
        st.title("Deploy Test Success")
        st.caption("Streamlit app booted without loading data providers, charts, or custom dashboard modules.")
        return

    try:
        _render_dashboard()
    except Exception as exc:
        st.error("应用启动失败。请查看 Render 日志或下方错误摘要。")
        st.exception(exc)
        with st.expander("Traceback", expanded=False):
            st.code(traceback.format_exc())
        raise


def _render_dashboard() -> None:
    """Render the full dashboard with lazy imports for deploy diagnostics."""

    from data_repository import DataRepository
    from services.analytics import calculate_market_analytics
    from services.summary import generate_chinese_summary
    from ui.components import (
        render_badges,
        render_breadth_section,
        render_data_debug,
        render_decision_matrix,
        render_macro_strip,
        render_mega_cap_section,
        render_overview,
        render_price_chart,
        render_stats,
        render_summary,
        render_terminal_status_bar,
    )
    from ui.styles import apply_dark_theme
    from utils.config import load_config

    apply_dark_theme()

    config = load_config()
    debug_enabled = st.sidebar.toggle("Data debug", value=config.debug_data)

    with st.spinner("正在加载市场数据..."):
        provider_result = DataRepository(config).load_market_data()

    analytics = calculate_market_analytics(provider_result.datasets, provider_result.market_breadth)
    summary_sections = generate_chinese_summary(analytics)

    render_terminal_status_bar(analytics, provider_result.source_name, provider_result.is_mock)
    if provider_result.warning:
        st.info(provider_result.warning)

    if debug_enabled:
        with st.expander("Data repository debug", expanded=True):
            st.caption(
                f"Provider preference: {config.provider_name} | "
                f"Cache dir: {config.cache_dir} | "
                f"TTL quote/macro/stats: {config.cache_ttl_quote}/{config.cache_ttl_macro}/{config.cache_ttl_stats}s"
            )
            render_data_debug(provider_result.debug_rows)

    render_macro_strip(analytics.macro_metrics)
    render_overview(analytics.index_metrics)

    st.divider()
    controls = st.columns([1, 1, 1, 1])
    with controls[0]:
        period = st.radio("时间区间", ["1D", "5D", "1M", "6M", "YTD", "1Y"], horizontal=True, index=3)
    with controls[1]:
        mode = st.radio("展示模式", ["原始点位", "归一化对比（起点=100）"], horizontal=True, index=1)
    with controls[2]:
        chart_style = st.radio("图表形态", ["线图", "面积图"], horizontal=True, index=0)
    with controls[3]:
        show_drawdown = st.toggle("回撤阴影", value=True)

    render_price_chart(provider_result.datasets, period, mode, chart_style, show_drawdown)

    st.divider()
    st.subheader("七巨头热力与贡献")
    render_mega_cap_section(analytics.mega_cap_metrics, analytics.mega_cap_average)

    st.divider()
    st.subheader("市场宽度")
    render_breadth_section(analytics)

    st.divider()
    st.subheader("五维市场判断")
    render_decision_matrix(analytics)
    render_badges(analytics)

    st.divider()
    st.subheader("成交量与统计")
    render_stats(analytics.index_metrics)

    st.divider()
    st.subheader("AI 盘后简报")
    render_summary(summary_sections)


if __name__ == "__main__":
    main()
