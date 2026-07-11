# BacktestValidator — 完整回测与显著性检验

> 模块：`feedback/backtest_validator.py`
> 层级：Layer 5 — 反馈验证层
> 详细设计：[2.5.2](../detailed-design2.md#252-backtestvalidator--feedbackbacktest_validatorpy)

## 概述

对策略进行完整的历史回测验证，输出统计显著的结果。改造现有的 `backtest.py`（目前仅框架），使其能产出可信的回测结果。

## 依赖

- **上游**：全部 pipeline 模块（与生产共用代码）, AKShare 历史数据
- **下游**：实施决策（是否投入实盘）

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/feedback/backtest_validator.py` 骨架
- [ ] **1.2** 创建 `tests/test_backtest_validator.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `BacktestConfig` dataclass
  - start_date, end_date, pool_size, top_n, hold_days
  - commission_rate, stamp_tax, slippage
  - initial_capital, benchmark
- [ ] **2.2** 实现 `BacktestPeriodResult` dataclass
  - 各持仓周期的详细统计（胜率/夏普/最大回撤/盈亏比/t检验等）
- [ ] **2.3** 实现 `FullBacktestResult` dataclass
  - 净值曲线、月度收益、风控指标、改进建议

### 3. 回测引擎

- [ ] **3.1** 实现 `run_full_backtest(config: BacktestConfig) -> FullBacktestResult`
  - Step1: 获取交易日历
  - Step2: 逐日构建历史 DataBundle（模拟当日收盘数据）
  - Step3: 执行完整分析管道（与生产代码相同）
  - Step4: 按信号买入 top_n 只，T+N 日后卖出
  - Step5: 扣除佣金（万三）、印花税（千一，卖出）、滑点（千一）
  - Step6: 计算净值曲线
  - Step7: 计算全部统计指标
- [ ] **3.2** 实现 `_build_historical_bundle(date, pool_size) -> DataBundle`
  - 获取 date 当天的股票池
  - 获取 date 之前的 K 线数据（避免未来函数）
  - 获取 date 当天可用的基本面数据
- [ ] **3.3** 实现 `_execute_trade(signal, entry_date, hold_days, trading_calendar) -> dict`
  - 模拟买入/卖出
  - 扣除全部交易成本
  - 返回交易记录
- [ ] **3.4** 实现 `_compute_benchmark_curve(trading_days, initial_capital, benchmark) -> list[float]`
  - 获取基准指数（沪深300）的同期收益曲线

### 4. 参数优化

- [ ] **4.1** 实现 `run_parameter_sweep(base_config, param_grid) -> list[tuple[dict, BacktestPeriodResult]]`
  - 网格搜索参数：top_n, hold_days, buy_threshold, min_buy_votes
  - 按夏普比率降序排列
  - 记录最优参数组合
- [ ] **4.2** 实现 `_split_train_test(trading_days, train_ratio=0.7) -> (list, list)`
  - 前 70% 用于参数优化
  - 后 30% 用于样本外验证

### 5. 统计检验

- [ ] **5.1** 实现 `statistical_significance_test(returns, benchmark_returns) -> (t_stat, p_value)`
  - 配对 t 检验
  - H0: 策略收益 ≤ 基准收益
  - p < 0.05 → 拒绝 H0
- [ ] **5.2** 实现 `monte_carlo_test(returns, n_simulations=10000) -> dict`
  - 随机重排收益率序列 10000 次
  - 真实夏普比率 vs 随机分布
  - 返回百分位和显著性判断

### 6. 报告生成

- [ ] **6.1** 实现 `generate_backtest_report(result: FullBacktestResult) -> str`
  - 包含：各周期指标对比表、净值曲线描述、月度/年度收益
  - 包含：是否通过最低标准
  - 包含：参数优化建议
- [ ] **6.2** 实现 `print_backtest_summary(result)` — 控制台输出

### 7. CLI 入口

- [ ] **7.1** 创建 `src/run_backtest.py` CLI 脚本
  - 支持 --config（配置文件路径）
  - 支持 --param-sweep（网格搜索模式）
  - 支持 --output（报告输出路径）

### 8. 测试

- [ ] **8.1** 测试随机策略回测 → Sharpe < 0
- [ ] **8.2** 测试模拟牛市数据 → Sharpe > 0.5
- [ ] **8.3** 测试交易成本扣减（已知收益序列）
- [ ] **8.4** 测试 t 检验（已知均值>0 序列）→ t > 2, p < 0.05
- [ ] **8.5** 测试蒙特卡洛检验
- [ ] **8.6** 测试无交易场景 → total_trades=0
- [ ] **8.7** 测试参数网格搜索 → 返回最优参数
- [ ] **8.8** 测试报告生成格式
- [ ] **8.9** 测试未来函数防护（回测日期前的数据不包含未来信息）
- [ ] **8.10** 运行 `pytest tests/test_backtest_validator.py -v` 全部通过

---

## 验收标准

最低标准（任一未达标不投入实盘）：

- [ ] 年化收益 > 5%
- [ ] 超额收益（vs 沪深300） > 3%
- [ ] 夏普比率 > 0.5
- [ ] 最大回撤 < 25%
- [ ] 胜率（5日） > 50%
- [ ] t 检验 p 值 < 0.05
- [ ] 10 个单元测试全部通过
