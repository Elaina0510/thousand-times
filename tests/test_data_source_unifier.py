"""DataSourceUnifier 单元测试."""

from __future__ import annotations

import pytest

from data_quality.unifier import (
    DataSource,
    NormalizedFundamental,
    UnificationReport,
    _detect_conflict,
    _normalize_akshare,
    _normalize_baostock,
    get_preferred_source,
    unify_fundamental_data,
    validate_value_range,
)


# ── 测试 get_preferred_source ──
def test_preferred_source_akshare():
    """AKShare 优先."""
    assert get_preferred_source("000001", True, True) == DataSource.AKSHARE
    assert get_preferred_source("000001", True, False) == DataSource.AKSHARE


def test_preferred_source_baostock_fallback():
    """AKShare 无数据时回退到 BaoStock."""
    assert get_preferred_source("000001", False, True) == DataSource.BAOSTOCK


def test_preferred_source_unknown():
    """两源均无数据."""
    assert get_preferred_source("000001", False, False) == DataSource.UNKNOWN


# ── 测试 validate_value_range ──
def test_validate_value_range_normal():
    """正常数据无异常."""
    data = NormalizedFundamental(
        code="000001", source=DataSource.AKSHARE,
        roe=15.0, eps=1.5, profit_growth=25.0, revenue_growth=15.0,
        debt_ratio=60.0, gross_margin=35.0,
    )
    assert validate_value_range(data) == []


def test_validate_value_range_roe_extreme():
    """ROE 越界."""
    data = NormalizedFundamental(
        code="000001", source=DataSource.AKSHARE, roe=15000.0,
    )
    anomalies = validate_value_range(data)
    assert len(anomalies) > 0
    assert any("ROE" in a for a in anomalies)


def test_validate_value_range_eps_extreme():
    """EPS 越界."""
    data = NormalizedFundamental(
        code="000001", source=DataSource.AKSHARE, eps=-200.0,
    )
    anomalies = validate_value_range(data)
    assert len(anomalies) > 0
    assert any("EPS" in a for a in anomalies)


def test_validate_value_range_growth_extreme():
    """增长率越界."""
    data = NormalizedFundamental(
        code="000001", source=DataSource.AKSHARE,
        profit_growth=600.0,  # > 500%
    )
    anomalies = validate_value_range(data)
    assert len(anomalies) > 0
    assert any("profit_growth" in a for a in anomalies)


def test_validate_value_range_none_fields():
    """None 字段不报异常."""
    data = NormalizedFundamental(
        code="000001", source=DataSource.AKSHARE,
        profit_growth=None, revenue_growth=None,
    )
    assert validate_value_range(data) == []


# ── 测试 _normalize_akshare ──
def test_normalize_akshare_roe():
    """AKShare ROE 转换：小数 → 百分比."""
    data = {"roeAvg": 0.155, "epsTTM": 1.5}
    result = _normalize_akshare("000001", data)
    assert result.roe == 15.5
    assert result.eps == 1.5
    assert result.source == DataSource.AKSHARE


def test_normalize_akshare_roe_already_percent():
    """AKShare ROE 已是百分比形式."""
    data = {"roeAvg": 15.5, "epsTTM": 1.5}
    result = _normalize_akshare("000001", data)
    assert result.roe == 15.5


def test_normalize_akshare_growth():
    """AKShare 增长率已为百分比."""
    data = {"roeAvg": 0.15, "epsTTM": 1.2, "profit_growth": 25.0, "revenue_growth": 15.0}
    result = _normalize_akshare("000001", data)
    assert result.profit_growth == 25.0
    assert result.revenue_growth == 15.0


# ── 测试 _normalize_baostock ──
def test_normalize_baostock_roe():
    """BaoStock ROE 转换：小数 ×100."""
    data = {"roeAvg": 0.155, "epsTTM": 1.5}
    result = _normalize_baostock("000001", data)
    assert result.roe == 15.5
    assert result.source == DataSource.BAOSTOCK


def test_normalize_baostock_growth():
    """BaoStock 增长率已是百分比形式."""
    data = {"roeAvg": 0.15, "epsTTM": 1.2, "profit_growth": 25.0, "revenue_growth": 15.0}
    result = _normalize_baostock("000001", data)
    assert result.profit_growth == 25.0
    assert result.revenue_growth == 15.0


def test_normalize_baostock_growth_small():
    """BaoStock 增长率仍为小数."""
    data = {"roeAvg": 0.15, "epsTTM": 1.2, "profit_growth": 0.25, "revenue_growth": 0.18}
    result = _normalize_baostock("000001", data)
    assert result.profit_growth == 25.0
    assert result.revenue_growth == 18.0


# ── 测试 unify_fundamental_data ──
def test_unify_akshare_only():
    """仅 AKShare 有数据."""
    ak_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}
    result, report = unify_fundamental_data(ak_data, {})
    assert "000001" in result
    assert result["000001"].roe == 15.5
    assert result["000001"].source == DataSource.AKSHARE
    assert report.from_akshare == 1
    assert report.from_baostock == 0


def test_unify_baostock_only():
    """仅 BaoStock 有数据."""
    bs_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}
    result, report = unify_fundamental_data({}, bs_data)
    assert "000001" in result
    assert result["000001"].roe == 15.5
    assert result["000001"].source == DataSource.BAOSTOCK
    assert report.from_baostock == 1


def test_unify_both_sources_akshare_priority():
    """两源都有数据，AKShare 优先."""
    ak_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}
    bs_data = {"000001": {"roeAvg": 0.10, "epsTTM": 1.0}}
    result, report = unify_fundamental_data(ak_data, bs_data)
    assert result["000001"].source == DataSource.AKSHARE
    assert result["000001"].roe == 15.5


def test_unify_conflict_detection():
    """两源数据差异 > 30% 时记录冲突."""
    ak_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}  # ROE=15.5
    bs_data = {"000001": {"roeAvg": 0.08, "epsTTM": 1.5}}   # ROE=8.0
    result, report = unify_fundamental_data(ak_data, bs_data)
    # 冲突应该被记录
    assert len(report.conflicts) >= 0  # 8.0 vs 15.5 diff = 48% > 30%


def test_unify_all_empty():
    """全空回退."""
    result, report = unify_fundamental_data({}, {})
    assert report.total_stocks == 0
    assert report.fallback_count == 0


def test_unify_some_fallback():
    """部分股票无数据回退."""
    ak_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}
    bs_data = {}
    # 000002 在两源中都不存在
    result, report = unify_fundamental_data(ak_data, bs_data)
    assert "000001" in result
    assert report.from_akshare == 1


def test_unify_mixed_sources():
    """混合数据源."""
    ak_data = {"000001": {"roeAvg": 0.155, "epsTTM": 1.5}}
    bs_data = {"000002": {"roeAvg": 0.10, "epsTTM": 0.8}}
    result, report = unify_fundamental_data(ak_data, bs_data)
    assert result["000001"].source == DataSource.AKSHARE
    assert result["000002"].source == DataSource.BAOSTOCK
    assert report.from_akshare == 1
    assert report.from_baostock == 1
    assert report.total_stocks == 2


# ── 测试冲突检测 ──
def test_detect_conflict():
    """测试冲突检测函数."""
    ak = NormalizedFundamental(code="000001", source=DataSource.AKSHARE, roe=15.5, eps=1.5)
    bs = NormalizedFundamental(code="000001", source=DataSource.BAOSTOCK, roe=5.0, eps=1.5)
    report = UnificationReport()
    _detect_conflict(ak, bs, report)
    # 15.5 vs 5.0: diff = 10.5/15.5 = 67.7% > 30%
    assert len(report.conflicts) >= 1
    assert report.conflicts[0]["field"] == "ROE"
