"""report_generator.py 单元测试。"""

from __future__ import annotations

import pytest

from report_generator import PolicyImpact, generate_report
from scoring import ScoreResult, TechnicalSignals


def _make_stock_result(
    code: str = "600519",
    name: str = "贵州茅台",
    total_score: float = 80.0,
    technical_signals: TechnicalSignals | None = None,
) -> ScoreResult:
    """创建测试用个股评分结果。"""
    return ScoreResult(
        code=code,
        name=name,
        is_etf=False,
        technical_score=30.0,
        fundamental_score=25.0,
        news_score=15.0,
        industry_score=10.0,
        fund_flow_score=None,
        total_score=total_score,
        profit_probability=75.0,
        judgment="recommend" if total_score >= 70 else "risk" if total_score < 30 else "watch",
        technical_signals=technical_signals or TechnicalSignals(),
        news_summary="消费刺激政策利好",
    )


def _make_etf_result(
    code: str = "512480",
    name: str = "半导体ETF",
    total_score: float = 78.0,
    fund_flow_score: float = 8.0,
) -> ScoreResult:
    """创建测试用ETF评分结果。"""
    return ScoreResult(
        code=code,
        name=name,
        is_etf=True,
        technical_score=45.0,
        fundamental_score=None,
        news_score=25.0,
        industry_score=None,
        fund_flow_score=fund_flow_score,
        total_score=total_score,
        profit_probability=70.0,
        judgment="recommend" if total_score >= 70 else "risk" if total_score < 30 else "watch",
        technical_signals=TechnicalSignals(),
        news_summary="芯片补贴政策持续加码",
    )


def _make_policy_impact(
    title: str = "央行宣布降准0.5个百分点",
    direction: str = "positive",
) -> PolicyImpact:
    """创建测试用政策影响。"""
    return PolicyImpact(
        news_title=title,
        affected_industries=["银行", "地产"],
        impact_direction=direction,
        impact_degree="direct",
        impact_score=17.5,
        summary="利好银行、地产板块",
    )


class TestGenerateReport:
    """报告生成测试。"""

    def test_with_recommend_and_risk(self) -> None:
        """有推荐+有风险的报告。"""
        stock_results = [
            _make_stock_result(total_score=80.0),
            _make_stock_result(code="000001", name="平安银行", total_score=25.0),
        ]
        etf_results = [
            _make_etf_result(total_score=78.0),
            _make_etf_result(code="512200", name="地产ETF", total_score=22.0),
        ]
        policy_impacts = [_make_policy_impact()]

        report = generate_report(stock_results, etf_results, policy_impacts, "2026-06-06")

        assert "🟢 买入区" in report
        assert "🔴 卖出区" in report
        assert "📰 今日政策要闻" in report
        assert "以上分析仅供参考" in report

    def test_only_recommend(self) -> None:
        """仅有推荐的报告。"""
        stock_results = [_make_stock_result(total_score=80.0)]
        etf_results = [_make_etf_result(total_score=78.0)]

        report = generate_report(stock_results, etf_results, [], "2026-06-06")

        assert "🟢 买入区" in report
        assert "🔴 卖出区" not in report

    def test_only_risk(self) -> None:
        """仅有风险的报告。"""
        stock_results = [_make_stock_result(total_score=20.0)]
        etf_results = [_make_etf_result(total_score=25.0)]

        report = generate_report(stock_results, etf_results, [], "2026-06-06")

        assert "🔴 卖出区" in report
        assert "🟢 买入区" not in report

    def test_no_recommend_no_risk(self) -> None:
        """无推荐无风险的报告。"""
        report = generate_report([], [], [], "2026-06-06")

        assert "今日无符合条件的推荐标的" in report
        assert "以上分析仅供参考" in report

    def test_empty_lists(self) -> None:
        """空列表不崩溃。"""
        report = generate_report([], [], [], "2026-06-06")
        assert isinstance(report, str)
        assert len(report) > 0

    def test_with_policy_impacts(self) -> None:
        """包含政策要闻。"""
        impacts = [
            _make_policy_impact("央行降准", "positive"),
            _make_policy_impact("加征关税", "negative"),
        ]
        report = generate_report([], [], impacts, "2026-06-06")

        assert "央行降准" in report
        assert "加征关税" in report

    def test_stock_technical_signals_shown(self) -> None:
        """技术信号正确显示。"""
        signals = TechnicalSignals(
            ma5_10_golden=True,
            macd_golden=True,
            volume_up=True,
        )
        result = _make_stock_result(total_score=80.0, technical_signals=signals)
        report = generate_report([result], [], [], "2026-06-06")

        assert "MA5/10金叉" in report
        assert "MACD金叉" in report
        assert "放量上涨" in report

    def test_etf_fund_flow_description(self) -> None:
        """ETF资金流向描述正确。"""
        result = _make_etf_result(total_score=78.0, fund_flow_score=9.0)
        report = generate_report([], [result], [], "2026-06-06")

        assert "份额持续增长" in report
