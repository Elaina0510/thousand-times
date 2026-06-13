# CLAUDE.md — AI 开发助手上下文

> 本文件为 AI 开发助手（Claude Code 等）提供项目上下文和开发规范。

## 项目概述

A股智能选股分析与推送系统。自动化分析A股行情，通过技术指标、基本面和政策新闻综合评分，筛选推荐/风险标的，生成报告推送到微信。

## 技术栈

- **语言**：Python 3.10+
- **数据源**：BaoStock（主） + Ashare（备） + AKShare（备）
- **依赖管理**：pip + requirements.txt
- **测试**：pytest
- **类型检查**：mypy --strict
- **代码质量**：ruff

## 目录结构

- `src/` — 源代码（21个模块）
- `tests/` — 测试文件（15个，与 src 一一对应）
- `doc/` — 文档（需求、设计、用户指南、开发者文档）
- `cache/` — 数据缓存（gitignore，24小时过期）
- `charts/` — 图表输出（gitignore）
- `logs/` — 日志输出（gitignore）

## 开发规范

### 代码风格

- 所有函数参数和返回值**必须**有类型注解
- 所有公共函数和类**必须**有 Google 风格 docstring
- 使用 `from __future__ import annotations` 延迟注解求值
- 日志使用 `logging.getLogger("thousand-times")`

### 测试规范

- 每个模块必须有对应的 `tests/test_<module>.py`
- 测试函数命名：`test_<功能描述>`
- 使用 `pytest` 的 `monkeypatch` 模拟外部 API 调用
- 不依赖网络连接，所有外部数据通过 mock 提交

### 提交规范

- 使用 Conventional Commits 格式：`<type>: <description>`
- 常用 type：`feat`、`fix`、`perf`、`test`、`docs`、`refactor`
- 示例：`perf: 优化运行时长，预计从60分钟降至15-20分钟`

### 运行命令

```bash
# 运行分析
python src/main.py

# 运行全部测试
pytest tests/ -v

# 类型检查
mypy --strict src/

# 代码质量检查
ruff check src/

# 验证配置
python verify_config.py
```

## 模块依赖关系

```
main.py（主入口，编排流水线）
├── config.py（无外部依赖）
├── stock_filter.py → BaoStock / AKShare
├── etf_analyzer.py → BaoStock / AKShare
├── technical_analysis.py → BaoStock, Pandas, NumPy
├── fundamental_analysis.py → BaoStock / AKShare
├── news_analysis.py → AKShare, LLM API
├── scoring.py（无外部依赖）
├── buy_sell_signal.py（依赖 technical_analysis, config）
├── sector_analysis.py（依赖 scoring, buy_sell_signal）
├── price_analysis.py（依赖 technical_analysis, buy_sell_signal, config）
├── chart_generator.py → mplfinance, Matplotlib
├── report_generator.py（依赖 scoring, buy_sell_signal, news_analysis）
├── push_service.py → Requests
└── cache_manager.py（JSON 文件 I/O）
```

## 关键设计决策

1. **多数据源容错**：BaoStock → Ashare → AKShare，逐级回退
2. **并行获取**：股票池、ETF池、新闻三路并行；K线和基本面数据使用线程池批量获取
3. **磁盘缓存**：K线和基本面数据缓存24小时，避免同日重复请求
4. **异常隔离**：单只股票/ETF分析失败不影响整体流程
5. **CI 容错**：检测 CI 环境变量，数据获取失败时生成空报告而非崩溃

## 配置说明

- 敏感信息通过环境变量（`.env` 或 GitHub Secrets）注入
- 评分权重、阈值等在 `config.py` 的 dataclass 中定义，可直接修改默认值
- ETF 池在 `config.py` 的 `DEFAULT_ETF_POOL` 中配置

## 注意事项

- BaoStock 需要先调用 `bs.login()` 才能获取数据，用完后调用 `bs.logout()`
- Ashare 使用新浪/腾讯双源，无需登录
- LLM 政策分析是可选功能，不配置 API Key 时使用默认中性评分
- 图表使用深色背景，中文标签，需确保系统安装了中文字体
