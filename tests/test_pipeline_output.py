"""输出模块测试。"""

from __future__ import annotations

import pytest

from src.pipeline.output import (
    RegimeAlert,
    ScoreAlert,
    _is_trading_session,
    generate_report_md,
)


class MockRegime:
    def __init__(self):
        self.state = "bull"
        self.confidence = 0.8
        self.position_advice = 0.9
        self.description = "牛市 (置信度: 80%)"
        self.signals = {"trend": "bull", "volume": "bull", "north": "neutral"}


class MockSignal:
    def __init__(self, action="buy"):
        self.code = "000001"
        self.name = "测试股票"
        self.action = action
        self.confidence = 0.8
        self.reason = "buy_votes=4"
        self.votes = []
        self.key_prices = type("KP", (), {
            "current_price": 15.0, "support": 13.0, "resistance": 17.0,
            "target": 18.0, "stop_loss": 12.0, "risk_reward_ratio": 2.0,
        })()
        self.factor_scores = type("FS", (), {
            "total": 80, "technical": 75, "fundamental": 70,
            "capital": 65, "sentiment": 60, "momentum": 85,
            "technical_detail": {"ma_trend": 80, "macd": 70},
            "fundamental_detail": {"valuation": 65, "growth": 75},
        })()


class TestGenerateReportMd:
    """报告生成测试。"""

    def test_basic_report(self):
        signals = [MockSignal("buy"), MockSignal("sell")]
        regime = MockRegime()
        report = generate_report_md(signals, [], regime, None)
        assert "A股智能选股分析报告" in report
        assert "买入信号" in report
        assert "卖出信号" in report
        assert "市场环境" in report

    def test_no_signals(self):
        regime = MockRegime()
        report = generate_report_md([], [], regime, None)
        assert "买入信号: 无" in report
        assert "卖出信号: 无" in report

    def test_statistics_section(self):
        signals = [MockSignal("buy")]
        regime = MockRegime()
        report = generate_report_md(signals, [], regime, None)
        assert "因子分布统计" in report


class TestIsTradingSession:
    """交易时段判断测试。"""

    def test_returns_bool(self):
        result = _is_trading_session()
        assert isinstance(result, bool)


class TestAlertDataclasses:
    """提醒数据类测试。"""

    def test_score_alert(self):
        alert = ScoreAlert(code="000001", delta=30.0, score=None, message="test")
        assert alert.code == "000001"
        assert alert.delta == 30.0

    def test_regime_alert(self):
        alert = RegimeAlert(old_state="sideways", new_regime=None, message="test")
        assert alert.old_state == "sideways"
