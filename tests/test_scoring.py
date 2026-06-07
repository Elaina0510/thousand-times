"""scoring.py 单元测试。"""

from __future__ import annotations

import pytest

from config import ScoreWeightConfig, TechnicalWeightConfig
from scoring import (
    ScoreResult,
    TechnicalSignals,
    calc_technical_score,
    calc_total_score,
    get_industry_trend_score,
    judge_score,
    score_to_probability,
)


class TestCalcTotalScore:
    """综合评分计算测试。"""

    def test_stock_full_score(self) -> None:
        """个股满分场景。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=40.0,
            fundamental=30.0,
            news=20.0,
            industry=10.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        assert abs(result - 100.0) < 1e-6

    def test_stock_zero_score(self) -> None:
        """个股零分场景。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=0.0,
            fundamental=0.0,
            news=0.0,
            industry=0.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        assert abs(result - 0.0) < 1e-6

    def test_etf_full_score(self) -> None:
        """ETF满分场景。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=55.0,
            fundamental=None,
            news=35.0,
            industry=None,
            fund_flow=10.0,
            is_etf=True,
            config=config,
        )
        assert abs(result - 100.0) < 1e-6

    def test_etf_zero_score(self) -> None:
        """ETF零分场景。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=0.0,
            fundamental=None,
            news=0.0,
            industry=None,
            fund_flow=0.0,
            is_etf=True,
            config=config,
        )
        assert abs(result - 0.0) < 1e-6

    def test_score_clamped_to_zero(self) -> None:
        """负分截断到0。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=-10.0,
            fundamental=0.0,
            news=0.0,
            industry=0.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        assert result == 0.0

    def test_score_clamped_to_hundred(self) -> None:
        """超100截断到100。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=50.0,
            fundamental=40.0,
            news=30.0,
            industry=20.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        assert result == 100.0

    def test_stock_partial_score(self) -> None:
        """个股部分得分。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=30.0,
            fundamental=20.0,
            news=15.0,
            industry=8.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        # 各维度评分直接求和：30 + 20 + 15 + 8 = 73
        expected = 30.0 + 20.0 + 15.0 + 8.0
        assert abs(result - expected) < 1e-6

    def test_etf_no_fund_flow(self) -> None:
        """ETF无资金流向数据。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=55.0,
            fundamental=None,
            news=35.0,
            industry=None,
            fund_flow=None,
            is_etf=True,
            config=config,
        )
        # 各维度评分直接求和：55 + 35 = 90
        expected = 55.0 + 35.0
        assert abs(result - expected) < 1e-6


class TestScoreToProbability:
    """盈利概率转换测试。"""

    def test_score_50_gives_50_percent(self) -> None:
        prob = score_to_probability(50.0)
        assert abs(prob - 50.0) < 1.0

    def test_score_70_gives_high_probability(self) -> None:
        prob = score_to_probability(70.0)
        assert 85 <= prob <= 95

    def test_score_30_gives_low_probability(self) -> None:
        prob = score_to_probability(30.0)
        assert 5 <= prob <= 15

    def test_score_0_gives_near_zero(self) -> None:
        prob = score_to_probability(0.0)
        assert prob < 5

    def test_score_100_gives_near_hundred(self) -> None:
        prob = score_to_probability(100.0)
        assert prob > 95


class TestJudgeScore:
    """评分判定测试。"""

    def test_recommend(self) -> None:
        assert judge_score(70.0, 70.0, 30.0) == "recommend"
        assert judge_score(85.0, 70.0, 30.0) == "recommend"

    def test_watch(self) -> None:
        assert judge_score(50.0, 70.0, 30.0) == "watch"
        assert judge_score(69.0, 70.0, 30.0) == "watch"

    def test_bearish(self) -> None:
        assert judge_score(30.0, 70.0, 30.0) == "bearish"
        assert judge_score(49.0, 70.0, 30.0) == "bearish"

    def test_risk(self) -> None:
        assert judge_score(29.0, 70.0, 30.0) == "risk"
        assert judge_score(0.0, 70.0, 30.0) == "risk"


class TestCalcTechnicalScore:
    """技术指标评分测试。"""

    def test_all_positive_signals(self) -> None:
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
        signals = TechnicalSignals(
            ma5_10_death=True,
            macd_death=True,
            volume_peak=True,
            volume_down=True,
        )
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        expected = -(5 + 5 + 5 + 4)
        assert score == 0.0  # 负分截断到0

    def test_mixed_signals(self) -> None:
        signals = TechnicalSignals(
            ma5_10_golden=True,
            macd_death=True,
        )
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        expected = 5 - 5
        assert score == 0.0

    def test_no_signals(self) -> None:
        signals = TechnicalSignals()
        weights = TechnicalWeightConfig()
        score = calc_technical_score(signals, weights)
        assert score == 0.0


class TestGetIndustryTrendScore:
    """行业趋势评分测试。"""

    def test_matched_industry(self) -> None:
        from config import AppConfig, IndustryTrendWeightConfig

        config = AppConfig()
        score = get_industry_trend_score("半导体", config.etf_pool, config)
        assert score == config.industry_trend_weight.sideways

    def test_unmatched_industry(self) -> None:
        from config import AppConfig

        config = AppConfig()
        score = get_industry_trend_score("未知行业", config.etf_pool, config)
        assert score == config.industry_trend_weight.sideways
