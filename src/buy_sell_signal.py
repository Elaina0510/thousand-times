"""买卖信号模块 — 生成买卖信号、关键价位和信号区间判断。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from config import BuySellSignalConfig
from technical_analysis import KlineData

logger = logging.getLogger("thousand-times")


@dataclass
class KeyPrice:
    """关键价位。"""
    current_price: float       # 当前价
    support_price: float       # 支撑位
    resistance_price: float    # 压力位
    target_price: float        # 目标价
    stop_loss: float           # 止损价


@dataclass
class SectorComparison:
    """板块对比。"""
    sector_name: str           # 板块名称
    rank_in_sector: int        # 板块内排名
    total_in_sector: int       # 板块内总数
    percentile: float          # 百分位（超过多少比例）
    vs_etf_return: float       # 对比板块ETF的超额收益


@dataclass
class HistoricalAccuracy:
    """历史准确率。"""
    period_days: int           # 周期天数
    accuracy_rate: float       # 准确率
    avg_return: float          # 平均收益
    total_signals: int         # 信号总数


@dataclass
class BuySellSignal:
    """买卖信号。"""
    code: str
    name: str
    is_etf: bool
    signal_score: int          # 0-100分
    signal_zone: str           # "买入区" / "观望区" / "卖出区"
    signal_emoji: str          # 🟢 / 🟡 / 🔴
    # 各维度评分
    technical_score: float
    fund_flow_score: float
    fundamental_score: float | None
    news_score: float
    # 关键价位
    key_prices: KeyPrice
    # 板块对比
    sector_comparison: SectorComparison | None
    # 历史准确率
    historical_accuracy: list[HistoricalAccuracy]
    # 链接
    link: str


def calc_key_prices(kline: KlineData, ma_weight: float = 0.4) -> KeyPrice:
    """根据K线数据计算关键价位。

    支撑位 = MA20 权重 × MA20 + (1-权重) × 近20日最低价
    压力位 = MA20 权重 × MA20 + (1-权重) × 近20日最高价
    目标价 = 当前价 + 2 × (压力位 - 当前价)  （突破潜力）
    止损价 = 当前价 - 0.5 × (当前价 - 支撑位)  （较紧止损）

    Args:
        kline: K线数据。
        ma_weight: 均线在支撑/压力位中的权重（0~1）。

    Returns:
        KeyPrice 对象。
    """
    closes = np.array(kline.closes)
    highs = np.array(kline.highs)
    lows = np.array(kline.lows)
    ma20 = np.array(kline.ma20)

    current_price = float(closes[-1])

    # 近20日（或可用数据）的最高/最低价
    n = min(20, len(closes))
    recent_high = float(np.max(highs[-n:]))
    recent_low = float(np.min(lows[-n:]))
    current_ma20 = float(ma20[-1])

    # 支撑位：MA20 和近期低点的加权
    support_price = ma_weight * current_ma20 + (1 - ma_weight) * recent_low
    # 压力位：MA20 和近期高点的加权
    resistance_price = ma_weight * current_ma20 + (1 - ma_weight) * recent_high

    # 目标价：当前价 + 2 × (压力位 - 当前价)
    target_price = current_price + 2 * max(0, resistance_price - current_price)
    # 止损价：当前价 - 0.5 × (当前价 - 支撑位)
    stop_loss = current_price - 0.5 * max(0, current_price - support_price)

    # 确保价格合理性
    support_price = round(max(0.01, support_price), 2)
    resistance_price = round(max(current_price, resistance_price), 2)
    target_price = round(max(resistance_price, target_price), 2)
    stop_loss = round(max(0.01, min(current_price, stop_loss)), 2)

    return KeyPrice(
        current_price=round(current_price, 2),
        support_price=support_price,
        resistance_price=resistance_price,
        target_price=target_price,
        stop_loss=stop_loss,
    )


def determine_signal_zone(
    score: float,
    config: BuySellSignalConfig,
) -> tuple[str, str]:
    """根据综合评分判断信号区间。

    Args:
        score: 综合评分（0~100）。
        config: 买卖信号配置。

    Returns:
        (signal_zone, signal_emoji) 元组。
    """
    if score >= config.buy_threshold:
        return "买入区", "🟢"
    elif score >= config.sell_threshold:
        return "观望区", "🟡"
    else:
        return "卖出区", "🔴"


def generate_buy_sell_signal(
    code: str,
    name: str,
    is_etf: bool,
    total_score: float,
    technical_score: float,
    fund_flow_score: float | None,
    fundamental_score: float | None,
    news_score: float,
    kline: KlineData,
    config: BuySellSignalConfig,
    sector_comparison: SectorComparison | None = None,
) -> BuySellSignal:
    """生成完整的买卖信号。

    Args:
        code: 股票/ETF代码。
        name: 名称。
        is_etf: 是否为ETF。
        total_score: 综合评分（0~100）。
        technical_score: 技术指标评分。
        fund_flow_score: 资金流向评分（ETF为None）。
        fundamental_score: 基本面评分（ETF为None）。
        news_score: 政策新闻评分。
        kline: K线数据。
        config: 买卖信号配置。
        sector_comparison: 板块对比结果（可选）。

    Returns:
        BuySellSignal 对象。
    """
    # 信号评分 = 综合评分（已归一化到 0-100）
    signal_score = int(round(total_score))

    # 信号区间
    signal_zone, signal_emoji = determine_signal_zone(total_score, config)

    # 关键价位
    key_prices = calc_key_prices(kline, config.ma_weight)

    # 链接
    if is_etf:
        link = f"https://fund.eastmoney.com/{code}.html"
    else:
        link = f"https://stockpage.10jqka.com.cn/{code}/"

    return BuySellSignal(
        code=code,
        name=name,
        is_etf=is_etf,
        signal_score=signal_score,
        signal_zone=signal_zone,
        signal_emoji=signal_emoji,
        technical_score=technical_score,
        fund_flow_score=fund_flow_score if fund_flow_score is not None else 0.0,
        fundamental_score=fundamental_score,
        news_score=news_score,
        key_prices=key_prices,
        sector_comparison=sector_comparison,
        historical_accuracy=[],  # TODO: 历史准确率需要回测，后续实现
        link=link,
    )
