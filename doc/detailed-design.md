# A股智能选股分析与推送系统 — 详细设计文档

> 版本：v1.0  
> 日期：2026-06-06  
> 状态：待评审  
> 依据：[需求文档 v1.1](proposal.md)

---

## 一、设计概述

### 1.1 设计目标

将需求文档中定义的功能模块进行详细设计，明确每个模块的职责边界、输入输出接口、核心数据结构和依赖关系，使各模块可以**独立开发和测试**。

### 1.2 模块总览

| 模块 | 文件 | 职责 | 可独立测试 |
|------|------|------|:----------:|
| 配置管理 | `config.py` | 集中管理所有可配置项 | ✅ |
| 股票池筛选 | `stock_filter.py` | 从全市场筛选符合条件的股票 | ✅ |
| ETF分析 | `etf_analyzer.py` | 获取ETF池并分析资金流向 | ✅ |
| 技术指标计算 | `technical_analysis.py` | 计算MA/MACD/成交量指标 | ✅ |
| 基本面分析 | `fundamental_analysis.py` | 获取并评估基本面数据 | ✅ |
| 政策新闻分析 | `news_analysis.py` | 抓取新闻、LLM分析政策影响 | ✅ |
| 综合评分 | `scoring.py` | 汇总各维度评分并排序 | ✅ |
| 图表生成 | `chart_generator.py` | 生成K线+MACD图表 | ✅ |
| 报告生成 | `report_generator.py` | 组装推送文本内容 | ✅ |
| 微信推送 | `push_service.py` | 调用PushPlus发送消息 | ✅ |
| 主程序 | `main.py` | 编排整个分析流水线 | 集成测试 |

### 1.3 设计约束

- 所有外部API调用需有重试机制和异常隔离
- 单只股票/ETF的处理失败不影响整体流程
- 评分权重、ETF池等可配置项集中管理，修改无需改动业务代码

---

## 二、模块详细设计

### 2.1 配置管理模块 — `config.py`

#### 2.1.1 职责

集中管理所有可配置参数，包括：评分权重、ETF池列表、过滤阈值、API参数等。

#### 2.1.2 数据结构

```python
@dataclass
class TechnicalWeightConfig:
    """技术指标评分权重配置"""
    ma_golden_cross: float = 5.0        # MA5/10金叉
    ma20_60_golden_cross: float = 5.0   # MA20/60金叉
    bullish_alignment: float = 5.0      # 多头排列
    above_ma20: float = 3.0             # 股价站上MA20
    macd_golden_cross: float = 5.0      # MACD金叉
    macd_above_zero: float = 5.0        # 零轴上方金叉
    macd_divergence: float = 5.0        # MACD底背离
    volume_up: float = 4.0              # 放量上涨
    pullback_ok: float = 3.0            # 缩量回调到位
    # 扣分项（存储为正数，计算时取负）
    ma_death_cross: float = 5.0         # MA5/10死叉
    macd_death_cross: float = 5.0       # MACD死叉
    volume_peak: float = 5.0            # 天量见天价
    volume_drop: float = 4.0            # 放量下跌

@dataclass
class FundamentalWeightConfig:
    """基本面评分权重配置（仅个股）"""
    pe_low: float = 8.0                 # PE合理偏低
    pe_mid: float = 3.0                 # PE偏高
    pe_high: float = 0.0                # PE过高
    pb_ok: float = 5.0                  # PB合理
    profit_high_growth: float = 10.0    # 净利润高增长
    profit_stable_growth: float = 5.0   # 净利润稳定增长
    profit_decline: float = 0.0         # 净利润下降
    revenue_high_growth: float = 7.0    # 营收高增长
    revenue_stable_growth: float = 3.0  # 营收稳定增长
    revenue_decline: float = 0.0        # 营收下降

@dataclass
class NewsWeightConfig:
    """政策新闻评分权重配置"""
    direct_positive: float = 17.5       # 直接利好（取中间值）
    indirect_positive: float = 11.0     # 间接利好
    neutral: float = 5.0                # 中性
    indirect_negative: float = -2.5     # 间接利空
    direct_negative: float = -7.5       # 直接利空

@dataclass
class IndustryTrendWeightConfig:
    """行业趋势评分权重配置（仅个股）"""
    uptrend: float = 9.0                # 上升趋势
    sideways: float = 4.5               # 横盘震荡
    downtrend: float = 1.0              # 下降趋势

@dataclass
class EtfFundFlowWeightConfig:
    """ETF资金流向评分权重配置"""
    continuous_growth: float = 9.0      # 份额持续增长
    slight_growth: float = 5.5          # 份额小幅增长
    flat: float = 3.0                   # 份额基本持平
    continuous_decline: float = 1.0     # 份额持续减少

@dataclass
class ScoreWeightConfig:
    """综合评分维度权重配置"""
    # 个股
    stock_technical: float = 0.40
    stock_fundamental: float = 0.30
    stock_news: float = 0.20
    stock_industry: float = 0.10
    # ETF
    etf_technical: float = 0.55
    etf_news: float = 0.35
    etf_fund_flow: float = 0.10

@dataclass
class FilterConfig:
    """股票池筛选配置"""
    min_market_cap: float = 20e8        # 最低市值（20亿）
    min_listing_months: int = 3         # 最低上市月数
    pool_size: int = 1000               # 筛选后保留数量

@dataclass
class AppConfig:
    """应用总配置"""
    filter: FilterConfig
    score_weight: ScoreWeightConfig
    technical_weight: TechnicalWeightConfig
    fundamental_weight: FundamentalWeightConfig
    news_weight: NewsWeightConfig
    industry_trend_weight: IndustryTrendWeightConfig
    etf_fund_flow_weight: EtfFundFlowWeightConfig
    etf_pool: list[str]                 # ETF代码列表
    score_threshold_high: float = 70.0  # 推送阈值（高概率）
    score_threshold_low: float = 30.0   # 推送阈值（风险警示）
    request_delay_range: tuple[float, float] = (1.0, 5.0)  # 请求延迟范围（秒）
    max_retries: int = 3                # 最大重试次数
    lookback_days: int = 60             # 技术指标回溯天数
    llm_api_url: str = ""               # LLM API地址
    llm_api_key: str = ""               # LLM API密钥（从环境变量读取）
```

#### 2.1.3 配置加载

```python
def load_config() -> AppConfig:
    """加载配置，优先级：环境变量 > 默认值"""
```

- 从环境变量读取敏感信息（`PUSHPLUS_TOKEN`、`LLM_API_KEY`）
- 硬编码默认值作为兜底
- 可选支持从 `config.yaml` 文件加载覆盖

#### 2.1.4 ETF池默认配置

```python
DEFAULT_ETF_POOL = [
    # 大盘宽基ETF
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    "159915",  # 创业板ETF
    "588000",  # 科创50ETF
    # 细分行业ETF
    "512480",  # 半导体ETF
    "516160",  # 新能源ETF
    "512010",  # 医药ETF
    "159928",  # 消费ETF
    "512660",  # 军工ETF
    "510230",  # 金融ETF
    "512200",  # 地产ETF
]
```

#### 2.1.5 测试要点

- 验证默认配置的完整性（所有必要字段均有值）
- 验证权重配置的合理性（如个股四项权重之和 = 1.0）
- 验证环境变量覆盖逻辑

---

### 2.2 股票池筛选模块 — `stock_filter.py`

#### 2.2.1 职责

从A股全市场中筛选出符合基本条件的股票，返回前N只进入分析池。

#### 2.2.2 接口定义

```python
def get_stock_pool(config: FilterConfig) -> pd.DataFrame:
    """
    获取筛选后的股票池
    
    Returns:
        DataFrame，columns = [code, name, market_cap, pe_ttm, pb, 
                              listing_date, industry]
        按 market_cap 降序，取前 config.pool_size 条
    """
```

#### 2.2.3 处理流程

```
1. 调用 ak.stock_zh_a_spot_em() 获取全市场股票实时行情
2. 过滤：market_cap >= 20亿
3. 过滤：name 不含 "ST"
4. 过滤：pe_ttm > 0
5. 过滤：listing_date >= 3个月前
6. 按 market_cap 降序排序
7. 取前 1000 条返回
```

#### 2.2.4 依赖

| 依赖 | 说明 |
|------|------|
| AKShare | `stock_zh_a_spot_em` 获取实时行情 |
| AKShare | `stock_info_a_code_name` 获取上市日期 |

#### 2.2.5 异常处理

- AKShare接口超时/失败：重试3次，间隔递增（2s/4s/8s）
- 全量获取失败：抛出异常，终止当日流程
- 个别字段缺失（如某只股票无PE数据）：该股票被过滤，记录警告日志

#### 2.2.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 正常数据 | 返回结果包含正确列，数量 ≤ pool_size |
| 含ST股 | 结果中无ST股票 |
| 含小市值 | 结果中市值均 ≥ 20亿 |
| 含负PE | 结果中PE均 > 0 |
| AKShare失败 | 重试3次后抛出异常 |

---

### 2.3 ETF分析模块 — `etf_analyzer.py`

#### 2.3.1 职责

获取ETF池中各ETF的行情数据和份额变化数据，计算资金流向得分。

#### 2.3.2 接口定义

```python
@dataclass
class EtfInfo:
    """ETF基本信息"""
    code: str
    name: str
    current_price: float
    change_pct: float

def get_etf_pool(config: AppConfig) -> list[EtfInfo]:
    """获取ETF池中各ETF的当前行情"""

def get_etf_fund_flow(code: str, days: int = 5) -> float:
    """
    获取ETF资金流向评分
    
    Args:
        code: ETF代码
        days: 回溯天数
    
    Returns:
        资金流向评分（0~10分）
    """
```

#### 2.3.3 资金流向评分逻辑

```python
def calc_fund_flow_score(share_changes: list[float]) -> float:
    """
    根据近N日份额变化计算评分
    
    Args:
        share_changes: 每日份额变化量列表（正数=增长，负数=减少）
    
    Returns:
        评分（0~10）
    """
```

| 条件 | 评分 |
|------|------|
| 连续N日份额增长 | 8~10 |
| 总体增长但有波动 | 4~7 |
| 基本持平 | 3 |
| 连续N日份额减少 | 0~2 |

#### 2.3.4 依赖

| 依赖 | 说明 |
|------|------|
| AKShare | `fund_etf_hist_em` 获取ETF行情数据 |
| AKShare | `fund_etf_fund_daily_em` 获取ETF份额数据 |

#### 2.3.5 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 份额连续增长 | 评分在 8~10 范围 |
| 份额连续减少 | 评分在 0~2 范围 |
| 份额持平 | 评分 = 3 |
| 数据不足 | 使用可用数据计算，记录警告 |

---

### 2.4 技术指标计算模块 — `technical_analysis.py`

#### 2.4.1 职责

基于最近60个交易日的行情数据，计算MA、MACD、成交量等技术指标，并生成信号评分。个股和ETF共用此模块。

#### 2.4.2 接口定义

```python
@dataclass
class TechnicalSignals:
    """技术指标信号汇总"""
    # 均线信号
    ma5_10_golden: bool          # MA5/10金叉（近3日）
    ma5_10_death: bool           # MA5/10死叉（近3日）
    ma20_60_golden: bool         # MA20/60金叉（近5日）
    bullish_alignment: bool      # 多头排列
    above_ma20: bool             # 股价站上MA20
    # MACD信号
    macd_golden: bool            # MACD金叉（近3日）
    macd_death: bool             # MACD死叉（近3日）
    macd_above_zero: bool        # 零轴上方金叉
    macd_divergence: bool        # MACD底背离（近10日）
    # 成交量信号
    volume_up: bool              # 放量上涨
    volume_down: bool            # 放量下跌
    volume_peak: bool            # 天量见天价
    pullback_ok: bool            # 缩量回调到位

@dataclass
class KlineData:
    """K线数据"""
    dates: list[str]             # 日期列表
    opens: list[float]
    highs: list[float]
    lows: list[float]
    closes: list[float]
    volumes: list[float]
    ma5: list[float]
    ma10: list[float]
    ma20: list[float]
    ma60: list[float]
    dif: list[float]
    dea: list[float]
    macd_hist: list[float]

def get_kline_data(code: str, days: int = 60, is_etf: bool = False) -> KlineData:
    """
    获取K线数据并计算技术指标
    
    Args:
        code: 股票/ETF代码
        days: 回溯天数
        is_etf: 是否为ETF
    
    Returns:
        KlineData 对象
    """

def calc_technical_signals(kline: KlineData) -> TechnicalSignals:
    """根据K线数据计算所有技术信号"""

def calc_technical_score(signals: TechnicalSignals, weights: TechnicalWeightConfig) -> float:
    """
    根据信号和权重计算技术指标评分
    
    Returns:
        评分（0~40分，可为负数，最终截断到0）
    """
```

#### 2.4.3 指标计算公式

**MA（移动平均线）：**

```
MA(n) = sum(close[i] for i in range(n)) / n
```

**MACD：**

```
EMA(n) = close * 2/(n+1) + prev_EMA * (n-1)/(n+1)
DIF = EMA(12) - EMA(26)
DEA = DIF * 2/(9+1) + prev_DEA * (9-1)/(9+1)
MACD柱 = (DIF - DEA) * 2
```

**量比：**

```
volume_ratio = today_volume / mean(volume[-5:])
```

#### 2.4.4 信号判定规则

| 信号 | 判定条件 |
|------|----------|
| MA5/10金叉 | 近3日内 MA5 从 < MA10 变为 > MA10 |
| MA5/10死叉 | 近3日内 MA5 从 > MA10 变为 < MA10 |
| MA20/60金叉 | 近5日内 MA20 从 < MA60 变为 > MA60 |
| 多头排列 | MA5 > MA10 > MA20 > MA60（最新一日） |
| 股价站上MA20 | 收盘价 > MA20（最新一日） |
| MACD金叉 | 近3日内 DIF 从 < DEA 变为 > DEA |
| MACD死叉 | 近3日内 DIF 从 > DEA 变为 < DEA |
| 零轴上方金叉 | MACD金叉 且 DIF > 0 且 DEA > 0 |
| MACD底背离 | 近10日内股价创新低但MACD不创新低 |
| 放量上涨 | 涨幅 > 0 且 量比 > 1.5 |
| 放量下跌 | 跌幅 > 2% 且 量比 > 2.0 |
| 天量见天价 | 成交量 = 60日最高 且 股价处于高位 |
| 缩量回调到位 | 回调至MA20附近(±2%) 且 量比 < 0.7 |

#### 2.4.5 依赖

| 依赖 | 说明 |
|------|------|
| AKShare | `stock_zh_a_hist` 获取个股历史行情 |
| AKShare | `fund_etf_hist_em` 获取ETF历史行情 |
| Pandas | 数据处理 |
| NumPy | 数值计算 |

#### 2.4.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 已知K线数据 | MA/MACD计算结果与手动计算一致 |
| 金叉/死叉场景 | 构造特定数据验证信号判定 |
| 数据不足60日 | 使用可用数据计算，缺失指标标记为False |
| ETF与个股 | 同一接口，仅数据源不同 |

---

### 2.5 基本面分析模块 — `fundamental_analysis.py`

#### 2.5.1 职责

获取个股的基本面数据（PE、PB、净利润增长率、营收增长率），并计算基本面评分。**仅用于个股，ETF跳过此模块。**

#### 2.5.2 接口定义

```python
@dataclass
class FundamentalData:
    """基本面数据"""
    pe_ttm: float                # 滚动市盈率
    pb: float                    # 市净率
    market_cap: float            # 总市值（元）
    profit_growth: float | None  # 净利润同比增长率（%）
    revenue_growth: float | None # 营收同比增长率（%）

def get_fundamental_data(code: str) -> FundamentalData:
    """获取个股基本面数据"""

def calc_fundamental_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float:
    """
    计算基本面评分
    
    Returns:
        评分（0~30分）
    """
```

#### 2.5.3 评分规则

| 指标 | 条件 | 得分 |
|------|------|------|
| PE-TTM | 10 < PE < 30 | +8 |
| PE-TTM | 30 ≤ PE < 60 | +3 |
| PE-TTM | PE ≥ 60 | 0 |
| PB | 1 < PB < 5 | +5 |
| 净利润同比 | > 20% | +10 |
| 净利润同比 | 0~20% | +5 |
| 净利润同比 | < 0% | 0 |
| 营收同比 | > 15% | +7 |
| 营收同比 | 0~15% | +3 |
| 营收同比 | < 0% | 0 |

#### 2.5.4 依赖

| 依赖 | 说明 |
|------|------|
| AKShare | `stock_financial_analysis_indicator` 获取财务指标 |

#### 2.5.5 异常处理

- 财务数据缺失（如次新股无同比数据）：缺失字段设为 `None`，对应评分为 0
- 接口失败：重试3次，仍失败则该股票基本面评分记为 0，记录警告

#### 2.5.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| PE=25, PB=3, 净利润+25%, 营收+20% | 评分 = 8+5+10+7 = 30 |
| PE=80, PB=10, 净利润-10%, 营收-5% | 评分 = 0+0+0+0 = 0 |
| 数据缺失 | 对应字段为None，评分不崩溃 |

---

### 2.6 政策新闻分析模块 — `news_analysis.py`

#### 2.6.1 职责

从财经新闻源抓取当日新闻，通过LLM分析政策影响方向和程度，关联到行业/板块。

#### 2.6.2 接口定义

```python
@dataclass
class NewsItem:
    """单条新闻"""
    title: str
    source: str              # 来源（新浪财经/东方财富/同花顺）
    url: str
    publish_time: datetime
    content: str

@dataclass
class PolicyImpact:
    """政策影响分析结果"""
    news_title: str
    affected_industries: list[str]   # 受影响行业列表
    impact_direction: str            # "positive" / "negative" / "neutral"
    impact_degree: str               # "direct" / "indirect"
    impact_score: float              # 影响评分（-20 ~ +20）
    summary: str                     # 影响摘要

def fetch_news() -> list[NewsItem]:
    """
    从AKShare获取当日财经新闻
    
    Returns:
        新闻列表，按时间倒序
    """

def filter_by_credibility(news: list[NewsItem]) -> list[NewsItem]:
    """
    按可信度过滤新闻
    
    可信度分级：
    - 高可信：政府官方发布（国务院、央行、证监会等）、三大证券报
    - 中可信：主流财经媒体（东方财富、同花顺、新浪财经）
    - 低可信：自媒体、论坛传闻 → 不纳入分析，直接过滤
    
    由于AKShare数据源本身来自主流财经平台，此函数主要做
    来源白名单校验，排除非主流来源的新闻。
    """

def analyze_policy_impact(news: list[NewsItem], llm_config: dict) -> list[PolicyImpact]:
    """
    使用LLM分析新闻的政策影响
    
    Args:
        news: 新闻列表
        llm_config: LLM配置（api_url, api_key）
    
    Returns:
        政策影响分析结果列表
    """

def get_industry_impact_score(industry: str, impacts: list[PolicyImpact]) -> float:
    """
    获取某行业的政策影响综合评分
    
    Args:
        industry: 行业名称
        impacts: 所有政策影响分析结果
    
    Returns:
        评分（-20 ~ +20）
    """
```

#### 2.6.3 新闻可信度分级

| 可信度 | 来源 | 处理方式 |
|--------|------|----------|
| 高可信 | 政府官方（国务院、央行、证监会）、三大证券报 | 纳入分析，权重最高 |
| 中可信 | 东方财富、同花顺、新浪财经 | 纳入分析 |
| 低可信 | 自媒体、论坛传闻 | **直接过滤，不纳入分析** |

由于AKShare数据源本身来自主流财经平台，可信度过滤主要做来源白名单校验。

#### 2.6.4 LLM分析流程

```
1. 可信度过滤：排除低可信来源的新闻
2. 类型过滤：排除明显的非政策类新闻（娱乐、体育等）
3. 将筛选后的新闻批量发送给LLM
4. LLM返回结构化结果：
   - 每条新闻的影响行业
   - 影响方向（利好/利空/中性）
   - 影响程度（直接/间接）
   - 影响评分（-20 ~ +20）
5. 汇总各行业的综合影响
```

#### 2.6.4 LLM Prompt 设计

```python
POLICY_ANALYSIS_PROMPT = """
你是一位专业的A股市场政策分析师。请分析以下财经新闻对A股各行业的影响。

新闻列表：
{news_list}

请对每条新闻返回以下JSON格式：
{{
  "news_title": "新闻标题",
  "affected_industries": ["行业1", "行业2"],
  "impact_direction": "positive/negative/neutral",
  "impact_degree": "direct/indirect",
  "impact_score": -20到20的数值,
  "summary": "一句话影响摘要"
}}

评分参考：
- 直接利好该行业：+15~20
- 间接利好：+8~14
- 中性：+5
- 间接利空：-5~0
- 直接利空：-10~-5

请只返回JSON数组，不要其他内容。
"""
```

#### 2.6.5 依赖

| 依赖 | 说明 |
|------|------|
| AKShare | `stock_news_em` 获取个股相关新闻 |
| LLM API | 政策影响分析（兼容OpenAI格式的API） |

#### 2.6.6 异常处理

- 新闻抓取失败：记录警告，返回空列表，新闻评分默认为中性（+5分）
- LLM调用失败：重试2次，仍失败则所有新闻影响记为中性
- LLM返回格式异常：解析失败时记录原始响应，使用默认中性评分

#### 2.6.7 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 模拟LLM返回 | 解析结果正确关联到行业 |
| LLM返回异常格式 | 降级为中性评分，不崩溃 |
| 新闻抓取失败 | 返回空列表，下游正常运行 |
| 多条新闻同一行业 | 评分正确累加/合并 |

---

### 2.7 综合评分模块 — `scoring.py`

#### 2.7.1 职责

汇总各维度的评分，按权重计算综合评分，并将评分转换为盈利概率。判定是否触发推送。

#### 2.7.2 接口定义

```python
@dataclass
class ScoreResult:
    """评分结果"""
    code: str
    name: str
    is_etf: bool
    # 各维度原始评分
    technical_score: float
    fundamental_score: float | None  # ETF为None
    news_score: float
    industry_score: float | None     # ETF为None
    fund_flow_score: float | None    # 个股为None
    # 综合
    total_score: float               # 综合评分（0~100）
    profit_probability: float        # 盈利概率（0~100%）
    judgment: str                    # "recommend" / "watch" / "bearish" / "risk"
    # 详情
    technical_signals: TechnicalSignals
    news_summary: str

def calc_total_score(
    technical: float,
    fundamental: float | None,
    news: float,
    industry: float | None,
    fund_flow: float | None,
    is_etf: bool,
    config: ScoreWeightConfig
) -> float:
    """
    计算综合评分
    
    Returns:
        综合评分（0~100）
    """

def score_to_probability(score: float) -> float:
    """
    将综合评分转换为盈利概率
    
    使用sigmoid-like映射：评分50分对应约50%概率，
    70分对应约75%概率，30分对应约25%概率
    
    Returns:
        盈利概率百分比（0~100）
    """

def judge_score(score: float, high_threshold: float, low_threshold: float) -> str:
    """
    判定评分等级
    
    Returns:
        "recommend" (≥70), "watch" (50~69), "bearish" (30~49), "risk" (<30)
    """

def get_industry_trend_score(
    industry: str,
    etf_pool: list[str],
    config: AppConfig
) -> float:
    """
    获取所属行业的趋势评分（仅个股使用）
    
    通过查找该行业对应的ETF，分析ETF的均线排列状态来评估行业趋势。
    
    Args:
        industry: 股票所属行业名称
        etf_pool: ETF代码列表
        config: 应用配置
    
    Returns:
        评分（0~10分）
    
    实现逻辑：
        1. 根据行业名称匹配对应的ETF代码（维护行业→ETF映射表）
        2. 获取该ETF的K线数据，计算MA5/MA10/MA20/MA60
        3. 判断均线排列状态：
           - 多头排列（MA5 > MA10 > MA20 > MA60）→ 8~10分
           - 横盘震荡（无明显趋势）→ 4~5分
           - 空头排列（MA5 < MA10 < MA20 < MA60）→ 0~2分
        4. 使用config.industry_trend_weight中的对应分值
    """
```

#### 2.7.3 盈利概率计算公式

使用归一化的sigmoid函数：

```python
import math

def score_to_probability(score: float) -> float:
    """
    将0-100的评分映射到0-100%的概率
    
    使用sigmoid函数：P = 1 / (1 + e^(-k*(x - x0)))
    其中 k=0.1, x0=50，使得：
    - 评分50 → 概率约50%
    - 评分70 → 概率约88%
    - 评分30 → 概率约12%
    
    最终归一化到0-100%范围
    """
    k = 0.1
    x0 = 50
    raw = 1 / (1 + math.exp(-k * (score - x0)))
    # 归一化：sigmoid(0) ~ sigmoid(100) 映射到 0% ~ 100%
    low = 1 / (1 + math.exp(-k * (0 - x0)))
    high = 1 / (1 + math.exp(-k * (100 - x0)))
    normalized = (raw - low) / (high - low)
    return round(normalized * 100, 0)
```

#### 2.7.4 综合评分计算

**个股：**
```
total = technical * 0.40 + fundamental * 0.30 + news * 0.20 + industry * 0.10
```

**ETF：**
```
total = technical * 0.55 + news * 0.35 + fund_flow * 0.10
```

评分截断到 [0, 100] 范围。

#### 2.7.5 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 满分场景 | 各维度满分时综合评分 = 100 |
| 零分场景 | 各维度零分时综合评分 = 0 |
| 评分截断 | 负分截断到0，超100截断到100 |
| 概率转换 | 70分 → 约88%，30分 → 约12% |
| ETF权重 | ETF无基本面/行业，权重正确分配 |

---

### 2.8 图表生成模块 — `chart_generator.py`

#### 2.8.1 职责

为推送的股票/ETF生成K线+MACD图表（PNG格式）。

#### 2.8.2 接口定义

```python
def generate_chart(
    code: str,
    name: str,
    kline: KlineData,
    save_path: str
) -> str:
    """
    生成K线+MACD图表
    
    Args:
        code: 股票/ETF代码
        name: 名称
        kline: K线数据
        save_path: 图片保存路径
    
    Returns:
        图片文件路径
    """
```

#### 2.8.3 图表布局

```
┌─────────────────────────────────────┐
│  {name} ({code}) — K线图 + MA均线    │
├─────────────────────────────────────┤
│                                     │
│      K线（蜡烛图）                    │
│      MA5（黄线）                      │
│      MA10（蓝线）                     │
│      MA20（紫线）                     │
│      MA60（绿线）                     │
│                                     │
├─────────────────────────────────────┤
│      MACD指标                        │
│      DIF线（白线）                    │
│      DEA线（黄线）                    │
│      MACD柱（红/绿）                  │
│      零轴（虚线）                     │
└─────────────────────────────────────┘
```

#### 2.8.4 样式配置

```python
CHART_STYLE = {
    "figsize": (12, 8),
    "kline_ratio": 3,        # K线区域占比
    "macd_ratio": 1,         # MACD区域占比
    "colors": {
        "up": "#FF4444",      # 涨 - 红色
        "down": "#00CC00",    # 跌 - 绿色
        "ma5": "#FFD700",     # MA5 - 金色
        "ma10": "#4169E1",    # MA10 - 蓝色
        "ma20": "#9370DB",    # MA20 - 紫色
        "ma60": "#32CD32",    # MA60 - 绿色
        "dif": "#FFFFFF",     # DIF - 白色
        "dea": "#FFD700",     # DEA - 金色
        "macd_up": "#FF4444", # MACD柱涨 - 红色
        "macd_down": "#00CC00" # MACD柱跌 - 绿色
    },
    "background": "#1A1A2E",  # 深色背景
    "grid": "#333355"         # 网格颜色
}
```

#### 2.8.5 依赖

| 依赖 | 说明 |
|------|------|
| mplfinance | K线图绘制 |
| Matplotlib | 自定义MACD子图 |

#### 2.8.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 正常数据 | 生成PNG文件，文件大小 > 0 |
| 数据不足 | 使用可用数据生成，不崩溃 |
| 特殊字符名称 | 文件名正确处理中文 |

---

### 2.9 报告生成模块 — `report_generator.py`

#### 2.9.1 职责

将评分结果和图表组装为最终的推送文本消息。

#### 2.9.2 接口定义

```python
def generate_report(
    stock_results: list[ScoreResult],
    etf_results: list[ScoreResult],
    policy_impacts: list[PolicyImpact],
    report_date: str
) -> str:
    """
    生成推送报告文本
    
    Args:
        stock_results: 个股评分结果（已筛选，仅包含推送项）
        etf_results: ETF评分结果（已筛选，仅包含推送项）
        policy_impacts: 政策影响分析结果
        report_date: 报告日期
    
    Returns:
        Markdown格式的推送文本
    """
```

#### 2.9.3 报告结构

```
📊 A股每日分析报告 — {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 今日个股推荐关注（综合评分 ≥ 70）
  [评分降序排列的个股列表]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 今日ETF推荐关注（综合评分 ≥ 70）
  [评分降序排列的ETF列表]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 个股风险警示（综合评分 < 30）
  [评分升序排列的风险个股]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ ETF风险警示（综合评分 < 30）
  [评分升序排列的风险ETF]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 今日政策要闻
  [政策影响摘要列表]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
```

#### 2.9.4 单只股票/ETF的输出格式

**个股：**
```
【1】{name} ({code}) — 综合评分：{score}分
├ 技术信号：{技术信号摘要}
├ 基本面：PE={pe}（{评价}），净利润同比{growth}
├ 政策影响：{新闻摘要}
├ 盈利概率：约 {probability}%
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{code}/
[附K线图 + MACD图]
```

**ETF：**
```
【1】{name} ({code}) — 综合评分：{score}分
├ 技术信号：{技术信号摘要}
├ 政策影响：{新闻摘要}
├ 资金流向：{资金流向描述}
├ 盈利概率：约 {probability}%
└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{code}/
[附K线图 + MACD图]
```

#### 2.9.5 无推荐场景

当无任何股票/ETF满足推送条件时：

```
📊 A股每日分析报告 — {date}

今日无符合条件的推荐标的。
所有股票和ETF的综合评分均在观望区间（30~70分）。

⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
```

#### 2.9.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 有推荐+有风险 | 报告包含两部分内容 |
| 仅有推荐 | 报告无风险警示部分 |
| 仅有风险 | 报告无推荐部分 |
| 无推荐无风险 | 显示"今日无推荐" |
| 空列表 | 不崩溃，显示空报告 |

---

### 2.10 微信推送模块 — `push_service.py`

#### 2.10.1 职责

调用PushPlus API将报告推送到微信。

#### 2.10.2 接口定义

```python
def push_to_wechat(
    title: str,
    content: str,
    token: str,
    template: str = "markdown"
) -> bool:
    """
    通过PushPlus推送消息到微信
    
    Args:
        title: 消息标题
        content: 消息内容（Markdown格式）
        token: PushPlus令牌
        template: 模板类型
    
    Returns:
        是否推送成功
    """
```

#### 2.10.3 PushPlus API调用

```python
PUSHPLUS_API = "http://www.pushplus.plus/send"

def push_to_wechat(title, content, token, template="markdown"):
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": template
    }
    response = requests.post(PUSHPLUS_API, json=payload, timeout=30)
    result = response.json()
    return result.get("code") == 200
```

#### 2.10.4 依赖

| 依赖 | 说明 |
|------|------|
| Requests | HTTP请求 |

#### 2.10.5 异常处理

- 网络超时：重试2次
- API返回错误：记录错误码和消息，返回False
- Token无效：抛出明确异常

#### 2.10.6 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 正常推送 | 返回True |
| Token无效 | 返回False，记录错误 |
| 网络超时 | 重试后返回False |

---

### 2.11 主程序 — `main.py`

#### 2.11.1 职责

编排整个分析流水线，协调各模块的执行顺序。

#### 2.11.2 主流程

```python
def main():
    # 1. 加载配置
    config = load_config()
    
    # 2. 获取股票池
    stock_pool = get_stock_pool(config.filter)
    
    # 3. 获取ETF池
    etf_pool = get_etf_pool(config)
    
    # 4. 抓取并分析新闻（全局只执行一次）
    news = fetch_news()
    policy_impacts = analyze_policy_impact(news, config.llm_config)
    
    # 5. 分析个股
    stock_results = []
    for _, stock in stock_pool.iterrows():
        try:
            result = analyze_single_stock(stock, policy_impacts, config)
            if result.total_score >= config.score_threshold_high or \
               result.total_score < config.score_threshold_low:
                stock_results.append(result)
        except Exception as e:
            logger.warning(f"分析股票 {stock['code']} 失败: {e}")
    
    # 6. 分析ETF
    etf_results = []
    for etf in etf_pool:
        try:
            result = analyze_single_etf(etf, policy_impacts, config)
            if result.total_score >= config.score_threshold_high or \
               result.total_score < config.score_threshold_low:
                etf_results.append(result)
        except Exception as e:
            logger.warning(f"分析ETF {etf.code} 失败: {e}")
    
    # 7. 生成图表
    for result in stock_results + etf_results:
        kline = get_kline_data(result.code, config.lookback_days, result.is_etf)
        generate_chart(result.code, result.name, kline, f"charts/{result.code}.png")
    
    # 8. 生成报告
    report = generate_report(stock_results, etf_results, policy_impacts, today())
    
    # 9. 推送
    success = push_to_wechat(
        title=f"A股每日分析报告 — {today()}",
        content=report,
        token=os.environ["PUSHPLUS_TOKEN"]
    )
    
    if not success:
        logger.error("推送失败")
```

#### 2.11.3 单只股票分析流程

```python
def analyze_single_stock(stock, policy_impacts, config) -> ScoreResult:
    code = stock["code"]
    
    # 获取K线数据
    kline = get_kline_data(code, config.lookback_days)
    
    # 技术指标
    signals = calc_technical_signals(kline)
    tech_score = calc_technical_score(signals, config.technical_weight)
    
    # 基本面
    fund_data = get_fundamental_data(code)
    fund_score = calc_fundamental_score(fund_data, config.fundamental_weight)
    
    # 政策新闻
    news_score = get_industry_impact_score(stock["industry"], policy_impacts)
    
    # 行业趋势
    industry_score = get_industry_trend_score(stock["industry"], config)
    
    # 综合评分
    total = calc_total_score(tech_score, fund_score, news_score, industry_score, 
                             None, False, config.score_weight)
    
    return ScoreResult(
        code=code,
        name=stock["name"],
        is_etf=False,
        technical_score=tech_score,
        fundamental_score=fund_score,
        news_score=news_score,
        industry_score=industry_score,
        fund_flow_score=None,
        total_score=total,
        profit_probability=score_to_probability(total),
        judgment=judge_score(total, config.score_threshold_high, config.score_threshold_low),
        technical_signals=signals,
        news_summary=""
    )
```

#### 2.11.4 依赖

所有其他模块。

#### 2.11.5 测试策略

| 测试场景 | 验证点 |
|----------|--------|
| 完整流程 | 各模块按序调用，报告生成正确 |
| 单只股票失败 | 跳过该股票，继续分析其他 |
| 全部失败 | 生成空报告，正常推送 |
| 推送失败 | 记录错误日志 |

---

## 三、模块依赖关系

```
main.py
  ├── config.py (无依赖)
  ├── stock_filter.py → AKShare
  ├── etf_analyzer.py → AKShare
  ├── technical_analysis.py → AKShare, Pandas, NumPy
  ├── fundamental_analysis.py → AKShare
  ├── news_analysis.py → AKShare, LLM API
  ├── scoring.py (无外部依赖)
  ├── chart_generator.py → mplfinance, Matplotlib
  ├── report_generator.py (无外部依赖)
  └── push_service.py → Requests
```

---

## 四、通用基础设施

### 4.1 日志规范

```python
import logging

logger = logging.getLogger("thousand-times")

# 日志级别
# INFO: 流程节点（开始分析、完成分析）
# WARNING: 单只股票分析失败、数据缺失
# ERROR: 推送失败、配置错误
```

### 4.2 重试装饰器

```python
def retry(max_attempts=3, backoff_factor=2):
    """通用重试装饰器，支持指数退避"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_factor ** attempt
                    logger.warning(f"{func.__name__} 第{attempt+1}次失败，{wait}秒后重试: {e}")
                    time.sleep(wait)
        return wrapper
    return decorator
```

### 4.3 请求延迟

```python
def random_delay(min_sec=1.0, max_sec=5.0):
    """随机延迟，避免触发API频率限制"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
```

---

## 五、数据流汇总

```
AKShare API
    │
    ├──→ stock_filter.py ──→ 股票池（1000只）
    │                              │
    │                              ▼
    │                     technical_analysis.py (技术指标)
    │                              │
    │                              ▼
    │                     fundamental_analysis.py (基本面)
    │                              │
    │                              ▼
    │                     scoring.py (综合评分)
    │                              │
    │                              ▼
    │                     筛选 ≥70 或 <30
    │
    ├──→ etf_analyzer.py ──→ ETF池
    │         │                    │
    │         │                    ▼
    │         │           technical_analysis.py (技术指标)
    │         │                    │
    │         ▼                    ▼
    │    资金流向评分          scoring.py (综合评分)
    │         │                    │
    │         │                    ▼
    │         │           筛选 ≥70 或 <30
    │         │                    │
    │         └────────┬───────────┘
    │                  ▼
    │         chart_generator.py (图表)
    │                  │
    ├──→ news_analysis.py ──→ 政策影响评分
    │                              │
    │                              ▼
    │                     report_generator.py (报告)
    │                              │
    │                              ▼
    │                     push_service.py (推送)
    │                              │
    │                              ▼
    │                         微信用户
```

---

## 六、环境依赖与CI/CD

### 6.1 Python 依赖（requirements.txt）

```
akshare>=1.10.0
pandas>=2.0.0
numpy>=1.24.0
mplfinance>=0.12.10
matplotlib>=3.7.0
requests>=2.31.0
beautifulsoup4>=4.12.0
```

### 6.2 环境变量（GitHub Secrets）

| 变量名 | 必需 | 说明 |
|--------|:----:|------|
| `PUSHPLUS_TOKEN` | ✅ | PushPlus推送令牌 |
| `LLM_API_URL` | ✅ | LLM API地址 |
| `LLM_API_KEY` | ✅ | LLM API密钥 |

### 6.3 GitHub Actions 配置

文件路径：`.github/workflows/daily_analysis.yml`

```yaml
name: Daily Stock Analysis

on:
  # 定时调度：工作日北京时间12:00（UTC 04:00）
  schedule:
    - cron: '0 4 * * 1-5'
  # 支持手动触发
  workflow_dispatch:

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run analysis
        env:
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
          LLM_API_URL: ${{ secrets.LLM_API_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
        run: python src/main.py

      - name: Upload logs on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: error-logs
          path: logs/
```

---

*本文档为详细设计初稿，待评审后进入开发阶段。*
