"""信号生成模块 — 基于因子评分生成买卖信号。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

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

    support: float = 0.0
    resistance: float = 0.0
    target: float = 0.0
    stop_loss: float = 0.0


@dataclass
class Signal:
    """最终交易信号。"""

    code: str = ""
    name: str = ""
    action: str = "hold"  # "buy", "sell", "hold"
    confidence: float = 0.0
    key_prices: KeyPrices = field(default_factory=KeyPrices)
    votes: list[SignalVote] = field(default_factory=list)
    reason: str = ""


def generate_signals(factors: list, data: object, config: object) -> list[Signal]:
    """生成交易信号.

    Args:
        factors: FactorScores 列表。
        data: DataBundle。
        config: AppConfig。

    Returns:
        Signal 列表。
    """
    signal_config = getattr(config, "signal", None)
    buy_threshold = getattr(signal_config, "factor_buy_threshold", 70.0) if signal_config else 70.0
    sell_threshold = getattr(signal_config, "factor_sell_threshold", 30.0) if signal_config else 30.0
    min_buy_votes = getattr(signal_config, "min_buy_votes", 3) if signal_config else 3

    signals: list[Signal] = []

    for fs in factors:
        votes: list[SignalVote] = []

        # 因子评分投票
        if fs.total >= buy_threshold:
            votes.append(SignalVote("factor", "buy", 0.8, f"综合因子 {fs.total:.0f} >= {buy_threshold}"))
        elif fs.total <= sell_threshold:
            votes.append(SignalVote("factor", "sell", 0.8, f"综合因子 {fs.total:.0f} <= {sell_threshold}"))
        else:
            votes.append(SignalVote("factor", "neutral", 0.5, f"综合因子 {fs.total:.0f}"))

        # 技术面投票
        if fs.technical >= 75:
            votes.append(SignalVote("technical", "buy", 0.7, f"技术因子 {fs.technical:.0f}"))
        elif fs.technical <= 25:
            votes.append(SignalVote("technical", "sell", 0.7, f"技术因子 {fs.technical:.0f}"))
        else:
            votes.append(SignalVote("technical", "neutral", 0.4, f"技术因子 {fs.technical:.0f}"))

        # 动量投票
        if fs.momentum >= 70:
            votes.append(SignalVote("momentum", "buy", 0.6, f"动量因子 {fs.momentum:.0f}"))
        elif fs.momentum <= 30:
            votes.append(SignalVote("momentum", "sell", 0.6, f"动量因子 {fs.momentum:.0f}"))
        else:
            votes.append(SignalVote("momentum", "neutral", 0.4, f"动量因子 {fs.momentum:.0f}"))

        # 统计投票
        buy_votes = sum(1 for v in votes if v.vote == "buy")
        sell_votes = sum(1 for v in votes if v.vote == "sell")

        if buy_votes >= min_buy_votes:
            action = "buy"
            confidence = buy_votes / len(votes)
        elif sell_votes >= min_buy_votes:
            action = "sell"
            confidence = sell_votes / len(votes)
        else:
            action = "hold"
            confidence = 0.5

        signals.append(Signal(
            code=fs.code, name=fs.name,
            action=action, confidence=confidence,
            votes=votes,
            reason=f"buy_votes={buy_votes}, sell_votes={sell_votes}",
        ))

    return signals
