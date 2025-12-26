"""
数据获取模块 - 使用 yfinance 获取金融数据
"""

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sys
sys.path.append('..')
from config import TICKERS, CALC_PARAMS, JP_10Y_YIELD_MANUAL


@st.cache_data(ttl=3600)  # 缓存1小时
def fetch_ticker_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    获取单个标的的历史数据
    
    Args:
        ticker: yfinance代码
        period: 数据周期 (1mo, 3mo, 6mo, 1y, 2y)
    
    Returns:
        包含OHLCV数据的DataFrame
    """
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            st.warning(f"无法获取 {ticker} 的数据")
            return pd.DataFrame()
        
        # 处理 yfinance 返回的 MultiIndex 列
        if isinstance(data.columns, pd.MultiIndex):
            # 只保留第一层列名 (Open, High, Low, Close, Volume, etc.)
            data.columns = data.columns.get_level_values(0)
        
        return data
    except Exception as e:
        st.error(f"获取 {ticker} 数据时出错: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_multiple_tickers(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    批量获取多个标的的数据
    
    Args:
        tickers: yfinance代码列表
        period: 数据周期
    
    Returns:
        标的代码到DataFrame的字典
    """
    result = {}
    for ticker in tickers:
        result[ticker] = fetch_ticker_data(ticker, period)
    return result


@st.cache_data(ttl=3600)
def get_us_10y_yield(period: str = "6mo") -> pd.DataFrame:
    """
    获取美国10年期国债收益率
    """
    data = fetch_ticker_data(TICKERS["US_10Y"], period)
    if not data.empty:
        # ^TNX返回的是收益率的百分比值，需要保持原样
        data = data.rename(columns={"Close": "US_10Y_Yield"})
    return data


@st.cache_data(ttl=3600)
def get_jp_10y_yield(period: str = "6mo") -> pd.DataFrame:
    """
    获取日本10年期国债收益率
    使用 yfinance ^JGB10Y 代码获取实时数据
    如果获取失败，使用手动设置的备用值
    """
    try:
        data = fetch_ticker_data(TICKERS["JP_10Y"], period)
        if not data.empty:
            data = data.rename(columns={"Close": "JP_10Y_Yield"})
            return data
    except Exception as e:
        st.warning(f"无法获取日本国债收益率: {str(e)}")
    
    # 如果获取失败，使用手动设置的备用值
    us_data = get_us_10y_yield(period)
    if us_data.empty:
        return pd.DataFrame()
    
    jp_yield = pd.DataFrame(index=us_data.index)
    jp_yield["JP_10Y_Yield"] = JP_10Y_YIELD_MANUAL
    st.info("使用手动设置的日本国债收益率备用值")
    return jp_yield


@st.cache_data(ttl=3600)
def get_usdjpy(period: str = "6mo") -> pd.DataFrame:
    """
    获取美元兑日元汇率
    """
    data = fetch_ticker_data(TICKERS["USDJPY"], period)
    return data


@st.cache_data(ttl=3600)
def get_high_beta_assets(period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    获取高贝塔资产数据（BTC、新兴市场）
    """
    tickers = [TICKERS["BTC"], TICKERS["EEM"]]
    return fetch_multiple_tickers(tickers, period)


@st.cache_data(ttl=3600)
def get_benchmark_assets(period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    获取大盘基准资产数据
    """
    tickers = [TICKERS["SPY"], TICKERS["NDX"]]
    return fetch_multiple_tickers(tickers, period)


@st.cache_data(ttl=3600)
def get_all_data(period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """
    获取所有需要的数据
    """
    all_tickers = list(TICKERS.values())
    return fetch_multiple_tickers(all_tickers, period)


def get_latest_price(ticker: str) -> Optional[float]:
    """
    获取最新价格
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return None
    except Exception:
        return None


def get_current_usdjpy() -> Optional[float]:
    """
    获取当前美元兑日元汇率
    """
    return get_latest_price(TICKERS["USDJPY"])


def get_current_us_10y() -> Optional[float]:
    """
    获取当前美国10年期国债收益率
    """
    return get_latest_price(TICKERS["US_10Y"])


def get_data_freshness() -> str:
    """
    返回数据新鲜度信息
    """
    now = datetime.now()
    return f"数据更新时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"

