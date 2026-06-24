"""动量因子计算.

子因子：
- 短期动量（近5日/10日收益率）
- 中期动量（近20日/60日收益率）
- 相对强弱（个股 vs 指数相对收益）
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _get_close(kline: pd.DataFrame) -> pd.Series:
    """获取收盘价列。"""
    close_col = "收盘" if "收盘" in kline.columns else "close"
    return kline[close_col].astype(float)


def _calc_short_momentum(kline: pd.DataFrame) -> float:
    """短期动量得分.

    基于近5日和10日收益率。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 10:
        return 50.0

    try:
        closes = _get_close(kline)

        # 5日收益率
        ret5 = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100 if len(closes) >= 6 else 0
        # 10日收益率
        ret10 = (closes.iloc[-1] / closes.iloc[-11] - 1) * 100 if len(closes) >= 11 else 0

        # 加权
        momentum = ret5 * 0.6 + ret10 * 0.4

        # 映射到 0-100: 50 为中性，每 1% 收益率偏移 3 分
        score = 50 + momentum * 3

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"短期动量计算异常: {e}")
        return 50.0


def _calc_mid_momentum(kline: pd.DataFrame) -> float:
    """中期动量得分.

    基于近20日和60日收益率。

    Args:
        kline: K线数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 20:
        return 50.0

    try:
        closes = _get_close(kline)

        # 20日收益率
        ret20 = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100 if len(closes) >= 21 else 0
        # 60日收益率
        ret60 = (closes.iloc[-1] / closes.iloc[-61] - 1) * 100 if len(closes) >= 61 else 0

        # 加权
        momentum = ret20 * 0.6 + ret60 * 0.4

        # 映射到 0-100
        score = 50 + momentum * 2

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"中期动量计算异常: {e}")
        return 50.0


def _calc_relative_strength(kline: pd.DataFrame, benchmark_kline: pd.DataFrame | None) -> float:
    """相对强弱得分.

    个股 vs 指数的相对收益。

    Args:
        kline: 个股K线数据。
        benchmark_kline: 基准指数K线数据（可选）。

    Returns:
        评分 0~100。
    """
    if kline.empty or len(kline) < 20:
        return 50.0

    if benchmark_kline is None or benchmark_kline.empty or len(benchmark_kline) < 20:
        return 50.0

    try:
        stock_close = _get_close(kline)
        bench_close = _get_close(benchmark_kline)

        # 对齐长度（取较短的）
        n = min(len(stock_close), len(bench_close))
        stock_close = stock_close.tail(n).reset_index(drop=True)
        bench_close = bench_close.tail(n).reset_index(drop=True)

        if n < 20:
            return 50.0

        # 20日相对收益
        stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-21] - 1) * 100 if n >= 21 else 0
        bench_ret = (bench_close.iloc[-1] / bench_close.iloc[-21] - 1) * 100 if n >= 21 else 0

        rs = stock_ret - bench_ret

        # 映射到 0-100
        score = 50 + rs * 2

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"相对强弱计算异常: {e}")
        return 50.0


def calc_momentum_factor(
    kline: pd.DataFrame,
    benchmark_kline: pd.DataFrame | None = None,
) -> dict[str, float]:
    """计算动量因子综合评分.

    Args:
        kline: K线数据 DataFrame。
        benchmark_kline: 基准指数K线数据（可选）。

    Returns:
        dict with keys: short_momentum, mid_momentum, relative_strength, score。
    """
    if kline.empty or len(kline) < 10:
        return {
            "short_momentum": 50.0,
            "mid_momentum": 50.0,
            "relative_strength": 50.0,
            "score": 50.0,
        }

    try:
        short = _calc_short_momentum(kline)
        mid = _calc_mid_momentum(kline)
        rs = _calc_relative_strength(kline, benchmark_kline)

        # 短期 40%，中期 40%，相对强弱 20%
        score = round(short * 0.4 + mid * 0.4 + rs * 0.2, 2)

        return {
            "short_momentum": short,
            "mid_momentum": mid,
            "relative_strength": rs,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"动量因子计算异常: {e}")
        return {
            "short_momentum": 50.0,
            "mid_momentum": 50.0,
            "relative_strength": 50.0,
            "score": 50.0,
        }
