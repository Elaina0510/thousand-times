# RiskGuard — 硬性风控规则引擎

> 模块：`risk/guard.py`
> 层级：Layer 4 — 风控执行层
> 详细设计：[2.4.3](../detailed-design2.md#243-riskguard--riskguardpy)

## 概述

在信号生成后执行硬性风控规则，过滤掉不符合交易规则的信号（ST、涨跌停、流动性不足等）。

## 依赖

- **上游**：`Signal[]`, `DataBundle.stock_pool`, `DataBundle.kline_cache`
- **下游**：`PositionSizer`（只处理过滤后的信号）

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/risk/guard.py` 骨架
- [ ] **1.2** 创建 `tests/test_risk_guard.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `RejectReason` 枚举
  - ST_STOCK, LIMIT_UP, LIMIT_DOWN, LOW_LIQUIDITY
  - HIGH_BID_ASK, PRICE_LIMIT, SECTOR_OVERWEIGHT
  - MAX_POSITION, RECENT_SIGNAL, EXCESSIVE_VOLATILITY
- [ ] **2.2** 实现 `RiskRuleResult` dataclass
  - passed, reject_reason, detail
- [ ] **2.3** 实现 `GuardResult` dataclass
  - input_count, passed_count, rejected[], passed[], warnings[]

### 3. 风控规则实现

- [ ] **3.1** 实现 `apply_risk_rules(signals, stock_pool, kline_cache, existing_positions, daily_stats) -> GuardResult`
  - 按优先级依次应用所有规则
  - 收集拒绝和警告
- [ ] **3.2** 实现 `check_st_stock(code, name) -> RiskRuleResult`
  - 名称含 ST 或 *ST → 拒绝
- [ ] **3.3** 实现 `check_limit_price(code, stock_pool) -> RiskRuleResult`
  - 涨跌幅达到 ±9.9% → 拒绝（买入：涨停无法买入，卖出：跌停无法卖出）
- [ ] **3.4** 实现 `check_liquidity(code, kline_cache) -> RiskRuleResult`
  - 近 20 日均成交额 < 1000 万 → 拒绝
- [ ] **3.5** 实现 `check_penny_stock(code, stock_pool, min_price=2.0) -> RiskRuleResult`
  - 股价 < 2 元 → 拒绝（仙股风险）
- [ ] **3.6** 实现 `check_sector_overweight(code, industry, existing_positions, max_pct=0.20) -> RiskRuleResult`
  - 与 PositionSizer 的行业限制协同
- [ ] **3.7** 实现 `check_max_positions(code, existing_positions, max_count) -> RiskRuleResult`
  - 当前持仓数超过市场环境对应的上限 → 拒绝新的买入信号
- [ ] **3.8** 实现 `check_duplicate_signal(code, action, existing_positions) -> RiskRuleResult`
  - 最近 3 日内同股票同方向 → 仅警告
- [ ] **3.9** 实现 `check_excessive_volatility(code, kline_cache) -> RiskRuleResult`
  - 年化波动率 > 200% → 仅警告

### 4. 风控规则配置

- [ ] **4.1** 实现 `RISK_RULES` 配置列表
  - 每条规则：name, priority, block (True=拒绝, False=仅警告)
  - 支持按优先级排序执行
- [ ] **4.2** 实现 `_get_max_positions(regime_state) -> int`
  - bull: 15, sideways: 10, bear: 5

### 5. 测试

- [ ] **5.1** 测试 ST 股票 → 拒绝
- [ ] **5.2** 测试涨停板 → 拒绝（买入）
- [ ] **5.3** 测试跌停板 → 拒绝（卖出）
- [ ] **5.4** 测试低流动性（均成交 500 万）→ 拒绝
- [ ] **5.5** 测试仙股（price=1.50）→ 拒绝
- [ ] **5.6** 测试正常股票 → 全部通过
- [ ] **5.7** 测试仅警告规则（波动率 250%）→ 通过但有警告
- [ ] **5.8** 测试行业超配 → 后续同行业信号拒绝
- [ ] **5.9** 测试规则优先级：先阻断后警告
- [ ] **5.10** 运行 `pytest tests/test_risk_guard.py -v` 全部通过

---

## 验收标准

- [ ] 8 条规则全部正确实现
- [ ] 阻断规则和警告规则区分正确
- [ ] 不合格股票 100% 被拦截
- [ ] 正常股票不会误拦截
- [ ] 10 个单元测试全部通过
