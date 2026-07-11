# A股智能选股分析与推送系统 V3

> 自动化A股行情分析系统，五层架构流水线。每日从多数据源抓取行情，通过**数据质量校验 → 因子评分校准 → 自适应信号生成 → 风控执行 → 反馈验证**全流程，筛选推荐/风险标的，生成报告推送到微信。

## 系统架构

```
统一管道入口: pipeline/unified.py
│
├── Layer 1: 数据质量层
│   ├── data_quality/validator.py   — DataValidator (数据完整性校验)
│   └── data_quality/unifier.py    — DataSourceUnifier (多数据源值域统一)
│
├── Layer 2: 因子评分层
│   ├── factors/calibrator.py      — FactorCalibrator (百分位评分校准)
│   └── factors/industry_rotation.py — IndustryRotationAnalyzer (行业轮动)
│
├── Layer 3: 信号生成层
│   ├── pipeline/signal.py (改造)  — AdaptiveVoter (自适应投票阈值)
│   └── pipeline/unified.py        — UnifiedPipeline (统一管道入口)
│
├── Layer 4: 风控执行层
│   ├── risk/position.py           — PositionSizer (仓位计算)
│   ├── risk/stop_loss.py          — StopLossTracker (止损跟踪)
│   └── risk/guard.py              — RiskGuard (硬性风控规则)
│
└── Layer 5: 反馈验证层
    ├── feedback/tracker.py         — SignalTracker (信号→收益闭环)
    ├── feedback/backtest_validator.py — BacktestValidator (回测与检验)
    └── feedback/paper_trader.py    — PaperTrader (纸交易模拟)
```

### 数据流

```
AKShare/BaoStock API
  → pipeline/collect.py → DataBundle
  → data_quality/validator.py → DataQualityReport
  → data_quality/unifier.py → NormalizedFundamental[]
  → pipeline/regime.py → MarketRegime
  → pipeline/factors.py → FactorScores[] (raw)
  → factors/calibrator.py → CalibratedScores[] (区分度↑)
  → factors/industry_rotation.py → IndustryScoreAdjustment[]
  → pipeline/signal.py (AdaptiveVoter) → Signal[]
  → risk/guard.py → Signal[] (过滤后)
  → risk/position.py → PositionAllocation[]
  → risk/stop_loss.py → StopLossRecord[]
  → feedback/tracker.py → 数据库
  → pipeline/output.py → 报告 → push_service → 微信
```

## 功能特性

- **数据质量校验**：10条校验规则，自动检测默认值填充、K线不足、空数据等，输出质量等级报告
- **多数据源值域统一**：AKShare/BaoStock 双源 ROE/EPS/增长率自动统一为相同尺度，冲突检测
- **百分位评分校准**：百分位排名+Z-score分布拉伸，解决评分压缩问题（σ: ~8 → ≥15）
- **自适应投票信号**：市场环境自适应阈值（牛/熊/震荡），解决"全部观望"问题
- **行业轮动分析**：31个申万一级行业动量计算，识别轮动模式，生成评分调整
- **硬性风控规则**：8条风控规则（ST过滤、涨跌停、流动性、仙股、行业超配等）
- **仓位计算**：Kelly启发式+波动率调整，市场环境自适应仓位限制
- **止损跟踪**：追踪止损（盈利>10%保本，>20%锁定10%，>30%锁定20%），接近预警
- **信号反馈闭环**：信号→收益追踪，自动推荐最优阈值
- **回测验证**：t检验+蒙特卡洛模拟，6项通过标准
- **纸交易模拟**：60天观察期，5项go-live条件
- **多数据源容错**：BaoStock → AKShare 双源回退
- **并行处理**：股票池、ETF池、新闻三路并行；K线和基本面数据线程池批量获取
- **图表生成**：K线+MACD图表（PNG格式，深色背景中文标签）
- **HTML报告**：图表内嵌base64，可离线浏览
- **微信推送**：通过 PushPlus 推送到微信
- **磁盘缓存**：K线和基本面数据24小时过期

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.10+ |
| 数据获取 | BaoStock + AKShare（东方财富） |
| 数据处理 | Pandas / NumPy |
| 图表 | mplfinance / Matplotlib |
| LLM | DeepSeek API（可选） |
| 推送 | PushPlus API |
| 测试 | pytest |
| 类型检查 | mypy（strict mode） |
| 代码质量 | ruff |

## 项目结构

```
thousand-times/
├── .github/workflows/
│   ├── daily_analysis.yml         # GitHub Actions 定时调度
│   └── test.yml                   # 测试工作流
├── src/
│   ├── config.py                  # 配置管理（权重、阈值、ETF池）
│   ├── main.py                    # 主入口（已废弃，转发到 V3 管道）
│   │
│   ├── pipeline/                  # V3 统一管道
│   │   ├── unified.py             # UnifiedPipeline（唯一入口）
│   │   ├── collect.py             # 数据采集阶段
│   │   ├── regime.py              # 市场环境判断
│   │   ├── factors.py             # 多因子引擎
│   │   ├── signal.py              # 信号生成（AdaptiveVoter）
│   │   └── output.py              # 报告输出
│   │
│   ├── data_quality/              # Layer 1: 数据质量
│   │   ├── validator.py           # 数据完整性校验
│   │   └── unifier.py             # 多数据源值域统一
│   │
│   ├── factors/                   # Layer 2: 因子评分（V3新增）
│   │   ├── technical.py           # 技术因子
│   │   ├── fundamental.py         # 基本面因子
│   │   ├── momentum.py            # 动量因子
│   │   ├── capital.py             # 资金因子
│   │   ├── sentiment.py           # 情绪因子
│   │   ├── calibrator.py          # 百分位评分校准 (NEW)
│   │   └── industry_rotation.py   # 行业轮动分析 (NEW)
│   │
│   ├── risk/                      # Layer 4: 风控执行 (NEW)
│   │   ├── guard.py               # 硬性风控规则引擎
│   │   ├── position.py            # 仓位计算与组合优化
│   │   └── stop_loss.py           # 止损跟踪与移动止损
│   │
│   ├── feedback/                  # Layer 5: 反馈验证 (NEW)
│   │   ├── tracker.py             # 信号→收益闭环追踪
│   │   ├── backtest_validator.py  # 回测验证（t检验+蒙特卡洛）
│   │   └── paper_trader.py        # 纸交易模拟
│   │
│   ├── data_sources/              # 数据源
│   │   ├── sentiment.py           # 涨跌停统计
│   │   ├── macro.py               # 宏观经济指标
│   │   ├── capital_flow.py        # 北向资金
│   │   └── sector_flow.py         # 行业资金流向
│   │
│   ├── stock_filter.py            # 股票池筛选
│   ├── etf_analyzer.py            # ETF分析
│   ├── fundamental_analysis.py    # 基本面数据获取
│   ├── technical_analysis.py      # 技术指标（V1，保留兼容）
│   ├── baostock_data.py           # BaoStock 封装
│   ├── news_analysis.py           # 政策新闻分析（LLM）
│   ├── chart_generator.py         # K线+MACD图表
│   ├── report_generator.py        # 文本报告
│   ├── html_report.py             # HTML报告
│   ├── push_service.py            # 微信推送（PushPlus）
│   ├── cache_manager.py           # 磁盘缓存管理
│   └── utils.py                   # 通用工具
│
├── tests/                         # 单元测试（与 src 一一对应）
├── doc/                           # 文档（需求/设计/用户指南）
├── cache/                         # 数据缓存（gitignore）
├── charts/                        # 图表输出（gitignore）
├── logs/                          # 日志输出（gitignore）
├── requirements.txt
├── pyproject.toml
└── README.md
```

## V3 量化策略

### 1. 数据质量层 — 校验 & 统一

**DataValidator** 对 DataBundle 执行 10 条校验规则：

| 数据集 | 校验项 | 条件 | 等级 |
|--------|--------|------|:----:|
| K线 | 最少行数 | < 20行 | BAD |
| K线 | 空数据比例 | > 30% | DEGRADED |
| K线 | 列完整性 | 缺少收盘列 | BAD |
| 基本面 | ROE默认值 | roe==0 比例 > 50% | BAD |
| 基本面 | EPS默认值 | eps==0 比例 > 50% | BAD |
| 资金面 | 空DataFrame | north_flow为空 | DEGRADED |
| 情绪面 | 涨跌停比为0 | limit_up==0且limit_down==0 | DEGRADED |

**DataSourceUnifier** 统一 AKShare/BaoStock 双源值域：

| 指标 | BaoStock原始 | AKShare原始 | 统一后 | 转换 |
|------|-------------|-------------|--------|------|
| ROE | 小数 (0.15) | 百分数 (3.2) | 百分数 (15.0) | BS×100, AK直用 |
| EPS | 元/股 | 元/股 | 元/股 | 直用 |
| 增长率 | 小数 (0.25) | 百分数 (25) | 百分数 (25) | BS×100, AK直用 |

优先级: AKShare > BaoStock > 空数据。差异 > 30% 时记录冲突。

### 2. 因子评分层 — 校准 & 行业轮动

**FactorCalibrator** 解决评分压缩（32.5~70.3, σ≈8）：

```
1. 计算每只股票每个因子的百分位排名
2. 百分位与原始分混合: final = raw×(1-w) + pct×w  (w=0.5)
3. Z-score 拉伸: target_mean=50, target_std=20
4. 截断到 [0, 100]
效果: σ ≥ 15, 范围 ~5~95
```

**IndustryRotationAnalyzer** 识别 6 种轮动模式：

- `growth_rotation` — 成长板块领涨
- `defensive_rotation` — 防御板块受青睐
- `cyclical_rotation` — 周期板块走强
- `broad_up` — 普涨行情
- `broad_down` — 普跌行情
- `no_pattern` — 无明显模式

行业排名前10%: +5~+10分；前10-30%: +2~+5分；后30%: 0~-5分。

### 3. 信号生成层 — 自适应投票

**AdaptiveVoter** 根据市场环境动态调整阈值：

| 参数 | 牛市 | 震荡 | 熊市 |
|------|:----:|:----:|:----:|
| 买入最低票数 | 2 | 2 | 4 |
| 卖出最低票数 | 4 | 2 | 2 |
| 因子买入阈值 | 65 | 70 | 80 |
| 最低盈亏比 | 1.5 | 2.0 | 2.5 |

5票投票制：因子综合 + 技术面 + 资金面 + 动量 + 市场环境。

### 4. 风控执行层

**RiskGuard** — 8条硬性风控规则（按优先级）：
1. ST/*ST 过滤（block）
2. 涨跌停检查 ≥ ±9.9%（block）
3. 流动性过滤 < 1000万日均（block）
4. 仙股过滤 < 2元（block）
5. 行业超配 > 20%（block）
6. 最大持仓（block）
7. 重复信号 3日内（仅警告）
8. 波动率 > 200%（仅警告）

**PositionSizer** — 仓位计算公式：

```
base_weight = confidence_i / Σ(confidence)
vol_penalty = median_vol / vol_i
regime_mult = {bull: 1.2, sideways: 0.8, bear: 0.4}
总仓位上限 = {bull: 80%, sideways: 60%, bear: 30%}
单只上限 ≤ 10%, 单行业 ≤ 20%
shares = floor(weight × capital / price / 100) × 100
```

**StopLossTracker** — 追踪止损规则：

| 盈利 | 止损上移 |
|------|----------|
| > 10% | 入场价（保本） |
| > 20% | 入场价 + 10% |
| > 30% | 入场价 + 20% |

### 5. 反馈验证层

**BacktestValidator** 通过标准（任一未达标不投入实盘）：

| 指标 | 最低标准 |
|------|:--------:|
| 年化收益 | > 5% |
| 超额收益 vs 沪深300 | > 3% |
| 夏普比率 | > 0.5 |
| 最大回撤 | < 25% |
| 胜率（5日） | > 50% |
| t检验 p值 | < 0.05 |

**PaperTrader** go-live 条件：
1. 纸交易运行 ≥ 60 个交易日
2. 累计收益 > 0
3. 夏普比率 > 0.5
4. 最大回撤 < 20%
5. 月胜率 > 50%

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
PUSHPLUS_TOKEN=your-token
LLM_API_URL=https://api.deepseek.com/v1/chat/completions  # 可选
LLM_API_KEY=your-key  # 可选
```

### 3. 运行

```bash
# V3 统一管道（推荐）
python -c "from config import load_config; from pipeline.unified import run; run(load_config())"

# V1 兼容入口（deprecated，自动转发到 V3）
python src/main.py

# 纸交易模式（不推送）
python -c "from config import load_config; from pipeline.unified import run_paper_trading; run_paper_trading(load_config())"

# 运行回测
python src/feedback/backtest_validator.py

# 运行测试
pytest tests/ -v

# 类型检查
mypy --strict src/

# 代码质量
ruff check src/
```

## GitHub Actions

定时调度：工作日 11:45（北京时间）。支持手动触发。CI 环境自动容错。

| Secret | 说明 | 必填 |
|--------|------|:----:|
| `PUSHPLUS_TOKEN` | PushPlus 推送令牌 | ✅ |
| `LLM_API_URL` | LLM API 地址 | 可选 |
| `LLM_API_KEY` | LLM API 密钥 | 可选 |

## 开发规范

- 所有函数参数和返回值**必须**有类型注解
- 所有公共函数和类**必须**有 Google 风格 docstring
- 使用 `from __future__ import annotations`
- 日志使用 `logging.getLogger("thousand-times")`
- 每个模块对应 `tests/test_<module>.py`
- 使用 `pytest` + `monkeypatch` 模拟外部 API
- 提交使用 Conventional Commits: `feat/fix/perf/test/docs/refactor`

## 更新日志

### V3 — 2026-07-11

五层架构全面升级，12个新模块，解决10项核心问题：

- 🔴 **致命修复**：基本面数据值域统一（DataSourceUnifier）、评分分布拉伸（FactorCalibrator, σ≥15）、自适应投票阈值（AdaptiveVoter）、信号反馈闭环（SignalTracker）
- 🟡 **重要新增**：仓位管理（PositionSizer）、止损跟踪（StopLossTracker）、回测验证（BacktestValidator, t检验+蒙特卡洛）
- 🟢 **增强**：行业轮动（IndustryRotationAnalyzer, 31行业）、硬性风控（RiskGuard, 8条规则）、统一管道（UnifiedPipeline, 废弃V1）
- ✅ 172 个单元测试全部通过，mypy --strict + ruff check 通过

### V2 — 2026-06

- 多因子引擎（技术/基本面/资金/情绪/动量）、V2管道（collect→regime→factors→signal→output）
- 市场环境判断、策略回测框架、HTML报告、BaoStock/AKShare双源集成

### V1 — 2026-06

- 初始版本：技术指标、基本面分析、政策新闻LLM分析、综合评分、微信推送

## 免责声明

⚠️ 本系统仅供学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。

## 许可证

仅供学习研究使用。
