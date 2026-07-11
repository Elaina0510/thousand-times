"""RiskGuard 单元测试."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk.guard import (
    GuardResult,
    RejectReason,
    RiskRuleResult,
    apply_risk_rules,
    check_liquidity,
    check_limit_price,
    check_price_limit,
    check_recent_signal,
    check_st_stock,
    check_volatility,
)


class MockSignal:
    def __init__(self, code="000001", name="测试", action="buy", confidence=0.8):
        self.code = code
        self.name = name
        self.action = action
        self.confidence = confidence
        self.key_prices = None


def _make_kline(price=10.0, rows=60, volume=5000000):
    """创建模拟 K 线."""
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    return pd.DataFrame({
        "日期": dates,
        "收盘": [price] * rows,
        "最高": [price * 1.02] * rows,
        "最低": [price * 0.98] * rows,
        "成交量": [volume] * rows,
    })


# ── check_st_stock ──
def test_st_stock_rejected():
    result = check_st_stock("000001", "*ST测试")
    assert not result.passed
    assert result.reject_reason == RejectReason.ST_STOCK


def test_normal_stock_pass():
    result = check_st_stock("000001", "测试科技")
    assert result.passed


# ── check_limit_price ──
def test_limit_up_rejected():
    stock_pool = pd.DataFrame({"code": ["000001"], "涨跌幅": [10.05]})
    result = check_limit_price("000001", stock_pool)
    assert not result.passed
    assert result.reject_reason == RejectReason.LIMIT_UP


def test_limit_down_rejected():
    stock_pool = pd.DataFrame({"code": ["000001"], "涨跌幅": [-10.0]})
    result = check_limit_price("000001", stock_pool)
    assert not result.passed
    assert result.reject_reason == RejectReason.LIMIT_DOWN


def test_normal_price_pass():
    stock_pool = pd.DataFrame({"code": ["000001"], "涨跌幅": [2.5]})
    result = check_limit_price("000001", stock_pool)
    assert result.passed


def test_empty_stock_pool():
    result = check_limit_price("000001", pd.DataFrame())
    assert result.passed


# ── check_liquidity ──
def test_low_liquidity_rejected():
    kline = _make_kline(price=10.0, volume=50000)
    result = check_liquidity("000001", {"000001": kline})
    assert not result.passed
    assert result.reject_reason == RejectReason.LOW_LIQUIDITY


def test_normal_liquidity_pass():
    kline = _make_kline(price=10.0, volume=5000000)  # 500万×10元=5000万
    result = check_liquidity("000001", {"000001": kline})
    assert result.passed


def test_no_kline_pass():
    result = check_liquidity("000001", {})
    assert result.passed


# ── check_price_limit ──
def test_penny_stock_rejected():
    kline = _make_kline(price=1.5)
    result = check_price_limit("000001", {"000001": kline})
    assert not result.passed
    assert result.reject_reason == RejectReason.PRICE_LIMIT


def test_normal_price_ok():
    kline = _make_kline(price=15.0)
    result = check_price_limit("000001", {"000001": kline})
    assert result.passed


# ── check_volatility ──
def test_high_volatility_warning():
    prices = [10.0]
    for _ in range(59):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.15)))
    kline = pd.DataFrame({
        "日期": pd.date_range("2026-01-01", periods=60, freq="B"),
        "收盘": prices,
    })
    result = check_volatility("000001", {"000001": kline})
    assert not result.passed  # 仅警告，但仍 passed=False


def test_normal_volatility_pass():
    kline = _make_kline(price=10.0)
    result = check_volatility("000001", {"000001": kline})
    assert result.passed  # 零波动率


# ── apply_risk_rules ──
def test_apply_risk_rules_stock_passes():
    signals = [MockSignal(code="000001", name="测试科技")]
    kline = {"000001": _make_kline(price=15.0, volume=5000000)}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试科技"], "涨跌幅": [2.5]})
    result = apply_risk_rules(signals, stock_pool, kline, [], {})
    assert result.passed_count == 1
    assert len(result.rejected) == 0


def test_apply_risk_rules_st_rejected():
    signals = [MockSignal(code="000001", name="*ST测试")]
    kline = {"000001": _make_kline(price=15.0)}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["*ST测试"], "涨跌幅": [2.5]})
    result = apply_risk_rules(signals, stock_pool, kline, [], {})
    assert result.passed_count == 0
    assert len(result.rejected) == 1


def test_apply_risk_rules_warnings_not_blocks():
    """警告不阻塞信号."""
    signals = [MockSignal(code="000001", name="测试科技")]
    # 高波动但正常价格 + 足够流动性
    prices = [15.0]
    for _ in range(25):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.05)))
    for _ in range(34):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.15)))
    kline_df = pd.DataFrame({
        "收盘": prices,
        "成交量": [5000000.0] * 60,
        "最高": [p * 1.02 for p in prices],
        "最低": [p * 0.98 for p in prices],
    })
    kline = {"000001": kline_df}
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试科技"], "涨跌幅": [2.5]})
    result = apply_risk_rules(signals, stock_pool, kline, [], {})
    # 波动率异常仅警告，不拒绝（流动性足够，价格正常）
    assert result.passed_count == 1


def test_apply_risk_rules_empty_signals():
    result = apply_risk_rules([], pd.DataFrame(), {}, [], {})
    assert result.input_count == 0
    assert result.passed_count == 0
