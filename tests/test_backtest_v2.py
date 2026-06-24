"""V2 回测引擎测试。"""

from __future__ import annotations

import pytest

from src.backtest import (
    BacktestResult,
    BacktestTrade,
    calc_calmar,
    calc_max_drawdown,
    calc_profit_factor,
    calc_sharpe,
)


class TestCalcSharpe:
    """夏普比率测试。"""

    def test_positive_returns(self):
        returns = [1.0, 2.0, 1.5, 2.5, 1.0]
        sharpe = calc_sharpe(returns)
        assert sharpe > 0

    def test_negative_returns(self):
        returns = [-1.0, -2.0, -1.5, -2.5, -1.0]
        sharpe = calc_sharpe(returns)
        assert sharpe < 0

    def test_empty_returns(self):
        assert calc_sharpe([]) == 0.0

    def test_single_return(self):
        assert calc_sharpe([1.0]) == 0.0

    def test_zero_std(self):
        assert calc_sharpe([1.0, 1.0, 1.0]) == 0.0


class TestCalcMaxDrawdown:
    """最大回撤测试。"""

    def test_no_drawdown(self):
        equity = [100, 110, 120, 130]
        assert calc_max_drawdown(equity) == 0.0

    def test_simple_drawdown(self):
        equity = [100, 120, 90, 110]
        dd = calc_max_drawdown(equity)
        assert abs(dd - 0.25) < 0.01  # (120-90)/120 = 0.25

    def test_empty(self):
        assert calc_max_drawdown([]) == 0.0

    def test_single_value(self):
        assert calc_max_drawdown([100]) == 0.0


class TestCalcCalmar:
    """卡玛比率测试。"""

    def test_positive(self):
        ratio = calc_calmar(0.20, 0.10)
        assert ratio == 2.0

    def test_zero_drawdown(self):
        assert calc_calmar(0.20, 0.0) == 0.0


class TestCalcProfitFactor:
    """盈亏比测试。"""

    def test_all_profits(self):
        pf = calc_profit_factor([1.0, 2.0, 3.0])
        assert pf == float("inf")

    def test_all_losses(self):
        pf = calc_profit_factor([-1.0, -2.0, -3.0])
        assert pf == 0.0

    def test_mixed(self):
        pf = calc_profit_factor([10.0, -5.0, 20.0, -10.0])
        assert pf == 30.0 / 15.0

    def test_empty(self):
        assert calc_profit_factor([]) == 0.0


class TestBacktestResult:
    """回测结果数据类测试。"""

    def test_default_values(self):
        r = BacktestResult()
        assert r.total_signals == 0
        assert r.win_rate == 0.0


class TestBacktestTrade:
    """交易记录数据类测试。"""

    def test_creation(self):
        t = BacktestTrade(date="2024-01-01", code="000001", action="buy", price=10.0)
        assert t.code == "000001"
        assert t.action == "buy"
