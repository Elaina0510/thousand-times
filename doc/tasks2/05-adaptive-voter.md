# AdaptiveVoter — 自适应投票信号生成

> 模块：`pipeline/signal.py` (改造)
> 层级：Layer 3 — 信号生成层
> 详细设计：[2.3.1](../detailed-design2.md#231-adaptivevoter--pipelinesignalpy-改造)

## 概述

改造现有的 5 票投票制，将硬编码的固定阈值替换为市场环境自适应的动态阈值，解决当前"全部观望"问题。

## 依赖

- **上游**：`MarketRegime.state`, `CalibratedScores[]`
- **下游**：`RiskGuard`, `PositionSizer`

---

## 任务清单

### 1. 数据结构

- [ ] **1.1** 实现 `AdaptiveThresholds` dataclass
  - min_buy_votes, min_sell_votes, max_oppose_votes
  - factor_buy, factor_sell, technical_buy, technical_sell
  - min_risk_reward
  - `@staticmethod for_regime(state: str) -> AdaptiveThresholds`
    - bull: buy=2, sell=4, factor_buy=65, rr=1.5
    - bear: buy=4, sell=2, factor_buy=80, rr=2.5
    - sideways: buy=2, sell=2, factor_buy=70, rr=2.0
- [ ] **1.2** 确认现有 `SignalVote`, `Signal`, `KeyPrices` dataclass 无需改动

### 2. 自适应投票决策

- [ ] **2.1** 实现 `_decide_action_adaptive(votes, thresholds, risk_reward) -> (action, confidence, detail)`
  - 替代现有 `_decide_action()` 函数
  - 买入：buy_votes ≥ min_buy 且 sell_votes ≤ max_oppose 且 rr ≥ min_rr
  - 卖出：sell_votes ≥ min_sell 且 buy_votes ≤ max_oppose
  - 观望细分：接近买入(2票)、接近卖出(2票)、信号混合
  - 返回详细原因字符串而非简单"观望"
- [ ] **2.2** 改造 `_vote_factor(fs, config) -> SignalVote`
  - 使用 AdaptiveThresholds 中的 factor_buy/factor_sell
- [ ] **2.3** 改造 `_vote_technical(fs, config) -> SignalVote`
  - 使用 AdaptiveThresholds 中的 technical_buy/technical_sell
- [ ] **2.4** 改造 `generate_signals(factors, data, config, regime_state) -> list[Signal]`
  - 调用 `AdaptiveThresholds.for_regime(regime_state)` 获取阈值
  - 传入 `_decide_action_adaptive`
  - 盈亏比过滤使用自适应 min_risk_reward

### 3. 向后兼容

- [ ] **3.1** 保留原有 `_decide_action()` 函数，标记 deprecated
- [ ] **3.2** 保留原有 `SignalConfig` 中的固定阈值字段（V1 回退用）
- [ ] **3.3** 在 `SignalConfig` 中新增 `thresholds: dict[str, AdaptiveThresholds]` 字段

### 4. 测试

- [ ] **4.1** 牛市 2 票 buy + 0 票 sell → buy
- [ ] **4.2** 熊市 2 票 buy + 0 票 sell → hold (不满足 4 票)
- [ ] **4.3** 震荡市 2 票 buy + 0 票 sell → buy
- [ ] **4.4** 盈亏比不足（buy=3, rr=1.0, bull）→ hold
- [ ] **4.5** 有 2 票反对（buy=3, sell=2）→ hold
- [ ] **4.6** 全中立（buy=0, sell=0）→ hold + 信号混合
- [ ] **4.7** 接近买入（buy=2, sell=0）→ hold + "接近买入"
- [ ] **4.8** 接近卖出（buy=0, sell=2）→ hold + "接近卖出"
- [ ] **4.9** 对比改造前后：同一批数据 → 改造后 hold 比例下降
- [ ] **4.10** 运行 `pytest tests/test_pipeline_signal.py -v` 全部通过

---

## 验收标准

- [ ] buy/sell 信号合计占总信号 < 40%（不再是 100% hold）
- [ ] 在历史报告数据上验证：至少出现 buy 和 sell 信号
- [ ] 三种市场环境的阈值切换正确
- [ ] 向后兼容：V1 回退路径仍可用
- [ ] 10 个单元测试全部通过
