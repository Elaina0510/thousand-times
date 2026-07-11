# A股智能选股系统 V3 — 详细设计文档

> 版本：v3.0
> 日期：2026-07-11
> 状态：待评审
> 依据：系统可行性评估（2026-07-10 分析报告），覆盖全部10项改进

---

## 一、设计概述

### 1.1 设计目标

基于对 V1/V2 系统的全面评估（[doc/report/24.txt](doc/report/24.txt)），本设计针对以下核心问题提出解决方案：

| 问题编号 | 问题 | 严重程度 | 对应模块 |
|----------|------|:--------:|----------|
| #1 | 基本面数据管道值域不统一、大量默认值填充 | 🔴 致命 | 数据质量层 |
| #2 | 评分压缩严重（32.5~70.3），无法区分优劣 | 🔴 致命 | 因子评分层 |
| #3 | 信号投票门槛过高，全部输出"观望" | 🔴 致命 | 信号生成层 |
| #4 | 信号追踪数据库只写不读，无反馈回路 | 🔴 致命 | 反馈验证层 |
| #5 | 无仓位管理和组合优化 | 🟡 重要 | 风控执行层 |
| #6 | 有止损价但无后续跟踪 | 🟡 重要 | 风控执行层 |
| #7 | 回测框架未产生验证结果 | 🟡 重要 | 反馈验证层 |
| #8 | 缺乏行业轮动和择时能力 | 🟢 增强 | 因子评分层 |
| #9 | 无硬性风控规则 | 🟢 增强 | 风控执行层 |
| #10 | V1/V2 双管道并存，因子逻辑不一致 | 🟢 增强 | 信号生成层 |

### 1.2 设计策略

- **部分重写**：废弃 V1 管道，以 V2 管道（`pipeline/` 目录下 5 阶段）为基础进行改造
- **分层架构**：按功能域分为 5 层，层间通过明确定义的接口通信
- **独立可测**：每个模块可独立编写单元测试，外部依赖通过接口注入

### 1.3 模块总览

```
┌─────────────────────────────────────────────────────────────┐
│                      统一管道入口                             │
│                 pipeline/unified.py                         │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│ 数据质量层 │    │  因子评分层   │    │  信号生成层   │
│ (Layer 1) │    │  (Layer 2)   │    │  (Layer 3)   │
│           │    │              │    │              │
│ Validator │    │ Calibrator   │    │ AdaptiveVoter│
│ Unifier   │    │ IndRotation  │    │ UnifiedPipe  │
└─────┬─────┘    └──────┬───────┘    └──────┬───────┘
      │                 │                   │
      └─────────┬───────┴───────────────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ 风控执行层 │ │ 反馈验证层 │ │  输出层(现有) │
│ (Layer 4) │ │ (Layer 5) │ │              │
│           │ │           │ │ report_gen   │
│ Position  │ │ Tracker   │ │ push_service │
│ StopLoss  │ │ Backtest  │ │ chart_gen    │
│ Guard     │ │ PaperTrade│ │              │
└──────────┘ └──────────┘ └──────────────┘
```

| 层级 | 模块 | 文件 | 职责 | 可独立测试 |
|------|------|------|------|:----------:|
| 数据质量 | DataValidator | `data_quality/validator.py` | 数据完整性校验与异常检测 | ✅ |
| 数据质量 | DataSourceUnifier | `data_quality/unifier.py` | 多数据源值域统一与标准化 | ✅ |
| 因子评分 | FactorCalibrator | `factors/calibrator.py` | 百分位评分校准，增大区分度 | ✅ |
| 因子评分 | IndustryRotation | `factors/industry_rotation.py` | 行业轮动与板块强弱分析 | ✅ |
| 信号生成 | AdaptiveVoter | `pipeline/signal.py` (改造) | 市场环境自适应投票阈值 | ✅ |
| 信号生成 | UnifiedPipeline | `pipeline/unified.py` | 统一管道入口，废弃V1 | 集成测试 |
| 风控执行 | PositionSizer | `risk/position.py` | 仓位计算与组合优化 | ✅ |
| 风控执行 | StopLossTracker | `risk/stop_loss.py` | 止损跟踪与触发推送 | ✅ |
| 风控执行 | RiskGuard | `risk/guard.py` | 硬性风控规则引擎 | ✅ |
| 反馈验证 | SignalTracker | `feedback/tracker.py` | 信号→收益闭环追踪 | ✅ |
| 反馈验证 | BacktestValidator | `feedback/backtest_validator.py` | 完整回测与显著性检验 | ✅ |
| 反馈验证 | PaperTrader | `feedback/paper_trader.py` | 模拟交易（纸交易） | ✅ |

### 1.4 与现有 V2 管道的集成

```
现有V2管道:  collect → regime → factors → signal → output
                 │        │         │         │        │
新增注入点:   Validator   │    Calibrator  Adaptive  │
              Unifier     │    IndRotation  Voter    │
                          │                    │     │
                          │              RiskGuard   │
                          │              Position    │
                          │              StopLoss    │
                          │                    │     │
                          └── Tracker ←───────┘     │
                               Backtest             │
                               PaperTrade           │
```

---

## 二、模块详细设计

---

### 2.1 数据质量层 — Layer 1

#### 2.1.1 DataValidator — `data_quality/validator.py`

##### 2.1.1.1 职责

校验 DataBundle 中各类数据的完整性和合理性，产出数据质量报告，标记异常数据供下游模块降级处理。

##### 2.1.1.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class QualityLevel(Enum):
    """数据质量等级"""
    GOOD = "good"           # 数据完整可用
    DEGRADED = "degraded"   # 部分缺失，可降级使用
    BAD = "bad"             # 严重缺失，建议跳过


@dataclass
class FieldQuality:
    """单个字段的质量报告"""
    field_name: str
    level: QualityLevel
    valid_count: int        # 有效值数量
    total_count: int        # 总数
    default_count: int      # 疑似默认值的数量
    mean_value: float | None
    std_value: float | None
    anomalies: list[str]    # 异常描述列表


@dataclass
class DataQualityReport:
    """完整数据质量报告"""
    timestamp: str
    # 各数据集质量
    kline_quality: dict[str, FieldQuality]   # code → quality
    fundamental_quality: dict[str, FieldQuality]
    capital_flow_quality: FieldQuality | None
    sentiment_quality: FieldQuality | None
    # 汇总
    overall_level: QualityLevel
    recommendation: str     # 对下游管道的建议
    details: list[str]      # 详细问题列表
```

##### 2.1.1.3 接口定义

```python
def validate_bundle(data: DataBundle) -> DataQualityReport:
    """
    对 DataBundle 进行完整性校验。

    校验内容：
    1. K线数据：检查每只股票的K线行数、是否存在全空、列是否齐全
    2. 基本面数据：检查 ROE/EPS/增长率是否使用了默认值（精确匹配）
    3. 资金面数据：检查北向资金、行业资金流向是否为空
    4. 情绪数据：检查涨跌停数据是否合理（非负，非异常大）

    Args:
        data: 统一数据包。

    Returns:
        DataQualityReport 质量报告。
    """

def detect_default_values(series: list[float], suspicious_values: set[float] = {60.0, 50.0, 0.0}) -> int:
    """
    检测疑似默认值填充。
    当某个值在数据集中出现比例过高（>30%），标记为疑似默认值。

    Args:
        series: 数值序列。
        suspicious_values: 预定义的疑似默认值集合。

    Returns:
        疑似默认值的数量。
    """

def flag_anomalous_stocks(report: DataQualityReport) -> list[str]:
    """
    返回应被跳过或降级处理的股票代码列表。

    Args:
        report: 质量报告。

    Returns:
        股票代码列表。
    """
```

##### 2.1.1.4 校验规则

| 数据集 | 校验项 | 条件 | 等级 |
|--------|--------|------|:----:|
| K线 | 最少行数 | < 20行 | BAD |
| K线 | 空数据比例 | > 30% 为空 | DEGRADED |
| K线 | 列完整性 | 缺少"收盘"或"close" | BAD |
| 基本面 | ROE默认值 | roe==0.0 比例 > 50% | BAD |
| 基本面 | EPS默认值 | eps==0.0 比例 > 50% | BAD |
| 基本面 | 增长率默认值 | profit_growth==None 比例 > 70% | DEGRADED |
| 资金面 | 空DataFrame | north_flow为空 | DEGRADED |
| 资金面 | 资金流默认值 | capital_score==60 比例 > 80% | BAD |
| 情绪面 | 涨跌停比为0 | limit_up==0 且 limit_down==0 | DEGRADED |
| K线 | 数值异常 | 收盘价突变 > 50%/天 | DEGRADED |

##### 2.1.1.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 全部数据正常 | 完整DataBundle | overall_level=GOOD |
| 基本面全为默认值 | roe全为0.0的DataBundle | fundamental_quality level=BAD |
| K线数据不足 | <20行的K线DataBundle | kline_quality level=BAD |
| 资金流全为60 | capital全为60的DataBundle | capital_flow_quality level=BAD |
| 混合异常 | 部分异常 | 正确分类各数据集等级 |

---

#### 2.1.2 DataSourceUnifier — `data_quality/unifier.py`

##### 2.1.2.1 职责

统一 AKShare 和 BaoStock 双数据源的值域，确保 ROE/EPS/增长率等关键指标在相同尺度上进行比较和评分。

##### 2.1.2.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class DataSource(Enum):
    """数据来源"""
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    UNKNOWN = "unknown"


@dataclass
class NormalizedFundamental:
    """标准化后的基本面数据"""
    code: str
    source: DataSource

    # 以下所有值均使用统一尺度
    roe: float                # 百分比，如 15.0 表示 15%
    eps: float                # 元/股
    market_cap: float         # 亿元
    profit_growth: float | None  # 百分比
    revenue_growth: float | None # 百分比
    debt_ratio: float | None     # 百分比
    cash_flow: float | None      # 元/股
    gross_margin: float | None   # 百分比

    # 元数据
    data_period: str          # 数据所属财报期，如 "2026Q1"
    is_estimated: bool        # 是否为预估值（非正式财报）


@dataclass
class UnificationReport:
    """统一化处理报告"""
    total_stocks: int
    from_akshare: int
    from_baostock: int
    conflicts: list[dict]     # 两源数据冲突的记录
    corrections: list[dict]   # 修正的记录
    fallback_count: int       # 回退到空数据的数量
```

##### 2.1.2.3 接口定义

```python
def unify_fundamental_data(
    akshare_results: dict[str, dict],
    baostock_results: dict[str, dict],
    quality_report: DataQualityReport,
) -> tuple[dict[str, NormalizedFundamental], UnificationReport]:
    """
    统一 AKShare 和 BaoStock 的基本面数据。

    统一规则：
    1. ROE: 统一为百分比（如 15.0 表示 15%）
       - AKShare stock_yjbb_em 已返回百分比，直接使用
       - BaoStock query_profit_data 返回小数 (0.15)，乘以 100
    2. EPS: 统一为元/股，不做转换
    3. 增长率: 统一为百分比
       - AKShare 已是百分比，直接使用
       - BaoStock YOYNI/YOYPNI 返回小数，乘以 100
    4. 优先使用 AKShare 数据（HTTP 直接获取），BaoStock 作为补充
    5. 当两源数据差异 > 30% 时，记录冲突，优先使用最近财报期数据

    Args:
        akshare_results: AKShare 原始数据。
        baostock_results: BaoStock 原始数据。
        quality_report: 数据质量报告。

    Returns:
        (标准化数据, 处理报告)
    """

def validate_value_range(data: NormalizedFundamental) -> list[str]:
    """
    验证标准化后的数据是否在合理范围内。

    合理范围：
    - ROE: [-100%, 100%]
    - EPS: [-100, 1000] 元
    - profit_growth: [-500%, 500%]
    - debt_ratio: [0%, 200%]
    - gross_margin: [-50%, 100%]

    Args:
        data: 标准化基本面数据。

    Returns:
        异常描述列表，无异常为空。
    """

def get_preferred_source(
    code: str,
    akshare_available: bool,
    baostock_available: bool,
) -> DataSource:
    """
    确定首选数据源。
    AKShare > BaoStock > 空数据。

    Args:
        code: 股票代码。
        akshare_available: AKShare 是否有数据。
        baostock_available: BaoStock 是否有数据。

    Returns:
        首选数据源。
    """
```

##### 2.1.2.4 值域映射表

| 指标 | BaoStock 原始值域 | AKShare 原始值域 | 统一后值域 | 转换逻辑 |
|------|-------------------|------------------|------------|----------|
| ROE | 小数 (0.15=15%) | 百分数 (3.2=3.2%) | 百分数 (15.0=15%) | BS×100, AK直用 |
| EPS | 元/股 | 元/股 | 元/股 | 直用 |
| profit_growth | 小数 (0.25=25%) | 百分数 (25=25%) | 百分数 (25.0=25%) | BS×100, AK直用 |
| revenue_growth | 小数 (0.18=18%) | 百分数 (18=18%) | 百分数 (18.0=18%) | BS×100, AK直用 |
| gross_margin | 小数 (0.35=35%) | 百分数 (35=35%) | 百分数 (35.0=35%) | BS×100, AK直用 |
| debt_ratio | N/A (单接口) | N/A (yjbb不含) | 百分数 | 额外接口获取 |

##### 2.1.2.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| AKShare有数据 | akshare返回roe=15.5 | NormalizedFundamental.roe=15.5 |
| BaoStock有数据 | baostock返回roeAvg=0.155 | NormalizedFundamental.roe=15.5 |
| 两源都有且一致 | AK=15.5, BS=0.155 | roe=15.5, conflicts=0 |
| 两源冲突>30% | AK=15.5, BS=0.08 | roe=15.5, conflicts=1 |
| 值域异常 | roe=15000 | validate_value_range 返回异常 |
| 全空回退 | 两源都无数据 | fallback_count+=1, 返回空 |

---

### 2.2 因子评分层 — Layer 2

#### 2.2.1 FactorCalibrator — `factors/calibrator.py`

##### 2.2.1.1 职责

解决评分压缩问题。通过百分位排名标准化和分布拉伸，将评分分布从 32.5~70.3 扩展到更有区分度的范围。

##### 2.2.1.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CalibratedScores:
    """校准后的因子评分"""
    code: str
    name: str

    # 原始评分（0-100，由现有因子模块计算）
    technical_raw: float
    fundamental_raw: float
    capital_raw: float
    sentiment_raw: float
    momentum_raw: float

    # 百分位评分（在股票池中的相对位置，0-100）
    technical_pct: float
    fundamental_pct: float
    capital_pct: float
    sentiment_pct: float
    momentum_pct: float

    # 校准后评分（加权混合原始+百分位）
    technical: float
    fundamental: float
    capital: float
    sentiment: float
    momentum: float

    # 综合分
    total: float
    total_pct: float         # 在全部股票中的百分位

    # 子因子详情（透传）
    technical_detail: dict[str, float] = field(default_factory=dict)
    fundamental_detail: dict[str, float] = field(default_factory=dict)
    capital_detail: dict[str, float] = field(default_factory=dict)
    sentiment_detail: dict[str, float] = field(default_factory=dict)
    momentum_detail: dict[str, float] = field(default_factory=dict)


@dataclass
class CalibrationParams:
    """校准参数（可通过回测优化）"""
    # 百分位评分权重（0=纯绝对评分，1=纯百分位评分）
    pct_weight: float = 0.5

    # 分布拉伸参数
    target_mean: float = 50.0      # 目标均值
    target_std: float = 20.0       # 目标标准差（当前约8-10，太低）

    # 尾部扩展
    tail_expand: float = 1.5       # 尾部拉伸倍数
```

##### 2.2.1.3 接口定义

```python
def calibrate_scores(
    raw_scores: list[FactorScores],
    params: CalibrationParams | None = None,
) -> list[CalibratedScores]:
    """
    对原始因子评分进行校准。

    校准流程：
    1. 计算每个因子在股票池中的百分位排名
    2. 百分位评分与原始评分加权混合：final = raw * (1-pct_weight) + pct * 100 * pct_weight
    3. Z-score 标准化拉伸：拉伸后均值=target_mean，标准差=target_std
    4. 截断到 [0, 100]

    效果：
    - 校准前：均值 47.8, 范围 32.5-70.3, 标准差 ~8
    - 校准后：均值 50.0, 范围 ~5-95, 标准差 ~20

    Args:
        raw_scores: 原始 FactorScores 列表。
        params: 校准参数，为 None 时使用默认值。

    Returns:
        校准后的 CalibratedScores 列表，按 total 降序排列。
    """

def calc_percentile_rank(value: float, all_values: list[float]) -> float:
    """
    计算单个值在群体中的百分位排名。

    Args:
        value: 目标值。
        all_values: 所有值列表。

    Returns:
        百分位排名（0-100），100 = 最高。
    """

def stretch_distribution(values: list[float], target_mean: float, target_std: float) -> list[float]:
    """
    使用 Z-score 标准化 + 线性拉伸将分布调整到目标均值和标准差。

    算法：
    1. 计算原始均值和标准差
    2. Z = (x - mean_orig) / std_orig
    3. stretched = target_mean + Z * target_std
    4. 截断到 [0, 100]

    Args:
        values: 原始值列表。
        target_mean: 目标均值。
        target_std: 目标标准差。

    Returns:
        拉伸后的值列表。
    """

def optimize_calibration_params(
    backtest_results: list[dict],
    param_grid: dict[str, list[float]],
) -> CalibrationParams:
    """
    通过回测结果优化校准参数（网格搜索）。

    Args:
        backtest_results: 不同参数下的回测结果。
        param_grid: 参数网格。

    Returns:
        最优 CalibrationParams。
    """
```

##### 2.2.1.4 校准算法伪代码

```python
def calibrate_scores(raw_scores, params):
    n = len(raw_scores)

    # Step 1: 计算每只股票每个因子的百分位
    for factor in ['technical', 'fundamental', 'capital', 'sentiment', 'momentum']:
        all_vals = [getattr(s, factor) for s in raw_scores]
        for s in raw_scores:
            pct = calc_percentile_rank(getattr(s, factor), all_vals)
            setattr(s, f'{factor}_pct', pct)

    # Step 2: 百分位与原始评分加权混合
    for s in raw_scores:
        for factor in ['technical', 'fundamental', 'capital', 'sentiment', 'momentum']:
            raw = getattr(s, factor)
            pct = getattr(s, f'{factor}_pct')
            calibrated = raw * (1 - w) + pct * w
            setattr(s, factor, calibrated)

    # Step 3: 分布拉伸
    totals = [s.total for s in raw_scores]
    stretched = stretch_distribution(totals, target_mean, target_std)
    for s, new_total in zip(raw_scores, stretched):
        s.total = new_total

    # Step 4: 重新计算排序和百分位
    raw_scores.sort(key=lambda s: s.total, reverse=True)
    for i, s in enumerate(raw_scores):
        s.total_pct = (1 - i / n) * 100

    return raw_scores
```

##### 2.2.1.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 集中分布 | 100个评分集中在[40,60] | 校准后范围 >= [10,90] |
| 极端分布 | 全为50分 | 校准后标准差 ≈ 0（无法区分） |
| 均匀分布 | 均匀分布在[0,100] | 校准后与原始基本一致 |
| 异常值 | 含 >100 或 <0 的值 | 截断不报错 |
| 百分位计算 | 最高值为95 | percentile_rank = 100 |
| 空列表 | raw_scores=[] | 返回 [] |

---

#### 2.2.2 IndustryRotationAnalyzer — `factors/industry_rotation.py`

##### 2.2.2.1 职责

分析行业板块间的强弱关系，识别轮动方向，为因子评分和仓位分配提供行业维度的 alpha。

##### 2.2.2.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class IndustryMomentum:
    """单个行业的动量数据"""
    industry_name: str
    etf_code: str | None       # 对应的 ETF 代码
    stock_count: int           # 行业内股票数量

    # 各周期收益率（%）
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    ret_60d: float = 0.0

    # 排名（1=最强）
    rank_5d: int = 0
    rank_20d: int = 0

    # 趋势强度
    trend_strength: float = 0.0  # 0-100, 越高越强
    trend_direction: str = "sideways"  # "up", "down", "sideways"

    # 资金流向
    fund_flow_5d: float = 0.0   # 近5日资金净流入（亿元）


@dataclass
class RotationSignal:
    """轮动信号"""
    # 领涨行业（动量最强的前N个）
    leading_industries: list[str]
    # 转向行业（从弱转强的）
    turning_industries: list[str]
    # 衰减行业（从强转弱的）
    fading_industries: list[str]
    # 轮动方向描述
    description: str
    # 建议超配行业
    overweight: list[str]
    # 建议低配行业
    underweight: list[str]


@dataclass
class IndustryScoreAdjustment:
    """行业维度对个股评分的调整量"""
    code: str
    industry: str
    # 行业 alpha：行业动量在全体行业中的百分位 (0~1)
    industry_alpha: float
    # 调整量：加到总分上的分数 (-10 ~ +10)
    adjustment: float
    # 理由
    reason: str
```

##### 2.2.2.3 接口定义

```python
def analyze_industry_rotation(
    etf_kline_cache: dict[str, pd.DataFrame],
    sector_flow: pd.DataFrame,
    industry_stocks: dict[str, list[str]],
    lookback_days: int = 60,
) -> tuple[list[IndustryMomentum], RotationSignal]:
    """
    分析行业轮动。

    分析流程：
    1. 通过行业 ETF 的 K 线计算各周期收益率
    2. 按 20 日收益率排名，识别领涨/领跌行业
    3. 对比 5 日和 20 日排名变化，识别转向行业
    4. 结合行业资金流向，确认轮动方向
    5. 生成超配/低配建议

    Args:
        etf_kline_cache: 行业 ETF 的 K 线缓存。
        sector_flow: 行业资金流向数据。
        industry_stocks: 行业→股票代码列表映射。
        lookback_days: 回溯天数。

    Returns:
        (行业动量列表, 轮动信号)
    """

def calc_industry_adjustments(
    stock_pool: pd.DataFrame,
    momentum_list: list[IndustryMomentum],
) -> list[IndustryScoreAdjustment]:
    """
    为每只股票计算行业维度的评分调整。

    调整规则：
    - 行业 20 日动量排名前 10%：+5 ~ +10 分
    - 行业 20 日动量排名前 10%~30%：+2 ~ +5 分
    - 行业 20 日动量排名后 30%：0 ~ -5 分
    - 行业资金持续流入 + 动量向上：额外 +2 分
    - 行业资金持续流出 + 动量向下：额外 -2 分

    Args:
        stock_pool: 股票池。
        momentum_list: 行业动量列表。

    Returns:
        评分调整列表。
    """

def detect_rotation_pattern(
    momentum_history: list[dict[str, float]],
) -> str:
    """
    检测轮动模式。

    模式识别：
    - "growth_rotation": 从价值转向成长
    - "defensive_rotation": 从周期转向防御
    - "cyclical_rotation": 从防御转向周期
    - "broad_up": 普涨
    - "broad_down": 普跌
    - "no_pattern": 无明显模式

    Args:
        momentum_history: 各行业的历史动量数据（最近N天每天的排名）。

    Returns:
        轮动模式标识。
    """
```

##### 2.2.2.4 行业→ETF映射扩展

在现有的 `INDUSTRY_ETF_MAP` 基础上扩展：

```python
# scoring.py 中现有 28 个映射，扩展到覆盖全部申万一级行业（31个）
EXTENDED_INDUSTRY_ETF_MAP: dict[str, str] = {
    # 现有映射保持不变...

    # 新增映射
    "农林牧渔": "159825",   # 农业ETF
    "有色金属": "512400",   # 有色ETF
    "钢铁": "515210",       # 钢铁ETF
    "化工": "516020",       # 化工ETF
    "汽车": "516110",       # 汽车ETF
    "家用电器": "159996",   # 家电ETF
    "纺织服装": "159840",   # 纺织ETF (如有)
    "公用事业": "159611",   # 电力ETF 作为代理
    "交通运输": "159662",   # 交运ETF
    "传媒": "512980",       # 传媒ETF
    "环保": "516650",       # 环保ETF (如有)
    "社会服务": "159766",   # 旅游ETF 作为代理
}
```

##### 2.2.2.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 明显的成长轮动 | 半导体ETF领涨+消费ETF领跌 | pattern="growth_rotation" |
| 普涨行情 | 所有ETF 20日收益 > 0 | pattern="broad_up" |
| 行业转向 | 5日排名 vs 20日排名差异大 | turning_industries 非空 |
| 资金确认 | 动量+资金同时向上 | 该行业 adjustment > +5 |
| 无ETF行业 | 行业无对应ETF | 使用市场平均，不报错 |
| 空数据 | etf_kline_cache 为空 | 返回全中性，不崩溃 |

---

### 2.3 信号生成层 — Layer 3

#### 2.3.1 AdaptiveVoter — `pipeline/signal.py` (改造)

##### 2.3.1.1 职责

改造现有的 5 票投票制，实现**市场环境自适应的投票阈值**，解决当前"全部观望"的问题。

##### 2.3.1.2 核心改造：自适应阈值

```python
# 改造前：固定阈值（现有代码）
min_buy_votes: int = 3   # 所有市场环境统一要求3票
min_sell_votes: int = 3

# 改造后：自适应阈值（新设计）
@dataclass
class AdaptiveThresholds:
    """市场环境自适应的信号阈值"""
    # 投票数阈值
    min_buy_votes: int
    min_sell_votes: int
    max_oppose_votes: int   # 允许的最大反对票

    # 分数阈值
    factor_buy: float       # 综合因子买入阈值
    factor_sell: float
    technical_buy: float    # 技术因子买入阈值
    technical_sell: float

    # 盈亏比要求
    min_risk_reward: float

    @staticmethod
    def for_regime(state: str) -> AdaptiveThresholds:
        """根据市场环境返回对应阈值"""
        if state == "bull":
            return AdaptiveThresholds(
                min_buy_votes=2,         # 牛市中2票即可买入（更积极）
                min_sell_votes=4,        # 牛市中卖出需4票（更谨慎做空）
                max_oppose_votes=2,
                factor_buy=65.0,         # 牛市中降低买入门槛
                factor_sell=25.0,
                technical_buy=65.0,
                technical_sell=20.0,
                min_risk_reward=1.5,
            )
        elif state == "bear":
            return AdaptiveThresholds(
                min_buy_votes=4,         # 熊市中买入需4票（更谨慎）
                min_sell_votes=2,        # 熊市中2票即可卖出（更积极止损）
                max_oppose_votes=1,
                factor_buy=80.0,         # 熊市中提高买入门槛
                factor_sell=35.0,
                technical_buy=80.0,
                technical_sell=30.0,
                min_risk_reward=2.5,     # 要求更高盈亏比
            )
        else:  # sideways
            return AdaptiveThresholds(
                min_buy_votes=2,
                min_sell_votes=2,
                max_oppose_votes=1,
                factor_buy=70.0,
                factor_sell=30.0,
                technical_buy=75.0,
                technical_sell=25.0,
                min_risk_reward=2.0,
            )
```

##### 2.3.1.3 改造后的投票决策

```python
def _decide_action_adaptive(
    votes: list[SignalVote],
    thresholds: AdaptiveThresholds,
    risk_reward: float,
) -> tuple[str, float, str]:
    """
    自适应投票决策（替代现有的 _decide_action）。

    改造要点：
    1. 阈值不再硬编码，根据市场环境动态调整
    2. 增加 max_oppose_votes 约束（买入信号中不允许太多反对票）
    3. 盈亏比作为独立否决条件
    4. 返回详细理由而非简单的"观望"

    Args:
        votes: 5个SignalVote。
        thresholds: 当前市场环境的自适应阈值。
        risk_reward: 关键价位的盈亏比。

    Returns:
        (action: "buy"/"sell"/"hold",
         confidence: 0.0~1.0,
         detail: 决策理由)
    """
    buy_votes = sum(1 for v in votes if v.vote == "buy")
    sell_votes = sum(1 for v in votes if v.vote == "sell")
    neutral_votes = len(votes) - buy_votes - sell_votes

    # 买入决策
    if buy_votes >= thresholds.min_buy_votes and sell_votes <= thresholds.max_oppose_votes:
        if risk_reward < thresholds.min_risk_reward:
            return ("hold", 0.4, f"买入票数{buy_votes}满足但盈亏比{risk_reward:.1f}<{thresholds.min_risk_reward}")
        confidence = buy_votes / len(votes)
        return ("buy", confidence, f"买入({buy_votes}/{len(votes)}票), 盈亏比{risk_reward:.1f}")

    # 卖出决策
    if sell_votes >= thresholds.min_sell_votes and buy_votes <= thresholds.max_oppose_votes:
        confidence = sell_votes / len(votes)
        return ("sell", confidence, f"卖出({sell_votes}/{len(votes)}票)")

    # 观望 — 提供更有信息量的理由
    if buy_votes == 2:
        return ("hold", 0.45, f"接近买入(buy={buy_votes}, sell={sell_votes})，等待确认")
    elif sell_votes == 2:
        return ("hold", 0.45, f"接近卖出(buy={buy_votes}, sell={sell_votes})，关注风险")
    else:
        return ("hold", 0.5, f"信号混合(buy={buy_votes}, sell={sell_votes}, neutral={neutral_votes})")
```

##### 2.3.1.4 测试策略

| 测试场景 | 市场环境 | 投票结果 | 期望输出 |
|----------|----------|----------|----------|
| 牛市2票buy | bull | buy=2,sell=0 | buy, confidence=0.4 |
| 震荡2票buy | sideways | buy=2,sell=0 | buy, confidence=0.4 |
| 熊市2票buy | bear | buy=2,sell=0 | hold (不满足4票) |
| 盈亏比不足 | bull | buy=3,sell=0, rr=1.0 | hold (rr否决) |
| 有反对票 | sideways | buy=3,sell=2 | hold (反对票>1) |
| 全中立 | any | buy=0,sell=0 | hold, 信号混合 |

---

#### 2.3.2 UnifiedPipeline — `pipeline/unified.py`

##### 2.3.2.1 职责

废弃 V1 管道（`main.py` 中的 `main()` 函数），以 V2 五阶段管道为基础，注入全部新模块，形成唯一的执行入口。

##### 2.3.2.2 统一管道流程

```
UnifiedPipeline.run()
│
├── 阶段1: 数据采集 (collect)
│   └── pipeline/collect.py::stage_collect() → DataBundle
│
├── 阶段1.5: 数据质量 (NEW)
│   ├── data_quality/validator.py::validate_bundle() → DataQualityReport
│   └── data_quality/unifier.py::unify_fundamental_data() → NormalizedFundamental[]
│
├── 阶段2: 市场环境 (regime)
│   └── pipeline/regime.py::judge_market_regime() → MarketRegime
│
├── 阶段3: 因子计算 (factors)
│   ├── pipeline/factors.py::calc_factors() → FactorScores[] (raw)
│   ├── factors/calibrator.py::calibrate_scores() → CalibratedScores[] (NEW)
│   └── factors/industry_rotation.py::calc_industry_adjustments() → adjustments[] (NEW)
│
├── 阶段4: 信号生成 (signal)
│   ├── pipeline/signal.py::generate_signals() [使用 AdaptiveVoter 改造版]
│   ├── risk/guard.py::apply_risk_rules() → filtered_signals (NEW)
│   ├── risk/position.py::assign_positions() → position_map (NEW)
│   └── risk/stop_loss.py::init_tracking() → stop_records (NEW)
│
├── 阶段5: 输出 (output)
│   ├── pipeline/output.py::stage_output() → report
│   └── feedback/tracker.py::record_signals() (NEW)
│
└── 阶段6: 反馈 (feedback, 异步)
    ├── feedback/tracker.py::compute_historical_accuracy()
    ├── feedback/backtest_validator.py::run_weekly_backtest()
    └── feedback/paper_trader.py::simulate_trades()
```

##### 2.3.2.3 接口定义

```python
@dataclass
class PipelineResult:
    """统一管道执行结果"""
    report_date: str
    regime: MarketRegime
    quality_report: DataQualityReport
    signals: list[Signal]            # 最终交易信号（含仓位、止损）
    report_text: str
    report_html_path: str | None
    push_success: bool
    execution_time_seconds: float
    errors: list[str]


def run(config: AppConfig) -> PipelineResult:
    """
    执行统一管道。

    废弃 V1 的 main() 函数，这是唯一的分析入口。

    Args:
        config: 应用配置。

    Returns:
        PipelineResult 完整执行结果。
    """

def run_paper_trading(config: AppConfig) -> PipelineResult:
    """
    纸交易模式：运行完整管道但不产生真实交易，
    所有信号仅记录到 SignalTracker 用于后续验证。

    Args:
        config: 应用配置。

    Returns:
        PipelineResult。
    """
```

##### 2.3.2.4 废弃清单

以下 V1 特定函数和代码路径将被标记为 deprecated，在 V3.1 中移除：

| 文件 | 函数/代码 | 替代 |
|------|----------|------|
| `main.py` | `main()` 函数 | `pipeline/unified.py::run()` |
| `main.py` | `analyze_single_stock()` | `pipeline/factors.py::calc_factors()` |
| `main.py` | `analyze_single_etf()` | `pipeline/factors.py::calc_factors()` |
| `main.py` | `parallel_batch_fetch()` | `pipeline/collect.py::_batch_fetch_klines()` |
| `scoring.py` | `calc_total_score()` (V1版) | `pipeline/factors.py::calc_factors()` |
| `scoring.py` | `calc_technical_score()` (V1版) | `factors/technical.py::calc_technical_factor()` |
| `buy_sell_signal.py` | `generate_buy_sell_signal()` | `pipeline/signal.py::generate_signals()` |
| `buy_sell_signal.py` | `determine_signal_zone()` | `pipeline/signal.py AdaptiveVoter` |

---

### 2.4 风控执行层 — Layer 4

#### 2.4.1 PositionSizer — `risk/position.py`

##### 2.4.1.1 职责

根据信号置信度、波动率和组合约束，为每个买入信号计算建议仓位大小。

##### 2.4.1.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PositionAllocation:
    """单只股票的仓位分配"""
    code: str
    name: str
    signal_confidence: float    # 信号置信度 (0~1)
    volatility_pct: float       # 年化波动率（%）
    base_weight: float          # 基础权重（%）
    adjusted_weight: float      # 调整后权重（%）
    shares: int                 # 建议股数（100股整数倍）
    capital: float              # 建议投入资金（元）
    max_loss: float             # 最大亏损金额（止损触发时）
    reason: str                 # 仓位计算理由


@dataclass
class PortfolioSummary:
    """组合汇总"""
    total_capital: float        # 总资金
    allocated_capital: float    # 已分配资金
    cash_reserve: float         # 现金储备
    position_count: int         # 持仓数量
    sector_exposure: dict[str, float]  # 行业暴露比例
    risk_contribution: dict[str, float]  # 各股票风险贡献
    warnings: list[str]         # 组合级别警告
```

##### 2.4.1.3 接口定义

```python
def assign_positions(
    buy_signals: list[Signal],
    stock_pool: pd.DataFrame,
    total_capital: float,
    regime: MarketRegime,
    kline_cache: dict[str, pd.DataFrame],
    config: object,
) -> tuple[list[PositionAllocation], PortfolioSummary]:
    """
    为买入信号分配仓位。

    分配算法（Kelly启发式 + 波动率调整）：
    1. 基础权重 = 信号置信度 / sum(所有信号置信度)
    2. 波动率惩罚：高波动股票降低权重
       adj_weight = base_weight / (volatility / median_volatility)
    3. 市场环境调整：牛市乘1.2，熊市乘0.5
    4. 单只上限：不超过总资金的 10%
    5. 单行业上限：不超过总资金的 20%
    6. 总仓位上限：牛市80%，震荡60%，熊市30%
    7. 向下取整到100股（A股1手=100股）

    Args:
        buy_signals: 买入信号列表。
        stock_pool: 股票池。
        total_capital: 总资金。
        regime: 市场环境。
        kline_cache: K线缓存。
        config: 配置。

    Returns:
        (仓位分配列表, 组合汇总)
    """

def calc_volatility(kline: pd.DataFrame, annualize: bool = True) -> float:
    """
    计算年化波动率。

    Args:
        kline: K线数据。
        annualize: 是否年化。

    Returns:
        波动率（%）。
    """

def check_sector_limits(
    allocations: list[PositionAllocation],
    industry_map: dict[str, str],
    max_sector_pct: float = 0.20,
) -> list[str]:
    """
    检查行业集中度是否超限。

    Args:
        allocations: 仓位分配。
        industry_map: code → industry 映射。
        max_sector_pct: 单行业最大比例。

    Returns:
        警告列表。
    """
```

##### 2.4.1.4 仓位计算公式

```
1. 基础权重（等权 + 置信度调整）：
   base_weight_i = confidence_i / sum(confidence_j for j in signals)

2. 波动率惩罚：
   vol_penalty_i = median_volatility / volatility_i
   risk_adj_weight_i = base_weight_i * vol_penalty_i

3. 市场环境乘数：
   regime_multiplier = {bull: 1.2, sideways: 0.8, bear: 0.4}
   env_adj_weight_i = risk_adj_weight_i * regime_multiplier

4. 硬上限裁剪（按优先级）：
   - 总仓位 ≤ regime.max_position (bull:80%, sideways:60%, bear:30%)
   - 单只 ≤ 10%
   - 单行业 ≤ 20%

5. 换算为股数：
   shares_i = floor(weight_i * total_capital / price_i / 100) * 100
```

##### 2.4.1.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 5个信号, 牛市10万资金 | bull, confidence=0.8 | 总仓位 ≤ 80000 |
| 单只超10% | 1个信号100%置信 | 权重裁剪到10% |
| 同行业多只 | 3只同一行业 | 行业总计 ≤ 20% |
| 高波动惩罚 | vol=2×中位数 | 权重降低50% |
| 熊市仓位限制 | bear | 总仓位 ≤ 30% |
| 零信号 | [] | PortfolioSummary.position_count=0 |

---

#### 2.4.2 StopLossTracker — `risk/stop_loss.py`

##### 2.4.2.1 职责

跟踪已推荐信号的止损状态，在价格触及止损价时主动推送提醒。

##### 2.4.2.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class StopLossRecord:
    """止损跟踪记录"""
    code: str
    name: str
    entry_date: str            # 推荐日期
    entry_price: float         # 推荐时价格
    stop_loss_price: float     # 止损价
    target_price: float        # 目标价
    current_price: float       # 当前价（每日更新）
    status: str                # "active", "stopped_out", "target_hit", "expired"
    days_held: int             # 已持仓天数
    pnl_pct: float             # 当前盈亏（%）
    hit_date: str | None       # 触发日期


@dataclass
class StopLossSummary:
    """止损汇总"""
    active_count: int
    stopped_out_today: list[StopLossRecord]
    target_hit_today: list[StopLossRecord]
    near_stop_loss: list[StopLossRecord]   # 距离止损 < 3%
    avg_pnl: float                         # 平均盈亏（%）
    win_rate: float                        # 胜率（目标价先触发 vs 止损先触发）
```

##### 2.4.2.3 接口定义

```python
def init_tracking(
    signals: list[Signal],
    today: str,
) -> list[StopLossRecord]:
    """
    为所有买入/卖出信号初始化止损跟踪记录。

    Args:
        signals: 交易信号列表。
        today: 今日日期。

    Returns:
        止损记录列表。
    """

def check_stop_losses(
    records: list[StopLossRecord],
    kline_cache: dict[str, pd.DataFrame],
    today: str,
) -> StopLossSummary:
    """
    检查所有活跃记录的止损状态。

    检查规则：
    - 当前价 <= 止损价 → status = "stopped_out"
    - 当前价 >= 目标价 → status = "target_hit"
    - 持仓超过30天 → status = "expired"
    - 当前价距止损 < 3% → 加入 near_stop_loss 预警

    Args:
        records: 所有止损记录。
        kline_cache: K线缓存（获取最新价格）。
        today: 今日日期。

    Returns:
        止损汇总。
    """

def generate_stop_loss_alert(summary: StopLossSummary) -> str:
    """
    生成止损提醒消息文本。

    Args:
        summary: 止损汇总。

    Returns:
        Markdown 格式提醒消息。
    """

def update_stop_price(
    record: StopLossRecord,
    new_stop: float,
    reason: str,
) -> StopLossRecord:
    """
    移动止损：当价格上涨后，上移止损价锁定利润。

    移动规则（追踪止损）：
    - 盈利 > 10%：止损上移到 入场价（保本止损）
    - 盈利 > 20%：止损上移到 入场价 + 10%（锁定10%利润）
    - 盈利 > 30%：止损上移到 入场价 + 20%

    Args:
        record: 当前止损记录。
        new_stop: 新止损价。
        reason: 移动理由。

    Returns:
        更新后的止损记录。
    """
```

##### 2.4.2.4 数据库存储

```sql
-- 扩展现有的 recommendations 表
ALTER TABLE recommendations ADD COLUMN stop_loss_price REAL;
ALTER TABLE recommendations ADD COLUMN target_price REAL;
ALTER TABLE recommendations ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE recommendations ADD COLUMN hit_date TEXT;
ALTER TABLE recommendations ADD COLUMN exit_price REAL;
ALTER TABLE recommendations ADD COLUMN pnl_pct REAL;
```

##### 2.4.2.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 价格触及止损 | current=止损, entry高于止损 | status=stopped_out |
| 价格触及目标 | current=目标 | status=target_hit |
| 价格距止损2% | current=止损×1.02 | near_stop_loss 包含该记录 |
| 持仓超30天 | days_held=31 | status=expired |
| 追踪止损上移 | 盈利25% | 新止损 = entry+10% |
| 空记录 | [] | active_count=0 |

---

#### 2.4.3 RiskGuard — `risk/guard.py`

##### 2.4.3.1 职责

在信号生成后执行硬性风控规则，过滤掉不符合交易规则的信号。

##### 2.4.3.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class RejectReason(Enum):
    """拒绝原因"""
    ST_STOCK = "ST/*ST 股票"
    LIMIT_UP = "涨停板（无法买入）"
    LIMIT_DOWN = "跌停板（无法卖出）"
    LOW_LIQUIDITY = "日均成交额过低（< 1000万）"
    HIGH_BID_ASK = "接近涨跌停（买入滑点过大）"
    PRICE_LIMIT = "股价过低（< 2元，仙股风险）"
    SECTOR_OVERWEIGHT = "行业超配"
    MAX_POSITION = "已达最大持仓数"
    RECENT_SIGNAL = "最近3日已有同向信号"
    EXCESSIVE_VOLATILITY = "波动率异常（> 年化200%）"


@dataclass
class RiskRuleResult:
    """单条风控规则的判断结果"""
    passed: bool
    reject_reason: RejectReason | None
    detail: str


@dataclass
class GuardResult:
    """风控检查结果"""
    input_count: int            # 输入信号数
    passed_count: int           # 通过数
    rejected: list[tuple[Signal, RejectReason, str]]  # 被拒绝的信号
    passed: list[Signal]        # 通过的信号
    warnings: list[str]         # 警告（不拒绝但需关注）
```

##### 2.4.3.3 接口定义

```python
# 风控规则集（按优先级排列）
RISK_RULES: list[dict] = [
    {"name": "ST过滤", "priority": 1, "block": True},
    {"name": "涨跌停检查", "priority": 2, "block": True},
    {"name": "流动性过滤", "priority": 3, "block": True},
    {"name": "仙股过滤", "priority": 4, "block": True},
    {"name": "行业超配检查", "priority": 5, "block": True},
    {"name": "最大持仓检查", "priority": 6, "block": True},
    {"name": "重复信号检查", "priority": 7, "block": False},  # 仅警告
    {"name": "波动率异常检查", "priority": 8, "block": False}, # 仅警告
]


def apply_risk_rules(
    signals: list[Signal],
    stock_pool: pd.DataFrame,
    kline_cache: dict[str, pd.DataFrame],
    existing_positions: list[dict],
    daily_stats: dict,
) -> GuardResult:
    """
    对信号列表执行全部风控规则。

    规则详情：
    1. ST/*ST过滤：名称含 ST → 拒绝
    2. 涨跌停检查：涨跌幅达到±9.9%以上 → 拒绝（无法成交）
    3. 流动性过滤：近20日均成交额 < 1000万 → 拒绝
    4. 仙股过滤：股价 < 2元 → 拒绝
    5. 行业超配：单行业持仓 > 20% → 该行业后续买入信号拒绝
    6. 最大持仓：已有 N 只持仓时拒绝新的买入信号（N=regime相关）
    7. 重复信号：3日内同股票同方向 → 仅警告
    8. 波动率异常：年化波动率 > 200% → 仅警告

    Args:
        signals: 待检查的信号列表。
        stock_pool: 股票池（含实时涨跌幅）。
        kline_cache: K线缓存（用于流动性计算）。
        existing_positions: 现有持仓（从 tracker 查询）。
        daily_stats: 当日市场统计。

    Returns:
        GuardResult 风控检查结果。
    """

def check_st_stock(code: str, name: str) -> RiskRuleResult:
    """检查是否为ST股票"""

def check_limit_price(code: str, stock_pool: pd.DataFrame) -> RiskRuleResult:
    """检查是否涨跌停"""

def check_liquidity(code: str, kline_cache: dict) -> RiskRuleResult:
    """检查日均成交额"""
```

##### 2.4.3.4 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| ST股票 | name="*ST某某" | 拒绝 |
| 涨停板 | change_pct=10.05 | 拒绝（买入） |
| 低流动性 | 均成交额=500万 | 拒绝 |
| 仙股 | price=1.50 | 拒绝 |
| 通过全部 | 正常股票 | 通过 |
| 仅警告 | 波动率=250% | 通过但有警告 |

---

### 2.5 反馈验证层 — Layer 5

#### 2.5.1 SignalTracker — `feedback/tracker.py`

##### 2.5.1.1 职责

将现有的"只写不读"信号追踪升级为完整的**信号→收益闭环反馈系统**。系统性地记录推荐历史，计算回顾准确率，并将结果反馈到信号置信度校准。

##### 2.5.1.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class SignalPerformance:
    """单条信号的回顾表现"""
    signal_id: int
    code: str
    name: str
    signal_date: str
    signal_action: str       # buy / sell
    signal_score: float
    entry_price: float

    # 各周期表现（%）
    ret_1d: float | None = None
    ret_3d: float | None = None
    ret_5d: float | None = None
    ret_10d: float | None = None
    ret_20d: float | None = None

    # 关键价位表现
    hit_target: bool = False     # 是否触及目标价
    hit_stop: bool = False       # 是否触及止损价
    max_favorable: float = 0.0   # 最大浮盈（%）
    max_adverse: float = 0.0     # 最大浮亏（%）

    # 超额收益
    vs_index_ret: float | None = None   # 相对沪深300超额收益
    vs_sector_ret: float | None = None  # 相对行业ETF超额收益


@dataclass
class AggregatePerformance:
    """汇总表现统计"""
    period: str                    # "all", "30d", "90d"
    total_signals: int
    buy_signals: int
    sell_signals: int

    # 核心指标
    win_rate_5d: float             # 5日胜率（%）
    avg_return_5d: float           # 5日平均收益（%）
    avg_excess_return_5d: float    # 5日平均超额收益（%）
    sharpe_ratio: float            # 年化夏普比率
    max_drawdown: float            # 最大回撤（%）
    profit_factor: float           # 盈亏比

    # 分类指标
    by_score_range: dict[str, dict]  # 各分数段的胜率和收益
    by_sector: dict[str, dict]       # 各行业的胜率和收益
    by_market_regime: dict[str, dict]  # 各市场环境下的表现

    # 建议
    score_threshold_advice: float   # 基于真实数据的最优买入阈值
```

##### 2.5.1.3 接口定义

```python
def record_signals_v3(signals: list[Signal], today: str) -> int:
    """
    记录信号到数据库（V3 增强版，扩展字段）。
    替代现有的 record_signals()。

    Returns:
        记录的信号数。
    """

def compute_pnl(signal_date: str, lookback_days: int = 20) -> list[SignalPerformance]:
    """
    计算特定日期的信号在 N 日后的回顾表现。

    计算逻辑：
    1. 从数据库查询 signal_date 的信号
    2. 从 AKShare 获取 signal_date + N 的K线数据
    3. 计算各周期的收益率
    4. 检查是否触达目标价/止损价

    Args:
        signal_date: 信号日期。
        lookback_days: 回溯天数。

    Returns:
        每条信号的表现数据。
    """

def compute_aggregate_performance(
    start_date: str,
    end_date: str,
) -> AggregatePerformance:
    """
    计算汇总表现统计。

    Args:
        start_date: 开始日期。
        end_date: 结束日期。

    Returns:
        AggregatePerformance。
    """

def recommend_thresholds(
    performance: AggregatePerformance,
) -> dict[str, float]:
    """
    基于真实表现数据推荐最优阈值。

    逻辑：
    - 按分数分段统计胜率
    - 找到胜率 > 55% 的最低分数作为 buy_threshold
    - 找到胜率 < 40% 的最高分数作为 sell_threshold
    - 反馈到 config 或下一次运行的 threshold override

    Args:
        performance: 汇总表现数据。

    Returns:
        推荐的阈值字典（buy_threshold, sell_threshold, min_buy_votes）。
    """

def generate_performance_report(
    performance: AggregatePerformance,
) -> str:
    """
    生成表现回顾报告（附加到每日报告的末尾）。

    Args:
        performance: 汇总表现数据。

    Returns:
        Markdown 格式的表现报告。
    """
```

##### 2.5.1.4 数据库 Schema 升级

```sql
-- 扩展现有 recommendations 表
CREATE TABLE IF NOT EXISTS signal_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    action TEXT NOT NULL,
    score REAL,
    entry_price REAL,

    -- 回顾数据（T+N 后填充）
    ret_1d REAL,
    ret_3d REAL,
    ret_5d REAL,
    ret_10d REAL,
    ret_20d REAL,
    hit_target INTEGER DEFAULT 0,  -- boolean
    hit_stop INTEGER DEFAULT 0,
    max_favorable REAL,
    max_adverse REAL,
    vs_index_ret REAL,
    vs_sector_ret REAL,

    computed_date TEXT,            -- 回顾数据计算日期
    UNIQUE(signal_date, code, action)
);

-- 参数优化记录
CREATE TABLE IF NOT EXISTS threshold_history (
    date TEXT PRIMARY KEY,
    buy_threshold REAL,
    sell_threshold REAL,
    min_buy_votes INTEGER,
    win_rate_5d REAL,
    sharpe_ratio REAL,
    notes TEXT
);
```

##### 2.5.1.5 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 记录信号 | 10条Signal | 数据库新增10条 |
| 计算回顾 | signal_date=7天前 | ret_5d 正确计算 |
| 目标价触达 | 后续最高价>目标价 | hit_target=True |
| 汇总统计 | 100条30天数据 | 胜率/夏普/最大回撤正确 |
| 阈值推荐 | 胜率数据 | 推荐阈值合理（胜率>50%） |
| 空数据库 | 新系统无历史 | 返回空结果不报错 |

---

#### 2.5.2 BacktestValidator — `feedback/backtest_validator.py`

##### 2.5.2.1 职责

对策略进行完整的历史回测验证，输出统计显著的结果。改造现有的 [backtest.py](src/backtest.py)（目前仅框架），使其能产出可信的回测结果。

##### 2.5.2.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    pool_size: int = 100
    top_n: int = 20               # 每日取前N只买入
    hold_days: list[int] = field(default_factory=lambda: [1, 3, 5, 10, 20])
    commission_rate: float = 0.0003  # 万三佣金
    stamp_tax: float = 0.001        # 千一印花税（卖出）
    slippage: float = 0.001         # 千一滑点
    initial_capital: float = 1_000_000.0
    benchmark: str = "000300"       # 基准指数（沪深300）


@dataclass
class BacktestPeriodResult:
    """单个持仓周期的回测结果"""
    hold_days: int
    total_trades: int
    win_rate: float                 # 胜率（%）
    avg_return: float               # 平均收益（%）
    median_return: float            # 中位数收益（%）
    max_win: float                  # 最大单笔盈利（%）
    max_loss: float                 # 最大单笔亏损（%）
    sharpe_ratio: float             # 年化夏普比率
    sortino_ratio: float            # 索提诺比率（只惩罚下行波动）
    max_drawdown: float             # 最大回撤（%）
    calmar_ratio: float             # 卡玛比率
    profit_factor: float            # 盈亏比
    win_loss_ratio: float           # 胜/负次数比
    avg_win_size: float             # 平均盈利幅度（%）
    avg_loss_size: float            # 平均亏损幅度（%）
    total_return: float             # 累计收益（%）
    annual_return: float            # 年化收益（%）
    benchmark_return: float         # 基准同期收益（%）
    excess_return: float            # 超额收益（%）
    information_ratio: float        # 信息比率
    t_statistic: float             # t 检验值（>2 表示统计显著）
    p_value: float                  # p 值


@dataclass
class FullBacktestResult:
    """完整回测报告"""
    config: BacktestConfig
    period_results: list[BacktestPeriodResult]
    equity_curve: list[float]       # 净值曲线
    benchmark_curve: list[float]    # 基准净值曲线
    monthly_returns: dict[str, float]  # 月度收益率
    yearly_returns: dict[str, float]   # 年度收益率
    worst_month: tuple[str, float]  # 最差月份
    best_month: tuple[str, float]   # 最佳月份
    consecutive_losses: int         # 最大连续亏损次数
    recommendations: str            # 基于回测结果的改进建议
```

##### 2.5.2.3 接口定义

```python
def run_full_backtest(config: BacktestConfig) -> FullBacktestResult:
    """
    运行完整回测。

    回测流程（13步）：
    1. 构建历史股票池：对每个交易日，取该日市值前 pool_size 只
    2. 获取历史K线数据（利用缓存，避免重复下载）
    3. 逐日执行分析管道：
       a. 构建 DataBundle（模拟当日收盘数据）
       b. 计算因子分数（calc_factors + calibrate_scores）
       c. 生成交易信号（generate_signals with AdaptiveVoter）
       d. 模拟交易：按信号买入 top_n 只
    4. T+N 日后卖出，记录收益
    5. 扣除手续费、印花税、滑点
    6. 计算净值曲线和基准净值曲线
    7. 计算全部统计指标（含统计显著性检验）

    Args:
        config: 回测配置。

    Returns:
        FullBacktestResult。
    """

def run_parameter_sweep(
    base_config: BacktestConfig,
    param_grid: dict[str, list],
) -> list[tuple[dict, BacktestPeriodResult]]:
    """
    参数网格搜索：寻找最优参数组合。

    优化的参数：
    - top_n (买入数量): [5, 10, 20, 30]
    - hold_days (持仓天数): [3, 5, 10, 20]
    - buy_threshold 相关: [60, 65, 70, 75]
    - min_buy_votes: [1, 2, 3]

    Args:
        base_config: 基础配置。
        param_grid: 参数网格。

    Returns:
        [(参数组合, 回测结果), ...] 按夏普比率降序。
    """

def statistical_significance_test(
    returns: list[float],
    benchmark_returns: list[float],
) -> tuple[float, float]:
    """
    策略超额收益的 t 检验。

    H0: 策略收益 ≤ 基准收益
    如果 p < 0.05，拒绝 H0，策略有统计显著的 alpha。

    Args:
        returns: 策略收益率序列。
        benchmark_returns: 基准收益率序列。

    Returns:
        (t_statistic, p_value)
    """

def monte_carlo_test(
    returns: list[float],
    n_simulations: int = 10000,
) -> dict:
    """
    蒙特卡洛模拟：验证策略表现是否来自运气。

    对收益率序列进行 10000 次随机重排，
    如果真实夏普比率高于 95% 的随机结果，则认为非运气。

    Args:
        returns: 收益率序列。
        n_simulations: 模拟次数。

    Returns:
        {"real_sharpe": x, "percentile": 97.5, "is_significant": True}
    """
```

##### 2.5.2.4 回测执行流程伪代码

```python
def run_full_backtest(config):
    # Step 1: 获取交易日历
    trading_days = get_trading_calendar(config.start_date, config.end_date)

    # Step 2: 初始化
    equity = [config.initial_capital]
    benchmark_equity = [config.initial_capital]
    all_trades = []

    # Step 3: 逐日回测
    for i, today in enumerate(trading_days):
        if i < 60:  # 跳过前60天（数据不足）
            continue

        # 构建当日 DataBundle（只用 today 之前的数据）
        bundle = build_historical_bundle(today, config.pool_size)

        # 执行分析管道（与生产代码相同）
        regime = judge_market_regime(bundle, app_config)
        raw_scores = calc_factors(bundle, app_config, regime.state)
        scores = calibrate_scores(raw_scores)  # NEW: 百分位校准
        signals = generate_signals(scores, bundle, app_config, regime.state)

        # 仅买入信号
        buy_signals = [s for s in signals if s.action == "buy"]
        buy_signals.sort(key=lambda s: s.confidence, reverse=True)

        # 取 top_n 只
        for sig in buy_signals[:config.top_n]:
            for hold in config.hold_days:
                if i + hold >= len(trading_days):
                    continue
                future_date = trading_days[i + hold]
                entry_price = get_price(sig.code, today)
                exit_price = get_price(sig.code, future_date)

                # 扣费
                cost = (entry_price + exit_price) * config.commission_rate
                cost += exit_price * config.stamp_tax  # 印花税只在卖出
                cost += entry_price * config.slippage + exit_price * config.slippage

                ret = (exit_price - entry_price - cost / 100) / entry_price
                all_trades.append({"code": sig.code, "hold": hold, "ret": ret})

        # 更新净值
        ...

    # Step 4: 统计汇总
    return compute_statistics(all_trades, equity, benchmark_equity)
```

##### 2.5.2.5 通过标准

在投入实盘前，策略必须满足以下最低标准：

| 指标 | 最低标准 | 理想标准 |
|------|:--------:|:--------:|
| 年化收益 | > 5% | > 15% |
| 超额收益（vs 沪深300） | > 3% | > 10% |
| 夏普比率 | > 0.5 | > 1.5 |
| 最大回撤 | < 25% | < 15% |
| 胜率（5日） | > 50% | > 55% |
| t 检验 p 值 | < 0.05 | < 0.01 |
| 蒙特卡洛百分位 | > 90% | > 95% |

**任一最低标准未达标 → 不投入实盘。**

##### 2.5.2.6 测试策略

| 测试场景 | 输入 | 期望输出 |
|----------|------|----------|
| 随机策略 | 随机买入 | Sharpe < 0, 不通过 |
| 趋势策略（牛市中） | 模拟牛市数据 | Sharpe > 0.5 |
| 交易成本 | 已知收益序列 | 正确扣除佣金+印花税+滑点 |
| 统计检验 | 已知均值>0序列 | t统计量>2, p<0.05 |
| 空数据 | 无交易 | FullBacktestResult.total_trades=0 |

---

#### 2.5.3 PaperTrader — `feedback/paper_trader.py`

##### 2.5.3.1 职责

在实盘交易前提供模拟交易（纸交易）模式。使用真实每日数据执行策略，但不产生真实资金变动。纸交易至少运行 3 个月且表现达标后，方可切换到实盘。

##### 2.5.3.2 数据结构

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class PaperAccount:
    """模拟账户"""
    initial_capital: float
    cash: float                   # 可用现金
    positions: dict[str, PaperPosition]  # 持仓
    total_value: float            # 总资产
    daily_pnl: float              # 当日盈亏
    total_pnl: float              # 累计盈亏
    total_pnl_pct: float          # 累计盈亏（%）
    trade_history: list[PaperTrade]
    daily_records: list[dict]     # 每日净值记录


@dataclass
class PaperPosition:
    """模拟持仓"""
    code: str
    name: str
    shares: int
    avg_cost: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    days_held: int


@dataclass
class PaperTrade:
    """模拟交易"""
    date: str
    code: str
    action: str                  # "buy" / "sell"
    price: float
    shares: int
    amount: float
    commission: float
    stamp_tax: float
    signal_score: float
    signal_confidence: float
    reason: str
```

##### 2.5.3.3 接口定义

```python
def init_paper_account(capital: float = 1_000_000.0) -> PaperAccount:
    """
    初始化模拟账户。

    Args:
        capital: 初始资金。

    Returns:
        PaperAccount。
    """

def execute_daily_signals(
    account: PaperAccount,
    signals: list[Signal],
    stock_pool: pd.DataFrame,
    today: str,
) -> PaperAccount:
    """
    根据当日信号执行模拟交易。

    交易规则：
    1. 买入：按 PositionSizer 计算的数量买入（100股整数倍）
    2. 卖出：信号为 sell 的持仓全部卖出
    3. 止损：检查所有持仓是否触及止损价
    4. 扣除：佣金万三 + 印花税千一（卖出） + 滑点千一
    5. 更新账户总资产

    Args:
        account: 当前账户状态。
        signals: 当日信号。
        stock_pool: 股票池（获取价格）。
        today: 今日日期。

    Returns:
        更新后的账户状态。
    """

def generate_paper_report(account: PaperAccount) -> str:
    """
    生成模拟交易日报。

    包含：
    - 账户总览（总资产/现金/持仓市值/累计收益率）
    - 当日交易明细
    - 持仓列表（含盈亏）
    - 净值曲线（与基准对比）
    - 关键指标（夏普比/最大回撤/胜率）

    Args:
        account: 账户状态。

    Returns:
        Markdown 报告文本。
    """

def check_go_live_readiness(account: PaperAccount, min_days: int = 60) -> tuple[bool, str]:
    """
    检查是否满足实盘切换条件。

    条件：
    1. 纸交易运行 >= 60 个交易日
    2. 累计收益 > 0（至少不亏）
    3. 夏普比率 > 0.5
    4. 最大回撤 < 20%
    5. 月胜率 > 50%（月度收益为正的月数 > 50%）

    Args:
        account: 账户状态。
        min_days: 最少交易日数。

    Returns:
        (是否就绪, 就绪/未就绪原因)
    """
```

##### 2.5.3.4 纸交易数据库

```sql
CREATE TABLE IF NOT EXISTS paper_account (
    date TEXT PRIMARY KEY,
    cash REAL,
    total_value REAL,
    daily_pnl REAL,
    total_pnl_pct REAL,
    position_count INTEGER
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL,
    shares INTEGER,
    amount REAL,
    commission REAL,
    stamp_tax REAL,
    signal_score REAL,
    signal_confidence REAL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS paper_positions (
    code TEXT PRIMARY KEY,
    name TEXT,
    shares INTEGER,
    avg_cost REAL,
    entry_date TEXT
);
```

---

## 三、模块依赖关系

```
UnifiedPipeline (pipeline/unified.py)
│
├── [数据采集] pipeline/collect.py (现有)
│   ├── stock_filter.py (现有)
│   ├── fundamental_analysis.py (现有，被 unifier 包装)
│   └── etf_analyzer.py (现有)
│
├── [数据质量] data_quality/
│   ├── validator.py ─── 依赖 collect 输出
│   └── unifier.py  ─── 依赖 validator 输出 + fundamental_analysis
│
├── [市场环境] pipeline/regime.py (现有)
│   └── 依赖 collect 输出的 index_kline, north_flow
│
├── [因子计算] factors/ + pipeline/factors.py
│   ├── factors/technical.py (现有)
│   ├── factors/fundamental.py (现有)
│   ├── factors/momentum.py (现有)
│   ├── factors/capital.py (现有)
│   ├── factors/sentiment.py (现有)
│   ├── factors/calibrator.py (NEW) ─── 依赖 calc_factors 输出
│   └── factors/industry_rotation.py (NEW) ─── 依赖 etf_kline_cache
│
├── [信号生成] pipeline/signal.py (改造)
│   ├── AdaptiveVoter ─── 依赖 regime.state, calibrated scores
│   ├── risk/guard.py (NEW) ─── 依赖 stock_pool, kline_cache
│   ├── risk/position.py (NEW) ─── 依赖 buy_signals, kline_cache
│   └── risk/stop_loss.py (NEW) ─── 依赖 signals, kline_cache
│
├── [输出] pipeline/output.py (现有)
│   ├── report_generator.py (现有)
│   ├── chart_generator.py (现有)
│   └── push_service.py (现有)
│
└── [反馈] feedback/
    ├── tracker.py ─── 依赖 signals (写入), AKShare (回看)
    ├── backtest_validator.py ─── 依赖全部 pipeline 模块
    └── paper_trader.py ─── 依赖 unified pipeline + risk 层
```

**层间依赖方向**（单向，不循环）：
```
collect → data_quality → regime → factors → signal → risk → output
                                                          ↓
                                                     feedback (读全部)
```

---

## 四、数据流汇总

```
AKShare / BaoStock API
    │
    ▼
pipeline/collect.py ──→ DataBundle (原始数据)
    │
    ▼
data_quality/validator.py ──→ DataQualityReport (质量标记)
    │
    ▼
data_quality/unifier.py ──→ NormalizedFundamental[] (标准化数据)
    │
    ▼
pipeline/regime.py ──→ MarketRegime (市场环境)
    │
    ├──→ factors/industry_rotation.py ──→ IndustryScoreAdjustment[]
    │
    ▼
pipeline/factors.py ──→ FactorScores[] (原始因子分)
    │
    ▼
factors/calibrator.py ──→ CalibratedScores[] (校准后, 区分度↑)
    │
    ▼
pipeline/signal.py (AdaptiveVoter) ──→ Signal[] (自适应投票)
    │
    ├──→ risk/guard.py ──→ Signal[] (过滤后)
    ├──→ risk/position.py ──→ PositionAllocation[]
    └──→ risk/stop_loss.py ──→ StopLossRecord[]
    │
    ├──→ feedback/tracker.py ──→ 写入数据库
    │
    ▼
pipeline/output.py ──→ 报告 → push_service → 微信
    │
    ▼
feedback/backtest_validator.py ──→ 回测报告 (独立运行)
feedback/paper_trader.py ──→ 模拟交易 (替代实盘)
```

---

## 五、配置扩展

在现有 `AppConfig` 基础上新增以下配置 dataclass：

```python
@dataclass
class CalibrationConfig:
    """评分校准配置"""
    pct_weight: float = 0.5          # 百分位权重
    target_std: float = 20.0         # 目标标准差
    tail_expand: float = 1.5         # 尾部拉伸


@dataclass
class RiskControlConfig:
    """风控配置"""
    max_single_position: float = 0.10   # 单只最大仓位
    max_sector_exposure: float = 0.20   # 单行业最大暴露
    max_positions_bull: int = 15        # 牛市最大持仓数
    max_positions_sideways: int = 10
    max_positions_bear: int = 5
    min_daily_volume: float = 10_000_000  # 最低日均成交额（元）
    min_price: float = 2.0              # 最低股价（元）
    trailing_stop_enabled: bool = True  # 是否启用移动止损
    max_drawdown_limit: float = 0.15    # 总回撤15%时停止交易


@dataclass
class FeedbackConfig:
    """反馈系统配置"""
    min_paper_trading_days: int = 60    # 最少纸交易天数
    min_go_live_sharpe: float = 0.5    # 实盘最低夏普
    min_go_live_win_rate: float = 0.50 # 实盘最低胜率
    auto_threshold_update: bool = False # 是否自动更新阈值（谨慎启用）


@dataclass
class AdaptiveSignalConfig(SignalConfig):
    """自适应信号配置（替换原有的固定阈值 SignalConfig）"""
    # 各市场环境下的投票阈值
    thresholds: dict[str, AdaptiveThresholds] = field(default_factory=lambda: {
        "bull": AdaptiveThresholds.for_regime("bull"),
        "bear": AdaptiveThresholds.for_regime("bear"),
        "sideways": AdaptiveThresholds.for_regime("sideways"),
    })
```

---

## 六、实施路线

### 6.1 阶段划分

| 阶段 | 内容 | 预计工期 | 产出 |
|:----:|------|:--------:|------|
| **Phase 1** | 数据质量层：Validator + Unifier | 3天 | 基本面数据正确率 > 80% |
| **Phase 2** | 因子评分层：Calibrator + IndustryRotation | 4天 | 评分标准差 > 15 |
| **Phase 3** | 信号生成层：AdaptiveVoter + UnifiedPipeline | 3天 | buy/sell 信号比例 < 总信号 40% |
| **Phase 4** | 风控执行层：PositionSizer + StopLossTracker + RiskGuard | 4天 | 完整风控链路 |
| **Phase 5** | 反馈验证层：SignalTracker + BacktestValidator | 5天 | 回测报告 + t检验 p<0.05 |
| **Phase 6** | 纸交易 + 文档：PaperTrader + 用户指南 | 3天 | 纸交易运行 + 用户文档 |

### 6.2 验收条件

- [ ] 基本面对比：修复后 ROE 数据与同花顺/东方财富公示值偏差 < 10%
- [ ] 评分区分度：最高分 ≥ 90, 最低分 ≤ 10, 标准差 ≥ 15
- [ ] 信号有效性：buy 信号数量 ≠ sell 信号数量, hold 信号 < 60%
- [ ] 回测验证：最低标准全部通过（见 2.5.2.5）
- [ ] 纸交易：连续运行 60 个交易日，满足 go-live 条件
- [ ] 单元测试：所有新模块测试覆盖率 > 80%

---

## 七、风险与注意事项

1. **过度拟合风险**：参数优化（网格搜索）可能导致过拟合。必须使用样本外数据（如 2026 年数据）验证。
2. **数据源稳定性**：AKShare/BaoStock API 可能变更或限流。保留三级回退机制不变。
3. **市场结构变化**：A 股市场规则可能变化（如 T+0 改革），策略需定期复核有效性。
4. **存活者偏差**：回测使用当前存活的股票，忽略了已退市的。在 backtest_validator 中需要处理退市股票。

---

*本文档为 V3 详细设计初稿，依据 2026-07-10 系统评估编写。请评审后进入开发阶段。*
