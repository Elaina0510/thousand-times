"""市场环境判断模块.

使用5信号投票制判断牛市/熊市/震荡市：
1. 趋势信号 — MA均线排列
2. 成交量信号 — 量能变化
3. 北向资金信号 — 外资流向
4. 涨跌比信号 — 市场广度
5. 估值信号 — PE百分位
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class RegimeVote:
    """单个信号的投票结果。"""

    signal_name: str
    vote: str  # "bull", "bear", "neutral"
    confidence: float = 0.0  # 0.0 ~ 1.0
    reason: str = ""


@dataclass
class MarketRegime:
    """市场环境判断结果。"""

    state: str  # "bull", "bear", "sideways"
    confidence: float = 0.0  # 0.0 ~ 1.0
    position_advice: float = 0.5  # 建议仓位 0.0 ~ 1.0
    signals: dict[str, str] = field(default_factory=dict)  # signal_name -> vote
    description: str = ""
    adjusted_weights: object | None = None  # ScoreWeightConfig


def judge_market_regime(data: object, config: object) -> MarketRegime:
    """判断市场环境.

    Args:
        data: DataBundle 数据包。
        config: AppConfig 配置。

    Returns:
        MarketRegime 市场环境判断结果。
    """
    votes: list[RegimeVote] = []

    # 1. 趋势信号
    index_kline = getattr(data, "index_kline", pd.DataFrame())
    regime_config = getattr(config, "regime", None)
    if regime_config is None:
        from src.config import RegimeConfig
        regime_config = RegimeConfig()

    if not index_kline.empty:
        votes.append(_signal_trend(index_kline, regime_config))
        votes.append(_signal_volume(index_kline, regime_config))
    else:
        votes.append(RegimeVote("trend", "neutral", 0.0, "无指数数据"))
        votes.append(RegimeVote("volume", "neutral", 0.0, "无指数数据"))

    # 2. 北向资金信号
    north_flow = getattr(data, "north_flow", pd.DataFrame())
    votes.append(_signal_north_flow(north_flow, regime_config))

    # 3. 涨跌比信号
    advance_decline_ratio = getattr(data, "advance_decline_ratio", 1.0)
    votes.append(_signal_advance_decline(advance_decline_ratio, regime_config))

    # 4. 估值信号（简化：使用涨跌比作为代理）
    votes.append(_signal_valuation(advance_decline_ratio, regime_config))

    # 投票决策
    bull_count = sum(1 for v in votes if v.vote == "bull")
    bear_count = sum(1 for v in votes if v.vote == "bear")
    total_votes = len(votes)

    if bull_count >= 3:
        state = "bull"
        confidence = bull_count / total_votes
        position_advice = 0.7 + 0.3 * confidence
    elif bear_count >= 3:
        state = "bear"
        confidence = bear_count / total_votes
        position_advice = 0.3 - 0.3 * confidence
    else:
        state = "sideways"
        confidence = 1.0 - abs(bull_count - bear_count) / total_votes
        position_advice = 0.5

    # 描述
    descriptions = {"bull": "牛市", "bear": "熊市", "sideways": "震荡市"}
    description = f"{descriptions[state]} (置信度: {confidence:.0%})"

    # 选择权重
    from src.config import ScoreWeightConfig
    factor_weights = getattr(config, "factor_weights", None)
    if factor_weights:
        weights_map = {"bull": factor_weights.bull, "bear": factor_weights.bear, "sideways": factor_weights.sideways}
    else:
        weights_map = {"bull": None, "bear": None, "sideways": None}

    return MarketRegime(
        state=state,
        confidence=confidence,
        position_advice=position_advice,
        signals={v.signal_name: v.vote for v in votes},
        description=description,
        adjusted_weights=weights_map.get(state),
    )


def _signal_trend(index_kline: pd.DataFrame, config: object) -> RegimeVote:
    """趋势信号：MA均线排列。"""
    try:
        close_col = "收盘" if "收盘" in index_kline.columns else "close"
        if close_col not in index_kline.columns:
            return RegimeVote("trend", "neutral", 0.0, "无收盘价列")

        closes = index_kline[close_col].astype(float)
        if len(closes) < 60:
            return RegimeVote("trend", "neutral", 0.0, "数据不足")

        ma_short = getattr(config, "ma_short", 20)
        ma_long_cfg = getattr(config, "ma_long", 60)

        ma20 = closes.rolling(ma_short).mean().iloc[-1]
        ma60 = closes.rolling(ma_long_cfg).mean().iloc[-1]
        last_close = closes.iloc[-1]

        if last_close > ma20 > ma60:
            return RegimeVote("trend", "bull", 0.8, f"价格>{ma_short}日均线>{ma_long_cfg}日均线")
        elif last_close < ma20 < ma60:
            return RegimeVote("trend", "bear", 0.8, f"价格<{ma_short}日均线<{ma_long_cfg}日均线")
        else:
            return RegimeVote("trend", "neutral", 0.5, "均线纠缠")
    except Exception as e:
        return RegimeVote("trend", "neutral", 0.0, f"计算异常: {e}")


def _signal_volume(index_kline: pd.DataFrame, config: object) -> RegimeVote:
    """成交量信号：量能变化。"""
    try:
        vol_col = "成交量" if "成交量" in index_kline.columns else "volume"
        if vol_col not in index_kline.columns:
            return RegimeVote("volume", "neutral", 0.0, "无成交量列")

        volumes = index_kline[vol_col].astype(float)
        if len(volumes) < 20:
            return RegimeVote("volume", "neutral", 0.0, "数据不足")

        recent_vol = volumes.tail(5).mean()
        avg_vol = volumes.tail(20).mean()

        bull_ratio = getattr(config, "volume_bull_ratio", 1.2)
        bear_ratio = getattr(config, "volume_bear_ratio", 0.8)

        if recent_vol > avg_vol * bull_ratio:
            return RegimeVote("volume", "bull", 0.6, f"近5日量能放大 {recent_vol/avg_vol:.1f}倍")
        elif recent_vol < avg_vol * bear_ratio:
            return RegimeVote("volume", "bear", 0.6, f"近5日量能萎缩 {recent_vol/avg_vol:.1f}倍")
        else:
            return RegimeVote("volume", "neutral", 0.4, "量能平稳")
    except Exception as e:
        return RegimeVote("volume", "neutral", 0.0, f"计算异常: {e}")


def _signal_north_flow(north_flow: pd.DataFrame, config: object) -> RegimeVote:
    """北向资金信号。"""
    try:
        if north_flow.empty:
            return RegimeVote("north", "neutral", 0.0, "无北向数据")

        threshold = getattr(config, "north_flow_threshold", 100e8)
        net_col = None
        for col in ["当日成交净买额", "净流入"]:
            if col in north_flow.columns:
                net_col = col
                break

        if net_col is None:
            return RegimeVote("north", "neutral", 0.0, "无净流入列")

        recent_flow = north_flow[net_col].astype(float).tail(5).sum()
        if recent_flow > threshold:
            return RegimeVote("north", "bull", 0.7, f"近5日北向净流入 {recent_flow/1e8:.0f}亿")
        elif recent_flow < -threshold:
            return RegimeVote("north", "bear", 0.7, f"近5日北向净流出 {abs(recent_flow)/1e8:.0f}亿")
        else:
            return RegimeVote("north", "neutral", 0.4, "北向资金平稳")
    except Exception as e:
        return RegimeVote("north", "neutral", 0.0, f"计算异常: {e}")


def _signal_advance_decline(ratio: float, config: object) -> RegimeVote:
    """涨跌比信号。"""
    try:
        bull_threshold = getattr(config, "advance_decline_bull", 1.5)
        bear_threshold = getattr(config, "advance_decline_bear", 0.7)

        if ratio > bull_threshold:
            return RegimeVote("advance_decline", "bull", 0.6, f"涨跌比 {ratio:.1f} > {bull_threshold}")
        elif ratio < bear_threshold:
            return RegimeVote("advance_decline", "bear", 0.6, f"涨跌比 {ratio:.1f} < {bear_threshold}")
        else:
            return RegimeVote("advance_decline", "neutral", 0.4, f"涨跌比 {ratio:.1f} 平稳")
    except Exception as e:
        return RegimeVote("advance_decline", "neutral", 0.0, f"计算异常: {e}")


def _signal_valuation(ratio: float, config: object) -> RegimeVote:
    """估值信号（简化：使用涨跌比作为市场情绪代理）。"""
    try:
        pe_low = getattr(config, "pe_percentile_low", 0.4)
        pe_high = getattr(config, "pe_percentile_high", 0.7)

        # 简化处理：用涨跌比映射到 0~1 范围
        normalized = min(ratio / 3.0, 1.0)

        if normalized < pe_low:
            return RegimeVote("valuation", "bull", 0.5, f"市场情绪偏低 ({normalized:.2f})")
        elif normalized > pe_high:
            return RegimeVote("valuation", "bear", 0.5, f"市场情绪偏高 ({normalized:.2f})")
        else:
            return RegimeVote("valuation", "neutral", 0.4, f"市场情绪中性 ({normalized:.2f})")
    except Exception as e:
        return RegimeVote("valuation", "neutral", 0.0, f"计算异常: {e}")
