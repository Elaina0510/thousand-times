"""IndustryRotationAnalyzer 单元测试."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factors.industry_rotation import (
    EXTENDED_INDUSTRY_ETF_MAP,
    IndustryMomentum,
    IndustryScoreAdjustment,
    RotationSignal,
    _calc_industry_returns,
    _calc_trend_strength,
    _match_industry,
    analyze_industry_rotation,
    calc_industry_adjustments,
    detect_rotation_pattern,
)


# ── 辅助函数 ──
def _make_kline(returns=None, rows=80, close_col="收盘"):
    """创建模拟 K 线，支持指定各日收益率."""
    if returns is None:
        returns = [0.5] * rows
    prices = [10.0]
    for r in returns[: rows - 1]:
        prices.append(prices[-1] * (1 + r / 100))
    dates = pd.date_range("2026-01-01", periods=len(prices), freq="B")
    df = pd.DataFrame({
        "日期": dates,
        close_col: prices,
        "最高": [p * 1.02 for p in prices],
        "最低": [p * 0.98 for p in prices],
        "成交量": np.random.randint(10000, 100000, len(prices)),
    })
    return df


# ── 测试 _calc_industry_returns ──
def test_calc_industry_returns():
    """测试收益率计算."""
    kline = _make_kline(rows=80)
    returns = _calc_industry_returns(kline, [1, 5, 20])
    assert 1 in returns
    assert 5 in returns
    assert 20 in returns


def test_calc_industry_returns_empty():
    """空K线返回 0."""
    returns = _calc_industry_returns(pd.DataFrame(), [1, 5, 20])
    assert returns[1] == 0.0


# ── 测试 _calc_trend_strength ──
def test_calc_trend_strength_bullish():
    """多头排列."""
    kline = _make_kline(rows=80)
    strength, direction = _calc_trend_strength(kline)
    assert strength > 50
    assert direction == "up"


def test_calc_trend_strength_empty():
    """空K线."""
    strength, direction = _calc_trend_strength(pd.DataFrame())
    assert strength == 50.0
    assert direction == "sideways"


# ── 测试 detect_rotation_pattern ──
def test_detect_rotation_broad_up():
    """普涨模式."""
    history = [
        {"name": f"行业{i}", "ret_20d": np.random.uniform(2, 10)}
        for i in range(10)
    ]
    assert detect_rotation_pattern(history) == "broad_up"


def test_detect_rotation_broad_down():
    """普跌模式."""
    history = [
        {"name": f"行业{i}", "ret_20d": np.random.uniform(-10, -2)}
        for i in range(10)
    ]
    assert detect_rotation_pattern(history) == "broad_down"


def test_detect_rotation_growth():
    """成长轮动."""
    history = [
        {"name": "电子", "ret_20d": 8.0},
        {"name": "半导体", "ret_20d": 10.0},
        {"name": "食品饮料", "ret_20d": -2.0},
        {"name": "医药生物", "ret_20d": -3.0},
        {"name": "钢铁", "ret_20d": 1.0},
    ]
    assert detect_rotation_pattern(history) == "growth_rotation"


def test_detect_rotation_empty():
    """空数据."""
    assert detect_rotation_pattern([]) == "no_pattern"


# ── 测试 analyze_industry_rotation ──
def test_analyze_industry_rotation_normal():
    """正常行业轮动分析."""
    etf_cache = {
        "512480": _make_kline([0.3] * 80),  # 半导体
        "512010": _make_kline([-0.1] * 80),   # 医药
        "512800": _make_kline([0.1] * 80),    # 银行
    }
    sector_flow = pd.DataFrame({
        "名称": ["电子", "医药", "银行"],
        "主力净流入-净额": [5.0, -2.0, 1.0],
    })
    industry_stocks = {
        "电子": ["000001", "000002"],
        "医药生物": ["000003"],
        "银行": ["000004", "000005"],
    }
    momentum_list, rotation = analyze_industry_rotation(
        etf_cache, sector_flow, industry_stocks,
    )
    assert len(momentum_list) == 3
    # 半导体/电子应该领涨
    assert len(rotation.leading_industries) > 0
    assert rotation.description != ""


def test_analyze_industry_rotation_empty_etf():
    """空 ETF 缓存不崩溃."""
    momentum_list, rotation = analyze_industry_rotation(
        {}, pd.DataFrame(), {"电子": ["000001"]},
    )
    assert len(momentum_list) >= 0  # 至少不崩溃


def test_analyze_industry_rotation_no_etf_match():
    """行业无对应 ETF."""
    etf_cache = {}
    industry_stocks = {"纺织服装": ["000001"]}
    momentum_list, rotation = analyze_industry_rotation(
        etf_cache, pd.DataFrame(), industry_stocks,
    )
    # 应该有动量数据（即使没有 ETF K 线），都应该是默认值
    assert len(momentum_list) == 1
    assert momentum_list[0].industry_name == "纺织服装"
    assert momentum_list[0].ret_20d == 0.0


# ── 测试 calc_industry_adjustments ──
def test_calc_industry_adjustments_leading():
    """领涨行业：adjustment 为正."""
    momentum = [
        IndustryMomentum(
            industry_name="电子", etf_code="512480", stock_count=10,
            ret_20d=8.0, rank_20d=1, rank_5d=1, trend_direction="up",
            fund_flow_5d=5.0,
        ),
        IndustryMomentum(
            industry_name="医药", etf_code="512010", stock_count=5,
            ret_20d=-3.0, rank_20d=5, rank_5d=5, trend_direction="down",
            fund_flow_5d=-2.0,
        ),
    ]
    stock_pool = pd.DataFrame({
        "code": ["000001", "000003"],
        "name": ["测试A", "测试B"],
        "industry": ["电子", "医药"],
    })
    adjustments = calc_industry_adjustments(stock_pool, momentum)
    assert len(adjustments) == 2
    # 电子行业应该获得正调整
    elec_adj = next(a for a in adjustments if a.code == "000001")
    assert elec_adj.adjustment > 0
    # 医药行业应该获得负调整
    med_adj = next(a for a in adjustments if a.code == "000003")
    assert med_adj.adjustment <= 0


def test_calc_industry_adjustments_no_match():
    """无匹配行业使用中性调整."""
    momentum = [IndustryMomentum(industry_name="电子", ret_20d=5.0, rank_20d=1)]
    stock_pool = pd.DataFrame({
        "code": ["000001"],
        "name": ["测试"],
        "industry": ["未知行业"],
    })
    adjustments = calc_industry_adjustments(stock_pool, momentum)
    assert len(adjustments) == 1
    assert adjustments[0].adjustment == 0.0


def test_calc_industry_adjustments_empty_momentum():
    """空动量列表."""
    stock_pool = pd.DataFrame({"code": ["000001"], "name": ["测试"], "industry": ["电子"]})
    adjustments = calc_industry_adjustments(stock_pool, [])
    assert adjustments == []


def test_calc_industry_adjustments_bounds():
    """调整量在 [-10, +10] 范围内."""
    # 极端场景：所有行业动量相同
    momentum = [
        IndustryMomentum(
            industry_name=f"行业{i}", rank_20d=i + 1,
            ret_20d=0.0, fund_flow_5d=100000.0, trend_direction="up",
        )
        for i in range(30)
    ]
    stock_pool = pd.DataFrame({
        "code": [f"{i:06d}" for i in range(30)],
        "name": [f"测试{i}" for i in range(30)],
        "industry": [f"行业{i}" for i in range(30)],
    })
    adjustments = calc_industry_adjustments(stock_pool, momentum)
    for a in adjustments:
        assert -10.0 <= a.adjustment <= 10.0, f"adjustment {a.adjustment} out of bounds"


# ── 测试扩展映射 ──
def test_extended_industry_etf_map_coverage():
    """扩展映射覆盖关键行业."""
    key_industries = ["电子", "医药生物", "银行", "有色金属", "钢铁", "化工",
                      "汽车", "家用电器", "农林牧渔", "公用事业", "传媒"]
    for ind in key_industries:
        assert ind in EXTENDED_INDUSTRY_ETF_MAP, f"缺少 {ind}"


# ── 测试 _match_industry ──
def test_match_industry_exact():
    """精确匹配."""
    mom_map = {"电子": IndustryMomentum(industry_name="电子")}
    result = _match_industry("电子", "", mom_map)
    assert result is not None
    assert result.industry_name == "电子"


def test_match_industry_partial():
    """部分匹配."""
    mom_map = {"医药生物": IndustryMomentum(industry_name="医药生物")}
    result = _match_industry("医药", "", mom_map)
    assert result is not None
