# Phase 6: 信号生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现信号生成模块 `pipeline/signal.py`，用5票投票制替代单一阈值判断，附带关键价位计算

**Architecture:** 5个独立信号各自投票（buy/sell/neutral），多数票决定最终操作方向。支持位/压力位/目标价/止损价基于ATR波动率计算

**Tech Stack:** Python 3.10+, pandas, numpy, dataclasses

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 信号生成使用投票制，非单一阈值
- 盈亏比 >= 2:1 才视为有效买入信号
- 默认不产生信号（保守策略）

## 文件结构

```
src/
└── pipeline/
    └── signal.py             ← 新建：信号生成

tests/
└── test_pipeline_signal.py   ← 新建
```

---

### Task 1: 定义信号数据结构

**Files:**
- Create: `src/pipeline/signal.py`
- Create: `tests/test_pipeline_signal.py`

**Interfaces:**
- Produces: `SignalVote`, `KeyPrices`, `Signal` dataclasses
- Produces: `generate_signals(scores: dict, data: DataBundle, config: AppConfig) -> list[Signal]`

- [ ] **Step 1: 编写数据结构测试**

```python
# tests/test_pipeline_signal.py
"""测试 pipeline/signal.py 信号生成模块."""
from __future__ import annotations

from src.pipeline.signal import KeyPrices, Signal, SignalVote
from src.pipeline.factors import FactorScores


class TestKeyPrices:
    """KeyPrices 测试."""

    def test_create(self) -> None:
        kp = KeyPrices(
            current_price=10.0,
            support=9.0,
            resistance=11.5,
            target_price=11.0,
            stop_loss=9.2,
            risk_reward_ratio=2.5,
        )
        assert kp.risk_reward_ratio == 2.5


class TestSignalVote:
    """SignalVote 测试."""

    def test_create_buy_vote(self) -> None:
        vote = SignalVote(name="factor", vote="buy", confidence=0.8, reason="因子分>=70")
        assert vote.vote == "buy"


class TestSignal:
    """Signal 测试."""

    def test_create_buy_signal(self) -> None:
        fs = FactorScores(
            code="600519", name="茅台",
            technical_score=80, fundamental_score=70,
            capital_score=65, sentiment_score=60, momentum_score=85,
            total_score=75, rank=1,
        )
        kp = KeyPrices(10.0, 9.0, 11.5, 11.0, 9.2, 2.5)
        votes = [
            SignalVote("factor", "buy", 0.8, ""),
            SignalVote("technical", "buy", 0.9, ""),
            SignalVote("momentum", "buy", 0.7, ""),
        ]
        signal = Signal(
            code="600519", name="茅台", is_etf=False,
            action="buy", confidence=0.6, votes=votes,
            key_prices=kp, factor_scores=fs,
            reason_summary="3/5票买入",
        )
        assert signal.action == "buy"
        assert signal.confidence == 0.6
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py -v`

Expected: FAIL

- [ ] **Step 3: 实现数据结构**

```python
# src/pipeline/signal.py
"""信号生成模块.

使用5票投票制生成买卖信号，计算关键价位。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import AppConfig
from src.pipeline.collect import DataBundle
from src.pipeline.factors import FactorScores

logger = logging.getLogger("thousand-times")


@dataclass
class SignalVote:
    """交易信号投票.

    注意: 与 pipeline/regime.py 的 RegimeVote 区分。
    """

    name: str           # 信号名称
    vote: str           # "buy" | "sell" | "neutral"
    confidence: float   # 0.0 ~ 1.0
    reason: str         # 投票理由


@dataclass
class KeyPrices:
    """关键价位."""

    current_price: float
    support: float          # 支撑位
    resistance: float       # 压力位
    target_price: float     # 目标价
    stop_loss: float        # 止损价
    risk_reward_ratio: float  # 盈亏比


@dataclass
class Signal:
    """交易信号."""

    code: str
    name: str
    is_etf: bool
    action: str             # "buy" | "sell" | "hold"
    confidence: float       # 0.0 ~ 1.0
    votes: list[SignalVote]
    key_prices: KeyPrices
    factor_scores: FactorScores
    reason_summary: str
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/signal.py tests/test_pipeline_signal.py
git commit -m "feat: 定义信号生成数据结构"
```

---

### Task 2: 实现5个投票信号

**Files:**
- Modify: `src/pipeline/signal.py`
- Modify: `tests/test_pipeline_signal.py`

**Interfaces:**
- Produces: 5个 `_vote_*` 函数，每个返回 SignalVote

- [ ] **Step 1: 编写投票信号测试**

在 `tests/test_pipeline_signal.py` 末尾添加：

```python
from unittest.mock import MagicMock, patch

import pandas as pd

from src.pipeline.signal import (
    _vote_factor,
    _vote_momentum,
    _vote_technical,
    _vote_regime,
    SignalVote,
)
from src.config import AppConfig, SignalConfig


class TestVoteFactor:
    """因子综合投票测试."""

    def test_buy_when_score_high(self) -> None:
        fs = FactorScores("code", "name", 80, 70, 65, 60, 85, total_score=75)
        config = SignalConfig()
        result = _vote_factor(fs, config)
        assert result.vote == "buy"

    def test_sell_when_score_low(self) -> None:
        fs = FactorScores("code", "name", 20, 15, 10, 25, 30, total_score=25)
        config = SignalConfig()
        result = _vote_factor(fs, config)
        assert result.vote == "sell"

    def test_neutral_when_score_mid(self) -> None:
        fs = FactorScores("code", "name", 50, 50, 50, 50, 50, total_score=55)
        config = SignalConfig()
        result = _vote_factor(fs, config)
        assert result.vote == "neutral"


class TestVoteTechnical:
    """技术面投票测试."""

    def test_buy_when_technical_high(self) -> None:
        fs = FactorScores("code", "name", 80, 50, 50, 50, 50, total_score=60)
        config = SignalConfig()
        result = _vote_technical(fs, config)
        assert result.vote == "buy"

    def test_sell_when_technical_low(self) -> None:
        fs = FactorScores("code", "name", 20, 50, 50, 50, 50, total_score=40)
        config = SignalConfig()
        result = _vote_technical(fs, config)
        assert result.vote == "sell"


class TestVoteMomentum:
    """动量投票测试."""

    def test_buy_when_momentum_positive(self) -> None:
        fs = FactorScores("code", "name", 50, 50, 50, 50, 80, total_score=60)
        config = SignalConfig()
        result = _vote_momentum(fs, config)
        assert result.vote == "buy"

    def test_sell_when_momentum_negative(self) -> None:
        fs = FactorScores("code", "name", 50, 50, 50, 50, 15, total_score=40)
        config = SignalConfig()
        result = _vote_momentum(fs, config)
        assert result.vote == "sell"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py::TestVoteFactor -v`

Expected: FAIL

- [ ] **Step 3: 实现5个投票信号**

在 `src/pipeline/signal.py` 中添加：

```python
from src.config import SignalConfig


def _vote_factor(scores: FactorScores, config: SignalConfig) -> SignalVote:
    """因子综合投票."""
    if scores.total_score >= config.factor_buy_threshold:
        return SignalVote("factor", "buy", 0.8,
                          f"因子总分{scores.total_score:.0f} >= {config.factor_buy_threshold}")
    elif scores.total_score <= config.factor_sell_threshold:
        return SignalVote("factor", "sell", 0.8,
                          f"因子总分{scores.total_score:.0f} <= {config.factor_sell_threshold}")
    return SignalVote("factor", "neutral", 0.5, "因子总分在中间区域")


def _vote_technical(scores: FactorScores, config: SignalConfig) -> SignalVote:
    """技术面投票（含趋势判断）."""
    if scores.technical_score >= config.technical_buy_threshold:
        return SignalVote("technical", "buy", 0.7,
                          f"技术面{scores.technical_score:.0f} >= {config.technical_buy_threshold}")
    elif scores.technical_score <= config.technical_sell_threshold:
        return SignalVote("technical", "sell", 0.7,
                          f"技术面{scores.technical_score:.0f} <= {config.technical_sell_threshold}")
    return SignalVote("technical", "neutral", 0.5, "技术面中性")


def _vote_capital(scores: FactorScores, config: SignalConfig) -> SignalVote:
    """资金面投票."""
    if scores.capital_score >= 70:
        return SignalVote("capital", "buy", 0.6, f"资金面{scores.capital_score:.0f}强势")
    elif scores.capital_score <= 30:
        return SignalVote("capital", "sell", 0.6, f"资金面{scores.capital_score:.0f}弱势")
    return SignalVote("capital", "neutral", 0.5, "资金面中性")


def _vote_momentum(scores: FactorScores, config: SignalConfig) -> SignalVote:
    """动量投票."""
    if scores.momentum_score >= 70:
        return SignalVote("momentum", "buy", 0.7,
                          f"动量{scores.momentum_score:.0f}强势")
    elif scores.momentum_score <= 30:
        return SignalVote("momentum", "sell", 0.7,
                          f"动量{scores.momentum_score:.0f}弱势")
    return SignalVote("momentum", "neutral", 0.5, "动量中性")


def _vote_regime(
    scores: FactorScores, regime_state: str, config: SignalConfig
) -> SignalVote:
    """市场环境投票."""
    if regime_state == "bull" and scores.momentum_score > 50:
        return SignalVote("regime", "buy", 0.6, "牛市加持")
    elif regime_state == "bear" and scores.momentum_score < 50:
        return SignalVote("regime", "sell", 0.6, "熊市压力")
    return SignalVote("regime", "neutral", 0.5, "环境中性")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/signal.py tests/test_pipeline_signal.py
git commit -m "feat: 实现5个投票信号函数"
```

---

### Task 3: 实现关键价位计算

**Files:**
- Modify: `src/pipeline/signal.py`
- Modify: `tests/test_pipeline_signal.py`

**Interfaces:**
- Produces: `calc_key_prices(kline: pd.DataFrame, config: SignalConfig) -> KeyPrices`

- [ ] **Step 1: 编写关键价位测试**

在 `tests/test_pipeline_signal.py` 末尾添加：

```python
from src.pipeline.signal import calc_key_prices


class TestCalcKeyPrices:
    """关键价位计算测试."""

    def _make_kline(self, prices: list[float]) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=len(prices))
        return pd.DataFrame({
            "date": dates,
            "open": [p * 0.99 for p in prices],
            "high": [p * 1.03 for p in prices],
            "low": [p * 0.97 for p in prices],
            "close": prices,
            "volume": [1e6] * len(prices),
        })

    def test_returns_key_prices(self) -> None:
        """返回 KeyPrices."""
        kline = self._make_kline([10.0] * 30)
        config = SignalConfig()
        result = calc_key_prices(kline, config)
        assert isinstance(result, KeyPrices)
        assert result.current_price == 10.0

    def test_risk_reward_positive(self) -> None:
        """盈亏比为正."""
        kline = self._make_kline([10.0] * 30)
        config = SignalConfig()
        result = calc_key_prices(kline, config)
        assert result.risk_reward_ratio > 0

    def test_support_below_current(self) -> None:
        """支撑位低于当前价."""
        prices = list(range(10, 15)) + [15.0] * 40
        kline = self._make_kline(prices)
        config = SignalConfig()
        result = calc_key_prices(kline, config)
        assert result.support <= result.current_price

    def test_resistance_above_current(self) -> None:
        """压力位高于当前价."""
        prices = list(range(5, 15)) + [15.0] * 40
        kline = self._make_kline(prices)
        config = SignalConfig()
        result = calc_key_prices(kline, config)
        assert result.resistance >= result.current_price
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py::TestCalcKeyPrices -v`

Expected: FAIL

- [ ] **Step 3: 实现关键价位计算**

在 `src/pipeline/signal.py` 中添加：

```python
def calc_key_prices(kline: pd.DataFrame, config: SignalConfig) -> KeyPrices:
    """计算关键价位：支撑/压力/目标/止损.

    基于 ATR（平均真实波幅）计算波动率驱动的价位。

    Args:
        kline: K线数据
        config: 信号配置

    Returns:
        KeyPrices: 关键价位
    """
    if kline.empty or "close" not in kline.columns:
        return KeyPrices(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    close = kline["close"].astype(float)
    current = close.iloc[-1]

    # 计算 ATR
    high = kline.get("high", close)
    low = kline.get("low", close)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1] if len(tr) >= 14 else current * 0.02

    # 支撑位：MA20、20日低点、布林下轨的中位数
    ma20 = close.rolling(20).mean().iloc[-1]
    low_20 = close.iloc[-20:].min()
    std = close.rolling(20).std().iloc[-1]
    boll_lower = ma20 - 2 * std
    support = float(np.median([ma20, low_20, boll_lower]))

    # 压力位：MA20、20日高点、布林上轨的中位数
    high_20 = close.iloc[-20:].max()
    boll_upper = ma20 + 2 * std
    resistance = float(np.median([ma20, high_20, boll_upper]))

    # 目标价和止损价
    target = current + atr * config.atr_target_multiplier
    stop_loss = current - atr * config.atr_stop_multiplier

    # 盈亏比
    potential_gain = target - current
    potential_loss = current - stop_loss
    rr_ratio = potential_gain / max(potential_loss, 1e-8)

    return KeyPrices(
        current_price=round(current, 2),
        support=round(support, 2),
        resistance=round(resistance, 2),
        target_price=round(target, 2),
        stop_loss=round(stop_loss, 2),
        risk_reward_ratio=round(rr_ratio, 2),
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/signal.py tests/test_pipeline_signal.py
git commit -m "feat: 实现基于ATR的关键价位计算"
```

---

### Task 4: 实现 generate_signals 主函数

**Files:**
- Modify: `src/pipeline/signal.py`
- Modify: `tests/test_pipeline_signal.py`

**Interfaces:**
- Produces: `generate_signals(scores: dict, data: DataBundle, config: AppConfig, regime_state: str = "sideways") -> list[Signal]`

- [ ] **Step 1: 编写 generate_signals 测试**

在 `tests/test_pipeline_signal.py` 末尾添加：

```python
from src.pipeline.signal import generate_signals


class TestGenerateSignals:
    """generate_signals 主函数测试."""

    def _make_scores(self, code: str, total: float, technical: float = 50,
                     momentum: float = 50) -> FactorScores:
        return FactorScores(
            code=code, name=f"stock_{code}",
            technical_score=technical, fundamental_score=50,
            capital_score=50, sentiment_score=50, momentum_score=momentum,
            total_score=total, rank=1,
        )

    def test_returns_buy_signal_for_high_scorer(self) -> None:
        """高分股票返回买入信号."""
        scores = {
            "sh.600519": self._make_scores("sh.600519", total=85, technical=80, momentum=80),
        }
        dates = pd.date_range("2024-01-01", periods=30)
        data = DataBundle(
            index_kline=pd.DataFrame(),
            stock_pool=pd.DataFrame(),
            kline_cache={
                "sh.600519": pd.DataFrame({
                    "date": dates, "open": [10]*30, "high": [10.5]*30,
                    "low": [9.5]*30, "close": [10]*30, "volume": [1e6]*30,
                }),
            },
            fundamental_cache={},
            north_flow=pd.DataFrame(),
            margin_data=None, limit_up_count=0, limit_down_count=0,
            advance_decline_ratio=1.0, macro_indicators={},
            sector_flow=pd.DataFrame(), news_items=[], policy_impacts=[],
            etf_pool=[], etf_kline_cache={},
        )
        config = AppConfig()

        result = generate_signals(scores, data, config)

        assert len(result) > 0
        assert result[0].action in ["buy", "sell", "hold"]

    def test_returns_empty_for_no_scores(self) -> None:
        """无分数返回空列表."""
        data = DataBundle(
            index_kline=pd.DataFrame(), stock_pool=pd.DataFrame(),
            kline_cache={}, fundamental_cache={},
            north_flow=pd.DataFrame(), margin_data=None,
            limit_up_count=0, limit_down_count=0, advance_decline_ratio=1.0,
            macro_indicators={}, sector_flow=pd.DataFrame(),
            news_items=[], policy_impacts=[], etf_pool=[], etf_kline_cache={},
        )
        config = AppConfig()

        result = generate_signals({}, data, config)

        assert result == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py::TestGenerateSignals -v`

Expected: FAIL

- [ ] **Step 3: 实现 generate_signals**

在 `src/pipeline/signal.py` 末尾添加：

```python
def _decide_action(votes: list[SignalVote], config: SignalConfig) -> tuple[str, float]:
    """根据投票决定最终操作.

    Args:
        votes: 所有投票信号
        config: 信号配置

    Returns:
        tuple[str, float]: (action, confidence)
    """
    buy_count = sum(1 for v in votes if v.vote == "buy")
    sell_count = sum(1 for v in votes if v.vote == "sell")
    total = len(votes)

    if buy_count >= config.min_buy_votes and sell_count <= 1:
        return "buy", float(buy_count) / total
    elif sell_count >= config.min_sell_votes and buy_count <= 1:
        return "sell", float(sell_count) / total
    else:
        return "hold", 0.5


def generate_signals(
    scores: dict[str, FactorScores],
    data: DataBundle,
    config: AppConfig,
    regime_state: str = "sideways",
) -> list[Signal]:
    """阶段4: 信号生成.

    Args:
        scores: 股票代码 -> FactorScores
        data: 数据包
        config: 应用配置
        regime_state: 市场环境（用于环境投票）

    Returns:
        list[Signal]: 信号列表
    """
    logger.info("=== 阶段4: 信号生成 ===")

    signal_config = config.signal
    signals: list[Signal] = []

    for code, fs in scores.items():
        # 获取K线
        kline = data.kline_cache.get(code, pd.DataFrame())

        # 5票投票
        votes: list[SignalVote] = [
            _vote_factor(fs, signal_config),
            _vote_technical(fs, signal_config),
            _vote_capital(fs, signal_config),
            _vote_momentum(fs, signal_config),
            _vote_regime(fs, regime_state, signal_config),
        ]

        # 决策
        action, confidence = _decide_action(votes, signal_config)

        # 计算关键价位
        key_prices = calc_key_prices(kline, signal_config)

        # 盈亏比过滤
        if action == "buy" and key_prices.risk_reward_ratio < signal_config.min_risk_reward:
            logger.debug(f"{code} {fs.name} 盈亏比{key_prices.risk_reward_ratio:.1f}不足，降级为hold")
            action = "hold"

        # 构建信号
        vote_reasons = [f"{v.name}:{v.vote}" for v in votes]
        reason_summary = f"{action} ({confidence*100:.0f}%) [{' '.join(vote_reasons)}]"

        signal = Signal(
            code=code,
            name=fs.name,
            is_etf=False,
            action=action,
            confidence=confidence,
            votes=votes,
            key_prices=key_prices,
            factor_scores=fs,
            reason_summary=reason_summary,
        )
        signals.append(signal)

    # 按置信度排序
    signals.sort(key=lambda x: x.confidence, reverse=True)

    buy_count = sum(1 for s in signals if s.action == "buy")
    sell_count = sum(1 for s in signals if s.action == "sell")
    logger.info(f"信号生成完成: {buy_count} 买入, {sell_count} 卖出, {len(signals)} 总")

    return signals
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_signal.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/signal.py tests/test_pipeline_signal.py
git commit -m "feat: 实现 generate_signals 信号生成主函数"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_pipeline_signal.py -v`
- [ ] 5票投票制: >=3 buy且<=1 sell → 买入信号
- [ ] 盈亏比过滤: < 2:1 的买入信号降级为hold
- [ ] 支撑位/压力位基于20日数据计算
- [ ] ATR目标价和止损价计算正确
- [ ] 信号按置信度排序
