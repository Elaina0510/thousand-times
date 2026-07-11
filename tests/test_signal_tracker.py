"""SignalTracker 单元测试."""

from __future__ import annotations

import pytest

from feedback.tracker import (
    AggregatePerformance,
    SignalPerformance,
    compute_aggregate_performance,
    compute_pnl,
    generate_performance_report,
    recommend_thresholds,
    record_signals_v3,
)


class MockSignal:
    def __init__(self, code="000001", name="test", action="buy", confidence=0.8):
        self.code = code
        self.name = name
        self.action = action
        self.confidence = confidence
        self.key_prices = MockKeyPrices()


class MockKeyPrices:
    current_price = 10.0


def test_record_signals_v3():
    """记录信号."""
    signals = [MockSignal(code="000001", action="buy")]
    count = record_signals_v3(signals, "2026-07-11")
    assert count >= 1


def test_record_signals_v3_empty():
    """空信号列表."""
    count = record_signals_v3([], "2026-07-11")
    assert count == 0


def test_compute_pnl_empty():
    """新数据库无历史数据."""
    results = compute_pnl("2099-01-01")
    assert results == []


def test_compute_aggregate_empty():
    """空数据汇总."""
    perf = compute_aggregate_performance("2099-01-01", "2099-12-31")
    assert perf.total_signals == 0


def test_recommend_thresholds():
    """阈值推荐."""
    perf = AggregatePerformance(win_rate_5d=60.0)
    rec = recommend_thresholds(perf)
    assert "buy_threshold" in rec
    assert rec["buy_threshold"] > 0


def test_generate_performance_report():
    """报告生成."""
    perf = AggregatePerformance(
        period="2026-07",
        total_signals=100,
        buy_signals=30,
        sell_signals=10,
        win_rate_5d=55.0,
    )
    report = generate_performance_report(perf)
    assert "信号表现回顾" in report
    assert "55.0" in report
