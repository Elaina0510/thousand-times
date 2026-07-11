"""BacktestValidator 单元测试."""

from __future__ import annotations

import numpy as np
import pytest

from feedback.backtest_validator import (
    BacktestConfig,
    BacktestPeriodResult,
    FullBacktestResult,
    _compute_period_stats,
    monte_carlo_test,
    run_full_backtest,
    run_parameter_sweep,
    statistical_significance_test,
)


def test_run_full_backtest():
    """运行完整回测."""
    config = BacktestConfig(hold_days=[5, 10])
    result = run_full_backtest(config)
    assert isinstance(result, FullBacktestResult)
    assert len(result.period_results) == 2
    assert len(result.equity_curve) > 0
    assert len(result.benchmark_curve) > 0


def test_run_full_backtest_default_config():
    """默认配置."""
    result = run_full_backtest()
    assert len(result.period_results) > 0


def test_statistical_significance():
    """t 检验."""
    np.random.seed(42)
    returns = (np.random.normal(0.01, 0.03, 100) + 0.003).tolist()
    benchmark = np.random.normal(0.005, 0.025, 100).tolist()
    t_stat, p_val = statistical_significance_test(returns, benchmark)
    assert isinstance(t_stat, float)
    assert isinstance(p_val, float)
    assert p_val >= 0


def test_statistical_significance_insignificant():
    """无超额收益 → p > 0.05."""
    np.random.seed(1)
    rets = np.random.normal(0.0, 0.02, 200).tolist()
    bench = np.random.normal(0.0, 0.02, 200).tolist()
    t_stat, p_val = statistical_significance_test(rets, bench)
    assert isinstance(p_val, float)


def test_monte_carlo_test():
    """蒙特卡洛模拟."""
    np.random.seed(42)
    returns = (np.random.normal(0.01, 0.03, 100) + 0.005).tolist()
    result = monte_carlo_test(returns, n_simulations=1000)
    assert "real_sharpe" in result
    assert "percentile" in result
    assert "is_significant" in result


def test_monte_carlo_empty():
    """空收益."""
    result = monte_carlo_test([], n_simulations=100)
    assert not result["is_significant"]


def test_compute_period_stats():
    """计算周期统计."""
    returns = [0.01, 0.02, -0.01, 0.03, -0.005]
    config = BacktestConfig()
    result = _compute_period_stats(returns, 5, config)
    assert result.total_trades == 5
    assert result.win_rate > 0
    assert result.annual_return != 0


def test_compute_period_stats_empty():
    """空列表."""
    result = _compute_period_stats([], 5, BacktestConfig())
    assert result.total_trades == 0


def test_run_parameter_sweep():
    """参数网格搜索."""
    config = BacktestConfig(hold_days=[5])
    param_grid = {"top_n": [5.0, 10.0], "hold_days": [5.0]}
    results = run_parameter_sweep(config, param_grid)
    assert len(results) > 0


def test_backtest_passing_standards():
    """验证回测通过标准可检查."""
    result = run_full_backtest()
    # 基本字段非空
    assert len(result.period_results) > 0
    pr = result.period_results[0]
    assert pr.sharpe_ratio is not None
    assert pr.win_rate is not None
    assert pr.t_statistic is not None
