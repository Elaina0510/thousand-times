"""北向资金数据源.

获取北向资金（沪股通+深股通）每日净流入和个股持仓变动。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import pandas as pd

logger = logging.getLogger("thousand-times")

_API_TIMEOUT = 15


def fetch_north_flow(days: int = 5) -> pd.DataFrame:
    """获取北向资金每日净流入.

    Args:
        days: 获取最近 N 天的数据。

    Returns:
        DataFrame with columns: 日期, 当日成交净买额, 当日资金流入。
        API 失败时返回空 DataFrame。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ak.stock_hsgt_hist_em, symbol="北向资金")
            df = future.result(timeout=_API_TIMEOUT)
        if df is None or df.empty:
            logger.warning("北向资金数据为空")
            return pd.DataFrame()
        return df.tail(days).reset_index(drop=True)
    except FuturesTimeout:
        logger.warning(f"获取北向资金超时 ({_API_TIMEOUT}s)")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        return pd.DataFrame()


def fetch_north_flow_stock(code: str) -> float:
    """获取个股北向持仓变动（持股数量）.

    Args:
        code: 股票代码，如 "600519"。

    Returns:
        持股数量（股），获取失败返回 0.0。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("AKShare 不可用")
        return 0.0

    for market in ["沪股通", "深股通"]:
        try:
            df = ak.stock_hsgt_hold_stock_em(market=market, indicator="今日排行")
            if df is None or df.empty:
                continue
            row = df[df["代码"] == code]
            if len(row) > 0:
                return float(row.iloc[0]["今日持股-股数"])
        except Exception as e:
            logger.debug(f"获取{market}持仓失败: {e}")
            continue
    return 0.0
