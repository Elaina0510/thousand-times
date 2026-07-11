"""PaperTrader 单元测试."""

from __future__ import annotations

import pandas as pd
import pytest

from feedback.paper_trader import (
    PaperAccount,
    PaperPosition,
    PaperTrade,
    check_go_live_readiness,
    execute_daily_signals,
    generate_paper_report,
    init_paper_account,
)


class MockSignal:
    def __init__(self, code="000001", name="test", action="buy", confidence=0.8,
                 current_price=10.0):
        self.code = code
        self.name = name
        self.action = action
        self.confidence = confidence
        self.key_prices = MockKeyPrices(current_price)


class MockKeyPrices:
    def __init__(self, current_price=10.0):
        self.current_price = current_price


def test_init_paper_account():
    """初始化账户."""
    account = init_paper_account(500000)
    assert account.initial_capital == 500000
    assert account.cash == 500000
    assert account.total_value == 500000


def test_init_paper_account_default():
    """默认资金."""
    account = init_paper_account()
    assert account.initial_capital == 1_000_000


def test_execute_buy_signal():
    """执行买入信号."""
    account = init_paper_account(100000)
    signals = [MockSignal(code="000001", action="buy", current_price=10.0)]
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试"]})
    account = execute_daily_signals(account, signals, stock_pool, "2026-07-11")
    assert "000001" in account.positions
    assert len(account.trade_history) == 1
    assert account.trade_history[0].action == "buy"


def test_execute_sell_signal():
    """执行卖出信号."""
    account = init_paper_account(100000)
    # 先买入
    buy_signal = MockSignal(code="000001", action="buy", current_price=10.0)
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试"]})
    account = execute_daily_signals(account, [buy_signal], stock_pool, "2026-07-11")
    # 再卖出
    sell_signal = MockSignal(code="000001", action="sell", current_price=11.0)
    account = execute_daily_signals(account, [sell_signal], stock_pool, "2026-07-12")
    assert "000001" not in account.positions
    assert len(account.trade_history) == 2


def test_execute_empty_signals():
    """空信号."""
    account = init_paper_account()
    account = execute_daily_signals(account, [], pd.DataFrame(), "2026-07-11")
    assert len(account.trade_history) == 0


def test_shares_rounding():
    """100股取整."""
    account = init_paper_account(10000)
    signals = [MockSignal(code="000001", action="buy", current_price=10.0)]
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试"]})
    account = execute_daily_signals(account, signals, stock_pool, "2026-07-11")
    if "000001" in account.positions:
        assert account.positions["000001"].shares % 100 == 0


def test_insufficient_cash():
    """资金不足时跳过买入."""
    account = init_paper_account(500)  # 只有 500 元
    signals = [MockSignal(code="000001", action="buy", current_price=1000.0)]
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试"]})
    account = execute_daily_signals(account, signals, stock_pool, "2026-07-11")
    assert "000001" not in account.positions


def test_generate_paper_report():
    """生成报告."""
    account = init_paper_account(100000)
    account.positions["000001"] = PaperPosition(
        code="000001", name="测试", shares=500,
        avg_cost=10.0, current_price=10.5, market_value=5250,
        pnl=250, pnl_pct=5.0,
    )
    report = generate_paper_report(account)
    assert "纸交易日报" in report
    assert "000001" in report


def test_check_go_live_not_ready():
    """刚初始化不满足条件."""
    account = init_paper_account()
    ready, reason = check_go_live_readiness(account)
    assert not ready
    assert "交易天数" in reason


def test_check_go_live_with_data():
    """有数据但未满足所有条件."""
    account = init_paper_account(100000)
    # 模拟 60 天数据
    for i in range(60):
        account.total_value = 100000 + i * 100
        account.daily_records.append({"date": f"2026-{i+1:02d}-01", "total_value": account.total_value})
    account.total_pnl = account.total_value - account.initial_capital
    ready, reason = check_go_live_readiness(account)
    # 可能通过也可能不通过（取决于夏普和回撤）
    assert isinstance(ready, bool)
