"""市场环境判断模块 — 基于中证全指判断当前市场状态。

使用中证全指（000985）作为基准，通过均线排列和波动率判断市场环境：
- 牛市（bull）：价格在MA20上方，MA20>MA60，波动率适中
- 熊市（bear）：价格在MA20下方，MA20<MA60，波动率偏高
- 震荡（sideways）：信号混合

根据市场环境动态调整评分权重：
- 牛市：技术面权重上调（趋势有效），基本面下调
- 熊市：基本面上调（防御性），技术面下调（趋势失效）
- 震荡：使用默认权重
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from config import AppConfig, ScoreWeightConfig

logger = logging.getLogger("thousand-times")

# 中证全指代码
CSI_FULL_INDEX_CODE = "000985"


@dataclass
class MarketRegime:
    """市场环境判断结果。"""

    state: str  # "bull" / "bear" / "sideways"
    confidence: float  # 判断置信度 0~1
    description: str  # 人类可读描述
    adjusted_weights: ScoreWeightConfig  # 调整后的权重


def _fetch_index_kline(code: str = CSI_FULL_INDEX_CODE, days: int = 120) -> dict | None:
    """获取指数K线数据。

    Args:
        code: 指数代码。
        days: 回溯天数。

    Returns:
        包含 closes, ma20, ma60 的字典，失败返回 None。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]
        df = ak.stock_zh_index_daily(symbol=f"sh{code}")
        if df.empty:
            logger.warning(f"AKShare 获取指数 {code} 数据为空")
            return None

        df = df.tail(days).reset_index(drop=True)
        closes = df["close"].astype(float).values

        ma20 = np.convolve(closes, np.ones(20) / 20, mode="valid")
        ma60 = np.convolve(closes, np.ones(60) / 60, mode="valid") if len(closes) >= 60 else np.array([])

        return {
            "closes": closes,
            "ma20": ma20,
            "ma60": ma60,
        }

    except Exception as e:
        logger.warning(f"获取指数 {code} 数据失败: {e}")
        return None


def _calc_volatility_regime(closes: np.ndarray, window: int = 20) -> float:
    """计算近期波动率（年化标准差）。

    Args:
        closes: 收盘价序列。
        window: 计算窗口。

    Returns:
        年化波动率百分比。
    """
    if len(closes) < window + 1:
        return 20.0  # 默认中等波动率

    returns = np.diff(np.log(closes[-window - 1:]))
    daily_vol = np.std(returns)
    annual_vol = daily_vol * np.sqrt(252) * 100
    return annual_vol


def judge_market_regime(config: AppConfig) -> MarketRegime:
    """判断当前市场环境。

    基于中证全指的均线排列和波动率综合判断。

    Args:
        config: 应用配置。

    Returns:
        MarketRegime 对象。
    """
    data = _fetch_index_kline()

    if data is None or len(data["closes"]) < 20:
        logger.warning("指数数据不足，默认震荡市")
        return MarketRegime(
            state="sideways",
            confidence=0.3,
            description="数据不足，默认震荡市",
            adjusted_weights=config.score_weight,
        )

    closes = data["closes"]
    ma20 = data["ma20"]
    ma60 = data["ma60"]

    current_price = closes[-1]
    current_ma20 = ma20[-1] if len(ma20) > 0 else current_price
    current_ma60 = ma60[-1] if len(ma60) > 0 else current_price

    # 均线排列判断
    above_ma20 = current_price > current_ma20
    ma20_above_ma60 = current_ma20 > current_ma60 if len(ma60) > 0 else True

    # 波动率
    vol = _calc_volatility_regime(closes)

    # 综合判断
    bull_signals = sum([above_ma20, ma20_above_ma60])
    bear_signals = sum([not above_ma20, not ma20_above_ma60])

    # 高波动倾向于熊市判断
    if vol > 30:
        bear_signals += 1
    elif vol < 15:
        bull_signals += 1

    total_signals = 2 + 1  # 均线2个 + 波动率1个

    if bull_signals >= 2:
        state = "bull"
        confidence = bull_signals / total_signals
        description = f"牛市（价格{'>' if above_ma20 else '<'}MA20，MA20{'>' if ma20_above_ma60 else '<'}MA60，波动率{vol:.1f}%）"
    elif bear_signals >= 2:
        state = "bear"
        confidence = bear_signals / total_signals
        description = f"熊市（价格{'<' if not above_ma20 else '>'}MA20，MA20{'<' if not ma20_above_ma60 else '>'}MA60，波动率{vol:.1f}%）"
    else:
        state = "sideways"
        confidence = 0.5
        description = f"震荡市（信号混合，波动率{vol:.1f}%）"

    # 根据市场状态调整权重
    adjusted = _adjust_weights(state, config.score_weight)

    logger.info(f"市场环境判断: {description} (置信度: {confidence:.0%})")

    return MarketRegime(
        state=state,
        confidence=confidence,
        description=description,
        adjusted_weights=adjusted,
    )


def _adjust_weights(state: str, base: ScoreWeightConfig) -> ScoreWeightConfig:
    """根据市场状态动态调整评分权重。

    调整逻辑：
    - 牛市：技术面+5%，基本面-5%（趋势跟踪有效）
    - 熊市：基本面+5%，技术面-5%（防御为主）
    - 震荡：保持默认

    Args:
        state: 市场状态（"bull"/"bear"/"sideways"）。
        base: 基础权重配置。

    Returns:
        调整后的权重配置。
    """
    if state == "bull":
        # 牛市：技术面权重上调，基本面下调
        return ScoreWeightConfig(
            stock_technical=min(0.40, base.stock_technical + 0.05),
            stock_trend=base.stock_trend,
            stock_volume_price=base.stock_volume_price,
            stock_fundamental=max(0.15, base.stock_fundamental - 0.05),
            stock_news=base.stock_news,
            stock_industry=base.stock_industry,
            etf_technical=min(0.60, base.etf_technical + 0.05),
            etf_news=max(0.30, base.etf_news - 0.05),
            etf_fund_flow=base.etf_fund_flow,
        )
    elif state == "bear":
        # 熊市：基本面上调，技术面下调
        return ScoreWeightConfig(
            stock_technical=max(0.30, base.stock_technical - 0.05),
            stock_trend=base.stock_trend,
            stock_volume_price=base.stock_volume_price,
            stock_fundamental=min(0.25, base.stock_fundamental + 0.05),
            stock_news=base.stock_news,
            stock_industry=base.stock_industry,
            etf_technical=max(0.50, base.etf_technical - 0.05),
            etf_news=min(0.40, base.etf_news + 0.05),
            etf_fund_flow=base.etf_fund_flow,
        )
    else:
        # 震荡：保持默认
        return ScoreWeightConfig(
            stock_technical=base.stock_technical,
            stock_trend=base.stock_trend,
            stock_volume_price=base.stock_volume_price,
            stock_fundamental=base.stock_fundamental,
            stock_news=base.stock_news,
            stock_industry=base.stock_industry,
            etf_technical=base.etf_technical,
            etf_news=base.etf_news,
            etf_fund_flow=base.etf_fund_flow,
        )
