"""technical_analysis.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from technical_analysis import KlineData, calc_technical_signals, get_kline_data
from config import TechnicalWeightConfig
from scoring import TechnicalSignals, calc_technical_score


def _make_kline_data(
    closes: list[float] | None = None,
    volumes: list[float] | None = None,
    ma5: list[float] | None = None,
    ma10: list[float] | None = None,
    ma20: list[float] | None = None,
    ma60: list[float] | None = None,
    dif: list[float] | None = None,
    dea: list[float] | None = None,
    macd_hist: list[float] | None = None,
) -> KlineData:
    """创建测试用K线数据。"""
    n = len(closes) if closes else 20
    return KlineData(
        dates=[f"2026-01-{i+1:02d}" for i in range(n)],
        opens=closes if closes else [100.0] * n,
        highs=closes if closes else [105.0] * n,
        lows=closes if closes else [95.0] * n,
        closes=closes if closes else [100.0] * n,
        volumes=volumes if volumes else [1000000.0] * n,
        ma5=ma5 if ma5 else [100.0] * n,
        ma10=ma10 if ma10 else [100.0] * n,
        ma20=ma20 if ma20 else [100.0] * n,
        ma60=ma60 if ma60 else [100.0] * n,
        dif=dif if dif else [0.0] * n,
        dea=dea if dea else [0.0] * n,
        macd_hist=macd_hist if macd_hist else [0.0] * n,
    )


def _make_stock_hist() -> pd.DataFrame:
    """创建测试用股票历史数据。"""
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    np.random.seed(42)
    closes = 100 + np.cumsum(np.random.randn(60) * 2)
    return pd.DataFrame(
        {
            "日期": dates,
            "开盘": closes + np.random.randn(60) * 0.5,
            "最高": closes + np.abs(np.random.randn(60) * 2),
            "最低": closes - np.abs(np.random.randn(60) * 2),
            "收盘": closes,
            "成交量": np.random.randint(500000, 2000000, 60),
        }
    )


class TestCalcTechnicalSignals:
    """技术信号计算测试。"""

    def test_empty_data(self) -> None:
        """空数据返回默认信号。"""
        kline = _make_kline_data(closes=[100.0])
        signals = calc_technical_signals(kline)
        assert isinstance(signals, TechnicalSignals)

    def test_ma5_10_golden_cross(self) -> None:
        """MA5/10金叉检测。"""
        # MA5 从下向上穿越 MA10
        ma5 = [95.0, 96.0, 97.0, 98.0, 102.0, 103.0, 104.0]
        ma10 = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        closes = [100.0] * 7
        kline = _make_kline_data(closes=closes, ma5=ma5, ma10=ma10)
        signals = calc_technical_signals(kline)
        assert signals.ma5_10_golden is True

    def test_ma5_10_death_cross(self) -> None:
        """MA5/10死叉检测。"""
        # MA5 从上向下穿越 MA10
        ma5 = [105.0, 104.0, 103.0, 102.0, 98.0, 97.0, 96.0]
        ma10 = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        closes = [100.0] * 7
        kline = _make_kline_data(closes=closes, ma5=ma5, ma10=ma10)
        signals = calc_technical_signals(kline)
        assert signals.ma5_10_death is True

    def test_bullish_alignment(self) -> None:
        """多头排列检测。"""
        ma5 = [105.0] * 7
        ma10 = [103.0] * 7
        ma20 = [101.0] * 7
        ma60 = [99.0] * 7
        closes = [100.0] * 7
        kline = _make_kline_data(
            closes=closes, ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60
        )
        signals = calc_technical_signals(kline)
        assert signals.bullish_alignment is True

    def test_above_ma20(self) -> None:
        """股价站上MA20检测。"""
        closes = [105.0] * 7
        ma20 = [100.0] * 7
        kline = _make_kline_data(closes=closes, ma20=ma20)
        signals = calc_technical_signals(kline)
        assert signals.above_ma20 is True

    def test_macd_golden_cross(self) -> None:
        """MACD金叉检测。"""
        # DIF 从下向上穿越 DEA（在最后3个元素内发生）
        dif = [-1.0, -0.5, 0.0, 0.5, -0.2, 0.3, 1.0]
        dea = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        closes = [100.0] * 7
        kline = _make_kline_data(closes=closes, dif=dif, dea=dea)
        signals = calc_technical_signals(kline)
        assert signals.macd_golden is True

    def test_macd_above_zero(self) -> None:
        """零轴上方金叉检测。"""
        # DIF 从下向上穿越 DEA，且都在零轴上方（在最后3个元素内发生）
        dif = [0.5, 0.8, 1.0, 0.8, 0.7, 1.2, 1.5]
        dea = [0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 1.0]
        closes = [100.0] * 7
        kline = _make_kline_data(closes=closes, dif=dif, dea=dea)
        signals = calc_technical_signals(kline)
        assert signals.macd_golden is True

    def test_volume_up(self) -> None:
        """放量上涨检测。"""
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 105.0]
        volumes = [1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 2000000.0]
        kline = _make_kline_data(closes=closes, volumes=volumes)
        signals = calc_technical_signals(kline)
        assert signals.volume_up is True

    def test_volume_down(self) -> None:
        """放量下跌检测。"""
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 95.0]
        volumes = [1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 3000000.0]
        kline = _make_kline_data(closes=closes, volumes=volumes)
        signals = calc_technical_signals(kline)
        assert signals.volume_down is True


class TestGetKlineData:
    """K线数据获取测试。"""

    @patch("technical_analysis._fetch_stock_hist")
    def test_normal_stock(self, mock_hist: MagicMock) -> None:
        """正常获取个股K线数据。"""
        mock_hist.return_value = _make_stock_hist()

        result = get_kline_data("600519", days=60, is_etf=False)

        assert isinstance(result, KlineData)
        assert len(result.closes) > 0
        assert len(result.ma5) > 0
        assert len(result.dif) > 0

    @patch("technical_analysis._fetch_etf_hist")
    def test_normal_etf(self, mock_hist: MagicMock) -> None:
        """正常获取ETF K线数据。"""
        mock_hist.return_value = _make_stock_hist()

        result = get_kline_data("512480", days=60, is_etf=True)

        assert isinstance(result, KlineData)
        assert len(result.closes) > 0

    @patch("technical_analysis._fetch_stock_hist")
    def test_api_failure(self, mock_hist: MagicMock) -> None:
        """AKShare失败时抛出异常。"""
        mock_hist.side_effect = Exception("API 超时")

        with pytest.raises(Exception, match="API 超时"):
            get_kline_data("600519", days=60, is_etf=False)


class TestCalcTechnicalScore:
    """技术指标评分测试。"""

    def test_all_positive_signals(self) -> None:
        """所有加分信号。"""
        signals = TechnicalSignals(
            ma5_10_golden=True,
            ma20_60_golden=True,
            bullish_alignment=True,
            above_ma20=True,
            macd_golden=True,
            macd_above_zero=True,
            macd_divergence=True,
            volume_up=True,
            pullback_ok=True,
        )
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        expected = 5 + 5 + 5 + 3 + 5 + 5 + 5 + 4 + 3
        assert score == expected

    def test_all_negative_signals(self) -> None:
        """所有扣分信号（负分截断到0）。"""
        signals = TechnicalSignals(
            ma5_10_death=True,
            macd_death=True,
            volume_peak=True,
            volume_down=True,
        )
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        assert score == 0.0

    def test_mixed_signals(self) -> None:
        """混合信号。"""
        signals = TechnicalSignals(
            ma5_10_golden=True,
            macd_death=True,
        )
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        assert score == 0.0

    def test_no_signals(self) -> None:
        """无信号。"""
        signals = TechnicalSignals()
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        assert score == 0.0
