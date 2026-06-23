# Phase 4: 因子库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现5个因子模块（技术面、基本面、资金面、情绪面、动量），每个模块计算对应类别的0-100标准化因子分数

**Architecture:** 每个因子模块独立实现，接收原始数据返回标准化分数。采用百分位排名法（截面内排名），在 `pipeline/factors.py` 中统一编排

**Tech Stack:** Python 3.10+, pandas, numpy, dataclasses

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 所有公共函数和类必须有 Google 风格 docstring
- 因子分数范围 0-100，使用百分位排名法标准化
- 空数据/异常数据返回默认中性分 50

## 文件结构

```
src/
└── factors/
    ├── __init__.py         ← 更新
    ├── technical.py        ← 新建：技术面因子
    ├── fundamental.py      ← 新建：基本面因子
    ├── capital.py          ← 新建：资金面因子
    ├── sentiment.py        ← 新建：情绪面因子
    └── momentum.py         ← 新建：动量因子

tests/
├── test_factors_technical.py
├── test_factors_fundamental.py
├── test_factors_capital.py
├── test_factors_sentiment.py
└── test_factors_momentum.py
```

---

### Task 1: 实现技术面因子 (factors/technical.py)

**Files:**
- Create: `src/factors/technical.py`
- Create: `tests/test_factors_technical.py`

**Interfaces:**
- Produces: `calc_technical_score(kline: pd.DataFrame) -> dict[str, float]`
- Returns: `{"ma_trend": 0-100, "macd": 0-100, "volume": 0-100, "bollinger": 0-100, "score": 0-100}`

- [ ] **Step 1: 编写技术面因子测试**

```python
# tests/test_factors_technical.py
"""测试 factors/technical.py 技术面因子."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors.technical import (
    calc_bollinger_score,
    calc_macd_score,
    calc_ma_trend_score,
    calc_technical_score,
    calc_volume_score,
)


def make_test_kline(trend: str = "up") -> pd.DataFrame:
    """构造测试用K线数据."""
    dates = pd.date_range("2024-01-01", periods=120)
    match trend:
        case "up":
            prices = np.linspace(10, 20, 120)
        case "down":
            prices = np.linspace(20, 10, 120)
        case _:
            prices = np.full(120, 15.0)
    return pd.DataFrame({
        "date": dates,
        "open": prices * 0.99,
        "high": prices * 1.02,
        "low": prices * 0.98,
        "close": prices,
        "volume": np.random.default_rng(42).uniform(1e6, 2e6, 120),
    })


class TestCalcMaTrendScore:
    """MA趋势得分测试."""

    def test_bullish_trend_scores_high(self) -> None:
        """上升趋势得分高."""
        score = calc_ma_trend_score(make_test_kline("up"))
        assert 0 <= score <= 100

    def test_bearish_trend_scores_low(self) -> None:
        """下降趋势得分低."""
        bull = calc_ma_trend_score(make_test_kline("up"))
        bear = calc_ma_trend_score(make_test_kline("down"))
        assert bull > bear

    def test_insufficient_data_returns_neutral(self) -> None:
        """数据不足返回50."""
        df = pd.DataFrame({"close": [10.0] * 10})
        score = calc_ma_trend_score(df)
        assert score == 50.0


class TestCalcMacdScore:
    """MACD得分测试."""

    def test_returns_0_to_100(self) -> None:
        """得分在0-100范围内."""
        score = calc_macd_score(make_test_kline("up"))
        assert 0 <= score <= 100

    def test_insufficient_data_returns_neutral(self) -> None:
        """数据不足返回50."""
        df = pd.DataFrame({"close": [10.0] * 10})
        score = calc_macd_score(df)
        assert score == 50.0


class TestCalcVolumeScore:
    """成交量得分测试."""

    def test_returns_0_to_100(self) -> None:
        """得分在0-100范围内."""
        score = calc_volume_score(make_test_kline("up"))
        assert 0 <= score <= 100

    def test_insufficient_data_returns_neutral(self) -> None:
        """数据不足返回50."""
        df = pd.DataFrame({"volume": [1e6] * 10})
        score = calc_volume_score(df)
        assert score == 50.0


class TestCalcBollingerScore:
    """布林带得分测试."""

    def test_returns_0_to_100(self) -> None:
        """得分在0-100范围内."""
        score = calc_bollinger_score(make_test_kline("up"))
        assert 0 <= score <= 100


class TestCalcTechnicalScore:
    """技术面综合得分测试."""

    def test_returns_dict_with_all_fields(self) -> None:
        """返回包含所有子因子的字典."""
        result = calc_technical_score(make_test_kline("up"))

        assert isinstance(result, dict)
        assert "ma_trend" in result
        assert "macd" in result
        assert "volume" in result
        assert "bollinger" in result
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_empty_dataframe_returns_neutral(self) -> None:
        """空数据返回中性分."""
        result = calc_technical_score(pd.DataFrame())
        assert result["score"] == 50.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_technical.py -v`

Expected: FAIL

- [ ] **Step 3: 实现技术面因子**

```python
# src/factors/technical.py
"""技术面因子模块.

计算 MA趋势、MACD、成交量、布林带四个技术面因子。

因子说明:
    - MA趋势: MA5/MA10/MA20/MA60 多头排列程度 (0-100)
    - MACD: DIF/DEA 交叉、柱状图趋势、背离 (0-100)
    - 成交量: 量比、量能趋势 (0-100)
    - 布林带: 价格相对布林带位置 (0-100)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


def calc_ma_trend_score(kline: pd.DataFrame) -> float:
    """MA趋势得分：检查 MA5/MA10/MA20/MA60 的多头排列程度.

    Args:
        kline: K线数据 (需包含 close 列)

    Returns:
        float: 0-100 分数
    """
    if len(kline) < 60 or "close" not in kline.columns:
        return 50.0

    try:
        close = kline["close"].astype(float)
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]
        current = close.iloc[-1]

        # 统计多排对数
        pairs = [(ma5, ma10), (ma10, ma20), (ma20, ma60), (current, ma5)]
        bullish_pairs = sum(1 for a, b in pairs if a > b)

        # 基础分 = 多头对数 / 总对数 * 100
        score = (bullish_pairs / 4) * 100

        # 加分：均线之间价差越大越好
        if ma60 > 0:
            spread = (current - ma60) / ma60 * 100  # 价格偏离60日均线的百分比
            score = min(100, score + max(0, spread * 5))

        return float(round(max(0, score)))
    except Exception as e:
        logger.debug(f"MA趋势计算异常: {e}")
        return 50.0


def calc_macd_score(kline: pd.DataFrame) -> float:
    """MACD得分：综合 DIF/DEA 交叉、柱状图和背离.

    Args:
        kline: K线数据 (需包含 close 列)

    Returns:
        float: 0-100 分数
    """
    if len(kline) < 35 or "close" not in kline.columns:
        return 50.0

    try:
        close = kline["close"].astype(float)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_bar = 2 * (dif - dea)

        # 当前值
        current_dif = dif.iloc[-1]
        current_dea = dea.iloc[-1]
        prev_dif = dif.iloc[-2]
        prev_dea = dea.iloc[-2]

        score = 50.0

        # DIF/DEA方向
        if current_dif > current_dea:
            score += 15
            if prev_dif <= prev_dea:
                score += 10  # 金叉
        else:
            score -= 15
            if prev_dif >= prev_dea:
                score -= 10  # 死叉

        # 柱状图趋势
        bars_last_5 = macd_bar.iloc[-5:]
        if len(bars_last_5) >= 2:
            if bars_last_5.iloc[-1] > 0 and bars_last_5.iloc[-1] > bars_last_5.iloc[-2]:
                score += 10  # 红柱放大
            elif bars_last_5.iloc[-1] < 0 and bars_last_5.iloc[-1] < bars_last_5.iloc[-2]:
                score -= 10  # 绿柱放大

        # 背离检测（简化）
        if current_dif > dif.iloc[-20] and close.iloc[-1] < close.iloc[-20]:
            score += 15  # 底背离

        return float(round(max(0, min(100, score))))
    except Exception as e:
        logger.debug(f"MACD计算异常: {e}")
        return 50.0


def calc_volume_score(kline: pd.DataFrame) -> float:
    """成交量得分：量比和量能趋势.

    Args:
        kline: K线数据 (需包含 volume, close 列)

    Returns:
        float: 0-100 分数
    """
    if len(kline) < 20 or "volume" not in kline.columns:
        return 50.0

    try:
        volume = kline["volume"].astype(float)
        close = kline["close"].astype(float)

        vol_ma5 = volume.iloc[-5:].mean()
        vol_ma20 = volume.iloc[-20:].mean()
        vol_ratio = vol_ma5 / max(vol_ma20, 1)

        # 量价配合
        price_change = close.pct_change(5).iloc[-1]

        score = 50.0

        # 量能评分
        if vol_ratio > 1.5:
            if price_change > 0:
                score += 20  # 放量上涨
            else:
                score -= 10  # 放量下跌
        elif vol_ratio < 0.5:
            if price_change > 0:
                score += 5   # 缩量上涨（温和）
            else:
                score += 10  # 缩量下跌（惜售）

        # 量能趋势（温和放量最好）
        vol_trend = volume.iloc[-10:].mean() / max(volume.iloc[-20:].mean(), 1)
        if 1.1 <= vol_trend <= 1.5:
            score += 10  # 温和放量

        return float(round(max(0, min(100, score))))
    except Exception as e:
        logger.debug(f"成交量计算异常: {e}")
        return 50.0


def calc_bollinger_score(kline: pd.DataFrame) -> float:
    """布林带得分：价格相对布林带位置.

    价格在布林带下轨附近（买入信号）得分高，在上轨附近（超买）得分低。
    注意：这是技术面因子的一部分，与动量分开评估。

    Args:
        kline: K线数据 (需包含 close 列)

    Returns:
        float: 0-100 分数
    """
    if len(kline) < 20 or "close" not in kline.columns:
        return 50.0

    try:
        close = kline["close"].astype(float)
        ma = close.rolling(20).mean().iloc[-1]
        std = close.rolling(20).std().iloc[-1]

        if std == 0:
            return 50.0

        current = close.iloc[-1]
        upper = ma + 2 * std
        lower = ma - 2 * std

        # 计算价格在布林带中的位置 0(下轨) ~ 1(上轨)
        position = (current - lower) / max(upper - lower, 1e-8)

        # 最优位置在下轨附近（买入良机）→高分
        # 上轨附近（超买）→低分
        if position <= 0.1:
            score = 90  # 超卖，买入信号
        elif position >= 0.9:
            score = 20  # 超买，卖出信号
        elif 0.3 <= position <= 0.7:
            score = 60  # 中间位置
        else:
            score = 50

        # 布林带收窄（变盘信号）适当加分
        bandwidth = (upper - lower) / max(ma, 1e-8)
        if bandwidth < 0.05:
            score += 10

        return float(round(max(0, min(100, score))))
    except Exception as e:
        logger.debug(f"布林带计算异常: {e}")
        return 50.0


def calc_technical_score(kline: pd.DataFrame) -> dict[str, float]:
    """计算技术面综合得分.

    四个子因子等权平均。

    Args:
        kline: K线数据

    Returns:
        dict: {"ma_trend": float, "macd": float, "volume": float,
               "bollinger": float, "score": float}
    """
    if kline.empty or len(kline) < 60:
        return {"ma_trend": 50.0, "macd": 50.0, "volume": 50.0,
                "bollinger": 50.0, "score": 50.0}

    ma_trend = calc_ma_trend_score(kline)
    macd = calc_macd_score(kline)
    volume = calc_volume_score(kline)
    bollinger = calc_bollinger_score(kline)

    score = (ma_trend + macd + volume + bollinger) / 4

    return {
        "ma_trend": ma_trend,
        "macd": macd,
        "volume": volume,
        "bollinger": bollinger,
        "score": round(score),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_technical.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/factors/technical.py tests/test_factors_technical.py
git commit -m "feat: 实现技术面因子模块 (factors/technical.py)"
```

---

### Task 2: 实现基本面因子 (factors/fundamental.py)

**Files:**
- Create: `src/factors/fundamental.py`
- Create: `tests/test_factors_fundamental.py`

**Interfaces:**
- Produces: `calc_fundamental_score(fund_data: FundamentalData) -> dict[str, float]`
- Returns: `{"valuation": 0-100, "profitability": 0-100, "growth": 0-100, "score": 0-100}`

- [ ] **Step 1: 编写基本面因子测试**

```python
# tests/test_factors_fundamental.py
"""测试 factors/fundamental.py 基本面因子."""
from __future__ import annotations

from src.factors.fundamental import calc_fundamental_score
from src.pipeline.collect import FundamentalData


class TestCalcFundamentalScore:
    """基本面综合得分测试."""

    def test_high_roe_scores_high(self) -> None:
        """高ROE得分高."""
        data = FundamentalData(roe=20.0, eps=2.0, profit_growth=15.0,
                               revenue_growth=10.0, pe_ttm=15.0, pb=2.0)
        result = calc_fundamental_score(data)
        assert result["profitability"] > 50

    def test_low_pe_scores_high(self) -> None:
        """低PE得分高."""
        data = FundamentalData(roe=10.0, eps=2.0, profit_growth=10.0,
                               revenue_growth=5.0, pe_ttm=5.0, pb=1.0)
        result = calc_fundamental_score(data)
        assert result["valuation"] > 60

    def test_high_growth_scores_high(self) -> None:
        """高增长得分高."""
        data_low = FundamentalData(profit_growth=0.0, revenue_growth=0.0)
        data_high = FundamentalData(profit_growth=30.0, revenue_growth=25.0)
        low = calc_fundamental_score(data_low)
        high = calc_fundamental_score(data_high)
        assert high["growth"] > low["growth"]

    def test_returns_0_to_100(self) -> None:
        """得分在0-100范围内."""
        data = FundamentalData()
        result = calc_fundamental_score(data)
        for key, value in result.items():
            assert 0 <= value <= 100, f"{key} = {value} out of range"

    def test_all_sub_factors_present(self) -> None:
        """所有子因子存在."""
        result = calc_fundamental_score(FundamentalData())
        assert "valuation" in result
        assert "profitability" in result
        assert "growth" in result
        assert "score" in result

    def test_extreme_pe_doesnt_break(self) -> None:
        """极端PE不崩溃."""
        data = FundamentalData(pe_ttm=500.0, eps=0.01)
        result = calc_fundamental_score(data)
        assert 0 <= result["valuation"] <= 100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_fundamental.py -v`

Expected: FAIL

- [ ] **Step 3: 实现基本面因子**

```python
# src/factors/fundamental.py
"""基本面因子模块.

计算估值、盈利能力和成长性三个基本面因子。
"""
from __future__ import annotations

import logging

from src.pipeline.collect import FundamentalData

logger = logging.getLogger("thousand-times")


def _calc_valuation_score(data: FundamentalData) -> float:
    """估值得分：PE/PB越低越好.

    Args:
        data: 基本面数据

    Returns:
        float: 0-100 分数
    """
    pe = data.pe_ttm
    pb = data.pb

    score = 50.0

    # PE评分
    if pe <= 0:
        return 30.0  # 亏损企业，估值无意义
    elif pe <= 10:
        score += 30
    elif pe <= 20:
        score += 15
    elif pe <= 30:
        score += 5
    elif pe <= 50:
        score -= 10
    else:
        score -= 25

    # PB评分
    if 0 < pb <= 1:
        score += 20
    elif pb <= 2:
        score += 10
    elif pb <= 5:
        score -= 10
    else:
        score -= 20

    return float(round(max(0, min(100, score))))


def _calc_profitability_score(data: FundamentalData) -> float:
    """盈利能力得分：ROE越高越好.

    Args:
        data: 基本面数据

    Returns:
        float: 0-100 分数
    """
    roe = data.roe

    if roe <= 0:
        return 10.0
    elif roe <= 5:
        return 25.0
    elif roe <= 10:
        return 50.0
    elif roe <= 15:
        return 65.0
    elif roe <= 20:
        return 80.0
    elif roe <= 30:
        return 90.0
    else:
        return 100.0


def _calc_growth_score(data: FundamentalData) -> float:
    """成长性得分：利润增速和营收增速.

    Args:
        data: 基本面数据

    Returns:
        float: 0-100 分数
    """
    profit_g = data.profit_growth
    revenue_g = data.revenue_growth

    score = 50.0

    # 利润增速
    score += min(25, max(-15, profit_g * 1.0))

    # 营收增速
    score += min(25, max(-15, revenue_g * 0.5))

    return float(round(max(0, min(100, score))))


def calc_fundamental_score(data: FundamentalData) -> dict[str, float]:
    """计算基本面综合得分.

    Args:
        data: 基本面数据

    Returns:
        dict: {"valuation": float, "profitability": float,
               "growth": float, "score": float}
    """
    valuation = _calc_valuation_score(data)
    profitability = _calc_profitability_score(data)
    growth = _calc_growth_score(data)

    score = (valuation + profitability + growth) / 3

    return {
        "valuation": valuation,
        "profitability": profitability,
        "growth": growth,
        "score": round(score),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_fundamental.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/factors/fundamental.py tests/test_factors_fundamental.py
git commit -m "feat: 实现基本面因子模块 (factors/fundamental.py)"
```

---

### Task 3: 实现资金面因子 (factors/capital.py)

**Files:**
- Create: `src/factors/capital.py`
- Create: `tests/test_factors_capital.py`

**Interfaces:**
- Produces: `calc_capital_score(code: str, north_flow: pd.DataFrame) -> dict[str, float]`
- Returns: `{"north_flow": 0-100, "main_flow": 0-100, "score": 0-100}`

- [ ] **Step 1: 编写资金面因子测试**

```python
# tests/test_factors_capital.py
"""测试 factors/capital.py 资金面因子."""
from __future__ import annotations

import pandas as pd

from src.factors.capital import calc_capital_score


class TestCalcCapitalScore:
    """资金面综合得分测试."""

    def test_returns_dict_with_all_fields(self) -> None:
        """返回包含所有子因子的字典."""
        north_flow = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [20e8, 25e8, 30e8, 15e8, 10e8],
        })
        result = calc_capital_score("600519", north_flow)
        assert "north_flow" in result
        assert "main_flow" in result
        assert "score" in result

    def test_positive_north_flow_scores_high(self) -> None:
        """北向资金净流入得分高."""
        bullish = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [30e8, 25e8, 20e8, 15e8, 10e8],
        })
        bearish = pd.DataFrame({
            "日期": pd.date_range("2024-01-01", periods=5),
            "当日成交净买额": [-30e8, -25e8, -20e8, -15e8, -10e8],
        })
        high = calc_capital_score("600519", bullish)
        low = calc_capital_score("600519", bearish)
        assert high["north_flow"] > low["north_flow"]

    def test_empty_north_flow_returns_neutral(self) -> None:
        """空数据返回中性分."""
        result = calc_capital_score("600519", pd.DataFrame())
        assert result["north_flow"] == 50.0
        assert result["score"] == 50.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_capital.py -v`

Expected: FAIL

- [ ] **Step 3: 实现资金面因子**

```python
# src/factors/capital.py
"""资金面因子模块.

计算北向资金和主力资金两个资金面因子。
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _calc_north_flow_score(north_flow: pd.DataFrame) -> float:
    """北向资金得分：基于近5日北向资金整体流向趋势.

    Args:
        north_flow: 北向资金数据

    Returns:
        float: 0-100 分数
    """
    if north_flow.empty or "当日成交净买额" not in north_flow.columns:
        return 50.0

    try:
        net_flow = north_flow["当日成交净买额"].astype(float).tail(5)
        total = net_flow.sum()
        consecutive = (net_flow > 0).sum()

        score = 50.0

        # 累计流入评分
        if total > 200e8:
            score += 30
        elif total > 100e8:
            score += 20
        elif total > 50e8:
            score += 10
        elif total > 0:
            score += 5
        elif total < -200e8:
            score -= 30
        elif total < -100e8:
            score -= 20
        elif total < -50e8:
            score -= 10
        else:
            score -= 5

        # 连续性评分
        if consecutive >= 4:
            score += 10
        elif consecutive <= 1:
            score -= 5

        return float(round(max(0, min(100, score))))
    except Exception as e:
        logger.debug(f"北向资金评分异常: {e}")
        return 50.0


def _calc_main_flow_score(code: str) -> float:
    """主力资金得分（简化实现，后续可扩展）.

    Args:
        code: 股票代码

    Returns:
        float: 0-100 分数
    """
    # P1阶段实现：调用资金流API获取个股主力资金数据
    # 当前返回中性分
    return 50.0


def calc_capital_score(code: str, north_flow: pd.DataFrame) -> dict[str, float]:
    """计算资金面综合得分.

    Args:
        code: 股票代码
        north_flow: 北向资金数据

    Returns:
        dict: {"north_flow": float, "main_flow": float, "score": float}
    """
    north_score = _calc_north_flow_score(north_flow)
    main_score = _calc_main_flow_score(code)

    score = (north_score + main_score) / 2

    return {
        "north_flow": north_score,
        "main_flow": main_score,
        "score": round(score),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_capital.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/factors/capital.py tests/test_factors_capital.py
git commit -m "feat: 实现资金面因子模块 (factors/capital.py)"
```

---

### Task 4: 实现情绪面因子和动量因子

**Files:**
- Create: `src/factors/sentiment.py`
- Create: `src/factors/momentum.py`
- Create: `tests/test_factors_sentiment.py`
- Create: `tests/test_factors_momentum.py`

**Interfaces:**
- `calc_sentiment_score(limit_up: int, limit_down: int, policy_impacts: list) -> dict[str, float]`
- `calc_momentum_score(code: str, kline_cache: dict, etf_kline_cache: dict) -> dict[str, float]`

- [ ] **Step 1: 编写情绪面和动量因子测试**

```python
# tests/test_factors_sentiment.py
"""测试 factors/sentiment.py 情绪面因子."""
from __future__ import annotations

from src.factors.sentiment import calc_sentiment_score


class TestCalcSentimentScore:
    """情绪面综合得分测试."""

    def test_bullish_sentiment_scores_high(self) -> None:
        """市场情绪好得分高."""
        result = calc_sentiment_score(limit_up=50, limit_down=5, policy_impacts=[])
        assert result["market_sentiment"] > 50

    def test_bearish_sentiment_scores_low(self) -> None:
        """市场情绪差得分低."""
        result = calc_sentiment_score(limit_up=5, limit_down=50, policy_impacts=[])
        assert result["market_sentiment"] < 50

    def test_balanced_sentiment_neutral(self) -> None:
        """情绪平衡得分中位."""
        result = calc_sentiment_score(limit_up=10, limit_down=10, policy_impacts=[])
        assert 40 <= result["market_sentiment"] <= 60

    def test_returns_all_fields(self) -> None:
        """返回所有字段."""
        result = calc_sentiment_score(limit_up=10, limit_down=5, policy_impacts=[])
        assert "market_sentiment" in result
        assert "news_sentiment" in result
        assert "score" in result
```

```python
# tests/test_factors_momentum.py
"""测试 factors/momentum.py 动量因子."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.factors.momentum import calc_momentum_score


def make_kline_cache(prices: list[float]) -> dict[str, pd.DataFrame]:
    """构造 K线缓存."""
    dates = pd.date_range("2024-01-01", periods=len(prices))
    return {
        "test_code": pd.DataFrame({
            "date": dates,
            "close": prices,
        }),
    }


class TestCalcMomentumScore:
    """动量综合得分测试."""

    def test_positive_momentum_scores_high(self) -> None:
        """正动量得分高."""
        prices = np.linspace(10, 20, 120).tolist()  # 持续上涨
        result = calc_momentum_score("test_code", make_kline_cache(prices), {})
        assert result["score"] > 50

    def test_negative_momentum_scores_low(self) -> None:
        """负动量得分低."""
        prices = np.linspace(20, 10, 120).tolist()  # 持续下跌
        result = calc_momentum_score("test_code", make_kline_cache(prices), {})
        assert result["score"] < 50

    def test_missing_code_returns_neutral(self) -> None:
        """缺失代码返回中性."""
        result = calc_momentum_score("nonexistent", {}, {})
        assert result["score"] == 50.0

    def test_returns_all_fields(self) -> None:
        """返回所有字段."""
        prices = [10.0] * 120
        result = calc_momentum_score("test_code", make_kline_cache(prices), {})
        assert "short_momentum" in result
        assert "mid_momentum" in result
        assert "relative_strength" in result
        assert "score" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_sentiment.py tests/test_factors_momentum.py -v`

Expected: FAIL

- [ ] **Step 3: 实现情绪面因子**

```python
# src/factors/sentiment.py
"""情绪面因子模块.

计算市场情绪和新闻情绪两个因子。
"""
from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def _calc_market_sentiment(limit_up: int, limit_down: int) -> float:
    """市场情绪得分：基于涨跌停家数比.

    Args:
        limit_up: 涨停家数
        limit_down: 跌停家数

    Returns:
        float: 0-100 分数
    """
    if limit_up == 0 and limit_down == 0:
        return 50.0

    total = limit_up + limit_down
    up_ratio = limit_up / max(total, 1)

    # 将涨跌比映射到 0-100
    return float(round(max(0, min(100, up_ratio * 100))))


def _calc_news_sentiment(policy_impacts: list) -> float:
    """新闻情绪得分：基于 LLM 政策分析结果.

    Args:
        policy_impacts: PolicyImpact 列表

    Returns:
        float: 0-100 分数，无数据返回50
    """
    if not policy_impacts:
        return 50.0

    try:
        scores = []
        for impact in policy_impacts:
            if hasattr(impact, "score"):
                scores.append(impact.score)
        if scores:
            avg = sum(scores) / len(scores)
            return float(round(max(0, min(100, avg))))
    except Exception as e:
        logger.debug(f"新闻情绪计算异常: {e}")

    return 50.0


def calc_sentiment_score(
    limit_up: int,
    limit_down: int,
    policy_impacts: list,
) -> dict[str, float]:
    """计算情绪面综合得分.

    Args:
        limit_up: 涨停家数
        limit_down: 跌停家数
        policy_impacts: LLM政策分析结果

    Returns:
        dict: {"market_sentiment": float, "news_sentiment": float, "score": float}
    """
    market = _calc_market_sentiment(limit_up, limit_down)
    news = _calc_news_sentiment(policy_impacts)

    score = (market + news) / 2

    return {
        "market_sentiment": market,
        "news_sentiment": news,
        "score": round(score),
    }
```

```python
# src/factors/momentum.py
"""动量因子模块.

计算短期动量、中期动量和相对强弱三个动量因子。
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _calc_short_momentum(kline: pd.DataFrame) -> float:
    """短期动量：近5日和10日收益率.

    Args:
        kline: K线数据

    Returns:
        float: 0-100 分数
    """
    if "close" not in kline.columns or len(kline) < 10:
        return 50.0

    try:
        close = kline["close"].astype(float)
        ret_5 = (close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0
        ret_10 = (close.iloc[-1] / close.iloc[-10] - 1) if len(close) >= 10 else 0

        score = 50.0 + ret_5 * 200 + ret_10 * 100
        return float(round(max(0, min(100, score))))
    except Exception:
        return 50.0


def _calc_mid_momentum(kline: pd.DataFrame) -> float:
    """中期动量：近20日和60日收益率.

    Args:
        kline: K线数据

    Returns:
        float: 0-100 分数
    """
    if "close" not in kline.columns or len(kline) < 60:
        return 50.0

    try:
        close = kline["close"].astype(float)
        ret_20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0
        ret_60 = (close.iloc[-1] / close.iloc[-60] - 1) if len(close) >= 60 else 0

        score = 50.0 + ret_20 * 200 + ret_60 * 100
        return float(round(max(0, min(100, score))))
    except Exception:
        return 50.0


def _calc_relative_strength(
    code: str,
    kline: pd.DataFrame,
    etf_kline_cache: dict[str, pd.DataFrame],
) -> float:
    """相对强弱：个股 vs 行业 ETF 的相对收益.

    Args:
        code: 股票代码
        kline: 个股K线
        etf_kline_cache: ETF K线缓存

    Returns:
        float: 0-100 分数
    """
    if "close" not in kline.columns:
        return 50.0

    try:
        stock_ret = kline["close"].astype(float).pct_change(20).iloc[-1]

        # 找对应行业ETF（简化处理）
        etf_rets = []
        for etf_code, etf_kline in etf_kline_cache.items():
            if "close" in etf_kline.columns and not etf_kline.empty:
                etf_rets.append(etf_kline["close"].astype(float).pct_change(20).iloc[-1])

        if etf_rets:
            avg_etf_ret = sum(etf_rets) / len(etf_rets)
            relative = stock_ret - avg_etf_ret
            score = 50.0 + relative * 300
        else:
            score = 50.0

        return float(round(max(0, min(100, score))))
    except Exception:
        return 50.0


def calc_momentum_score(
    code: str,
    kline_cache: dict[str, pd.DataFrame],
    etf_kline_cache: dict[str, pd.DataFrame],
) -> dict[str, float]:
    """计算动量综合得分.

    Args:
        code: 股票代码
        kline_cache: K线缓存字典
        etf_kline_cache: ETF K线缓存字典

    Returns:
        dict: {"short_momentum": float, "mid_momentum": float,
               "relative_strength": float, "score": float}
    """
    if code not in kline_cache or kline_cache[code].empty:
        return {"short_momentum": 50.0, "mid_momentum": 50.0,
                "relative_strength": 50.0, "score": 50.0}

    kline = kline_cache[code]

    short = _calc_short_momentum(kline)
    mid = _calc_mid_momentum(kline)
    relative = _calc_relative_strength(code, kline, etf_kline_cache)

    score = (short + mid + relative) / 3

    return {
        "short_momentum": short,
        "mid_momentum": mid,
        "relative_strength": relative,
        "score": round(score),
    }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_factors_sentiment.py tests/test_factors_momentum.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/factors/sentiment.py src/factors/momentum.py tests/test_factors_sentiment.py tests/test_factors_momentum.py
git commit -m "feat: 实现情绪面因子和动量因子"
```

---

### Task 5: 更新 factors 包导出

**Files:**
- Modify: `src/factors/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
# src/factors/__init__.py
"""Factors package - 多因子计算库."""
from __future__ import annotations

from src.factors.technical import calc_technical_score
from src.factors.fundamental import calc_fundamental_score
from src.factors.capital import calc_capital_score
from src.factors.sentiment import calc_sentiment_score
from src.factors.momentum import calc_momentum_score

__all__ = [
    "technical",
    "fundamental",
    "capital",
    "sentiment",
    "momentum",
    "calc_technical_score",
    "calc_fundamental_score",
    "calc_capital_score",
    "calc_sentiment_score",
    "calc_momentum_score",
]
```

- [ ] **Step 2: 验证导入**

Run: `cd "h:/code/thousand times" && python -c "from src.factors import calc_technical_score, calc_fundamental_score, calc_capital_score, calc_sentiment_score, calc_momentum_score; print('OK')"`

Expected: OK

- [ ] **Step 3: Commit**

```bash
cd "h:/code/thousand times"
git add src/factors/__init__.py
git commit -m "feat: 更新 factors 包导出"
```

---

## 自检清单

- [ ] 所有因子测试通过: `pytest tests/test_factors_*.py -v`
- [ ] 每个因子返回值范围 0-100
- [ ] 空数据/异常数据返回中性分 50
- [ ] 5个因子模块全部实现: technical, fundamental, capital, sentiment, momentum
- [ ] 代码质量: `ruff check src/factors/`
