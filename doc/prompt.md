# VibeCoding Prompt — A股智能选股分析与推送系统

> 自动生成于 2026-06-06  
> 用途：作为 VibeCoding 起始 Prompt，驱动主 Agent 自动完成全部模块开发

---

## 项目概述

构建一套自动化的A股行情分析系统。每日定时从 AKShare 抓取股票和行业ETF行情数据，通过技术指标、基本面数据和政策新闻进行综合评分，筛选出高概率盈利或存在特殊风险的个股和ETF，生成分析报告（含K线+MACD图表），通过 PushPlus 推送到微信。

**核心原则**：宁缺毋滥（只推≥70分或<30分）、数据可信、风险提示。

---

## 参考文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 需求文档 | `doc/proposal.md` | 功能需求、评分规则、推送格式 |
| 详细设计 | `doc/detailed-design.md` | 模块接口、数据结构、计算公式 |
| 任务清单 | `doc/tasks/*.md` | 每个模块的最小可执行任务列表 |
| 进度跟踪 | `doc/tasks/progress.md` | 模块完成状态（需持续更新） |

**开发前必须先阅读以上文档，理解完整的业务逻辑和接口定义。**

---

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.10+ |
| 数据获取 | AKShare |
| 数据处理 | Pandas / NumPy |
| 图表 | mplfinance / Matplotlib |
| 推送 | PushPlus API（requests） |
| 测试 | pytest |
| 类型检查 | mypy（strict mode） |
| 代码质量 | ruff |

---

## 项目结构

```
thousand-times/
├── .github/
│   └── workflows/
│       └── daily_analysis.yml      # GitHub Actions
├── src/
│   ├── __init__.py
│   ├── config.py                   # 配置管理
│   ├── stock_filter.py             # 股票池筛选
│   ├── etf_analyzer.py             # ETF分析
│   ├── technical_analysis.py       # 技术指标计算
│   ├── fundamental_analysis.py     # 基本面分析
│   ├── news_analysis.py            # 政策新闻分析
│   ├── scoring.py                  # 综合评分
│   ├── chart_generator.py          # 图表生成
│   ├── report_generator.py         # 报告生成
│   ├── push_service.py             # 微信推送
│   └── main.py                     # 主程序
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_stock_filter.py
│   ├── test_etf_analyzer.py
│   ├── test_technical_analysis.py
│   ├── test_fundamental_analysis.py
│   ├── test_news_analysis.py
│   ├── test_scoring.py
│   ├── test_chart_generator.py
│   ├── test_report_generator.py
│   ├── test_push_service.py
│   └── test_main.py
├── charts/                         # 图表输出（gitignore）
├── logs/                           # 日志输出（gitignore）
├── requirements.txt
├── pyproject.toml                  # ruff + mypy 配置
├── .gitignore
└── README.md
```

---

## 开发规则

### 1. 代码规范

- **类型注解**：所有函数参数和返回值必须有类型注解
- **docstring**：所有公共函数和类必须有 Google 风格 docstring
- **命名**：snake_case（函数/变量）、PascalCase（类）、UPPER_CASE（常量）
- **导入顺序**：标准库 → 第三方库 → 本地模块（ruff 自动排序）
- **类型检查**：所有代码必须通过 `mypy --strict`
- **代码质量**：所有代码必须通过 `ruff check`

### 2. 测试规范

- **覆盖率**：每个模块必须有对应的 `tests/test_*.py`
- **测试框架**：pytest
- **外部依赖隔离**：所有 AKShare、requests、LLM API 调用必须 mock
- **测试场景**：
  - 正常输入 → 正确输出
  - 边界值 → 不崩溃
  - 异常输入 → 降级处理或抛出预期异常
  - 外部API失败 → 重试后优雅降级
- **测试数据**：构造确定性的测试数据，不依赖真实 API 返回
- **必须全部通过**：`pytest tests/` 零失败

### 3. 模块开发顺序

按依赖关系从底层到顶层，每个模块开发完成后必须：
1. 代码通过 mypy --strict
2. 代码通过 ruff check
3. 测试全部通过
4. 更新 `doc/tasks/progress.md` 中的完成状态

```
阶段1：基础层（无外部API依赖，纯逻辑）
  ① infra（项目初始化、requirements.txt、pyproject.toml、.gitignore）
  ② config.py
  ③ scoring.py
  ④ report_generator.py

阶段2：数据层（依赖 AKShare，需 mock 测试）
  ⑤ stock_filter.py
  ⑥ technical_analysis.py
  ⑦ fundamental_analysis.py

阶段3：分析层（依赖 AKShare + LLM API，需 mock 测试）
  ⑧ etf_analyzer.py
  ⑨ news_analysis.py

阶段4：输出层
  ⑩ chart_generator.py
  ⑪ push_service.py

阶段5：集成
  ⑫ main.py
  ⑬ GitHub Actions 配置
```

### 4. 子 Agent 职责

每个子 Agent 负责一个模块，必须：
1. 阅读 `doc/detailed-design.md` 中对应模块的设计文档
2. 阅读 `doc/tasks/` 中对应模块的任务清单
3. 实现模块代码（`src/*.py`）
4. 编写完整单元测试（`tests/test_*.py`）
5. 确保 `mypy --strict` 通过
6. 确保 `ruff check` 通过
7. 确保 `pytest tests/test_*.py` 全部通过
8. 向主 Agent 报告完成状态

### 5. 主 Agent 职责

主 Agent 负责：
1. **阅读理解**：首先完整阅读 `doc/proposal.md`、`doc/detailed-design.md`、`doc/tasks/*.md`
2. **环境初始化**：创建项目目录结构、`requirements.txt`、`pyproject.toml`、`.gitignore`
3. **任务调度**：按开发顺序生成子 Agent，每个子 Agent 对应一个模块
4. **进度跟踪**：每个子 Agent 完成后更新 `doc/tasks/progress.md`
5. **质量把关**：每个子 Agent 完成后验证 mypy/ruff/pytest 结果
6. **集成验证**：所有模块完成后，运行全量测试确认无冲突
7. **异常处理**：子 Agent 失败时记录错误，尝试修复或跳过

---

## 环境初始化指令

在生成第一个子 Agent 之前，主 Agent 必须先完成：

```bash
# 1. 创建目录
mkdir -p src tests charts logs .github/workflows

# 2. 创建 requirements.txt
cat > requirements.txt << 'EOF'
akshare>=1.10.0
pandas>=2.0.0
numpy>=1.24.0
mplfinance>=0.12.10
matplotlib>=3.7.0
requests>=2.31.0
beautifulsoup4>=4.12.0
EOF

# 3. 创建 pyproject.toml
cat > pyproject.toml << 'EOF'
[tool.ruff]
target-version = "py310"
line-length = 120
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
EOF

# 4. 创建 .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
charts/
logs/
*.egg-info/
dist/
build/
.env
EOF

# 5. 创建 src/__init__.py 和 tests/__init__.py
touch src/__init__.py tests/__init__.py

# 6. 安装依赖：pip install -r requirements.txt
# 7. 安装开发依赖：pip install pytest mypy ruff types-requests
```

---

## 子 Agent Prompt 模板

每个子 Agent 的 Prompt 应包含以下内容（主 Agent 根据实际模块填充）：

```
你是 [模块名] 的开发者。

## 你的任务
根据以下文档实现 [src/模块名.py] 及其完整单元测试 [tests/test_模块名.py]。

## 参考文档
- 详细设计：阅读 doc/detailed-design.md 中 "[模块名]" 章节
- 任务清单：阅读 doc/tasks/[模块名].md

## 实现要求
1. 所有函数参数和返回值必须有类型注解
2. 所有公共函数和类必须有 docstring
3. 外部 API 调用（AKShare、requests、LLM）必须通过 mock 隔离
4. 测试必须覆盖：正常输入、边界值、异常输入、API失败

## 质量门禁
完成以下全部检查后才能报告完成：
```bash
mypy --strict src/[模块名].py
ruff check src/[模块名].py
pytest tests/test_[模块名].py -v
```

## 完成标准
- 代码实现完整，覆盖设计文档中的所有接口
- 测试全部通过，覆盖所有关键场景
- mypy --strict 零错误
- ruff check 零警告
```

---

## 依赖模块接口速查

子 Agent 实现时可能需要引用其他模块的接口，以下是关键接口速查：

### config.py
```python
@dataclass
class AppConfig:
    filter: FilterConfig
    score_weight: ScoreWeightConfig
    technical_weight: TechnicalWeightConfig
    fundamental_weight: FundamentalWeightConfig
    news_weight: NewsWeightConfig
    industry_trend_weight: IndustryTrendWeightConfig
    etf_fund_flow_weight: EtfFundFlowWeightConfig
    etf_pool: list[str]
    score_threshold_high: float = 70.0
    score_threshold_low: float = 30.0
    request_delay_range: tuple[float, float] = (1.0, 5.0)
    max_retries: int = 3
    lookback_days: int = 60
    llm_api_url: str = ""
    llm_api_key: str = ""

def load_config() -> AppConfig: ...
```

### technical_analysis.py
```python
@dataclass
class TechnicalSignals:
    ma5_10_golden: bool
    ma5_10_death: bool
    ma20_60_golden: bool
    bullish_alignment: bool
    above_ma20: bool
    macd_golden: bool
    macd_death: bool
    macd_above_zero: bool
    macd_divergence: bool
    volume_up: bool
    volume_down: bool
    volume_peak: bool
    pullback_ok: bool

@dataclass
class KlineData:
    dates: list[str]
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

def get_kline_data(code: str, days: int = 60, is_etf: bool = False) -> KlineData: ...
def calc_technical_signals(kline: KlineData) -> TechnicalSignals: ...
def calc_technical_score(signals: TechnicalSignals, weights: TechnicalWeightConfig) -> float: ...
```

### scoring.py
```python
@dataclass
class ScoreResult:
    code: str
    name: str
    is_etf: bool
    technical_score: float
    fundamental_score: float | None
    news_score: float
    industry_score: float | None
    fund_flow_score: float | None
    total_score: float
    profit_probability: float
    judgment: str
    technical_signals: TechnicalSignals
    news_summary: str

def calc_total_score(technical, fundamental, news, industry, fund_flow, is_etf, config) -> float: ...
def score_to_probability(score: float) -> float: ...
def judge_score(score, high_threshold, low_threshold) -> str: ...
def get_industry_trend_score(industry, etf_pool, config) -> float: ...
```

### fundamental_analysis.py
```python
@dataclass
class FundamentalData:
    pe_ttm: float
    pb: float
    market_cap: float
    profit_growth: float | None
    revenue_growth: float | None

def get_fundamental_data(code: str) -> FundamentalData: ...
def calc_fundamental_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float: ...
```

### etf_analyzer.py
```python
@dataclass
class EtfInfo:
    code: str
    name: str
    current_price: float
    change_pct: float

def get_etf_pool(config: AppConfig) -> list[EtfInfo]: ...
def get_etf_fund_flow(code: str, days: int = 5) -> float: ...
def calc_fund_flow_score(share_changes: list[float]) -> float: ...
```

### news_analysis.py
```python
@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    publish_time: datetime
    content: str

@dataclass
class PolicyImpact:
    news_title: str
    affected_industries: list[str]
    impact_direction: str
    impact_degree: str
    impact_score: float
    summary: str

def fetch_news() -> list[NewsItem]: ...
def filter_by_credibility(news: list[NewsItem]) -> list[NewsItem]: ...
def analyze_policy_impact(news: list[NewsItem], llm_config: dict) -> list[PolicyImpact]: ...
def get_industry_impact_score(industry: str, impacts: list[PolicyImpact]) -> float: ...
```

### chart_generator.py
```python
def generate_chart(code: str, name: str, kline: KlineData, save_path: str) -> str: ...
```

### report_generator.py
```python
def generate_report(
    stock_results: list[ScoreResult],
    etf_results: list[ScoreResult],
    policy_impacts: list[PolicyImpact],
    report_date: str
) -> str: ...
```

### 通用工具（可放在 src/utils.py 或各模块内部）

```python
import functools
import time
import random
import logging

def retry(max_attempts: int = 3, backoff_factor: float = 2.0):
    """通用重试装饰器，支持指数退避。

    Args:
        max_attempts: 最大重试次数。
        backoff_factor: 退避因子，等待时间 = backoff_factor ** attempt。
    """
    def decorator(func): ...
    return decorator

def random_delay(min_sec: float = 1.0, max_sec: float = 5.0) -> None:
    """随机延迟，避免触发API频率限制。"""
    ...

logger = logging.getLogger("thousand-times")
```

### push_service.py
```python
def push_to_wechat(title: str, content: str, token: str, template: str = "markdown") -> bool: ...
```

### main.py
```python
def main() -> None: ...
def analyze_single_stock(
    stock: pd.Series, policy_impacts: list[PolicyImpact], config: AppConfig
) -> ScoreResult: ...
def analyze_single_etf(
    etf: EtfInfo, policy_impacts: list[PolicyImpact], config: AppConfig
) -> ScoreResult: ...
```

---

## 关键业务规则速查

### 股票池筛选
- 市值 ≥ 20亿
- 名称不含 "ST"
- PE-TTM > 0
- 上市 ≥ 3个月
- 取市值前 1000

### 综合评分权重
- **个股**：技术40% + 基本面30% + 政策20% + 行业10%
- **ETF**：技术55% + 政策35% + 资金流向10%

### 推送判定
- ≥ 70 分 → "建议关注"
- < 30 分 → "风险警示"
- 其他 → 不推送

### 盈利概率转换
- sigmoid 函数：`P = 1 / (1 + e^(-0.1*(x-50)))`
- 归一化到 0~100%

---

## 执行指令

**主 Agent 请按以下步骤执行：**

1. 完整阅读 `doc/proposal.md`、`doc/detailed-design.md`、`doc/tasks/*.md`
2. 执行环境初始化（创建目录、配置文件、安装依赖）
3. 按开发顺序生成子 Agent，每个子 Agent 完成一个模块
4. 每个子 Agent 完成后：
   - 验证 mypy --strict 通过
   - 验证 ruff check 通过
   - 验证 pytest 通过
   - 更新 `doc/tasks/progress.md`
5. 所有模块完成后，运行全量测试：`pytest tests/ -v`
6. 最终报告：列出所有模块的完成状态和测试结果

**注意：整个过程不需要人工干预。如果某个子 Agent 失败，记录错误并继续下一个模块。**
