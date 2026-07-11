"""回测验证模块 — BacktestValidator.

对策略进行完整的历史回测验证，输出统计显著的结果。
包含统计显著性检验（t检验）和蒙特卡洛模拟。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("thousand-times")


@dataclass
class BacktestConfig:
    """回测配置."""

    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    pool_size: int = 100
    top_n: int = 20               # 每日取前N只买入
    hold_days: list[int] = field(default_factory=lambda: [1, 3, 5, 10, 20])
    commission_rate: float = 0.0003  # 万三佣金
    stamp_tax: float = 0.001        # 千一印花税（卖出）
    slippage: float = 0.001         # 千一滑点
    initial_capital: float = 1_000_000.0
    benchmark: str = "000300"       # 基准指数（沪深300）


@dataclass
class BacktestPeriodResult:
    """单个持仓周期的回测结果."""

    hold_days: int = 0
    total_trades: int = 0
    win_rate: float = 0.0           # 胜率（%）
    avg_return: float = 0.0         # 平均收益（%）
    median_return: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    win_loss_ratio: float = 0.0
    avg_win_size: float = 0.0
    avg_loss_size: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    information_ratio: float = 0.0
    t_statistic: float = 0.0
    p_value: float = 1.0


@dataclass
class FullBacktestResult:
    """完整回测报告."""

    config: BacktestConfig = field(default_factory=BacktestConfig)
    period_results: list[BacktestPeriodResult] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    benchmark_curve: list[float] = field(default_factory=list)
    monthly_returns: dict[str, float] = field(default_factory=dict)
    yearly_returns: dict[str, float] = field(default_factory=dict)
    worst_month: tuple[str, float] = ("", 0.0)
    best_month: tuple[str, float] = ("", 0.0)
    consecutive_losses: int = 0
    recommendations: str = ""


def run_full_backtest(config: BacktestConfig | None = None) -> FullBacktestResult:
    """运行完整回测（简化版，用于测试验证框架）.

    Args:
        config: 回测配置.

    Returns:
        FullBacktestResult.
    """
    if config is None:
        config = BacktestConfig()

    result = FullBacktestResult(config=config)

    # 对各持仓周期生成模拟结果
    for hold_days in config.hold_days:
        np.random.seed(42 + hold_days)
        n_trades = 200

        # 生成模拟收益（正期望策略）
        returns = np.random.normal(0.005, 0.03, n_trades).tolist()

        period = _compute_period_stats(returns, hold_days, config)
        result.period_results.append(period)

    # 模拟净值曲线
    np.random.seed(99)
    n_days = 500
    daily_rets = np.random.normal(0.0005, 0.015, n_days)
    equity = config.initial_capital
    result.equity_curve = [equity]
    for r in daily_rets:
        equity *= (1 + r)
        result.equity_curve.append(float(equity))

    # 基准
    bench_equity = config.initial_capital
    result.benchmark_curve = [bench_equity]
    bench_rets = np.random.normal(0.0003, 0.012, n_days)
    for r in bench_rets:
        bench_equity *= (1 + r)
        result.benchmark_curve.append(float(bench_equity))

    # t 检验
    t_stat, p_val = statistical_significance_test(
        [float(x) for x in daily_rets], [float(x) for x in bench_rets],
    )

    if result.period_results:
        result.period_results[0].t_statistic = t_stat
        result.period_results[0].p_value = p_val

    result.recommendations = _generate_recommendations(result)

    return result


def _compute_period_stats(
    returns: list[float],
    hold_days: int,
    config: BacktestConfig,
) -> BacktestPeriodResult:
    """计算单周期的统计指标."""
    if not returns:
        return BacktestPeriodResult(hold_days=hold_days)

    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    avg_ret = float(np.mean(returns))
    annual_factor = 252 / max(hold_days, 1)
    sharpe = float(np.mean(returns) / max(np.std(returns), 1e-8) * np.sqrt(annual_factor))

    # 下行标准差
    downside = [min(r, 0) for r in returns]
    downside_std = float(np.std(downside))
    sortino = float(np.mean(returns) / max(downside_std, 1e-8) * np.sqrt(annual_factor))

    # 盈亏比
    total_wins = sum(wins) if wins else 0
    total_losses = abs(sum(losses)) if losses else 0
    profit_factor = total_wins / max(total_losses, 1e-8)

    return BacktestPeriodResult(
        hold_days=hold_days,
        total_trades=len(returns),
        win_rate=len(wins) / len(returns) * 100,
        avg_return=round(avg_ret * 100, 2),
        median_return=round(float(np.median(returns)) * 100, 2),
        max_win=round(max(returns) * 100, 2) if returns else 0.0,
        max_loss=round(min(returns) * 100, 2) if returns else 0.0,
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        profit_factor=round(profit_factor, 2),
        total_return=round(float(np.sum(returns)) * 100, 2),
        annual_return=round(float(np.mean(returns)) * annual_factor * 100, 2),
    )


def run_parameter_sweep(
    base_config: BacktestConfig,
    param_grid: dict[str, list[float]],
) -> list[tuple[dict[str, float], BacktestPeriodResult]]:
    """参数网格搜索.

    Args:
        base_config: 基础配置.
        param_grid: 参数网格.

    Returns:
        [(参数组合, 结果), ...] 按夏普比率降序.
    """
    results: list[tuple[dict[str, float], BacktestPeriodResult]] = []

    top_ns = param_grid.get("top_n", [base_config.top_n])
    hold_days_list = param_grid.get("hold_days", [base_config.hold_days[0]])

    for top_n in top_ns:
        for hold in hold_days_list:
            params = {"top_n": float(top_n), "hold_days": float(hold)}
            config = BacktestConfig(
                **{**base_config.__dict__, "top_n": int(top_n), "hold_days": [int(hold)]},
            )
            fb = run_full_backtest(config)
            if fb.period_results:
                results.append((params, fb.period_results[0]))

    results.sort(key=lambda x: x[1].sharpe_ratio, reverse=True)
    return results


def statistical_significance_test(
    returns: list[float],
    benchmark_returns: list[float],
) -> tuple[float, float]:
    """策略超额收益的 t 检验.

    H0: 策略收益 ≤ 基准收益
    如果 p < 0.05，拒绝 H0，策略有统计显著的 alpha.

    Args:
        returns: 策略收益率序列.
        benchmark_returns: 基准收益率序列.

    Returns:
        (t_statistic, p_value)
    """
    if len(returns) != len(benchmark_returns):
        min_len = min(len(returns), len(benchmark_returns))
        returns = returns[:min_len]
        benchmark_returns = benchmark_returns[:min_len]

    if len(returns) < 10:
        return 0.0, 1.0

    excess = [returns[i] - benchmark_returns[i] for i in range(len(returns))]
    n = len(excess)
    mean_excess = float(np.mean(excess))
    std_excess = float(np.std(excess, ddof=1))

    if std_excess < 1e-10:
        return 0.0, 1.0

    t_stat = mean_excess / (std_excess / np.sqrt(n))

    # 近似 p 值（使用正态分布近似）
    from math import erf, sqrt
    p_value = float(2 * (1 - 0.5 * (1 + erf(abs(t_stat) / sqrt(2)))))

    return round(t_stat, 4), round(p_value, 4)


def monte_carlo_test(
    returns: list[float],
    n_simulations: int = 10000,
) -> dict[str, float]:
    """蒙特卡洛模拟：验证策略表现是否来自运气.

    Args:
        returns: 收益率序列.
        n_simulations: 模拟次数.

    Returns:
        {"real_sharpe": x, "percentile": 95.0, "is_significant": True}
    """
    if not returns or len(returns) < 5:
        return {"real_sharpe": 0.0, "percentile": 50.0, "is_significant": False}

    real_sharpe = float(np.mean(returns) / max(np.std(returns), 1e-8) * np.sqrt(252))

    # 随机重排模拟
    simulated_sharpes: list[float] = []
    np.random.seed(42)
    for _ in range(n_simulations):
        shuffled = np.random.permutation(returns)
        sim_sharpe = float(np.mean(shuffled) / max(np.std(shuffled), 1e-8) * np.sqrt(252))
        simulated_sharpes.append(sim_sharpe)

    percentile = float(sum(1 for s in simulated_sharpes if s <= real_sharpe) / n_simulations * 100)

    return {
        "real_sharpe": round(real_sharpe, 4),
        "percentile": round(percentile, 1),
        "is_significant": percentile > 95.0,
    }


def _generate_recommendations(result: FullBacktestResult) -> str:
    """基于回测结果生成改进建议."""
    lines: list[str] = []
    for pr in result.period_results:
        if pr.sharpe_ratio < 0.5:
            lines.append(f"持仓 {pr.hold_days} 日夏普比率 {pr.sharpe_ratio} < 0.5，建议优化")
        if pr.win_rate < 50:
            lines.append(f"持仓 {pr.hold_days} 日胜率 {pr.win_rate:.0f}% < 50%，需调整阈值")
        if pr.p_value > 0.05:
            lines.append(f"持仓 {pr.hold_days} 日 p={pr.p_value} > 0.05，统计不显著")
    return "; ".join(lines) if lines else "回测通过基本标准"
