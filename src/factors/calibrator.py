"""百分位评分校准模块 — FactorCalibrator.

解决评分压缩问题。通过百分位排名标准化和分布拉伸，
将评分分布从 32.5~70.3 (σ≈8) 扩展到 ~5~95 (σ≈20)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("thousand-times")


@dataclass
class CalibratedScores:
    """校准后的因子评分."""

    code: str
    name: str

    # 原始评分（0-100，由现有因子模块计算）
    technical_raw: float = 50.0
    fundamental_raw: float = 50.0
    capital_raw: float = 50.0
    sentiment_raw: float = 50.0
    momentum_raw: float = 50.0

    # 百分位评分（在股票池中的相对位置，0-100）
    technical_pct: float = 50.0
    fundamental_pct: float = 50.0
    capital_pct: float = 50.0
    sentiment_pct: float = 50.0
    momentum_pct: float = 50.0

    # 校准后评分（加权混合原始+百分位）
    technical: float = 50.0
    fundamental: float = 50.0
    capital: float = 50.0
    sentiment: float = 50.0
    momentum: float = 50.0

    # 综合分
    total: float = 50.0
    total_pct: float = 50.0       # 在全部股票中的百分位

    # 子因子详情（透传）
    technical_detail: dict[str, float] = field(default_factory=dict)
    fundamental_detail: dict[str, float] = field(default_factory=dict)
    capital_detail: dict[str, float] = field(default_factory=dict)
    sentiment_detail: dict[str, float] = field(default_factory=dict)
    momentum_detail: dict[str, float] = field(default_factory=dict)


@dataclass
class CalibrationParams:
    """校准参数（可通过回测优化）."""

    # 百分位评分权重（0=纯绝对评分，1=纯百分位评分）
    pct_weight: float = 0.5

    # 分布拉伸参数
    target_mean: float = 50.0      # 目标均值
    target_std: float = 20.0       # 目标标准差（当前约8-10，太低）

    # 尾部扩展
    tail_expand: float = 1.5       # 尾部拉伸倍数


def calc_percentile_rank(value: float, all_values: list[float]) -> float:
    """计算单个值在群体中的百分位排名.

    Args:
        value: 目标值.
        all_values: 所有值列表.

    Returns:
        百分位排名（0-100），100 = 最高.
    """
    if not all_values:
        return 50.0

    # 计算严格小于目标值的比例
    count_below = sum(1 for v in all_values if v < value)
    count_equal = sum(1 for v in all_values if v == value)

    # 使用中点百分位法：处理平局
    if count_equal == 0:
        return (count_below / len(all_values)) * 100

    # 平局：取平局范围的中点
    return ((count_below + count_equal / 2) / len(all_values)) * 100


def stretch_distribution(
    values: list[float],
    target_mean: float,
    target_std: float,
) -> list[float]:
    """使用 Z-score 标准化 + 线性拉伸将分布调整到目标均值和标准差.

    算法：
    1. 计算原始均值和标准差
    2. Z = (x - mean_orig) / std_orig
    3. stretched = target_mean + Z * target_std
    4. 截断到 [0, 100]

    Args:
        values: 原始值列表.
        target_mean: 目标均值.
        target_std: 目标标准差.

    Returns:
        拉伸后的值列表.
    """
    if not values:
        return []

    arr = np.array(values, dtype=float)
    mean_orig = float(np.mean(arr))
    std_orig = float(np.std(arr))

    if std_orig < 1e-8:
        # 所有值几乎相同，无法拉伸，返回均值为中心的窄分布
        return [float(np.clip(target_mean, 0.0, 100.0))] * len(values)

    z_scores = (arr - mean_orig) / std_orig
    stretched = target_mean + z_scores * target_std

    # 截断到 [0, 100]
    return [float(np.clip(v, 0.0, 100.0)) for v in stretched]


def _calibrate_single_factor(
    raw_values: list[float],
    pct_weight: float,
) -> list[float]:
    """对单个因子的值进行校准（Step 2-4）.

    1. 计算百分位排名
    2. 混合原始值和百分位值
    3. 拉伸分布
    4. 截断

    Args:
        raw_values: 原始因子值列表.
        pct_weight: 百分位权重.

    Returns:
        校准后的值列表.
    """
    if not raw_values:
        return []

    # Step 1: 计算百分位
    pct_values = [calc_percentile_rank(v, raw_values) for v in raw_values]

    # Step 2: 混合
    w = pct_weight
    mixed = [raw * (1 - w) + pct * w for raw, pct in zip(raw_values, pct_values, strict=True)]

    # Step 3-4: 拉伸 + 截断
    return stretch_distribution(mixed, 50.0, 20.0)


def calibrate_scores(
    raw_scores: list[object],
    params: CalibrationParams | None = None,
) -> list[CalibratedScores]:
    """对原始因子评分进行校准.

    校准流程：
    1. 计算每个因子在股票池中的百分位排名
    2. 百分位评分与原始评分加权混合：final = raw * (1-pct_weight) + pct * 100 * pct_weight
    3. Z-score 标准化拉伸：拉伸后均值=target_mean，标准差=target_std
    4. 截断到 [0, 100]

    效果：
    - 校准前：均值 47.8, 范围 32.5-70.3, 标准差 ~8
    - 校准后：均值 50.0, 范围 ~5-95, 标准差 ~20

    Args:
        raw_scores: 原始 FactorScores 列表.
        params: 校准参数，为 None 时使用默认值.

    Returns:
        校准后的 CalibratedScores 列表，按 total 降序排列.
    """
    if params is None:
        params = CalibrationParams()

    if not raw_scores:
        return []

    n = len(raw_scores)
    w = params.pct_weight

    # 提取各因子原始值
    factor_names = ["technical", "fundamental", "capital", "sentiment", "momentum"]
    raw_dict: dict[str, list[float]] = {f: [] for f in factor_names}

    for s in raw_scores:
        for f in factor_names:
            raw_dict[f].append(getattr(s, f, 50.0))

    # 对每个因子进行校准
    calibrated_dict: dict[str, list[float]] = {}
    for f in factor_names:
        calibrated_dict[f] = _calibrate_single_factor(raw_dict[f], w)

    # 计算百分位
    pct_dict: dict[str, list[float]] = {}
    for f in factor_names:
        pct_dict[f] = [calc_percentile_rank(v, raw_dict[f]) for v in raw_dict[f]]

    # 计算 total（原始总分加权混合）
    raw_totals = [getattr(s, "total", 50.0) for s in raw_scores]
    # 同样对 total 做混合
    total_pcts = [calc_percentile_rank(v, raw_totals) for v in raw_totals]
    mixed_totals = [raw * (1 - w) + pct * w for raw, pct in zip(raw_totals, total_pcts, strict=True)]
    stretched_totals = stretch_distribution(mixed_totals, params.target_mean, params.target_std)

    # 组装结果
    results: list[CalibratedScores] = []
    for i, s in enumerate(raw_scores):
        code = getattr(s, "code", "")
        name = getattr(s, "name", "")

        detail_fields = [
            "technical_detail", "fundamental_detail", "capital_detail",
            "sentiment_detail", "momentum_detail",
        ]
        details: dict[str, dict[str, float]] = {}
        for df in detail_fields:
            val = getattr(s, df, {})
            details[df] = dict(val) if val else {}

        results.append(CalibratedScores(
            code=code,
            name=name,
            technical_raw=raw_dict["technical"][i],
            fundamental_raw=raw_dict["fundamental"][i],
            capital_raw=raw_dict["capital"][i],
            sentiment_raw=raw_dict["sentiment"][i],
            momentum_raw=raw_dict["momentum"][i],
            technical_pct=pct_dict["technical"][i],
            fundamental_pct=pct_dict["fundamental"][i],
            capital_pct=pct_dict["capital"][i],
            sentiment_pct=pct_dict["sentiment"][i],
            momentum_pct=pct_dict["momentum"][i],
            technical=calibrated_dict["technical"][i],
            fundamental=calibrated_dict["fundamental"][i],
            capital=calibrated_dict["capital"][i],
            sentiment=calibrated_dict["sentiment"][i],
            momentum=calibrated_dict["momentum"][i],
            total=stretched_totals[i],
            total_pct=0.0,  # 稍后填充
            **{k: v for k, v in details.items()},
        ))

    # 按 total 降序排列并填充 total_pct
    results.sort(key=lambda x: x.total, reverse=True)
    for i, r in enumerate(results):
        r.total_pct = round((1 - i / n) * 100, 1)

    return results


def optimize_calibration_params(
    backtest_results: list[dict[str, float]],
    param_grid: dict[str, list[float]],
) -> CalibrationParams:
    """通过回测结果优化校准参数（网格搜索）.

    Args:
        backtest_results: 不同参数下的回测结果.
        param_grid: 参数网格 {"pct_weight": [...], "target_std": [...]}.

    Returns:
        最优 CalibrationParams.
    """
    if not backtest_results:
        return CalibrationParams()

    # 按夏普比率降序，取最优
    best = max(backtest_results, key=lambda r: r.get("sharpe_ratio", -999))
    return CalibrationParams(
        pct_weight=float(best.get("pct_weight", 0.5)),
        target_std=float(best.get("target_std", 20.0)),
        target_mean=float(best.get("target_mean", 50.0)),
        tail_expand=float(best.get("tail_expand", 1.5)),
    )
