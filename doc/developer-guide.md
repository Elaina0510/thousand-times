# 开发者文档

> 版本：v1.0
> 日期：2026-06-13

---

## 一、项目架构

### 1.1 模块总览

项目包含 21 个源码模块，按职责分为 5 层：

```
┌─────────────────────────────────────────────┐
│                 编排层（main.py）              │
├─────────────────────────────────────────────┤
│              分析层（analysis）                │
│  technical_analysis  fundamental_analysis    │
│  news_analysis  scoring  buy_sell_signal     │
│  sector_analysis  price_analysis             │
├─────────────────────────────────────────────┤
│              数据层（data）                    │
│  stock_filter  etf_analyzer                  │
│  baostock_data  ashare_data  remote_data     │
├─────────────────────────────────────────────┤
│              输出层（output）                  │
│  chart_generator  report_generator           │
│  push_service                                 │
├─────────────────────────────────────────────┤
│              基础层（infra）                   │
│  config  cache_manager  utils                │
└─────────────────────────────────────────────┘
```

### 1.2 模块依赖关系

```
main.py（编排整个流水线）
├── config.py（无外部依赖）
├── stock_filter.py → baostock_data / AKShare
├── etf_analyzer.py → baostock_data / AKShare
├── technical_analysis.py → baostock_data, Pandas, NumPy
├── fundamental_analysis.py → baostock_data / AKShare
├── news_analysis.py → AKShare, LLM API
├── scoring.py（无外部依赖）
├── buy_sell_signal.py → technical_analysis, config
├── sector_analysis.py → scoring, buy_sell_signal
├── price_analysis.py → technical_analysis, buy_sell_signal, config
├── chart_generator.py → mplfinance, Matplotlib
├── report_generator.py → scoring, buy_sell_signal, news_analysis
├── push_service.py → Requests
└── cache_manager.py（JSON 文件 I/O）
```

---

## 二、核心数据结构

### 2.1 KlineData（K线数据）

```python
@dataclass
class KlineData:
    dates: list[str]       # 日期列表（YYYY-MM-DD）
    opens: list[float]     # 开盘价
    highs: list[float]     # 最高价
    lows: list[float]      # 最低价
    closes: list[float]    # 收盘价
    volumes: list[float]   # 成交量
    ma5: list[float]       # 5日均线
    ma10: list[float]      # 10日均线
    ma20: list[float]      # 20日均线
    ma60: list[float]      # 60日均线
    dif: list[float]       # MACD DIF线
    dea: list[float]       # MACD DEA线
    macd_hist: list[float] # MACD柱状图
```

### 2.2 TechnicalSignals（技术信号）

```python
@dataclass
class TechnicalSignals:
    ma5_10_golden: bool    # MA5/10金叉（近3日）
    ma5_10_death: bool     # MA5/10死叉（近3日）
    ma20_60_golden: bool   # MA20/60金叉（近5日）
    bullish_alignment: bool # 多头排列
    above_ma20: bool       # 股价站上MA20
    macd_golden: bool      # MACD金叉（近3日）
    macd_death: bool       # MACD死叉（近3日）
    macd_above_zero: bool  # 零轴上方金叉
    macd_divergence: bool  # MACD底背离（近10日）
    volume_up: bool        # 放量上涨
    volume_down: bool      # 放量下跌
    volume_peak: bool      # 天量见天价
    pullback_ok: bool      # 缩量回调到位
```

### 2.3 ScoreResult（评分结果）

```python
@dataclass
class ScoreResult:
    code: str                      # 股票/ETF代码
    name: str                      # 名称
    is_etf: bool                   # 是否为ETF
    technical_score: float         # 技术指标评分
    fundamental_score: float | None # 基本面评分（ETF为None）
    news_score: float              # 政策新闻评分
    industry_score: float | None   # 行业趋势评分（ETF为None）
    fund_flow_score: float | None  # 资金流向评分（个股为None）
    total_score: float             # 综合评分（0-100）
    profit_probability: float      # 盈利概率（0-100%）
    judgment: str                  # "recommend"/"watch"/"bearish"/"risk"
    technical_signals: TechnicalSignals
    news_summary: str              # 新闻摘要
```

### 2.4 BuySellSignal（买卖信号）

```python
@dataclass
class BuySellSignal:
    code: str
    name: str
    is_etf: bool
    signal_score: int              # 0-100分
    signal_zone: str               # "买入区"/"观望区"/"卖出区"
    signal_emoji: str              # 🟢/🟡/🔴
    technical_score: float
    fund_flow_score: float
    fundamental_score: float | None
    news_score: float
    key_prices: KeyPrice           # 关键价位
    sector_comparison: SectorComparison | None # 板块对比
    historical_accuracy: list[HistoricalAccuracy]
    link: str                      # 行情链接
```

### 2.5 AppConfig（应用配置）

```python
@dataclass
class AppConfig:
    filter: FilterConfig           # 股票池筛选配置
    score_weight: ScoreWeightConfig # 评分权重配置
    technical_weight: TechnicalWeightConfig
    fundamental_weight: FundamentalWeightConfig
    news_weight: NewsWeightConfig
    industry_trend_weight: IndustryTrendWeightConfig
    etf_fund_flow_weight: EtfFundFlowWeightConfig
    etf_pool: list[str]            # ETF代码列表
    buy_sell_signal: BuySellSignalConfig
    score_threshold_high: float    # 推荐阈值（默认75）
    score_threshold_low: float     # 风险阈值（默认45）
    request_delay_range: tuple[float, float]
    max_retries: int
    lookback_days: int             # 技术指标回溯天数（默认60）
    llm_api_url: str
    llm_api_key: str
```

---

## 三、数据流

### 3.1 主流程（main.py）

```
1. 加载配置（config.load_config）
     │
2. 并行获取（ThreadPoolExecutor, max_workers=3）
     ├── 获取股票池（stock_filter.get_stock_pool）
     ├── 获取ETF池（etf_analyzer.get_etf_pool）
     └── 获取新闻（news_analysis.fetch_news + filter_by_credibility）
     │
3. 政策影响分析（news_analysis.analyze_policy_impact）
     │
4. 分析个股（遍历股票池）
     ├── 获取K线数据（优先缓存，未命中则 BaoStock 批量获取）
     ├── 获取基本面数据（优先缓存，未命中则批量获取）
     ├── 计算技术指标（technical_analysis.calc_technical_signals）
     ├── 计算基本面评分（fundamental_analysis.calc_fundamental_score）
     ├── 计算政策新闻评分（news_analysis.get_industry_impact_score）
     ├── 计算行业趋势评分（scoring.get_industry_trend_score）
     ├── 计算综合评分（scoring.calc_total_score）
     └── 筛选 ≥75 或 <45 的标的
     │
5. 分析ETF（遍历ETF池，复用预获取的K线缓存）
     ├── 计算技术指标
     ├── 计算政策新闻评分
     ├── 计算资金流向评分（etf_analyzer.get_etf_fund_flow）
     ├── 计算综合评分
     └── 筛选 ≥75 或 <45 的标的
     │
6. 构建板块对比数据（sector_analysis.build_sector_stocks）
     │
7. 生成买卖信号（buy_sell_signal.generate_buy_sell_signal）
     │
8. 生成图表（chart_generator.generate_chart，ThreadPoolExecutor 并行）
     │
9. 生成报告（report_generator.generate_report）
     │
10. 推送（push_service.push_to_wechat）
```

### 3.2 数据获取策略

```
K线数据获取：
  1. 检查磁盘缓存（cache_manager.load_cached_dataframe）
     ├── 命中 → 使用缓存
     └── 未命中 → 继续
  2. 并行批量获取（parallel_batch_fetch, workers=4）
     ├── BaoStock 批量获取（baostock_data.get_stock_hist_batch_baostock）
     └── 写入缓存（cache_manager.set_cached_data）

基本面数据获取：
  1. 检查磁盘缓存
     ├── 命中 → 反序列化为 FundamentalData
     └── 未命中 → 继续
  2. 并行批量获取（parallel_batch_fetch, workers=4）
     └── 写入缓存
```

---

## 四、评分算法

### 4.1 技术指标计算

#### MA（移动平均线）

```python
MA(n) = sum(close[i] for i in range(n)) / n
```

#### MACD

```python
EMA(n) = close * 2/(n+1) + prev_EMA * (n-1)/(n+1)
DIF = EMA(12) - EMA(26)
DEA = DIF * 2/(9+1) + prev_DEA * (9-1)/(9+1)
MACD柱 = (DIF - DEA) * 2
```

#### 量比

```python
volume_ratio = today_volume / mean(volume[-5:])
```

### 4.2 综合评分计算

#### 个股四维度模型

```python
# 归一化各维度到 0-100
tech_norm = normalize(technical_score, TECHNICAL_MAX)     # 0~100
trend_norm = normalize(industry_score, TREND_MAX)          # 0~100
vp_norm = normalize(news_score + TREND_MAX, VOLUME_PRICE_MAX) # 0~100
fund_norm = normalize(fundamental_score, FUNDAMENTAL_MAX)  # 0~100

# 加权求和
total = (tech_norm * 0.35
       + trend_norm * 0.25
       + vp_norm * 0.20
       + fund_norm * 0.20)

# 截断到 [0, 100]
total = max(0, min(100, total))
```

#### ETF 三维度模型

```python
tech_norm = normalize(technical_score, TECHNICAL_MAX)
news_norm = normalize(news_score, ETF_NEWS_MAX)
flow_norm = normalize(fund_flow_score, ETF_FUND_FLOW_MAX)

total = (tech_norm * 0.55
       + news_norm * 0.35
       + flow_norm * 0.10)
```

### 4.3 盈利概率转换

使用归一化的 sigmoid 函数：

```python
k = 0.1
x0 = 50
raw = 1 / (1 + math.exp(-k * (score - x0)))
low = 1 / (1 + math.exp(-k * (0 - x0)))
high = 1 / (1 + math.exp(-k * (100 - x0)))
probability = (raw - low) / (high - low) * 100
```

映射关系：
- 评分 0 → 概率约 12%
- 评分 50 → 概率约 50%
- 评分 75 → 概率约 88%
- 评分 100 → 概率约 100%

---

## 五、开发指南

### 5.1 环境搭建

```bash
# 1. 克隆仓库
git clone <repo-url>
cd thousand-times

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 5. 验证配置
python verify_config.py

# 6. 运行测试
pytest tests/ -v
```

### 5.2 代码规范

#### 类型注解

所有函数参数和返回值必须有类型注解：

```python
def calc_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float:
    """计算基本面评分。"""
    ...
```

#### Docstring

所有公共函数和类必须有 Google 风格 docstring：

```python
def get_stock_pool(config: FilterConfig) -> pd.DataFrame:
    """获取筛选后的股票池。

    Args:
        config: 股票池筛选配置。

    Returns:
        包含 code, name, market_cap 等列的 DataFrame，
        按 market_cap 降序排列，取前 config.pool_size 条。
    """
```

#### 日志

使用统一的 logger：

```python
import logging
logger = logging.getLogger("thousand-times")

logger.info("开始分析...")
logger.warning(f"数据缺失: {code}")
logger.error(f"推送失败: {e}")
```

### 5.3 添加新数据源

1. 在 `src/` 下创建新的数据源模块（如 `new_data_source.py`）
2. 实现标准接口：`get_stock_hist(code, days) -> pd.DataFrame`
3. 在 `technical_analysis.py` 的 `_fetch_stock_hist_ashare` 中添加回退逻辑
4. 在 `requirements.txt` 中添加新依赖
5. 编写对应的测试文件

### 5.4 添加新评分维度

1. 在 `config.py` 中添加新的权重配置 dataclass
2. 在 `AppConfig` 中添加新配置字段
3. 在 `scoring.py` 的 `ScoreCalculator` 中实现新维度的评分逻辑
4. 更新 `calc_total_score` 函数的权重计算
5. 在 `main.py` 的 `analyze_single_stock` / `analyze_single_etf` 中调用新维度
6. 更新 `report_generator.py` 的输出格式
7. 编写测试

### 5.5 修改 ETF 池

编辑 `src/config.py` 中的 `DEFAULT_ETF_POOL`：

```python
DEFAULT_ETF_POOL: list[str] = [
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    # 添加新的ETF代码...
]
```

### 5.6 调整评分权重

编辑 `src/config.py` 中的相关 dataclass：

```python
@dataclass
class ScoreWeightConfig:
    # 个股权重（四项之和应为 1.0）
    stock_technical: float = 0.35
    stock_trend: float = 0.25
    stock_volume_price: float = 0.20
    stock_fundamental: float = 0.20
    # ETF权重（三项之和应为 1.0）
    etf_technical: float = 0.55
    etf_news: float = 0.35
    etf_fund_flow: float = 0.10
```

---

## 六、测试

### 6.1 测试结构

每个模块在 `tests/` 下有对应的测试文件：

| 模块 | 测试文件 |
|------|----------|
| config.py | test_config.py |
| stock_filter.py | test_stock_filter.py |
| etf_analyzer.py | test_etf_analyzer.py |
| technical_analysis.py | test_technical_analysis.py |
| fundamental_analysis.py | test_fundamental_analysis.py |
| news_analysis.py | test_news_analysis.py |
| scoring.py | test_scoring.py |
| buy_sell_signal.py | test_buy_sell_signal.py |
| sector_analysis.py | test_sector_analysis.py |
| price_analysis.py | test_price_analysis.py |
| chart_generator.py | test_chart_generator.py |
| report_generator.py | test_report_generator.py |
| push_service.py | test_push_service.py |
| main.py | test_main.py |

### 6.2 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行指定测试文件
pytest tests/test_scoring.py -v

# 运行指定测试函数
pytest tests/test_scoring.py::test_calc_total_score -v

# 显示覆盖率
pytest tests/ -v --cov=src --cov-report=term-missing
```

### 6.3 编写测试

测试规范：
- 使用 `monkeypatch` 模拟外部 API 调用，不依赖网络
- 测试函数命名：`test_<功能描述>`
- 每个测试函数只验证一个行为
- 测试数据使用构造的 DataFrame / dict，不使用真实数据

示例：

```python
def test_calc_total_score_full_marks():
    """各维度满分时综合评分 = 100。"""
    from scoring import calc_total_score
    from config import ScoreWeightConfig

    config = ScoreWeightConfig()
    score = calc_total_score(
        technical=55.0,
        fundamental=30.0,
        news=17.5,
        industry=9.0,
        fund_flow=None,
        is_etf=False,
        config=config,
    )
    assert score == 100.0
```

---

## 七、部署

### 7.1 GitHub Actions 自动运行

工作流文件：`.github/workflows/daily_analysis.yml`

```yaml
name: Daily Stock Analysis

on:
  schedule:
    - cron: '0 4 * * 1-5'  # 工作日 UTC 04:00（北京时间 12:00）
  workflow_dispatch:        # 支持手动触发

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python src/main.py
        env:
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
          LLM_API_URL: ${{ secrets.LLM_API_URL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
```

### 7.2 本地定时运行

使用 cron（Linux/Mac）或任务计划程序（Windows）：

```bash
# Linux/Mac cron 示例（每个工作日 12:00 执行）
0 12 * * 1-5 cd /path/to/thousand-times && python src/main.py >> logs/cron.log 2>&1
```

### 7.3 Docker 部署（可选）

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "src/main.py"]
```

---

## 八、性能优化

### 8.1 缓存策略

- **K线数据**：磁盘缓存 24 小时，key 为 `kline_<日期>`
- **基本面数据**：磁盘缓存 24 小时，key 为 `fund_<日期>`
- **缓存目录**：`cache/`，JSON 格式，自动过期清理

### 8.2 并行获取

- 股票池、ETF池、新闻三路并行（ThreadPoolExecutor, max_workers=3）
- K线数据 4 线程并行批量获取
- 基本面数据 4 线程并行批量获取
- 图表生成 4 线程并行

### 8.3 预期运行时间

| 阶段 | 耗时（约） |
|------|-----------|
| 获取股票池 | 30-60s |
| 获取ETF池 | 20-40s |
| 获取新闻 | 10-20s |
| 批量获取K线 | 2-5min |
| 批量获取基本面 | 2-5min |
| 分析个股（200只） | 1-2min |
| 分析ETF（11只） | 10-20s |
| 生成图表 | 30-60s |
| 生成报告+推送 | 5-10s |
| **总计** | **约 8-15min** |

---

## 九、故障排查

### 9.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| BaoStock 登录失败 | 网络问题或服务不可用 | 检查网络连接，系统会自动回退到 Ashare |
| K线数据为空 | 股票代码格式错误 | 检查代码格式（6位数字，如 600519） |
| 推送失败 | Token 无效或过期 | 重新获取 PushPlus Token |
| mypy 报错 | 类型注解不完整 | 运行 `mypy --strict src/` 查看具体错误 |
| pytest 失败 | 依赖缺失 | 运行 `pip install -r requirements.txt` |

### 9.2 日志查看

```bash
# 查看运行日志
cat logs/analysis.log

# 查看最新报告
cat logs/report_$(date +%Y-%m-%d).md

# 实时跟踪日志
tail -f logs/analysis.log
```

### 9.3 调试模式

在 `src/main.py` 中修改日志级别：

```python
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 查看详细日志
    ...
)
```
