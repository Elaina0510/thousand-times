# 千倍系统 v2 重构设计文档

> 目标：重构为实用主义量化系统，解决评分荒谬、不看大环境、无回测三大痛点。

---

## 一、现状问题清单

| # | 问题                                                                                    | 严重程度 | 影响                                    |
| - | --------------------------------------------------------------------------------------- | -------- | --------------------------------------- |
| 1 | `get_industry_trend_score()` 永远返回 4.5（震荡默认值），行业趋势维度等于摆设         | 高       | 25%权重形同虚设，所有股票得分被均匀拉高 |
| 2 | 回测用简化信号（满分~20） vs 生产用完整信号（满分~55），同一阈值70产生完全不同的信号率 | 高       | 回测结果无法指导实际策略                |
| 3 | 市场环境判断仅用2个布尔信号+1个波动率，太粗糙                                           | 高       | 牛熊误判导致策略方向错误                |
| 4 | "volume_price"权重维度实际接收的是新闻分数，不是量价数据                                | 中       | 命名误导，逻辑混乱                      |
| 5 | 评分权重人工拍脑袋，无因子有效性检验                                                    | 中       | 权重不合理，选不出好股票                |
| 6 | 股票分析串行执行，有并行基础设施但未使用                                                | 低       | 运行慢，但不影响正确性                  |
| 7 | 无资金流向、情绪面、宏观面数据                                                          | 高       | 信息维度太单一                          |

---

## 二、目标架构：五阶段管道

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 01_regime   │────▶│ 02_collect  │────▶│ 03_factors  │────▶│ 04_signal   │────▶│ 05_output   │
│ 市场环境判断 │     │ 数据采集    │     │ 多因子计算   │     │ 信号生成    │     │ 报告+推送    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼                   ▼
  MarketRegime         RawData           FactorScores        SignalList          Report/Alert
  牛/熊/震荡          全数据源           因子分数排名        买卖信号+置信度      微信+文件
  仓位建议                                                      关键价位
```

### 目录结构

```
src/
├── main.py              ← 精简为管道编排器（~100行）
├── config.py            ← 扩展：增加策略配置、新数据源配置
├── pipeline/
│   ├── __init__.py
│   ├── regime.py        ← 阶段1: 市场环境判断（重写）
│   ├── collect.py       ← 阶段2: 统一数据采集（新）
│   ├── factors.py       ← 阶段3: 多因子计算（替代scoring.py）
│   ├── signal.py        ← 阶段4: 信号生成（重写buy_sell_signal.py）
│   └── output.py        ← 阶段5: 报告+推送+实时提醒
├── data_sources/        ← 新增数据源模块
│   ├── __init__.py
│   ├── capital_flow.py  ← 北向资金、主力资金、融资融券
│   ├── sentiment.py     ← 涨跌停统计、涨跌比、连板高度
│   ├── macro.py         ← CPI/PMI/利率等宏观指标
│   └── sector_flow.py   ← 行业资金流向、板块轮动
├── factors/             ← 因子库（新）
│   ├── __init__.py
│   ├── technical.py     ← 技术面因子（从technical_analysis.py迁移）
│   ├── fundamental.py   ← 基本面因子（从fundamental_analysis.py迁移）
│   ├── capital.py       ← 资金面因子（新）
│   ├── sentiment.py     ← 情绪面因子（新）
│   └── momentum.py      ← 动量因子（新）
├── backtest.py          ← 重写回测引擎（与生产共用因子计算）
├── baostock_data.py     ← 保留（数据层不变）
├── ashare.py            ← 保留
├── ashare_data.py       ← 保留
├── cache_manager.py     ← 保留
├── chart_generator.py   ← 保留
├── html_report.py       ← 保留
├── push_service.py      ← 保留
├── history_tracker.py   ← 保留
└── utils.py             ← 保留
```

### 保留 vs 重写 vs 新增

| 模块                               | 操作           | 原因                                                           |
| ---------------------------------- | -------------- | -------------------------------------------------------------- |
| `baostock_data.py`               | 保留           | 数据层稳定，无需改动                                           |
| `ashare.py` / `ashare_data.py` | 保留           | 备用数据源，保留容错                                           |
| `cache_manager.py`               | 保留           | 缓存逻辑通用                                                   |
| `chart_generator.py`             | 保留           | 图表生成独立                                                   |
| `html_report.py`                 | 保留           | 报告模板独立                                                   |
| `push_service.py`                | 保留           | 推送逻辑独立                                                   |
| `history_tracker.py`             | 保留           | 历史追踪独立，用于记录每日评分变化趋势                         |
| `technical_analysis.py`          | 重构           | 拆分：K线数据获取保留在原模块（供collect.py调用），指标计算迁移到 `factors/technical.py` |
| `fundamental_analysis.py`        | 重构           | 拆分：数据获取保留在原模块（供collect.py调用），评分逻辑迁移到 `factors/fundamental.py`  |
| `scoring.py`                     | **重写** | 替换为 `pipeline/factors.py`（多因子引擎）                   |
| `market_regime.py`               | **重写** | 替换为 `pipeline/regime.py`（增强版）                        |
| `buy_sell_signal.py`             | **重写** | 替换为 `pipeline/signal.py`（信号投票制）                    |
| `backtest.py`                    | **重写** | 与生产共用因子计算，消除信号不一致                             |
| `main.py`                        | **重写** | 精简为管道编排器                                               |
| `config.py`                      | 扩展           | 增加新配置项                                                   |
| `stock_filter.py`                | 保留           | 股票池筛选逻辑不变                                             |
| `etf_analyzer.py`                | 保留           | ETF分析逻辑不变                                                |
| `news_analysis.py`               | 保留           | 新闻获取+LLM分析不变                                           |
| `price_analysis.py`              | 重构           | 价格分析逻辑迁移到 `factors/technical.py`，原模块可删除       |
| `sector_analysis.py`             | 重构           | 行业对比逻辑迁移到 `factors/capital.py`，原模块可删除         |
| `remote_data.py`                 | 保留           | 远程数据获取不变                                               |

---

## 三、错误处理与降级策略

### 数据源失败处理

| 失败场景 | 降级策略 | 影响范围 |
|---------|---------|---------|
| 北向资金获取失败 | 跳过该信号，投票制从5票降为4票 | 市场环境判断、个股信号 |
| 涨跌停统计获取失败 | 跳过情绪面因子，使用默认中性分 | 市场环境判断 |
| 融资融券获取失败 | 跳过该因子，不影响主流程 | 个股资金面因子 |
| 个股K线获取失败 | 跳过该股票，不参与排名 | 单只股票 |
| 个股基本面获取失败 | 基本面分数设为50（中性），继续分析 | 单只股票 |
| 指数K线获取失败 | 市场环境判断使用上一次缓存结果 | 全局 |
| LLM新闻分析失败 | 新闻情绪设为中性（50分），继续分析 | 个股新闻因子 |

### 管道级错误处理

```python
def run_pipeline(config: AppConfig) -> None:
    """管道主函数，每阶段独立异常处理"""
    try:
        regime = stage_regime(config)
    except Exception as e:
        logger.error(f"市场环境判断失败: {e}，使用默认震荡")
        regime = MarketRegime(state="sideways", confidence=0.5, position_advice=0.5, signals={}, description="默认")

    try:
        data = stage_collect(config, regime)
    except Exception as e:
        logger.error(f"数据采集失败: {e}，终止本次运行")
        return

    try:
        scores = stage_factors(data, config, regime)
    except Exception as e:
        logger.error(f"因子计算失败: {e}，终止本次运行")
        return

    signals = stage_signal(scores, data, config, regime)
    stage_output(signals, scores, data, config, regime)
```

---

## 四、阶段1：市场环境判断（pipeline/regime.py）

### 目标

准确判断当前市场处于**牛市、熊市、震荡市**，输出置信度和仓位建议。

### 数据源

- **全A指数**（000985）日K线：价格、成交量
- **北向资金**净流入（新增）
- **涨跌家数比**（新增）
- **全A股PE中位数分位数**（新增）

### 判断逻辑（多信号投票制）

```python
@dataclass
class MarketRegime:
    state: str                    # "bull" | "bear" | "sideways"
    confidence: float             # 0.0 ~ 1.0
    position_advice: float        # 建议仓位 0.0 ~ 1.0
    signals: dict[str, str]       # 各信号的原始判断: "bull" | "bear" | "neutral"
    description: str              # 人类可读描述
```

**信号矩阵（5个信号，多数投票）：**

| 信号         | 牛市条件                       | 熊市条件                       | 权重 |
| ------------ | ------------------------------ | ------------------------------ | ---- |
| 趋势信号     | MA20 > MA60 且 价格 > MA20     | MA20 < MA60 且 价格 < MA20     | 1票  |
| 成交量信号   | 近20日成交量 > 近60日均量×1.2 | 近20日成交量 < 近60日均量×0.8 | 1票  |
| 北向资金信号 | 近5日净流入 > 0 且累计 > 100亿 | 近5日净流出 > 0 且累计 > 100亿 | 1票  |
| 涨跌比信号   | 涨停家数/跌停家数 > 3.0        | 跌停家数/涨停家数 > 3.0        | 1票  |
| 估值信号     | 全A PE分位数 < 40%（近3年分位） | 全A PE分位数 > 70%（近3年分位） | 1票  |

**决策规则：**

- 牛市信号 >= 3 → 牛市，仓位建议 0.7~1.0
- 熊市信号 >= 3 → 熊市，仓位建议 0.0~0.3
- 其他 → 震荡市，仓位建议 0.3~0.7
- 置信度 = 胜出票数 / 总票数

**权重动态调整：**

- 牛市：提高动量因子权重，降低防御因子权重
- 熊市：提高低波动因子权重，降低进攻因子权重
- 震荡：使用默认权重

**仓位建议计算：**
- 牛市：`position_advice = 0.7 + 0.3 × confidence`（置信度越高仓位越重）
- 熊市：`position_advice = 0.3 - 0.3 × confidence`（置信度越高仓位越轻）
- 震荡：`position_advice = 0.5`（固定半仓）

---

## 五、阶段2：数据采集（pipeline/collect.py）

### 目标

统一采集所有数据源，返回结构化数据包。

### 数据源清单

#### 5.1 现有数据源（保留）

| 数据源          | 模块                        | 数据内容                     |
| --------------- | --------------------------- | ---------------------------- |
| BaoStock K线    | `baostock_data.py`        | 日K线（开高低收量）          |
| BaoStock 基本面 | `fundamental_analysis.py` | ROE、EPS、利润增速、营收增速 |
| AKShare 新闻    | `news_analysis.py`        | 财经新闻 + LLM政策分析       |
| AKShare 指数    | `pipeline/collect.py`     | 全A指数日K线（原market_regime.py的数据获取部分） |
| AKShare ETF     | `etf_analyzer.py`         | ETF份额/资金流               |

#### 5.2 新增数据源

| 数据源     | API                                                                  | 数据内容                | 优先级 |
| ---------- | -------------------------------------------------------------------- | ----------------------- | ------ |
| 北向资金   | `ak.stock_hsgt_hist_em(symbol="北向资金")`                       | 每日净流入/流出         | P0     |
| 融资融券   | `ak.stock_margin_detail_szse()` / `ak.stock_margin_detail_sse()` | 融资余额、融券余额（注意：沪深返回列名不同，需统一处理） | P1     |
| 涨跌停统计 | `ak.stock_zt_pool_em()` / `ak.stock_zt_pool_dtgc_em()`          | 涨停/跌停家数、连板高度 | P0     |
| 行业资金流 | `ak.stock_sector_fund_flow_rank()`                                 | 行业板块资金净流入排名  | P1     |
| 宏观指标   | `ak.macro_china_cpi_monthly()` 等                                  | CPI、PMI、利率          | P2     |
| 龙虎榜     | `ak.stock_lhb_detail_em()`                                         | 龙虎榜买卖席位          | P2     |

**优先级说明：**

- P0：必须实现，对择时和选股有直接帮助
- P1：第二阶段实现，增强因子库
- P2：可选，数据更新频率低，对日内交易帮助有限

### 数据包结构

```python
@dataclass
class DataBundle:
    # 指数数据
    index_kline: pd.DataFrame          # 全A指数日K线
  
    # 股票池
    stock_pool: pd.DataFrame           # 股票列表
  
    # 个股数据（code -> data）
    kline_cache: dict[str, pd.DataFrame]       # K线缓存
    fundamental_cache: dict[str, FundamentalData]  # 基本面缓存
  
    # 资金面（新增）
    north_flow: pd.DataFrame           # 北向资金每日净流入
    margin_data: pd.DataFrame | None   # 融资融券数据
  
    # 情绪面（新增）
    limit_up_count: int                # 今日涨停家数
    limit_down_count: int              # 今日跌停家数
    advance_decline_ratio: float       # 涨跌家数比
  
    # 宏观面（新增）
    macro_indicators: dict[str, float] # CPI, PMI, 利率等
  
    # 行业数据
    sector_flow: pd.DataFrame          # 行业资金流向
  
    # 新闻
    news_items: list[NewsItem]         # 新闻列表
    policy_impacts: list[PolicyImpact] # LLM政策分析结果
  
    # ETF
    etf_pool: list[EtfInfo]            # ETF列表
    etf_kline_cache: dict[str, pd.DataFrame]
```

---

## 六、阶段3：多因子计算（pipeline/factors.py）

### 目标

替代当前 `scoring.py`，用多因子模型计算每只股票的综合分数。

### 因子体系

#### 6.1 因子分类

| 因子类别         | 因子名称     | 计算方式                    | 数据来源     |
| ---------------- | ------------ | --------------------------- | ------------ |
| **技术面** | MA趋势得分   | MA5/MA10/MA20/MA60排列+交叉 | K线数据      |
|                  | MACD得分     | DIF/DEA交叉+柱状图+背离     | K线数据      |
|                  | 成交量得分   | 量比、量能趋势、天量/地量   | K线数据      |
|                  | 布林带得分   | 价格相对布林带位置          | K线数据      |
| **基本面** | 估值得分     | PE/PB分位数（行业内排名）   | 基本面数据   |
|                  | 盈利能力     | ROE、毛利率                 | 基本面数据   |
|                  | 成长性       | 利润增速、营收增速          | 基本面数据   |
| **资金面** | 北向资金得分 | 个股北向持仓变动            | 北向资金数据 |
|                  | 主力资金得分 | 大单净流入/流出             | 资金流数据   |
| **情绪面** | 市场情绪得分 | 涨跌比、涨停数、连板高度    | 情绪数据     |
|                  | 新闻情绪     | LLM政策分析得分             | 新闻数据     |
| **动量**   | 短期动量     | 近5日/10日收益率            | K线数据      |
|                  | 中期动量     | 近20日/60日收益率           | K线数据      |
|                  | 相对强弱     | 个股vs行业ETF相对收益       | K线+ETF数据  |

#### 6.2 因子编排

`pipeline/factors.py` 作为编排层，调用各因子模块计算类别分数：

```python
def calc_factors(data: DataBundle, config: AppConfig) -> dict[str, FactorScores]:
    """遍历股票池，对每只股票计算所有因子类别分数并合成"""
    from factors.technical import calc_technical_score
    from factors.fundamental import calc_fundamental_score
    from factors.capital import calc_capital_score
    from factors.sentiment import calc_sentiment_score
    from factors.momentum import calc_momentum_score

    results = {}
    for _, row in data.stock_pool.iterrows():
        code = row['code']
        technical = calc_technical_score(data.kline_cache[code])
        fundamental = calc_fundamental_score(data.fundamental_cache[code])
        capital = calc_capital_score(code, data.north_flow)
        sentiment = calc_sentiment_score(data.limit_up_count, data.limit_down_count, data.policy_impacts)
        momentum = calc_momentum_score(code, data.kline_cache, data.etf_kline_cache)
        # 百分位排名 + 加权合成（见下文）
        results[code] = combine_scores(code, row['name'], technical, fundamental, capital, sentiment, momentum, config)
    return results
```

#### 6.3 因子标准化

每个因子计算原始值后，标准化为 0~100 分。**采用截面百分位排名法**（在股票池内排名），而非绝对值比较：

```python
def percentile_to_0_100(values: pd.Series) -> pd.Series:
    """将因子值在股票池内做百分位排名，映射到0-100"""
    return values.rank(pct=True) * 100
```

**为什么用百分位而非Z-score：** Z-score受极端值影响大（如某只股票PE极高会压缩其他股票的分数），百分位排名更稳健，且天然产生均匀分布。

#### 6.4 因子合成

```python
@dataclass
class FactorScores:
    code: str
    name: str
  
    # 各因子原始分数（0-100）
    technical_score: float      # 技术面综合
    fundamental_score: float    # 基本面综合
    capital_score: float        # 资金面综合
    sentiment_score: float      # 情绪面综合
    momentum_score: float       # 动量综合
  
    # 各因子子项（用于报告展示）
    technical_detail: dict[str, float]
    fundamental_detail: dict[str, float]
  
    # 最终分数
    total_score: float          # 加权合成后的总分
    rank: int                   # 在股票池中的排名
```

**子因子聚合为类别分数：**

每个类别内的子因子先做等权平均，再参与类别间的加权合成：

```
technical_score = (ma_trend + macd + volume + bollinger) / 4
fundamental_score = (valuation + profitability + growth) / 3
capital_score = (north_flow + main_flow) / 2
sentiment_score = (market_sentiment + news_sentiment) / 2
momentum_score = (short_momentum + mid_momentum + relative_strength) / 3
```

**类别间合成公式：**

```
total_score = Σ (category_score_i × weight_i)
```

权重由市场环境阶段动态决定：

| 环境 | 技术面 | 基本面 | 资金面 | 情绪面 | 动量 |
| ---- | ------ | ------ | ------ | ------ | ---- |
| 牛市 | 0.30   | 0.15   | 0.15   | 0.10   | 0.30 |
| 熊市 | 0.25   | 0.30   | 0.15   | 0.15   | 0.15 |
| 震荡 | 0.30   | 0.20   | 0.15   | 0.15   | 0.20 |

#### 6.5 因子有效性检验（IC检验）

**目的：** 验证每个因子对未来收益的预测能力。

**方法：**

```python
def calc_ic(factor_values: pd.Series, future_returns: pd.Series) -> float:
    """计算因子IC（Information Coefficient）= 秩相关系数"""
    return factor_values.corr(future_returns, method='spearman')

def calc_ic_ir(ic_series: pd.Series) -> float:
    """IC_IR = mean(IC) / std(IC)，衡量因子稳定性"""
    return ic_series.mean() / max(ic_series.std(), 1e-8)
```

**使用方式：**

- 回测时计算每个因子的IC和IC_IR
- IC_IR > 0.5 的因子视为有效，权重上调
- IC_IR < 0.2 的因子视为无效，权重下调或移除
- IC检验结果输出到报告中，供人工审核

---

## 七、阶段4：信号生成（pipeline/signal.py）

### 目标

基于因子分数，生成明确的买入/卖出信号，附带置信度和关键价位。

### 7.1 信号投票制

不再用单一阈值判断，而是多个独立信号各自投票：

```python
@dataclass
class VoteSignal:
    name: str           # 信号名称
    vote: str           # "buy" | "sell" | "neutral"
    confidence: float   # 0.0 ~ 1.0
    reason: str         # 投票理由
```

**投票信号列表：**

| 信号     | 买入条件                       | 卖出条件                       |
| -------- | ------------------------------ | ------------------------------ |
| 因子综合 | total_score >= 70              | total_score <= 30              |
| 技术面   | technical_score >= 75 且有金叉 | technical_score <= 25 且有死叉 |
| 资金面   | 北向+主力净流入 > 流通市值0.1% | 北向+主力净流出 > 流通市值0.1% |
| 动量     | 短期动量 > 0 且中期动量 > 0    | 短期动量 < 0 且中期动量 < 0    |
| 市场环境 | 牛市且个股趋势向上             | 熊市且个股趋势向下             |

**决策规则：**

- 买入信号：>= 3票买入，且无卖出票 > 1
- 卖出信号：>= 3票卖出，且无买入票 > 1
- 其他：观望

**置信度：** 触发方向的票数 / 总票数（买入时 = 买入票数/5，卖出时 = 卖出票数/5）

### 7.2 关键价位计算

```python
@dataclass
class KeyPrices:
    current_price: float
    support: float          # 支撑位
    resistance: float       # 压力位
    target_price: float     # 目标价
    stop_loss: float        # 止损价
    risk_reward_ratio: float # 盈亏比
```

**算法改进（相比当前版本）：**

- 支撑位：MA20 + 近20日低点 + 布林带下轨，取中位数
- 压力位：MA20 + 近20日高点 + 布林带上轨，取中位数
- 目标价：当前价 + ATR × 2（基于波动率的目标，而非固定倍数）
- 止损价：当前价 - ATR × 1.5（基于波动率的止损）
- 盈亏比：(目标价 - 当前价) / (当前价 - 止损价)，要求 >= 2:1

### 7.3 信号输出

```python
@dataclass
class Signal:
    code: str
    name: str
    is_etf: bool
    action: str             # "buy" | "sell" | "hold"
    confidence: float       # 0.0 ~ 1.0
    votes: list[VoteSignal] # 各信号投票详情
    key_prices: KeyPrices
    factor_scores: FactorScores
    reason_summary: str     # 综合理由（一句话）
```

---

## 八、阶段5：输出（pipeline/output.py）

### 8.1 每日报告

**内容结构：**

1. **市场环境摘要**：当前牛/熊/震荡，置信度，仓位建议
2. **买入信号列表**：按置信度排序，每只股票附带因子分数、关键价位、投票详情
3. **卖出信号列表**：同上
4. **重点关注**：置信度最高的3只股票，详细分析
5. **因子IC报告**：各因子近期有效性（可选，周报级别）
6. **ETF信号**：ETF的买卖信号

**格式：** Markdown（微信推送）+ HTML（详细版）

### 8.2 实时提醒

**触发条件：**

- 盘中某只股票因子分数突变（如从50跳到75）
- 市场环境状态切换（如从震荡转为牛市）
- 北向资金大幅流入/流出（单日 > 100亿）

**推送方式：** 微信推送（复用现有 PushPlus 通道）

**实现方式：** 定时任务（cron / GitHub Actions）每30分钟检查一次

---

## 九、回测引擎（backtest.py 重写）

### 核心原则

**回测与生产共用同一套因子计算代码**，消除当前信号不一致的问题。

### 设计

`BacktestConfig` 定义在 `config.py` 中（见第九章），此处定义结果结构：

```python
@dataclass
class BacktestResult:
    period: str                 # 持有天数
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

### 回测流程

```
1. 加载历史数据（AKShare）
2. 对每个交易日：
   a. 计算当日所有股票的因子分数（复用 pipeline/factors.py）
   b. 生成信号（复用 pipeline/signal.py）
   c. 模拟交易（考虑手续费、滑点）
3. 汇总统计：胜率、夏普、最大回撤等
4. 输出回测报告
```

### 关键改进

| 当前问题       | 改进方案                         |
| -------------- | -------------------------------- |
| 回测用简化信号 | 复用生产因子计算代码             |
| 无手续费/滑点  | 加入 commission_rate 和 slippage |
| 无资金管理     | 模拟实际资金曲线                 |
| 只看收益率     | 增加夏普比率、最大回撤、卡玛比率 |
| 串行执行       | 并行处理多只股票                 |

---

## 十、配置扩展（config.py）

### 新增配置项

```python
@dataclass
class RegimeConfig:
    """市场环境判断配置"""
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
    """因子权重配置（按市场环境）"""
    bull: dict[str, float]      # 牛市权重
    bear: dict[str, float]      # 熊市权重
    sideways: dict[str, float]  # 震荡权重

@dataclass
class SignalConfig:
    """信号生成配置"""
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
    """实时提醒配置"""
    check_interval_minutes: int = 30
    score_jump_threshold: float = 25.0  # 分数跳变阈值
    north_flow_alert: float = 100e8     # 北向资金 alert 阈值

@dataclass
class BacktestConfig:
    """回测配置"""
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

### 配置文件支持

新增 YAML 配置文件支持（可选，优先级低于环境变量）。需新增依赖：

```
# requirements.txt 新增
pyyaml>=6.0
```

```yaml
# config.yaml
regime:
  ma_short: 20
  ma_long: 60

factor_weights:
  bull:
    technical: 0.30
    fundamental: 0.15
    capital: 0.15
    sentiment: 0.10
    momentum: 0.30
  bear:
    technical: 0.25
    fundamental: 0.30
    capital: 0.15
    sentiment: 0.15
    momentum: 0.15
  sideways:
    technical: 0.30
    fundamental: 0.20
    capital: 0.15
    sentiment: 0.15
    momentum: 0.20

signal:
  min_buy_votes: 3
  atr_target_multiplier: 2.0
```

---

## 十一、数据源实现细节

### 11.1 北向资金（capital_flow.py）

```python
# AKShare API
import akshare as ak

def fetch_north_flow(days: int = 5) -> pd.DataFrame:
    """获取北向资金每日净流入"""
    df = ak.stock_hsgt_hist_em(symbol="北向资金")
    # 列名: 日期, 当日成交净买额, 当日资金流入 等
    return df.tail(days)

def fetch_north_flow_stock(code: str) -> float:
    """获取个股北向持仓变动（持股数量变化）
    
    注意：market="北向" 可能因网络问题返回 None，需做异常处理
    列名: 代码, 名称, 今日持股-股数, 今日持股-市值, 今日持股-占流通股比 等
    """
    try:
        df = ak.stock_hsgt_hold_stock_em(market="沪股通", indicator="今日排行")
        row = df[df['代码'] == code]
        if len(row) == 0:
            df = ak.stock_hsgt_hold_stock_em(market="深股通", indicator="今日排行")
            row = df[df['代码'] == code]
        if len(row) == 0:
            return 0.0
        return float(row.iloc[0]['今日持股-股数'])
    except Exception:
        return 0.0
```

### 11.2 涨跌停统计（sentiment.py）

```python
def fetch_limit_stats(date: str) -> dict:
    """获取涨跌停统计
    
    Args:
        date: 交易日期，格式 YYYYMMDD
    """
    zt = ak.stock_zt_pool_em(date=date)          # 涨停池
    dt = ak.stock_zt_pool_dtgc_em(date=date)     # 跌停池（注意函数名不同）
    return {
        "limit_up_count": len(zt),
        "limit_down_count": len(dt),
        "max_consecutive": zt['涨停统计'].str.split('天').str[0].astype(int).max() if len(zt) > 0 else 0,
    }
```

### 11.3 行业资金流向（sector_flow.py）

```python
def fetch_sector_flow() -> pd.DataFrame:
    """获取行业板块资金流向排名
    
    注意：列名随 indicator 参数动态变化（"今日" → "5日" → "10日"）
    返回列: 名称, 今日主力净流入-净额, 今日主力净流入-净占比, 今日主力净流入最大股 等
    """
    df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    # 过滤掉列名为 "-" 的无用列
    df = df.loc[:, df.columns != '-']
    return df
```

### 11.4 宏观指标（macro.py）

```python
def fetch_macro_indicators() -> dict[str, float]:
    """获取最新宏观指标"""
    cpi = ak.macro_china_cpi_monthly()  # 列名: 商品, 日期, 今值, 预测值, 前值
    pmi = ak.macro_china_pmi()          # 列名: 月份, 制造业-指数, 制造业-同比增长, ...
    return {
        "cpi": float(cpi.iloc[-1]['今值']) if len(cpi) > 0 else None,
        "pmi": float(pmi.iloc[-1]['制造业-指数']) if len(pmi) > 0 else None,
    }
```

---

## 十二、实时提醒机制

### 实现方案

在 `main.py` 中新增 `--realtime` 模式：

```bash
# 每日分析模式（现有）
python src/main.py

# 实时监控模式（新增）
python src/main.py --realtime
```

### quick_collect 函数

只采集实时监控所需的最小数据集（非全量采集），返回 `DataBundle`：
- 最新1日K线（所有股票池中的股票）
- 最新北向资金数据
- 最新涨跌停统计
- 不重新获取基本面数据（使用缓存）

### 缺失函数说明

以下函数在监控代码中引用，实现时定义在对应模块中：
- `judge_market_regime(data)` → `pipeline/regime.py` 的主函数
- `calc_factors(data, config)` → `pipeline/factors.py` 的主函数，返回 `dict[str, FactorScores]`
- `push_alerts(alerts, config)` → `pipeline/output.py` 的推送函数

### 数据结构

```python
@dataclass
class ScoreAlert:
    code: str
    delta: float
    score: FactorScores
    message: str

@dataclass
class RegimeAlert:
    old_state: str
    new_regime: MarketRegime
    message: str
```

### 监控逻辑

```python
def realtime_monitor(config: AppConfig):
    """实时监控主循环（交易时段 9:30-15:00 运行）"""
    last_scores = {}  # code -> last_score
    last_regime = None  # 上一次市场环境状态
  
    while True:
        # 1. 快速采集数据（只取最新K线和资金流）
        data = quick_collect(config)
      
        # 2. 计算因子分数
        scores = calc_factors(data, config)
      
        # 3. 检查触发条件
        alerts = []
        for code, score in scores.items():
            if code in last_scores:
                delta = score.total_score - last_scores[code]
                if abs(delta) >= config.realtime.score_jump_threshold:
                    direction = "↑" if delta > 0 else "↓"
                    alerts.append(ScoreAlert(
                        code=code, delta=delta, score=score,
                        message=f"{score.name} 分数{direction}{abs(delta):.1f} → {score.total_score:.1f}"
                    ))
            last_scores[code] = score.total_score

        # 4. 检查市场环境变化
        regime = judge_market_regime(data)
        if last_regime is not None and regime.state != last_regime:
            alerts.append(RegimeAlert(
                old_state=last_regime, new_regime=regime,
                message=f"市场环境切换：{last_regime} → {regime.state}"
            ))
        last_regime = regime.state
      
        # 5. 推送提醒
        if alerts:
            push_alerts(alerts, config)
      
        # 6. 等待下一轮
        time.sleep(config.realtime.check_interval_minutes * 60)
```

---

## 十三、实施路线图

### 阶段一：基础设施（预计2-3天）

1. 创建 `pipeline/` 和 `data_sources/` 和 `factors/` 目录结构
2. 实现 `pipeline/collect.py`（统一数据采集）
3. 实现 `data_sources/capital_flow.py`（北向资金，P0）
4. 实现 `data_sources/sentiment.py`（涨跌停统计，P0）
5. 扩展 `config.py`（新增配置项）

### 阶段二：核心引擎（预计3-4天）

6. 实现 `pipeline/regime.py`（市场环境判断，重写）
7. 实现 `factors/` 各因子模块
8. 实现 `pipeline/factors.py`（多因子计算引擎）
9. 实现 `pipeline/signal.py`（信号投票制）

### 阶段三：回测验证（预计2-3天）

10. 重写 `backtest.py`（与生产共用因子代码）
11. 运行回测，验证因子有效性（IC检验）
12. 根据回测结果调整因子权重

### 阶段四：集成输出（预计2天）

13. 实现 `pipeline/output.py`（报告+推送）
14. 精简 `main.py` 为管道编排器
15. 实现实时提醒模式

### 阶段五：增强（可选）

16. 实现 `data_sources/sector_flow.py`（P1）
17. 实现 `data_sources/macro.py`（P2）
18. 龙虎榜数据（P2）
19. YAML配置文件支持

---

## 十四、风险与应对

| 风险                 | 影响           | 应对                                                      |
| -------------------- | -------------- | --------------------------------------------------------- |
| AKShare API变更/限流 | 数据获取失败   | 保留BaoStock作为主数据源，AKShare作为补充；增加重试和缓存 |
| 新数据源数据质量差   | 因子计算错误   | 数据校验+异常值处理+缺失值填充                            |
| 回测过拟合           | 策略在实盘失效 | 样本外测试、滚动回测、因子IC持续监控                      |
| 改造范围过大         | 无法按时完成   | 分阶段实施，每阶段可独立运行验证                          |
| 与现有功能冲突       | 回归bug        | 保留旧模块，新模块独立，通过main.py切换                   |
| 实时监控API限流      | 监控中断       | 控制请求频率，增加重试和降级逻辑                          |

---

## 十五、ETF评分方案

ETF使用与股票不同的因子体系：

| 因子类别   | 因子名称     | 计算方式               | 权重（牛市） | 权重（熊市） | 权重（震荡） |
| ---------- | ------------ | ---------------------- | ------------ | ------------ | ------------ |
| **技术面** | MA趋势       | MA5/10/20/60排列       | 0.25         | 0.20         | 0.25         |
|            | MACD         | DIF/DEA交叉+柱状图     | 0.15         | 0.10         | 0.15         |
|            | 成交量       | 量比、量能趋势         | 0.10         | 0.10         | 0.10         |
| **资金面** | 份额变动     | ETF份额增减趋势        | 0.20         | 0.25         | 0.20         |
|            | 净流入       | 资金净流入/流出        | 0.10         | 0.15         | 0.10         |
| **情绪面** | 新闻情绪     | LLM政策分析得分        | 0.15         | 0.15         | 0.15         |
| **动量**   | 短期动量     | 近5日/10日收益率       | 0.05         | 0.05         | 0.05         |

**ETF信号生成：** 使用与股票相同的投票制，但投票信号简化为3票：
- 因子综合（总分 >= 70 买入 / <= 30 卖出）
- 技术面（技术分 >= 75 买入 / <= 25 卖出）
- 资金面（份额连续增长 买入 / 连续下降 卖出）

---

## 十六、旧模块处理方案

### 过渡期策略（双轨并行）

重构完成后，旧模块不立即删除，而是通过配置开关切换：

```python
# config.py
@dataclass
class AppConfig:
    use_v2_pipeline: bool = False  # False=旧流程, True=新管道
```

**过渡流程：**
1. 新管道开发完成后，`use_v2_pipeline=False`（默认旧流程）
2. 运行新管道并对比输出，确认无回归
3. 切换为 `use_v2_pipeline=True`（默认新管道）
4. 观察1-2周，确认稳定
5. 删除旧模块：`scoring.py`、`market_regime.py`、`buy_sell_signal.py`

### 需要删除的旧模块

| 模块                | 替代方案              | 删除时机               |
| ------------------- | --------------------- | ---------------------- |
| `scoring.py`        | `pipeline/factors.py` | 新管道稳定后           |
| `market_regime.py`  | `pipeline/regime.py`  | 新管道稳定后           |
| `buy_sell_signal.py`| `pipeline/signal.py`  | 新管道稳定后           |

---

## 十七、测试策略

### 测试范围

| 模块                | 测试类型     | 测试重点                                   |
| ------------------- | ------------ | ------------------------------------------ |
| `pipeline/regime.py`| 单元测试     | 各信号判断逻辑、投票决策、边界条件         |
| `pipeline/collect.py`| 集成测试    | 数据源调用、异常处理、缓存命中             |
| `pipeline/factors.py`| 单元测试    | 因子计算正确性、标准化、权重合成           |
| `pipeline/signal.py`| 单元测试     | 投票逻辑、关键价位计算、边界条件           |
| `data_sources/*`    | 集成测试     | API调用、数据格式解析、异常降级            |
| `backtest.py`       | 集成测试     | 回测流程完整性、统计指标正确性             |
| `factors/*`         | 单元测试     | 各因子计算逻辑、边界值处理                 |

### 测试原则

- 所有外部API调用使用 `monkeypatch` 模拟，不依赖网络
- 因子计算测试使用构造的DataFrame，验证数值正确性
- 信号投票测试覆盖所有投票组合（5票中3票买入、2票卖出等）
- 回测测试使用小数据集（5只股票×20天），验证统计指标

### 测试文件结构

```
tests/
├── test_pipeline_regime.py
├── test_pipeline_collect.py
├── test_pipeline_factors.py
├── test_pipeline_signal.py
├── test_pipeline_output.py
├── test_data_sources.py
├── test_factors_technical.py
├── test_factors_fundamental.py
├── test_factors_capital.py
├── test_factors_sentiment.py
├── test_factors_momentum.py
└── test_backtest_v2.py
```

---

## 十八、可行性评估总结

### API可用性（已验证）

| 优先级 | 数据源 | API | 状态 | 备注 |
|--------|--------|-----|------|------|
| P0 | 北向资金(整体) | `ak.stock_hsgt_hist_em(symbol="北向资金")` | ✅ | 返回DataFrame，列：日期/当日成交净买额/当日资金流入 |
| P0 | 北向资金(个股) | `ak.stock_hsgt_hold_stock_em(market, indicator)` | ⚠️ | market="北向"可能返回None，建议分沪股通/深股通两次调用 |
| P0 | 涨停统计 | `ak.stock_zt_pool_em(date)` | ✅ | date格式YYYYMMDD |
| P0 | 跌停统计 | `ak.stock_zt_pool_dtgc_em(date)` | ✅ | 仅支持近30天数据 |
| P1 | 融资融券(深) | `ak.stock_margin_detail_szse(date)` | ✅ | 沪深列名不同，需统一 |
| P1 | 融资融券(沪) | `ak.stock_margin_detail_sse(date)` | ✅ | 同上 |
| P1 | 行业资金流 | `ak.stock_sector_fund_flow_rank(indicator, sector_type)` | ✅ | 列名随indicator动态变化 |
| P2 | CPI | `ak.macro_china_cpi_monthly()` | ✅ | 无参数，返回历史数据 |
| P2 | PMI | `ak.macro_china_pmi()` | ✅ | 无参数，返回历史数据 |
| P2 | 龙虎榜 | `ak.stock_lhb_detail_em(start_date, end_date)` | ✅ | 日期范围查询 |
| - | 指数K线 | `ak.stock_zh_index_daily(symbol)` | ✅ | symbol格式：sh000001 |
| - | ETF数据 | `ak.fund_etf_fund_daily_em()` | ✅ | 无参数，返回所有ETF |

### 依赖评估

| 依赖 | 当前版本 | 需要升级？ | 说明 |
|------|---------|-----------|------|
| akshare | ≥1.10.0 (实际1.18.64) | 建议锁定≥1.14.0 | 所有API在1.14+可用 |
| baostock | ≥0.8.8 | 否 | 只用query_history_k_data_plus() |
| pandas | ≥2.0.0 | 否 | 百分位排名等高级功能 |
| numpy | ≥1.24.0 | 否 | 技术指标计算 |
| pyyaml | 未安装 | 需新增（可选） | YAML配置文件支持 |

### 风险点

1. **北向资金API不稳定**：`stock_hsgt_hold_stock_em(market="北向")` 可能返回None，需分沪/深分别调用
2. **跌停数据限制**：`stock_zt_pool_dtgc_em` 仅支持近30天，无法用于历史回测
3. **融资融券列名差异**：沪深两市返回的列名不同，需要统一映射
4. **行业资金流列名动态**：`stock_sector_fund_flow_rank` 的列名随indicator参数变化
5. **AKShare版本漂移**：当前未锁定版本，建议在requirements.txt中锁定最低版本

### 结论

**可行性：高**。所有P0级API均已验证可用，只需修正2个API名称（已更新到文档）。无新增核心依赖，现有技术栈完全满足需求。
