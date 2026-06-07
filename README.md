# A股智能选股分析与推送系统

> 自动化A股行情分析系统，每日定时从 AKShare 抓取股票和行业ETF行情数据，通过技术指标、基本面数据和政策新闻进行综合评分，筛选出高概率盈利或存在特殊风险的个股和ETF，生成分析报告（含K线+MACD图表），通过 PushPlus 推送到微信。

## 功能特性

- **股票池筛选**：从A股全市场中筛选出符合条件的股票（市值≥20亿、非ST、PE>0、上市≥3个月）
- **ETF分析**：分析主流行业ETF（宽基+细分行业），独立评分
- **技术指标**：计算MA、MACD、成交量等技术指标
- **基本面分析**：获取PE、PB、净利润增长率、营收增长率
- **政策新闻分析**：抓取财经新闻，通过LLM分析政策影响
- **综合评分**：多维度加权评分，筛选≥70分（建议关注）或<30分（风险警示）
- **图表生成**：生成K线+MACD图表（PNG格式）
- **微信推送**：通过PushPlus推送到微信

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.10+ |
| 数据获取 | AKShare |
| 数据处理 | Pandas / NumPy |
| 图表 | mplfinance / Matplotlib |
| 推送 | PushPlus API |
| 测试 | pytest |
| 类型检查 | mypy（strict mode） |
| 代码质量 | ruff |

## 项目结构

```
thousand-times/
├── .github/workflows/
│   └── daily_analysis.yml      # GitHub Actions 配置
├── src/
│   ├── __init__.py
│   ├── config.py               # 配置管理
│   ├── stock_filter.py         # 股票池筛选
│   ├── etf_analyzer.py         # ETF分析
│   ├── technical_analysis.py   # 技术指标计算
│   ├── fundamental_analysis.py # 基本面分析
│   ├── news_analysis.py        # 政策新闻分析
│   ├── scoring.py              # 综合评分
│   ├── chart_generator.py      # 图表生成
│   ├── report_generator.py     # 报告生成
│   ├── push_service.py         # 微信推送
│   ├── main.py                 # 主程序
│   └── utils.py                # 通用工具
├── tests/
│   └── test_*.py               # 单元测试
├── doc/
│   ├── proposal.md             # 需求文档
│   ├── detailed-design.md      # 详细设计
│   └── tasks/                  # 任务清单
├── charts/                     # 图表输出（gitignore）
├── logs/                       # 日志输出（gitignore）
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# PushPlus 推送令牌（必填）
export PUSHPLUS_TOKEN="your-token"

# LLM API 配置（可选，用于政策新闻分析）
export LLM_API_URL="https://api.example.com/v1/chat/completions"
export LLM_API_KEY="your-api-key"
```

### 3. 运行分析

```bash
python src/main.py
```

### 4. 运行测试

```bash
pytest tests/ -v
```

### 5. 代码质量检查

```bash
# 类型检查
mypy --strict src/

# 代码质量
ruff check src/
```

## 评分体系

### 个股评分（满分100分）

| 维度 | 权重 | 满分 |
|------|------|------|
| 技术指标 | 40% | 40分 |
| 基本面 | 30% | 30分 |
| 政策新闻 | 20% | 20分 |
| 行业趋势 | 10% | 10分 |

### ETF评分（满分100分）

| 维度 | 权重 | 满分 |
|------|------|------|
| 技术指标 | 55% | 55分 |
| 政策新闻 | 35% | 35分 |
| 资金流向 | 10% | 10分 |

### 推送判定

| 综合评分 | 判定 | 推送行为 |
|----------|------|----------|
| ≥ 70 分 | 高概率盈利 | 推送，标注"建议关注" |
| 50 ~ 69 分 | 观望 | 不推送 |
| 30 ~ 49 分 | 偏空 | 不推送 |
| < 30 分 | 特殊风险 | 推送，标注"风险警示" |

## GitHub Actions 配置

项目支持通过 GitHub Actions 每日自动执行：

1. 在 GitHub 仓库设置中添加 Secrets：
   - `PUSHPLUS_TOKEN`：PushPlus 推送令牌
   - `LLM_API_URL`：LLM API 地址（可选）
   - `LLM_API_KEY`：LLM API 密钥（可选）

2. 工作流配置：
   - 定时调度：工作日北京时间 12:00（UTC 04:00）
   - 支持手动触发

## 开发规则

- **类型注解**：所有函数参数和返回值必须有类型注解
- **docstring**：所有公共函数和类必须有 Google 风格 docstring
- **测试覆盖**：每个模块必须有对应的测试文件
- **代码质量**：通过 mypy --strict 和 ruff check

## 免责声明

⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
