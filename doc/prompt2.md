# VibeCoding Master Prompt — A股智能选股系统 V3

> **角色**：你是主 Agent（Orchestrator），负责统筹 V3 系统的全部开发工作。
> **目标**：无人工干预地完成 12 个模块的代码实现、单元测试、类型检查和代码质量验证。
> **约束**：每个模块必须通过 pytest（完整单元测试）+ mypy --strict + ruff check。

---

## 一、项目背景

### 1.1 当前系统

A股智能选股分析与推送系统，已运行 V2 版本。技术栈 Python 3.10+，数据源 BaoStock + AKShare。

**现有 V2 管道**（`src/pipeline/` 目录）：
```
collect → regime → factors → signal → output
```

### 1.2 V3 目标

基于系统评估报告（[doc/report/24.txt](doc/report/24.txt)），解决 10 项核心问题：
- 🔴 致命：基本面数据值域不统一、评分压缩（32.5~70.3）、信号全"观望"、反馈只写不读
- 🟡 重要：无仓位管理、止损无跟踪、回测无产出
- 🟢 增强：无行业轮动、无硬性风控、V1/V2 双管道并存

### 1.3 设计文档

- **详细设计**：[doc/detailed-design2.md](doc/detailed-design2.md) — 全部 12 个模块的接口定义、数据结构、算法伪代码
- **任务划分**：[doc/tasks2/](doc/tasks2/) — 每个模块的细分任务清单（含测试策略）

---

## 二、V3 系统架构

### 2.1 五层架构

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

### 2.2 数据流

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

### 2.3 依赖顺序（开发顺序）

```
Phase 1: Validator → Unifier
Phase 2: Calibrator + IndustryRotation (可并行)
Phase 3: AdaptiveVoter → UnifiedPipeline
Phase 4: Guard → PositionSizer + StopLossTracker (可并行)
Phase 5: Tracker → BacktestValidator → PaperTrader
```

---

## 三、主 Agent 工作流程

### 3.1 你的职责

1. **读取详细设计文档**：[doc/detailed-design2.md](doc/detailed-design2.md)（本 prompt 引用的设计细节以此文档为准）
2. **读取任务文件**：[doc/tasks2/](doc/tasks2/) 目录下的 `progress.md` 和各模块任务文件
3. **按依赖顺序**创建子 Agent 实现每个模块
4. **验证每个子 Agent 的产出**：确认 pytest、mypy、ruff 全部通过
5. **更新进度**：编辑 [doc/tasks2/progress.md](doc/tasks2/progress.md) 标记完成状态
6. **模块间集成**：确保接口匹配，下游模块能正确消费上游模块的输出

### 3.2 对每个模块的标准流程

```
Step 1: 阅读详细设计文档中对应章节（doc/detailed-design2.md 第二部分）
Step 2: 阅读任务文件（doc/tasks2/XX-module-name.md）
Step 3: 检查是否需读取现有源码（如上游模块的输出类型）
Step 4: 创建子 Agent，给出完整的实现指令
Step 5: 等待子 Agent 完成
Step 6: 运行 pytest 验证 → 不通过则让子 Agent 修复
Step 7: 运行 mypy --strict 验证 → 不通过则让子 Agent 修复
Step 8: 运行 ruff check 验证 → 不通过则让子 Agent 修复
Step 9: 更新 progress.md
Step 10: 进入下一个模块
```

### 3.3 子 Agent 指令模板

对每个子 Agent，必须包含：
- 模块名、文件路径、层级
- 参考的详细设计章节（具体到小节号）
- 数据结构定义（完整 dataclass/enum）
- 函数签名和 docstring（从设计文档复制）
- 算法逻辑（从设计文档复制或引用）
- 现有代码的接口（如上游模块的类型）
- 测试策略（从任务文件复制）
- 开发规范：from __future__ import annotations、logger、类型注解、Google docstring
- 验收标准

---

## 四、12 个模块详细说明

### 4.1 DataValidator — `data_quality/validator.py`

**设计参考**：[doc/detailed-design2.md 2.1.1 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/01-data-validator.md](doc/tasks2/01-data-validator.md)

**需要创建的文件**：
- `src/data_quality/__init__.py`
- `src/data_quality/validator.py`
- `tests/test_data_validator.py`

**核心数据结构**：
- `QualityLevel` enum（GOOD/DEGRADED/BAD）
- `FieldQuality` dataclass（单字段质量报告）
- `DataQualityReport` dataclass（完整质量报告）

**核心函数**：
- `validate_bundle(data: DataBundle) -> DataQualityReport`
- `detect_default_values(series, suspicious_values={60.0, 50.0, 0.0}) -> int`
- `flag_anomalous_stocks(report) -> list[str]`

**校验规则**：10 条规则（K线、基本面、资金面、情绪面），见设计文档 2.1.1.4 节

**测试**：10 个测试用例，覆盖全正常、K线不足、全默认值、混合异常、空数据等

**验收**：正确分类 GOOD/DEGRADED/BAD，默认值检测准确率 > 90%

---

### 4.2 DataSourceUnifier — `data_quality/unifier.py`

**设计参考**：[doc/detailed-design2.md 2.1.2 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/02-data-source-unifier.md](doc/tasks2/02-data-source-unifier.md)

**需要创建的文件**：
- `src/data_quality/unifier.py`
- `tests/test_data_source_unifier.py`

**核心数据结构**：
- `DataSource` enum（AKSHARE/BAOSTOCK/UNKNOWN）
- `NormalizedFundamental` dataclass（统一尺度基本面数据）
- `UnificationReport` dataclass

**关键转换逻辑**（见设计文档 2.1.2.4 值域映射表）：
- ROE: BaoStock 小数×100, AKShare 直用
- EPS: 两源直用
- 增长率: BaoStock×100, AKShare 直用
- 优先级: AKShare > BaoStock > 空数据
- 冲突检测: 两源差异 > 30% 时记录

**核心函数**：
- `unify_fundamental_data(akshare_results, baostock_results, quality_report)`
- `validate_value_range(data) -> list[str]`
- `get_preferred_source(code, akshare_avail, baostock_avail) -> DataSource`

**测试**：10 个用例，覆盖 AK/BaoStock 各场景、冲突、异常值域、全空回退等

**重要**：必须参考现有 `src/fundamental_analysis.py` 和 `src/baostock_data.py` 的返回格式

---

### 4.3 FactorCalibrator — `factors/calibrator.py`

**设计参考**：[doc/detailed-design2.md 2.2.1 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/03-factor-calibrator.md](doc/tasks2/03-factor-calibrator.md)

**需要创建的文件**：
- `src/factors/calibrator.py`
- `tests/test_factor_calibrator.py`

**核心数据结构**：
- `CalibratedScores` dataclass（technical/fundamental/capital/sentiment/momentum 各含 raw/pct/calibrated 三层）
- `CalibrationParams` dataclass（pct_weight=0.5, target_mean=50.0, target_std=20.0, tail_expand=1.5）

**核心算法**（见设计文档 2.2.1.4 伪代码）：
1. 计算每个因子在股票池中的百分位排名
2. 百分位与原始评分加权混合：`final = raw*(1-w) + pct*100*w`
3. Z-score 标准化拉伸：`stretched = target_mean + (x-μ)/σ * target_std`
4. 截断到 [0, 100]
5. 按 total 降序重排

**核心函数**：
- `calibrate_scores(raw_scores, params=None) -> list[CalibratedScores]`
- `calc_percentile_rank(value, all_values) -> float`
- `stretch_distribution(values, target_mean, target_std) -> list[float]`
- `optimize_calibration_params(backtest_results, param_grid) -> CalibrationParams`

**关键效果目标**：标准差从 ~8 → ≥15，范围从 32.5~70.3 → ~5~95

**测试**：10 个用例，覆盖集中分布、极端分布、均匀分布、异常值、空列表等

**重要**：必须参考现有 `src/pipeline/factors.py` 中 `FactorScores` 的类型定义

---

### 4.4 IndustryRotationAnalyzer — `factors/industry_rotation.py`

**设计参考**：[doc/detailed-design2.md 2.2.2 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/04-industry-rotation.md](doc/tasks2/04-industry-rotation.md)

**需要创建的文件**：
- `src/factors/industry_rotation.py`
- `tests/test_industry_rotation.py`

**核心数据结构**：
- `IndustryMomentum` dataclass（含 ret_1d/5d/20d/60d, trend_strength, fund_flow）
- `RotationSignal` dataclass（leading/turning/fading industries）
- `IndustryScoreAdjustment` dataclass（industry_alpha, adjustment, reason）

**核心函数**：
- `analyze_industry_rotation(etf_kline_cache, sector_flow, industry_stocks, lookback_days=60)`
- `calc_industry_adjustments(stock_pool, momentum_list) -> list[IndustryScoreAdjustment]`
- `detect_rotation_pattern(momentum_history) -> str`（6 种模式）

**行业映射**：扩展现有 `INDUSTRY_ETF_MAP` 到 31 个申万一级行业（见设计 2.2.2.4 节）

**测试**：8 个用例，覆盖成长轮动、普涨、行业转向、无 ETF 匹配、空数据等

**调整规则**：前 10% 行业 +5~+10，前 10-30% 行业 +2~+5，后 30% 行业 0~-5

---

### 4.5 AdaptiveVoter — `pipeline/signal.py`（改造）

**设计参考**：[doc/detailed-design2.md 2.3.1 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/05-adaptive-voter.md](doc/tasks2/05-adaptive-voter.md)

**需要修改的文件**：
- `src/pipeline/signal.py`（改造现有代码）
- `tests/test_pipeline_signal.py`（扩展）

**核心数据结构**：
- `AdaptiveThresholds` dataclass（含 `@staticmethod for_regime(state: str)`）
  - bull: min_buy=2, min_sell=4, factor_buy=65, rr=1.5
  - bear: min_buy=4, min_sell=2, factor_buy=80, rr=2.5
  - sideways: min_buy=2, min_sell=2, factor_buy=70, rr=2.0

**核心改造**：
1. 新增 `_decide_action_adaptive(votes, thresholds, risk_reward)` 替代硬编码 `_decide_action()`
2. 改造 `_vote_factor()` 和 `_vote_technical()` 使用自适应阈值
3. 改造 `generate_signals()` 调用 `AdaptiveThresholds.for_regime(regime_state)`
4. 保留旧函数标记 deprecated，保持 V1 回退路径

**关键指标**：buy/sell 信号合计占比从 0% 提升到 < 40% 总信号

**测试**：10 个用例，覆盖三种市场环境下的各种投票组合、盈亏比否决、反对票限制

---

### 4.6 UnifiedPipeline — `pipeline/unified.py`

**设计参考**：[doc/detailed-design2.md 2.3.2 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/06-unified-pipeline.md](doc/tasks2/06-unified-pipeline.md)

**需要创建的文件**：
- `src/pipeline/unified.py`
- `tests/test_unified_pipeline.py`

**核心数据结构**：
- `PipelineResult` dataclass（report_date, regime, quality_report, signals, report_text, errors, execution_time_seconds）

**核心函数**：
- `run(config: AppConfig) -> PipelineResult` — 六阶段编排（collect → quality → regime → factors → signal+risk → output+feedback）
- `run_paper_trading(config: AppConfig) -> PipelineResult` — 纸交易模式（不推送）

**废弃处理**：
- `main.py::main()` 顶部加 deprecation warning，自动转发到 `run(config)`
- `main.py::analyze_single_stock()` 和 `analyze_single_etf()` 标记 deprecated
- CLI 保留 `--v1` 应急回退选项
- 更新 GitHub Actions workflow 调用统一管道

**错误隔离**：每个阶段 try/except 包裹，单阶段失败不中断全部

**配置扩展**：在 `AppConfig` 中新增 `CalibrationConfig`、`RiskControlConfig`、`FeedbackConfig`（见设计第五章）

**测试**：8 个集成测试，覆盖端到端、阶段失败降级、纸交易模式、V1 回退等

---

### 4.7 PositionSizer — `risk/position.py`

**设计参考**：[doc/detailed-design2.md 2.4.1 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/07-position-sizer.md](doc/tasks2/07-position-sizer.md)

**需要创建的文件**：
- `src/risk/__init__.py`
- `src/risk/position.py`
- `tests/test_position_sizer.py`

**核心数据结构**：
- `PositionAllocation` dataclass（code, signal_confidence, volatility_pct, base_weight, adjusted_weight, shares, capital, max_loss, reason）
- `PortfolioSummary` dataclass（total_capital, allocated_capital, cash_reserve, position_count, sector_exposure, risk_contribution, warnings）

**仓位算法**（Kelly 启发式 + 波动率调整）：
1. base_weight = confidence_i / sum(all_confidence)
2. vol_penalty = median_vol / vol_i
3. regime_multiplier = {bull: 1.2, sideways: 0.8, bear: 0.4}
4. 硬上限：单只 ≤ 10%, 单行业 ≤ 20%, 总仓位 = {bull: 80%, sideways: 60%, bear: 30%}
5. shares = floor(weight * capital / price / 100) * 100

**核心函数**：
- `assign_positions(buy_signals, stock_pool, total_capital, regime, kline_cache, config)`
- `calc_volatility(kline, annualize=True) -> float`
- `check_sector_limits(allocations, industry_map, max_sector_pct=0.20) -> list[str]`

**测试**：10 个用例，覆盖各环境仓位限制、超限裁剪、波动率惩罚、零信号、100 股取整

---

### 4.8 StopLossTracker — `risk/stop_loss.py`

**设计参考**：[doc/detailed-design2.md 2.4.2 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/08-stop-loss-tracker.md](doc/tasks2/08-stop-loss-tracker.md)

**需要创建的文件**：
- `src/risk/stop_loss.py`
- `tests/test_stop_loss_tracker.py`

**核心数据结构**：
- `StopLossRecord` dataclass（code, entry_price, stop_loss_price, target_price, current_price, status, days_held, pnl_pct, hit_date）
- `StopLossSummary` dataclass（active_count, stopped_out_today, target_hit_today, near_stop_loss, avg_pnl, win_rate）

**核心函数**：
- `init_tracking(signals, today) -> list[StopLossRecord]`
- `check_stop_losses(records, kline_cache, today) -> StopLossSummary`
- `update_stop_price(record, new_stop, reason) -> StopLossRecord`
- `generate_stop_loss_alert(summary) -> str`

**追踪止损规则**：
- 盈利 > 10%：止损上移到入场价（保本）
- 盈利 > 20%：止损上移到 entry + 10%
- 盈利 > 30%：止损上移到 entry + 20%

**数据库**：ALTER TABLE recommendations 添加 stop_loss_price/target_price/status/hit_date/exit_price/pnl_pct 列

**测试**：10 个用例，覆盖止损/目标触发、接近预警、过期、追踪上移、数据库读写

---

### 4.9 RiskGuard — `risk/guard.py`

**设计参考**：[doc/detailed-design2.md 2.4.3 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/09-risk-guard.md](doc/tasks2/09-risk-guard.md)

**需要创建的文件**：
- `src/risk/guard.py`
- `tests/test_risk_guard.py`

**核心数据结构**：
- `RejectReason` enum（ST_STOCK, LIMIT_UP, LIMIT_DOWN, LOW_LIQUIDITY, HIGH_BID_ASK, PRICE_LIMIT, SECTOR_OVERWEIGHT, MAX_POSITION, RECENT_SIGNAL, EXCESSIVE_VOLATILITY）
- `RiskRuleResult` dataclass（passed, reject_reason, detail）
- `GuardResult` dataclass（input_count, passed_count, rejected[], passed[], warnings[]）

**8 条风控规则**（按优先级）：
1. ST/*ST 过滤（block）
2. 涨跌停检查 ≥ ±9.9%（block）
3. 流动性过滤 < 1000 万日均（block）
4. 仙股过滤 < 2 元（block）
5. 行业超配 > 20%（block）
6. 最大持仓（block）
7. 重复信号 3 日内（仅警告）
8. 波动率 > 200%（仅警告）

**核心函数**：
- `apply_risk_rules(signals, stock_pool, kline_cache, existing_positions, daily_stats) -> GuardResult`
- 每条规则独立的 `check_*` 函数

**测试**：10 个用例，覆盖全部 8 条规则、正常通过、警告 ≠ 拒绝

---

### 4.10 SignalTracker — `feedback/tracker.py`

**设计参考**：[doc/detailed-design2.md 2.5.1 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/10-signal-tracker.md](doc/tasks2/10-signal-tracker.md)

**需要创建的文件**：
- `src/feedback/__init__.py`
- `src/feedback/tracker.py`
- `tests/test_signal_tracker.py`

**核心数据结构**：
- `SignalPerformance` dataclass（含各周期收益 ret_1d/3d/5d/10d/20d, hit_target, hit_stop, max_favorable, max_adverse, vs_index_ret, vs_sector_ret）
- `AggregatePerformance` dataclass（含 win_rate_5d, sharpe_ratio, max_drawdown, profit_factor, by_score_range, by_sector, by_market_regime, score_threshold_advice）

**核心函数**：
- `record_signals_v3(signals, today) -> int` — 替代现有 `record_signals()`
- `compute_pnl(signal_date, lookback_days=20) -> list[SignalPerformance]`
- `compute_aggregate_performance(start_date, end_date) -> AggregatePerformance`
- `recommend_thresholds(performance) -> dict[str, float]` — 基于真实数据推荐阈值
- `generate_performance_report(performance) -> str`

**数据库**：创建 `signal_performance` 表和 `threshold_history` 表（见设计 2.5.1.4 节）

**反馈回路**：`recommend_thresholds()` 的输出应能反馈到 `AdaptiveVoter` 的阈值配置中

**测试**：10 个用例，覆盖记录、回顾计算、目标/止损坏检测、汇总统计、阈值推荐、空数据库

---

### 4.11 BacktestValidator — `feedback/backtest_validator.py`

**设计参考**：[doc/detailed-design2.md 2.5.2 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/11-backtest-validator.md](doc/tasks2/11-backtest-validator.md)

**需要创建的文件**：
- `src/feedback/backtest_validator.py`
- `tests/test_backtest_validator.py`
- `src/run_backtest.py`（CLI 入口脚本）

**核心数据结构**：
- `BacktestConfig` dataclass（start_date, end_date, pool_size, top_n, hold_days, commission_rate, stamp_tax, slippage, initial_capital, benchmark）
- `BacktestPeriodResult` dataclass（含 20+ 个统计指标：win_rate, sharpe, sortino, max_drawdown, calmar, profit_factor, t_statistic, p_value 等）
- `FullBacktestResult` dataclass（含 equity_curve, benchmark_curve, monthly_returns 等）

**核心函数**：
- `run_full_backtest(config) -> FullBacktestResult` — 13 步流程（见设计 2.5.2.4 伪代码）
- `run_parameter_sweep(base_config, param_grid) -> list`
- `statistical_significance_test(returns, benchmark_returns) -> (float, float)`
- `monte_carlo_test(returns, n_simulations=10000) -> dict`

**关键防护**：
- 必须避免未来函数（回测日期前不可见数据）
- 扣除交易成本（万三佣金 + 千一印花税 + 千一滑点）
- 训练/测试集分割（前 70% 参数优化，后 30% 样本外验证）

**通过标准**（任一未达标不投入实盘）：
| 指标 | 最低标准 |
|------|:--------:|
| 年化收益 | > 5% |
| 超额收益 vs 沪深300 | > 3% |
| 夏普比率 | > 0.5 |
| 最大回撤 | < 25% |
| 胜率 5日 | > 50% |
| t 检验 p 值 | < 0.05 |

**测试**：10 个用例，覆盖随机策略、牛市策略、成本扣减、t 检验、蒙特卡洛、未来函数防护等

---

### 4.12 PaperTrader — `feedback/paper_trader.py`

**设计参考**：[doc/detailed-design2.md 2.5.3 节](doc/detailed-design2.md)
**任务文件**：[doc/tasks2/12-paper-trader.md](doc/tasks2/12-paper-trader.md)

**需要创建的文件**：
- `src/feedback/paper_trader.py`
- `tests/test_paper_trader.py`

**核心数据结构**：
- `PaperAccount` dataclass（initial_capital, cash, positions, total_value, daily_pnl, total_pnl, trade_history, daily_records）
- `PaperPosition` dataclass（code, shares, avg_cost, current_price, market_value, pnl, days_held）
- `PaperTrade` dataclass（date, code, action, price, shares, amount, commission, stamp_tax, signal_score, signal_confidence, reason）

**核心函数**：
- `init_paper_account(capital=1_000_000.0) -> PaperAccount`
- `execute_daily_signals(account, signals, stock_pool, today) -> PaperAccount`
- `generate_paper_report(account) -> str`
- `check_go_live_readiness(account, min_days=60) -> (bool, str)`

**Go-live 条件**：
1. 纸交易运行 ≥ 60 个交易日
2. 累计收益 > 0
3. 夏普比率 > 0.5
4. 最大回撤 < 20%
5. 月胜率 > 50%

**数据库**：创建 `paper_account`、`paper_trades`、`paper_positions` 三张表（见设计 2.5.3.4 节）

**测试**：12 个用例，覆盖初始化、买入/卖出/止损执行、交易成本、100 股取整、资金不足、go-live 检查、数据库持久化、报告生成

---

## 五、开发规范

### 5.1 代码风格

```python
from __future__ import annotations  # 每个 .py 文件首行（docstring 之后）

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("thousand-times")

# 所有函数参数和返回值必须有类型注解
# 所有公共函数和类必须有 Google 风格 docstring
def example(param: str) -> int:
    """简要描述。

    Args:
        param: 参数说明。

    Returns:
        返回值说明。

    Raises:
        ValueError: 异常说明。
    """
    ...
```

### 5.2 测试规范

```python
# tests/test_<module>.py, 每个模块对应一个测试文件
# 使用 monkeypatch 模拟外部 API 调用
# 不依赖网络连接，所有外部数据通过 mock 提交
# 函数命名：test_<功能描述>

def test_normal_data_bundle(monkeypatch):
    """测试全部数据正常场景。"""
    ...

def test_kline_insufficient_data():
    """测试K线数据不足场景。"""
    ...
```

### 5.3 验证命令

```bash
# 单个模块测试
pytest tests/test_<module>.py -v

# 类型检查
mypy --strict src/<package>/<module>.py

# 代码质量
ruff check src/<package>/<module>.py

# 全部测试（最终验证）
pytest tests/ -v
```

---

## 六、进度追踪

### 6.1 进度文件

编辑 [doc/tasks2/progress.md](doc/tasks2/progress.md)，更新：
- 各模块状态：⬜ 未开始 → 🟡 开发中 → 🟢 已完成
- 开始/完成时间
- 阶段汇总百分比

### 6.2 验收条件总览

- [ ] 基本面 ROE 与公开数据偏差 < 10%
- [ ] 评分标准差 ≥ 15（从 ~8 提升）
- [ ] buy/sell 信号比例 < 总信号 40%
- [ ] 全部最低回测标准通过
- [ ] 纸交易连续 60 个交易日满足 go-live
- [ ] 所有模块单元测试通过
- [ ] 所有模块 mypy --strict 通过
- [ ] 所有模块 ruff check 通过

---

## 七、开始执行

请按照 **Phase 1 → Phase 5** 的顺序执行。

### Phase 1: 数据质量层
- **Task 1.1**: 实现 DataValidator → 验证通过
- **Task 1.2**: 实现 DataSourceUnifier → 验证通过

### Phase 2: 因子评分层
- **Task 2.1**: 实现 FactorCalibrator → 验证通过
- **Task 2.2**: 实现 IndustryRotationAnalyzer → 验证通过（可与 2.1 并行）

### Phase 3: 信号生成层
- **Task 3.1**: 改造 AdaptiveVoter → 验证通过
- **Task 3.2**: 实现 UnifiedPipeline → 验证通过（依赖 3.1 + Phase 1-2 全部完成）

### Phase 4: 风控执行层
- **Task 4.1**: 实现 RiskGuard → 验证通过
- **Task 4.2**: 实现 PositionSizer → 验证通过（可与 4.2 并行）
- **Task 4.3**: 实现 StopLossTracker → 验证通过（可与 4.1 并行）

### Phase 5: 反馈验证层
- **Task 5.1**: 实现 SignalTracker → 验证通过
- **Task 5.2**: 实现 BacktestValidator → 验证通过（依赖 5.1）
- **Task 5.3**: 实现 PaperTrader → 验证通过（依赖所有前序模块）

### 最终验证
- [ ] `pytest tests/ -v` 全部通过
- [ ] `mypy --strict src/` 全部通过
- [ ] `ruff check src/` 全部通过

---

> **文档版本**：v1.0
> **生成日期**：2026-07-11
> **输入来源**：[doc/detailed-design2.md](doc/detailed-design2.md) + [doc/tasks2/](doc/tasks2/)
