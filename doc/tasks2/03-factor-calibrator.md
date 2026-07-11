# FactorCalibrator — 百分位评分校准

> 模块：`factors/calibrator.py`
> 层级：Layer 2 — 因子评分层
> 详细设计：[2.2.1](../detailed-design2.md#221-factorcalibrator--factorscalibratorpy)

## 概述

解决评分压缩问题。通过百分位排名标准化和分布拉伸，将评分分布从 32.5~70.3 (σ≈8) 扩展到 ~5~95 (σ≈20)。

## 依赖

- **上游**：`pipeline/factors.py::calc_factors()` → `FactorScores[]`
- **下游**：`pipeline/signal.py::generate_signals()` (AdaptiveVoter)

---

## 任务清单

### 1. 基础设施

- [ ] **1.1** 创建 `src/factors/calibrator.py` 骨架
- [ ] **1.2** 创建 `tests/test_factor_calibrator.py` 骨架

### 2. 数据结构

- [ ] **2.1** 实现 `CalibratedScores` dataclass
  - 含 raw（原始分）、pct（百分位）、calibrated（校准后）三组字段
  - 含 total_pct、rank_percentile
- [ ] **2.2** 实现 `CalibrationParams` dataclass
  - pct_weight=0.5, target_mean=50.0, target_std=20.0, tail_expand=1.5

### 3. 核心校准函数

- [ ] **3.1** 实现 `calibrate_scores(raw_scores, params=None) -> list[CalibratedScores]`
  - Step1: 对每个因子计算百分位排名
  - Step2: 百分位与原始评分加权混合：`final = raw*(1-w) + pct*100*w`
  - Step3: Z-score 标准化拉伸到 target_mean/target_std
  - Step4: 截断到 [0, 100]
  - Step5: 按 total 降序重排
  - 返回校准后的列表
- [ ] **3.2** 实现 `calc_percentile_rank(value, all_values) -> float`
  - 输入：目标值和全体值列表
  - 输出：百分位排名 0-100（100=最高）
- [ ] **3.3** 实现 `stretch_distribution(values, target_mean, target_std) -> list[float]`
  - Z = (x - μ) / σ
  - stretched = target_mean + Z * target_std
  - 截断到 [0, 100]
- [ ] **3.4** 实现 `_calibrate_single_factor(raw_list, pct_weight) -> list[float]`
  - 对单个因子（如 technical）执行 Step2-4

### 4. 参数优化

- [ ] **4.1** 实现 `optimize_calibration_params(backtest_results, param_grid) -> CalibrationParams`
  - 网格搜索最优 pct_weight 和 target_std
  - 目标：最大化回测夏普比率
  - 注意防止过拟合（保留样本外验证集）

### 5. 测试

- [ ] **5.1** 测试集中分布：100个评分集中在 [40,60] → 校准后范围 ≥ [10,90]
- [ ] **5.2** 测试极端分布：全为50分 → 校准后标准差 ≈ 0（无法区分）
- [ ] **5.3** 测试均匀分布：均匀在 [0,100] → 校准后与原始基本一致
- [ ] **5.4** 测试异常值：含 >100 或 <0 → 截断不报错
- [ ] **5.5** 测试百分位计算：最高值 → pct_rank=100
- [ ] **5.6** 测试空列表：raw_scores=[] → 返回 []
- [ ] **5.7** 测试分布拉伸：验证目标均值=50 和 目标标准差=20
- [ ] **5.8** 测试单因子校准函数
- [ ] **5.9** 测试参数优化（使用模拟回测数据）
- [ ] **5.10** 运行 `pytest tests/test_factor_calibrator.py -v` 全部通过

---

## 验收标准

- [ ] 校准后评分标准差 ≥ 15（从当前 ~8 提升）
- [ ] 评分范围覆盖 [5, 95]
- [ ] 排序一致性：校准前后的排名相关系数 > 0.8（不破坏相对次序）
- [ ] 10 个单元测试全部通过
