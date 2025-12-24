"""
波动率计算模块 - 计算日元汇率波动率指标
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
import sys
sys.path.append('..')
from config import CALC_PARAMS, ALERT_THRESHOLDS


def calculate_historical_volatility(
    prices: pd.DataFrame,
    window: int = None
) -> pd.Series:
    """
    计算历史波动率（年化）
    
    Args:
        prices: 价格DataFrame（需包含Close列）
        window: 计算窗口，默认使用配置值
    
    Returns:
        年化波动率Series
    """
    if window is None:
        window = CALC_PARAMS["VOL_WINDOW"]
    
    if prices.empty:
        return pd.Series()
    
    # 获取收盘价
    if 'Close' in prices.columns:
        close = prices['Close']
    else:
        close = prices.iloc[:, 0]
    
    # 计算对数收益率
    log_returns = np.log(close / close.shift(1))
    
    # 计算滚动标准差并年化（252个交易日）
    volatility = log_returns.rolling(window=window).std() * np.sqrt(252) * 100
    
    return volatility


def calculate_atr(
    prices: pd.DataFrame,
    window: int = None
) -> pd.Series:
    """
    计算ATR (Average True Range)
    
    Args:
        prices: OHLC价格DataFrame
        window: 计算窗口，默认使用配置值
    
    Returns:
        ATR Series
    """
    if window is None:
        window = CALC_PARAMS["ATR_WINDOW"]
    
    if prices.empty:
        return pd.Series()
    
    high = prices['High']
    low = prices['Low']
    close = prices['Close']
    
    # 计算True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 计算ATR
    atr = true_range.rolling(window=window).mean()
    
    return atr


def calculate_atr_percent(prices: pd.DataFrame, window: int = None) -> pd.Series:
    """
    计算ATR百分比（相对于收盘价）
    
    Args:
        prices: OHLC价格DataFrame
        window: 计算窗口
    
    Returns:
        ATR百分比Series
    """
    atr = calculate_atr(prices, window)
    close = prices['Close']
    
    return (atr / close) * 100


def calculate_daily_change(prices: pd.DataFrame) -> pd.Series:
    """
    计算每日涨跌幅
    
    Args:
        prices: 价格DataFrame
    
    Returns:
        日涨跌幅Series (%)
    """
    if prices.empty:
        return pd.Series()
    
    if 'Close' in prices.columns:
        close = prices['Close']
    else:
        close = prices.iloc[:, 0]
    
    daily_change = close.pct_change() * 100
    
    return daily_change


def get_volatility_percentile(
    volatility: pd.Series,
    lookback: int = None
) -> float:
    """
    计算当前波动率在历史中的百分位
    
    Args:
        volatility: 波动率Series
        lookback: 回溯期，默认使用配置值
    
    Returns:
        百分位值 (0-100)
    """
    if lookback is None:
        lookback = CALC_PARAMS["VOL_LOOKBACK"]
    
    if len(volatility) < lookback:
        lookback = len(volatility)
    
    if lookback == 0:
        return 50.0
    
    recent_vol = volatility.tail(lookback).dropna()
    
    if len(recent_vol) == 0:
        return 50.0
    
    current_vol = recent_vol.iloc[-1]
    percentile = (recent_vol < current_vol).sum() / len(recent_vol) * 100
    
    return percentile


def _to_scalar(val):
    """将 pandas/numpy 值转换为 Python 标量"""
    if hasattr(val, 'item'):
        return val.item()
    if isinstance(val, pd.Series):
        return val.iloc[0] if len(val) > 0 else 0
    return float(val) if val is not None else 0


def get_volatility_stats(prices: pd.DataFrame) -> Dict:
    """
    获取综合波动率统计
    
    Args:
        prices: 价格DataFrame
    
    Returns:
        波动率统计字典
    """
    if prices.empty:
        return {}
    
    # 计算各类波动率指标
    hv = calculate_historical_volatility(prices)
    atr = calculate_atr(prices)
    atr_pct = calculate_atr_percent(prices)
    daily_change = calculate_daily_change(prices)
    
    # 获取最新值并转换为标量
    current_hv = _to_scalar(hv.iloc[-1]) if len(hv) > 0 else 0
    current_atr = _to_scalar(atr.iloc[-1]) if len(atr) > 0 else 0
    current_atr_pct = _to_scalar(atr_pct.iloc[-1]) if len(atr_pct) > 0 else 0
    current_daily_change = _to_scalar(daily_change.iloc[-1]) if len(daily_change) > 0 else 0
    
    # 计算百分位
    hv_percentile = _to_scalar(get_volatility_percentile(hv))
    
    stats = {
        'historical_volatility': current_hv,
        'atr': current_atr,
        'atr_percent': current_atr_pct,
        'daily_change': current_daily_change,
        'hv_percentile': hv_percentile,
        'hv_mean': _to_scalar(hv.mean()) if len(hv) > 0 else 0,
        'hv_std': _to_scalar(hv.std()) if len(hv) > 0 else 0,
        'max_daily_change_5d': _to_scalar(abs(daily_change.tail(5)).max()) if len(daily_change) >= 5 else 0,
        'weekly_range': _to_scalar(calculate_weekly_range(prices)),
    }
    
    return stats


def calculate_weekly_range(prices: pd.DataFrame) -> float:
    """
    计算过去一周的价格波动范围（%）
    """
    if prices.empty or len(prices) < 5:
        return 0.0
    
    recent = prices.tail(5)
    high = recent['High'].max() if 'High' in recent.columns else recent['Close'].max()
    low = recent['Low'].min() if 'Low' in recent.columns else recent['Close'].min()
    
    return (high - low) / low * 100


def check_volatility_alert(
    daily_change: float,
    weekly_change: float = 0,
    hv_percentile: float = 50
) -> Tuple[str, str, str]:
    """
    检查波动率预警状态
    
    Args:
        daily_change: 日涨跌幅（%）
        weekly_change: 周涨跌幅（%）
        hv_percentile: 历史波动率百分位
    
    Returns:
        (预警级别, 预警颜色, 预警信息)
    """
    # 确保所有输入都是标量
    daily_change = _to_scalar(daily_change)
    weekly_change = _to_scalar(weekly_change)
    hv_percentile = _to_scalar(hv_percentile)
    
    alerts = []
    
    # 检查日波动
    if abs(daily_change) >= ALERT_THRESHOLDS["JPY_DAILY_MOVE"]:
        alerts.append(("danger", "#FF5722", f"日元单日波动 {daily_change:.2f}%"))
    
    # 检查周波动
    if abs(weekly_change) >= ALERT_THRESHOLDS["JPY_WEEKLY_MOVE"]:
        alerts.append(("danger", "#FF1744", f"日元周波动 {weekly_change:.2f}%"))
    
    # 检查波动率百分位
    if hv_percentile >= ALERT_THRESHOLDS["VOL_PERCENTILE_EXTREME"]:
        alerts.append(("critical", "#9C27B0", f"波动率处于历史极端水平 ({hv_percentile:.0f}%)"))
    elif hv_percentile >= ALERT_THRESHOLDS["VOL_PERCENTILE_HIGH"]:
        alerts.append(("warning", "#FFD600", f"波动率偏高 ({hv_percentile:.0f}%)"))
    
    if alerts:
        # 返回最高级别的预警
        priority = {"critical": 0, "danger": 1, "warning": 2}
        alerts.sort(key=lambda x: priority.get(x[0], 99))
        return alerts[0]
    
    return ("safe", "#00C853", "波动率正常")


def is_volatility_spiking(prices: pd.DataFrame) -> bool:
    """
    检测波动率是否正在飙升
    
    Returns:
        True 如果波动率在快速上升
    """
    hv = calculate_historical_volatility(prices)
    
    if len(hv) < 20:
        return False
    
    # 比较近5日均值与近20日均值
    recent_5d = hv.tail(5).mean()
    recent_20d = hv.tail(20).mean()
    
    # 如果近5日波动率比近20日高50%以上，视为飙升
    return recent_5d > recent_20d * 1.5

