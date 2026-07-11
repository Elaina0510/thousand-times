# PositionSizer — 仓位计算与组合优化

> 模块：`risk/position.py`
> 层级：Layer 4 — 风控执行层
> 详细设计：[2.4.1](../detailed-design2.md#241-positionsizer--riskpositionpy)

## 概述

根据信号置信度、波动率和组合约束，为每个买入信号计算建议仓位大小（Kelly 启发式 + 波动率调整）。

## 依赖

- **上游**：`Signal[]` (buy), `MarketRegime`, `DataBundle.kline_cache`
- **下游**：`UnifiedPipeline`, `PaperTrader`

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/risk/__init__.py`
- [ ] **1.2** 创建 `src/risk/position.py` 骨架
- [ ] **1.3** 创建 `tests/test_position_sizer.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `PositionAllocation` dataclass
  - code, name, signal_confidence, volatility_pct
  - base_weight, adjusted_weight, shares, capital, max_loss, reason
- [ ] **2.2** 实现 `PortfolioSummary` dataclass
  - total_capital, allocated_capital, cash_reserve
  - position_count, sector_exposure, risk_contribution, warnings

### 3. 仓位分配算法

- [ ] **3.1** 实现 `assign_positions(buy_signals, stock_pool, total_capital, regime, kline_cache, config) -> (list, PortfolioSummary)`
  - Step1: 基础权重 = confidence_i / sum(confidence)
  - Step2: 波动率惩罚 = median_vol / vol_i
  - Step3: 市场环境乘数（bull=1.2, sideways=0.8, bear=0.4）
  - Step4: 硬上限裁剪
  - Step5: 换算为 100 股整数倍
- [ ] **3.2** 实现 `calc_volatility(kline, annualize=True) -> float`
  - 基于日收益率标准差 × sqrt(252) 计算年化波动率
  - 至少需要 20 天数据
- [ ] **3.3** 实现 `_apply_limits(weights, allocations, config) -> list[PositionAllocation]`
  - 单只 ≤ 10%
  - 单行业 ≤ 20%
  - 总仓位：bull≤80%, sideways≤60%, bear≤30%

### 4. 风控检查

- [ ] **4.1** 实现 `check_sector_limits(allocations, industry_map, max_sector_pct=0.20) -> list[str]`
  - 按行业汇总暴露度
  - 超限行业返回警告
- [ ] **4.2** 实现 `_calc_risk_contribution(allocations, kline_cache) -> dict[str, float]`
  - 近似计算每只股票对组合风险的贡献
  - 基于波动率和仓位加权

### 5. 测试

- [ ] **5.1** 测试正常场景：5 个信号, 牛市, 10 万资金 → 总仓位 ≤ 80000
- [ ] **5.2** 测试单只超 10% → 裁剪到 10%
- [ ] **5.3** 测试同行业 3 只 → 行业总计 ≤ 20%
- [ ] **5.4** 测试高波动惩罚：vol = 2× 中位数 → 权重降低 ~50%
- [ ] **5.5** 测试熊市限制：bear → 总仓位 ≤ 30%
- [ ] **5.6** 测试零信号 → position_count=0
- [ ] **5.7** 测试 100 股整数倍取整
- [ ] **5.8** 测试现金预留（不超总资金）
- [ ] **5.9** 测试波动率计算：验证年化公式
- [ ] **5.10** 测试空 kline_cache → 波动率使用默认值

---

## 验收标准

- [ ] 所有硬上限不被突破（单只 10%、单行业 20%、总仓位按环境）
- [ ] 高波动股票确实被低配
- [ ] 100 股整数倍取整正确（A 股 1 手 = 100 股）
- [ ] 10 个单元测试全部通过
