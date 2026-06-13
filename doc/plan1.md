# A股买卖信号系统实现计划

## Context

用户是一个代码小白，希望将现有的A股分析程序改造成一个直观的买卖信号系统。当前系统存在以下问题：

### 功能缺失
- 直观的买卖信号（0-100分制，三档划分）
- 关键价位（支撑位/压力位）
- 板块对比（行业内排名 + 对比板块ETF）
- 历史准确率（30天/90天/180天多周期对比）
- 股票链接

### 现有报告问题（参考 doc/report/4.txt）
- 只有风险警示，没有推荐（报告生成器用70/30阈值，但配置已改成50/20）
- 基本面评分都是0分（数据获取可能有问题）
- ETF评分都是15分（行业趋势评分是固定值）
- 格式不直观，缺少可视化元素

### 性能问题（运行时长 50-100 分钟）
| 操作 | 耗时 | 原因 |
|------|------|------|
| `get_fundamental_data_batch` | 30-60分钟 | 200只股票 × 最多10次API调用 = 2000次串行调用 |
| `get_stock_hist_batch_baostock` | 15-30分钟 | 200次串行BaoStock查询 |
| ETF数据获取 | 6-10分钟 | 重复获取 + 每次新建会话 |
| 其他 | 1-2分钟 | 新闻、技术分析、图表生成 |

## 需求总结

| 维度 | 用户选择 |
|------|----------|
| 信号形式 | 0-100分制，三档划分 |
| 分数解读 | 0-30=卖出区 🔴，30-70=观望区 🟡，70-100=买入区 🟢 |
| 判断依据 | 综合评分 + 资金流向 |
| 更新频率 | 每日早盘结束后（11:30后） |
| 关键价位 | 技术面+基本面综合计算 |
| 板块对比 | 行业内排名 + 对比板块ETF |
| 历史准确率 | 30天/90天/180天多周期对比，区间最优价计算 |
| 股票链接 | 同花顺详情链接 |

## 阈值体系统一方案

**核心原则**：全系统使用一套三档阈值（70/30），main.py 不再做阈值过滤。

| 位置 | 修改前 | 修改后 |
|------|--------|--------|
| `config.py` `AppConfig` | `score_threshold_high=50`, `score_threshold_low=20` | 删除这两个字段 |
| `config.py` 新增 `BuySellSignalConfig` | — | `buy_threshold=70`, `sell_threshold=30` |
| `main.py` 过滤逻辑 | 只保留 >=50 或 <20 的结果 | 保留所有结果（不过滤） |
| `report_generator.py` | 硬编码 70/30 | 改用 `BuySellSignalConfig` 的配置值 |

**效果**：
- 所有股票/ETF 都进入 report
- report 内部按 70/30 划分三档展示：买入区(≥70)、观望区(30-69)、卖出区(<30)
- 观望区的股票也会展示，不再被静默丢弃

**关联修改**：
- `src/main.py` 中 `analyze_single_stock` 和 `analyze_single_etf` 调用了 `judge_score(total, config.score_threshold_high, config.score_threshold_low)`
- 删除 `score_threshold_high/low` 后，需改为 `judge_score(total, config.buy_sell_signal.buy_threshold, config.buy_sell_signal.sell_threshold)`
- `src/scoring.py` 中的 `judge_score` 函数签名不变，只改调用处的参数来源

## 实现方案

### Phase 0: 性能优化（优先级最高）(2-3天)

#### 0.1 修复报告生成器阈值bug
**文件**: `src/report_generator.py`

```python
# 当前（错误）：
stock_recommend = [r for r in stock_results if r.total_score >= 70]
stock_risk = [r for r in stock_results if r.total_score < 30]

# 修复后：使用三档划分，不再硬编码
# 具体修改见 Phase 5 的报告生成器重构
```

#### 0.2 并行化独立的数据获取阶段
**文件**: `src/main.py`

```python
from concurrent.futures import ThreadPoolExecutor

# stock_pool 和 etf_pool 有依赖关系（etf_pool 不依赖 stock_pool），
# 但 news 不依赖它们，可以并行
with ThreadPoolExecutor(max_workers=3) as executor:
    stock_future = executor.submit(get_stock_pool, config.filter)
    etf_future = executor.submit(get_etf_pool, config)
    news_future = executor.submit(fetch_news)

    stock_pool = stock_future.result()
    etf_pool = etf_future.result()
    news = news_future.result()
```

#### 0.3 并行化批量数据获取
**文件**: `src/main.py`

```python
def parallel_batch_fetch(codes, fetch_func, workers=4):
    """将股票代码分组，并行获取数据。

    使用列表切片确保不丢失尾部元素。
    """
    chunk_size = (len(codes) + workers - 1) // workers  # 向上取整
    chunks = [codes[i:i+chunk_size] for i in range(0, len(codes), chunk_size)]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_func, chunk) for chunk in chunks]
        results = {}
        for future in futures:
            try:
                results.update(future.result())
            except Exception as e:
                logger.warning(f"批量获取部分失败: {e}")
    return results

# 使用
kline_cache = parallel_batch_fetch(stock_codes, get_stock_hist_batch_baostock, workers=4)
fund_cache = parallel_batch_fetch(stock_codes, get_fundamental_data_batch, workers=4)
```

**注意**：BaoStock session 不能跨线程共享。需要确保 `get_stock_hist_batch_baostock` 和 `get_fundamental_data_batch` 内部各自创建独立的 session，或者改为每个 chunk 使用独立 session。

#### 0.4 减少基本面API调用次数
**文件**: `src/fundamental_analysis.py`

```python
# 当前：每只股票最多尝试5个季度
def _fetch_single_with_session(code, session, max_quarters=5):

# 优化后：只尝试最近2个季度
def _fetch_single_with_session(code, session, max_quarters=2):
```

#### 0.5 消除ETF重复获取
**文件**: `src/main.py`

```python
# 当前：get_etf_pool 获取一次，main.py 又获取一次
# 优化后：复用 get_etf_pool 已获取的数据，ETF K-line 统一获取一次
etf_pool = get_etf_pool(config)
etf_kline_cache = {}
for etf in etf_pool:
    # get_etf_pool 内部已经获取了 K-line，直接复用
    # 如果 EtfInfo 没有 kline_data 属性，则统一批量获取
    pass  # 具体实现取决于 EtfInfo 的结构
```

#### 0.6 添加磁盘缓存
**文件**: `src/cache_manager.py` (新增)

```python
import json
import os
from datetime import datetime

CACHE_DIR = "cache"
CACHE_TTL = 86400  # 24小时

def get_cached_data(key: str):
    """获取缓存数据。使用 JSON 格式，避免 pickle 的安全和兼容性问题。"""
    cache_file = f"{CACHE_DIR}/{key}.json"
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if datetime.now().timestamp() - mtime < CACHE_TTL:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None

def set_cached_data(key: str, data) -> None:
    """设置缓存数据。使用 JSON 格式。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{key}.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, default=str)
```

**说明**：使用 JSON 而非 pickle，避免安全风险和 Python 版本兼容性问题。DataFrame 数据通过 `to_dict(orient='records')` 序列化。

#### 0.7 使用缓存的主程序流程
**文件**: `src/main.py`

```python
from cache_manager import get_cached_data, set_cached_data

# 尝试从缓存获取
kline_cache = get_cached_data(f"kline_{report_date}")
if kline_cache is None:
    kline_cache = parallel_batch_fetch(stock_codes, get_stock_hist_batch_baostock)
    set_cached_data(f"kline_{report_date}", kline_cache)

fund_cache = get_cached_data(f"fund_{report_date}")
if fund_cache is None:
    fund_cache = parallel_batch_fetch(stock_codes, get_fundamental_data_batch)
    set_cached_data(f"fund_{report_date}", fund_cache)
```

### 性能优化预期效果

| 场景 | 当前耗时 | 优化后耗时 |
|------|----------|------------|
| 首次运行 | 50-100分钟 | **10-15分钟** |
| 重复运行（有缓存） | 50-100分钟 | **1-2分钟** |

---

### Phase 1: 新增配置和数据结构 (1天)

#### 1.0 前置修改（为后续 Phase 做准备）

**文件**: `src/scoring.py`

将 `get_industry_trend_score` 内部的 `industry_etf_map` 提取为模块级常量 `INDUSTRY_ETF_MAP`，供 `sector_analysis.py` 导入使用：

```python
# 提取为模块级常量（原来是 get_industry_trend_score 的局部变量）
INDUSTRY_ETF_MAP: dict[str, str] = {
    "半导体": "512480",
    "芯片": "512480",
    "新能源": "516160",
    # ... 其余 29 个映射保持不变 ...
}
```

**文件**: `src/technical_analysis.py`

该文件已有一个私有函数 `_df_to_kline_data(df, code, days)`（行 210-272），
以及两个公开包装函数 `get_kline_data` 和 `get_kline_data_from_cache`。

**不需要重新提取**，直接复用已有的公开 API：

```python
# 直接使用已有的公开函数
from technical_analysis import get_kline_data_from_cache

# 用法：kline_data = get_kline_data_from_cache(df, code, days=60)
```

**文件**: `src/config.py`

新增配置类，并嵌入 `AppConfig`：

```python
@dataclass
class BuySellSignalConfig:
    """买卖信号配置。"""
    # 三档阈值
    buy_threshold: float = 70.0      # 买入区阈值
    sell_threshold: float = 30.0     # 卖出区阈值
    # 关键价位计算权重
    ma_weight: float = 0.4           # 均线权重（支撑位/压力位中均线的占比，剩余为近期高低点）
    # 历史准确率周期
    history_days: list[int] = field(default_factory=lambda: [30, 90, 180])

@dataclass
class AppConfig:
    # ... 现有字段保持不变 ...
    buy_sell_signal: BuySellSignalConfig = field(default_factory=BuySellSignalConfig)  # 新增
    # 删除: score_threshold_high 和 score_threshold_low（由 BuySellSignalConfig 的阈值替代）
```

**使用方式**：`config.buy_sell_signal.buy_threshold`、`config.buy_sell_signal.ma_weight` 等。

**文件**: `src/signal.py` (新增)

将买卖信号相关的数据类从 `scoring.py` 中分离出来，保持职责单一：

```python
from dataclasses import dataclass, field
from scoring import ScoreResult

@dataclass
class KeyPrice:
    """关键价位。"""
    current_price: float       # 当前价
    support_price: float       # 支撑位
    resistance_price: float    # 压力位
    target_price: float        # 目标价
    stop_loss: float           # 止损价

@dataclass
class SectorComparison:
    """板块对比。"""
    sector_name: str           # 板块名称
    rank_in_sector: int        # 板块内排名
    total_in_sector: int       # 板块内总数
    percentile: float          # 百分位（超过多少比例）
    vs_etf_return: float       # 对比板块ETF的超额收益

@dataclass
class HistoricalAccuracy:
    """历史准确率。"""
    period_days: int           # 周期天数
    accuracy_rate: float       # 准确率
    avg_return: float          # 平均收益
    total_signals: int         # 信号总数

@dataclass
class BuySellSignal:
    """买卖信号。"""
    code: str
    name: str
    is_etf: bool
    signal_score: int          # 0-100分
    signal_zone: str           # "买入区" / "观望区" / "卖出区"
    signal_emoji: str          # 🟢 / 🟡 / 🔴
    # 各维度评分
    technical_score: float
    fund_flow_score: float
    fundamental_score: float | None
    news_score: float
    # 关键价位
    key_prices: KeyPrice
    # 板块对比
    sector_comparison: SectorComparison | None
    # 历史准确率
    historical_accuracy: list[HistoricalAccuracy]
    # 链接
    link: str
    # 原始评分结果
    score_result: ScoreResult
```

**说明**：
- `BuySellSignal` 放在独立的 `src/signal.py` 中，避免 `scoring.py` 变得臃肿
- 新增 `news_score` 字段，避免嵌套访问 `score_result.news_score`
- 删除了 `valuation_weight` 配置项（BaoStock 不提供估值数据，该配置是死代码）

### Phase 2: 实现关键价位计算 (1天)

**文件**: `src/price_analysis.py` (新增)

```python
import logging
from signal import KeyPrice
from config import BuySellSignalConfig

logger = logging.getLogger(__name__)

def calculate_key_prices(
    code: str,
    kline,
    config: BuySellSignalConfig,
) -> KeyPrice | None:
    """计算关键价位。

    综合技术面计算：
    1. 支撑位：MA20、近期低点、布林带下轨
    2. 压力位：MA60、近期高点、布林带上轨
    3. 目标价：估值中枢、技术目标位
    4. 止损价：支撑位下方3-5%

    返回 None 如果数据不足。
    """
    try:
        if len(kline.closes) < 20:
            logger.warning(f"{code}: K线数据不足20天，跳过关键价位计算")
            return None

        current_price = kline.closes[-1]

        # 技术面支撑位（取多个支撑的加权平均）
        ma20_support = kline.ma20[-1] if kline.ma20 else min(kline.lows[-20:])
        recent_low = min(kline.lows[-20:])
        support_price = ma20_support * config.ma_weight + recent_low * (1 - config.ma_weight)

        # 技术面压力位
        ma60_resistance = kline.ma60[-1] if kline.ma60 and len(kline.ma60) > 0 else max(kline.highs[-20:])
        recent_high = max(kline.highs[-20:])
        resistance_price = ma60_resistance * config.ma_weight + recent_high * (1 - config.ma_weight)

        # 确保支撑位 < 当前价 < 压力位
        if support_price >= current_price:
            support_price = current_price * 0.95
        if resistance_price <= current_price:
            resistance_price = current_price * 1.05

        # 目标价（突破压力位后5%）
        target_price = resistance_price * 1.05

        # 止损价（支撑位下方5%）
        stop_loss = support_price * 0.95

        return KeyPrice(
            current_price=round(current_price, 2),
            support_price=round(support_price, 2),
            resistance_price=round(resistance_price, 2),
            target_price=round(target_price, 2),
            stop_loss=round(stop_loss, 2),
        )
    except Exception as e:
        logger.error(f"{code}: 关键价位计算失败: {e}")
        return None
```

### Phase 3: 实现板块对比功能 (1天)

**架构说明**：板块对比需要所有股票的评分数据，因此采用**两阶段流水线**：

1. **阶段一**：`main.py` 完成所有股票的评分，结果存入 `score_cache: dict[str, float]`
2. **阶段二**：调用 `analyze_sector_comparison`，传入 `score_cache` 做排名

**文件**: `src/sector_analysis.py` (新增)

```python
import logging
import pandas as pd
from signal import SectorComparison
from scoring import INDUSTRY_ETF_MAP  # 从 scoring.py 的模块级常量导入

logger = logging.getLogger(__name__)

def analyze_sector_comparison(
    code: str,
    industry: str,
    score: float,
    kline,
    stock_pool: pd.DataFrame,
    score_cache: dict[str, float],
    etf_kline_cache: dict[str, object],
) -> SectorComparison | None:
    """分析板块对比。

    1. 行业内排名：在同行业股票中的评分排名（使用 score_cache 中已计算的评分）
    2. 对比板块ETF：个股表现 vs 板块ETF表现

    Args:
        code: 股票代码
        industry: 行业名称
        score: 当前股票评分
        kline: 当前股票K线数据（KlineData 对象）
        stock_pool: 股票池 DataFrame（含 code, industry 列）
        score_cache: 所有股票的评分缓存 {code: score}
        etf_kline_cache: ETF K线缓存 {etf_code: KlineData}
    """
    try:
        # 找到同行业股票
        sector_stocks = stock_pool[stock_pool['industry'] == industry]
        if len(sector_stocks) < 2:
            logger.debug(f"{code}: 同行业股票不足2只，跳过板块对比")
            return None

        # 从 score_cache 中获取同行业股票的评分
        sector_scores = []
        for _, stock in sector_stocks.iterrows():
            stock_code = stock['code']
            stock_score = score_cache.get(stock_code)
            if stock_score is not None:
                sector_scores.append((stock_code, stock_score))

        if len(sector_scores) < 2:
            return None

        # 按评分降序排列
        sector_scores.sort(key=lambda x: x[1], reverse=True)
        rank = next((i for i, (c, _) in enumerate(sector_scores, 1) if c == code), len(sector_scores))
        percentile = (1 - rank / len(sector_scores)) * 100

        # 找到对应ETF并计算超额收益（使用模块级常量 INDUSTRY_ETF_MAP）
        vs_etf_return = 0.0
        etf_code = INDUSTRY_ETF_MAP.get(industry)
        if etf_code and etf_code in etf_kline_cache:
            etf_kline = etf_kline_cache[etf_code]
            if len(kline.closes) >= 20 and len(etf_kline.closes) >= 20:
                stock_return = (kline.closes[-1] / kline.closes[-20] - 1) * 100
                etf_return = (etf_kline.closes[-1] / etf_kline.closes[-20] - 1) * 100
                vs_etf_return = stock_return - etf_return

        return SectorComparison(
            sector_name=_get_sector_display_name(industry),
            rank_in_sector=rank,
            total_in_sector=len(sector_scores),
            percentile=round(percentile, 1),
            vs_etf_return=round(vs_etf_return, 2),
        )
    except Exception as e:
        logger.error(f"{code}: 板块对比分析失败: {e}")
        return None

def _get_sector_display_name(industry: str) -> str:
    """获取行业显示名称。"""
    # 如果行业名称已经是中文，直接返回
    # 否则从 industry_etf_map 的 ETF 名称中提取
    return industry or "未知行业"
```

**文件**: `src/main.py` (修改流程)

**前置步骤**：将 `kline_cache` 中的 `pd.DataFrame` 转换为 `KlineData` 对象。
现有代码中 `technical_analysis.py` 已有公开函数 `get_kline_data_from_cache(df, code, days)`，
直接复用即可，无需额外提取。

```python
from technical_analysis import get_kline_data_from_cache

# 将 DataFrame 缓存转换为 KlineData 缓存（复用已有公开 API）
kline_data_cache = {}
for code, df in kline_cache.items():
    try:
        kline_data_cache[code] = get_kline_data_from_cache(df, code, days=config.lookback_days)
    except Exception as e:
        logger.warning(f"{code}: K线数据转换失败: {e}")

# ETF K-line 同样转换
etf_kline_data_cache = {}
for code, df in etf_kline_cache.items():
    try:
        etf_kline_data_cache[code] = get_kline_data_from_cache(df, code, days=config.lookback_days)
    except Exception as e:
        logger.warning(f"{code}: ETF K线数据转换失败: {e}")
```

```python
# 两阶段流水线
# 阶段一：完成所有股票评分
score_cache = {}
stock_signals = []
for _, row in stock_pool.iterrows():
    code = row['code']
    signal = analyze_single_stock(code, row, kline_data_cache, fund_cache, ...)
    if signal:
        stock_signals.append(signal)
        score_cache[code] = signal.signal_score

# 批量记录所有信号（避免每只股票单独写文件）
from history_tracker import record_signals_batch
today = datetime.now().strftime('%Y-%m-%d')
record_signals_batch([
    (s.code, s.signal_score, s.key_prices.current_price, today)
    for s in stock_signals
])

# 阶段二：使用 score_cache 做板块对比
for signal in stock_signals:
    sector_comp = analyze_sector_comparison(
        code=signal.code,
        industry=stock_pool[stock_pool['code'] == signal.code]['industry'].iloc[0],
        score=signal.signal_score,
        kline=kline_data_cache.get(signal.code),
        stock_pool=stock_pool,
        score_cache=score_cache,
        etf_kline_cache=etf_kline_data_cache,
    )
    signal.sector_comparison = sector_comp
```

### Phase 4: 实现历史准确率追踪 (1天)

**文件**: `src/history_tracker.py` (新增)

```python
import json
import os
import logging
from datetime import datetime, timedelta
from signal import HistoricalAccuracy

logger = logging.getLogger(__name__)

HISTORY_FILE = "data/signal_history.json"

def load_signal_history() -> dict:
    """加载历史信号数据。"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"加载历史数据失败: {e}")
    return {}

def save_signal_history(history: dict) -> None:
    """保存历史信号数据。"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def record_signal(code: str, signal_score: int, price: float, date: str) -> None:
    """记录单只股票的信号。"""
    history = load_signal_history()
    if code not in history:
        history[code] = []
    history[code].append({
        'date': date,
        'signal_score': signal_score,
        'price': price,
    })
    # 只保留最近365天的数据
    cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    history[code] = [r for r in history[code] if r['date'] >= cutoff]
    save_signal_history(history)

def record_signals_batch(records: list[tuple[str, int, float, str]]) -> None:
    """批量记录多只股票的信号。只读写文件一次，避免200次I/O。

    Args:
        records: [(code, signal_score, price, date), ...]
    """
    history = load_signal_history()
    cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    for code, signal_score, price, date in records:
        if code not in history:
            history[code] = []
        history[code].append({
            'date': date,
            'signal_score': signal_score,
            'price': price,
        })
        history[code] = [r for r in history[code] if r['date'] >= cutoff]
    save_signal_history(history)

def calculate_historical_accuracy(
    code: str,
    periods: list[int] = [30, 90, 180],
) -> list[HistoricalAccuracy]:
    """计算历史准确率。

    使用区间最优价计算：
    - 买入信号（>=70）：看5天内最高价，如果最高价 > 信号时价格 → 准确
    - 卖出信号（<30）：看5天内最低价，如果最低价 < 信号时价格 → 准确
    - 观望信号：不计入准确率
    """
    history = load_signal_history()
    if code not in history:
        return [HistoricalAccuracy(p, 0, 0, 0) for p in periods]

    records = history[code]
    # 按日期排序，方便查找区间数据
    records_by_date = {r['date']: r for r in records}

    results = []
    for period in periods:
        cutoff = (datetime.now() - timedelta(days=period)).strftime('%Y-%m-%d')
        period_records = [r for r in records if r['date'] >= cutoff]

        if not period_records:
            results.append(HistoricalAccuracy(period, 0, 0, 0))
            continue

        correct = 0
        total_return = 0
        valid_signals = 0

        for record in period_records:
            signal_score = record['signal_score']
            signal_price = record['price']

            # 只统计买入或卖出信号
            if signal_score >= 70 or signal_score < 30:
                # 获取信号后5天内的所有价格数据
                signal_date = datetime.strptime(record['date'], '%Y-%m-%d')
                future_prices = []
                for day_offset in range(1, 6):
                    future_date = (signal_date + timedelta(days=day_offset)).strftime('%Y-%m-%d')
                    if future_date in records_by_date:
                        future_prices.append(records_by_date[future_date]['price'])

                if not future_prices:
                    continue

                if signal_score >= 70:
                    # 买入信号：看5天内最高价
                    best_price = max(future_prices)
                    actual_return = (best_price / signal_price - 1) * 100
                    if best_price > signal_price:
                        correct += 1
                else:
                    # 卖出信号：看5天内最低价
                    best_price = min(future_prices)
                    actual_return = (best_price / signal_price - 1) * 100
                    if best_price < signal_price:
                        correct += 1

                total_return += actual_return
                valid_signals += 1

        accuracy_rate = (correct / valid_signals * 100) if valid_signals > 0 else 0
        avg_return = (total_return / valid_signals) if valid_signals > 0 else 0

        results.append(HistoricalAccuracy(
            period_days=period,
            accuracy_rate=round(accuracy_rate, 1),
            avg_return=round(avg_return, 2),
            total_signals=valid_signals,
        ))

    return results
```

### Phase 5: 修改报告生成器 (1天)

**文件**: `src/report_generator.py`

修改 `_format_stock_item` 和 `_format_etf_item` 函数，展示新的信号格式：

```python
def _format_signal_card(signal: BuySellSignal) -> str:
    """格式化买卖信号卡片。使用缩进列表风格，避免 box drawing 对齐问题。"""
    lines = []

    # 标题行
    lines.append(f"### {signal.signal_emoji} {signal.name} ({signal.code}) — {signal.signal_score}/100 {signal.signal_zone}")
    lines.append("")

    # 信号维度
    lines.append("📊 **信号维度**")
    lines.append(f"  ├─ 技术面: {signal.technical_score:.0f}分")
    lines.append(f"  ├─ 资金面: {signal.fund_flow_score:.0f}分")
    if signal.fundamental_score is not None:
        lines.append(f"  ├─ 基本面: {signal.fundamental_score:.0f}分")
    lines.append(f"  └─ 情绪面: {signal.news_score:.0f}分")
    lines.append("")

    # 关键价位
    lines.append("📍 **关键价位**")
    lines.append(f"  ├─ 当前价: {signal.key_prices.current_price:.2f}")
    lines.append(f"  ├─ 支撑位: {signal.key_prices.support_price:.2f}")
    lines.append(f"  ├─ 压力位: {signal.key_prices.resistance_price:.2f}")
    lines.append(f"  ├─ 目标价: {signal.key_prices.target_price:.2f}")
    lines.append(f"  └─ 止损价: {signal.key_prices.stop_loss:.2f}")
    lines.append("")

    # 板块对比
    if signal.sector_comparison:
        lines.append("📈 **板块对比**")
        lines.append(f"  ├─ {signal.sector_comparison.sector_name}排名: "
                     f"第{signal.sector_comparison.rank_in_sector}/"
                     f"{signal.sector_comparison.total_in_sector} "
                     f"(超过{signal.sector_comparison.percentile:.0f}%的同行)")
        vs_label = "跑赢" if signal.sector_comparison.vs_etf_return >= 0 else "跑输"
        lines.append(f"  └─ vs 板块ETF: {vs_label}板块 "
                     f"{abs(signal.sector_comparison.vs_etf_return):.1f}%")
        lines.append("")

    # 历史准确率
    if signal.historical_accuracy:
        lines.append("📜 **历史信号准确率**")
        for i, acc in enumerate(signal.historical_accuracy):
            prefix = "├─" if i < len(signal.historical_accuracy) - 1 else "└─"
            lines.append(f"  {prefix} 近{acc.period_days}天: "
                         f"{acc.accuracy_rate:.0f}%准确, "
                         f"平均收益 {acc.avg_return:+.1f}%")
        lines.append("")

    # 链接
    lines.append(f"🔗 [同花顺详情]({signal.link})")
    lines.append("[附K线图 + MACD图]")
    lines.append("")

    return "\n".join(lines)

def generate_report(stock_signals: list, etf_signals: list, policy_impacts, report_date, signal_config=None):
    """生成报告。使用三档划分展示所有结果。

    Args:
        stock_signals: list[BuySellSignal] — 已经在 main.py 中构建好的股票信号
        etf_signals: list[BuySellSignal] — 已经在 main.py 中构建好的 ETF 信号
        policy_impacts: 政策新闻列表
        report_date: 报告日期
        signal_config: BuySellSignal 配置
    """
    from config import BuySellSignalConfig
    if signal_config is None:
        signal_config = BuySellSignalConfig()

    buy_threshold = signal_config.buy_threshold  # 70
    sell_threshold = signal_config.sell_threshold  # 30

    # 三档划分
    stock_buy = [s for s in stock_signals if s.signal_score >= buy_threshold]
    stock_watch = [s for s in stock_signals if sell_threshold <= s.signal_score < buy_threshold]
    stock_sell = [s for s in stock_signals if s.signal_score < sell_threshold]

    etf_buy = [s for s in etf_signals if s.signal_score >= buy_threshold]
    etf_watch = [s for s in etf_signals if sell_threshold <= s.signal_score < buy_threshold]
    etf_sell = [s for s in etf_signals if s.signal_score < sell_threshold]

    lines = [f"# A股每日分析报告 — {report_date}", ""]

    # 买入区
    if stock_buy or etf_buy:
        lines.append("## 🟢 买入区")
        lines.append("")
        for s in sorted(stock_buy, key=lambda x: x.signal_score, reverse=True):
            lines.append(_format_signal_card(s))
        for s in sorted(etf_buy, key=lambda x: x.signal_score, reverse=True):
            lines.append(_format_signal_card(s))

    # 观望区
    if stock_watch or etf_watch:
        lines.append("## 🟡 观望区")
        lines.append("")
        for s in sorted(stock_watch, key=lambda x: x.signal_score, reverse=True):
            lines.append(_format_signal_card(s))
        for s in sorted(etf_watch, key=lambda x: x.signal_score, reverse=True):
            lines.append(_format_signal_card(s))

    # 卖出区
    if stock_sell or etf_sell:
        lines.append("## 🔴 卖出区")
        lines.append("")
        for s in sorted(stock_sell, key=lambda x: x.signal_score):
            lines.append(_format_signal_card(s))
        for s in sorted(etf_sell, key=lambda x: x.signal_score):
            lines.append(_format_signal_card(s))

    # 政策新闻
    if policy_impacts:
        lines.append("## 📰 政策新闻")
        lines.append("")
        for impact in policy_impacts:
            lines.append(f"- {impact}")
        lines.append("")

    # 免责声明
    lines.append("---")
    lines.append("*本报告仅供参考，不构成投资建议。*")

    return "\n".join(lines)
```

### Phase 6: 修改主程序 (1天)

**文件**: `src/main.py`

在 `analyze_single_stock` 和 `analyze_single_etf` 函数中调用新的模块：

```python
from signal import BuySellSignal, KeyPrice
from price_analysis import calculate_key_prices
from history_tracker import calculate_historical_accuracy
# 注意：record_signal 不在这里调用，改为 main.py 中批量调用 record_signals_batch

def analyze_single_stock(...) -> BuySellSignal | None:
    """分析单只股票，返回买卖信号。"""
    try:
        # 原有的评分逻辑...
        score_result = ...  # 已有逻辑

        # 计算关键价位（kline 参数已经是 KlineData 对象，由 main.py 转换）
        key_prices = calculate_key_prices(code, kline, config.buy_sell_signal)
        if key_prices is None:
            # 数据不足时使用简化的关键价位
            key_prices = KeyPrice(
                current_price=kline.closes[-1],
                support_price=round(kline.closes[-1] * 0.95, 2),
                resistance_price=round(kline.closes[-1] * 1.05, 2),
                target_price=round(kline.closes[-1] * 1.10, 2),
                stop_loss=round(kline.closes[-1] * 0.90, 2),
            )

        # 历史准确率
        historical_accuracy = calculate_historical_accuracy(code, config.buy_sell_signal.history_days)

        # 生成信号（记录信号在 main.py 中批量执行）
        signal_score = int(score_result.total_score)
        if signal_score >= config.buy_sell_signal.buy_threshold:
            signal_zone = "买入区"
            signal_emoji = "🟢"
        elif signal_score >= config.buy_sell_signal.sell_threshold:
            signal_zone = "观望区"
            signal_emoji = "🟡"
        else:
            signal_zone = "卖出区"
            signal_emoji = "🔴"

        return BuySellSignal(
            code=code,
            name=name,
            is_etf=False,
            signal_score=signal_score,
            signal_zone=signal_zone,
            signal_emoji=signal_emoji,
            technical_score=score_result.technical_score,
            fund_flow_score=0,
            fundamental_score=score_result.fundamental_score,
            news_score=score_result.news_score,
            key_prices=key_prices,
            sector_comparison=None,  # 阶段二补算
            historical_accuracy=historical_accuracy,
            link=f"https://stockpage.10jqka.com.cn/{code}/",
            score_result=score_result,
        )
    except Exception as e:
        logger.error(f"{code}: 分析失败: {e}")
        return None

def main():
    """主程序流程（两阶段流水线）。"""
    # ... 加载配置、获取数据 ...

    # DataFrame → KlineData 转换（复用已有 API，详见 Phase 3）
    from technical_analysis import get_kline_data_from_cache
    kline_data_cache = {}
    for code, df in kline_cache.items():
        try:
            kline_data_cache[code] = get_kline_data_from_cache(df, code, days=config.lookback_days)
        except Exception as e:
            logger.warning(f"{code}: K线数据转换失败: {e}")
    etf_kline_data_cache = {}
    for code, df in etf_kline_cache.items():
        try:
            etf_kline_data_cache[code] = get_kline_data_from_cache(df, code, days=config.lookback_days)
        except Exception as e:
            logger.warning(f"{code}: ETF K线数据转换失败: {e}")

    # 阶段一：完成所有股票评分
    score_cache = {}
    stock_signals = []
    for _, row in stock_pool.iterrows():
        signal = analyze_single_stock(row['code'], row, kline_data_cache, fund_cache, ...)
        if signal:
            stock_signals.append(signal)
            score_cache[signal.code] = signal.signal_score

    # 批量记录所有信号
    from history_tracker import record_signals_batch
    today = datetime.now().strftime('%Y-%m-%d')
    record_signals_batch([
        (s.code, s.signal_score, s.key_prices.current_price, today)
        for s in stock_signals
    ])

    # 阶段二：板块对比（需要所有股票评分）
    for signal in stock_signals:
        industry = stock_pool[stock_pool['code'] == signal.code]['industry'].iloc[0]
        signal.sector_comparison = analyze_sector_comparison(
            code=signal.code,
            industry=industry,
            score=signal.signal_score,
            kline=kline_data_cache.get(signal.code),
            stock_pool=stock_pool,
            score_cache=score_cache,
            etf_kline_cache=etf_kline_data_cache,
        )

    # ETF分析（类似股票，将 ScoreResult 转换为 BuySellSignal）
    etf_signals = []
    for etf in etf_pool:
        score_result = analyze_single_etf(etf, policy_impacts, config, etf_kline_cache)
        if score_result:
            kline = etf_kline_data_cache.get(etf.code)
            key_prices = calculate_key_prices(etf.code, kline, config.buy_sell_signal) if kline else None
            if key_prices is None and kline:
                key_prices = KeyPrice(
                    current_price=kline.closes[-1],
                    support_price=round(kline.closes[-1] * 0.95, 2),
                    resistance_price=round(kline.closes[-1] * 1.05, 2),
                    target_price=round(kline.closes[-1] * 1.10, 2),
                    stop_loss=round(kline.closes[-1] * 0.90, 2),
                )
            signal_score = int(score_result.total_score)
            if signal_score >= config.buy_sell_signal.buy_threshold:
                signal_zone, signal_emoji = "买入区", "🟢"
            elif signal_score >= config.buy_sell_signal.sell_threshold:
                signal_zone, signal_emoji = "观望区", "🟡"
            else:
                signal_zone, signal_emoji = "卖出区", "🔴"
            etf_signals.append(BuySellSignal(
                code=etf.code, name=etf.name, is_etf=True,
                signal_score=signal_score, signal_zone=signal_zone, signal_emoji=signal_emoji,
                technical_score=score_result.technical_score,
                fund_flow_score=score_result.fund_flow_score or 0,
                fundamental_score=None,
                news_score=score_result.news_score,
                key_prices=key_prices,
                sector_comparison=None,  # ETF 不做板块对比
                historical_accuracy=calculate_historical_accuracy(etf.code, config.buy_sell_signal.history_days),
                link=f"https://stockpage.10jqka.com.cn/{etf.code}/",
                score_result=score_result,
            ))

    # 图表生成...
    # 报告生成（直接传入 BuySellSignal 列表）
    report = generate_report(stock_signals, etf_signals, policy_impacts, report_date)
```

## 实现步骤

### Step 0: 性能优化（优先级最高）(2-3天)

#### 0.1 修复报告生成器阈值bug
**文件**: `src/report_generator.py`
- 删除硬编码的 70/30 阈值
- 改用 `BuySellSignalConfig` 的配置值

#### 0.2 并行化独立的数据获取阶段
**文件**: `src/main.py`
- 并行获取 stock_pool、etf_pool、news
- 注意 BaoStock session 的线程安全

#### 0.3 并行化批量数据获取
**文件**: `src/main.py`
- 将200只股票分成4组，并行获取K线和基本面数据
- 修复分组逻辑，使用向上取整确保不丢失尾部元素
- 每个 chunk 使用独立的 BaoStock session

#### 0.4 减少基本面API调用次数
**文件**: `src/fundamental_analysis.py`
- 从5个季度减少到2个季度

#### 0.5 消除ETF重复获取
**文件**: `src/main.py`
- 复用 get_etf_pool 的结果

#### 0.6 添加磁盘缓存
**文件**: `src/cache_manager.py` (新增)
- 使用 JSON 格式，24小时 TTL

#### 0.7 使用缓存的主程序流程
**文件**: `src/main.py`
- K线和基本面数据使用缓存

---

### Step 1: 新增配置和数据结构 (1天)
- 修改 `src/scoring.py`，将 `industry_etf_map` 提取为模块级常量 `INDUSTRY_ETF_MAP`
- 修改 `src/config.py`，新增 `BuySellSignalConfig` 并嵌入 `AppConfig`，删除 `score_threshold_high/low`
- 新增 `src/signal.py`，存放 `BuySellSignal`、`KeyPrice`、`SectorComparison`、`HistoricalAccuracy` 数据类

### Step 2: 实现关键价位计算 (1天)
- 新增 `src/price_analysis.py`
- 实现 `calculate_key_prices` 函数
- 添加错误处理（数据不足时返回 None）
- 编写单元测试

### Step 3: 实现板块对比功能 ✅ (1天)
- 新增 `src/sector_analysis.py`
- 实现 `analyze_sector_comparison` 函数
- 修改 `src/main.py` 为两阶段流水线
- 编写单元测试

### Step 4: 实现历史准确率追踪 (1天)
- 新增 `src/history_tracker.py`
- 实现信号记录和准确率计算（区间最优价）
- 编写单元测试

### Step 5: 修改报告生成器 (1天)
- 修改 `src/report_generator.py`
- 新增 `_format_signal_card` 函数（缩进列表风格）
- 修改 `generate_report` 函数（三档划分展示）
- 阈值从 `BuySellSignalConfig` 读取，不再硬编码

### Step 6: 修改主程序 (1天)
- 修改 `src/main.py`
- 集成新模块
- 删除 `score_threshold_high`/`score_threshold_low` 的使用
- 将 `judge_score` 调用改为使用 `config.buy_sell_signal.buy_threshold/sell_threshold`
- 实现两阶段流水线
- 构建 `stock_signals` 和 `etf_signals`（`list[BuySellSignal]`）
- 测试完整流程

### Step 7: 测试和优化 (2天)
- 运行完整测试
- 修复bug
- 优化性能
- 验证报告格式

## 文件清单

### 性能优化相关
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/main.py` | 修改 | 并行化数据获取、两阶段流水线 |
| `src/fundamental_analysis.py` | 修改 | 减少API调用次数（5→2季度） |
| `src/cache_manager.py` | 新增 | 磁盘缓存管理（JSON格式） |
| `cache/` | 新增目录 | 缓存数据存储 |

### 买卖信号系统相关
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/scoring.py` | 修改 | 提取 `INDUSTRY_ETF_MAP` 为模块级常量 |
| `src/config.py` | 修改 | 新增 `BuySellSignalConfig` 嵌入 `AppConfig`，删除 `score_threshold_high/low` |
| `src/signal.py` | 新增 | 买卖信号数据类（从 scoring.py 分离） |
| `src/price_analysis.py` | 新增 | 关键价位计算（复用 `get_kline_data_from_cache`） |
| `src/sector_analysis.py` | 新增 | 板块对比功能（使用 `INDUSTRY_ETF_MAP`） |
| `src/history_tracker.py` | 新增 | 历史准确率追踪（含 `record_signals_batch`） |
| `src/report_generator.py` | 修改 | 新信号格式（缩进列表）、三档展示、阈值配置化，接收 `list[BuySellSignal]` |
| `src/main.py` | 修改 | 集成新模块、两阶段流水线、使用 `get_kline_data_from_cache` 转换、批量记录信号 |
| `tests/test_price_analysis.py` | 新增 | 单元测试 |
| `tests/test_sector_analysis.py` | 新增 | 单元测试 |
| `tests/test_history_tracker.py` | 新增 | 单元测试 |
| `data/signal_history.json` | 新增 | 历史数据存储 |

## 验证方案

1. **单元测试**: 为每个新模块编写单元测试
   - `test_price_analysis.py`: 测试数据不足、边界值、正常场景
   - `test_sector_analysis.py`: 测试排名计算、ETF对比、异常处理
   - `test_history_tracker.py`: 测试信号记录、准确率计算、区间最优价
2. **集成测试**: 运行完整的分析流程，检查输出格式
3. **手动验证**: 检查报告中的信号卡片是否符合预期格式
4. **性能测试**: 确保新增功能不会显著增加运行时间

## 预期输出示例

```markdown
# A股每日分析报告 — 2026-06-13

## 🟢 买入区

### 🟢 贵州茅台 (600519) — 78/100 买入区

📊 **信号维度**
  ├─ 技术面: 82分
  ├─ 资金面: 75分
  ├─ 基本面: 80分
  └─ 情绪面: 70分

📍 **关键价位**
  ├─ 当前价: 1850.00
  ├─ 支撑位: 1780.00
  ├─ 压力位: 1920.00
  ├─ 目标价: 2016.00
  └─ 止损价: 1691.00

📈 **板块对比**
  ├─ 白酒行业排名: 第3/28 (超过89%的同行)
  └─ vs 板块ETF: 跑赢板块 +2.3%

📜 **历史信号准确率**
  ├─ 近30天: 72%准确, 平均收益 +3.2%
  ├─ 近90天: 68%准确, 平均收益 +5.1%
  └─ 近180天: 65%准确, 平均收益 +8.7%

🔗 [同花顺详情](https://stockpage.10jqka.com.cn/600519/)
[附K线图 + MACD图]

## 🟡 观望区

### 🟡 比亚迪 (002594) — 55/100 观望区

📊 **信号维度**
  ├─ 技术面: 60分
  ├─ 资金面: 50分
  ├─ 基本面: 55分
  └─ 情绪面: 45分

📍 **关键价位**
  ├─ 当前价: 280.00
  ├─ 支撑位: 265.00
  ├─ 压力位: 295.00
  ├─ 目标价: 310.00
  └─ 止损价: 252.00

📈 **板块对比**
  ├─ 新能源汽车排名: 第8/35 (超过77%的同行)
  └─ vs 板块ETF: 跑输板块 -1.5%

📜 **历史信号准确率**
  ├─ 近30天: 60%准确, 平均收益 +1.8%
  ├─ 近90天: 55%准确, 平均收益 +2.3%
  └─ 近180天: 52%准确, 平均收益 +3.1%

🔗 [同花顺详情](https://stockpage.10jqka.com.cn/002594/)
[附K线图 + MACD图]

## 🔴 卖出区

### 🔴 某股票 (600000) — 15/100 卖出区

📊 **信号维度**
  ├─ 技术面: 10分
  ├─ 资金面: 20分
  ├─ 基本面: 15分
  └─ 情绪面: 10分

📍 **关键价位**
  ├─ 当前价: 10.50
  ├─ 支撑位: 9.80
  ├─ 压力位: 11.20
  ├─ 目标价: 11.76
  └─ 止损价: 9.31

📜 **历史信号准确率**
  ├─ 近30天: 80%准确, 平均收益 -5.2%
  ├─ 近90天: 75%准确, 平均收益 -3.8%
  └─ 近180天: 70%准确, 平均收益 -2.1%

🔗 [同花顺详情](https://stockpage.10jqka.com.cn/600000/)
[附K线图 + MACD图]

## 📰 政策新闻

- 国际油价下跌，石化板块承压
- 新能源汽车渗透率持续提升
- 5月CPI数据公布，通胀预期温和

---

*本报告仅供参考，不构成投资建议。*
```
