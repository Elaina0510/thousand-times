"""信号生成模块 — 基于因子评分生成买卖信号.

使用5信号投票制（V3 自适应版）：
1. 因子综合 — total_score vs 阈值（自适应市场环境）
2. 技术面 — technical_score vs 阈值（自适应市场环境）
3. 资金面 — capital_score vs 阈值
4. 动量 — momentum_score vs 阈值
5. 市场环境 — 牛熊市增强/削弱

V3 新增：AdaptiveThresholds 根据市场环境动态调整投票阈值，
解决 V2 固定阈值导致"全部观望"的问题。
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class AdaptiveThresholds:
    """市场环境自适应的信号阈值（V3 新增）."""

    # 投票数阈值
    min_buy_votes: int = 2
    min_sell_votes: int = 2
    max_oppose_votes: int = 1   # 允许的最大反对票

    # 分数阈值
    factor_buy: float = 70.0    # 综合因子买入阈值
    factor_sell: float = 30.0
    technical_buy: float = 75.0  # 技术因子买入阈值
    technical_sell: float = 25.0

    # 盈亏比要求
    min_risk_reward: float = 2.0

    @staticmethod
    def for_regime(state: str) -> AdaptiveThresholds:
        """根据市场环境返回对应阈值.

        Args:
            state: 市场环境状态 ("bull", "bear", "sideways").

        Returns:
            该环境下的自适应阈值.
        """
        if state == "bull":
            return AdaptiveThresholds(
                min_buy_votes=2,         # 牛市中2票即可买入（更积极）
                min_sell_votes=4,        # 牛市中卖出需4票（更谨慎做空）
                max_oppose_votes=2,
                factor_buy=65.0,         # 牛市中降低买入门槛
                factor_sell=25.0,
                technical_buy=65.0,
                technical_sell=20.0,
                min_risk_reward=1.5,
            )
        elif state == "bear":
            return AdaptiveThresholds(
                min_buy_votes=4,         # 熊市中买入需4票（更谨慎）
                min_sell_votes=2,        # 熊市中2票即可卖出（更积极止损）
                max_oppose_votes=1,
                factor_buy=80.0,         # 熊市中提高买入门槛
                factor_sell=35.0,
                technical_buy=80.0,
                technical_sell=30.0,
                min_risk_reward=2.5,     # 要求更高盈亏比
            )
        else:  # sideways
            return AdaptiveThresholds(
                min_buy_votes=2,
                min_sell_votes=2,
                max_oppose_votes=1,
                factor_buy=70.0,
                factor_sell=30.0,
                technical_buy=75.0,
                technical_sell=25.0,
                min_risk_reward=2.0,
            )


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


def _vote_factor(
    fs: object,
    config: object,
    thresholds: AdaptiveThresholds | None = None,
) -> SignalVote:
    """因子综合投票（V3：支持自适应阈值）.

    Args:
        fs: FactorScores 或 CalibratedScores.
        config: AppConfig.
        thresholds: 自适应阈值，None 时使用 config 中的固定阈值（V2 兼容）.
    """
    if thresholds is not None:
        buy_th = thresholds.factor_buy
        sell_th = thresholds.factor_sell
    else:
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


def _vote_technical(
    fs: object,
    config: object,
    thresholds: AdaptiveThresholds | None = None,
) -> SignalVote:
    """技术面投票（V3：支持自适应阈值）.

    Args:
        fs: FactorScores 或 CalibratedScores.
        config: AppConfig.
        thresholds: 自适应阈值，None 时使用 config 中的固定阈值（V2 兼容）.
    """
    if thresholds is not None:
        buy_th = thresholds.technical_buy
        sell_th = thresholds.technical_sell
    else:
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
            lo = lows.iloc[i]
            prev_c = closes.iloc[i - 1]
            tr = max(h - lo, abs(h - prev_c), abs(lo - prev_c))
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
    """根据投票决定行动（V2 固定阈值，已废弃）.

    已废弃: 请使用 _decide_action_adaptive。
    保留此函数用于 V1 回退兼容。

    Args:
        votes: 投票列表。
        config: AppConfig 配置。

    Returns:
        (action, confidence) 元组。
    """
    warnings.warn(
        "_decide_action is deprecated, use _decide_action_adaptive instead",
        DeprecationWarning,
        stacklevel=2,
    )
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


def _decide_action_adaptive(
    votes: list[SignalVote],
    thresholds: AdaptiveThresholds,
    risk_reward: float,
) -> tuple[str, float, str]:
    """自适应投票决策（替代现有的 _decide_action）.

    改造要点：
    1. 阈值不再硬编码，根据市场环境动态调整
    2. 增加 max_oppose_votes 约束（买入信号中不允许太多反对票）
    3. 盈亏比作为独立否决条件
    4. 返回详细理由而非简单的"观望"

    Args:
        votes: 5个SignalVote。
        thresholds: 当前市场环境的自适应阈值。
        risk_reward: 关键价位的盈亏比。

    Returns:
        (action: "buy"/"sell"/"hold",
         confidence: 0.0~1.0,
         detail: 决策理由)
    """
    buy_votes = sum(1 for v in votes if v.vote == "buy")
    sell_votes = sum(1 for v in votes if v.vote == "sell")
    neutral_votes = len(votes) - buy_votes - sell_votes

    # 买入决策
    if buy_votes >= thresholds.min_buy_votes and sell_votes <= thresholds.max_oppose_votes:
        if risk_reward < thresholds.min_risk_reward:
            return (
                "hold", 0.4,
                f"买入票数{buy_votes}满足但盈亏比{risk_reward:.1f}<{thresholds.min_risk_reward}",
            )
        confidence = buy_votes / len(votes)
        return ("buy", confidence, f"买入({buy_votes}/{len(votes)}票), 盈亏比{risk_reward:.1f}")

    # 卖出决策
    if sell_votes >= thresholds.min_sell_votes and buy_votes <= thresholds.max_oppose_votes:
        confidence = sell_votes / len(votes)
        return ("sell", confidence, f"卖出({sell_votes}/{len(votes)}票)")

    # 观望 — 提供更有信息量的理由
    if buy_votes == 2:
        return ("hold", 0.45, f"接近买入(buy={buy_votes}, sell={sell_votes})，等待确认")
    elif sell_votes == 2:
        return ("hold", 0.45, f"接近卖出(buy={buy_votes}, sell={sell_votes})，关注风险")
    else:
        return (
            "hold", 0.5,
            f"信号混合(buy={buy_votes}, sell={sell_votes}, neutral={neutral_votes})",
        )


def generate_signals(
    factors: list[object],
    data: object,
    config: object,
    regime_state: str = "sideways",
    use_adaptive: bool = True,
) -> list[Signal]:
    """生成交易信号（V3：默认使用自适应阈值）.

    Args:
        factors: FactorScores 或 CalibratedScores 列表。
        data: DataBundle。
        config: AppConfig。
        regime_state: 市场环境状态。
        use_adaptive: 是否使用自适应阈值（V3），False 回退到 V2 固定阈值。

    Returns:
        Signal 列表。
    """
    kline_cache = getattr(data, "kline_cache", {})

    # V3: 获取自适应阈值
    thresholds = None
    if use_adaptive:
        thresholds = AdaptiveThresholds.for_regime(regime_state)
        min_risk_reward = thresholds.min_risk_reward
    else:
        signal_config = getattr(config, "signal", None)
        min_risk_reward = getattr(signal_config, "min_risk_reward", 2.0) if signal_config else 2.0

    signals: list[Signal] = []

    for fs in factors:
        # 5 票投票（V3：使用自适应阈值）
        votes: list[SignalVote] = [
            _vote_factor(fs, config, thresholds),
            _vote_technical(fs, config, thresholds),
            _vote_capital(fs, config),
            _vote_momentum(fs, config),
            _vote_regime(fs, regime_state, config),
        ]

        # 决策（V3：使用自适应投票逻辑）
        code = str(getattr(fs, "code", ""))
        kline = kline_cache.get(code, pd.DataFrame())
        key_prices = calc_key_prices(kline, config)

        if use_adaptive and thresholds is not None:
            action, confidence, detail = _decide_action_adaptive(
                votes, thresholds, key_prices.risk_reward_ratio,
            )
        else:
            # V2 兼容模式
            action, confidence = _decide_action(votes, config)
            detail = ""
            # 盈亏比过滤（仅对买入信号）
            if action == "buy" and key_prices.risk_reward_ratio < min_risk_reward:
                action = "hold"
                confidence = 0.5

        # 综合理由
        if detail:
            reason = detail
        else:
            buy_votes = [v for v in votes if v.vote == "buy"]
            sell_votes = [v for v in votes if v.vote == "sell"]
            if action == "buy":
                reason = f"买入({len(buy_votes)}/5): " + ", ".join(v.source for v in buy_votes)
            elif action == "sell":
                reason = f"卖出({len(sell_votes)}/5): " + ", ".join(v.source for v in sell_votes)
            else:
                reason = f"观望(buy={len(buy_votes)}, sell={len(sell_votes)})"

        signals.append(Signal(
            code=str(getattr(fs, "code", "")),
            name=str(getattr(fs, "name", "")),
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
