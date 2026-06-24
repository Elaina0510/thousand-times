"""动量因子测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def uptrend_kline() -> pd.DataFrame:
    """上涨趋势K线。"""
    n = 60
    prices = np.linspace(10, 20, n)
    return pd.DataFrame({
        "close": prices,
        "open": prices * 0.99,
        "high": prices * 1.01,
        "low": prices * 0.98,
        "volume": np.ones(n) * 1e6,
    })


@pytest.fixture
def downtrend_kline() -> pd.DataFrame:
    """下跌趋势K线。"""
    n = 60
    prices = np.linspace(20, 10, n)
    return pd.DataFrame({
        "close": prices,
        "open": prices * 1.01,
        "high": prices * 1.02,
        "low": prices * 0.99,
        "volume": np.ones(n) * 1e6,
    })


class TestShortMomentum:
    """短期动量测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.momentum import _calc_short_momentum
        assert _calc_short_momentum(pd.DataFrame()) == 50.0

    def test_uptrend_high_score(self, uptrend_kline):
        from src.factors.momentum import _calc_short_momentum
        score = _calc_short_momentum(uptrend_kline)
        assert score >= 60

    def test_downtrend_low_score(self, downtrend_kline):
        from src.factors.momentum import _calc_short_momentum
        score = _calc_short_momentum(downtrend_kline)
        assert score <= 40


class TestMidMomentum:
    """中期动量测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.momentum import _calc_mid_momentum
        assert _calc_mid_momentum(pd.DataFrame()) == 50.0

    def test_uptrend_high_score(self, uptrend_kline):
        from src.factors.momentum import _calc_mid_momentum
        score = _calc_mid_momentum(uptrend_kline)
        assert score >= 60

    def test_downtrend_low_score(self, downtrend_kline):
        from src.factors.momentum import _calc_mid_momentum
        score = _calc_mid_momentum(downtrend_kline)
        assert score <= 40


class TestRelativeStrength:
    """相对强弱测试。"""

    def test_no_benchmark(self, uptrend_kline):
        from src.factors.momentum import _calc_relative_strength
        score = _calc_relative_strength(uptrend_kline, None)
        assert score == 50.0

    def test_outperform(self, uptrend_kline):
        """个股强于基准应得高分。"""
        from src.factors.momentum import _calc_relative_strength
        # 基准下跌
        n = 60
        bench = pd.DataFrame({"close": np.linspace(10, 8, n)})
        score = _calc_relative_strength(uptrend_kline, bench)
        assert score >= 60


class TestCalcMomentumFactor:
    """综合动量因子测试。"""

    def test_returns_dict(self, uptrend_kline):
        from src.factors.momentum import calc_momentum_factor
        result = calc_momentum_factor(uptrend_kline)
        assert isinstance(result, dict)
        assert "short_momentum" in result
        assert "mid_momentum" in result
        assert "relative_strength" in result
        assert "score" in result

    def test_all_scores_in_range(self, uptrend_kline):
        from src.factors.momentum import calc_momentum_factor
        result = calc_momentum_factor(uptrend_kline)
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"

    def test_empty_returns_neutral(self):
        from src.factors.momentum import calc_momentum_factor
        result = calc_momentum_factor(pd.DataFrame())
        assert result["score"] == 50.0
