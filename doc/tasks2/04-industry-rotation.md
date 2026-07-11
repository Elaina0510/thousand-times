# IndustryRotationAnalyzer — 行业轮动分析

> 模块：`factors/industry_rotation.py`
> 层级：Layer 2 — 因子评分层
> 详细设计：[2.2.2](../detailed-design2.md#222-industryrotationanalyzer--factorsindustry_rotationpy)

## 概述

分析行业板块间的强弱关系，识别轮动方向，为因子评分提供行业维度的 alpha 调整。

## 依赖

- **上游**：`DataBundle.etf_kline_cache`, `DataBundle.sector_flow`, `DataBundle.stock_pool`
- **下游**：`FactorCalibrator`（评分调整注入）, `UnifiedPipeline`

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/factors/industry_rotation.py` 骨架
- [ ] **1.2** 创建 `tests/test_industry_rotation.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `IndustryMomentum` dataclass（行业动量数据）
- [ ] **2.2** 实现 `RotationSignal` dataclass（轮动信号）
- [ ] **2.3** 实现 `IndustryScoreAdjustment` dataclass（评分调整量）

### 3. 行业动量计算

- [ ] **3.1** 实现 `analyze_industry_rotation(etf_kline_cache, sector_flow, industry_stocks, lookback_days=60) -> (list, RotationSignal)`
  - 对每个行业 ETF：计算 1/5/20/60 日收益率
  - 按 20 日收益率排名
  - 识别领涨/领跌行业
  - 识别转向行业（5日 vs 20日排名变化 ≥ 5名）
- [ ] **3.2** 实现 `_calc_industry_returns(etf_kline, days_list) -> dict`
  - 返回各周期的收益率
- [ ] **3.3** 实现 `_calc_trend_strength(etf_kline) -> (float, str)`
  - MA 均线排列判断趋势方向和强度
  - 多头排列 → up / strength=80-100
  - 空头排列 → down / strength=80-100
  - 纠缠 → sideways / strength=30-70

### 4. 评分调整

- [ ] **4.1** 实现 `calc_industry_adjustments(stock_pool, momentum_list) -> list[IndustryScoreAdjustment]`
  - 前 10% 行业：+5 ~ +10 分
  - 前 10-30% 行业：+2 ~ +5 分
  - 后 30% 行业：0 ~ -5 分
  - 资金持续流入+动量向上：额外 +2
  - 资金持续流出+动量向下：额外 -2
- [ ] **4.2** 实现 `_map_stock_to_industry(stock_pool, industry_stocks) -> dict`
  - 构建 code → industry_name 映射
  - 利用现有的 INDUSTRY_ETF_MAP 和行业关键词匹配

### 5. 轮动模式识别

- [ ] **5.1** 实现 `detect_rotation_pattern(momentum_history) -> str`
  - growth_rotation: 科技、半导体从低排名快速上升
  - defensive_rotation: 消费、医药排名上升而周期下降
  - cyclical_rotation: 金融、地产、有色排名上升
  - broad_up: 80% 行业 20 日收益 > 0
  - broad_down: 80% 行业 20 日收益 < 0
  - no_pattern: 其他

### 6. 扩展映射表

- [ ] **6.1** 在 `EXTENDED_INDUSTRY_ETF_MAP` 中新增 11 个申万一级行业 → ETF 映射
  - 农林牧渔→159825, 有色金属→512400, 钢铁→515210, 化工→516020
  - 汽车→516110, 家电→159996, 纺织→159840, 公用事业→159611
  - 交运→159662, 传媒→512980, 环保→516650, 社会服务→159766

### 7. 测试

- [ ] **7.1** 测试明显的成长轮动模式
- [ ] **7.2** 测试普涨模式
- [ ] **7.3** 测试行业转向检测（排名变化 ≥ 5）
- [ ] **7.4** 测试评分调整：领涨行业 → adjustment > +5
- [ ] **7.5** 测试无 ETF 匹配行业 → 返回市场平均
- [ ] **7.6** 测试空 ETF 缓存 → 不崩溃
- [ ] **7.7** 测试评分调整边界（不越界）
- [ ] **7.8** 运行 `pytest tests/test_industry_rotation.py -v` 全部通过

---

## 验收标准

- [ ] 轮动模式识别正确率 > 80%（与手动标注对比5个交易日）
- [ ] 评分调整在 [-10, +10] 范围内
- [ ] 行业映射覆盖所有申万一级行业（31个）
- [ ] 8 个单元测试全部通过
