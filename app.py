"""
日元套利监控系统 - Streamlit 主应用
追踪日元套利资金流动，监控关键风险指标
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 导入配置
from config import (
    TICKERS, UI_CONFIG, CALC_PARAMS, ALERT_THRESHOLDS,
    JP_10Y_YIELD_MANUAL, HISTORICAL_EVENTS
)

# 导入数据获取
from data.fetcher import (
    get_us_10y_yield, get_usdjpy, get_all_data,
    get_current_usdjpy, get_current_us_10y, get_data_freshness
)

# 导入指标计算
from indicators.spread import (
    calculate_yield_spread, get_spread_statistics,
    get_spread_trend, check_spread_alert, is_spread_accelerating
)
from indicators.volatility import (
    calculate_historical_volatility, get_volatility_stats,
    check_volatility_alert, is_volatility_spiking
)
from indicators.divergence import (
    detect_divergence, get_divergence_alert, analyze_liquidity_retreat
)

# 导入UI组件
from components.alerts import (
    create_alert, render_alert_banner, render_risk_summary,
    calculate_composite_risk_score, render_risk_gauge, Alert, AlertLevel
)
from components.charts import (
    create_spread_chart, create_usdjpy_chart,
    create_divergence_chart, create_correlation_heatmap,
    create_historical_comparison_chart
)


# =============================================================================
# 页面配置
# =============================================================================

st.set_page_config(
    page_title=UI_CONFIG["PAGE_TITLE"],
    page_icon=UI_CONFIG["PAGE_ICON"],
    layout=UI_CONFIG["LAYOUT"],
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    /* 主题颜色 */
    :root {
        --primary-color: #2962FF;
        --background-color: #0e1117;
        --secondary-background-color: #1a1a2e;
        --text-color: #e0e0e0;
    }
    
    /* 指标卡片 */
    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #2d2d44;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2962FF;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #888;
        margin-top: 5px;
    }
    
    .metric-delta {
        font-size: 0.85rem;
        margin-top: 8px;
    }
    
    .delta-positive { color: #00C853; }
    .delta-negative { color: #FF1744; }
    
    /* 预警横幅 */
    .alert-banner {
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-weight: 500;
    }
    
    .alert-critical {
        background: linear-gradient(90deg, #9C27B0, #7B1FA2);
        border-left: 5px solid #E040FB;
    }
    
    .alert-danger {
        background: linear-gradient(90deg, #D32F2F, #C62828);
        border-left: 5px solid #FF5252;
    }
    
    .alert-warning {
        background: linear-gradient(90deg, #F9A825, #F57F17);
        border-left: 5px solid #FFEA00;
        color: #000;
    }
    
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Tab样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        border-radius: 8px;
        padding: 10px 20px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #2962FF;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# 侧边栏
# =============================================================================

with st.sidebar:
    st.title("⚙️ 控制面板")
    
    st.markdown("---")
    
    # 数据周期选择
    st.subheader("📅 数据周期")
    period_options = list(CALC_PARAMS["HISTORY_PERIODS"].keys())
    selected_period_label = st.selectbox(
        "选择时间范围",
        period_options,
        index=2  # 默认6M
    )
    selected_period = CALC_PARAMS["HISTORY_PERIODS"][selected_period_label]
    
    st.markdown("---")
    
    # 日本国债收益率手动输入
    st.subheader("🇯🇵 日本国债收益率")
    jp_yield_input = st.number_input(
        "10年期日债收益率 (%)",
        min_value=0.0,
        max_value=5.0,
        value=JP_10Y_YIELD_MANUAL,
        step=0.05,
        help="由于yfinance无法直接获取日债收益率，请手动输入最新值"
    )
    
    st.markdown("---")
    
    # 预警阈值调整
    st.subheader("🎚️ 预警阈值")
    
    spread_warning = st.slider(
        "利差警告线 (%)",
        min_value=1.0,
        max_value=4.0,
        value=ALERT_THRESHOLDS["SPREAD_WARNING"],
        step=0.1
    )
    
    spread_danger = st.slider(
        "利差危险线 (%)",
        min_value=0.5,
        max_value=3.0,
        value=ALERT_THRESHOLDS["SPREAD_DANGER"],
        step=0.1
    )
    
    jpy_daily_threshold = st.slider(
        "日元日波动预警 (%)",
        min_value=1.0,
        max_value=5.0,
        value=ALERT_THRESHOLDS["JPY_DAILY_MOVE"],
        step=0.5
    )
    
    st.markdown("---")
    
    # 自动刷新控制
    st.subheader("🔄 自动刷新")
    auto_refresh = st.checkbox("启用自动刷新", value=True)
    refresh_interval = st.selectbox(
        "刷新间隔",
        ["5分钟", "15分钟", "30分钟", "1小时"],
        index=3
    )
    
    interval_map = {"5分钟": 300, "15分钟": 900, "30分钟": 1800, "1小时": 3600}
    
    if auto_refresh:
        st_autorefresh(interval=interval_map[refresh_interval] * 1000, key="data_refresh")
    
    # 手动刷新按钮
    if st.button("🔄 立即刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # 数据状态
    st.caption(get_data_freshness())


# =============================================================================
# 主页面
# =============================================================================

# 标题
st.title("💹 日元套利监控系统")
st.caption("实时追踪日元套利资金流动，预警潜在风险")

# 更新阈值（根据侧边栏输入）
current_thresholds = ALERT_THRESHOLDS.copy()
current_thresholds["SPREAD_WARNING"] = spread_warning
current_thresholds["SPREAD_DANGER"] = spread_danger
current_thresholds["JPY_DAILY_MOVE"] = jpy_daily_threshold


# =============================================================================
# 数据加载
# =============================================================================

@st.cache_data(ttl=3600)
def load_all_data(period: str, jp_yield: float):
    """加载所有必要数据"""
    # 获取美债收益率
    us_yield = get_us_10y_yield(period)
    
    # 获取USD/JPY
    usdjpy = get_usdjpy(period)
    
    # 计算利差
    spread_df = calculate_yield_spread(us_yield, jp_yield)
    
    # 获取所有资产数据
    all_data = get_all_data(period)
    
    return {
        'us_yield': us_yield,
        'usdjpy': usdjpy,
        'spread': spread_df,
        'all_data': all_data,
    }


# 加载数据
with st.spinner("正在加载数据..."):
    data = load_all_data(selected_period, jp_yield_input)

spread_df = data['spread']
usdjpy_df = data['usdjpy']
all_data = data['all_data']


# =============================================================================
# 计算指标和预警
# =============================================================================

# 利差统计
spread_stats = get_spread_statistics(spread_df) if not spread_df.empty else {}
spread_trend = get_spread_trend(spread_df) if not spread_df.empty else "未知"
current_spread = spread_stats.get('current', 0)
spread_alert = check_spread_alert(current_spread)

# 波动率统计
vol_stats = get_volatility_stats(usdjpy_df) if not usdjpy_df.empty else {}
hv = calculate_historical_volatility(usdjpy_df) if not usdjpy_df.empty else pd.Series()
vol_alert = check_volatility_alert(
    vol_stats.get('daily_change', 0),
    vol_stats.get('weekly_range', 0),
    vol_stats.get('hv_percentile', 50)
)

# 背离检测
high_beta_assets = {
    'BTC-USD': all_data.get(TICKERS['BTC'], pd.DataFrame()),
    'EEM': all_data.get(TICKERS['EEM'], pd.DataFrame()),
}
benchmark = all_data.get(TICKERS['SPY'], pd.DataFrame())
divergence_result = detect_divergence(high_beta_assets, benchmark)
div_alert = get_divergence_alert(divergence_result)

# 汇总预警
alerts = []
if spread_alert[0] != "safe":
    alerts.append(create_alert(spread_alert[0], "利差", f"当前利差 {current_spread:.2f}%", spread_alert[1]))
if vol_alert[0] != "safe":
    alerts.append(create_alert(vol_alert[0], "波动率", vol_alert[2], vol_alert[1]))
if div_alert[0] != "safe":
    alerts.append(create_alert(div_alert[0], "背离", div_alert[2], div_alert[1]))


# =============================================================================
# 预警横幅
# =============================================================================

render_alert_banner(alerts)


# =============================================================================
# 核心指标卡片
# =============================================================================

st.markdown("### 📊 核心指标")

col1, col2, col3, col4 = st.columns(4)

with col1:
    delta_1d = spread_stats.get('change_1d', 0)
    delta_color = "normal" if delta_1d >= 0 else "inverse"
    st.metric(
        label="美日利差",
        value=f"{current_spread:.2f}%",
        delta=f"{delta_1d:+.2f}% (1D)",
        delta_color=delta_color
    )
    st.caption(f"趋势: {spread_trend}")

with col2:
    current_usdjpy = usdjpy_df['Close'].iloc[-1] if not usdjpy_df.empty else 0
    daily_change = vol_stats.get('daily_change', 0)
    st.metric(
        label="USD/JPY",
        value=f"{current_usdjpy:.2f}",
        delta=f"{daily_change:+.2f}% (1D)",
        delta_color="off"
    )

with col3:
    current_hv = vol_stats.get('historical_volatility', 0)
    hv_percentile = vol_stats.get('hv_percentile', 50)
    st.metric(
        label="20日波动率",
        value=f"{current_hv:.1f}%",
        delta=f"{hv_percentile:.0f}分位"
    )

with col4:
    div_score = divergence_result.get('divergence_score', 0)
    div_detected = "检测到" if divergence_result.get('divergence_detected', False) else "未检测"
    st.metric(
        label="背离度",
        value=f"{div_score:.2f}",
        delta=div_detected,
        delta_color="inverse" if divergence_result.get('divergence_detected', False) else "off"
    )


# =============================================================================
# 主要图表区域 (Tabs)
# =============================================================================

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 利差监控",
    "💱 汇率波动",
    "📉 背离检测",
    "🔗 相关性",
    "📚 历史回溯"
])

with tab1:
    st.markdown("### 10年期美日国债利差")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**当前利差**: {current_spread:.2f}%")
    with col2:
        st.info(f"**历史均值**: {spread_stats.get('mean', 0):.2f}%")
    with col3:
        percentile = spread_stats.get('percentile', 50)
        st.info(f"**历史分位**: {percentile:.0f}%")
    
    # 利差趋势解读
    if is_spread_accelerating(spread_df):
        st.warning("⚠️ 检测到利差收窄正在加速！")
    
    # 利差图表
    spread_chart = create_spread_chart(spread_df, show_thresholds=True, show_events=True)
    st.plotly_chart(spread_chart, use_container_width=True)
    
    # 利差统计表格
    with st.expander("📊 利差详细统计"):
        stats_df = pd.DataFrame({
            '指标': ['当前值', '1日变化', '5日变化', '20日变化', '最小值', '最大值', '标准差'],
            '数值': [
                f"{current_spread:.2f}%",
                f"{spread_stats.get('change_1d', 0):+.3f}%",
                f"{spread_stats.get('change_5d', 0):+.3f}%",
                f"{spread_stats.get('change_20d', 0):+.3f}%",
                f"{spread_stats.get('min', 0):.2f}%",
                f"{spread_stats.get('max', 0):.2f}%",
                f"{spread_stats.get('std', 0):.3f}%",
            ]
        })
        st.dataframe(stats_df, hide_index=True, use_container_width=True)


with tab2:
    st.markdown("### USD/JPY 汇率与波动率")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info(f"**当前汇率**: {current_usdjpy:.2f}")
    with col2:
        st.info(f"**日涨跌**: {vol_stats.get('daily_change', 0):+.2f}%")
    with col3:
        st.info(f"**波动率**: {current_hv:.1f}%")
    with col4:
        st.info(f"**ATR%**: {vol_stats.get('atr_percent', 0):.2f}%")
    
    # 波动率飙升检测
    if is_volatility_spiking(usdjpy_df):
        st.error("🚨 波动率正在快速飙升！")
    
    # 汇率图表
    usdjpy_chart = create_usdjpy_chart(usdjpy_df, hv, show_bollinger=True)
    st.plotly_chart(usdjpy_chart, use_container_width=True)
    
    # 波动率统计
    with st.expander("📊 波动率详细统计"):
        vol_df = pd.DataFrame({
            '指标': ['20日历史波动率', 'ATR', 'ATR百分比', '最大日波动(5日)', '周波动范围', '波动率百分位'],
            '数值': [
                f"{vol_stats.get('historical_volatility', 0):.2f}%",
                f"{vol_stats.get('atr', 0):.4f}",
                f"{vol_stats.get('atr_percent', 0):.2f}%",
                f"{vol_stats.get('max_daily_change_5d', 0):.2f}%",
                f"{vol_stats.get('weekly_range', 0):.2f}%",
                f"{vol_stats.get('hv_percentile', 50):.0f}%",
            ]
        })
        st.dataframe(vol_df, hide_index=True, use_container_width=True)


with tab3:
    st.markdown("### 资产背离检测")
    st.caption("监控高贝塔资产（BTC、新兴市场）相对大盘的表现，识别套利资金撤退信号")
    
    # 背离状态
    if divergence_result.get('divergence_detected', False):
        st.error(f"⚠️ 检测到资产背离！背离度: {divergence_result.get('divergence_score', 0):.2f}")
        
        # 显示背离详情
        for detail in divergence_result.get('details', []):
            st.warning(f"- {detail['message']}")
    else:
        st.success("✅ 未检测到明显背离")
    
    # 各资产表现
    col1, col2, col3 = st.columns(3)
    with col1:
        bench_perf = divergence_result.get('benchmark_performance', 0)
        st.metric("SPY (基准)", f"{bench_perf:+.2f}%")
    
    high_beta_perf = divergence_result.get('high_beta_performance', {})
    for i, (ticker, perf) in enumerate(high_beta_perf.items()):
        with [col2, col3][i % 2]:
            st.metric(ticker, f"{perf:+.2f}%")
    
    # 背离图表
    divergence_chart = create_divergence_chart(benchmark, high_beta_assets)
    st.plotly_chart(divergence_chart, use_container_width=True)
    
    # 流动性撤退分析
    with st.expander("🔍 流动性撤退分析"):
        all_assets = {**high_beta_assets, 'NDX': all_data.get(TICKERS['NDX'], pd.DataFrame())}
        retreat_result = analyze_liquidity_retreat(all_assets, benchmark)
        
        if retreat_result.get('retreat_detected', False):
            st.warning(f"检测到流动性撤退模式！严重程度: {retreat_result.get('severity', 'unknown')}")
            st.write("撤退顺序:", retreat_result.get('retreat_order', []))
        else:
            st.info("未检测到明显的流动性撤退模式")


with tab4:
    st.markdown("### 资产相关性矩阵")
    st.caption("观察各资产之间的相关性变化，相关性突变可能预示市场结构变化")
    
    # 准备相关性数据
    corr_assets = {
        'USD/JPY': usdjpy_df,
        'SPY': benchmark,
        'BTC': high_beta_assets.get('BTC-USD', pd.DataFrame()),
        'EEM': high_beta_assets.get('EEM', pd.DataFrame()),
    }
    
    # 相关性热力图
    corr_chart = create_correlation_heatmap(corr_assets)
    st.plotly_chart(corr_chart, use_container_width=True)


with tab5:
    st.markdown("### 历史数据回溯")
    
    # 历史周期选择
    history_period = st.selectbox(
        "选择回溯周期",
        list(CALC_PARAMS["HISTORY_PERIODS"].keys()),
        index=4,  # 默认2Y
        key="history_period"
    )
    
    history_period_value = CALC_PARAMS["HISTORY_PERIODS"][history_period]
    
    # 加载历史数据
    with st.spinner("加载历史数据..."):
        hist_us_yield = get_us_10y_yield(history_period_value)
        hist_usdjpy = get_usdjpy(history_period_value)
        hist_spread = calculate_yield_spread(hist_us_yield, jp_yield_input)
    
    # 历史对比图
    history_chart = create_historical_comparison_chart(hist_spread, hist_usdjpy, history_period)
    st.plotly_chart(history_chart, use_container_width=True)
    
    # 历史事件时间线
    st.markdown("#### 📅 重要历史事件")
    for event in HISTORICAL_EVENTS:
        st.markdown(f"- **{event['date']}**: {event['event']} - {event['description']}")
    
    # 数据导出
    with st.expander("📥 导出数据"):
        col1, col2 = st.columns(2)
        
        with col1:
            if not hist_spread.empty:
                csv_spread = hist_spread.to_csv()
                st.download_button(
                    label="下载利差数据 (CSV)",
                    data=csv_spread,
                    file_name=f"spread_data_{history_period}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if not hist_usdjpy.empty:
                csv_usdjpy = hist_usdjpy.to_csv()
                st.download_button(
                    label="下载汇率数据 (CSV)",
                    data=csv_usdjpy,
                    file_name=f"usdjpy_data_{history_period}.csv",
                    mime="text/csv"
                )


# =============================================================================
# 风险评估汇总
# =============================================================================

st.markdown("---")
st.markdown("### 🎯 综合风险评估")

# 计算综合风险分数
risk_score, risk_factors = calculate_composite_risk_score(
    spread_stats, vol_stats, divergence_result
)

col1, col2 = st.columns([1, 2])

with col1:
    render_risk_gauge(risk_score)
    
with col2:
    if risk_factors:
        st.markdown("**风险因素:**")
        for factor in risk_factors:
            st.markdown(f"- {factor}")
    else:
        st.success("当前未检测到显著风险因素")

# 风险状态汇总
render_risk_summary(spread_alert, vol_alert, div_alert)


# =============================================================================
# 页脚
# =============================================================================

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.8rem;">
    <p>日元套利监控系统 | 数据来源: Yahoo Finance | 仅供参考，不构成投资建议</p>
    <p>⚠️ 注意：日本国债收益率需手动更新，请确保使用最新数据</p>
</div>
""", unsafe_allow_html=True)

