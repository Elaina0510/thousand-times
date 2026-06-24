"""技术面因子测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_kline() -> pd.DataFrame:
    """生成模拟K线数据（100天）。"""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    base = 10.0
    # 模拟上涨趋势
    returns = np.random.normal(0.002, 0.02, n)
    prices = base * np.cumprod(1 + returns)

    return pd.DataFrame({
        "date": dates,
        "open": prices * (1 + np.random.uniform(-0.01, 0.01, n)),
        "high": prices * (1 + np.random.uniform(0, 0.03, n)),
        "low": prices * (1 - np.random.uniform(0, 0.03, n)),
        "close": prices,
        "volume": np.random.randint(1000000, 5000000, n).astype(float),
    })


@pytest.fixture
def short_kline() -> pd.DataFrame:
    """数据不足的K线。"""
    return pd.DataFrame({
        "close": [10.0, 10.5, 11.0],
        "volume": [1000000, 1200000, 1100000],
    })


class TestMaTrendScore:
    """MA趋势得分测试。"""

    def test_returns_50_for_empty(self):
        from src.factors.technical import calc_ma_trend_score
        assert calc_ma_trend_score(pd.DataFrame()) == 50.0

    def test_returns_50_for_short_data(self, short_kline):
        from src.factors.technical import calc_ma_trend_score
        assert calc_ma_trend_score(short_kline) == 50.0

    def test_normal_kline(self, sample_kline):
        from src.factors.technical import calc_ma_trend_score
        score = calc_ma_trend_score(sample_kline)
        assert 0 <= score <= 100

    def test_bullish_trend_scores_high(self):
        """多头排列应得高分。"""
        from src.factors.technical import calc_ma_trend_score
        # 构造强上涨趋势
        n = 80
        prices = np.linspace(10, 20, n)
        kline = pd.DataFrame({
            "close": prices,
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "volume": np.ones(n) * 1e6,
        })
        score = calc_ma_trend_score(kline)
        assert score >= 70

    def test_bearish_trend_scores_low(self):
        """空头排列应得低分。"""
        from src.factors.technical import calc_ma_trend_score
        n = 80
        prices = np.linspace(20, 10, n)
        kline = pd.DataFrame({
            "close": prices,
            "open": prices * 1.01,
            "high": prices * 1.02,
            "low": prices * 0.99,
            "volume": np.ones(n) * 1e6,
        })
        score = calc_ma_trend_score(kline)
        assert score <= 30


class TestMacdScore:
    """MACD得分测试。"""

    def test_returns_50_for_empty(self):
        from src.factors.technical import calc_macd_score
        assert calc_macd_score(pd.DataFrame()) == 50.0

    def test_returns_50_for_short_data(self, short_kline):
        from src.factors.technical import calc_macd_score
        assert calc_macd_score(short_kline) == 50.0

    def test_normal_kline(self, sample_kline):
        from src.factors.technical import calc_macd_score
        score = calc_macd_score(sample_kline)
        assert 0 <= score <= 100


class TestVolumeScore:
    """成交量得分测试。"""

    def test_returns_50_for_empty(self):
        from src.factors.technical import calc_volume_score
        assert calc_volume_score(pd.DataFrame()) == 50.0

    def test_normal_kline(self, sample_kline):
        from src.factors.technical import calc_volume_score
        score = calc_volume_score(sample_kline)
        assert 0 <= score <= 100


class TestBollingerScore:
    """布林带得分测试。"""

    def test_returns_50_for_empty(self):
        from src.factors.technical import calc_bollinger_score
        assert calc_bollinger_score(pd.DataFrame()) == 50.0

    def test_normal_kline(self, sample_kline):
        from src.factors.technical import calc_bollinger_score
        score = calc_bollinger_score(sample_kline)
        assert 0 <= score <= 100


class TestCalcTechnicalFactor:
    """综合技术因子测试。"""

    def test_returns_dict(self, sample_kline):
        from src.factors.technical import calc_technical_factor
        result = calc_technical_factor(sample_kline)
        assert isinstance(result, dict)
        assert "ma_trend" in result
        assert "macd" in result
        assert "volume" in result
        assert "bollinger" in result
        assert "score" in result

    def test_all_scores_in_range(self, sample_kline):
        from src.factors.technical import calc_technical_factor
        result = calc_technical_factor(sample_kline)
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"

    def test_empty_returns_neutral(self):
        from src.factors.technical import calc_technical_factor
        result = calc_technical_factor(pd.DataFrame())
        assert result["score"] == 50.0
