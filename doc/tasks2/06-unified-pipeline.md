# UnifiedPipeline — 统一管道入口

> 模块：`pipeline/unified.py`
> 层级：Layer 3 — 信号生成层
> 详细设计：[2.3.2](../detailed-design2.md#232-unifiedpipeline--pipelineunifiedpy)

## 概述

废弃 V1 管道（`main.py::main()`），以 V2 五阶段管道为基础注入全部新模块，形成唯一执行入口。

## 依赖

- **上游**：所有模块（编排器）
- **下游**：GitHub Actions 工作流、手动执行

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/pipeline/unified.py` 骨架
- [ ] **1.2** 实现 `PipelineResult` dataclass

### 2. 统一管道主函数

- [ ] **2.1** 实现 `run(config: AppConfig) -> PipelineResult`
  - 阶段 1：数据采集 → `stage_collect()` → DataBundle
  - 阶段 1.5：数据质量 → `validate_bundle()` → report, `unify_fundamental_data()` → normalized
  - 阶段 2：市场环境 → `judge_market_regime()` → MarketRegime
  - 阶段 3：因子计算 → `calc_factors()` → raw_scores → `calibrate_scores()` → calibrated
  - 阶段 3.5：行业调整 → `analyze_industry_rotation()` → adjustments
  - 阶段 4：信号生成 → `generate_signals()` (+AdaptiveVoter) → `apply_risk_rules()` → `assign_positions()` → `init_tracking()`
  - 阶段 5：输出 → `stage_output()` + `record_signals_v3()`
  - 统计执行耗时，收集所有错误
- [ ] **2.2** 实现 `run_paper_trading(config) -> PipelineResult`
  - 同 `run()` 但不推送
  - 所有信号记录到 SignalTracker 用于验证
- [ ] **2.3** 实现错误隔离逻辑
  - 每个阶段的异常不中断整个管道
  - 使用 try/except 包裹每个阶段
  - 记录错误到 PipelineResult.errors[]

### 3. V1 废弃处理

- [ ] **3.1** 在 `main.py::main()` 函数顶部添加 deprecation warning
  - `logger.warning("V1管道已废弃，请使用 pipeline/unified.py::run()")`
  - 自动转发到 `run(config)`
- [ ] **3.2** 在 `main.py::analyze_single_stock()` 添加 deprecation warning
- [ ] **3.3** 在 `main.py::analyze_single_etf()` 添加 deprecation warning
- [ ] **3.4** 在 CLI 参数中保留 --v1 选项用于应急回退
- [ ] **3.5** 更新 `.github/workflows/daily_analysis.yml` 调用统一管道

### 4. 配置集成

- [ ] **4.1** 在 `AppConfig` 中添加 `calibration: CalibrationConfig`
- [ ] **4.2** 在 `AppConfig` 中添加 `risk_control: RiskControlConfig`
- [ ] **4.3** 在 `AppConfig` 中添加 `feedback: FeedbackConfig`
- [ ] **4.4** 更新 `load_config()` 支持从 YAML 加载新配置节
- [ ] **4.5** 更新 `config.yaml` 示例文件

### 5. 测试

- [ ] **5.1** 集成测试：完整管道运行（使用 mock 数据）
- [ ] **5.2** 测试阶段 1.5 失败不影响后续
- [ ] **5.3** 测试阶段 3 失败时使用原始评分（降级）
- [ ] **5.4** 测试所有阶段成功 → PipelineResult.errors=[], push_success
- [ ] **5.5** 测试纸交易模式 → 不推送
- [ ] **5.6** 测试执行耗时统计
- [ ] **5.7** 测试 CLI --v1 回退路径
- [ ] **5.8** 运行 `pytest tests/test_unified_pipeline.py -v` 全部通过

---

## 验收标准

- [ ] `run(config)` 端到端执行成功
- [ ] 所有新模块正确注入（数据质量 → 校准 → 自适应投票 → 风控 → 反馈）
- [ ] V1 调用自动转发到 V3，带 deprecation 警告
- [ ] GitHub Actions 工作流更新为调用统一管道
- [ ] 8 个集成测试全部通过
