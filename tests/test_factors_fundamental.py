"""基本面因子测试。"""

from __future__ import annotations

import pytest


class TestValuationScore:
    """估值得分测试。"""

    def test_low_pe_high_score(self):
        from src.factors.fundamental import _calc_valuation_score
        assert _calc_valuation_score(8) >= 70

    def test_high_pe_low_score(self):
        from src.factors.fundamental import _calc_valuation_score
        assert _calc_valuation_score(100) <= 20

    def test_negative_pe(self):
        from src.factors.fundamental import _calc_valuation_score
        assert _calc_valuation_score(-5) == 30.0

    def test_mid_pe(self):
        from src.factors.fundamental import _calc_valuation_score
        score = _calc_valuation_score(25)
        assert 40 <= score <= 60


class TestProfitabilityScore:
    """盈利能力得分测试。"""

    def test_high_roe_positive_eps(self):
        from src.factors.fundamental import _calc_profitability_score
        score = _calc_profitability_score(25, 2.0)
        assert score >= 80

    def test_low_roe(self):
        from src.factors.fundamental import _calc_profitability_score
        score = _calc_profitability_score(3, 0.1)
        assert score < 60

    def test_negative_roe(self):
        from src.factors.fundamental import _calc_profitability_score
        score = _calc_profitability_score(-5, -0.5)
        assert score <= 40


class TestGrowthScore:
    """成长性得分测试。"""

    def test_high_growth(self):
        from src.factors.fundamental import _calc_growth_score
        score = _calc_growth_score(60, 30)
        assert score >= 70  # 50 + 20 (>50 growth) + 5 (>20 revenue) = 75

    def test_negative_growth(self):
        from src.factors.fundamental import _calc_growth_score
        score = _calc_growth_score(-40, -10)
        assert score <= 30

    def test_moderate_growth(self):
        from src.factors.fundamental import _calc_growth_score
        score = _calc_growth_score(15, 10)
        assert 50 <= score <= 80


class TestCalcFundamentalFactor:
    """综合基本面因子测试。"""

    def test_returns_dict(self):
        from src.factors.fundamental import calc_fundamental_factor
        result = calc_fundamental_factor(roe=15, eps=1.0, profit_growth=20, pe_ttm=15)
        assert isinstance(result, dict)
        assert "valuation" in result
        assert "profitability" in result
        assert "growth" in result
        assert "score" in result

    def test_all_scores_in_range(self):
        from src.factors.fundamental import calc_fundamental_factor
        result = calc_fundamental_factor(roe=15, eps=1.0, profit_growth=20, pe_ttm=15)
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"

    def test_defaults(self):
        from src.factors.fundamental import calc_fundamental_factor
        result = calc_fundamental_factor()
        assert result["score"] > 0
