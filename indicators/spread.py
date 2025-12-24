"""
利差计算模块 - 计算10年期美日国债利差
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional
import sys
sys.path.append('..')
from config import JP_10Y_YIELD_MANUAL, ALERT_THRESHOLDS


def _to_scalar(val):
    """将 pandas/numpy 值转换为 Python 标量"""
    if hasattr(val, 'item'):
        return val.item()
    if isinstance(val, pd.Series):
        return val.iloc[0] if len(val) > 0 else 0
    return float(val) if val is not None else 0


def calculate_yield_spread(
    us_yield: pd.DataFrame,
    jp_yield: float = JP_10Y_YIELD_MANUAL
) -> pd.DataFrame:
    """
    计算美日10年期国债利差
    
    Args:
        us_yield: 美国10年期国债收益率DataFrame（包含Close列）
        jp_yield: 日本10年期国债收益率（固定值或DataFrame）
    
    Returns:
        包含利差数据的DataFrame
    """
    if us_yield.empty:
        return pd.DataFrame()
    
    spread_df = pd.DataFrame(index=us_yield.index)
    
    # 获取美债收益率
    if 'Close' in us_yield.columns:
        us_rate = us_yield['Close']
    elif 'US_10Y_Yield' in us_yield.columns:
        us_rate = us_yield['US_10Y_Yield']
    else:
        # 尝试获取第一列
        us_rate = us_yield.iloc[:, 0]
    
    spread_df['US_10Y'] = us_rate
    spread_df['JP_10Y'] = jp_yield
    spread_df['Spread'] = us_rate - jp_yield
    
    return spread_df


def get_spread_statistics(spread_df: pd.DataFrame) -> dict:
    """
    计算利差统计数据
    
    Args:
        spread_df: 利差DataFrame
    
    Returns:
        统计数据字典
    """
    if spread_df.empty or 'Spread' not in spread_df.columns:
        return {}
    
    spread = spread_df['Spread'].dropna()
    
    if len(spread) == 0:
        return {}
    
    current_spread = _to_scalar(spread.iloc[-1])
    
    stats = {
        'current': current_spread,
        'mean': _to_scalar(spread.mean()),
        'std': _to_scalar(spread.std()),
        'min': _to_scalar(spread.min()),
        'max': _to_scalar(spread.max()),
        'percentile': _to_scalar((spread < current_spread).sum() / len(spread) * 100),
        'change_1d': _to_scalar(spread.iloc[-1] - spread.iloc[-2]) if len(spread) > 1 else 0,
        'change_5d': _to_scalar(spread.iloc[-1] - spread.iloc[-5]) if len(spread) > 5 else 0,
        'change_20d': _to_scalar(spread.iloc[-1] - spread.iloc[-20]) if len(spread) > 20 else 0,
    }
    
    return stats


def get_spread_trend(spread_df: pd.DataFrame, window: int = 20) -> str:
    """
    判断利差趋势
    
    Args:
        spread_df: 利差DataFrame
        window: 计算窗口
    
    Returns:
        趋势描述: "收窄", "扩大", "震荡"
    """
    if spread_df.empty or 'Spread' not in spread_df.columns:
        return "未知"
    
    spread = spread_df['Spread'].dropna()
    
    if len(spread) < window:
        return "数据不足"
    
    recent = spread.tail(window)
    
    # 计算线性回归斜率
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent.values, 1)[0]
    
    # 根据斜率判断趋势
    threshold = 0.01  # 每天0.01%的变化作为阈值
    
    if slope < -threshold:
        return "收窄"
    elif slope > threshold:
        return "扩大"
    else:
        return "震荡"


def check_spread_alert(current_spread: float) -> Tuple[str, str]:
    """
    检查利差预警状态
    
    Args:
        current_spread: 当前利差值
    
    Returns:
        (预警级别, 预警颜色): 如 ("danger", "#FF1744")
    """
    # 确保是标量
    current_spread = _to_scalar(current_spread)
    
    if current_spread <= ALERT_THRESHOLDS["SPREAD_CRITICAL"]:
        return ("critical", "#9C27B0")  # 紫色 - 极端风险
    elif current_spread <= ALERT_THRESHOLDS["SPREAD_DANGER"]:
        return ("danger", "#FF1744")    # 红色 - 高风险
    elif current_spread <= ALERT_THRESHOLDS["SPREAD_WARNING"]:
        return ("warning", "#FFD600")   # 黄色 - 警告
    else:
        return ("safe", "#00C853")      # 绿色 - 安全


def calculate_spread_velocity(spread_df: pd.DataFrame, window: int = 5) -> float:
    """
    计算利差变化速度（日均变化）
    
    Args:
        spread_df: 利差DataFrame
        window: 计算窗口
    
    Returns:
        日均利差变化（正值表示扩大，负值表示收窄）
    """
    if spread_df.empty or 'Spread' not in spread_df.columns:
        return 0.0
    
    spread = spread_df['Spread'].dropna()
    
    if len(spread) < window:
        return 0.0
    
    recent = spread.tail(window)
    velocity = (recent.iloc[-1] - recent.iloc[0]) / window
    
    return velocity


def is_spread_accelerating(spread_df: pd.DataFrame) -> bool:
    """
    检查利差收窄是否在加速
    
    Returns:
        True 如果利差收窄在加速
    """
    velocity_5d = calculate_spread_velocity(spread_df, 5)
    velocity_20d = calculate_spread_velocity(spread_df, 20)
    
    # 如果短期收窄速度大于长期，说明在加速收窄
    return velocity_5d < velocity_20d and velocity_5d < 0

