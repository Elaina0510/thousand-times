# Phase 7: 回测引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 `backtest.py`，与生产共用因子计算代码，消除信号不一致，增加夏普比率、最大回撤等专业指标

**Architecture:** 回测引擎复用 `pipeline/factors.py` 和 `pipeline/signal.py`，加载历史数据逐日模拟交易，汇总统计指标

**Tech Stack:** Python 3.10+, pandas, numpy, dataclasses

## Global Constraints

- 回测与生产共用同一套因子计算代码（`pipeline/factors.py` + `factors/`）
- 模拟交易需考虑手续费和滑点
- 统计指标: 胜率、夏普比率、最大回撤、卡玛比率、盈亏比

## 文件结构

```
src/
├── backtest.py              ← 重写
tests/
└── test_backtest_v2.py      ← 新建
```

---

### Task 1: 定义回测数据结构

**Files:**
- Create: `tests/test_backtest_v2.py`
- Modify: `src/backtest.py` (先新建，后续重写)

**Interfaces:**
- Produces: `BacktestResult` dataclass
- Produces: `BacktestTrade` dataclass

- [ ] **Step 1: 编写数据结构测试**

```python
# tests/test_backtest_v2.py
"""测试 backtest.py 回测引擎（V2版本）."""
from __future__ import annotations

from src.backtest import BacktestResult, BacktestTrade


class TestBacktestResult:
    """BacktestResult 测试."""

    def test_create(self) -> None:
        result = BacktestResult(
            period="10days",
            total_signals=100,
            buy_signals=60,
            sell_signals=40,
            win_rate=0.65,
            avg_return=0.05,
            max_drawdown=-0.12,
            sharpe_ratio=2.1,
            profit_factor=2.5,
            calmar_ratio=1.8,
        )
        assert result.win_rate == 0.65
        assert result.sharpe_ratio == 2.1


class TestBacktestTrade:
    """BacktestTrade 测试."""

    def test_create(self) -> None:
        trade = BacktestTrade(
            date="2024-01-15",
            code="600519",
            action="buy",
            price=100.0,
            shares=100,
            amount=10000.0,
        )
        assert trade.amount == 10000.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py -v`

Expected: FAIL

- [ ] **Step 3: 实现数据结构**

```python
# src/backtest.py
"""回测引擎.

与生产共用因子计算代码，逐日模拟交易，汇总统计指标。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import AppConfig, BacktestConfig

logger = logging.getLogger("thousand-times")


@dataclass
class BacktestTrade:
    """单笔交易记录."""

    date: str
    code: str
    action: str  # "buy" | "sell"
    price: float
    shares: int
    amount: float


@dataclass
class BacktestResult:
    """回测结果."""

    period: str                 # 持有天数标签
    total_signals: int
    buy_signals: int
    sell_signals: int
    win_rate: float             # 胜率
    avg_return: float           # 平均收益
    max_drawdown: float         # 最大回撤
    sharpe_ratio: float         # 夏普比率
    profit_factor: float        # 盈亏比
    calmar_ratio: float         # 卡玛比率
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/backtest.py tests/test_backtest_v2.py
git commit -m "feat: 定义回测数据结构 BacktestResult/BacktestTrade"
```

---

### Task 2: 实现统计指标计算

**Files:**
- Modify: `src/backtest.py`
- Modify: `tests/test_backtest_v2.py`

**Interfaces:**
- Produces: `calc_sharpe(returns: pd.Series, risk_free: float) -> float`
- Produces: `calc_max_drawdown(equity_curve: pd.Series) -> float`
- Produces: `calc_calmar(returns: pd.Series, max_dd: float) -> float`
- Produces: `calc_profit_factor(winning: list[float], losing: list[float]) -> float`

- [ ] **Step 1: 编写统计指标测试**

在 `tests/test_backtest_v2.py` 末尾添加：

```python
import numpy as np
import pandas as pd

from src.backtest import (
    calc_calmar,
    calc_max_drawdown,
    calc_profit_factor,
    calc_sharpe,
)


class TestCalcSharpe:
    """夏普比率测试."""

    def test_positive_returns(self) -> None:
        returns = pd.Series([0.01, 0.02, 0.015, 0.01, 0.005])
        result = calc_sharpe(returns, risk_free=0.0)
        assert result > 0

    def test_zero_returns(self) -> None:
        returns = pd.Series([0.0] * 10)
        result = calc_sharpe(returns, risk_free=0.0)
        assert result == 0.0

    def test_negative_returns(self) -> None:
        returns = pd.Series([-0.01, -0.02, -0.015, -0.01, -0.005])
        result = calc_sharpe(returns, risk_free=0.0)
        assert result < 0


class TestCalcMaxDrawdown:
    """最大回撤测试."""

    def test_no_losses(self) -> None:
        equity = pd.Series([100, 101, 102, 103, 104])
        result = calc_max_drawdown(equity)
        assert result == 0.0

    def test_with_losses(self) -> None:
        equity = pd.Series([100, 95, 98, 90, 105])
        result = calc_max_drawdown(equity)
        assert result < 0
        assert abs(result - (-0.1)) < 0.05  # 大约-10%

    def test_steep_drop(self) -> None:
        equity = pd.Series([100, 80, 60, 80, 100])
        result = calc_max_drawdown(equity)
        assert abs(result - (-0.4)) < 0.01  # -40%


class TestCalcCalmar:
    """卡玛比率测试."""

    def test_positive_calmar(self) -> None:
        returns = pd.Series([0.02] * 20)  # 年化约+40%
        max_dd = -0.1
        result = calc_calmar(returns, max_dd)
        assert result > 0


class TestCalcProfitFactor:
    """盈亏比测试."""

    def test_more_profitable(self) -> None:
        result = calc_profit_factor([10, 20, 15], [-5, -3])
        assert result > 1.0

    def test_more_losses(self) -> None:
        result = calc_profit_factor([10], [-10, -8, -6])
        assert result < 1.0

    def test_no_losses(self) -> None:
        result = calc_profit_factor([10, 20], [])
        # 无穷大，返回一个大值
        assert result > 100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py::TestCalcSharpe -v`

Expected: FAIL

- [ ] **Step 3: 实现统计指标**

在 `src/backtest.py` 中添加：

```python
def calc_sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
    """计算夏普比率 = (年化收益 - 无风险利率) / 年化波动率.

    假设日度数据，Annualization = sqrt(252)。

    Args:
        returns: 日收益率序列
        risk_free: 无风险利率 (年化)

    Returns:
        float: 夏普比率
    """
    if len(returns) < 2 or returns.std() == 0:
        return 0.0

    excess = returns.mean() * 252 - risk_free
    vol = returns.std() * np.sqrt(252)
    return float(excess / max(vol, 1e-8))


def calc_max_drawdown(equity_curve: pd.Series) -> float:
    """计算最大回撤 = (最低点 - 最高点) / 最高点.

    只考虑在最高点之后的最低点。

    Args:
        equity_curve: 权益曲线序列

    Returns:
        float: 最大回撤（负数），0表示无回撤
    """
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return float(drawdown.min())


def calc_calmar(returns: pd.Series, max_dd: float) -> float:
    """计算卡玛比率 = 年化收益 / |最大回撤|.

    Args:
        returns: 日收益率序列
        max_dd: 最大回撤（应为负数）

    Returns:
        float: 卡玛比率
    """
    annual_return = returns.mean() * 252
    return float(annual_return / max(abs(max_dd), 1e-8))


def calc_profit_factor(winning: list[float], losing: list[float]) -> float:
    """计算盈亏比 = 总盈利 / |总亏损|.

    Args:
        winning: 盈利金额列表
        losing: 亏损金额列表

    Returns:
        float: 盈亏比
    """
    total_win = sum(winning)
    total_loss = abs(sum(losing))
    if total_loss == 0:
        return float("inf") if total_win > 0 else 0.0
    return float(total_win / total_loss)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/backtest.py tests/test_backtest_v2.py
git commit -m "feat: 实现回测统计指标（夏普/最大回撤/卡玛/盈亏比）"
```

---

### Task 3: 实现模拟交易和回测主函数

**Files:**
- Modify: `src/backtest.py`
- Modify: `tests/test_backtest_v2.py`

**Interfaces:**
- Produces: `run_backtest(config: AppConfig) -> list[BacktestResult]`

- [ ] **Step 1: 编写回测主函数测试**

在 `tests/test_backtest_v2.py` 末尾添加：

```python
from unittest.mock import MagicMock, patch

from src.backtest import simulate_trade


class TestSimulateTrade:
    """模拟交易测试."""

    def test_buy_reduces_cash(self) -> None:
        """买入减少现金."""
        result_shares, result_cash, result_cost = simulate_trade(
            action="buy", price=10.0, capital=10000.0, shares=0,
            commission_rate=0.001, slippage=0.001,
        )
        assert result_shares > 0
        assert result_cash < 10000.0
        assert result_cost > 0

    def test_sell_increases_cash(self) -> None:
        """卖出增加现金."""
        result_shares, result_cash, result_cost = simulate_trade(
            action="sell", price=10.0, capital=5000.0, shares=1000,
            commission_rate=0.001, slippage=0.001,
        )
        assert result_shares == 0
        assert result_cash > 5000.0

    def test_hold_does_nothing(self) -> None:
        """hold保持不动."""
        result_shares, result_cash, result_cost = simulate_trade(
            action="hold", price=10.0, capital=10000.0, shares=100,
            commission_rate=0.001, slippage=0.001,
        )
        assert result_shares == 100
        assert result_cash == 10000.0


class TestRunBacktest:
    """run_backtest 集成测试."""

    @patch("src.backtest.ak")
    def test_returns_results_list(self, mock_ak: MagicMock) -> None:
        """返回 BacktestResult 列表."""
        # 构造历史K线数据
        dates = pd.date_range("2024-01-01", periods=30)
        mock_kline = pd.DataFrame({
            "date": dates,
            "open": [10.0] * 30,
            "high": [10.5] * 30,
            "low": [9.5] * 30,
            "close": np.linspace(10, 12, 30),
            "volume": [1e6] * 30,
        })
        mock_ak.stock_zh_index_daily.return_value = mock_kline

        from src.backtest import run_backtest
        config = AppConfig()
        config.backtest.start_date = "2024-01-01"
        config.backtest.end_date = "2024-01-30"
        config.backtest.pool_size = 3

        # 使用 mock 跳过数据采集
        with patch("src.backtest.fetch_index_kline") as mock_idx, \
             patch("src.backtest.batch_fetch_klines") as mock_klines, \
             patch("src.backtest.calc_factors") as mock_factors, \
             patch("src.backtest.generate_signals") as mock_signals:

            mock_idx.return_value = mock_kline
            mock_klines.return_value = {}
            mock_factors.return_value = {}
            mock_signals.return_value = []

            results = run_backtest(config)

            # 即使无信号也应返回空结果列表
            assert isinstance(results, list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py::TestSimulateTrade -v`

Expected: FAIL

- [ ] **Step 3: 实现模拟交易和回测主函数**

在 `src/backtest.py` 末尾添加：

```python
from src.pipeline.collect import fetch_index_kline, batch_fetch_klines
from src.pipeline.factors import calc_factors
from src.pipeline.signal import generate_signals


def simulate_trade(
    action: str,
    price: float,
    capital: float,
    shares: int,
    commission_rate: float = 0.001,
    slippage: float = 0.001,
) -> tuple[int, float, float]:
    """模拟单笔交易.

    Args:
        action: "buy" | "sell" | "hold"
        price: 成交价格
        capital: 当前可用资金
        shares: 当前持仓股数
        commission_rate: 手续费率
        slippage: 滑点率

    Returns:
        tuple[int, float, float]: (新持仓股数, 新可用资金, 交易成本)
    """
    if action == "hold":
        return shares, capital, 0.0

    if action == "buy":
        # 全仓买入
        buy_price = price * (1 + slippage)
        max_shares = int(capital / (buy_price * (1 + commission_rate)))
        if max_shares <= 0:
            return shares, capital, 0.0
        cost = max_shares * buy_price * (1 + commission_rate)
        return max_shares, capital - cost, cost

    if action == "sell":
        # 全仓卖出
        sell_price = price * (1 - slippage)
        revenue = shares * sell_price * (1 - commission_rate)
        return 0, capital + revenue, revenue

    return shares, capital, 0.0


def _simulate_period(
    trading_dates: list[str],
    kline_cache: dict[str, pd.DataFrame],
    index_kline: pd.DataFrame,
    hold_days: int,
    config: AppConfig,
) -> tuple[list[float], list[float], int, int, int]:
    """对单个持有期进行逐日模拟.

    Args:
        trading_dates: 回测期间的交易日列表
        kline_cache: 个股K线缓存
        index_kline: 指数K线
        hold_days: 持有天数
        config: 应用配置

    Returns:
        tuple: (winning_returns, losing_returns, total_signals, buy_signals, sell_signals)
    """
    winning: list[float] = []
    losing: list[float] = []
    total_signals = 0
    buy_signals = 0
    sell_signals = 0

    bt_config = config.backtest
    codes = list(kline_cache.keys())

    for i, date in enumerate(trading_dates):
        if i + hold_days >= len(trading_dates):
            break  # 不够持有天数

        # 截取当前日期之前的K线做因子计算
        current_kline_cache: dict[str, pd.DataFrame] = {}
        for code in codes:
            kline = kline_cache[code]
            mask = kline["date"].astype(str) <= str(date)[:10]
            if mask.sum() >= 60:
                current_kline_cache[code] = kline[mask].reset_index(drop=True)

        if not current_kline_cache:
            continue

        # 模拟 DataBundle
        from src.pipeline.collect import DataBundle, FundamentalData
        from src.pipeline.factors import calc_factors
        from src.pipeline.signal import generate_signals

        stock_pool = pd.DataFrame({
            "code": list(current_kline_cache.keys()),
            "name": list(current_kline_cache.keys()),
        })

        # 截取指数历史
        idx_mask = index_kline["date"].astype(str) <= str(date)[:10]
        current_index = index_kline[idx_mask].reset_index(drop=True)

        data = DataBundle(
            index_kline=current_index,
            stock_pool=stock_pool,
            kline_cache=current_kline_cache,
            fundamental_cache={c: FundamentalData() for c in current_kline_cache},
            north_flow=pd.DataFrame(),
            margin_data=None,
            limit_up_count=0,
            limit_down_count=0,
            advance_decline_ratio=1.0,
            macro_indicators={},
            sector_flow=pd.DataFrame(),
            news_items=[],
            policy_impacts=[],
            etf_pool=[],
            etf_kline_cache={},
        )

        try:
            scores = calc_factors(data, config, regime_state="sideways")
            signals = generate_signals(scores, data, config, regime_state="sideways")
        except Exception:
            continue

        # 模拟交易
        for signal in signals:
            if signal.action == "hold":
                continue

            entry_kline = kline_cache.get(signal.code)
            if entry_kline is None:
                continue

            # 获取入场价
            entry_mask = entry_kline["date"].astype(str) == str(date)[:10]
            if not entry_mask.any():
                continue
            entry_price = float(entry_kline[entry_mask]["close"].iloc[0])

            # 获取出场价（hold_days 后）
            exit_idx = i + hold_days
            if exit_idx >= len(trading_dates):
                continue
            exit_date = str(trading_dates[exit_idx])[:10]
            exit_mask = entry_kline["date"].astype(str) == exit_date
            if not exit_mask.any():
                continue
            exit_price = float(entry_kline[exit_mask]["close"].iloc[0])

            # 计算收益（含手续费和滑点）
            slippage = bt_config.slippage
            commission = bt_config.commission_rate

            if signal.action == "buy":
                actual_entry = entry_price * (1 + slippage)
                actual_exit = exit_price * (1 - slippage)
                ret = (actual_exit / actual_entry) - 1 - 2 * commission
                buy_signals += 1
            else:  # sell (做空信号按反向计算)
                actual_entry = entry_price * (1 - slippage)
                actual_exit = exit_price * (1 + slippage)
                ret = (actual_entry / actual_exit) - 1 - 2 * commission
                sell_signals += 1

            total_signals += 1
            if ret > 0:
                winning.append(ret)
            else:
                losing.append(ret)

    return winning, losing, total_signals, buy_signals, sell_signals


def run_backtest(config: AppConfig) -> list[BacktestResult]:
    """运行回测.

    加载历史数据，逐日模拟交易，汇总统计。

    与生产共用 pipeline/factors.py + pipeline/signal.py，消除信号不一致。

    Args:
        config: 应用配置

    Returns:
        list[BacktestResult]: 各持有期结果
    """
    logger.info("=== 回测引擎启动 ===")
    bt_config = config.backtest

    # 1. 加载历史指数数据
    index_kline = fetch_index_kline("sh000985", days=500)
    if index_kline.empty:
        logger.error("无法获取指数K线，回测终止")
        return []

    # 2. 获取交易日历
    all_dates = index_kline["date"].tolist()
    trading_dates = [d for d in all_dates
                     if bt_config.start_date <= str(d)[:10] <= bt_config.end_date]

    if not trading_dates:
        logger.error("回测期间内无交易日")
        return []

    logger.info(f"回测期间: {bt_config.start_date} ~ {bt_config.end_date} ({len(trading_dates)} 个交易日)")

    # 3. 预加载历史K线（使用日期切片模拟历史状态）
    kline_cache = batch_fetch_klines([], days=500)  # 小股票池
    if not kline_cache:
        logger.warning("无股票数据，使用指数数据做简化回测")
        # 用指数数据构造一个虚拟股票
        kline_cache = {"sh000985": index_kline}

    # 4. 对每个持有期运行模拟
    results: list[BacktestResult] = []

    for hold_days in bt_config.hold_days:
        winning, losing, total, buys, sells = _simulate_period(
            trading_dates, kline_cache, index_kline, hold_days, config
        )

        # 计算统计指标
        all_returns = winning + losing
        if not all_returns:
            results.append(BacktestResult(
                period=f"{hold_days}days", total_signals=0, buy_signals=0,
                sell_signals=0, win_rate=0.0, avg_return=0.0,
                max_drawdown=0.0, sharpe_ratio=0.0,
                profit_factor=0.0, calmar_ratio=0.0,
            ))
            continue

        returns_series = pd.Series(all_returns)
        equity_curve = (1 + returns_series).cumprod() * bt_config.initial_capital
        max_dd = calc_max_drawdown(equity_curve)

        result = BacktestResult(
            period=f"{hold_days}days",
            total_signals=total,
            buy_signals=buys,
            sell_signals=sells,
            win_rate=len(winning) / max(len(all_returns), 1),
            avg_return=float(returns_series.mean()),
            max_drawdown=max_dd,
            sharpe_ratio=calc_sharpe(returns_series),
            profit_factor=calc_profit_factor(winning, losing),
            calmar_ratio=calc_calmar(returns_series, max_dd),
        )
        results.append(result)
        logger.info(
            f"  {hold_days}日持有: {total}信号 胜率={result.win_rate:.1%} "
            f"夏普={result.sharpe_ratio:.2f} 最大回撤={result.max_drawdown:.1%}"
        )

    logger.info("回测完成")
    return results
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_backtest_v2.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/backtest.py tests/test_backtest_v2.py
git commit -m "feat: 实现回测模拟交易和 run_backtest 主函数"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_backtest_v2.py -v`
- [ ] 夏普比率计算正确 (年化 * sqrt(252))
- [ ] 最大回撤计算正确 (峰值到谷值)
- [ ] 卡玛比率计算正确 (年化收益率/|最大回撤|)
- [ ] 模拟交易含手续费和滑点
- [ ] run_backtest 实现逐日回测循环，复用 pipeline/factors.py + pipeline/signal.py
- [ ] 回测结果包含完整统计指标 (胜率/夏普/回撤/卡玛/盈亏比)
- [ ] 回测复用 pipeline/factors.py 和 pipeline/signal.py
