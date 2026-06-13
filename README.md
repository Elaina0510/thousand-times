# A股智能选股分析与推送系统

> 自动化A股行情分析系统，每日定时从多个数据源抓取股票和行业ETF行情数据，通过技术指标、基本面数据和政策新闻进行综合评分，筛选出高概率盈利或存在特殊风险的个股和ETF，生成分析报告（含K线+MACD图表+买卖信号），通过 PushPlus 推送到微信。

## 功能特性

- **股票池筛选**：从A股全市场中筛选出符合条件的股票（市值≥20亿、非ST、PE>0、上市≥3个月）
- **ETF分析**：分析主流行业ETF（宽基+细分行业），独立评分
- **技术指标**：计算MA、MACD、成交量等技术指标
- **基本面分析**：获取PE、PB、净利润增长率、营收增长率
- **政策新闻分析**：抓取财经新闻，通过LLM分析政策影响
- **综合评分**：多维度加权评分，个股四维度（技术35%+趋势25%+量价20%+基本面20%），ETF三维度（技术55%+新闻35%+资金流向10%）
- **买卖信号**：基于综合评分生成买入/观望/卖出信号，计算支撑位、压力位、目标价和止损价
- **板块对比**：分析个股在所属板块内的排名和相对ETF的超额收益
- **图表生成**：生成K线+MACD图表（PNG格式）
- **磁盘缓存**：自动缓存K线和基本面数据，避免重复请求，24小时自动过期
- **微信推送**：通过PushPlus推送到微信
- **多数据源支持**：BaoStock + Ashare（新浪/腾讯）+ AKShare（东方财富），支持海外服务器

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.10+ |
| 数据获取 | BaoStock + Ashare（新浪/腾讯双源）+ AKShare |
| 数据处理 | Pandas / NumPy |
| 图表 | mplfinance / Matplotlib |
| 推送 | PushPlus API |
| LLM | DeepSeek API（可选） |
| 测试 | pytest |
| 类型检查 | mypy（strict mode） |
| 代码质量 | ruff |

## 项目结构

```
thousand-times/
├── .github/workflows/
│   ├── daily_analysis.yml      # GitHub Actions 主工作流
│   └── test.yml                # 测试工作流
├── src/
│   ├── __init__.py
│   ├── config.py               # 配置管理（含买卖信号配置）
│   ├── stock_filter.py         # 股票池筛选
│   ├── etf_analyzer.py         # ETF分析
│   ├── technical_analysis.py   # 技术指标计算
│   ├── fundamental_analysis.py # 基本面分析
│   ├── news_analysis.py        # 政策新闻分析
│   ├── scoring.py              # 综合评分（四维度模型）
│   ├── buy_sell_signal.py      # 买卖信号生成
│   ├── sector_analysis.py      # 板块对比分析
│   ├── price_analysis.py       # 关键价位计算
│   ├── chart_generator.py      # 图表生成
│   ├── report_generator.py     # 报告生成（含买卖信号）
│   ├── push_service.py         # 微信推送
│   ├── cache_manager.py        # 磁盘缓存管理
│   ├── baostock_data.py        # BaoStock 数据源
│   ├── ashare.py               # Ashare 核心库（新浪+腾讯双源）
│   ├── ashare_data.py          # Ashare 封装模块
│   ├── remote_data.py          # 远程API数据源（可选）
│   ├── main.py                 # 主程序
│   └── utils.py                # 通用工具
├── tests/
│   ├── test_config.py
│   ├── test_stock_filter.py
│   ├── test_etf_analyzer.py
│   ├── test_technical_analysis.py
│   ├── test_fundamental_analysis.py
│   ├── test_news_analysis.py
│   ├── test_scoring.py
│   ├── test_buy_sell_signal.py
│   ├── test_sector_analysis.py
│   ├── test_price_analysis.py
│   ├── test_chart_generator.py
│   ├── test_report_generator.py
│   ├── test_push_service.py
│   └── test_main.py
├── doc/
│   ├── proposal.md             # 需求文档
│   ├── detailed-design.md      # 详细设计
│   ├── user-guide.md           # 用户使用指南
│   ├── developer-guide.md      # 开发者文档
│   └── tasks/                  # 任务清单
├── cache/                      # 数据缓存（gitignore）
├── charts/                     # 图表输出（gitignore）
├── logs/                       # 日志输出（gitignore）
├── .env.example                # 环境变量示例
├── verify_config.py            # 配置验证脚本
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

复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# PushPlus 推送令牌（必填）
PUSHPLUS_TOKEN=your-pushplus-token-here

# LLM API 配置（可选，用于政策新闻分析）
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_API_KEY=your-api-key-here
```

### 3. 验证配置

```bash
python verify_config.py
```

### 4. 运行分析

```bash
python src/main.py
```

### 5. 运行测试

```bash
pytest tests/ -v
```

### 6. 代码质量检查

```bash
# 类型检查
mypy --strict src/

# 代码质量
ruff check src/
```

## 数据源说明

### 数据源优先级

```
1. BaoStock（证券宝）→ 国内外均可，免费 ✅
2. Ashare（新浪/腾讯双源）→ 海外服务器可用 ✅
3. AKShare（东方财富）→ 国内服务器可用
```

### BaoStock 数据源

- **来源**：[baostock/baostock](https://github.com/baostock/baostock)
- **数据源**：证券宝（baostock.com）
- **优势**：国内外均可访问，数据全面，支持批量获取
- **支持**：日线、周线、月线、分钟线，复权数据

### Ashare 数据源

- **来源**：[mpquant/Ashare](https://github.com/mpquant/Ashare)
- **数据源**：新浪财经 + 腾讯财经（双源自动切换）
- **优势**：海外服务器可用，无需 API Key，完全免费
- **支持**：日线、周线、月线、分钟线（1m/5m/15m/30m/60m）

### 海外服务器使用

如果在海外服务器（如 GitHub Actions）运行，系统会自动使用 BaoStock / Ashare 获取数据：

```python
# 自动切换数据源
优先使用 BaoStock（国内外均可）
  ↓ 失败
回退到 Ashare（海外可用）
  ↓ 失败
回退到 AKShare（国内可用）
```

## 评分体系

### 个股评分（满分100分）

| 维度 | 权重 | 满分 |
|------|------|------|
| 技术指标 | 35% | 35分 |
| 趋势判断 | 25% | 25分 |
| 量价配合 | 20% | 20分 |
| 基本面 | 20% | 20分 |

### ETF评分（满分100分）

| 维度 | 权重 | 满分 |
|------|------|------|
| 技术指标 | 55% | 55分 |
| 政策新闻 | 35% | 35分 |
| 资金流向 | 10% | 10分 |

### 买卖信号

| 综合评分 | 信号区间 | 图标 |
|----------|----------|------|
| ≥ 75 分 | 买入区 | 🟢 |
| 45 ~ 74 分 | 观望区 | 🟡 |
| < 45 分 | 卖出区 | 🔴 |

每只推送的股票/ETF均附带：
- **支撑位**：MA20 与近期低点的加权平均
- **压力位**：MA20 与近期高点的加权平均
- **目标价**：突破压力位后 5%
- **止损价**：支撑位下方 5%

### 推送判定

| 综合评分 | 判定 | 推送行为 |
|----------|------|----------|
| ≥ 75 分 | 高概率盈利 | 推送，标注"建议关注" |
| 50 ~ 74 分 | 观望 | 不推送 |
| 45 ~ 49 分 | 偏空 | 不推送 |
| < 45 分 | 特殊风险 | 推送，标注"风险警示" |

## GitHub Actions 配置

### 1. 配置 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret 名称 | 说明 | 必填 |
|-------------|------|------|
| `PUSHPLUS_TOKEN` | PushPlus 推送令牌 | ✅ |
| `LLM_API_URL` | LLM API 地址（如 DeepSeek） | 可选 |
| `LLM_API_KEY` | LLM API 密钥 | 可选 |

### 2. 工作流配置

- **定时调度**：工作日北京时间 12:00（UTC 04:00）
- **手动触发**：支持在 GitHub Actions 页面手动运行
- **CI 环境**：自动检测并启用容错模式

### 3. 运行状态

- ✅ 海外服务器可正常运行（使用 BaoStock / Ashare 数据源）
- ✅ 国内服务器可正常运行（使用 AKShare 数据源）
- ✅ 无数据源时生成空报告（优雅降级）

## 开发规则

- **类型注解**：所有函数参数和返回值必须有类型注解
- **docstring**：所有公共函数和类必须有 Google 风格 docstring
- **测试覆盖**：每个模块必须有对应的测试文件
- **代码质量**：通过 mypy --strict 和 ruff check
- **缓存策略**：K线和基本面数据使用磁盘缓存，24小时自动过期

## 更新日志

### 2026-06-13 (Step 4 性能优化)
- ✅ 新增买卖信号模块（buy_sell_signal.py），生成买入/观望/卖出信号
- ✅ 新增板块对比分析模块（sector_analysis.py），分析板块内排名
- ✅ 新增关键价位计算模块（price_analysis.py），计算支撑/压力位
- ✅ 新增磁盘缓存管理模块（cache_manager.py），避免重复请求
- ✅ 集成 BaoStock 数据源，支持批量获取K线数据
- ✅ 并行获取股票池、ETF池、新闻，大幅缩短运行时间
- ✅ 个股评分升级为四维度模型（技术+趋势+量价+基本面）
- ✅ 报告中增加买卖信号、关键价位、板块对比信息

### 2026-06-07
- ✅ 集成 Ashare 数据源（新浪/腾讯双源），支持海外服务器
- ✅ 添加 .env 文件支持（python-dotenv）
- ✅ 添加配置验证脚本（verify_config.py）
- ✅ 优化 GitHub Actions 配置（Node.js 24 兼容）
- ✅ 添加 CI 环境容错处理
- ✅ 添加远程 API 数据源支持（可选）

### 2026-06-06
- ✅ 完成所有模块开发（12个模块）
- ✅ 119个单元测试全部通过
- ✅ 配置 GitHub Actions 自动执行

## 免责声明

⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。

## 相关链接

- [BaoStock](http://baostock.com) - 证券宝数据接口
- [Ashare 数据源](https://github.com/mpquant/Ashare) - 新浪/腾讯双源 A 股数据
- [AKShare](https://github.com/akfamily/akshare) - 东方财富数据接口
- [PushPlus](https://www.pushplus.plus/) - 微信推送服务
- [DeepSeek](https://platform.deepseek.com/) - LLM API 服务

## 许可证

本项目仅供学习研究使用，请遵守相关法律法规。
