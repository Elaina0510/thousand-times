"""动量因子计算。"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def calc_momentum_factor(kline: pd.DataFrame) -> float:
    """计算动量因子评分.

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    if kline.empty or len(kline) < 20:
        return 50.0

    try:
        close_col = "收盘" if "收盘" in kline.columns else "close"
        closes = kline[close_col].astype(float)

        # 5日动量
        ret5 = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100 if len(closes) >= 6 else 0
        # 20日动量
        ret20 = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100 if len(closes) >= 21 else 0

        # 综合动量
        momentum = ret5 * 0.4 + ret20 * 0.6
        score = 50 + momentum * 3

        return min(max(score, 0), 100)
    except Exception as e:
        logger.warning(f"动量因子计算异常: {e}")
        return 50.0
