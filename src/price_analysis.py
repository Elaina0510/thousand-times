"""关键价位计算模块 — 计算支撑位、压力位、目标价和止损价。"""

from __future__ import annotations

import logging

from buy_sell_signal import KeyPrice
from config import BuySellSignalConfig
from technical_analysis import KlineData

logger = logging.getLogger("thousand-times")


def calculate_key_prices(
    code: str,
    kline: KlineData,
    config: BuySellSignalConfig,
) -> KeyPrice | None:
    """计算关键价位。

    综合技术面计算：
    1. 支撑位：MA20、近期低点的加权平均
    2. 压力位：MA60、近期高点的加权平均
    3. 目标价：突破压力位后5%
    4. 止损价：支撑位下方5%

    Args:
        code: 股票代码。
        kline: K线数据对象。
        config: 买卖信号配置。

    Returns:
        KeyPrice 对象，如果数据不足则返回 None。
    """
    try:
        if len(kline.closes) < 20:
            logger.warning(f"{code}: K线数据不足20天，跳过关键价位计算")
            return None

        current_price = kline.closes[-1]

        # 技术面支撑位（取多个支撑的加权平均）
        # MA20 作为均线支撑
        ma20_support = kline.ma20[-1] if kline.ma20 and len(kline.ma20) > 0 else min(kline.lows[-20:])
        # 近期低点
        recent_low = min(kline.lows[-20:])
        # 加权平均
        support_price = ma20_support * config.ma_weight + recent_low * (1 - config.ma_weight)

        # 技术面压力位
        # MA60 作为均线压力
        ma60_resistance = kline.ma60[-1] if kline.ma60 and len(kline.ma60) > 0 else max(kline.highs[-20:])
        # 近期高点
        recent_high = max(kline.highs[-20:])
        # 加权平均
        resistance_price = ma60_resistance * config.ma_weight + recent_high * (1 - config.ma_weight)

        # 确保支撑位 < 当前价 < 压力位
        if support_price >= current_price:
            support_price = current_price * 0.95
        if resistance_price <= current_price:
            resistance_price = current_price * 1.05

        # 目标价（突破压力位后5%）
        target_price = resistance_price * 1.05

        # 止损价（支撑位下方5%）
        stop_loss = support_price * 0.95

        return KeyPrice(
            current_price=round(current_price, 2),
            support_price=round(support_price, 2),
            resistance_price=round(resistance_price, 2),
            target_price=round(target_price, 2),
            stop_loss=round(stop_loss, 2),
        )
    except Exception as e:
        logger.error(f"{code}: 关键价位计算失败: {e}")
        return None
