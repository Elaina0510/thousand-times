"""buy_sell_signal.py 单元测试。"""

from __future__ import annotations

import pytest

from buy_sell_signal import (
    BuySellSignal,
    KeyPrice,
    calc_key_prices,
    determine_signal_zone,
    generate_buy_sell_signal,
)
from config import BuySellSignalConfig
from technical_analysis import KlineData


def _make_kline_data(
    closes: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    ma20: list[float] | None = None,
) -> KlineData:
    """创建测试用K线数据。"""
    n = len(closes) if closes else 20
    return KlineData(
        dates=[f"2026-01-{i+1:02d}" for i in range(n)],
        opens=closes if closes else [100.0] * n,
        highs=highs if highs else [105.0] * n,
        lows=lows if lows else [95.0] * n,
        closes=closes if closes else [100.0] * n,
        volumes=[1000000.0] * n,
        ma5=[100.0] * n,
        ma10=[100.0] * n,
        ma20=ma20 if ma20 else [100.0] * n,
        ma60=[100.0] * n,
        dif=[0.0] * n,
        dea=[0.0] * n,
        macd_hist=[0.0] * n,
    )


class TestCalcKeyPrices:
    """关键价位计算测试。"""

    def test_basic_calculation(self) -> None:
        """基本关键价位计算。"""
        kline = _make_kline_data(
            closes=[100.0] * 20,
            highs=[105.0] * 20,
            lows=[95.0] * 20,
            ma20=[100.0] * 20,
        )
        kp = calc_key_prices(kline, ma_weight=0.4)

        assert isinstance(kp, KeyPrice)
        assert kp.current_price == 100.0
        # 支撑位 = 0.4 * 100 + 0.6 * 95 = 40 + 57 = 97.0
        assert kp.support_price == 97.0
        # 压力位 = 0.4 * 100 + 0.6 * 105 = 40 + 63 = 103.0
        assert kp.resistance_price == 103.0
        # 目标价 = 100 + 2 * (103 - 100) = 106.0
        assert kp.target_price == 106.0
        # 止损价 = 100 - 0.5 * (100 - 97) = 98.5
        assert kp.stop_loss == 98.5

    def test_different_ma_weight(self) -> None:
        """不同均线权重。"""
        kline = _make_kline_data(
            closes=[100.0] * 20,
            highs=[110.0] * 20,
            lows=[90.0] * 20,
            ma20=[100.0] * 20,
        )
        kp = calc_key_prices(kline, ma_weight=0.6)

        # 支撑位 = 0.6 * 100 + 0.4 * 90 = 60 + 36 = 96.0
        assert kp.support_price == 96.0
        # 压力位 = 0.6 * 100 + 0.4 * 110 = 60 + 44 = 104.0
        assert kp.resistance_price == 104.0

    def test_price_above_ma20(self) -> None:
        """股价在MA20上方。"""
        kline = _make_kline_data(
            closes=[110.0] * 20,
            highs=[115.0] * 20,
            lows=[105.0] * 20,
            ma20=[100.0] * 20,
        )
        kp = calc_key_prices(kline, ma_weight=0.4)

        assert kp.current_price == 110.0
        assert kp.support_price > 0
        assert kp.resistance_price >= kp.current_price
        assert kp.target_price >= kp.resistance_price
        assert kp.stop_loss <= kp.current_price

    def test_minimum_price_bounds(self) -> None:
        """价格下限不为负。"""
        kline = _make_kline_data(
            closes=[1.0] * 20,
            highs=[1.5] * 20,
            lows=[0.5] * 20,
            ma20=[1.0] * 20,
        )
        kp = calc_key_prices(kline, ma_weight=0.4)

        assert kp.support_price > 0
        assert kp.stop_loss > 0
        assert kp.resistance_price >= kp.current_price

    def test_short_data(self) -> None:
        """数据不足20天时使用可用数据。"""
        kline = _make_kline_data(
            closes=[100.0] * 5,
            highs=[105.0] * 5,
            lows=[95.0] * 5,
            ma20=[100.0] * 5,
        )
        kp = calc_key_prices(kline, ma_weight=0.4)

        assert isinstance(kp, KeyPrice)
        assert kp.current_price == 100.0


class TestDetermineSignalZone:
    """信号区间判断测试。"""

    def test_buy_zone(self) -> None:
        """买入区（>=70）。"""
        config = BuySellSignalConfig()
        zone, emoji = determine_signal_zone(75.0, config)
        assert zone == "买入区"
        assert emoji == "🟢"

    def test_watch_zone(self) -> None:
        """观望区（30~69）。"""
        config = BuySellSignalConfig()
        zone, emoji = determine_signal_zone(50.0, config)
        assert zone == "观望区"
        assert emoji == "🟡"

    def test_sell_zone(self) -> None:
        """卖出区（<30）。"""
        config = BuySellSignalConfig()
        zone, emoji = determine_signal_zone(20.0, config)
        assert zone == "卖出区"
        assert emoji == "🔴"

    def test_boundary_buy(self) -> None:
        """买入区边界值。"""
        config = BuySellSignalConfig()
        zone, _ = determine_signal_zone(70.0, config)
        assert zone == "买入区"

    def test_boundary_sell(self) -> None:
        """卖出区边界值。"""
        config = BuySellSignalConfig()
        zone, _ = determine_signal_zone(30.0, config)
        assert zone == "观望区"

    def test_custom_thresholds(self) -> None:
        """自定义阈值。"""
        config = BuySellSignalConfig(buy_threshold=80.0, sell_threshold=40.0)
        zone, _ = determine_signal_zone(75.0, config)
        assert zone == "观望区"


class TestGenerateBuySellSignal:
    """买卖信号生成测试。"""

    def test_stock_signal(self) -> None:
        """个股买卖信号生成。"""
        kline = _make_kline_data(
            closes=[100.0] * 20,
            highs=[105.0] * 20,
            lows=[95.0] * 20,
            ma20=[100.0] * 20,
        )
        config = BuySellSignalConfig()

        signal = generate_buy_sell_signal(
            code="600519",
            name="贵州茅台",
            is_etf=False,
            total_score=75.0,
            technical_score=35.0,
            fund_flow_score=None,
            fundamental_score=25.0,
            news_score=15.0,
            kline=kline,
            config=config,
        )

        assert isinstance(signal, BuySellSignal)
        assert signal.code == "600519"
        assert signal.name == "贵州茅台"
        assert signal.is_etf is False
        assert signal.signal_score == 75
        assert signal.signal_zone == "买入区"
        assert signal.signal_emoji == "🟢"
        assert signal.technical_score == 35.0
        assert signal.fundamental_score == 25.0
        assert signal.news_score == 15.0
        assert isinstance(signal.key_prices, KeyPrice)
        assert "10jqka" in signal.link

    def test_etf_signal(self) -> None:
        """ETF买卖信号生成。"""
        kline = _make_kline_data(
            closes=[100.0] * 20,
            highs=[105.0] * 20,
            lows=[95.0] * 20,
            ma20=[100.0] * 20,
        )
        config = BuySellSignalConfig()

        signal = generate_buy_sell_signal(
            code="512480",
            name="半导体ETF",
            is_etf=True,
            total_score=60.0,
            technical_score=40.0,
            fund_flow_score=8.0,
            fundamental_score=None,
            news_score=12.0,
            kline=kline,
            config=config,
        )

        assert signal.code == "512480"
        assert signal.is_etf is True
        assert signal.signal_zone == "观望区"
        assert signal.fund_flow_score == 8.0
        assert signal.fundamental_score is None
        assert "eastmoney" in signal.link

    def test_sell_zone_signal(self) -> None:
        """卖出区信号。"""
        kline = _make_kline_data(
            closes=[100.0] * 20,
            highs=[105.0] * 20,
            lows=[95.0] * 20,
            ma20=[100.0] * 20,
        )
        config = BuySellSignalConfig()

        signal = generate_buy_sell_signal(
            code="000001",
            name="平安银行",
            is_etf=False,
            total_score=20.0,
            technical_score=5.0,
            fund_flow_score=None,
            fundamental_score=10.0,
            news_score=5.0,
            kline=kline,
            config=config,
        )

        assert signal.signal_zone == "卖出区"
        assert signal.signal_emoji == "🔴"
