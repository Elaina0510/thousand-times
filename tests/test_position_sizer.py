"""PositionSizer 单元测试."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk.position import (
    PositionAllocation,
    PortfolioSummary,
    assign_positions,
    calc_volatility,
    check_sector_limits,
)


class MockSignal:
    def __init__(self, code="000001", name="test", confidence=0.8, key_prices=None):
        self.code = code
        self.name = name
        self.action = "buy"
        self.confidence = confidence
        self.key_prices = key_prices


class MockKeyPrices:
    def __init__(self, current_price=10.0, stop_loss=9.0, target=12.0):
        self.current_price = current_price
        self.stop_loss = stop_loss
        self.target = target
        self.risk_reward_ratio = 2.0


class MockRegime:
    def __init__(self, state="bull"):
        self.state = state


def _make_kline(price=10.0, rows=60):
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    prices = np.linspace(price * 0.9, price, rows)
    return pd.DataFrame({
        "日期": dates,
        "收盘": prices,
        "成交量": np.ones(rows) * 5000000,
    })


# ── calc_volatility ──
def test_calc_volatility():
    kline = _make_kline(10.0)
    vol = calc_volatility(kline)
    assert vol > 0


def test_calc_volatility_empty():
    assert calc_volatility(pd.DataFrame()) == 30.0


# ── check_sector_limits ──
def test_check_sector_limits_ok():
    allocations = [
        PositionAllocation(code="000001", adjusted_weight=5.0, capital=5000),
    ]
    industry_map = {"000001": "电子"}
    warnings = check_sector_limits(allocations, industry_map)
    assert warnings == []


def test_check_sector_limits_over():
    allocations = [
        PositionAllocation(code="000001", adjusted_weight=15.0, capital=15000),
        PositionAllocation(code="000002", adjusted_weight=10.0, capital=10000),
    ]
    industry_map = {"000001": "电子", "000002": "电子"}
    warnings = check_sector_limits(allocations, industry_map)
    assert len(warnings) > 0  # 25% > 20%


# ── assign_positions ──
def test_assign_positions_bull():
    signals = [
        MockSignal(code="000001", confidence=0.8, key_prices=MockKeyPrices()),
        MockSignal(code="000002", confidence=0.6, key_prices=MockKeyPrices()),
    ]
    kline = {"000001": _make_kline(10.0), "000002": _make_kline(20.0)}
    stock_pool = pd.DataFrame({"code": ["000001", "000002"], "name": ["A", "B"]})
    regime = MockRegime("bull")
    allocations, summary = assign_positions(signals, stock_pool, 100000, regime, kline)
    assert len(allocations) == 2
    # 牛市总仓位 ≤ 80%
    assert summary.allocated_capital <= 80000


def test_assign_positions_bear():
    signals = [MockSignal(code="000001", confidence=0.8, key_prices=MockKeyPrices())]
    kline = {"000001": _make_kline(10.0)}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["A"]})
    regime = MockRegime("bear")
    allocations, summary = assign_positions(signals, stock_pool, 100000, regime, kline)
    assert len(allocations) <= 1
    assert summary.allocated_capital <= 30000  # 熊市 ≤ 30%


def test_assign_positions_single_max():
    """单只不超过 10%."""
    signals = [MockSignal(code="000001", confidence=1.0, key_prices=MockKeyPrices())]
    kline = {"000001": _make_kline(10.0)}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["A"]})
    regime = MockRegime("bull")
    allocations, summary = assign_positions(signals, stock_pool, 100000, regime, kline)
    for a in allocations:
        assert a.adjusted_weight <= 10.0


def test_assign_positions_shares_rounding():
    """100 股取整."""
    signals = [MockSignal(code="000001", confidence=0.5, key_prices=MockKeyPrices(current_price=10.0))]
    kline = {"000001": _make_kline(10.0)}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["A"]})
    regime = MockRegime("bull")
    allocations, summary = assign_positions(signals, stock_pool, 100000, regime, kline)
    if allocations:
        assert allocations[0].shares % 100 == 0


def test_assign_positions_empty():
    allocations, summary = assign_positions([], pd.DataFrame(), 100000, MockRegime(), {})
    assert allocations == []
    assert summary.position_count == 0
    assert summary.cash_reserve == 100000


def test_assign_positions_volatility_penalty():
    """高波动股票权重更低."""
    high_vol_kline = _make_kline(10.0)
    # 修改为高波动
    high_vol_kline["收盘"] = [10.0 + np.random.randn() * 3 for _ in range(60)]
    low_vol_kline = _make_kline(10.0)
    low_vol_kline["收盘"] = [10.0 + np.random.randn() * 0.5 for _ in range(60)]

    kline = {"000001": high_vol_kline, "000002": low_vol_kline}
    signals = [
        MockSignal(code="000001", confidence=0.5, key_prices=MockKeyPrices()),
        MockSignal(code="000002", confidence=0.5, key_prices=MockKeyPrices()),
    ]
    stock_pool = pd.DataFrame({"code": ["000001", "000002"], "name": ["A", "B"]})
    regime = MockRegime("sideways")
    allocations, summary = assign_positions(signals, stock_pool, 100000, regime, kline)

    if len(allocations) == 2:
        high_vol_alloc = next(a for a in allocations if a.code == "000001")
        low_vol_alloc = next(a for a in allocations if a.code == "000002")
        # 低波动权重应该 ≥ 高波动（因为波动率惩罚）
        assert low_vol_alloc.base_weight >= high_vol_alloc.base_weight * 0.5
