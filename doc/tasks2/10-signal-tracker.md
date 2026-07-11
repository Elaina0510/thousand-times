# SignalTracker — 信号→收益闭环追踪

> 模块：`feedback/tracker.py`
> 层级：Layer 5 — 反馈验证层
> 详细设计：[2.5.1](../detailed-design2.md#251-signaltracker--feedbacktrackerpy)

## 概述

将现有的"只写不读"信号追踪升级为完整的信号→收益闭环反馈系统。记录推荐历史，计算回顾准确率，将结果反馈到信号置信度校准。

## 依赖

- **上游**：`Signal[]`, `DataBundle.kline_cache`
- **下游**：`AdaptiveVoter`（阈值推荐反馈）, 数据库（SQLite）

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/feedback/__init__.py`
- [ ] **1.2** 创建 `src/feedback/tracker.py` 骨架
- [ ] **1.3** 创建 `tests/test_signal_tracker.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `SignalPerformance` dataclass
  - signal_id, code, name, signal_date, signal_action, signal_score, entry_price
  - ret_1d/3d/5d/10d/20d, hit_target, hit_stop, max_favorable, max_adverse
  - vs_index_ret, vs_sector_ret
- [ ] **2.2** 实现 `AggregatePerformance` dataclass
  - period, total_signals, buy_signals, sell_signals
  - win_rate_5d, avg_return_5d, avg_excess_return_5d
  - sharpe_ratio, max_drawdown, profit_factor
  - by_score_range, by_sector, by_market_regime
  - score_threshold_advice

### 3. 信号记录

- [ ] **3.1** 实现 `record_signals_v3(signals, today) -> int`
  - 替代现有的 `signal_tracker.py::record_signals()`
  - 扩展字段：stop_loss_price, target_price, status, confidence
  - 返回记录的信号数
- [ ] **3.2** 确保与现有 `recommendations` 表兼容
  - 使用 INSERT OR REPLACE 避免重复

### 4. 回顾计算

- [ ] **4.1** 实现 `compute_pnl(signal_date, lookback_days=20) -> list[SignalPerformance]`
  - 从数据库查询 signal_date 的信号
  - 通过 AKShare 获取回溯期的 K 线数据
  - 计算各周期收益率（1d/3d/5d/10d/20d）
  - 检查是否触达 target_price 和 stop_loss_price
  - 计算最大浮盈/浮亏
  - 计算相对沪深 300 和行业 ETF 的超额收益
- [ ] **4.2** 实现 `_fetch_pnl_kline(code, from_date, to_date) -> pd.DataFrame`
  - 从 AKShare 获取回顾期的 K 线
  - 使用缓存避免重复下载
- [ ] **4.3** 实现 `_check_price_levels(code, kline, entry_price, target, stop) -> (bool, bool, float, float)`
  - 遍历 K 线检查是否触达 target 或 stop
  - 计算最大浮盈和最大浮亏

### 5. 汇总统计

- [ ] **5.1** 实现 `compute_aggregate_performance(start_date, end_date) -> AggregatePerformance`
  - 统计全部信号的整体胜率、平均收益、夏普比率等
  - 按分数段分类：<50, 50-60, 60-70, 70-80, >80
  - 按行业分类
  - 按市场环境分类
- [ ] **5.2** 实现 `recommend_thresholds(performance) -> dict[str, float]`
  - 找胜率 > 55% 的最低分数 → 推荐 buy_threshold
  - 找胜率 < 40% 的最高分数 → 推荐 sell_threshold
  - 返回推荐字典
- [ ] **5.3** 实现 `generate_performance_report(performance) -> str`
  - 生成 Markdown 格式表现报告
  - 附加到每日报告的末尾

### 6. 数据库

- [ ] **6.1** 创建 `signal_performance` 表（见设计文档）
- [ ] **6.2** 创建 `threshold_history` 表（记录阈值优化历史）
- [ ] **6.3** 实现 `_save_performance(performances)` 持久化
- [ ] **6.4** 实现 `_load_performance(start_date, end_date) -> list[SignalPerformance]`

### 7. 测试

- [ ] **7.1** 测试记录 10 条信号 → 数据库新增 10 条
- [ ] **7.2** 测试计算 7 天前信号的 5 日收益（使用 mock K线数据）
- [ ] **7.3** 测试目标价触达检测
- [ ] **7.4** 测试止损价触达检测
- [ ] **7.5** 测试汇总统计：100 条 30 天数据 → 胜率/夏普正确
- [ ] **7.6** 测试阈值推荐：给定胜率数据 → 推荐阈值胜率 > 50%
- [ ] **7.7** 测试空数据库 → 返回空结果不报错
- [ ] **7.8** 测试超额收益计算（vs index, vs sector）
- [ ] **7.9** 测试表现报告生成格式
- [ ] **7.10** 运行 `pytest tests/test_signal_tracker.py -v` 全部通过

---

## 验收标准

- [ ] 信号记录成功率 100%
- [ ] 回顾收益计算与真实行情偏差 < 0.5%
- [ ] 阈值推荐基于真实数据（非硬编码）
- [ ] 表现报告正确格式化
- [ ] 10 个单元测试全部通过
