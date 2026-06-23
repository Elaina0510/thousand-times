# 千倍系统V2重构 - Agent执行Prompt

## 角色

你是A股量化分析系统的开发工程师，负责按照设计文档实施系统重构。

## 任务

按照以下8个计划文件，逐步实施系统重构：

```
doc/plans/2026-06-23-phase1-infrastructure.md  (基础设施)
doc/plans/2026-06-23-phase2-collect.md          (数据采集)
doc/plans/2026-06-23-phase3-regime.md           (环境判断)
doc/plans/2026-06-23-phase4-factors-lib.md      (因子库)
doc/plans/2026-06-23-phase5-factors-engine.md   (因子引擎)
doc/plans/2026-06-23-phase6-signal.md           (信号生成)
doc/plans/2026-06-23-phase7-backtest.md         (回测引擎)
doc/plans/2026-06-23-phase8-output-integration.md (输出集成)
```

## 执行规则

1. **严格按顺序执行**: 必须完成Phase N才能开始Phase N+1
2. **每个Task完成后**: 运行测试 → 确认通过 → 提交代码
3. **每个Phase完成后**: 运行该Phase的自检命令
4. **遇到错误时**: 停止执行，分析原因，修复后继续

## 关键约束

### 命名规范
- 市场环境投票: `RegimeVote` (bull/bear/neutral)
- 交易信号投票: `SignalVote` (buy/sell/neutral)
- 不要使用 `VoteSignal`，会导致命名冲突

### 函数签名
```python
# Phase 3: 市场环境判断
_signal_trend(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote
_signal_volume(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote
_signal_north_flow(north_flow: pd.DataFrame, config: RegimeConfig) -> RegimeVote
_signal_advance_decline(limit_up: int, limit_down: int, config: RegimeConfig) -> RegimeVote
_signal_valuation(index_kline: pd.DataFrame, config: RegimeConfig) -> RegimeVote

# Phase 2: 数据采集
stage_collect(config: AppConfig, regime: MarketRegime | None = None) -> DataBundle

# Phase 5: 因子引擎
calc_factors(data: DataBundle, config: AppConfig, regime_state: str = "sideways") -> dict[str, FactorScores]

# Phase 8: 报告生成
generate_report_md(signals: list[Signal], scores: dict[str, FactorScores], regime: MarketRegime) -> str
```

### 异常处理
- 单只股票失败: 跳过，不影响其他股票
- 单个信号失败: 返回 neutral
- 每个阶段: 独立 try-except

## 执行流程

### Phase 1: 基础设施
```
读取计划 → 执行Task 1-5 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_config_v2.py tests/test_data_sources.py -v
```

### Phase 2: 数据采集
```
读取计划 → 执行Task 1-4 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_pipeline_collect.py -v
```

### Phase 3: 市场环境判断
```
读取计划 → 执行Task 1-4 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_pipeline_regime.py -v
```

### Phase 4: 因子库
```
读取计划 → 执行Task 1-5 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_factors_*.py -v
```

### Phase 5: 因子引擎
```
读取计划 → 执行Task 1-3 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_pipeline_factors.py -v
```

### Phase 6: 信号生成
```
读取计划 → 执行Task 1-4 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_pipeline_signal.py -v
```

### Phase 7: 回测引擎
```
读取计划 → 执行Task 1-3 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_backtest_v2.py -v
```

### Phase 8: 输出与集成
```
读取计划 → 执行Task 1-4 → 运行测试 → 提交
```

自检:
```bash
pytest tests/test_pipeline_output.py -v
python -m src.main --help
```

## 最终验证

所有Phase完成后，运行：

```bash
# 完整测试套件
pytest tests/ -v

# 类型检查
mypy --strict src/

# 代码质量
ruff check src/

# 管道导入验证
python -c "from src.pipeline import MarketRegime, DataBundle, FactorScores, Signal, stage_collect, calc_factors, generate_signals, stage_output; print('ALL OK')"

# 命令行验证
python -m src.main --help
```

## 报告格式

每个Phase完成后，输出：

```
## Phase N 完成报告

### 完成的任务
- [x] Task 1: xxx
- [x] Task 2: xxx
...

### 测试结果
- 通过: X
- 失败: 0

### 自检结果
- [x] 所有测试通过
- [x] 类型检查通过
...

### 提交信息
feat: Phase N - xxx

### 下一步
开始 Phase N+1: xxx
```

## 注意事项

1. **不要跳过测试**: 每个Task都必须运行测试确认通过
2. **不要修改已有模块**: 除非计划文件明确要求
3. **保持向后兼容**: 旧模块保留，通过配置开关切换
4. **记录问题**: 遇到计划文件未覆盖的问题，记录但不擅自修改

## 开始执行

现在开始执行 Phase 1。读取 `doc/plans/2026-06-23-phase1-infrastructure.md` 并按照计划实施。
