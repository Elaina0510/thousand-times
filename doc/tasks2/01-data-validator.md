# DataValidator — 数据完整性校验

> 模块：`data_quality/validator.py`
> 层级：Layer 1 — 数据质量层
> 详细设计：[2.1.1](../detailed-design2.md#211-datavalidator--data_qualityvalidatorpy)

## 概述

校验 DataBundle 中各类数据的完整性和合理性，产出质量报告，标记异常数据供下游降级处理。

## 依赖

- **上游**：`pipeline/collect.py` → `DataBundle`
- **下游**：`DataSourceUnifier`, `UnifiedPipeline`

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/data_quality/__init__.py`
- [ ] **1.2** 创建 `src/data_quality/validator.py` 骨架（dataclass + 函数签名）
- [ ] **1.3** 创建 `tests/test_data_validator.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `QualityLevel` 枚举（GOOD / DEGRADED / BAD）
- [ ] **2.2** 实现 `FieldQuality` dataclass
- [ ] **2.3** 实现 `DataQualityReport` dataclass

### 3. 核心校验函数

- [ ] **3.1** 实现 `validate_bundle(data: DataBundle) -> DataQualityReport`
  - 输入：DataBundle 数据包
  - 输出：完整质量报告
  - 调用所有子校验函数
- [ ] **3.2** 实现 `_validate_kline(kline_cache) -> dict[str, FieldQuality]`
  - 检查每只股票 K线行数 ≥ 20
  - 检查空数据比例 < 30%
  - 检查列完整性（必须有"收盘"或"close"列）
- [ ] **3.3** 实现 `_validate_fundamental(fundamental_cache) -> dict[str, FieldQuality]`
  - 检测 roe==0.0 比例
  - 检测 eps==0.0 比例
  - 检测 profit_growth/revenue_growth 为 None 比例
  - 检测 debt_ratio/cash_flow/gross_margin 缺失比例
- [ ] **3.4** 实现 `_validate_capital_flow(north_flow, sector_flow) -> FieldQuality`
  - 检查北向资金 DataFrame 是否为空
  - 检查行业资金流向是否为空
- [ ] **3.5** 实现 `_validate_sentiment(limit_up, limit_down, ad_ratio) -> FieldQuality`
  - 检查涨跌停数据是否合理（非负、非异常大）
  - 检查涨跌比是否为默认值 1.0

### 4. 辅助函数

- [ ] **4.1** 实现 `detect_default_values(series, suspicious_values={60.0, 50.0, 0.0}) -> int`
  - 统计值在可疑集合中出现的次数
  - 如果某值出现比例 > 30%，标记为疑似默认值
- [ ] **4.2** 实现 `flag_anomalous_stocks(report) -> list[str]`
  - 汇总所有 BAD 等级的股票代码
  - 供下游跳过或降级处理

### 5. 测试

- [ ] **5.1** 测试全部数据正常场景 → overall_level=GOOD
- [ ] **5.2** 测试 K线数据不足场景（< 20行）→ BAD
- [ ] **5.3** 测试 K线缺少收盘列场景 → BAD
- [ ] **5.4** 测试基本面全为默认值场景（roe 全为 0.0）→ BAD
- [ ] **5.5** 测试资金面全为 60 场景 → BAD
- [ ] **5.6** 测试混合异常场景 → 正确分类各数据集等级
- [ ] **5.7** 测试 detect_default_values → 正确计数
- [ ] **5.8** 测试 flag_anomalous_stocks → 正确返回异常股票列表
- [ ] **5.9** 测试空 DataBundle 场景 → 不崩溃
- [ ] **5.10** 运行 `pytest tests/test_data_validator.py -v` 全部通过

---

## 验收标准

- [ ] DataQualityReport 正确分类每个数据集的 GOOD / DEGRADED / BAD
- [ ] 默认值检测准确率 > 90%（与人工标注对比）
- [ ] 10 个单元测试全部通过
- [ ] 对下游无副作用（纯读操作，不修改 DataBundle）
