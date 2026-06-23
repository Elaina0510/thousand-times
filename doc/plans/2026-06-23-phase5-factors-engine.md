# Phase 5: 多因子引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现多因子计算引擎 `pipeline/factors.py`，统一编排5个因子模块，输出每只股票的 FactorScores

**Architecture:** 遍历股票池，对每只股票调用5个因子模块，做截面百分位排名，按市场环境动态分配权重合成总分

**Tech Stack:** Python 3.10+, pandas, dataclasses

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 因子标准化使用截面百分位排名法，非Z-score
- 权重按市场环境（牛/熊/震荡）动态调整
- 单只股票因子计算失败 → 跳过该股票

## 文件结构

```
src/
└── pipeline/
    └── factors.py           ← 新建：多因子引擎

tests/
└── test_pipeline_factors.py ← 新建
```

---

### Task 1: 定义 FactorScores 数据结构和百分位排名工具

**Files:**
- Create: `src/pipeline/factors.py`
- Create: `tests/test_pipeline_factors.py`

**Interfaces:**
- Produces: `FactorScores` dataclass
- Produces: `percentile_to_0_100(values: pd.Series) -> pd.Series`
- Produces: `calc_factors(data: DataBundle, config: AppConfig, regime_state: str = "sideways") -> dict[str, FactorScores]`

- [ ] **Step 1: 编写 FactorScores 和百分位排名测试**

```python
# tests/test_pipeline_factors.py
"""测试 pipeline/factors.py 多因子引擎."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.pipeline.factors import (
    FactorScores,
    calc_factors,
    percentile_to_0_100,
)


class TestPercentileTo0100:
    """百分位排名标准化测试."""

    def test_maps_to_0_100(self) -> None:
        """映射到0-100范围."""
        values = pd.Series([10, 20, 30, 40, 50])
        result = percentile_to_0_100(values)
        assert result.min() == 0.0
        assert result.max() == 100.0

    def test_uniform_distribution(self) -> None:
        """产生均匀分布."""
        values = pd.Series(np.random.default_rng(42).normal(50, 20, 100))
        result = percentile_to_0_100(values)
        # 中位数应接近50
        assert 40 <= result.median() <= 60

    def test_higher_value_higher_percentile(self) -> None:
        """更高的值有更高的百分位排名."""
        values = pd.Series([1, 2, 3, 4, 5])
        result = percentile_to_0_100(values)
        assert result.iloc[-1] > result.iloc[0]

    def test_handles_ties(self) -> None:
        """处理相同值."""
        values = pd.Series([10, 10, 10, 10, 10])
        result = percentile_to_0_100(values)
        # 全部相同，排名应接近50
        assert abs(result.mean() - 50) < 20


class TestFactorScores:
    """FactorScores 数据结构测试."""

    def test_create(self) -> None:
        """创建 FactorScores."""
        scores = FactorScores(
            code="600519",
            name="贵州茅台",
            total_score=75.0,
            rank=1,
            technical_score=80.0,
            fundamental_score=70.0,
            capital_score=65.0,
            sentiment_score=60.0,
            momentum_score=85.0,
            technical_detail={"ma_trend": 90, "macd": 80, "volume": 70, "bollinger": 80},
            fundamental_detail={"valuation": 60, "profitability": 80, "growth": 70},
        )
        assert scores.code == "600519"
        assert scores.total_score == 75.0
        assert len(scores.technical_detail) == 4
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py -v`

Expected: FAIL

- [ ] **Step 3: 实现 FactorScores 和百分位排名**

```python
# src/pipeline/factors.py
"""多因子计算引擎.

遍历股票池，计算每只股票的因子分数，做截面排名，按权重合成总分。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.config import AppConfig
from src.pipeline.collect import DataBundle

logger = logging.getLogger("thousand-times")


@dataclass
class FactorScores:
    """单只股票的因子分数."""

    code: str
    name: str

    # 类别分数 (0-100)
    technical_score: float
    fundamental_score: float
    capital_score: float
    sentiment_score: float
    momentum_score: float

    # 子因子明细
    technical_detail: dict[str, float] = field(default_factory=dict)
    fundamental_detail: dict[str, float] = field(default_factory=dict)

    # 合成结果
    total_score: float = 0.0
    rank: int = 0


def percentile_to_0_100(values: pd.Series) -> pd.Series:
    """将因子值在股票池内做百分位排名，映射到 0-100.

    比 Z-score 更稳健，不受极端值影响。

    Args:
        values: 因子原始值序列

    Returns:
        pd.Series: 0-100 标准化分数
    """
    return values.rank(pct=True) * 100
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/factors.py tests/test_pipeline_factors.py
git commit -m "feat: 定义 FactorScores 和百分位排名工具"
```

---

### Task 2: 实现 calc_factors 主函数（核心编排逻辑）

**Files:**
- Modify: `src/pipeline/factors.py`
- Modify: `tests/test_pipeline_factors.py`

**Interfaces:**
- Produces: `calc_factors(data: DataBundle, config: AppConfig, regime_state: str = "sideways") -> dict[str, FactorScores]`

- [ ] **Step 1: 编写 calc_factors 集成测试**

在 `tests/test_pipeline_factors.py` 末尾添加：

```python
from unittest.mock import MagicMock, patch


class TestCalcFactors:
    """calc_factors 集成测试."""

    def _make_data_bundle(self, codes: list[str]) -> MagicMock:
        """构造测试用 DataBundle."""
        from src.pipeline.collect import DataBundle, FundamentalData

        kline_cache = {}
        fundamental_cache = {}
        rng = np.random.default_rng(42)

        for code in codes:
            dates = pd.date_range("2024-01-01", periods=120)
            prices = np.linspace(10, 10 + len(codes) * 2, 120) + rng.normal(0, 0.5, 120)
            kline_cache[code] = pd.DataFrame({
                "date": dates,
                "open": prices * 0.99,
                "high": prices * 1.02,
                "low": prices * 0.98,
                "close": prices,
                "volume": rng.uniform(1e6, 2e6, 120),
            })
            fundamental_cache[code] = FundamentalData(
                roe=rng.uniform(5, 25),
                eps=rng.uniform(0.5, 5),
                profit_growth=rng.uniform(-10, 30),
                revenue_growth=rng.uniform(-5, 25),
                pe_ttm=rng.uniform(10, 50),
                pb=rng.uniform(1, 5),
            )

        return DataBundle(
            index_kline=kline_cache[codes[0]],
            stock_pool=pd.DataFrame({
                "code": codes,
                "name": [f"Stock_{c}" for c in codes],
            }),
            kline_cache=kline_cache,
            fundamental_cache=fundamental_cache,
            north_flow=pd.DataFrame({
                "日期": pd.date_range("2024-01-01", periods=5),
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

    def test_returns_dict_of_factor_scores(self) -> None:
        """返回 FactorScores 字典."""
        data = self._make_data_bundle(["sh.600519", "sz.000858", "sh.600036"])
        config = AppConfig()

        result = calc_factors(data, config, regime_state="sideways")

        assert isinstance(result, dict)
        assert len(result) == 3
        for code, scores in result.items():
            assert isinstance(scores, FactorScores)
            assert scores.code == code
            assert 0 <= scores.total_score <= 100

    def test_ranks_are_assigned(self) -> None:
        """排名被正确分配."""
        data = self._make_data_bundle(["sh.600519", "sz.000858", "sh.600036"])
        config = AppConfig()

        result = calc_factors(data, config, regime_state="sideways")

        ranks = {s.rank for s in result.values()}
        assert len(ranks) == 3  # 所有排名唯一
        assert min(ranks) == 1
        assert max(ranks) == 3

    def test_empty_stock_pool_returns_empty_dict(self) -> None:
        """空股票池返回空字典."""
        data = self._make_data_bundle([])
        data.stock_pool = pd.DataFrame(columns=["code", "name"])
        config = AppConfig()

        result = calc_factors(data, config, regime_state="sideways")

        assert result == {}

    def test_skips_stocks_without_kline(self) -> None:
        """跳过无K线数据的股票."""
        data = self._make_data_bundle(["sh.600519", "sh.600036"])
        data.kline_cache = {}  # 模拟K线获取失败
        config = AppConfig()

        result = calc_factors(data, config, regime_state="sideways")

        assert len(result) == 0

    def test_weights_sum_to_100_percent(self) -> None:
        """百分位排名后的分数应在0-100范围内."""
        data = self._make_data_bundle(["sh.600519", "sz.000858"])
        config = AppConfig()

        result = calc_factors(data, config, regime_state="sideways")

        for scores in result.values():
            assert 0 <= scores.technical_score <= 100
            assert 0 <= scores.fundamental_score <= 100
            assert 0 <= scores.total_score <= 100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py::TestCalcFactors -v`

Expected: FAIL

- [ ] **Step 3: 实现 calc_factors**

在 `src/pipeline/factors.py` 中添加：

```python
from src.factors.technical import calc_technical_score
from src.factors.fundamental import calc_fundamental_score
from src.factors.capital import calc_capital_score
from src.factors.sentiment import calc_sentiment_score
from src.factors.momentum import calc_momentum_score


def _get_weights(regime_state: str, config: AppConfig) -> dict[str, float]:
    """根据市场环境获取因子权重.

    Args:
        regime_state: "bull" | "bear" | "sideways"
        config: 应用配置

    Returns:
        dict[str, float]: 各因子类别权重
    """
    weights_map = {
        "bull": config.factor_weights.bull,
        "bear": config.factor_weights.bear,
        "sideways": config.factor_weights.sideways,
    }
    return weights_map.get(regime_state, config.factor_weights.sideways)


def _combine_scores(
    code: str,
    name: str,
    technical: dict[str, float],
    fundamental: dict[str, float],
    capital: dict[str, float],
    sentiment: dict[str, float],
    momentum: dict[str, float],
    weights: dict[str, float],
) -> FactorScores:
    """合成各因子类别分数为总分.

    Args:
        code: 股票代码
        name: 股票名称
        technical: 技术面因子分数
        fundamental: 基本面因子分数
        capital: 资金面因子分数
        sentiment: 情绪面因子分数
        momentum: 动量因子分数
        weights: 各因子类别权重

    Returns:
        FactorScores: 合成结果
    """
    total = (
        technical["score"] * weights.get("technical", 0.20)
        + fundamental["score"] * weights.get("fundamental", 0.20)
        + capital["score"] * weights.get("capital", 0.15)
        + sentiment["score"] * weights.get("sentiment", 0.15)
        + momentum["score"] * weights.get("momentum", 0.20)
    )

    return FactorScores(
        code=code,
        name=name,
        technical_score=technical["score"],
        fundamental_score=fundamental["score"],
        capital_score=capital["score"],
        sentiment_score=sentiment["score"],
        momentum_score=momentum["score"],
        technical_detail={k: v for k, v in technical.items() if k != "score"},
        fundamental_detail={k: v for k, v in fundamental.items() if k != "score"},
        total_score=round(total),
    )


def calc_factors(
    data: DataBundle, config: AppConfig, regime_state: str = "sideways"
) -> dict[str, FactorScores]:
    """阶段3: 多因子计算.

    遍历股票池，对每只股票计算所有因子类别分数并合成。
    使用截面百分位排名法标准化因子分数。

    Args:
        data: 数据包
        config: 应用配置
        regime_state: 市场环境状态 ("bull" | "bear" | "sideways")

    Returns:
        dict[str, FactorScores]: 股票代码 -> 因子分数
    """
    logger.info("=== 阶段3: 多因子计算 ===")

    if data.stock_pool.empty:
        logger.warning("股票池为空，跳过因子计算")
        return {}

    # 根据市场环境确定权重
    weights = _get_weights(regime_state, config)

    # 第一轮：收集所有股票的原始因子分数
    raw_technical: dict[str, dict] = {}
    raw_fundamental: dict[str, dict] = {}
    raw_capital: dict[str, dict] = {}
    raw_sentiment: dict[str, dict] = {}
    raw_momentum: dict[str, dict] = {}

    for _, row in data.stock_pool.iterrows():
        code = row["code"]
        name = row.get("name", code)

        if code not in data.kline_cache or data.kline_cache[code].empty:
            logger.warning(f"{code} {name} 无K线数据，跳过")
            continue

        try:
            kline = data.kline_cache[code]
            fund_data = data.fundamental_cache.get(code)

            raw_technical[code] = calc_technical_score(kline)
            raw_fundamental[code] = calc_fundamental_score(fund_data) if fund_data else {
                "valuation": 50.0, "profitability": 50.0, "growth": 50.0, "score": 50.0
            }
            raw_capital[code] = calc_capital_score(code, data.north_flow)
            raw_sentiment[code] = calc_sentiment_score(
                data.limit_up_count, data.limit_down_count, data.policy_impacts
            )
            raw_momentum[code] = calc_momentum_score(code, data.kline_cache, data.etf_kline_cache)

        except Exception as e:
            logger.error(f"计算 {code} {name} 因子失败: {e}")
            continue

    if not raw_technical:
        logger.warning("无有效因子计算结果")
        return {}

    # 第二轮：截面百分位排名标准化
    codes = list(raw_technical.keys())

    # 将各类别分数转为 Series 做百分位排名
    technical_scores = pd.Series({c: raw_technical[c]["score"] for c in codes})
    fundamental_scores = pd.Series({c: raw_fundamental[c]["score"] for c in codes})
    capital_scores = pd.Series({c: raw_capital[c]["score"] for c in codes})
    sentiment_scores = pd.Series({c: raw_sentiment[c]["score"] for c in codes})
    momentum_scores = pd.Series({c: raw_momentum[c]["score"] for c in codes})

    # 百分位排名标准化
    tech_pct = percentile_to_0_100(technical_scores)
    fund_pct = percentile_to_0_100(fundamental_scores)
    cap_pct = percentile_to_0_100(capital_scores)
    sent_pct = percentile_to_0_100(sentiment_scores)
    mom_pct = percentile_to_0_100(momentum_scores)

    # 第三轮：合成 FactorScores
    raw_results: list[FactorScores] = []
    for code in codes:
        name = data.stock_pool[data.stock_pool["code"] == code]["name"].iloc[0] if len(data.stock_pool[data.stock_pool["code"] == code]) > 0 else code

        technical = raw_technical[code].copy()
        technical["score"] = tech_pct[code]
        fundamental = raw_fundamental[code].copy()
        fundamental["score"] = fund_pct[code]
        capital = raw_capital[code].copy()
        capital["score"] = cap_pct[code]
        sentiment = raw_sentiment[code].copy()
        sentiment["score"] = sent_pct[code]
        momentum = raw_momentum[code].copy()
        momentum["score"] = mom_pct[code]

        scores = _combine_scores(
            code, name, technical, fundamental,
            capital, sentiment, momentum, weights,
        )
        raw_results.append(scores)

    # 截面排名：按总分排序
    raw_results.sort(key=lambda x: x.total_score, reverse=True)
    for rank, scores in enumerate(raw_results, 1):
        scores.rank = rank

    result = {s.code: s for s in raw_results}

    logger.info(f"因子计算完成: {len(result)} 只股票 (环境: {regime_state})")
    return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/factors.py tests/test_pipeline_factors.py
git commit -m "feat: 实现 calc_factors 多因子计算引擎"
```

---

### Task 3: 实现因子有效性检验 (IC/IC_IR)

**Files:**
- Modify: `src/pipeline/factors.py`
- Modify: `tests/test_pipeline_factors.py`

**Interfaces:**
- Produces: `calc_ic(factor_values: pd.Series, future_returns: pd.Series) -> float`
- Produces: `calc_ic_ir(ic_series: pd.Series) -> float`

- [ ] **Step 1: 编写 IC 检验测试**

在 `tests/test_pipeline_factors.py` 末尾添加：

```python
from src.pipeline.factors import calc_ic, calc_ic_ir


class TestIC:
    """因子IC检验测试."""

    def test_perfect_correlation(self) -> None:
        """完全相关 IC=1."""
        a = pd.Series([1, 2, 3, 4, 5])
        b = pd.Series([1, 2, 3, 4, 5])
        result = calc_ic(a, b)
        assert abs(result - 1.0) < 1e-6

    def test_perfect_negative_correlation(self) -> None:
        """完全负相关 IC=-1."""
        a = pd.Series([1, 2, 3, 4, 5])
        b = pd.Series([5, 4, 3, 2, 1])
        result = calc_ic(a, b)
        assert abs(result + 1.0) < 1e-6

    def test_range_minus1_to_1(self) -> None:
        """IC 在 -1 到 1 范围内."""
        a = pd.Series(np.random.default_rng(42).normal(0, 1, 100))
        b = pd.Series(np.random.default_rng(43).normal(0, 1, 100))
        result = calc_ic(a, b)
        assert -1.0 <= result <= 1.0


class TestICIR:
    """IC_IR 测试."""

    def test_stable_positive_ic(self) -> None:
        """稳定正IC 有高 IC_IR."""
        ic_series = pd.Series([0.1] * 20)  # 完全稳定
        result = calc_ic_ir(ic_series)
        assert result > 0.5

    def test_volatile_ic(self) -> None:
        """波动IC 有低 IC_IR."""
        ic_series = pd.Series(np.random.default_rng(42).normal(0.1, 0.5, 100))
        result = calc_ic_ir(ic_series)
        assert result < 0.5

    def test_zero_variance_returns_inf(self) -> None:
        """零方差返回很大的值."""
        ic_series = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5])
        result = calc_ic_ir(ic_series)
        assert result > 100  # mean/std → 0.5/0 = large number
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py::TestIC -v`

Expected: FAIL

- [ ] **Step 3: 实现 IC 检验**

在 `src/pipeline/factors.py` 末尾添加：

```python
def calc_ic(factor_values: pd.Series, future_returns: pd.Series) -> float:
    """计算因子IC（Information Coefficient）= Spearman秩相关系数.

    IC 衡量因子对未来收益的预测能力。
    IC > 0 表示因子有正向预测能力，IC ≈ 0 表示无效。

    Args:
        factor_values: 因子值序列
        future_returns: 未来收益率序列

    Returns:
        float: IC 值，范围 -1.0 ~ 1.0
    """
    return float(factor_values.corr(future_returns, method="spearman"))


def calc_ic_ir(ic_series: pd.Series) -> float:
    """计算 IC_IR = mean(IC) / std(IC).

    衡量因子预测能力的稳定性。IC_IR > 0.5 有效，< 0.2 无效。

    Args:
        ic_series: 各期 IC 值序列

    Returns:
        float: IC_IR 值
    """
    return float(ic_series.mean() / max(ic_series.std(), 1e-8))
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_factors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/factors.py tests/test_pipeline_factors.py
git commit -m "feat: 实现因子IC/IC_IR检验函数"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_pipeline_factors.py -v`
- [ ] FactorScores 包含所有字段 (technical_score, fundamental_score, ...)
- [ ] 百分位排名正确: 最高因子值→100分，最低→0分
- [ ] 权重按配置选择: bull/bear/sideways 三套权重
- [ ] 单只股票失败不影响其他: 跳过即可，不抛异常
- [ ] IC/IC_IR 计算正确
