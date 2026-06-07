"""Ashare 数据源模块 — 使用新浪/腾讯双源获取 A 股数据。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger("thousand-times")


def _convert_code(code: str) -> str:
    """将股票代码转换为 Ashare 格式。

    Args:
        code: 股票代码，如 '600519', '000001', '512480'

    Returns:
        Ashare 格式代码，如 'sh600519', 'sz000001'
    """
    code = code.strip()

    # 如果已经是 sh/sz 格式，直接返回
    if code.startswith('sh') or code.startswith('sz'):
        return code

    # 如果是 .XSHG/.XSHE 格式，直接返回
    if '.XSHG' in code or '.XSHE' in code:
        return code

    # 根据代码判断交易所
    # 上海：6开头的股票，5开头的ETF，000001（上证指数）
    # 深圳：0/3开头的股票，1开头的ETF
    if code.startswith('6') or code.startswith('5'):
        return f'sh{code}'
    elif code.startswith('0') or code.startswith('3') or code.startswith('1'):
        return f'sz{code}'
    else:
        # 默认尝试上海
        return f'sh{code}'


def get_stock_hist_ashare(code: str, days: int = 60) -> pd.DataFrame:
    """使用 Ashare 获取个股历史行情。

    Args:
        code: 股票代码
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    try:
        from ashare import get_price

        ashare_code = _convert_code(code)
        logger.info(f"使用 Ashare 获取 {ashare_code} 历史数据")

        df = get_price(ashare_code, frequency='1d', count=days)

        if df is None or df.empty:
            logger.warning(f"Ashare 返回空数据: {code}")
            return pd.DataFrame()

        # 重命名列以匹配 AKShare 格式
        df = df.reset_index()
        df = df.rename(columns={
            'index': '日期',
            'time': '日期',
            'day': '日期',
            'open': '开盘',
            'close': '收盘',
            'high': '最高',
            'low': '最低',
            'volume': '成交量',
        })

        # 确保日期列存在
        if '日期' not in df.columns:
            df['日期'] = df.index

        logger.info(f"Ashare 获取 {code} 成功，共 {len(df)} 条数据")
        return df

    except Exception as e:
        logger.error(f"Ashare 获取 {code} 失败: {e}")
        return pd.DataFrame()


def get_etf_hist_ashare(code: str, days: int = 60) -> pd.DataFrame:
    """使用 Ashare 获取 ETF 历史行情。

    Args:
        code: ETF 代码
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    # ETF 和股票使用相同的接口
    return get_stock_hist_ashare(code, days)


def get_index_hist_ashare(code: str, days: int = 60) -> pd.DataFrame:
    """使用 Ashare 获取指数历史行情。

    Args:
        code: 指数代码，如 '000001'（上证指数）
        days: 获取天数

    Returns:
        DataFrame，包含 open, close, high, low, volume 列
    """
    try:
        from ashare import get_price

        # 指数代码格式
        if code == '000001':
            ashare_code = 'sh000001'
        elif code == '399006':
            ashare_code = 'sz399006'
        elif code == '399001':
            ashare_code = 'sz399001'
        else:
            ashare_code = _convert_code(code)

        logger.info(f"使用 Ashare 获取指数 {ashare_code} 历史数据")

        df = get_price(ashare_code, frequency='1d', count=days)

        if df is None or df.empty:
            logger.warning(f"Ashare 返回空数据: {code}")
            return pd.DataFrame()

        # 重命名列
        df = df.reset_index()
        df = df.rename(columns={
            'index': '日期',
            'time': '日期',
            'day': '日期',
            'open': '开盘',
            'close': '收盘',
            'high': '最高',
            'low': '最低',
            'volume': '成交量',
        })

        if '日期' not in df.columns:
            df['日期'] = df.index

        return df

    except Exception as e:
        logger.error(f"Ashare 获取指数 {code} 失败: {e}")
        return pd.DataFrame()


def test_ashare() -> bool:
    """测试 Ashare 是否可用。

    Returns:
        是否可用
    """
    try:
        from ashare import get_price

        # 测试获取上证指数
        df = get_price('sh000001', frequency='1d', count=5)

        if df is not None and not df.empty:
            logger.info("Ashare 测试成功")
            return True
        else:
            logger.warning("Ashare 测试失败：返回空数据")
            return False

    except Exception as e:
        logger.warning(f"Ashare 测试失败: {e}")
        return False


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("测试 Ashare 数据源...")
    if test_ashare():
        print("✅ Ashare 可用")

        # 测试获取贵州茅台
        df = get_stock_hist_ashare('600519', days=10)
        print(f"\n贵州茅台最近10天数据:")
        print(df)
    else:
        print("❌ Ashare 不可用")
