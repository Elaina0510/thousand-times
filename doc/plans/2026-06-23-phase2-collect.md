# Phase 2: 数据采集层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现统一数据采集层 `pipeline/collect.py`，定义 `DataBundle` 数据结构，整合现有数据源和新增数据源

**Architecture:** `pipeline/collect.py` 作为数据采集编排器，调用各数据源模块（baostock_data、data_sources 等），将结果打包为 `DataBundle` 供下游使用

**Tech Stack:** Python 3.10+, pandas, dataclasses, baostock, akshare

## Global Constraints

- 所有函数参数和返回值必须有类型注解
- 所有公共函数和类必须有 Google 风格 docstring
- 使用 `from __future__ import annotations` 延迟注解求值
- 日志使用 `logging.getLogger("thousand-times")`
- 单只股票/ETF 数据获取失败不影响整体流程

## 文件结构

```
src/
├── pipeline/
│   ├── __init__.py
│   └── collect.py         ← 新建：统一数据采集
tests/
└── test_pipeline_collect.py  ← 新建
```

---

### Task 1: 定义 DataBundle 数据结构

**Files:**
- Create: `src/pipeline/collect.py`
- Create: `tests/test_pipeline_collect.py`

**Interfaces:**
- Produces: `DataBundle` dataclass, `FundamentalData` dataclass

- [ ] **Step 1: 编写 DataBundle 测试**

```python
# tests/test_pipeline_collect.py
"""测试 pipeline/collect.py 数据采集模块."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.pipeline.collect import DataBundle, FundamentalData


class TestDataBundle:
    """DataBundle 数据结构测试."""

    def test_create_empty_bundle(self) -> None:
        """测试创建空的 DataBundle."""
        bundle = DataBundle(
            index_kline=pd.DataFrame(),
            stock_pool=pd.DataFrame(),
            kline_cache={},
            fundamental_cache={},
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
        assert bundle.index_kline.empty
        assert bundle.stock_pool.empty
        assert bundle.limit_up_count == 0

    def test_bundle_has_all_fields(self) -> None:
        """测试 DataBundle 包含所有必要字段."""
        fields = [
            "index_kline", "stock_pool", "kline_cache", "fundamental_cache",
            "north_flow", "margin_data", "limit_up_count", "limit_down_count",
            "advance_decline_ratio", "macro_indicators", "sector_flow",
            "news_items", "policy_impacts", "etf_pool", "etf_kline_cache",
        ]
        for field in fields:
            assert hasattr(DataBundle, field), f"Missing field: {field}"


class TestFundamentalData:
    """FundamentalData 数据结构测试."""

    def test_create_fundamental_data(self) -> None:
        """测试创建 FundamentalData."""
        data = FundamentalData(
            roe=15.0,
            eps=2.5,
            profit_growth=10.0,
            revenue_growth=8.0,
            pe_ttm=20.0,
            pb=3.0,
        )
        assert data.roe == 15.0
        assert data.eps == 2.5
        assert data.pe_ttm == 20.0

    def test_default_values(self) -> None:
        """测试默认值（获取失败时使用中性值）."""
        data = FundamentalData()
        assert data.roe == 0.0
        assert data.eps == 0.0
        assert data.pe_ttm == 50.0  # 中性估值
        assert data.pb == 1.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py -v`

Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 DataBundle 和 FundamentalData**

```python
# src/pipeline/collect.py
"""统一数据采集模块.

整合所有数据源，返回结构化的 DataBundle 供下游使用。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.data_sources.capital_flow import fetch_north_flow
from src.data_sources.sentiment import fetch_limit_stats

logger = logging.getLogger("thousand-times")


@dataclass
class FundamentalData:
    """个股基本面数据."""

    roe: float = 0.0          # 净资产收益率
    eps: float = 0.0          # 每股收益
    profit_growth: float = 0.0  # 净利润增速 (%)
    revenue_growth: float = 0.0  # 营收增速 (%)
    pe_ttm: float = 50.0      # 市盈率(TTM)，默认中性
    pb: float = 1.0           # 市净率


@dataclass
class DataBundle:
    """统一数据包，包含所有分析所需数据."""

    # 指数数据
    index_kline: pd.DataFrame  # 全A指数日K线

    # 股票池
    stock_pool: pd.DataFrame   # 股票列表 (code, name, ...)

    # 个股数据
    kline_cache: dict[str, pd.DataFrame]  # code -> K线数据
    fundamental_cache: dict[str, FundamentalData]  # code -> 基本面

    # 资金面
    north_flow: pd.DataFrame   # 北向资金每日净流入
    margin_data: pd.DataFrame | None  # 融资融券数据

    # 情绪面
    limit_up_count: int        # 今日涨停家数
    limit_down_count: int      # 今日跌停家数
    advance_decline_ratio: float  # 涨跌家数比

    # 宏观面
    macro_indicators: dict[str, float]  # CPI, PMI, 利率等

    # 行业数据
    sector_flow: pd.DataFrame  # 行业资金流向

    # 新闻
    news_items: list  # NewsItem list
    policy_impacts: list  # PolicyImpact list

    # ETF
    etf_pool: list  # EtfInfo list
    etf_kline_cache: dict[str, pd.DataFrame]  # code -> K线数据
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/collect.py tests/test_pipeline_collect.py
git commit -m "feat: 定义 DataBundle 和 FundamentalData 数据结构"
```

---

### Task 2: 实现指数数据采集

**Files:**
- Modify: `src/pipeline/collect.py`
- Modify: `tests/test_pipeline_collect.py`

**Interfaces:**
- Produces: `fetch_index_kline(symbol: str, days: int) -> pd.DataFrame`

- [ ] **Step 1: 编写指数数据采集测试**

在 `tests/test_pipeline_collect.py` 末尾添加：

```python
from src.pipeline.collect import fetch_index_kline


class TestFetchIndexKline:
    """指数K线数据采集测试."""

    @patch("src.pipeline.collect.ak")
    def test_returns_dataframe(self, mock_ak: MagicMock) -> None:
        """测试返回 DataFrame."""
        mock_df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1e6, 1.1e6],
        })
        mock_ak.stock_zh_index_daily.return_value = mock_df

        result = fetch_index_kline("sh000001", days=60)

        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    @patch("src.pipeline.collect.ak")
    def test_handles_api_error(self, mock_ak: MagicMock) -> None:
        """测试 API 异常时返回空 DataFrame."""
        mock_ak.stock_zh_index_daily.side_effect = Exception("API Error")

        result = fetch_index_kline("sh000001")

        assert isinstance(result, pd.DataFrame)
        assert result.empty
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py::TestFetchIndexKline -v`

Expected: FAIL

- [ ] **Step 3: 实现指数数据采集**

在 `src/pipeline/collect.py` 中添加：

```python
import akshare as ak


def fetch_index_kline(symbol: str, days: int = 120) -> pd.DataFrame:
    """获取指数日K线数据.

    Args:
        symbol: 指数代码，如 "sh000001" (上证指数), "sh000985" (全A指数)
        days: 获取最近 N 天的数据

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
        Empty DataFrame if API fails
    """
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            logger.warning(f"指数 {symbol} K线数据为空")
            return pd.DataFrame()
        # 确保日期列存在且排序
        if "date" in df.columns:
            df = df.sort_values("date").tail(days).reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"获取指数 {symbol} K线失败: {e}")
        return pd.DataFrame()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/collect.py tests/test_pipeline_collect.py
git commit -m "feat: 实现指数K线数据采集"
```

---

### Task 3: 实现个股数据批量采集

**Files:**
- Modify: `src/pipeline/collect.py`
- Modify: `tests/test_pipeline_collect.py`

**Interfaces:**
- Produces: `fetch_stock_kline(code: str, days: int) -> pd.DataFrame`
- Produces: `fetch_stock_fundamental(code: str) -> FundamentalData`
- Produces: `batch_fetch_klines(codes: list[str], days: int, max_workers: int) -> dict[str, pd.DataFrame]`

- [ ] **Step 1: 编写个股数据采集测试**

在 `tests/test_pipeline_collect.py` 末尾添加：

```python
from src.pipeline.collect import (
    batch_fetch_klines,
    fetch_stock_fundamental,
    fetch_stock_kline,
)


class TestFetchStockKline:
    """个股K线数据采集测试."""

    @patch("src.pipeline.collect.bs")
    def test_returns_dataframe(self, mock_bs: MagicMock) -> None:
        """测试返回 DataFrame."""
        mock_result = MagicMock()
        mock_result.error_code = "0"
        mock_result.error_msg = ""
        mock_result.get_row_data.return_value = [
            "2024-01-01", "10.00", "10.50", "9.80", "10.20", "1000000", "1e8",
            "10.00", "10.20", "1.02", "2.00", "10.20", "10.00", "1e6"
        ]
        mock_result.next.return_value = False
        mock_bs.query_history_k_data_plus.return_value = mock_result

        result = fetch_stock_kline("sh.600519", days=60)

        assert isinstance(result, pd.DataFrame)

    def test_handles_empty_code(self) -> None:
        """测试空代码返回空 DataFrame."""
        result = fetch_stock_kline("", days=60)

        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestFetchStockFundamental:
    """个股基本面数据采集测试."""

    def test_returns_fundamental_data(self) -> None:
        """测试返回 FundamentalData."""
        result = fetch_stock_fundamental("sh.600519")

        assert isinstance(result, FundamentalData)

    def test_handles_error_returns_neutral(self) -> None:
        """测试异常时返回中性值."""
        with patch("src.pipeline.collect.bs") as mock_bs:
            mock_bs.query_history_k_data_plus.side_effect = Exception("Error")

            result = fetch_stock_fundamental("sh.600519")

            assert isinstance(result, FundamentalData)
            assert result.pe_ttm == 50.0  # 中性值


class TestBatchFetchKlines:
    """批量K线数据采集测试."""

    def test_returns_dict(self) -> None:
        """测试返回字典."""
        with patch("src.pipeline.collect.fetch_stock_kline") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({"close": [10.0]})

            result = batch_fetch_klines(["sh.600519", "sz.000858"], days=60)

            assert isinstance(result, dict)
            assert len(result) == 2

    def test_handles_partial_failure(self) -> None:
        """测试部分失败时返回成功的结果."""
        with patch("src.pipeline.collect.fetch_stock_kline") as mock_fetch:
            mock_fetch.side_effect = [
                pd.DataFrame({"close": [10.0]}),
                pd.DataFrame(),  # 失败
            ]

            result = batch_fetch_klines(["sh.600519", "sz.000858"], days=60)

            assert len(result) == 1
            assert "sh.600519" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py::TestFetchStockKline -v`

Expected: FAIL

- [ ] **Step 3: 实现个股数据采集函数**

在 `src/pipeline/collect.py` 中添加：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

import baostock as bs


def fetch_stock_kline(code: str, days: int = 120) -> pd.DataFrame:
    """获取个股日K线数据.

    Args:
        code: 股票代码，如 "sh.600519"
        days: 获取最近 N 天的数据

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, amount
        Empty DataFrame if fails
    """
    if not code:
        return pd.DataFrame()

    try:
        # 确保已登录
        lg = bs.login()
        if lg.error_code != "0":
            logger.error(f"BaoStock login failed: {lg.error_msg}")
            return pd.DataFrame()

        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume,amount",
            start_date="2020-01-01",
            frequency="d",
            adjustflag="2",  # 前复权
        )

        if rs.error_code != "0":
            logger.warning(f"获取 {code} K线失败: {rs.error_msg}")
            return pd.DataFrame()

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=rs.fields)
        # 转换数值列
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.tail(days).reset_index(drop=True)

    except Exception as e:
        logger.error(f"获取 {code} K线异常: {e}")
        return pd.DataFrame()


def fetch_stock_fundamental(code: str) -> FundamentalData:
    """获取个股基本面数据.

    Args:
        code: 股票代码，如 "sh.600519"

    Returns:
        FundamentalData，获取失败返回中性值
    """
    try:
        lg = bs.login()
        if lg.error_code != "0":
            return FundamentalData()

        # 获取盈利能力
        rs_profit = bs.query_profit_data(code=code, year=2024, quarter=4)
        if rs_profit.error_code == "0" and rs_profit.next():
            row = rs_profit.get_row_data()
            roe = float(row[4]) if row[4] else 0.0
            eps = float(row[5]) if row[5] else 0.0
        else:
            roe, eps = 0.0, 0.0

        # 获取成长能力
        rs_growth = bs.query_growth_data(code=code, year=2024, quarter=4)
        if rs_growth.error_code == "0" and rs_growth.next():
            row = rs_growth.get_row_data()
            profit_growth = float(row[4]) if row[4] else 0.0
            revenue_growth = float(row[6]) if row[6] else 0.0
        else:
            profit_growth, revenue_growth = 0.0, 0.0

        # 获取估值数据（从K线计算）
        kline = fetch_stock_kline(code, days=5)
        if not kline.empty:
            last_close = float(kline.iloc[-1]["close"])
            # 简化处理：用EPS估算PE
            pe_ttm = last_close / eps if eps > 0 else 50.0
            pb = 1.0  # 需要额外数据，暂用默认值
        else:
            pe_ttm, pb = 50.0, 1.0

        return FundamentalData(
            roe=roe,
            eps=eps,
            profit_growth=profit_growth,
            revenue_growth=revenue_growth,
            pe_ttm=pe_ttm,
            pb=pb,
        )

    except Exception as e:
        logger.error(f"获取 {code} 基本面异常: {e}")
        return FundamentalData()


def batch_fetch_klines(
    codes: list[str],
    days: int = 120,
    max_workers: int = 4,
) -> dict[str, pd.DataFrame]:
    """批量获取个股K线数据.

    Args:
        codes: 股票代码列表
        days: 获取最近 N 天的数据
        max_workers: 最大并发数

    Returns:
        dict: code -> DataFrame
    """
    results: dict[str, pd.DataFrame] = {}

    # BaoStock 需要单会话，顺序获取
    for code in codes:
        df = fetch_stock_kline(code, days)
        if not df.empty:
            results[code] = df

    return results
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/collect.py tests/test_pipeline_collect.py
git commit -m "feat: 实现个股数据批量采集"
```

---

### Task 4: 实现 stage_collect 主函数

**Files:**
- Modify: `src/pipeline/collect.py`
- Modify: `tests/test_pipeline_collect.py`

**Interfaces:**
- Produces: `stage_collect(config: AppConfig, regime: MarketRegime | None = None) -> DataBundle`

- [ ] **Step 1: 编写 stage_collect 测试**

在 `tests/test_pipeline_collect.py` 末尾添加：

```python
from src.pipeline.collect import stage_collect
from src.config import AppConfig


class TestStageCollect:
    """stage_collect 主函数测试."""

    @patch("src.pipeline.collect.fetch_index_kline")
    @patch("src.pipeline.collect.fetch_north_flow")
    @patch("src.pipeline.collect.fetch_limit_stats")
    def test_returns_data_bundle(
        self,
        mock_limit: MagicMock,
        mock_north: MagicMock,
        mock_index: MagicMock,
    ) -> None:
        """测试返回 DataBundle."""
        mock_index.return_value = pd.DataFrame({"close": [100.0]})
        mock_north.return_value = pd.DataFrame({"net": [1e8]})
        mock_limit.return_value = {
            "limit_up_count": 10,
            "limit_down_count": 5,
            "max_consecutive": 3,
        }

        config = AppConfig()
        result = stage_collect(config, regime=None)

        assert isinstance(result, DataBundle)
        assert result.limit_up_count == 10
        assert result.limit_down_count == 5

    @patch("src.pipeline.collect.fetch_index_kline")
    def test_handles_index_failure(self, mock_index: MagicMock) -> None:
        """测试指数数据失败时仍返回 DataBundle."""
        mock_index.return_value = pd.DataFrame()

        config = AppConfig()
        result = stage_collect(config, regime=None)

        assert isinstance(result, DataBundle)
        assert result.index_kline.empty
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py::TestStageCollect -v`

Expected: FAIL

- [ ] **Step 3: 实现 stage_collect**

在 `src/pipeline/collect.py` 中添加：

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import AppConfig

if TYPE_CHECKING:
    from src.pipeline.regime import MarketRegime


def stage_collect(config: AppConfig, regime: MarketRegime | None = None) -> DataBundle:
    """阶段2: 统一数据采集.

    Args:
        config: 应用配置
        regime: 市场环境判断结果（可选，用于动态调整采集范围）

    Returns:
        DataBundle: 包含所有分析所需数据
    """
    logger.info("=== 阶段2: 数据采集 ===")

    # 1. 获取指数K线
    index_kline = fetch_index_kline("sh000985", days=120)

    # 2. 获取股票池
    stock_pool = _fetch_stock_pool(config)

    # 3. 批量获取个股K线
    codes = stock_pool["code"].tolist() if not stock_pool.empty else []
    kline_cache = batch_fetch_klines(codes, days=120)

    # 4. 获取基本面数据
    fundamental_cache = {}
    for code in codes:
        fundamental_cache[code] = fetch_stock_fundamental(code)

    # 5. 获取北向资金
    north_flow = fetch_north_flow(days=20)

    # 6. 获取涨跌停统计
    today = pd.Timestamp.now().strftime("%Y%m%d")
    limit_stats = fetch_limit_stats(today)

    # 7. 计算涨跌比
    limit_up = limit_stats["limit_up_count"]
    limit_down = limit_stats["limit_down_count"]
    advance_decline_ratio = limit_up / max(limit_down, 1)

    # 8. ETF数据（复用现有模块）
    etf_pool, etf_kline_cache = _fetch_etf_data(config)

    # 9. 获取新闻和政策分析
    news_items, policy_impacts = _fetch_news_data(config)

    return DataBundle(
        index_kline=index_kline,
        stock_pool=stock_pool,
        kline_cache=kline_cache,
        fundamental_cache=fundamental_cache,
        north_flow=north_flow,
        margin_data=None,  # P1 阶段实现
        limit_up_count=limit_up,
        limit_down_count=limit_down,
        advance_decline_ratio=advance_decline_ratio,
        macro_indicators={},  # P2 阶段实现
        sector_flow=pd.DataFrame(),  # P1 阶段实现
        news_items=news_items,
        policy_impacts=policy_impacts,
        etf_pool=etf_pool,
        etf_kline_cache=etf_kline_cache,
    )


def _fetch_stock_pool(config: AppConfig) -> pd.DataFrame:
    """获取股票池.

    复用现有 stock_filter 模块。
    """
    try:
        from src.stock_filter import get_stock_pool
        return get_stock_pool()
    except Exception as e:
        logger.error(f"获取股票池失败: {e}")
        return pd.DataFrame(columns=["code", "name"])


def _fetch_etf_data(config: AppConfig) -> tuple[list, dict[str, pd.DataFrame]]:
    """获取 ETF 数据.

    复用现有 etf_analyzer 模块。
    """
    try:
        from src.etf_analyzer import get_etf_pool, get_etf_klines
        etf_pool = get_etf_pool()
        etf_kline_cache = get_etf_klines(etf_pool)
        return etf_pool, etf_kline_cache
    except Exception as e:
        logger.error(f"获取 ETF 数据失败: {e}")
        return [], {}


def _fetch_news_data(config: AppConfig) -> tuple[list, list]:
    """获取新闻和政策分析数据.

    复用现有 news_analysis 模块。

    Returns:
        tuple: (news_items, policy_impacts)
    """
    try:
        from src.news_analysis import fetch_news, analyze_policy
        news_items = fetch_news()
        policy_impacts = analyze_policy(news_items) if news_items else []
        return news_items, policy_impacts
    except Exception as e:
        logger.warning(f"获取新闻数据失败，使用空列表: {e}")
        return [], []
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_collect.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/collect.py tests/test_pipeline_collect.py
git commit -m "feat: 实现 stage_collect 主函数"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_pipeline_collect.py -v`
- [ ] DataBundle 包含设计文档中所有字段
- [ ] 单只股票获取失败不影响整体流程
- [ ] 复用现有 stock_filter 和 etf_analyzer 模块
