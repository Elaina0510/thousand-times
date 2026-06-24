"""信号生成模块 — 基于因子评分生成买卖信号.

使用5信号投票制：
1. 因子综合 — total_score vs 阈值
2. 技术面 — technical_score vs 阈值
3. 资金面 — capital_score vs 阈值
4. 动量 — momentum_score vs 阈值
5. 市场环境 — 牛熊市增强/削弱
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class SignalVote:
    """单个信号投票。"""

    source: str
    vote: str  # "buy", "sell", "neutral"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class KeyPrices:
    """关键价位。"""

    current_price: float = 0.0
    support: float = 0.0
    resistance: float = 0.0
    target: float = 0.0
    stop_loss: float = 0.0
    risk_reward_ratio: float = 0.0


@dataclass
class Signal:
    """最终交易信号。"""

    code: str = ""
    name: str = ""
    is_etf: bool = False
    action: str = "hold"  # "buy", "sell", "hold"
    confidence: float = 0.0
    key_prices: KeyPrices = field(default_factory=KeyPrices)
    votes: list[SignalVote] = field(default_factory=list)
    factor_scores: object = None  # FactorScores reference
    reason: str = ""


def _vote_factor(fs: object, config: object) -> SignalVote:
    """因子综合投票。"""
    signal_config = getattr(config, "signal", None)
    buy_th = getattr(signal_config, "factor_buy_threshold", 70.0) if signal_config else 70.0
    sell_th = getattr(signal_config, "factor_sell_threshold", 30.0) if signal_config else 30.0

    total = getattr(fs, "total", 50.0)
    if total >= buy_th:
        return SignalVote("factor", "buy", 0.8, f"综合因子 {total:.0f} >= {buy_th}")
    elif total <= sell_th:
        return SignalVote("factor", "sell", 0.8, f"综合因子 {total:.0f} <= {sell_th}")
    else:
        return SignalVote("factor", "neutral", 0.5, f"综合因子 {total:.0f}")


def _vote_technical(fs: object, config: object) -> SignalVote:
    """技术面投票。"""
    signal_config = getattr(config, "signal", None)
    buy_th = getattr(signal_config, "technical_buy_threshold", 75.0) if signal_config else 75.0
    sell_th = getattr(signal_config, "technical_sell_threshold", 25.0) if signal_config else 25.0

    tech = getattr(fs, "technical", 50.0)
    if tech >= buy_th:
        return SignalVote("technical", "buy", 0.7, f"技术因子 {tech:.0f} >= {buy_th}")
    elif tech <= sell_th:
        return SignalVote("technical", "sell", 0.7, f"技术因子 {tech:.0f} <= {sell_th}")
    else:
        return SignalVote("technical", "neutral", 0.4, f"技术因子 {tech:.0f}")


def _vote_capital(fs: object, config: object) -> SignalVote:
    """资金面投票。"""
    cap = getattr(fs, "capital", 50.0)
    if cap >= 70:
        return SignalVote("capital", "buy", 0.6, f"资金因子 {cap:.0f} >= 70")
    elif cap <= 30:
        return SignalVote("capital", "sell", 0.6, f"资金因子 {cap:.0f} <= 30")
    else:
        return SignalVote("capital", "neutral", 0.4, f"资金因子 {cap:.0f}")


def _vote_momentum(fs: object, config: object) -> SignalVote:
    """动量投票。"""
    mom = getattr(fs, "momentum", 50.0)
    if mom >= 70:
        return SignalVote("momentum", "buy", 0.6, f"动量因子 {mom:.0f} >= 70")
    elif mom <= 30:
        return SignalVote("momentum", "sell", 0.6, f"动量因子 {mom:.0f} <= 30")
    else:
        return SignalVote("momentum", "neutral", 0.4, f"动量因子 {mom:.0f}")


def _vote_regime(fs: object, regime_state: str, config: object) -> SignalVote:
    """市场环境投票.

    牛市且技术面向好 → 买入加分
    熊市且技术面向弱 → 卖出加分
    """
    tech = getattr(fs, "technical", 50.0)

    if regime_state == "bull" and tech >= 60:
        return SignalVote("regime", "buy", 0.5, f"牛市环境 + 技术因子 {tech:.0f}")
    elif regime_state == "bear" and tech <= 40:
        return SignalVote("regime", "sell", 0.5, f"熊市环境 + 技术因子 {tech:.0f}")
    else:
        env_map = {"bull": "牛市", "bear": "熊市", "sideways": "震荡"}
        return SignalVote("regime", "neutral", 0.3, f"{env_map.get(regime_state, '未知')}环境")


def calc_key_prices(kline: pd.DataFrame, config: object) -> KeyPrices:
    """计算关键价位.

    基于 MA20、近20日高低点、布林带和 ATR。

    Args:
        kline: K线数据 DataFrame。
        config: AppConfig 配置。

    Returns:
        KeyPrices 关键价位。
    """
    if kline.empty or len(kline) < 20:
        return KeyPrices()

    try:
        close_col = "收盘" if "收盘" in kline.columns else "close"
        high_col = "最高" if "最高" in kline.columns else "high"
        low_col = "最低" if "最低" in kline.columns else "low"

        closes = kline[close_col].astype(float)
        highs = kline[high_col].astype(float)
        lows = kline[low_col].astype(float)

        last_close = closes.iloc[-1]

        # MA20
        ma20 = closes.rolling(20).mean().iloc[-1]

        # 近20日高低点
        high_20 = highs.tail(20).max()
        low_20 = lows.tail(20).min()

        # 布林带
        std20 = closes.rolling(20).std().iloc[-1]
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20

        # ATR（14日）
        tr_list = []
        for i in range(-14, 0):
            h = highs.iloc[i]
            l = lows.iloc[i]
            prev_c = closes.iloc[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
        atr = np.mean(tr_list)

        # ATR 乘数
        signal_config = getattr(config, "signal", None)
        atr_target_mult = getattr(signal_config, "atr_target_multiplier", 2.0) if signal_config else 2.0
        atr_stop_mult = getattr(signal_config, "atr_stop_multiplier", 1.5) if signal_config else 1.5

        # 支撑位：MA20、近20日低点、布林带下轨取中位数
        support_candidates = [ma20, low_20, bb_lower]
        support = float(np.median(support_candidates))

        # 压力位：MA20、近20日高点、布林带上轨取中位数
        resistance_candidates = [ma20, high_20, bb_upper]
        resistance = float(np.median(resistance_candidates))

        # 目标价和止损价
        target = last_close + atr * atr_target_mult
        stop_loss = last_close - atr * atr_stop_mult

        # 盈亏比
        risk = last_close - stop_loss
        reward = target - last_close
        risk_reward_ratio = reward / risk if risk > 0 else 0.0

        return KeyPrices(
            current_price=round(last_close, 2),
            support=round(support, 2),
            resistance=round(resistance, 2),
            target=round(target, 2),
            stop_loss=round(stop_loss, 2),
            risk_reward_ratio=round(risk_reward_ratio, 2),
        )
    except Exception as e:
        logger.warning(f"关键价位计算异常: {e}")
        return KeyPrices()


def _decide_action(votes: list[SignalVote], config: object) -> tuple[str, float]:
    """根据投票决定行动.

    Args:
        votes: 投票列表。
        config: AppConfig 配置。

    Returns:
        (action, confidence) 元组。
    """
    signal_config = getattr(config, "signal", None)
    min_buy_votes = getattr(signal_config, "min_buy_votes", 3) if signal_config else 3
    min_sell_votes = getattr(signal_config, "min_sell_votes", 3) if signal_config else 3

    buy_votes = sum(1 for v in votes if v.vote == "buy")
    sell_votes = sum(1 for v in votes if v.vote == "sell")
    total = len(votes)

    if buy_votes >= min_buy_votes and sell_votes <= 1:
        return "buy", buy_votes / total
    elif sell_votes >= min_sell_votes and buy_votes <= 1:
        return "sell", sell_votes / total
    else:
        return "hold", 0.5


def generate_signals(
    factors: list,
    data: object,
    config: object,
    regime_state: str = "sideways",
) -> list[Signal]:
    """生成交易信号.

    Args:
        factors: FactorScores 列表。
        data: DataBundle。
        config: AppConfig。
        regime_state: 市场环境状态。

    Returns:
        Signal 列表。
    """
    kline_cache = getattr(data, "kline_cache", {})
    min_risk_reward = 2.0
    signal_config = getattr(config, "signal", None)
    if signal_config:
        min_risk_reward = getattr(signal_config, "min_risk_reward", 2.0)

    signals: list[Signal] = []

    for fs in factors:
        # 5 票投票
        votes: list[SignalVote] = [
            _vote_factor(fs, config),
            _vote_technical(fs, config),
            _vote_capital(fs, config),
            _vote_momentum(fs, config),
            _vote_regime(fs, regime_state, config),
        ]

        # 决策
        action, confidence = _decide_action(votes, config)

        # 计算关键价位
        kline = kline_cache.get(fs.code, pd.DataFrame())
        key_prices = calc_key_prices(kline, config)

        # 盈亏比过滤（仅对买入信号）
        if action == "buy" and key_prices.risk_reward_ratio < min_risk_reward:
            action = "hold"
            confidence = 0.5

        # 综合理由
        buy_votes = [v for v in votes if v.vote == "buy"]
        sell_votes = [v for v in votes if v.vote == "sell"]
        if action == "buy":
            reason = f"买入({len(buy_votes)}/5): " + ", ".join(v.source for v in buy_votes)
        elif action == "sell":
            reason = f"卖出({len(sell_votes)}/5): " + ", ".join(v.source for v in sell_votes)
        else:
            reason = f"观望(buy={len(buy_votes)}, sell={len(sell_votes)})"

        signals.append(Signal(
            code=fs.code,
            name=fs.name,
            action=action,
            confidence=confidence,
            key_prices=key_prices,
            votes=votes,
            factor_scores=fs,
            reason=reason,
        ))

    # 按置信度排序
    signals.sort(key=lambda s: s.confidence, reverse=True)

    return signals
