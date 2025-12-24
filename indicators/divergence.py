"""
背离检测模块 - 检测高贝塔资产与大盘的背离
用于识别日元套利资金撤退的早期信号
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import sys
sys.path.append('..')
from config import CALC_PARAMS, ALERT_THRESHOLDS


def _to_scalar(val):
    """将 pandas/numpy 值转换为 Python 标量"""
    if hasattr(val, 'item'):
        return val.item()
    if isinstance(val, pd.Series):
        return val.iloc[0] if len(val) > 0 else 0
    return float(val) if val is not None else 0


def calculate_relative_strength(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    window: int = None
) -> pd.Series:
    """
    计算资产相对基准的相对强弱
    
    Args:
        asset: 资产价格DataFrame
        benchmark: 基准价格DataFrame
        window: 计算窗口
    
    Returns:
        相对强弱Series（正值表示跑赢，负值表示跑输）
    """
    if window is None:
        window = CALC_PARAMS["RELATIVE_STRENGTH_WINDOW"]
    
    if asset.empty or benchmark.empty:
        return pd.Series()
    
    # 获取收盘价
    asset_close = asset['Close'] if 'Close' in asset.columns else asset.iloc[:, 0]
    bench_close = benchmark['Close'] if 'Close' in benchmark.columns else benchmark.iloc[:, 0]
    
    # 对齐日期
    common_idx = asset_close.index.intersection(bench_close.index)
    asset_close = asset_close.loc[common_idx]
    bench_close = bench_close.loc[common_idx]
    
    # 计算收益率
    asset_returns = asset_close.pct_change(window)
    bench_returns = bench_close.pct_change(window)
    
    # 相对强弱 = 资产收益率 - 基准收益率
    relative_strength = (asset_returns - bench_returns) * 100
    
    return relative_strength


def calculate_rolling_correlation(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    window: int = None
) -> pd.Series:
    """
    计算滚动相关性
    
    Args:
        asset: 资产价格DataFrame
        benchmark: 基准价格DataFrame
        window: 滚动窗口
    
    Returns:
        滚动相关性Series
    """
    if window is None:
        window = CALC_PARAMS["CORRELATION_WINDOW"]
    
    if asset.empty or benchmark.empty:
        return pd.Series()
    
    # 获取收盘价
    asset_close = asset['Close'] if 'Close' in asset.columns else asset.iloc[:, 0]
    bench_close = benchmark['Close'] if 'Close' in benchmark.columns else benchmark.iloc[:, 0]
    
    # 对齐日期
    common_idx = asset_close.index.intersection(bench_close.index)
    asset_close = asset_close.loc[common_idx]
    bench_close = bench_close.loc[common_idx]
    
    # 计算日收益率
    asset_returns = asset_close.pct_change()
    bench_returns = bench_close.pct_change()
    
    # 计算滚动相关性
    correlation = asset_returns.rolling(window=window).corr(bench_returns)
    
    return correlation


def detect_divergence(
    high_beta_assets: Dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    window: int = None
) -> Dict:
    """
    检测高贝塔资产与大盘的背离
    
    核心逻辑：
    - 当大盘稳定但高贝塔资产（BTC、新兴市场）开始阴跌
    - 说明套利资金开始从风险资产撤退
    
    Args:
        high_beta_assets: 高贝塔资产字典 {ticker: DataFrame}
        benchmark: 基准（如SPY）DataFrame
        window: 计算窗口
    
    Returns:
        背离检测结果字典
    """
    if window is None:
        window = CALC_PARAMS["RELATIVE_STRENGTH_WINDOW"]
    
    results = {
        'divergence_detected': False,
        'divergence_score': 0.0,
        'details': [],
        'benchmark_performance': 0.0,
        'high_beta_performance': {},
    }
    
    if benchmark.empty:
        return results
    
    # 计算基准近期表现
    bench_close = benchmark['Close'] if 'Close' in benchmark.columns else benchmark.iloc[:, 0]
    bench_return = _to_scalar((bench_close.iloc[-1] / bench_close.iloc[-window] - 1) * 100) if len(bench_close) > window else 0
    results['benchmark_performance'] = bench_return
    
    divergence_scores = []
    
    for ticker, asset_df in high_beta_assets.items():
        if asset_df.empty:
            continue
        
        # 计算相对强弱
        rs = calculate_relative_strength(asset_df, benchmark, window)
        
        if len(rs) == 0:
            continue
        
        current_rs = _to_scalar(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else 0
        
        # 计算资产表现
        asset_close = asset_df['Close'] if 'Close' in asset_df.columns else asset_df.iloc[:, 0]
        asset_return = _to_scalar((asset_close.iloc[-1] / asset_close.iloc[-window] - 1) * 100) if len(asset_close) > window else 0
        
        results['high_beta_performance'][ticker] = asset_return
        
        # 检测背离：大盘稳/涨但高贝塔资产跑输
        if bench_return >= -2 and current_rs < ALERT_THRESHOLDS["DIVERGENCE_THRESHOLD"] * 100:
            divergence_scores.append(current_rs)
            results['details'].append({
                'ticker': ticker,
                'relative_strength': current_rs,
                'asset_return': asset_return,
                'message': f"{ticker} 相对大盘跑输 {abs(current_rs):.2f}%"
            })
    
    # 计算综合背离分数
    if divergence_scores:
        results['divergence_score'] = _to_scalar(np.mean(divergence_scores))
        results['divergence_detected'] = True
    
    return results


def get_divergence_alert(divergence_result: Dict) -> Tuple[str, str, str]:
    """
    根据背离检测结果生成预警
    
    Args:
        divergence_result: detect_divergence的返回结果
    
    Returns:
        (预警级别, 颜色, 消息)
    """
    if not divergence_result.get('divergence_detected', False):
        return ("safe", "#00C853", "未检测到明显背离")
    
    score = divergence_result.get('divergence_score', 0)
    
    # 根据背离程度分级
    if score < -20:
        level = "critical"
        color = "#9C27B0"
        msg = f"严重背离：高贝塔资产大幅跑输大盘 ({score:.1f}%)"
    elif score < -10:
        level = "danger"
        color = "#FF1744"
        msg = f"显著背离：高贝塔资产明显跑输 ({score:.1f}%)"
    else:
        level = "warning"
        color = "#2979FF"
        msg = f"轻度背离：关注高贝塔资产走势 ({score:.1f}%)"
    
    return (level, color, msg)


def calculate_beta(
    asset: pd.DataFrame,
    benchmark: pd.DataFrame,
    window: int = 60
) -> float:
    """
    计算资产相对于基准的Beta值
    
    Args:
        asset: 资产价格DataFrame
        benchmark: 基准价格DataFrame
        window: 计算窗口
    
    Returns:
        Beta值
    """
    if asset.empty or benchmark.empty:
        return 1.0
    
    # 获取收盘价
    asset_close = asset['Close'] if 'Close' in asset.columns else asset.iloc[:, 0]
    bench_close = benchmark['Close'] if 'Close' in benchmark.columns else benchmark.iloc[:, 0]
    
    # 对齐日期
    common_idx = asset_close.index.intersection(bench_close.index)
    asset_close = asset_close.loc[common_idx].tail(window)
    bench_close = bench_close.loc[common_idx].tail(window)
    
    if len(asset_close) < 20:
        return 1.0
    
    # 计算日收益率
    asset_returns = asset_close.pct_change().dropna()
    bench_returns = bench_close.pct_change().dropna()
    
    # 计算Beta = Cov(asset, benchmark) / Var(benchmark)
    covariance = asset_returns.cov(bench_returns)
    variance = bench_returns.var()
    
    if variance == 0:
        return 1.0
    
    beta = covariance / variance
    
    return beta


def analyze_liquidity_retreat(
    assets: Dict[str, pd.DataFrame],
    benchmark: pd.DataFrame
) -> Dict:
    """
    分析流动性撤退模式
    
    逻辑：日元套利盘撤退时，会先撤离流动性最差、风险最高的资产
    
    Args:
        assets: 资产字典
        benchmark: 基准
    
    Returns:
        流动性撤退分析结果
    """
    results = {
        'retreat_detected': False,
        'retreat_order': [],
        'severity': 'none',
    }
    
    # 按Beta值排序资产，高Beta先撤
    asset_metrics = []
    
    for ticker, df in assets.items():
        if df.empty:
            continue
        
        beta = calculate_beta(df, benchmark)
        rs = calculate_relative_strength(df, benchmark, 5)
        current_rs = rs.iloc[-1] if len(rs) > 0 and not pd.isna(rs.iloc[-1]) else 0
        
        asset_metrics.append({
            'ticker': ticker,
            'beta': beta,
            'relative_strength_5d': current_rs
        })
    
    # 按Beta降序排列
    asset_metrics.sort(key=lambda x: x['beta'], reverse=True)
    
    # 检查是否存在高Beta资产跑输而低Beta资产稳定的模式
    high_beta_underperforming = 0
    low_beta_stable = 0
    
    for i, asset in enumerate(asset_metrics):
        if asset['beta'] > 1.2 and asset['relative_strength_5d'] < -5:
            high_beta_underperforming += 1
            results['retreat_order'].append(asset['ticker'])
        elif asset['beta'] < 1.0 and asset['relative_strength_5d'] > -2:
            low_beta_stable += 1
    
    # 判断撤退模式
    if high_beta_underperforming >= 2 and low_beta_stable >= 1:
        results['retreat_detected'] = True
        results['severity'] = 'high' if high_beta_underperforming >= 3 else 'medium'
    
    return results

