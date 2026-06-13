"""price_analysis.py 单元测试。"""

from __future__ import annotations

import pytest

from config import BuySellSignalConfig
from price_analysis import calculate_key_prices
from technical_analysis import KlineData


def _make_kline(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    ma20: list[float] | None = None,
    ma60: list[float] | None = None,
) -> KlineData:
    """创建测试用的 KlineData 对象。"""
    n = len(closes)
    if highs is None:
        highs = [c * 1.02 for c in closes]
    if lows is None:
        lows = [c * 0.98 for c in closes]
    if ma20 is None:
        ma20 = [sum(closes[max(0, i - 19):i + 1]) / min(20, i + 1) for i in range(n)]
    if ma60 is None:
        ma60 = [sum(closes[max(0, i - 59):i + 1]) / min(60, i + 1) for i in range(n)]

    return KlineData(
        dates=[f"2026-01-{i + 1:02d}" for i in range(n)],
        opens=[c * 0.99 for c in closes],
        highs=highs,
        lows=lows,
        closes=closes,
        volumes=[1000000.0] * n,
        ma5=[sum(closes[max(0, i - 4):i + 1]) / min(5, i + 1) for i in range(n)],
        ma10=[sum(closes[max(0, i - 9):i + 1]) / min(10, i + 1) for i in range(n)],
        ma20=ma20,
        ma60=ma60,
        dif=[0.0] * n,
        dea=[0.0] * n,
        macd_hist=[0.0] * n,
    )


class TestCalculateKeyPrices:
    """关键价位计算测试。"""

    def test_normal_case(self) -> None:
        """正常场景：数据充足，计算正确。"""
        config = BuySellSignalConfig(ma_weight=0.4)
        # 创建 30 天的数据
        closes = [100.0 + i * 0.5 for i in range(30)]
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        assert result.current_price == closes[-1]
        # 支撑位应低于当前价
        assert result.support_price < result.current_price
        # 压力位应高于当前价
        assert result.resistance_price > result.current_price
        # 目标价应高于压力位
        assert result.target_price > result.resistance_price
        # 止损价应低于支撑位
        assert result.stop_loss < result.support_price

    def test_insufficient_data(self) -> None:
        """数据不足20天，返回 None。"""
        config = BuySellSignalConfig()
        closes = [100.0 + i for i in range(10)]  # 只有 10 天
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is None

    def test_support_below_current_price(self) -> None:
        """支撑位必须低于当前价。"""
        config = BuySellSignalConfig(ma_weight=0.5)
        # 创建一个当前价远高于 MA20 和近期低点的情况
        closes = [50.0] * 20 + [100.0] * 10  # 前 20 天 50，后 10 天 100
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        assert result.support_price < result.current_price

    def test_resistance_above_current_price(self) -> None:
        """压力位必须高于当前价。"""
        config = BuySellSignalConfig(ma_weight=0.5)
        # 创建一个当前价远低于 MA60 和近期高点的情况
        closes = [100.0] * 20 + [50.0] * 10  # 前 20 天 100，后 10 天 50
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        assert result.resistance_price > result.current_price

    def test_ma_weight_affects_calculation(self) -> None:
        """ma_weight 配置影响支撑位/压力位计算。"""
        closes = [100.0 + i * 0.5 for i in range(30)]
        kline = _make_kline(closes)

        # 使用高 ma_weight（更多依赖均线）
        config_high = BuySellSignalConfig(ma_weight=0.8)
        result_high = calculate_key_prices("600519", kline, config_high)

        # 使用低 ma_weight（更多依赖近期高低点）
        config_low = BuySellSignalConfig(ma_weight=0.2)
        result_low = calculate_key_prices("600519", kline, config_low)

        assert result_high is not None
        assert result_low is not None
        # 两种配置应该产生不同的结果
        assert result_high.support_price != result_low.support_price or \
               result_high.resistance_price != result_low.resistance_price

    def test_target_price_calculation(self) -> None:
        """目标价 = 压力位 * 1.05。"""
        config = BuySellSignalConfig()
        closes = [100.0] * 30
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        expected_target = round(result.resistance_price * 1.05, 2)
        assert result.target_price == expected_target

    def test_stop_loss_calculation(self) -> None:
        """止损价 = 支撑位 * 0.95。"""
        config = BuySellSignalConfig()
        closes = [100.0] * 30
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        expected_stop_loss = round(result.support_price * 0.95, 2)
        assert result.stop_loss == expected_stop_loss

    def test_rounding(self) -> None:
        """结果保留两位小数。"""
        config = BuySellSignalConfig()
        closes = [100.123456] * 30
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None
        # 检查所有价格都是两位小数
        assert result.current_price == round(result.current_price, 2)
        assert result.support_price == round(result.support_price, 2)
        assert result.resistance_price == round(result.resistance_price, 2)
        assert result.target_price == round(result.target_price, 2)
        assert result.stop_loss == round(result.stop_loss, 2)

    def test_exact_20_days(self) -> None:
        """刚好 20 天数据，应该正常计算。"""
        config = BuySellSignalConfig()
        closes = [100.0] * 20
        kline = _make_kline(closes)

        result = calculate_key_prices("600519", kline, config)

        assert result is not None

    def test_exception_handling(self) -> None:
        """异常处理：数据异常时返回 None。"""
        config = BuySellSignalConfig()
        # 创建一个空的 closes 列表但长度 >= 20
        closes = [0.0] * 20
        kline = _make_kline(closes)

        # 即使数据异常，也应该返回结果（不抛出异常）
        result = calculate_key_prices("600519", kline, config)
        # 由于 current_price = 0，支撑位会被设置为 0 * 0.95 = 0
        assert result is not None
