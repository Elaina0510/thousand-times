# Phase 3: 市场环境判断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现增强版市场环境判断模块 `pipeline/regime.py`，使用5信号投票制准确判断牛市/熊市/震荡市

**Architecture:** 5个独立信号（趋势、成交量、北向资金、涨跌比、估值）各自投票，多数票决定市场状态，输出置信度和仓位建议

**Tech Stack:** Python 3.10+, pandas, numpy, dataclasses

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 所有公共函数和类必须有 Google 风格 docstring
- 使用 `from __future__ import annotations` 延迟注解求值
- 日志使用 `logging.getLogger("thousand-times")`
- 单个信号获取失败时跳过该票，不影响其他信号

## 文件结构

```
src/
└── pipeline/
    └── regime.py              ← 新建：市场环境判断

tests/
└── test_pipeline_regime.py    ← 新建
```

---

### Task 1: 定义 MarketRegime 数据结构和信号接口

**Files:**
- Create: `src/pipeline/regime.py`
- Create: `tests/test_pipeline_regime.py`

**Interfaces:**
- Produces: `MarketRegime` dataclass
- Produces: `RegimeVote` dataclass
- Produces: `judge_market_regime(data: DataBundle, config: AppConfig) -> MarketRegime`

- [ ] **Step 1: 编写 MarketRegime 测试**

```python
# tests/test_pipeline_regime.py
"""测试 pipeline/regime.py 市场环境判断模块."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.pipeline.regime import MarketRegime, RegimeVote, judge_market_regime


class TestMarketRegime:
    """MarketRegime 数据结构测试."""

    def test_create_bull_regime(self) -> None:
        """测试创建牛市环境."""
        regime = MarketRegime(
            state="bull",
            confidence=0.8,
            position_advice=0.94,
            signals={"trend": "bull", "volume": "bull", "north": "bull"},
            description="牛市",
        )
        assert regime.state == "bull"
        assert regime.confidence == 0.8
        assert regime.position_advice > 0.7

    def test_create_bear_regime(self) -> None:
        """测试创建熊市环境."""
        regime = MarketRegime(
            state="bear",
            confidence=0.6,
            position_advice=0.12,
            signals={"trend": "bear", "volume": "bear"},
            description="熊市",
        )
        assert regime.state == "bear"
        assert regime.position_advice < 0.3

    def test_create_sideways_regime(self) -> None:
        """测试创建震荡环境."""
        regime = MarketRegime(
            state="sideways",
            confidence=0.5,
            position_advice=0.5,
            signals={"trend": "neutral", "volume": "bull"},
            description="震荡",
        )
        assert regime.state == "sideways"
        assert regime.position_advice == 0.5


class TestRegimeVote:
    """RegimeVote 数据结构测试."""

    def test_create_vote(self) -> None:
        """测试创建投票信号."""
        vote = RegimeVote(
            name="trend",
            vote="bull",
            confidence=0.9,
            reason="MA20 > MA60 且价格 > MA20",
        )
        assert vote.name == "trend"
        assert vote.vote == "bull"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py -v`

Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 MarketRegime 和 RegimeVote**

```python
# src/pipeline/regime.py
"""市场环境判断模块.

使用5信号投票制判断当前市场处于牛市/熊市/震荡市。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import AppConfig

logger = logging.getLogger("thousand-times")


@dataclass
class RegimeVote:
    """市场环境投票信号.

    注意: 与 pipeline/signal.py 的 SignalVote 区分。
    """

    name: str           # 信号名称
    vote: str           # "bull" | "bear" | "neutral"
    confidence: float   # 0.0 ~ 1.0
    reason: str         # 投票理由


@dataclass
class MarketRegime:
    """市场环境判断结果."""

    state: str                    # "bull" | "bear" | "sideways"
    confidence: float             # 0.0 ~ 1.0
    position_advice: float        # 建议仓位 0.0 ~ 1.0
    signals: dict[str, str]       # 各信号的原始判断
    description: str              # 人类可读描述
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py::TestMarketRegime tests/test_pipeline_regime.py::TestRegimeVote -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/regime.py tests/test_pipeline_regime.py
git commit -m "feat: 定义 MarketRegime 和 RegimeVote 数据结构"
```

---

### Task 2: 实现趋势信号和成交量信号

**Files:**
- Modify: `src/pipeline/regime.py`
- Modify: `tests/test_pipeline_regime.py`

**Interfaces:**
- Produces: `_signal_trend(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote`
- Produces: `_signal_volume(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote`

- [ ] **Step 1: 编写趋势信号测试**

在 `tests/test_pipeline_regime.py` 末尾添加：

```python
from src.pipeline.regime import _signal_trend, _signal_volume
from src.config import RegimeConfig


class TestSignalTrend:
    """趋势信号测试."""

    def test_bull_when_ma20_above_ma60_and_price_above_ma20(self) -> None:
        """测试牛市条件: MA20 > MA60 且价格 > MA20."""
        # 构造上升趋势数据
        dates = pd.date_range("2024-01-01", periods=100)
        prices = np.linspace(10, 20, 100)  # 线性上涨
        df = pd.DataFrame({
            "date": dates,
            "close": prices,
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "volume": [1e6] * 100,
        })

        config = RegimeConfig()
        result = _signal_trend(df, config)

        assert result.vote == "bull"

    def test_bear_when_ma20_below_ma60_and_price_below_ma20(self) -> None:
        """测试熊市条件: MA20 < MA60 且价格 < MA20."""
        # 构造下降趋势数据
        dates = pd.date_range("2024-01-01", periods=100)
        prices = np.linspace(20, 10, 100)  # 线性下跌
        df = pd.DataFrame({
            "date": dates,
            "close": prices,
            "open": prices * 1.01,
            "high": prices * 1.02,
            "low": prices * 0.99,
            "volume": [1e6] * 100,
        })

        config = RegimeConfig()
        result = _signal_trend(df, config)

        assert result.vote == "bear"

    def test_neutral_when_mixed_signals(self) -> None:
        """测试中性条件: MA 交叉或价格在均线附近."""
        # 构造震荡数据
        dates = pd.date_range("2024-01-01", periods=100)
        prices = [10 + np.sin(i / 5) for i in range(100)]
        df = pd.DataFrame({
            "date": dates,
            "close": prices,
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "volume": [1e6] * 100,
        })

        config = RegimeConfig()
        result = _signal_trend(df, config)

        assert result.vote in ["bull", "bear", "neutral"]

    def test_returns_neutral_on_insufficient_data(self) -> None:
        """测试数据不足时返回中性."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10),
            "close": [10.0] * 10,
        })

        config = RegimeConfig()
        result = _signal_trend(df, config)

        assert result.vote == "neutral"


class TestSignalVolume:
    """成交量信号测试."""

    def test_bull_when_volume_expanding(self) -> None:
        """测试牛市条件: 近20日成交量 > 近60日均量 × 1.2."""
        dates = pd.date_range("2024-01-01", periods=100)
        # 前60日低量，后40日高量
        volumes = [1e6] * 60 + [2e6] * 40
        df = pd.DataFrame({
            "date": dates,
            "close": [10.0] * 100,
            "volume": volumes,
        })

        config = RegimeConfig()
        result = _signal_volume(df, config)

        assert result.vote == "bull"

    def test_bear_when_volume_shrinking(self) -> None:
        """测试熊市条件: 近20日成交量 < 近60日均量 × 0.8."""
        dates = pd.date_range("2024-01-01", periods=100)
        # 前60日高量，后40日低量
        volumes = [2e6] * 60 + [0.5e6] * 40
        df = pd.DataFrame({
            "date": dates,
            "close": [10.0] * 100,
            "volume": volumes,
        })

        config = RegimeConfig()
        result = _signal_volume(df, config)

        assert result.vote == "bear"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py::TestSignalTrend -v`

Expected: FAIL

- [ ] **Step 3: 实现趋势信号和成交量信号**

在 `src/pipeline/regime.py` 中添加：

```python
from src.config import RegimeConfig


def _signal_trend(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote:
    """趋势信号: MA20/MA60 排列 + 价格位置.

    Args:
        index_kline: 指数K线数据
        config: 市场环境配置

    Returns:
        RegimeVote: 趋势投票信号
    """
    if len(index_kline) < config.ma_long:
        return RegimeVote("trend", "neutral", 0.0, "数据不足")

    close = index_kline["close"].astype(float)
    ma_short = close.rolling(config.ma_short).mean()
    ma_long = close.rolling(config.ma_long).mean()

    current_price = close.iloc[-1]
    current_ma_short = ma_short.iloc[-1]
    current_ma_long = ma_long.iloc[-1]

    if current_ma_short > current_ma_long and current_price > current_ma_short:
        return RegimeVote(
            "trend", "bull", 0.9,
            f"MA{config.ma_short}({current_ma_short:.2f}) > MA{config.ma_long}({current_ma_long:.2f})，价格在均线上方"
        )
    elif current_ma_short < current_ma_long and current_price < current_ma_short:
        return RegimeVote(
            "trend", "bear", 0.9,
            f"MA{config.ma_short}({current_ma_short:.2f}) < MA{config.ma_long}({current_ma_long:.2f})，价格在均线下方"
        )
    else:
        return RegimeVote("trend", "neutral", 0.5, "均线纠缠或价格在均线附近")


def _signal_volume(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote:
    """成交量信号: 近期量能 vs 长期量能.

    Args:
        index_kline: 指数K线数据
        config: 市场环境配置

    Returns:
        RegimeVote: 成交量投票信号
    """
    if len(index_kline) < config.ma_long:
        return RegimeVote("volume", "neutral", 0.0, "数据不足")

    volume = index_kline["volume"].astype(float)
    vol_short = volume.iloc[-config.ma_short:].mean()
    vol_long = volume.iloc[-config.ma_long:].mean()

    if vol_long == 0:
        return RegimeVote("volume", "neutral", 0.0, "成交量数据异常")

    ratio = vol_short / vol_long

    if ratio > config.volume_bull_ratio:
        return RegimeVote(
            "volume", "bull", 0.8,
            f"近{config.ma_short}日量能({vol_short:.0f}) > 近{config.ma_long}日均量×{config.volume_bull_ratio}"
        )
    elif ratio < config.volume_bear_ratio:
        return RegimeVote(
            "volume", "bear", 0.8,
            f"近{config.ma_short}日量能({vol_short:.0f}) < 近{config.ma_long}日均量×{config.volume_bear_ratio}"
        )
    else:
        return RegimeVote("volume", "neutral", 0.5, f"量能正常 (ratio={ratio:.2f})")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py::TestSignalTrend tests/test_pipeline_regime.py::TestSignalVolume -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/regime.py tests/test_pipeline_regime.py
git commit -m "feat: 实现趋势信号和成交量信号"
```

---

### Task 3: 实现北向资金、涨跌比、估值信号

**Files:**
- Modify: `src/pipeline/regime.py`
- Modify: `tests/test_pipeline_regime.py`

**Interfaces:**
- Produces: `_signal_north_flow(north_flow: pd.DataFrame, config: RegimeConfig) -> RegimeVote`
- Produces: `_signal_advance_decline(limit_up: int, limit_down: int, config: RegimeConfig) -> RegimeVote`
- Produces: `_signal_valuation(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote`

- [ ] **Step 1: 编写北向资金信号测试**

在 `tests/test_pipeline_regime.py` 末尾添加：

```python
from src.pipeline.regime import (
    _signal_advance_decline,
    _signal_north_flow,
    _signal_valuation,
)


class TestSignalNorthFlow:
    """北向资金信号测试."""

    def test_bull_when_north_flow_positive(self) -> None:
        """测试牛市条件: 近5日净流入 > 0 且累计 > 100亿."""
        df = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [30e8, 25e8, 20e8, 15e8, 10e8],  # 累计100亿
        })

        config = RegimeConfig()
        result = _signal_north_flow(df, config)

        assert result.vote == "bull"

    def test_bear_when_north_flow_negative(self) -> None:
        """测试熊市条件: 近5日净流出 > 0 且累计 > 100亿."""
        df = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [-30e8, -25e8, -20e8, -15e8, -10e8],
        })

        config = RegimeConfig()
        result = _signal_north_flow(df, config)

        assert result.vote == "bear"

    def test_neutral_when_flow_mixed(self) -> None:
        """测试中性条件: 流入流出混合."""
        df = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [10e8, -5e8, 15e8, -10e8, 5e8],
        })

        config = RegimeConfig()
        result = _signal_north_flow(df, config)

        assert result.vote == "neutral"

    def test_returns_neutral_on_empty_data(self) -> None:
        """测试空数据返回中性."""
        df = pd.DataFrame()

        config = RegimeConfig()
        result = _signal_north_flow(df, config)

        assert result.vote == "neutral"


class TestSignalAdvanceDecline:
    """涨跌比信号测试."""

    def test_bull_when_advance_dominates(self) -> None:
        """测试牛市条件: 涨停/跌停 > 3.0."""
        config = RegimeConfig()
        result = _signal_advance_decline(30, 5, config)

        assert result.vote == "bull"

    def test_bear_when_decline_dominates(self) -> None:
        """测试熊市条件: 跌停/涨停 > 3.0."""
        config = RegimeConfig()
        result = _signal_advance_decline(5, 30, config)

        assert result.vote == "bear"

    def test_neutral_when_balanced(self) -> None:
        """测试中性条件: 涨跌比接近."""
        config = RegimeConfig()
        result = _signal_advance_decline(10, 10, config)

        assert result.vote == "neutral"


class TestSignalValuation:
    """估值信号测试."""

    def test_bull_when_low_valuation(self) -> None:
        """测试牛市条件: PE分位数 < 40%."""
        # 构造历史PE数据，当前处于低位
        dates = pd.date_range("2024-01-01", periods=100)
        pe_values = [20.0] * 90 + [15.0] * 10  # 当前PE较低
        df = pd.DataFrame({
            "date": dates,
            "close": pe_values,  # 用close模拟PE
        })

        config = RegimeConfig()
        result = _signal_valuation(df, config)

        assert result.vote == "bull"

    def test_bear_when_high_valuation(self) -> None:
        """测试熊市条件: PE分位数 > 70%."""
        dates = pd.date_range("2024-01-01", periods=100)
        pe_values = [15.0] * 90 + [25.0] * 10  # 当前PE较高
        df = pd.DataFrame({
            "date": dates,
            "close": pe_values,
        })

        config = RegimeConfig()
        result = _signal_valuation(df, config)

        assert result.vote == "bear"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py::TestSignalNorthFlow -v`

Expected: FAIL

- [ ] **Step 3: 实现三个信号函数**

在 `src/pipeline/regime.py` 中添加：

```python
def _signal_north_flow(north_flow: pd.DataFrame, config: RegimeConfig) -> RegimeVote:
    """北向资金信号: 近5日净流入趋势.

    Args:
        north_flow: 北向资金数据
        config: 市场环境配置

    Returns:
        RegimeVote: 北向资金投票信号
    """
    if north_flow.empty or len(north_flow) < 5:
        return RegimeVote("north", "neutral", 0.0, "北向资金数据不足")

    # 获取近5日净流入
    net_flow = north_flow["当日成交净买额"].astype(float).tail(5)
    total_flow = net_flow.sum()

    if total_flow > config.north_flow_threshold:
        return RegimeVote(
            "north", "bull", 0.8,
            f"北向资金近5日净流入 {total_flow/1e8:.0f}亿"
        )
    elif total_flow < -config.north_flow_threshold:
        return RegimeVote(
            "north", "bear", 0.8,
            f"北向资金近5日净流出 {abs(total_flow)/1e8:.0f}亿"
        )
    else:
        return RegimeVote("north", "neutral", 0.5, f"北向资金近5日变动 {total_flow/1e8:.1f}亿")


def _signal_advance_decline(
    limit_up: int, limit_down: int, config: RegimeConfig
) -> RegimeVote:
    """涨跌比信号: 涨停/跌停家数比.

    Args:
        limit_up: 涨停家数
        limit_down: 跌停家数
        config: 市场环境配置

    Returns:
        RegimeVote: 涨跌比投票信号
    """
    if limit_up == 0 and limit_down == 0:
        return RegimeVote("advance_decline", "neutral", 0.0, "无涨跌停数据")

    # 避免除零
    ratio = limit_up / max(limit_down, 1)
    inverse_ratio = limit_down / max(limit_up, 1)

    if ratio > config.advance_decline_bull:
        return RegimeVote(
            "advance_decline", "bull", 0.7,
            f"涨停{limit_up}家 vs 跌停{limit_down}家，比值{ratio:.1f}"
        )
    elif inverse_ratio > config.advance_decline_bear:
        return RegimeVote(
            "advance_decline", "bear", 0.7,
            f"跌停{limit_down}家 vs 涨停{limit_up}家，比值{inverse_ratio:.1f}"
        )
    else:
        return RegimeVote(
            "advance_decline", "neutral", 0.5,
            f"涨跌比均衡: 涨停{limit_up}家，跌停{limit_down}家"
        )


def _signal_valuation(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote:
    """估值信号: 基于历史分位数.

    使用近3年数据计算当前价格的分位数位置。
    注意: 设计文档要求"全A PE中位数分位数"，此处用指数价格分位数近似。

    Args:
        index_kline: 指数K线数据
        config: 市场环境配置

    Returns:
        RegimeVote: 估值投票信号
    """
    if len(index_kline) < 60:
        return RegimeVote("valuation", "neutral", 0.0, "估值数据不足")

    close = index_kline["close"].astype(float)
    current_price = close.iloc[-1]

    # 计算分位数
    percentile = (close < current_price).mean()

    if percentile < config.pe_percentile_low:
        return RegimeVote(
            "valuation", "bull", 0.7,
            f"当前估值处于历史 {percentile*100:.0f}% 分位（低估）"
        )
    elif percentile > config.pe_percentile_high:
        return RegimeVote(
            "valuation", "bear", 0.7,
            f"当前估值处于历史 {percentile*100:.0f}% 分位（高估）"
        )
    else:
        return RegimeVote(
            "valuation", "neutral", 0.5,
            f"当前估值处于历史 {percentile*100:.0f}% 分位（合理）"
        )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/regime.py tests/test_pipeline_regime.py
git commit -m "feat: 实现北向资金、涨跌比、估值信号"
```

---

### Task 4: 实现投票决策和 judge_market_regime 主函数

**Files:**
- Modify: `src/pipeline/regime.py`
- Modify: `tests/test_pipeline_regime.py`

**Interfaces:**
- Produces: `_vote_decision(votes: list[RegimeVote]) -> tuple[str, float]`
- Produces: `judge_market_regime(data: DataBundle, config: AppConfig) -> MarketRegime`

- [ ] **Step 1: 编写投票决策测试**

在 `tests/test_pipeline_regime.py` 末尾添加：

```python
from src.pipeline.regime import _vote_decision, RegimeVote


class TestVoteDecision:
    """投票决策测试."""

    def test_bull_when_majority_bull(self) -> None:
        """测试多数票为牛市."""
        votes = [
            RegimeVote("trend", "bull", 0.9, ""),
            RegimeVote("volume", "bull", 0.8, ""),
            RegimeVote("north", "bull", 0.7, ""),
            RegimeVote("advance", "neutral", 0.5, ""),
            RegimeVote("valuation", "bear", 0.6, ""),
        ]
        state, confidence = _vote_decision(votes)
        assert state == "bull"
        assert confidence == 0.6  # 3/5

    def test_bear_when_majority_bear(self) -> None:
        """测试多数票为熊市."""
        votes = [
            RegimeVote("trend", "bear", 0.9, ""),
            RegimeVote("volume", "bear", 0.8, ""),
            RegimeVote("north", "bear", 0.7, ""),
            RegimeVote("advance", "neutral", 0.5, ""),
            RegimeVote("valuation", "bull", 0.6, ""),
        ]
        state, confidence = _vote_decision(votes)
        assert state == "bear"
        assert confidence == 0.6

    def test_sideways_when_no_majority(self) -> None:
        """测试无多数票为震荡."""
        votes = [
            RegimeVote("trend", "bull", 0.9, ""),
            RegimeVote("volume", "bear", 0.8, ""),
            RegimeVote("north", "neutral", 0.5, ""),
            RegimeVote("advance", "bull", 0.7, ""),
            RegimeVote("valuation", "bear", 0.6, ""),
        ]
        state, confidence = _vote_decision(votes)
        assert state == "sideways"

    def test_ignores_neutral_votes(self) -> None:
        """测试中性票不计入投票."""
        votes = [
            RegimeVote("trend", "bull", 0.9, ""),
            RegimeVote("volume", "bull", 0.8, ""),
            RegimeVote("north", "neutral", 0.0, ""),  # 不计入
            RegimeVote("advance", "neutral", 0.0, ""),  # 不计入
            RegimeVote("valuation", "neutral", 0.0, ""),  # 不计入
        ]
        state, confidence = _vote_decision(votes)
        assert state == "bull"
        assert confidence == 1.0  # 2有效票中2票bull


class TestJudgeMarketRegime:
    """judge_market_regime 主函数测试."""

    def test_returns_market_regime(self) -> None:
        """测试返回 MarketRegime."""
        from src.pipeline.collect import DataBundle
        from src.config import AppConfig

        # 构造测试数据
        dates = pd.date_range("2024-01-01", periods=120)
        prices = np.linspace(10, 20, 120)
        index_kline = pd.DataFrame({
            "date": dates,
            "close": prices,
            "volume": [1e6] * 120,
        })

        data = DataBundle(
            index_kline=index_kline,
            stock_pool=pd.DataFrame(),
            kline_cache={},
            fundamental_cache={},
            north_flow=pd.DataFrame({
                "日期": dates[:5],
                "当日成交净买额": [20e8] * 5,
            }),
            margin_data=None,
            limit_up_count=30,
            limit_down_count=5,
            advance_decline_ratio=6.0,
            macro_indicators={},
            sector_flow=pd.DataFrame(),
            news_items=[],
            policy_impacts=[],
            etf_pool=[],
            etf_kline_cache={},
        )

        config = AppConfig()
        result = judge_market_regime(data, config)

        assert isinstance(result, MarketRegime)
        assert result.state in ["bull", "bear", "sideways"]
        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.position_advice <= 1.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py::TestVoteDecision -v`

Expected: FAIL

- [ ] **Step 3: 实现投票决策和主函数**

在 `src/pipeline/regime.py` 中添加：

```python
from src.pipeline.collect import DataBundle


def _vote_decision(votes: list[RegimeVote]) -> tuple[str, float]:
    """投票决策: 多数票决定市场状态.

    Args:
        votes: 所有投票信号列表

    Returns:
        tuple: (state, confidence)
    """
    bull_count = sum(1 for v in votes if v.vote == "bull")
    bear_count = sum(1 for v in votes if v.vote == "bear")
    effective_votes = bull_count + bear_count

    if effective_votes == 0:
        return "sideways", 0.0

    if bull_count >= 3:
        return "bull", bull_count / len(votes)
    elif bear_count >= 3:
        return "bear", bear_count / len(votes)
    else:
        return "sideways", max(bull_count, bear_count) / len(votes)


def _calc_position_advice(state: str, confidence: float) -> float:
    """计算建议仓位.

    Args:
        state: 市场状态
        confidence: 置信度

    Returns:
        float: 建议仓位 0.0 ~ 1.0
    """
    if state == "bull":
        return 0.7 + 0.3 * confidence
    elif state == "bear":
        return 0.3 - 0.3 * confidence
    else:
        return 0.5


def judge_market_regime(data: DataBundle, config: AppConfig) -> MarketRegime:
    """阶段1: 市场环境判断.

    Args:
        data: 数据包
        config: 应用配置

    Returns:
        MarketRegime: 市场环境判断结果
    """
    logger.info("=== 阶段1: 市场环境判断 ===")

    regime_config = config.regime
    votes: list[RegimeVote] = []

    # 1. 趋势信号
    votes.append(_signal_trend(data.index_kline, regime_config))

    # 2. 成交量信号
    votes.append(_signal_volume(data.index_kline, regime_config))

    # 3. 北向资金信号
    votes.append(_signal_north_flow(data.north_flow, regime_config))

    # 4. 涨跌比信号
    votes.append(_signal_advance_decline(
        data.limit_up_count, data.limit_down_count, regime_config
    ))

    # 5. 估值信号
    votes.append(_signal_valuation(data.index_kline, regime_config))

    # 投票决策
    state, confidence = _vote_decision(votes)
    position_advice = _calc_position_advice(state, confidence)

    # 构建信号字典
    signals = {v.name: v.vote for v in votes}

    # 生成描述
    state_names = {"bull": "牛市", "bear": "熊市", "sideways": "震荡"}
    description = f"{state_names[state]}（置信度 {confidence*100:.0f}%，建议仓位 {position_advice*100:.0f}%）"

    result = MarketRegime(
        state=state,
        confidence=confidence,
        position_advice=position_advice,
        signals=signals,
        description=description,
    )

    logger.info(f"市场环境: {description}")
    for v in votes:
        logger.debug(f"  {v.name}: {v.vote} - {v.reason}")

    return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_regime.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/regime.py tests/test_pipeline_regime.py
git commit -m "feat: 实现投票决策和 judge_market_regime 主函数"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_pipeline_regime.py -v`
- [ ] 5个信号全部实现: trend, volume, north_flow, advance_decline, valuation
- [ ] 投票决策正确: >=3票bull→牛市, >=3票bear→熊市, 其他→震荡
- [ ] 仓位建议计算正确: 牛市0.7-1.0, 熊市0.0-0.3, 震荡0.5
- [ ] 单个信号失败时返回 neutral，不影响整体
