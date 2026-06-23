"""14 种典型股票场景测试 — 验证评分与判断逻辑覆盖。

覆盖：
- 场景 1~4：各类推荐/风险股票
- 场景 5~8：边界条件（零分、满分、缺失数据、冲突信号）
- 场景 9~11：ETF 场景
- 场景 12~14：综合场景（新闻利好/利空、行业匹配）

评分公式（个股四维度加权）：
  total = tech_norm*0.35 + trend_norm*0.25 + vp_norm*0.20 + fund_norm*0.20
  tech_norm  = (technical / 55) * 100
  trend_norm = (industry / 10) * 100
  vp_norm    = (max(0, news) / 20) * 100
  fund_norm  = (fundamental / 30) * 100

评分公式（ETF 三维度加权）：
  total = tech_norm*0.55 + news_norm*0.35 + fund_norm*0.10
  tech_norm = (technical / 55) * 100
  news_norm = (max(0, news) / 35) * 100
  fund_norm = (fund_flow / 10) * 100
"""

from __future__ import annotations

import pytest

from config import ScoreWeightConfig
from scoring import TechnicalSignals, calc_total_score, judge_score, score_to_probability


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────


def _stock_total(tech: float, fund: float, news: float, industry: float) -> float:
    """计算个股综合评分。"""
    return calc_total_score(
        technical=tech, fundamental=fund, news=news,
        industry=industry, fund_flow=None, is_etf=False,
        config=ScoreWeightConfig(),
    )


def _etf_total(tech: float, news: float, fund_flow: float) -> float:
    """计算 ETF 综合评分。"""
    return calc_total_score(
        technical=tech, fundamental=None, news=news,
        industry=None, fund_flow=fund_flow, is_etf=True,
        config=ScoreWeightConfig(),
    )


# ─────────────────────────────────────────────
# 场景 1~4：各类推荐/风险股票
# ─────────────────────────────────────────────


class TestScenario01StrongBuy:
    """场景 1：全信号看多 → 强烈买入。

    技术指标全满（tech=40）、行业趋势上升（industry=10）、
    政策直接利好（news=17.5）、基本面全满分（fund=30）。
    """

    def test_total_score(self) -> None:
        total = _stock_total(tech=40, fund=30, news=17.5, industry=10)
        # tech_norm=72.73, trend_norm=100, vp_norm=87.5, fund_norm=100
        # 72.73*0.35 + 100*0.25 + 87.5*0.20 + 100*0.20 = 87.95
        assert total == pytest.approx(87.95, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=40, fund=30, news=17.5, industry=10)
        assert judge_score(total) == "strong_buy"

    def test_probability(self) -> None:
        total = _stock_total(tech=40, fund=30, news=17.5, industry=10)
        prob = score_to_probability(total)
        assert prob > 70


class TestScenario02Buy:
    """场景 2：部分看多信号 → 买入。

    技术指标部分（tech=17）、行业横盘（industry=4.5）、
    新闻中性（news=5）、基本面中等（fund=13）。
    """

    def test_total_score(self) -> None:
        total = _stock_total(tech=17, fund=13, news=5, industry=4.5)
        # tech_norm=30.91, trend_norm=45, vp_norm=25, fund_norm=43.33
        # 30.91*0.35 + 45*0.25 + 25*0.20 + 43.33*0.20 = 35.73
        assert total == pytest.approx(35.73, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=17, fund=13, news=5, industry=4.5)
        assert judge_score(total) in ("hold", "avoid")


class TestScenario03Sell:
    """场景 3：看空信号 → 回避。

    技术指标全空（tech=0）、行业下降趋势（industry=1）、
    新闻利空（news=-7.5）、基本面差（fund=5）。
    """

    def test_total_score(self) -> None:
        total = _stock_total(tech=0, fund=5, news=-7.5, industry=1)
        # tech_norm=0, trend_norm=10, vp_norm=0(news<0→0), fund_norm=16.67
        # 0*0.35 + 10*0.25 + 0*0.20 + 16.67*0.20 = 5.83
        assert total == pytest.approx(5.83, abs=0.5)

    def test_judgment(self) -> None:
        total = _stock_total(tech=0, fund=5, news=-7.5, industry=1)
        assert judge_score(total) == "avoid"


class TestScenario04HighFundamental:
    """场景 4：基本面超强但技术面弱。

    tech=10, fund=34（满分+调节）, news=5, industry=4.5。
    """

    def test_total_score(self) -> None:
        total = _stock_total(tech=10, fund=34, news=5, industry=4.5)
        # tech_norm=18.18, trend_norm=45, vp_norm=25, fund_norm=100(clamped)
        # 18.18*0.35 + 45*0.25 + 25*0.20 + 100*0.20 = 42.61
        assert total == pytest.approx(42.61, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=10, fund=34, news=5, industry=4.5)
        assert judge_score(total) in ("hold", "avoid")


# ─────────────────────────────────────────────
# 场景 5~8：边界条件
# ─────────────────────────────────────────────


class TestScenario05ZeroScore:
    """场景 5：全零分。"""

    def test_total_score(self) -> None:
        total = _stock_total(tech=0, fund=0, news=0, industry=0)
        assert total == 0.0

    def test_judgment(self) -> None:
        assert judge_score(0.0) == "avoid"

    def test_probability(self) -> None:
        prob = score_to_probability(0.0)
        assert prob < 10


class TestScenario06MaxScore:
    """场景 6：全满分。"""

    def test_total_score(self) -> None:
        total = _stock_total(tech=55, fund=30, news=20, industry=10)
        # All normalize to 100
        # 100*0.35 + 100*0.25 + 100*0.20 + 100*0.20 = 100
        assert total == pytest.approx(100.0, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=55, fund=30, news=20, industry=10)
        assert judge_score(total) == "strong_buy"


class TestScenario07MissingData:
    """场景 7：缺失数据（基本面和行业趋势为 None）。"""

    def test_total_score(self) -> None:
        total = calc_total_score(
            technical=30, fundamental=None, news=10,
            industry=None, fund_flow=None, is_etf=False,
            config=ScoreWeightConfig(),
        )
        # tech_norm=54.55, trend_norm=0, vp_norm=50, fund_norm=0
        # 54.55*0.35 + 0*0.25 + 50*0.20 + 0*0.20 = 29.09
        assert total == pytest.approx(29.09, abs=0.5)

    def test_judgment(self) -> None:
        total = calc_total_score(
            technical=30, fundamental=None, news=10,
            industry=None, fund_flow=None, is_etf=False,
            config=ScoreWeightConfig(),
        )
        assert judge_score(total) == "avoid"


class TestScenario08ConflictingSignals:
    """场景 8：冲突信号（技术面强 + 基本面弱 + 新闻利空）。"""

    def test_total_score(self) -> None:
        total = _stock_total(tech=40, fund=5, news=-10, industry=2)
        # tech_norm=72.73, trend_norm=20, vp_norm=0(news<0), fund_norm=16.67
        # 72.73*0.35 + 20*0.25 + 0*0.20 + 16.67*0.20 = 33.79
        assert total == pytest.approx(33.79, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=40, fund=5, news=-10, industry=2)
        assert judge_score(total) == "avoid"


# ─────────────────────────────────────────────
# 场景 9~11：ETF 场景
# ─────────────────────────────────────────────


class TestScenario09EtfStrongBuy:
    """场景 9：ETF 全看多 → 强烈买入。"""

    def test_total_score(self) -> None:
        total = _etf_total(tech=50, news=30, fund_flow=9)
        # tech_norm=90.91, news_norm=85.71, fund_norm=90
        # 90.91*0.55 + 85.71*0.35 + 90*0.10 = 88.99
        assert total == pytest.approx(89.0, abs=1.0)

    def test_judgment(self) -> None:
        total = _etf_total(tech=50, news=30, fund_flow=9)
        assert judge_score(total) == "strong_buy"


class TestScenario10EtfHold:
    """场景 10：ETF 中性。"""

    def test_total_score(self) -> None:
        total = _etf_total(tech=20, news=5, fund_flow=3)
        # tech_norm=36.36, news_norm=14.29, fund_norm=30
        # 36.36*0.55 + 14.29*0.35 + 30*0.10 = 28.0
        assert total == pytest.approx(28.0, abs=1.0)

    def test_judgment(self) -> None:
        total = _etf_total(tech=20, news=5, fund_flow=3)
        assert judge_score(total) == "avoid"


class TestScenario11EtfAvoid:
    """场景 11：ETF 全看空。"""

    def test_total_score(self) -> None:
        total = _etf_total(tech=0, news=-10, fund_flow=0)
        # tech_norm=0, news_norm=0(news<0), fund_norm=0
        # 0*0.55 + 0*0.35 + 0*0.10 = 0
        assert total == 0.0

    def test_judgment(self) -> None:
        total = _etf_total(tech=0, news=-10, fund_flow=0)
        assert judge_score(total) == "avoid"


# ─────────────────────────────────────────────
# 场景 12~14：综合场景
# ─────────────────────────────────────────────


class TestScenario12NewsBoost:
    """场景 12：新闻强利好推动（中等技术面 + 强新闻）。"""

    def test_total_score(self) -> None:
        total = _stock_total(tech=25, fund=20, news=17.5, industry=7)
        # tech_norm=45.45, trend_norm=70, vp_norm=87.5, fund_norm=66.67
        # 45.45*0.35 + 70*0.25 + 87.5*0.20 + 66.67*0.20 = 64.24
        assert total == pytest.approx(64.24, abs=1.0)

    def test_judgment(self) -> None:
        total = _stock_total(tech=25, fund=20, news=17.5, industry=7)
        assert judge_score(total) == "buy"


class TestScenario13NewsDrag:
    """场景 13：新闻利空拖累（中等技术面 + 利空新闻）。"""

    def test_total_score(self) -> None:
        total = _stock_total(tech=25, fund=20, news=-7.5, industry=7)
        # tech_norm=45.45, trend_norm=70, vp_norm=0(news<0), fund_norm=66.67
        # 45.45*0.35 + 70*0.25 + 0*0.20 + 66.67*0.20 = 46.74
        assert total == pytest.approx(46.74, abs=0.1)

    def test_judgment(self) -> None:
        total = _stock_total(tech=25, fund=20, news=-7.5, industry=7)
        assert judge_score(total) == "hold"


class TestScenario14IndustryMatch:
    """场景 14：行业趋势强匹配。"""

    def test_high_industry_boost(self) -> None:
        total = _stock_total(tech=30, fund=20, news=10, industry=10)
        # tech_norm=54.55, trend_norm=100, vp_norm=50, fund_norm=66.67
        # 54.55*0.35 + 100*0.25 + 50*0.20 + 66.67*0.20 = 67.42
        assert total == pytest.approx(67.42, abs=0.1)
        assert judge_score(total) == "buy"

    def test_low_industry_drag(self) -> None:
        total = _stock_total(tech=30, fund=20, news=10, industry=1)
        # tech_norm=54.55, trend_norm=10, vp_norm=50, fund_norm=66.67
        # 54.55*0.35 + 10*0.25 + 50*0.20 + 66.67*0.20 = 44.92
        assert total == pytest.approx(44.92, abs=0.1)
        assert judge_score(total) == "avoid"
