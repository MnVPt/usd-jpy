"""
图表组件模块 - 使用Plotly创建交互式图表
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import sys
sys.path.append('..')
from config import ALERT_THRESHOLDS, HISTORICAL_EVENTS, UI_CONFIG


# 图表主题颜色
CHART_COLORS = {
    'primary': '#2962FF',
    'secondary': '#00BFA5',
    'danger': '#FF1744',
    'warning': '#FFD600',
    'success': '#00C853',
    'neutral': '#757575',
    'background': '#1a1a2e',
    'grid': '#2d2d44',
    'text': '#e0e0e0',
}


def get_chart_layout(title: str, height: int = 500) -> dict:
    """
    获取统一的图表布局配置
    """
    return dict(
        title=dict(
            text=title,
            font=dict(size=18, color=CHART_COLORS['text']),
            x=0.5
        ),
        height=height,
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,26,46,0.8)',
        font=dict(color=CHART_COLORS['text']),
        xaxis=dict(
            gridcolor=CHART_COLORS['grid'],
            showgrid=True,
            gridwidth=1,
        ),
        yaxis=dict(
            gridcolor=CHART_COLORS['grid'],
            showgrid=True,
            gridwidth=1,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=60, r=40, t=80, b=60),
        hovermode='x unified',
    )


def create_spread_chart(
    spread_df: pd.DataFrame,
    show_thresholds: bool = True,
    show_events: bool = True
) -> go.Figure:
    """
    创建利差走势图
    
    Args:
        spread_df: 利差数据DataFrame
        show_thresholds: 是否显示阈值线
        show_events: 是否显示历史事件
    
    Returns:
        Plotly Figure对象
    """
    if spread_df.empty:
        return go.Figure().update_layout(title="无数据")
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("10年期美日国债利差", "美债收益率")
    )
    
    # 主图：利差走势
    fig.add_trace(
        go.Scatter(
            x=spread_df.index,
            y=spread_df['Spread'],
            mode='lines',
            name='利差',
            line=dict(color=CHART_COLORS['primary'], width=2),
            fill='tozeroy',
            fillcolor='rgba(41, 98, 255, 0.2)',
        ),
        row=1, col=1
    )
    
    # 添加阈值线
    if show_thresholds:
        # 警告线 2.5%
        fig.add_hline(
            y=ALERT_THRESHOLDS["SPREAD_WARNING"],
            line_dash="dash",
            line_color=CHART_COLORS['warning'],
            annotation_text=f"警告线 {ALERT_THRESHOLDS['SPREAD_WARNING']}%",
            annotation_position="right",
            row=1, col=1
        )
        
        # 危险线 2.0%
        fig.add_hline(
            y=ALERT_THRESHOLDS["SPREAD_DANGER"],
            line_dash="dash",
            line_color=CHART_COLORS['danger'],
            annotation_text=f"危险线 {ALERT_THRESHOLDS['SPREAD_DANGER']}%",
            annotation_position="right",
            row=1, col=1
        )
    
    # 副图：美债收益率
    if 'US_10Y' in spread_df.columns:
        fig.add_trace(
            go.Scatter(
                x=spread_df.index,
                y=spread_df['US_10Y'],
                mode='lines',
                name='美债10Y',
                line=dict(color=CHART_COLORS['secondary'], width=1.5),
            ),
            row=2, col=1
        )
    
    # 添加历史事件标注
    if show_events:
        for event in HISTORICAL_EVENTS:
            event_date = pd.to_datetime(event['date'])
            if event_date in spread_df.index or (spread_df.index[0] <= event_date <= spread_df.index[-1]):
                fig.add_vline(
                    x=event_date,
                    line_dash="dot",
                    line_color="#9C27B0",
                    opacity=0.7,
                    row=1, col=1
                )
                fig.add_annotation(
                    x=event_date,
                    y=spread_df['Spread'].max(),
                    text=event['event'],
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#9C27B0",
                    font=dict(size=10, color="#9C27B0"),
                    row=1, col=1
                )
    
    layout = get_chart_layout("美日国债利差监控")
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="利差 (%)", row=1, col=1)
    fig.update_yaxes(title_text="收益率 (%)", row=2, col=1)
    
    return fig


def create_usdjpy_chart(
    usdjpy_df: pd.DataFrame,
    volatility: pd.Series = None,
    show_bollinger: bool = True
) -> go.Figure:
    """
    创建USD/JPY汇率图表
    
    Args:
        usdjpy_df: 汇率OHLC数据
        volatility: 波动率Series
        show_bollinger: 是否显示布林带
    
    Returns:
        Plotly Figure对象
    """
    if usdjpy_df.empty:
        return go.Figure().update_layout(title="无数据")
    
    has_volatility = volatility is not None and len(volatility) > 0
    
    fig = make_subplots(
        rows=2 if has_volatility else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3] if has_volatility else [1.0],
        subplot_titles=("USD/JPY 汇率", "历史波动率") if has_volatility else ("USD/JPY 汇率",)
    )
    
    # K线图
    fig.add_trace(
        go.Candlestick(
            x=usdjpy_df.index,
            open=usdjpy_df['Open'],
            high=usdjpy_df['High'],
            low=usdjpy_df['Low'],
            close=usdjpy_df['Close'],
            name='USD/JPY',
            increasing_line_color=CHART_COLORS['success'],
            decreasing_line_color=CHART_COLORS['danger'],
        ),
        row=1, col=1
    )
    
    # 布林带
    if show_bollinger and len(usdjpy_df) >= 20:
        close = usdjpy_df['Close']
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        
        fig.add_trace(
            go.Scatter(
                x=usdjpy_df.index,
                y=upper,
                mode='lines',
                name='布林上轨',
                line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'),
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=usdjpy_df.index,
                y=lower,
                mode='lines',
                name='布林下轨',
                line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'),
                fill='tonexty',
                fillcolor='rgba(150, 150, 150, 0.1)',
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=usdjpy_df.index,
                y=sma20,
                mode='lines',
                name='MA20',
                line=dict(color=CHART_COLORS['warning'], width=1),
            ),
            row=1, col=1
        )
    
    # 波动率子图
    if has_volatility:
        fig.add_trace(
            go.Scatter(
                x=volatility.index,
                y=volatility,
                mode='lines',
                name='波动率',
                line=dict(color=CHART_COLORS['secondary'], width=1.5),
                fill='tozeroy',
                fillcolor='rgba(0, 191, 165, 0.2)',
            ),
            row=2, col=1
        )
        
        # 波动率均值线
        vol_mean = volatility.mean()
        fig.add_hline(
            y=vol_mean,
            line_dash="dash",
            line_color=CHART_COLORS['neutral'],
            annotation_text=f"均值 {vol_mean:.1f}%",
            row=2, col=1
        )
    
    layout = get_chart_layout("USD/JPY 汇率与波动率")
    fig.update_layout(**layout)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="汇率", row=1, col=1)
    if has_volatility:
        fig.update_yaxes(title_text="波动率 (%)", row=2, col=1)
    
    return fig


def create_divergence_chart(
    benchmark_df: pd.DataFrame,
    high_beta_assets: Dict[str, pd.DataFrame],
    window: int = 20
) -> go.Figure:
    """
    创建资产背离检测图表
    
    Args:
        benchmark_df: 基准（SPY）数据
        high_beta_assets: 高贝塔资产数据字典
        window: 归一化窗口
    
    Returns:
        Plotly Figure对象
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.6, 0.4],
        subplot_titles=("归一化价格走势对比", "相对强弱 (vs SPY)")
    )
    
    if benchmark_df.empty:
        return fig.update_layout(title="无数据")
    
    # 归一化基准价格
    bench_close = benchmark_df['Close'] if 'Close' in benchmark_df.columns else benchmark_df.iloc[:, 0]
    bench_normalized = (bench_close / bench_close.iloc[0]) * 100
    
    fig.add_trace(
        go.Scatter(
            x=benchmark_df.index,
            y=bench_normalized,
            mode='lines',
            name='SPY (基准)',
            line=dict(color=CHART_COLORS['primary'], width=2),
        ),
        row=1, col=1
    )
    
    # 添加高贝塔资产
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
    
    for i, (ticker, df) in enumerate(high_beta_assets.items()):
        if df.empty:
            continue
        
        # 对齐日期
        common_idx = bench_close.index.intersection(df.index)
        if len(common_idx) == 0:
            continue
        
        asset_close = df['Close'] if 'Close' in df.columns else df.iloc[:, 0]
        asset_close = asset_close.loc[common_idx]
        asset_normalized = (asset_close / asset_close.iloc[0]) * 100
        
        color = colors[i % len(colors)]
        
        fig.add_trace(
            go.Scatter(
                x=common_idx,
                y=asset_normalized,
                mode='lines',
                name=ticker,
                line=dict(color=color, width=1.5),
            ),
            row=1, col=1
        )
        
        # 计算相对强弱
        bench_aligned = bench_close.loc[common_idx]
        asset_return = asset_close.pct_change(window)
        bench_return = bench_aligned.pct_change(window)
        relative_strength = (asset_return - bench_return) * 100
        
        fig.add_trace(
            go.Scatter(
                x=common_idx,
                y=relative_strength,
                mode='lines',
                name=f'{ticker} RS',
                line=dict(color=color, width=1.5, dash='dot'),
            ),
            row=2, col=1
        )
    
    # 零线
    fig.add_hline(y=0, line_dash="solid", line_color=CHART_COLORS['neutral'], row=2, col=1)
    
    # 背离阈值
    fig.add_hline(
        y=ALERT_THRESHOLDS["DIVERGENCE_THRESHOLD"] * 100,
        line_dash="dash",
        line_color=CHART_COLORS['warning'],
        annotation_text="背离阈值",
        row=2, col=1
    )
    
    layout = get_chart_layout("资产背离检测")
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="归一化价格", row=1, col=1)
    fig.update_yaxes(title_text="相对强弱 (%)", row=2, col=1)
    
    return fig


def create_correlation_heatmap(
    assets: Dict[str, pd.DataFrame],
    window: int = 60
) -> go.Figure:
    """
    创建资产相关性热力图
    
    Args:
        assets: 资产数据字典
        window: 计算窗口
    
    Returns:
        Plotly Figure对象
    """
    # 提取收益率
    returns_dict = {}
    
    for ticker, df in assets.items():
        if df.empty:
            continue
        close = df['Close'] if 'Close' in df.columns else df.iloc[:, 0]
        returns_dict[ticker] = close.pct_change().tail(window)
    
    if len(returns_dict) < 2:
        return go.Figure().update_layout(title="数据不足以计算相关性")
    
    returns_df = pd.DataFrame(returns_dict).dropna()
    
    if len(returns_df) < 10:
        return go.Figure().update_layout(title="数据不足")
    
    corr_matrix = returns_df.corr()
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale='RdBu_r',
        zmid=0,
        text=np.round(corr_matrix.values, 2),
        texttemplate='%{text}',
        textfont=dict(size=12),
        hovertemplate='%{x} vs %{y}<br>相关性: %{z:.3f}<extra></extra>',
    ))
    
    layout = get_chart_layout("资产相关性矩阵", height=400)
    fig.update_layout(**layout)
    
    return fig


def create_historical_comparison_chart(
    spread_df: pd.DataFrame,
    usdjpy_df: pd.DataFrame,
    period_label: str = "6M"
) -> go.Figure:
    """
    创建利差与汇率的历史对比图
    
    Args:
        spread_df: 利差数据
        usdjpy_df: 汇率数据
        period_label: 周期标签
    
    Returns:
        Plotly Figure对象
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=("美日利差", "USD/JPY汇率")
    )
    
    if not spread_df.empty and 'Spread' in spread_df.columns:
        fig.add_trace(
            go.Scatter(
                x=spread_df.index,
                y=spread_df['Spread'],
                mode='lines',
                name='利差',
                line=dict(color=CHART_COLORS['primary'], width=2),
                fill='tozeroy',
                fillcolor='rgba(41, 98, 255, 0.2)',
            ),
            row=1, col=1
        )
    
    if not usdjpy_df.empty:
        close = usdjpy_df['Close'] if 'Close' in usdjpy_df.columns else usdjpy_df.iloc[:, 0]
        fig.add_trace(
            go.Scatter(
                x=usdjpy_df.index,
                y=close,
                mode='lines',
                name='USD/JPY',
                line=dict(color=CHART_COLORS['secondary'], width=2),
            ),
            row=2, col=1
        )
    
    # 添加历史事件
    for event in HISTORICAL_EVENTS:
        event_date = pd.to_datetime(event['date'])
        for row in [1, 2]:
            fig.add_vline(
                x=event_date,
                line_dash="dot",
                line_color="#9C27B0",
                opacity=0.5,
                row=row, col=1
            )
    
    layout = get_chart_layout(f"历史数据回溯 ({period_label})")
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="利差 (%)", row=1, col=1)
    fig.update_yaxes(title_text="汇率", row=2, col=1)
    
    return fig


def create_metric_card_chart(
    value: float,
    title: str,
    delta: float = None,
    suffix: str = "",
    color: str = None
) -> go.Figure:
    """
    创建指标卡片图表
    
    Args:
        value: 数值
        title: 标题
        delta: 变化值
        suffix: 后缀（如%）
        color: 颜色
    
    Returns:
        Plotly Figure对象
    """
    if color is None:
        color = CHART_COLORS['primary']
    
    fig = go.Figure(go.Indicator(
        mode="number+delta" if delta is not None else "number",
        value=value,
        delta={'reference': value - delta, 'relative': False} if delta else None,
        number={'suffix': suffix, 'font': {'size': 40, 'color': color}},
        title={'text': title, 'font': {'size': 16}},
    ))
    
    fig.update_layout(
        height=150,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    return fig

