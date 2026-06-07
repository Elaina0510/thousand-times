"""技术指标计算模块 — 计算MA、MACD、成交量等技术指标。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import TechnicalWeightConfig
from scoring import TechnicalSignals
from utils import random_delay, retry

logger = logging.getLogger("thousand-times")


@dataclass
class KlineData:
    """K线数据。"""

    dates: list[str]  # 日期列表
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
    ma5: list[float]
    ma10: list[float]
    ma20: list[float]
    ma60: list[float]
    dif: list[float]
    dea: list[float]
    macd_hist: list[float]


def _fetch_stock_hist_ashare(code: str, days: int) -> pd.DataFrame:
    """使用 Ashare 获取个股历史行情。

    Args:
        code: 股票代码。
        days: 回溯天数。

    Returns:
        包含历史行情的 DataFrame。
    """
    try:
        from ashare_data import get_stock_hist_ashare
        df = get_stock_hist_ashare(code, days)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"Ashare 获取 {code} 失败: {e}")

    # 回退到 AKShare
    import akshare as ak  # type: ignore[import-untyped]
    result: pd.DataFrame = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        adjust="qfq",
    )
    return result


def _fetch_etf_hist_ashare(code: str, days: int) -> pd.DataFrame:
    """使用 Ashare 获取 ETF 历史行情。

    Args:
        code: ETF 代码。
        days: 回溯天数。

    Returns:
        包含历史行情的 DataFrame。
    """
    try:
        from ashare_data import get_etf_hist_ashare
        df = get_etf_hist_ashare(code, days)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"Ashare 获取 ETF {code} 失败: {e}")

    # 回退到 AKShare
    import akshare as ak  # type: ignore[import-untyped]
    result: pd.DataFrame = ak.fund_etf_hist_em(
        symbol=code,
        period="daily",
        adjust="qfq",
    )
    return result


def _calc_ema(series: pd.Series, n: int) -> pd.Series:
    """计算指数移动平均线（EMA）。

    Args:
        series: 价格序列。
        n: 周期。

    Returns:
        EMA 序列。
    """
    return series.ewm(span=n, adjust=False).mean()


def _calc_ma(series: pd.Series, n: int) -> pd.Series:
    """计算简单移动平均线（MA）。

    Args:
        series: 价格序列。
        n: 周期。

    Returns:
        MA 序列。
    """
    return series.rolling(window=n, min_periods=1).mean()


def _calc_macd(closes: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """计算MACD指标。

    Args:
        closes: 收盘价序列。

    Returns:
        (DIF, DEA, MACD柱) 三个序列。
    """
    ema12 = _calc_ema(closes, 12)
    ema26 = _calc_ema(closes, 26)
    dif = ema12 - ema26
    dea = _calc_ema(dif, 9)
    macd_hist = (dif - dea) * 2
    return dif, dea, macd_hist


def get_kline_data(code: str, days: int = 60, is_etf: bool = False) -> KlineData:
    """获取K线数据并计算技术指标。

    Args:
        code: 股票/ETF代码。
        days: 回溯天数。
        is_etf: 是否为ETF。

    Returns:
        KlineData 对象。

    Raises:
        RuntimeError: 数据获取失败。
    """
    # 获取历史行情
    df = _fetch_etf_hist_ashare(code, days) if is_etf else _fetch_stock_hist_ashare(code, days)

    random_delay()

    # 重命名列
    column_mapping = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)

    # 确保必要的列存在
    required_columns = ["date", "open", "high", "low", "close", "volume"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"数据缺少必要列: {col}")

    # 取最近 days 天的数据
    df = df.tail(days).reset_index(drop=True)

    # 计算技术指标
    closes = df["close"].astype(float)

    # MA
    ma5 = _calc_ma(closes, 5)
    ma10 = _calc_ma(closes, 10)
    ma20 = _calc_ma(closes, 20)
    ma60 = _calc_ma(closes, 60)

    # MACD
    dif, dea, macd_hist = _calc_macd(closes)

    return KlineData(
        dates=df["date"].astype(str).tolist(),
        opens=df["open"].astype(float).tolist(),
        highs=df["high"].astype(float).tolist(),
        lows=df["low"].astype(float).tolist(),
        closes=closes.tolist(),
        volumes=df["volume"].astype(float).tolist(),
        ma5=ma5.tolist(),
        ma10=ma10.tolist(),
        ma20=ma20.tolist(),
        ma60=ma60.tolist(),
        dif=dif.tolist(),
        dea=dea.tolist(),
        macd_hist=macd_hist.tolist(),
    )


def calc_technical_signals(kline: KlineData) -> TechnicalSignals:
    """根据K线数据计算所有技术信号。

    Args:
        kline: K线数据。

    Returns:
        TechnicalSignals 对象。
    """
    n = len(kline.closes)
    if n < 2:
        return TechnicalSignals()

    closes = np.array(kline.closes)
    ma5 = np.array(kline.ma5)
    ma10 = np.array(kline.ma10)
    ma20 = np.array(kline.ma20)
    ma60 = np.array(kline.ma60)
    dif = np.array(kline.dif)
    dea = np.array(kline.dea)
    volumes = np.array(kline.volumes)

    signals = TechnicalSignals()

    # MA5/10 金叉（近3日）
    for i in range(max(0, n - 3), n):
        if i > 0 and ma5[i] > ma10[i] and ma5[i - 1] <= ma10[i - 1]:
            signals.ma5_10_golden = True
            break

    # MA5/10 死叉（近3日）
    for i in range(max(0, n - 3), n):
        if i > 0 and ma5[i] < ma10[i] and ma5[i - 1] >= ma10[i - 1]:
            signals.ma5_10_death = True
            break

    # MA20/60 金叉（近5日）
    for i in range(max(0, n - 5), n):
        if i > 0 and ma20[i] > ma60[i] and ma20[i - 1] <= ma60[i - 1]:
            signals.ma20_60_golden = True
            break

    # 多头排列（最新一日）
    if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
        signals.bullish_alignment = True

    # 股价站上MA20（最新一日）
    if closes[-1] > ma20[-1]:
        signals.above_ma20 = True

    # MACD 金叉（近3日）
    for i in range(max(0, n - 3), n):
        if i > 0 and dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            signals.macd_golden = True
            # 零轴上方金叉
            if dif[i] > 0 and dea[i] > 0:
                signals.macd_above_zero = True
            break

    # MACD 死叉（近3日）
    for i in range(max(0, n - 3), n):
        if i > 0 and dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]:
            signals.macd_death = True
            break

    # MACD 底背离（近10日）
    if n >= 10:
        recent_10 = closes[-10:]
        macd_10 = np.array(kline.macd_hist[-10:])
        # 找到股价最低点
        price_min_idx = np.argmin(recent_10)
        # 找到MACD最低点
        macd_min_idx = np.argmin(macd_10)
        # 如果股价创新低但MACD不创新低，认为底背离
        if price_min_idx > macd_min_idx and recent_10[price_min_idx] < recent_10[0]:
            signals.macd_divergence = True

    # 成交量信号
    if n >= 5:
        # 量比 = 当日成交量 / 近5日平均成交量
        avg_vol_5 = np.mean(volumes[-6:-1]) if n >= 6 else np.mean(volumes[-5:])
        volume_ratio = volumes[-1] / avg_vol_5 if avg_vol_5 > 0 else 0

        # 涨跌幅
        change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] > 0 else 0

        # 放量上涨（涨幅 > 0 且量比 > 1.5）
        if change_pct > 0 and volume_ratio > 1.5:
            signals.volume_up = True

        # 放量下跌（跌幅 > 2% 且量比 > 2.0）
        if change_pct < -2 and volume_ratio > 2.0:
            signals.volume_down = True

        # 天量见天价（成交量60日新高且股价高位）
        if volumes[-1] == np.max(volumes) and closes[-1] > ma20[-1]:
            signals.volume_peak = True

        # 缩量回调到位（回调至MA20附近±2%且量比 < 0.7）
        ma20_pct = abs(closes[-1] - ma20[-1]) / ma20[-1] * 100 if ma20[-1] > 0 else 0
        if ma20_pct <= 2 and volume_ratio < 0.7:
            signals.pullback_ok = True

    return signals


def calc_technical_score(signals: TechnicalSignals, weights: TechnicalWeightConfig) -> float:
    """根据技术信号和权重计算技术指标评分。

    Args:
        signals: 技术信号汇总。
        weights: 技术指标权重配置。

    Returns:
        评分（0~40分，负分截断到0）。
    """
    score = 0.0

    # 加分项
    if signals.ma5_10_golden:
        score += weights.ma_golden_cross
    if signals.ma20_60_golden:
        score += weights.ma20_60_golden_cross
    if signals.bullish_alignment:
        score += weights.bullish_alignment
    if signals.above_ma20:
        score += weights.above_ma20
    if signals.macd_golden:
        score += weights.macd_golden_cross
    if signals.macd_above_zero:
        score += weights.macd_above_zero
    if signals.macd_divergence:
        score += weights.macd_divergence
    if signals.volume_up:
        score += weights.volume_up
    if signals.pullback_ok:
        score += weights.pullback_ok

    # 扣分项
    if signals.ma5_10_death:
        score -= weights.ma_death_cross
    if signals.macd_death:
        score -= weights.macd_death_cross
    if signals.volume_peak:
        score -= weights.volume_peak
    if signals.volume_down:
        score -= weights.volume_drop

    # 截断到 0
    return max(0.0, score)
