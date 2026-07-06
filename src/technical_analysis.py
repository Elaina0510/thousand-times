"""技术指标计算模块 — 计算MA、MACD、成交量、波动率等技术指标。

修复项：
- MA60 使用 min_periods=60，避免前段数据不可靠
- MACD底背离检测：使用局部极值点，要求两次探底确认
- 天量见天价：使用95%分位数替代精确等于
- 均线信号冲突：金叉/死叉同时存在时，只保留最近发生的
- 新增ATR和布林带宽度作为波动率指标
"""

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
    # 波动率指标
    atr: list[float]  # 平均真实波幅（14日）
    bb_upper: list[float]  # 布林带上轨
    bb_lower: list[float]  # 布林带下轨
    bb_width: list[float]  # 布林带宽度 = (上轨-下轨)/中轨


def _fetch_stock_hist_ashare(code: str, days: int) -> pd.DataFrame:
    """使用 BaoStock 获取个股历史行情。

    Args:
        code: 股票代码。
        days: 回溯天数。

    Returns:
        包含历史行情的 DataFrame。
    """
    try:
        from baostock_data import get_stock_hist_baostock
        logger.info(f"使用 BaoStock 获取 {code} 历史数据")
        df = get_stock_hist_baostock(code, days)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"BaoStock 获取 {code} 失败: {e}")

    return pd.DataFrame()


def _fetch_etf_hist_ashare(code: str, days: int) -> pd.DataFrame:
    """使用 BaoStock 获取 ETF 历史行情。

    Args:
        code: ETF 代码。
        days: 回溯天数。

    Returns:
        包含历史行情的 DataFrame。
    """
    try:
        from baostock_data import get_etf_hist_baostock
        logger.info(f"使用 BaoStock 获取 ETF {code} 历史数据")
        df = get_etf_hist_baostock(code, days)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"BaoStock 获取 ETF {code} 失败: {e}")

    return pd.DataFrame()


def _calc_ema(series: pd.Series, n: int) -> pd.Series:
    """计算指数移动平均线（EMA）。

    Args:
        series: 价格序列。
        n: 周期。

    Returns:
        EMA 序列。
    """
    return series.ewm(span=n, adjust=False).mean()


def _calc_ma(series: pd.Series, n: int, min_periods: int | None = None) -> pd.Series:
    """计算简单移动平均线（MA）。

    Args:
        series: 价格序列。
        n: 周期。
        min_periods: 最小数据量（默认等于n，确保MA有效）。

    Returns:
        MA 序列。
    """
    if min_periods is None:
        min_periods = n
    return series.rolling(window=n, min_periods=min_periods).mean()


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


def _calc_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> pd.Series:
    """计算平均真实波幅（ATR）。

    Args:
        highs: 最高价序列。
        lows: 最低价序列。
        closes: 收盘价序列。
        period: 计算周期，默认14日。

    Returns:
        ATR 序列。
    """
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=1).mean()


def _calc_bollinger(
    closes: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """计算布林带。

    Args:
        closes: 收盘价序列。
        period: 中轨周期，默认20日。
        num_std: 标准差倍数，默认2.0。

    Returns:
        (上轨, 下轨, 布林带宽度) 三个序列。宽度 = (上轨-下轨)/中轨。
    """
    mid = closes.rolling(window=period, min_periods=1).mean()
    std = closes.rolling(window=period, min_periods=1).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    # 布林带宽度：归一化波动率
    width = ((upper - lower) / mid * 100).where(mid > 0, 0)
    return upper, lower, width


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
    df = _fetch_etf_hist_ashare(code, days) if is_etf else _fetch_stock_hist_ashare(code, days)
    return _df_to_kline_data(df, code, days)


def get_kline_data_from_cache(df: pd.DataFrame, code: str, days: int = 60) -> KlineData:
    """从缓存的DataFrame获取K线数据并计算技术指标。

    Args:
        df: 缓存的DataFrame（包含 日期, 开盘, 收盘, 最高, 最低, 成交量 列）。
        code: 股票代码（用于日志）。
        days: 回溯天数。

    Returns:
        KlineData 对象。

    Raises:
        RuntimeError: 数据获取失败。
    """
    if df.empty:
        raise RuntimeError(f"缓存数据为空: {code}")

    return _df_to_kline_data(df, code, days)


def _df_to_kline_data(df: pd.DataFrame, code: str, days: int = 60) -> KlineData:
    """将DataFrame转换为KlineData对象。

    Args:
        df: DataFrame（包含日期、开盘、收盘、最高、最低、成交量列）。
        code: 股票代码（用于日志）。
        days: 回溯天数。

    Returns:
        KlineData 对象。

    Raises:
        RuntimeError: 数据获取失败。
    """

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
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)

    # MA — MA60 使用 min_periods=min(60, len)，新股不会全NaN
    ma5 = _calc_ma(closes, 5, min_periods=1)
    ma10 = _calc_ma(closes, 10, min_periods=1)
    ma20 = _calc_ma(closes, 20, min_periods=1)
    ma60 = _calc_ma(closes, 60, min_periods=min(60, len(closes)))

    # MACD
    dif, dea, macd_hist = _calc_macd(closes)

    # 波动率指标
    atr = _calc_atr(highs, lows, closes, period=14)
    bb_upper, bb_lower, bb_width = _calc_bollinger(closes, period=20)

    return KlineData(
        dates=df["date"].astype(str).tolist(),
        opens=df["open"].astype(float).tolist(),
        highs=highs.tolist(),
        lows=lows.tolist(),
        closes=closes.tolist(),
        volumes=df["volume"].astype(float).tolist(),
        ma5=ma5.tolist(),
        ma10=ma10.tolist(),
        ma20=ma20.tolist(),
        ma60=ma60.tolist(),
        dif=dif.tolist(),
        dea=dea.tolist(),
        macd_hist=macd_hist.tolist(),
        atr=atr.tolist(),
        bb_upper=bb_upper.tolist(),
        bb_lower=bb_lower.tolist(),
        bb_width=bb_width.tolist(),
    )


def _find_local_minima(arr: np.ndarray, order: int = 3) -> list[int]:
    """寻找局部极小值点的索引。

    Args:
        arr: 数据数组。
        order: 比较两侧的数据点数（越大越严格）。

    Returns:
        局部极小值点的索引列表。
    """
    minima = []
    for i in range(order, len(arr) - order):
        if arr[i] == min(arr[i - order: i + order + 1]):
            minima.append(i)
    return minima


def calc_technical_signals(kline: KlineData) -> TechnicalSignals:
    """根据K线数据计算所有技术信号。

    修复项：
    - MA金叉/死叉冲突：只保留窗口内最后发生的信号
    - MACD底背离：使用局部极值点检测，要求两次探底确认
    - 天量见天价：使用95%分位数替代精确等于

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

    # 记录 MA60 有效数据天数
    signals.ma60_data_days = int(np.sum(~np.isnan(ma60)))

    # ── MA5/10 金叉/死叉（近3日，冲突时取最后发生的） ──
    last_ma_cross = None  # "golden" or "death"
    for i in range(max(1, n - 3), n):
        if ma5[i] > ma10[i] and ma5[i - 1] <= ma10[i - 1]:
            last_ma_cross = "golden"
        if ma5[i] < ma10[i] and ma5[i - 1] >= ma10[i - 1]:
            last_ma_cross = "death"
    if last_ma_cross == "golden":
        signals.ma5_10_golden = True
    elif last_ma_cross == "death":
        signals.ma5_10_death = True

    # ── MA20/60 金叉（近5日） ──
    for i in range(max(1, n - 5), n):
        if not np.isnan(ma60[i]) and not np.isnan(ma60[i - 1]):
            if ma20[i] > ma60[i] and ma20[i - 1] <= ma60[i - 1]:
                signals.ma20_60_golden = True
                break

    # ── 多头排列（最新一日，MA60有效时才判断） ──
    if not any(np.isnan([ma5[-1], ma10[-1], ma20[-1], ma60[-1]])):
        if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
            signals.bullish_alignment = True

    # ── 股价站上MA20 ──
    if closes[-1] > ma20[-1]:
        signals.above_ma20 = True

    # ── MACD 金叉/死叉（近3日，冲突时取最后发生的） ──
    last_macd_cross = None
    for i in range(max(1, n - 3), n):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            last_macd_cross = "golden"
            # 零轴上方金叉
            if dif[i] > 0 and dea[i] > 0:
                signals.macd_above_zero = True
        if dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]:
            last_macd_cross = "death"
    if last_macd_cross == "golden":
        signals.macd_golden = True
    elif last_macd_cross == "death":
        signals.macd_death = True

    # ── MACD 底背离（近20日，局部极值点检测） ──
    lookback = min(20, n)
    if lookback >= 10:
        recent_closes = closes[-lookback:]
        recent_macd = np.array(kline.macd_hist[-lookback:])

        # 找到价格和MACD的局部极小值点
        price_lows = _find_local_minima(recent_closes, order=3)
        macd_lows = _find_local_minima(recent_macd, order=3)

        if len(price_lows) >= 2 and len(macd_lows) >= 2:
            # 取最近两个价格低点
            p1_idx, p2_idx = price_lows[-2], price_lows[-1]
            # 在MACD中找到对应时间窗口内的低点
            m1_candidates = [m for m in macd_lows if abs(m - p1_idx) <= 3]
            m2_candidates = [m for m in macd_lows if abs(m - p2_idx) <= 3]

            if m1_candidates and m2_candidates:
                m1_idx = m1_candidates[-1]
                m2_idx = m2_candidates[-1]
                # 底背离：价格创新低，MACD未创新低
                if (recent_closes[p2_idx] < recent_closes[p1_idx]
                        and recent_macd[m2_idx] > recent_macd[m1_idx]):
                    signals.macd_divergence = True

    # ── 成交量信号 ──
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

        # 天量见天价（成交量达到60日95%分位数且股价在MA20上方）
        vol_95th = np.percentile(volumes, 95)
        if volumes[-1] >= vol_95th and closes[-1] > ma20[-1]:
            signals.volume_peak = True

        # 缩量回调到位（回调至MA20附近±2%且量比 < 0.7）
        ma20_pct = abs(closes[-1] - ma20[-1]) / ma20[-1] * 100 if ma20[-1] > 0 else 0
        if ma20_pct <= 2 and volume_ratio < 0.7:
            signals.pullback_ok = True

    return signals


def calc_technical_score(
    signals: TechnicalSignals,
    weights: TechnicalWeightConfig,
    kline: KlineData | None = None,
) -> float:
    """根据技术信号和权重计算技术指标评分。

    Args:
        signals: 技术信号汇总。
        weights: 技术指标权重配置。
        kline: K线数据（可选，用于计算基线分）。

    Returns:
        评分（0~40分，负分截断到0）。
    """
    score = 0.0

    # MA60 数据不足时，相关信号权重减半
    ma60_days = getattr(signals, 'ma60_data_days', 60)
    ma60_penalty = 0.5 if ma60_days < 60 else 1.0

    # 加分项
    if signals.ma5_10_golden:
        score += weights.ma_golden_cross
    if signals.ma20_60_golden:
        score += weights.ma20_60_golden_cross * ma60_penalty
    if signals.bullish_alignment:
        score += weights.bullish_alignment * ma60_penalty
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

    # 基线分：近期涨跌幅（有K线数据时）
    if kline is not None and len(kline.closes) >= 5:
        closes_arr = np.array(kline.closes)
        change_5d = (closes_arr[-1] - closes_arr[-5]) / closes_arr[-5] * 100 if closes_arr[-5] > 0 else 0
        change_20d = 0.0
        if len(closes_arr) >= 20 and closes_arr[-20] > 0:
            change_20d = (closes_arr[-1] - closes_arr[-20]) / closes_arr[-20] * 100
        if change_5d > 0:
            score += 5.0
        if change_20d > 0:
            score += 3.0

    # 截断到 0
    return max(0.0, score)
