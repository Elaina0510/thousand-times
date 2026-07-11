"""DataValidator 单元测试."""

from __future__ import annotations

import pandas as pd
import pytest

from data_quality.validator import (
    DataQualityReport,
    FieldQuality,
    QualityLevel,
    _validate_capital_flow,
    _validate_fundamental,
    _validate_kline,
    _validate_sentiment,
    detect_default_values,
    flag_anomalous_stocks,
    validate_bundle,
)


# ── 辅助：构造模拟 DataBundle ──
class MockFundamentalData:
    """模拟基本面数据."""
    def __init__(self, roe=15.0, eps=1.5, profit_growth=20.0, revenue_growth=15.0):
        self.roe = roe
        self.eps = eps
        self.profit_growth = profit_growth
        self.revenue_growth = revenue_growth


class MockDataBundle:
    """模拟 DataBundle."""
    def __init__(
        self,
        kline_cache=None,
        fundamental_cache=None,
        north_flow=None,
        sector_flow=None,
        limit_up=50,
        limit_down=10,
        ad_ratio=5.0,
    ):
        self.kline_cache = kline_cache or {}
        self.fundamental_cache = fundamental_cache or {}
        self.north_flow = north_flow if north_flow is not None else pd.DataFrame()
        self.sector_flow = sector_flow if sector_flow is not None else pd.DataFrame()
        self.limit_up_count = limit_up
        self.limit_down_count = limit_down
        self.advance_decline_ratio = ad_ratio


def _make_kline_df(rows=60, close_col="收盘"):
    """创建模拟 K 线 DataFrame."""
    import numpy as np
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    return pd.DataFrame({
        "日期": dates,
        close_col: np.random.randn(rows).cumsum() + 10,
        "最高": np.random.randn(rows).cumsum() + 11,
        "最低": np.random.randn(rows).cumsum() + 9,
        "成交量": np.random.randint(10000, 100000, rows),
    })


# ── 测试 detect_default_values ──
def test_detect_default_values_no_defaults():
    """测试无默认值场景."""
    series = [15.0, 20.0, 25.0, 30.0, 35.0]
    assert detect_default_values(series) == 0


def test_detect_default_values_with_zeros():
    """测试包含大量零值."""
    series = [0.0] * 40 + [15.0] * 60  # 40% 是 0.0
    result = detect_default_values(series)
    assert result == 40  # 40 个零值，占比 > 30%


def test_detect_default_values_empty():
    """测试空序列."""
    assert detect_default_values([]) == 0


def test_detect_default_values_below_threshold():
    """测试默认值未超过阈值."""
    series = [0.0] * 20 + [15.0] * 80  # 20% 是 0.0，未超过 30%
    result = detect_default_values(series)
    assert result == 0


# ── 测试 flag_anomalous_stocks ──
def test_flag_anomalous_stocks():
    """测试异常股票标记."""
    report = DataQualityReport(
        timestamp="2026-07-11",
        kline_quality={
            "000001": FieldQuality(
                field_name="kline_000001", level=QualityLevel.GOOD,
                valid_count=60, total_count=60, default_count=0,
                mean_value=10.0, std_value=1.0,
            ),
            "000002": FieldQuality(
                field_name="kline_000002", level=QualityLevel.BAD,
                valid_count=0, total_count=10, default_count=0,
                mean_value=None, std_value=None,
                anomalies=["K线数据仅 10 行"],
            ),
        },
        fundamental_quality={
            "000001": FieldQuality(
                field_name="fund_000001", level=QualityLevel.GOOD,
                valid_count=1, total_count=1, default_count=0,
                mean_value=15.0, std_value=None,
            ),
            "000002": FieldQuality(
                field_name="fund_000002", level=QualityLevel.BAD,
                valid_count=0, total_count=1, default_count=2,
                mean_value=None, std_value=None,
                anomalies=["ROE 为 0"],
            ),
        },
    )
    anomalous = flag_anomalous_stocks(report)
    assert "000002" in anomalous


# ── 测试 validate_bundle 全部正常 ──
def test_validate_bundle_all_good():
    """测试全部数据正常场景."""
    kline = {"000001": _make_kline_df(60)}
    fund = {"000001": MockFundamentalData(roe=15.0, eps=1.5, profit_growth=20.0, revenue_growth=10.0)}
    nf = pd.DataFrame({"当日成交净买额": [1e8, 2e8, 3e8, 4e8, 5e8]})
    sf = pd.DataFrame({"行业": ["银行"], "涨跌幅": [1.5]})
    bundle = MockDataBundle(kline_cache=kline, fundamental_cache=fund, north_flow=nf, sector_flow=sf)
    report = validate_bundle(bundle)
    assert report.overall_level == QualityLevel.GOOD


# ── 测试 K 线不足 ──
def test_validate_bundle_kline_insufficient():
    """测试 K 线数据不足（< 20 行）."""
    kline = {"000001": _make_kline_df(10)}
    bundle = MockDataBundle(kline_cache=kline)
    report = validate_bundle(bundle)
    assert report.kline_quality["000001"].level == QualityLevel.BAD


# ── 测试 K 线缺少收盘列 ──
def test_validate_bundle_kline_missing_close():
    """测试 K 线缺少收盘价列."""
    import numpy as np
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    df = pd.DataFrame({"日期": dates, "最高": [10] * 60, "最低": [9] * 60})
    kline = {"000001": df}
    bundle = MockDataBundle(kline_cache=kline)
    report = validate_bundle(bundle)
    assert report.kline_quality["000001"].level == QualityLevel.BAD


# ── 测试基本面全为默认值 ──
def test_validate_bundle_fundamental_all_defaults():
    """测试基本面全为默认值（roe=0, eps=0）."""
    fund = {"000001": MockFundamentalData(roe=0.0, eps=0.0, profit_growth=None, revenue_growth=None)}
    kline = {"000001": _make_kline_df(60)}
    bundle = MockDataBundle(kline_cache=kline, fundamental_cache=fund)
    report = validate_bundle(bundle)
    assert report.fundamental_quality["000001"].level == QualityLevel.BAD


# ── 测试混合异常 ──
def test_validate_bundle_mixed_anomalies():
    """测试混合异常场景."""
    kline = {
        "000001": _make_kline_df(60),
        "000002": _make_kline_df(10),  # 不足
    }
    fund = {
        "000001": MockFundamentalData(roe=15.0, eps=1.5),
        "000002": MockFundamentalData(roe=0.0, eps=0.0),
    }
    bundle = MockDataBundle(kline_cache=kline, fundamental_cache=fund)
    report = validate_bundle(bundle)
    # 000001 应该正常
    assert report.kline_quality["000001"].level == QualityLevel.GOOD
    # 000002 K 线 BAD
    assert report.kline_quality["000002"].level == QualityLevel.BAD
    # 不会崩溃
    assert report.details is not None


# ── 测试空 DataBundle ──
def test_validate_bundle_empty():
    """测试空 DataBundle 不崩溃."""
    bundle = MockDataBundle(kline_cache={}, fundamental_cache={})
    report = validate_bundle(bundle)
    # 空数据应该有合理的输出
    assert report.overall_level in (QualityLevel.GOOD, QualityLevel.DEGRADED)


# ── 测试情绪面异常 ──
def test_validate_sentiment_zero_data():
    """测试涨跌停数据均为 0."""
    result = _validate_sentiment(0, 0, 1.0)
    assert result.level == QualityLevel.DEGRADED
    assert any("均为 0" in a for a in result.anomalies)


def test_validate_sentiment_negative():
    """测试涨跌停负数."""
    result = _validate_sentiment(-5, -2, 2.5)
    # 负数会被检测到，但仍有有效数据量
    assert any("异常" in a for a in result.anomalies)


# ── 测试资金面异常 ──
def test_validate_capital_flow_empty():
    """测试资金面全部为空."""
    result = _validate_capital_flow(pd.DataFrame(), pd.DataFrame())
    assert result.level == QualityLevel.DEGRADED
    assert result.valid_count == 0


# ── 测试资金面正常 ──
def test_validate_capital_flow_normal():
    """测试资金面正常."""
    nf = pd.DataFrame({"当日成交净买额": [1e8, 2e8]})
    sf = pd.DataFrame({"行业": ["银行"]})
    result = _validate_capital_flow(nf, sf)
    assert result.level == QualityLevel.GOOD
    assert result.valid_count == 2


# ── 测试资金流全为 60 场景 ──
def test_validate_bundle_capital_score_default():
    """测试资金面评分为默认值 60 不被 validator 直接检测（由下游处理）."""
    # validator 检查的是资金流 DataFrame 是否为空，不检查具体评分值
    nf = pd.DataFrame({"当日成交净买额": [60.0] * 20})
    result = _validate_capital_flow(nf, pd.DataFrame({"行业": ["银行"]}))
    # 非空即为正常
    assert result.level != QualityLevel.BAD
