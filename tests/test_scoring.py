"""scoring.py 单元测试。"""

from __future__ import annotations

import pytest

from config import ScoreWeightConfig, TechnicalWeightConfig
from scoring import (
    ScoreCalculator,
    ScoreResult,
    TechnicalSignals,
    calc_technical_score,
    calc_total_score,
    get_industry_trend_score,
    judge_score,
    score_to_probability,
)


class TestScoreCalculator:
    """ScoreCalculator 类测试。"""

    def test_normalize_score_zero(self) -> None:
        """零分归一化为0。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert calc.normalize_score(0.0, 55.0) == 0.0

    def test_normalize_score_full(self) -> None:
        """满分归一化为100。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert calc.normalize_score(55.0, 55.0) == 100.0

    def test_normalize_score_partial(self) -> None:
        """部分分归一化正确。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert abs(calc.normalize_score(27.5, 55.0) - 50.0) < 1e-6

    def test_normalize_score_clamp_above(self) -> None:
        """超过满分截断到100。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert calc.normalize_score(60.0, 55.0) == 100.0

    def test_normalize_score_clamp_below(self) -> None:
        """负分截断到0。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert calc.normalize_score(-10.0, 55.0) == 0.0

    def test_normalize_score_zero_max(self) -> None:
        """满分为0时返回0。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        assert calc.normalize_score(10.0, 0.0) == 0.0

    def test_classify_strong_buy(self) -> None:
        """≥75 为强烈买入。"""
        assert ScoreCalculator.classify(75.0) == "strong_buy"
        assert ScoreCalculator.classify(90.0) == "strong_buy"
        assert ScoreCalculator.classify(100.0) == "strong_buy"

    def test_classify_buy(self) -> None:
        """60~74 为买入。"""
        assert ScoreCalculator.classify(60.0) == "buy"
        assert ScoreCalculator.classify(70.0) == "buy"
        assert ScoreCalculator.classify(74.9) == "buy"

    def test_classify_hold(self) -> None:
        """45~59 为持有。"""
        assert ScoreCalculator.classify(45.0) == "hold"
        assert ScoreCalculator.classify(50.0) == "hold"
        assert ScoreCalculator.classify(59.9) == "hold"

    def test_classify_avoid(self) -> None:
        """<45 为回避。"""
        assert ScoreCalculator.classify(44.9) == "avoid"
        assert ScoreCalculator.classify(30.0) == "avoid"
        assert ScoreCalculator.classify(0.0) == "avoid"

    def test_calc_total_score_stock_full(self) -> None:
        """个股满分场景（各维度均满分）。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=55.0,
            fundamental=30.0,
            news=20.0,
            industry=10.0,
            fund_flow=None,
            is_etf=False,
        )
        assert abs(result - 100.0) < 1e-6

    def test_calc_total_score_stock_zero(self) -> None:
        """个股零分场景。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=0.0,
            fundamental=0.0,
            news=0.0,
            industry=0.0,
            fund_flow=None,
            is_etf=False,
        )
        assert abs(result - 0.0) < 1e-6

    def test_calc_total_score_etf_full(self) -> None:
        """ETF满分场景。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=55.0,
            fundamental=None,
            news=35.0,
            industry=None,
            fund_flow=10.0,
            is_etf=True,
        )
        assert abs(result - 100.0) < 1e-6

    def test_calc_total_score_etf_zero(self) -> None:
        """ETF零分场景。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=0.0,
            fundamental=None,
            news=0.0,
            industry=None,
            fund_flow=0.0,
            is_etf=True,
        )
        assert abs(result - 0.0) < 1e-6

    def test_calc_total_score_stock_weighted(self) -> None:
        """个股加权评分正确。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=30.0,
            fundamental=20.0,
            news=15.0,
            industry=8.0,
            fund_flow=None,
            is_etf=False,
        )
        # 技术: (30/55)*100*0.35 = 19.09
        # 趋势: (8/10)*100*0.25 = 20.00
        # 量价: (15/20)*100*0.20 = 15.00
        # 基本面: (20/30)*100*0.20 = 13.33
        expected = (30 / 55) * 100 * 0.35 + (8 / 10) * 100 * 0.25 + (15 / 20) * 100 * 0.20 + (20 / 30) * 100 * 0.20
        assert abs(result - round(expected, 2)) < 1e-6

    def test_calc_total_score_etf_weighted(self) -> None:
        """ETF加权评分正确。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=55.0,
            fundamental=None,
            news=35.0,
            industry=None,
            fund_flow=None,
            is_etf=True,
        )
        # 技术: (55/55)*100*0.55 = 55.0
        # 新闻: (35/35)*100*0.35 = 35.0
        # 资金流向: 0 (None)
        expected = 55.0 + 35.0 + 0.0
        assert abs(result - expected) < 1e-6

    def test_calc_total_score_negative_news(self) -> None:
        """负新闻评分为0（不减分）。"""
        calc = ScoreCalculator(ScoreWeightConfig())
        result = calc.calc_total_score(
            technical=30.0,
            fundamental=15.0,
            news=-10.0,
            industry=5.0,
            fund_flow=None,
            is_etf=False,
        )
        # 负新闻 max(0, -10) = 0，量价维度为0
        tech_norm = (30 / 55) * 100
        fund_norm = (15 / 30) * 100
        trend_norm = (5 / 10) * 100
        vp_norm = 0.0  # 负新闻
        expected = tech_norm * 0.35 + trend_norm * 0.25 + vp_norm * 0.20 + fund_norm * 0.20
        assert abs(result - round(expected, 2)) < 1e-6


class TestCalcTotalScore:
    """综合评分计算测试（兼容旧接口）。"""

    def test_stock_full_score(self) -> None:
        """个股满分场景。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=55.0,
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
        """负技术分截断到0。"""
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
        """超满分截断到100。"""
        config = ScoreWeightConfig()
        result = calc_total_score(
            technical=60.0,
            fundamental=40.0,
            news=30.0,
            industry=20.0,
            fund_flow=None,
            is_etf=False,
            config=config,
        )
        assert result == 100.0

    def test_stock_partial_score(self) -> None:
        """个股部分得分（加权计算）。"""
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
        expected = (30 / 55) * 100 * 0.35 + (8 / 10) * 100 * 0.25 + (15 / 20) * 100 * 0.20 + (20 / 30) * 100 * 0.20
        assert abs(result - round(expected, 2)) < 1e-6

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
        expected = 55.0 + 35.0 + 0.0
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
    """评分判定测试（四档分类）。"""

    def test_strong_buy(self) -> None:
        assert judge_score(75.0) == "strong_buy"
        assert judge_score(85.0) == "strong_buy"
        assert judge_score(100.0) == "strong_buy"

    def test_buy(self) -> None:
        assert judge_score(60.0) == "buy"
        assert judge_score(70.0) == "buy"
        assert judge_score(74.9) == "buy"

    def test_hold(self) -> None:
        assert judge_score(45.0) == "hold"
        assert judge_score(50.0) == "hold"
        assert judge_score(59.9) == "hold"

    def test_avoid(self) -> None:
        assert judge_score(44.9) == "avoid"
        assert judge_score(30.0) == "avoid"
        assert judge_score(0.0) == "avoid"

    def test_custom_thresholds(self) -> None:
        """自定义阈值。"""
        assert judge_score(80.0, high_threshold=80.0, low_threshold=50.0) == "strong_buy"
        assert judge_score(60.0, high_threshold=80.0, low_threshold=50.0) == "buy"
        assert judge_score(50.0, high_threshold=80.0, low_threshold=50.0) == "hold"
        assert judge_score(40.0, high_threshold=80.0, low_threshold=50.0) == "avoid"


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
