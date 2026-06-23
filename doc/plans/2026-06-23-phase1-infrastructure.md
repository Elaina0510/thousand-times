# Phase 1: 基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建新管道的目录结构、扩展配置系统、实现P0级数据源模块（北向资金、涨跌停统计）

**Architecture:** 新建 `pipeline/`、`data_sources/`、`factors/` 三个包，扩展 `config.py` 增加策略配置类，实现两个P0数据源模块作为后续阶段的数据基础

**Tech Stack:** Python 3.10+, AKShare, dataclasses, pandas

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 所有公共函数和类必须有 Google 风格 docstring
- 使用 `from __future__ import annotations` 延迟注解求值
- 日志使用 `logging.getLogger("thousand-times")`
- 外部 API 调用必须有异常处理和降级策略
- 测试使用 pytest + monkeypatch，不依赖网络

## 文件结构

```
src/
├── config.py                    ← 修改：新增配置类
├── pipeline/
│   ├── __init__.py              ← 新建：包初始化
│   ├── regime.py                ← 后续任务
│   ├── collect.py               ← 后续任务
│   ├── factors.py               ← 后续任务
│   ├── signal.py                ← 后续任务
│   └── output.py                ← 后续任务
├── data_sources/
│   ├── __init__.py              ← 新建：包初始化
│   ├── capital_flow.py          ← 新建：北向资金
│   └── sentiment.py             ← 新建：涨跌停统计
└── factors/
    └── __init__.py              ← 新建：包初始化

tests/
├── test_data_sources.py         ← 新建
└── test_config_v2.py            ← 新建
```

---

### Task 1: 创建目录结构和包初始化文件

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/data_sources/__init__.py`
- Create: `src/factors/__init__.py`

**Interfaces:**
- Produces: 三个 Python 包，供后续模块导入

- [ ] **Step 1: 创建 pipeline 包初始化文件**

```python
# src/pipeline/__init__.py
"""Pipeline package - 五阶段管道架构.

阶段:
    1. regime - 市场环境判断
    2. collect - 数据采集
    3. factors - 多因子计算
    4. signal - 信号生成
    5. output - 报告输出
"""

from __future__ import annotations

__all__ = ["regime", "collect", "factors", "signal", "output"]
```

- [ ] **Step 2: 创建 data_sources 包初始化文件**

```python
# src/data_sources/__init__.py
"""Data sources package - 外部数据源模块.

模块:
    capital_flow - 北向资金、融资融券
    sentiment - 涨跌停统计、市场情绪
    sector_flow - 行业资金流向（P1）
    macro - 宏观指标（P2）
"""

from __future__ import annotations

__all__ = ["capital_flow", "sentiment"]
```

- [ ] **Step 3: 创建 factors 包初始化文件**

```python
# src/factors/__init__.py
"""Factors package - 多因子计算库.

模块:
    technical - 技术面因子
    fundamental - 基本面因子
    capital - 资金面因子
    sentiment - 情绪面因子
    momentum - 动量因子
"""

from __future__ import annotations

__all__ = ["technical", "fundamental", "capital", "sentiment", "momentum"]
```

- [ ] **Step 4: 验证包导入**

Run: `cd "h:/code/thousand times" && python -c "from src.pipeline import regime; from src.data_sources import capital_flow; from src.factors import technical; print('OK')"`

Expected: 如果模块不存在会报错，但包本身应该可以导入

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/__init__.py src/data_sources/__init__.py src/factors/__init__.py
git commit -m "feat: 创建 pipeline/data_sources/factors 包结构"
```

---

### Task 2: 扩展 config.py - 新增配置类

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config_v2.py`

**Interfaces:**
- Produces: `RegimeConfig`, `FactorWeightConfig`, `SignalConfig`, `RealtimeConfig`, `BacktestConfig` 数据类

- [ ] **Step 1: 编写配置类测试**

```python
# tests/test_config_v2.py
"""测试 config.py 新增配置类."""
from __future__ import annotations

from src.config import (
    AppConfig,
    BacktestConfig,
    FactorWeightConfig,
    RealtimeConfig,
    RegimeConfig,
    SignalConfig,
)


class TestRegimeConfig:
    """市场环境判断配置测试."""

    def test_default_values(self) -> None:
        config = RegimeConfig()
        assert config.ma_short == 20
        assert config.ma_long == 60
        assert config.volume_bull_ratio == 1.2
        assert config.volume_bear_ratio == 0.8
        assert config.north_flow_threshold == 100e8
        assert config.advance_decline_bull == 1.5
        assert config.advance_decline_bear == 0.7
        assert config.pe_percentile_low == 0.4
        assert config.pe_percentile_high == 0.7

    def test_custom_values(self) -> None:
        config = RegimeConfig(ma_short=10, ma_long=30)
        assert config.ma_short == 10
        assert config.ma_long == 30


class TestFactorWeightConfig:
    """因子权重配置测试."""

    def test_default_weights(self) -> None:
        config = FactorWeightConfig()
        assert config.bull == {
            "technical": 0.30,
            "fundamental": 0.15,
            "capital": 0.15,
            "sentiment": 0.10,
            "momentum": 0.30,
        }
        assert config.bear == {
            "technical": 0.25,
            "fundamental": 0.30,
            "capital": 0.15,
            "sentiment": 0.15,
            "momentum": 0.15,
        }
        assert config.sideways == {
            "technical": 0.30,
            "fundamental": 0.20,
            "capital": 0.15,
            "sentiment": 0.15,
            "momentum": 0.20,
        }

    def test_weights_sum_to_one(self) -> None:
        config = FactorWeightConfig()
        assert abs(sum(config.bull.values()) - 1.0) < 1e-6
        assert abs(sum(config.bear.values()) - 1.0) < 1e-6
        assert abs(sum(config.sideways.values()) - 1.0) < 1e-6


class TestSignalConfig:
    """信号生成配置测试."""

    def test_default_values(self) -> None:
        config = SignalConfig()
        assert config.min_buy_votes == 3
        assert config.min_sell_votes == 3
        assert config.factor_buy_threshold == 70.0
        assert config.factor_sell_threshold == 30.0
        assert config.technical_buy_threshold == 75.0
        assert config.technical_sell_threshold == 25.0
        assert config.atr_target_multiplier == 2.0
        assert config.atr_stop_multiplier == 1.5
        assert config.min_risk_reward == 2.0


class TestRealtimeConfig:
    """实时提醒配置测试."""

    def test_default_values(self) -> None:
        config = RealtimeConfig()
        assert config.check_interval_minutes == 30
        assert config.score_jump_threshold == 25.0
        assert config.north_flow_alert == 100e8


class TestBacktestConfig:
    """回测配置测试."""

    def test_default_values(self) -> None:
        config = BacktestConfig()
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2025-12-31"
        assert config.pool_size == 50
        assert config.hold_days == [1, 3, 5, 10]
        assert config.buy_threshold == 70.0
        assert config.sell_threshold == 30.0
        assert config.commission_rate == 0.001
        assert config.slippage == 0.001
        assert config.initial_capital == 100000.0


class TestAppConfigV2:
    """AppConfig 扩展测试."""

    def test_has_new_config_fields(self) -> None:
        config = AppConfig()
        assert hasattr(config, "regime")
        assert hasattr(config, "factor_weights")
        assert hasattr(config, "signal")
        assert hasattr(config, "realtime")
        assert hasattr(config, "backtest")
        assert hasattr(config, "use_v2_pipeline")

    def test_default_v2_pipeline_disabled(self) -> None:
        config = AppConfig()
        assert config.use_v2_pipeline is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_config_v2.py -v`

Expected: FAIL - ImportError (配置类不存在)

- [ ] **Step 3: 在 config.py 中添加新配置类**

在 `src/config.py` 文件末尾（AppConfig 类之前）添加以下配置类：

```python
@dataclass
class RegimeConfig:
    """市场环境判断配置."""

    ma_short: int = 20
    ma_long: int = 60
    volume_bull_ratio: float = 1.2
    volume_bear_ratio: float = 0.8
    north_flow_threshold: float = 100e8  # 100亿
    advance_decline_bull: float = 1.5
    advance_decline_bear: float = 0.7
    pe_percentile_low: float = 0.4
    pe_percentile_high: float = 0.7


@dataclass
class FactorWeightConfig:
    """因子权重配置（按市场环境）."""

    bull: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.30,
        "fundamental": 0.15,
        "capital": 0.15,
        "sentiment": 0.10,
        "momentum": 0.30,
    })
    bear: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.25,
        "fundamental": 0.30,
        "capital": 0.15,
        "sentiment": 0.15,
        "momentum": 0.15,
    })
    sideways: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.30,
        "fundamental": 0.20,
        "capital": 0.15,
        "sentiment": 0.15,
        "momentum": 0.20,
    })


@dataclass
class SignalConfig:
    """信号生成配置."""

    min_buy_votes: int = 3
    min_sell_votes: int = 3
    factor_buy_threshold: float = 70.0
    factor_sell_threshold: float = 30.0
    technical_buy_threshold: float = 75.0
    technical_sell_threshold: float = 25.0
    atr_target_multiplier: float = 2.0
    atr_stop_multiplier: float = 1.5
    min_risk_reward: float = 2.0


@dataclass
class RealtimeConfig:
    """实时提醒配置."""

    check_interval_minutes: int = 30
    score_jump_threshold: float = 25.0
    north_flow_alert: float = 100e8


@dataclass
class BacktestConfig:
    """回测配置."""

    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    pool_size: int = 50
    hold_days: list[int] = field(default_factory=lambda: [1, 3, 5, 10])
    buy_threshold: float = 70.0
    sell_threshold: float = 30.0
    commission_rate: float = 0.001
    slippage: float = 0.001
    initial_capital: float = 100000.0
```

- [ ] **Step 4: 在 AppConfig 类中添加新字段**

在 `AppConfig` 类中添加以下字段（在现有字段之后）：

```python
    # V2 管道配置
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    factor_weights: FactorWeightConfig = field(default_factory=FactorWeightConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    realtime: RealtimeConfig = field(default_factory=RealtimeConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    use_v2_pipeline: bool = False
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_config_v2.py -v`

Expected: PASS - 所有测试通过

- [ ] **Step 6: Commit**

```bash
cd "h:/code/thousand times"
git add src/config.py tests/test_config_v2.py
git commit -m "feat: 扩展 config.py 新增 V2 管道配置类"
```

---

### Task 3: 实现北向资金数据源 (data_sources/capital_flow.py)

**Files:**
- Create: `src/data_sources/capital_flow.py`
- Modify: `tests/test_data_sources.py`

**Interfaces:**
- Produces:
  - `fetch_north_flow(days: int = 5) -> pd.DataFrame` - 获取北向资金每日净流入
  - `fetch_north_flow_stock(code: str) -> float` - 获取个股北向持仓变动

- [ ] **Step 1: 编写北向资金测试**

```python
# tests/test_data_sources.py
"""测试 data_sources 模块."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data_sources.capital_flow import fetch_north_flow, fetch_north_flow_stock


class TestFetchNorthFlow:
    """北向资金整体流向测试."""

    @patch("src.data_sources.capital_flow.ak")
    def test_returns_dataframe(self, mock_ak: MagicMock) -> None:
        """测试返回 DataFrame."""
        mock_df = pd.DataFrame({
            "日期": ["2024-01-01", "2024-01-02"],
            "当日成交净买额": [1e8, 2e8],
            "当日资金流入": [3e8, 4e8],
        })
        mock_ak.stock_hsgt_hist_em.return_value = mock_df

        result = fetch_north_flow(days=2)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        mock_ak.stock_hsgt_hist_em.assert_called_once_with(symbol="北向资金")

    @patch("src.data_sources.capital_flow.ak")
    def test_handles_api_error(self, mock_ak: MagicMock) -> None:
        """测试 API 异常时返回空 DataFrame."""
        mock_ak.stock_hsgt_hist_em.side_effect = Exception("API Error")

        result = fetch_north_flow()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch("src.data_sources.capital_flow.ak")
    def test_limits_rows_by_days(self, mock_ak: MagicMock) -> None:
        """测试按 days 参数限制返回行数."""
        mock_df = pd.DataFrame({
            "日期": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "当日成交净买额": [1e8] * 10,
        })
        mock_ak.stock_hsgt_hist_em.return_value = mock_df

        result = fetch_north_flow(days=5)

        assert len(result) == 5


class TestFetchNorthFlowStock:
    """个股北向持仓测试."""

    @patch("src.data_sources.capital_flow.ak")
    def test_returns_float(self, mock_ak: MagicMock) -> None:
        """测试返回浮点数."""
        mock_df = pd.DataFrame({
            "代码": ["600519"],
            "名称": ["贵州茅台"],
            "今日持股-股数": [1000000],
        })
        mock_ak.stock_hsgt_hold_stock_em.return_value = mock_df

        result = fetch_north_flow_stock("600519")

        assert isinstance(result, float)
        assert result == 1000000.0

    @patch("src.data_sources.capital_flow.ak")
    def test_stock_not_found_returns_zero(self, mock_ak: MagicMock) -> None:
        """测试股票不存在时返回 0."""
        mock_df = pd.DataFrame({
            "代码": ["000001"],
            "名称": ["平安银行"],
            "今日持股-股数": [500000],
        })
        mock_ak.stock_hsgt_hold_stock_em.return_value = mock_df

        result = fetch_north_flow_stock("600519")

        assert result == 0.0

    @patch("src.data_sources.capital_flow.ak")
    def test_api_error_returns_zero(self, mock_ak: MagicMock) -> None:
        """测试 API 异常时返回 0."""
        mock_ak.stock_hsgt_hold_stock_em.side_effect = Exception("Network Error")

        result = fetch_north_flow_stock("600519")

        assert result == 0.0

    @patch("src.data_sources.capital_flow.ak")
    def test_tries_both_markets(self, mock_ak: MagicMock) -> None:
        """测试先查沪股通，找不到再查深股通."""
        # 第一次调用（沪股通）返回空
        # 第二次调用（深股通）返回数据
        mock_ak.stock_hsgt_hold_stock_em.side_effect = [
            pd.DataFrame({"代码": [], "名称": [], "今日持股-股数": []}),
            pd.DataFrame({
                "代码": ["000858"],
                "名称": ["五粮液"],
                "今日持股-股数": [200000],
            }),
        ]

        result = fetch_north_flow_stock("000858")

        assert result == 200000.0
        assert mock_ak.stock_hsgt_hold_stock_em.call_count == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_data_sources.py::TestFetchNorthFlow -v`

Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 capital_flow.py**

```python
# src/data_sources/capital_flow.py
"""北向资金数据源.

获取北向资金（沪股通+深股通）每日净流入和个股持仓变动。
"""
from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

logger = logging.getLogger("thousand-times")


def fetch_north_flow(days: int = 5) -> pd.DataFrame:
    """获取北向资金每日净流入.

    Args:
        days: 获取最近 N 天的数据

    Returns:
        DataFrame with columns: 日期, 当日成交净买额, 当日资金流入
        Empty DataFrame if API fails
    """
    try:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is None or df.empty:
            logger.warning("北向资金数据为空")
            return pd.DataFrame()
        return df.tail(days).reset_index(drop=True)
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        return pd.DataFrame()


def fetch_north_flow_stock(code: str) -> float:
    """获取个股北向持仓变动（持股数量）.

    Args:
        code: 股票代码，如 "600519"

    Returns:
        持股数量（股），获取失败返回 0.0
    """
    for market in ["沪股通", "深股通"]:
        try:
            df = ak.stock_hsgt_hold_stock_em(market=market, indicator="今日排行")
            if df is None or df.empty:
                continue
            row = df[df["代码"] == code]
            if len(row) > 0:
                return float(row.iloc[0]["今日持股-股数"])
        except Exception as e:
            logger.debug(f"获取{market}持仓失败: {e}")
            continue
    return 0.0
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_data_sources.py::TestFetchNorthFlow tests/test_data_sources.py::TestFetchNorthFlowStock -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/data_sources/capital_flow.py tests/test_data_sources.py
git commit -m "feat: 实现北向资金数据源 (capital_flow.py)"
```

---

### Task 4: 实现涨跌停统计数据源 (data_sources/sentiment.py)

**Files:**
- Create: `src/data_sources/sentiment.py`
- Modify: `tests/test_data_sources.py`

**Interfaces:**
- Produces:
  - `fetch_limit_stats(date: str) -> dict[str, int | float]` - 获取涨跌停统计
  - 返回: `{"limit_up_count": int, "limit_down_count": int, "max_consecutive": int}`

- [ ] **Step 1: 编写涨跌停统计测试**

在 `tests/test_data_sources.py` 文件末尾添加：

```python
from src.data_sources.sentiment import fetch_limit_stats


class TestFetchLimitStats:
    """涨跌停统计测试."""

    @patch("src.data_sources.sentiment.ak")
    def test_returns_dict_with_counts(self, mock_ak: MagicMock) -> None:
        """测试返回包含涨跌停数量的字典."""
        mock_zt = pd.DataFrame({
            "代码": ["600519", "000858"],
            "名称": ["贵州茅台", "五粮液"],
            "涨停统计": ["2天", "3天"],
        })
        mock_dt = pd.DataFrame({
            "代码": ["000001"],
            "名称": ["平安银行"],
        })
        mock_ak.stock_zt_pool_em.return_value = mock_zt
        mock_ak.stock_zt_pool_dtgc_em.return_value = mock_dt

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 2
        assert result["limit_down_count"] == 1
        assert result["max_consecutive"] == 3

    @patch("src.data_sources.sentiment.ak")
    def test_handles_empty_zt_pool(self, mock_ak: MagicMock) -> None:
        """测试涨停池为空的情况."""
        mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
        mock_ak.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 0
        assert result["limit_down_count"] == 0
        assert result["max_consecutive"] == 0

    @patch("src.data_sources.sentiment.ak")
    def test_handles_api_error(self, mock_ak: MagicMock) -> None:
        """测试 API 异常时返回默认值."""
        mock_ak.stock_zt_pool_em.side_effect = Exception("API Error")

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 0
        assert result["limit_down_count"] == 0
        assert result["max_consecutive"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_data_sources.py::TestFetchLimitStats -v`

Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 sentiment.py**

```python
# src/data_sources/sentiment.py
"""涨跌停统计数据源.

获取涨停、跌停家数及连板高度。
"""
from __future__ import annotations

import logging

import akshare as ak
import pandas as pd

logger = logging.getLogger("thousand-times")


def fetch_limit_stats(date: str) -> dict[str, int]:
    """获取涨跌停统计.

    Args:
        date: 交易日期，格式 YYYYMMDD

    Returns:
        dict with keys:
            - limit_up_count: 涨停家数
            - limit_down_count: 跌停家数
            - max_consecutive: 最高连板天数
    """
    result = {"limit_up_count": 0, "limit_down_count": 0, "max_consecutive": 0}

    # 获取涨停池
    try:
        zt = ak.stock_zt_pool_em(date=date)
        if zt is not None and not zt.empty:
            result["limit_up_count"] = len(zt)
            # 解析连板天数: "2天" -> 2
            if "涨停统计" in zt.columns:
                consecutive = zt["涨停统计"].str.split("天").str[0]
                result["max_consecutive"] = int(consecutive.astype(int).max())
    except Exception as e:
        logger.warning(f"获取涨停统计失败: {e}")

    # 获取跌停池
    try:
        dt = ak.stock_zt_pool_dtgc_em(date=date)
        if dt is not None and not dt.empty:
            result["limit_down_count"] = len(dt)
    except Exception as e:
        logger.warning(f"获取跌停统计失败: {e}")

    return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_data_sources.py -v`

Expected: PASS - 所有测试通过

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/data_sources/sentiment.py tests/test_data_sources.py
git commit -m "feat: 实现涨跌停统计数据源 (sentiment.py)"
```

---

### Task 5: 更新 data_sources 包导出

**Files:**
- Modify: `src/data_sources/__init__.py`

**Interfaces:**
- Produces: 从包级别导出主要函数

- [ ] **Step 1: 更新 __init__.py 导出**

```python
# src/data_sources/__init__.py
"""Data sources package - 外部数据源模块.

模块:
    capital_flow - 北向资金、融资融券
    sentiment - 涨跌停统计、市场情绪
    sector_flow - 行业资金流向（P1）
    macro - 宏观指标（P2）
"""
from __future__ import annotations

from src.data_sources.capital_flow import fetch_north_flow, fetch_north_flow_stock
from src.data_sources.sentiment import fetch_limit_stats

__all__ = [
    "capital_flow",
    "sentiment",
    "fetch_north_flow",
    "fetch_north_flow_stock",
    "fetch_limit_stats",
]
```

- [ ] **Step 2: 验证导入**

Run: `cd "h:/code/thousand times" && python -c "from src.data_sources import fetch_north_flow, fetch_limit_stats; print('OK')"`

Expected: OK

- [ ] **Step 3: Commit**

```bash
cd "h:/code/thousand times"
git add src/data_sources/__init__.py
git commit -m "feat: 更新 data_sources 包导出"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_config_v2.py tests/test_data_sources.py -v`
- [ ] 类型检查通过: `mypy --strict src/config.py src/data_sources/`
- [ ] 代码质量通过: `ruff check src/config.py src/data_sources/`
- [ ] 目录结构正确: `pipeline/`, `data_sources/`, `factors/` 包存在
- [ ] 配置类可正确实例化: `AppConfig()` 包含所有新字段
- [ ] 数据源函数有异常处理: API 失败时返回空数据而非抛异常
