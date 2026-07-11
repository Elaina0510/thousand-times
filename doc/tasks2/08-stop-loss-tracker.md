# StopLossTracker — 止损跟踪与触发推送

> 模块：`risk/stop_loss.py`
> 层级：Layer 4 — 风控执行层
> 详细设计：[2.4.2](../detailed-design2.md#242-stoplosstracker--riskstop_losspy)

## 概述

跟踪已推荐信号的止损状态，在价格触及止损价时主动推送提醒。支持追踪止损（盈利后上移止损）。

## 依赖

- **上游**：`Signal[]`, `DataBundle.kline_cache`
- **下游**：`UnifiedPipeline`, 数据库（SQLite）

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/risk/stop_loss.py` 骨架
- [ ] **1.2** 创建 `tests/test_stop_loss_tracker.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `StopLossRecord` dataclass
  - code, name, entry_date, entry_price, stop_loss_price, target_price
  - current_price, status, days_held, pnl_pct, hit_date
- [ ] **2.2** 实现 `StopLossSummary` dataclass
  - active_count, stopped_out_today, target_hit_today, near_stop_loss
  - avg_pnl, win_rate

### 3. 止损跟踪

- [ ] **3.1** 实现 `init_tracking(signals, today) -> list[StopLossRecord]`
  - 从 signals 提取 key_prices 中的 stop_loss 和 target
  - 初始化 status="active"
- [ ] **3.2** 实现 `check_stop_losses(records, kline_cache, today) -> StopLossSummary`
  - 遍历活跃记录，获取最新价格
  - 当前价 ≤ 止损价 → stopped_out
  - 当前价 ≥ 目标价 → target_hit
  - 持仓 > 30 天 → expired
  - 距止损 < 3% → near_stop_loss 预警
- [ ] **3.3** 实现 `_update_prices(record, kline_cache) -> StopLossRecord`
  - 从 kline_cache 获取最新收盘价
  - 计算 days_held 和 pnl_pct

### 4. 追踪止损

- [ ] **4.1** 实现 `update_stop_price(record, new_stop, reason) -> StopLossRecord`
  - 允许手动和自动更新止损价
- [ ] **4.2** 实现 `_auto_trailing_stop(record) -> (bool, float, str)`
  - 盈利 > 10%：止损上移到入场价（保本）
  - 盈利 > 20%：止损上移到 entry + 10%
  - 盈利 > 30%：止损上移到 entry + 20%
  - 返回 (是否更新, 新止损价, 理由)

### 5. 数据库

- [ ] **5.1** 在 `cache/recommendations.db` 中 ALTER TABLE 添加新列
  - stop_loss_price REAL
  - target_price REAL
  - status TEXT DEFAULT 'active'
  - hit_date TEXT
  - exit_price REAL
  - pnl_pct REAL
- [ ] **5.2** 实现 `_save_records(records)` 写入数据库
- [ ] **5.3** 实现 `_load_active_records() -> list[StopLossRecord]` 加载历史记录

### 6. 消息推送

- [ ] **6.1** 实现 `generate_stop_loss_alert(summary) -> str`
  - 触及止损：列出代码、名称、亏损比例
  - 触及目标：列出代码、名称、盈利比例
  - 接近止损：预警列表
- [ ] **6.2** 集成到 `UnifiedPipeline`：每日运行后调用 `check_stop_losses()`

### 7. 测试

- [ ] **7.1** 测试价格触及止损 → status=stopped_out
- [ ] **7.2** 测试价格触及目标 → status=target_hit
- [ ] **7.3** 测试距止损 2% → near_stop_loss 包含该记录
- [ ] **7.4** 测试持仓 > 30 天 → expired
- [ ] **7.5** 测试追踪止损上移（盈利 25%）→ 新止损 = entry + 10%
- [ ] **7.6** 测试盈利 < 10% 不触发追踪止损
- [ ] **7.7** 测试空记录 → active_count=0
- [ ] **7.8** 测试数据库读写
- [ ] **7.9** 测试消息生成格式
- [ ] **7.10** 运行 `pytest tests/test_stop_loss_tracker.py -v` 全部通过

---

## 验收标准

- [ ] 止损触发 100% 被检测（无漏报）
- [ ] 追踪止损规则正确执行
- [ ] 数据库正确持久化
- [ ] 10 个单元测试全部通过
