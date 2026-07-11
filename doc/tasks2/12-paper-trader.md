# PaperTrader — 模拟交易（纸交易）

> 模块：`feedback/paper_trader.py`
> 层级：Layer 5 — 反馈验证层
> 详细设计：[2.5.3](../detailed-design2.md#253-papertrader--feedbackpaper_traderpy)

## 概述

在实盘交易前提供模拟交易（纸交易）模式。使用真实每日数据执行策略但不产生真实资金变动。纸交易至少运行 60 个交易日且达标后，方可切换到实盘。

## 依赖

- **上游**：`UnifiedPipeline`（每日信号）, `PositionSizer`（仓位计算）
- **下游**：实施决策（go-live）

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/feedback/paper_trader.py` 骨架
- [ ] **1.2** 创建 `tests/test_paper_trader.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `PaperAccount` dataclass
  - initial_capital, cash, positions, total_value
  - daily_pnl, total_pnl, total_pnl_pct
  - trade_history, daily_records
- [ ] **2.2** 实现 `PaperPosition` dataclass
  - code, name, shares, avg_cost, current_price
  - market_value, pnl, pnl_pct, days_held
- [ ] **2.3** 实现 `PaperTrade` dataclass
  - date, code, action, price, shares, amount
  - commission, stamp_tax, signal_score, signal_confidence, reason

### 3. 账户管理

- [ ] **3.1** 实现 `init_paper_account(capital=1_000_000.0) -> PaperAccount`
  - 初始化 0 持仓的模拟账户
  - 创建数据库记录
- [ ] **3.2** 实现 `_load_account() -> PaperAccount`
  - 从数据库加载最新账户状态
- [ ] **3.3** 实现 `_save_account(account)` 
  - 持久化账户快照到数据库

### 4. 交易执行

- [ ] **4.1** 实现 `execute_daily_signals(account, signals, stock_pool, today) -> PaperAccount`
  - 买入：按 PositionSizer 计算的股数（100 股整数倍）
  - 卖出：信号为 sell 的持仓全部卖出
  - 止损：检查触发止损的持仓并强制卖出
  - 扣费：佣金万三 + 印花税千一（卖出） + 滑点千一
  - 更新持仓市值和账户总资产
- [ ] **4.2** 实现 `_execute_buy(account, signal, stock_pool, today) -> PaperTrade`
  - 计算买入股数（100 股整数倍）
  - 检查资金是否充足
  - 创建/更新 PaperPosition
- [ ] **4.3** 实现 `_execute_sell(account, position, price, today, reason) -> PaperTrade`
  - 清空对应持仓
  - 计算实现盈亏
  - 扣除卖出成本
- [ ] **4.4** 实现 `_update_market_values(account, stock_pool)`
  - 用当日收盘价更新所有持仓市值
  - 计算每日浮盈

### 5. 业绩报告

- [ ] **5.1** 实现 `generate_paper_report(account) -> str`
  - 账户总览：总资产/现金/持仓市值/累计收益率
  - 当日交易明细
  - 持仓列表（含盈亏）
  - 净值曲线（与基准对比）
  - 关键指标：夏普比/最大回撤/胜率
- [ ] **5.2** 实现 `_compute_paper_metrics(account) -> dict`
  - 日收益率序列 → 年化收益、波动率、夏普比率
  - 净值曲线 → 最大回撤

### 6. 实盘就绪检查

- [ ] **6.1** 实现 `check_go_live_readiness(account, min_days=60) -> (bool, str)`
  - 纸交易运行 ≥ 60 个交易日
  - 累计收益 > 0
  - 夏普比率 > 0.5
  - 最大回撤 < 20%
  - 月胜率 > 50%
  - 返回 (是否就绪, 就绪/未就绪原因)
- [ ] **6.2** 实现 `_compute_monthly_win_rate(account) -> float`
  - 月度收益为正的月数 / 总月数

### 7. 数据库

- [ ] **7.1** 创建 `paper_account` 表（每日快照）
- [ ] **7.2** 创建 `paper_trades` 表（交易记录）
- [ ] **7.3** 创建 `paper_positions` 表（当前持仓）

### 8. 测试

- [ ] **8.1** 测试初始化账户（100万）→ cash=100万
- [ ] **8.2** 测试买入信号执行 → 持仓新增，现金减少
- [ ] **8.3** 测试卖出信号执行 → 持仓清空，现金增加，盈亏计算正确
- [ ] **8.4** 测试止损触发 → 强制卖出
- [ ] **8.5** 测试交易成本扣除（买入+卖出）
- [ ] **8.6** 测试 100 股整数倍
- [ ] **8.7** 测试资金不足 → 买入拒绝
- [ ] **8.8** 测试每日市值更新
- [ ] **8.9** 测试 go-live 条件检查（模拟 60 天数据）
- [ ] **8.10** 测试报告生成格式
- [ ] **8.11** 测试数据库持久化和恢复
- [ ] **8.12** 运行 `pytest tests/test_paper_trader.py -v` 全部通过

---

## 验收标准

- [ ] 交易成本正确扣除（佣金 + 印花税 + 滑点）
- [ ] 100 股整数倍约束不被突破
- [ ] 数据库正确持久化（重启后恢复）
- [ ] go-live 检查 5 个条件全部正确判断
- [ ] 12 个单元测试全部通过
