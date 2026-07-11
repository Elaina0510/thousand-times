# DataSourceUnifier — 多数据源值域统一

> 模块：`data_quality/unifier.py`
> 层级：Layer 1 — 数据质量层
> 详细设计：[2.1.2](../detailed-design2.md#212-datasourceunifier--data_qualityunifierpy)

## 概述

统一 AKShare 和 BaoStock 双数据源的值域，确保 ROE/EPS/增长率等关键指标在相同尺度上比较和评分。

## 依赖

- **上游**：`DataValidator` → `DataQualityReport`, `fundamental_analysis.py` → 原始数据
- **下游**：`pipeline/factors.py` 中的基本面因子计算

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/data_quality/unifier.py` 骨架
- [ ] **1.2** 创建 `tests/test_data_source_unifier.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `DataSource` 枚举（AKSHARE / BAOSTOCK / UNKNOWN）
- [ ] **2.2** 实现 `NormalizedFundamental` dataclass（统一尺度后的数据）
- [ ] **2.3** 实现 `UnificationReport` dataclass（处理报告）

### 3. 核心统一函数

- [ ] **3.1** 实现 `unify_fundamental_data(akshare_results, baostock_results, quality_report) -> (dict, UnificationReport)`
  - 输入：AKShare 原始数据、BaoStock 原始数据、质量报告
  - 输出：(标准化数据映射, 处理报告)
  - ROI 统一：AKShare 返回百分数直接使用，BaoStock 小数×100
  - EPS 统一：两源都返回元/股，直接使用
  - 增长率统一：AKShare 直用，BaoStock ×100
  - 优先使用 AKShare 数据
- [ ] **3.2** 实现 `_normalize_akshare_row(row) -> NormalizedFundamental`
  - 提取 AKShare stock_yjbb_em 行的数据
  - 映射到统一字段名和值域
- [ ] **3.3** 实现 `_normalize_baostock_row(row) -> NormalizedFundamental`
  - 提取 BaoStock query_profit_data 行的数据
  - roeAvg × 100, YOYNI/YOYPNI × 100
  - 映射到统一字段名和值域
- [ ] **3.4** 实现冲突检测逻辑
  - 当 AKShare 和 BaoStock 对同一股票有数据且差异 > 30% 时
  - 记录到 UnificationReport.conflicts
  - 优先使用最近财报期数据

### 4. 辅助函数

- [ ] **4.1** 实现 `validate_value_range(data: NormalizedFundamental) -> list[str]`
  - ROE: [-100, 100]
  - EPS: [-100, 1000]
  - profit_growth: [-500, 500]
  - debt_ratio: [0, 200]
  - gross_margin: [-50, 100]
  - 越界值记录异常但不丢弃
- [ ] **4.2** 实现 `get_preferred_source(code, akshare_avail, baostock_avail) -> DataSource`
  - AKShare > BaoStock > 空数据
- [ ] **4.3** 实现 `get_data_period(row) -> str`
  - 从原始数据中提取财报期（如 "2026Q1"）

### 5. 测试

- [ ] **5.1** 测试 AKShare 数据转换：roe=15.5 → NormalizedFundamental.roe=15.5
- [ ] **5.2** 测试 BaoStock 数据转换：roeAvg=0.155 → NormalizedFundamental.roe=15.5
- [ ] **5.3** 测试两源数据一致时无冲突
- [ ] **5.4** 测试两源数据差异 > 30% 时记录冲突
- [ ] **5.5** 测试 AKShare 优先逻辑
- [ ] **5.6** 测试值域校验：roe=15000 → 返回异常
- [ ] **5.7** 测试全空回退：两源无数据 → fallback_count+=1
- [ ] **5.8** 测试 BaoStock 增长率为小数：YOYNI=0.25 → profit_growth=25.0
- [ ] **5.9** 测试混合数据源（部分 AKShare，部分 BaoStock）
- [ ] **5.10** 运行 `pytest tests/test_data_source_unifier.py -v` 全部通过

---

## 验收标准

- [ ] ROE 统一后与同花顺/东方财富公示值偏差 < 10%
- [ ] 冲突检测正确率 > 95%
- [ ] 值域异常检出率 100%（所有越界值都被标记）
- [ ] 10 个单元测试全部通过
