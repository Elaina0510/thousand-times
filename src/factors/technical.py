"""技术面因子计算。"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


def calc_technical_factor(kline: pd.DataFrame) -> float:
    """计算技术面因子评分.

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

        # MA趋势
        ma5 = closes.rolling(5).mean().iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        last_close = closes.iloc[-1]

        trend_score = 50.0
        if last_close > ma5 > ma20:
            trend_score = 70.0
        elif last_close < ma5 < ma20:
            trend_score = 30.0

        # 动量
        ret5 = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100 if len(closes) >= 6 else 0
        momentum_score = min(max(50 + ret5 * 5, 0), 100)

        return round((trend_score * 0.6 + momentum_score * 0.4), 2)
    except Exception as e:
        logger.warning(f"技术因子计算异常: {e}")
        return 50.0
