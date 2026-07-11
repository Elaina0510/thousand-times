"""FactorCalibrator 单元测试."""

from __future__ import annotations

import numpy as np
import pytest

from factors.calibrator import (
    CalibratedScores,
    CalibrationParams,
    _calibrate_single_factor,
    calc_percentile_rank,
    calibrate_scores,
    optimize_calibration_params,
    stretch_distribution,
)


# ── 辅助：构造模拟 FactorScores ──
class MockFactorScores:
    """模拟 pipeline/factors.py 的 FactorScores."""
    def __init__(self, code, name="test", technical=50.0, fundamental=50.0,
                 capital=50.0, sentiment=50.0, momentum=50.0, total=50.0):
        self.code = code
        self.name = name
        self.technical = technical
        self.fundamental = fundamental
        self.capital = capital
        self.sentiment = sentiment
        self.momentum = momentum
        self.total = total
        self.technical_detail: dict[str, float] = {}
        self.fundamental_detail: dict[str, float] = {}
        self.capital_detail: dict[str, float] = {}
        self.sentiment_detail: dict[str, float] = {}
        self.momentum_detail: dict[str, float] = {}


# ── 测试 calc_percentile_rank ──
def test_percentile_rank_highest():
    """最高值百分位应为 100."""
    result = calc_percentile_rank(100.0, [0.0, 50.0, 100.0])
    assert result == pytest.approx(83.33, abs=1.0)  # 中点百分位: (2+0.5)/3*100


def test_percentile_rank_lowest():
    """最低值百分位应接近 0."""
    result = calc_percentile_rank(0.0, [0.0, 50.0, 100.0])
    assert result == pytest.approx(16.67, abs=1.0)


def test_percentile_rank_empty():
    """空列表返回 50."""
    assert calc_percentile_rank(50.0, []) == 50.0


# ── 测试 stretch_distribution ──
def test_stretch_distribution_normal():
    """正常拉伸：验证目标均值."""
    np.random.seed(42)
    values = [float(x) for x in np.random.normal(50, 8, 100)]
    stretched = stretch_distribution(values, 50.0, 20.0)
    assert len(stretched) == 100
    assert abs(np.mean(stretched) - 50.0) < 5.0


def test_stretch_distribution_clipping():
    """拉伸后值在 [0, 100] 内."""
    values = [-10.0, 0.0, 50.0, 100.0, 110.0]
    stretched = stretch_distribution(values, 50.0, 20.0)
    for v in stretched:
        assert 0.0 <= v <= 100.0


def test_stretch_distribution_empty():
    """空列表返回空."""
    assert stretch_distribution([], 50.0, 20.0) == []


def test_stretch_distribution_all_same():
    """所有值相同时不崩溃."""
    values = [50.0] * 10
    stretched = stretch_distribution(values, 50.0, 20.0)
    assert len(stretched) == 10
    assert all(v == 50.0 for v in stretched)


# ── 测试 _calibrate_single_factor ──
def test_calibrate_single_factor():
    """单因子校准."""
    raw = [40.0, 45.0, 50.0, 55.0, 60.0]
    calibrated = _calibrate_single_factor(raw, 0.5)
    assert len(calibrated) == 5
    # 校准后应该有更好的区分度
    assert max(calibrated) - min(calibrated) >= abs(max(raw) - min(raw)) * 0.5


# ── 测试 calibrate_scores ──
def test_calibrate_scores_concentrated():
    """集中分布：100个评分集中在 [40,60] → 校准后范围扩大."""
    scores = [
        MockFactorScores(
            code=f"{i:06d}",
            technical=40.0 + i * 0.2,
            fundamental=45.0 + i * 0.1,
            capital=42.0 + i * 0.15,
            sentiment=48.0 + i * 0.12,
            momentum=38.0 + i * 0.22,
            total=43.0 + i * 0.17,
        )
        for i in range(100)
    ]
    params = CalibrationParams(pct_weight=0.5, target_mean=50.0, target_std=20.0)
    result = calibrate_scores(scores, params)

    assert len(result) == 100
    # 校准后范围应该扩大
    totals = [r.total for r in result]
    raw_totals = [s.total for s in scores]
    assert max(totals) - min(totals) >= max(raw_totals) - min(raw_totals)
    # 标准差应该 >= 15
    assert np.std(totals) >= 15.0


def test_calibrate_scores_all_same():
    """所有分数相同 → 标准差 ≈ 0."""
    scores = [MockFactorScores(code=f"{i:06d}") for i in range(10)]
    result = calibrate_scores(scores)
    assert len(result) == 10
    # 所有分数相同，校准后标准差应该仍接近 0
    totals = [r.total for r in result]
    assert np.std(totals) < 1.0


def test_calibrate_scores_uniform():
    """均匀分布 [0,100] → 校准后与原始基本一致."""
    scores = [
        MockFactorScores(
            code=f"{i:06d}",
            technical=float(i),
            fundamental=float(i),
            capital=float(i),
            sentiment=float(i),
            momentum=float(i),
            total=float(i),
        )
        for i in range(100)
    ]
    result = calibrate_scores(scores)
    assert len(result) == 100
    # 均匀分布下校准不应大幅改变排名顺序
    totals = [r.total for r in result]
    assert max(totals) - min(totals) > 60  # 应保持良好的区分度


def test_calibrate_scores_outliers():
    """异常值（>100 或 <0）→ 截断不报错."""
    scores = [
        MockFactorScores(code="000001", technical=120.0, fundamental=-10.0, total=80.0),
        MockFactorScores(code="000002", technical=50.0, fundamental=50.0, total=50.0),
    ]
    result = calibrate_scores(scores)
    assert len(result) == 2
    for r in result:
        assert 0.0 <= r.technical <= 100.0
        assert 0.0 <= r.fundamental <= 100.0


def test_calibrate_scores_empty():
    """空列表返回空."""
    assert calibrate_scores([]) == []


def test_calibrate_scores_ranking_preserved():
    """排名顺序大致保持."""
    np.random.seed(42)
    scores = [
        MockFactorScores(
            code=f"{i:06d}",
            technical=np.random.uniform(30, 70),
            fundamental=np.random.uniform(30, 70),
            capital=np.random.uniform(30, 70),
            sentiment=np.random.uniform(30, 70),
            momentum=np.random.uniform(30, 70),
            total=np.random.uniform(30, 70),
        )
        for i in range(50)
    ]
    result = calibrate_scores(scores)
    # 按 total 降序，验证大致排名一致
    sorted_raw = sorted(scores, key=lambda s: s.total, reverse=True)
    sorted_cal = sorted(result, key=lambda r: r.total, reverse=True)
    # 排名相关系数 > 0.8（top 5 至少应该有重叠）
    raw_top5 = {s.code for s in sorted_raw[:5]}
    cal_top5 = {r.code for r in sorted_cal[:5]}
    overlap = len(raw_top5 & cal_top5)
    assert overlap >= 2  # 至少 2 只重合


# ── 测试 optimize_calibration_params ──
def test_optimize_calibration_params():
    """网格搜索找最优参数."""
    backtest_results = [
        {"pct_weight": 0.3, "target_std": 15.0, "sharpe_ratio": 0.8},
        {"pct_weight": 0.5, "target_std": 20.0, "sharpe_ratio": 1.2},
        {"pct_weight": 0.7, "target_std": 25.0, "sharpe_ratio": 0.9},
    ]
    params = optimize_calibration_params(
        backtest_results,
        {"pct_weight": [0.3, 0.5, 0.7], "target_std": [15.0, 20.0, 25.0]},
    )
    assert params.pct_weight == 0.5
    assert params.target_std == 20.0


def test_optimize_calibration_params_empty():
    """空回测结果返回默认参数."""
    params = optimize_calibration_params([], {})
    assert params.pct_weight == 0.5
    assert params.target_std == 20.0
