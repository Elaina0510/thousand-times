"""技术面因子计算.

子因子：
- MA趋势得分（MA5/MA10/MA20/MA60 排列 + 交叉）
- MACD得分（DIF/DEA 交叉 + 柱状图方向）
- 成交量得分（量比 + 量能趋势）
- 布林带得分（价格相对布林带位置）
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


def _get_close(kline: pd.DataFrame) -> pd.Series:
    """获取收盘价列。"""
    close_col = "收盘" if "收盘" in kline.columns else "close"
    return kline[close_col].astype(float)


def _get_volume(kline: pd.DataFrame) -> pd.Series:
    """获取成交量列。"""
    vol_col = "成交量" if "成交量" in kline.columns else "volume"
    return kline[vol_col].astype(float)


def calc_ma_trend_score(kline: pd.DataFrame) -> float:
    """MA趋势得分.

    基于 MA5/MA10/MA20/MA60 的排列关系和价格位置。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 60:
        return 50.0

    try:
        closes = _get_close(kline)
        last = closes.iloc[-1]
        ma5 = closes.rolling(5).mean().iloc[-1]
        ma10 = closes.rolling(10).mean().iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        ma60 = closes.rolling(60).mean().iloc[-1]

        score = 50.0

        # 多头排列: price > MA5 > MA10 > MA20 > MA60
        if last > ma5 > ma10 > ma20 > ma60:
            score = 85.0
        # 准多头: price > MA5 > MA20
        elif last > ma5 > ma20:
            score = 70.0
        # 空头排列: price < MA5 < MA10 < MA20 < MA60
        elif last < ma5 < ma10 < ma20 < ma60:
            score = 15.0
        # 准空头: price < MA5 < MA20
        elif last < ma5 < ma20:
            score = 30.0
        # 均线纠缠
        else:
            score = 50.0

        # 金叉/死叉加减分
        if len(closes) >= 2:
            prev_ma5 = closes.rolling(5).mean().iloc[-2]
            prev_ma20 = closes.rolling(20).mean().iloc[-2]
            if prev_ma5 <= prev_ma20 and ma5 > ma20:
                score = min(score + 10, 100)  # 金叉
            elif prev_ma5 >= prev_ma20 and ma5 < ma20:
                score = max(score - 10, 0)  # 死叉

        return round(score, 2)
    except Exception as e:
        logger.warning(f"MA趋势计算异常: {e}")
        return 50.0


def calc_macd_score(kline: pd.DataFrame) -> float:
    """MACD得分.

    基于 DIF/DEA 交叉、柱状图方向和背离。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 35:
        return 50.0

    try:
        closes = _get_close(kline)

        # 计算 EMA12/EMA26
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        histogram = (dif - dea) * 2

        last_dif = dif.iloc[-1]
        last_dea = dea.iloc[-1]
        last_hist = histogram.iloc[-1]
        prev_dif = dif.iloc[-2]
        prev_dea = dea.iloc[-2]

        score = 50.0

        # DIF > DEA（多头）
        if last_dif > last_dea:
            score += 15
        else:
            score -= 15

        # 金叉/死叉
        if prev_dif <= prev_dea and last_dif > last_dea:
            score += 15  # 金叉
        elif prev_dif >= prev_dea and last_dif < last_dea:
            score -= 15  # 死叉

        # 柱状图方向
        if len(histogram) >= 2:
            if last_hist > histogram.iloc[-2]:
                score += 5  # 柱状图放大
            else:
                score -= 5  # 柱状图缩小

        # 零轴上方加分
        if last_dif > 0:
            score += 5
        else:
            score -= 5

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"MACD计算异常: {e}")
        return 50.0


def calc_volume_score(kline: pd.DataFrame) -> float:
    """成交量得分.

    基于量比和量能趋势。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 20:
        return 50.0

    try:
        volumes = _get_volume(kline)
        closes = _get_close(kline)

        # 量比：近5日均量 / 近20日均量
        vol_5 = volumes.tail(5).mean()
        vol_20 = volumes.tail(20).mean()
        vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

        # 价格方向
        price_up = closes.iloc[-1] > closes.iloc[-6] if len(closes) >= 6 else True

        score = 50.0

        # 放量上涨 → 看多
        if vol_ratio > 1.3 and price_up:
            score = 75.0
        # 放量下跌 → 看空
        elif vol_ratio > 1.5 and not price_up:
            score = 25.0
        # 缩量上涨 → 弱势反弹
        elif vol_ratio < 0.7 and price_up:
            score = 45.0
        # 缩量下跌 → 抛压减轻
        elif vol_ratio < 0.7 and not price_up:
            score = 55.0
        # 温和放量
        elif vol_ratio > 1.1:
            score = 60.0
        # 温和缩量
        elif vol_ratio < 0.9:
            score = 40.0

        return round(score, 2)
    except Exception as e:
        logger.warning(f"成交量计算异常: {e}")
        return 50.0


def calc_bollinger_score(kline: pd.DataFrame) -> float:
    """布林带得分.

    基于价格相对布林带的位置。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 20:
        return 50.0

    try:
        closes = _get_close(kline)

        # 布林带参数
        ma20 = closes.rolling(20).mean()
        std20 = closes.rolling(20).std()
        upper = ma20 + 2 * std20
        lower = ma20 - 2 * std20

        last_close = closes.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]
        last_ma20 = ma20.iloc[-1]

        band_width = last_upper - last_lower
        if band_width <= 0:
            return 50.0

        # 价格在布林带中的相对位置 (0=下轨, 1=上轨)
        position = (last_close - last_lower) / band_width

        # 接近下轨 → 超卖 → 看多
        if position < 0.1:
            score = 75.0
        elif position < 0.3:
            score = 65.0
        # 接近上轨 → 超买 → 看空
        elif position > 0.9:
            score = 25.0
        elif position > 0.7:
            score = 35.0
        # 中轨附近
        else:
            score = 50.0

        # 突破上轨（强势）加分
        if last_close > last_upper:
            score = max(score, 70.0)
        # 跌破下轨（弱势）减分
        elif last_close < last_lower:
            score = min(score, 30.0)

        return round(score, 2)
    except Exception as e:
        logger.warning(f"布林带计算异常: {e}")
        return 50.0


def calc_technical_factor(kline: pd.DataFrame) -> dict[str, float]:
    """计算技术面因子综合评分.

    Args:
        kline: K线数据 DataFrame。

    Returns:
        dict with keys: ma_trend, macd, volume, bollinger, score。
        数据不足时各项返回 50。
    """
    if kline.empty or len(kline) < 20:
        return {"ma_trend": 50.0, "macd": 50.0, "volume": 50.0, "bollinger": 50.0, "score": 50.0}

    try:
        ma_trend = calc_ma_trend_score(kline)
        macd = calc_macd_score(kline)
        volume = calc_volume_score(kline)
        bollinger = calc_bollinger_score(kline)

        # 等权平均
        score = round((ma_trend + macd + volume + bollinger) / 4, 2)

        return {
            "ma_trend": ma_trend,
            "macd": macd,
            "volume": volume,
            "bollinger": bollinger,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"技术因子计算异常: {e}")
        return {"ma_trend": 50.0, "macd": 50.0, "volume": 50.0, "bollinger": 50.0, "score": 50.0}
