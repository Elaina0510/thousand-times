"""fundamental_analysis.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config import FundamentalWeightConfig
from fundamental_analysis import FundamentalData, calc_fundamental_score, get_fundamental_data


def _make_financial_indicator() -> dict:
    """创建测试用财务指标数据（BaoStock dict 格式）。

    注意：get_fundamental_data 中 pe_ttm 存储 ROE，pb 存储 EPS。
    """
    return {
        "roeAvg": 0.18,       # ROE 18%  → pe_ttm = 18.0
        "epsTTM": 2.5,        # EPS 2.5  → pb = 2.5
        "profit_growth": 25.0,
        "revenue_growth": 20.0,
    }


class TestGetFundamentalData:
    """基本面数据获取测试。"""

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_normal_data(self, mock_fetch: MagicMock) -> None:
        """正常获取基本面数据。"""
        mock_fetch.return_value = _make_financial_indicator()

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        # ROE 0.18 → pe_ttm = 18.0
        assert result.pe_ttm == pytest.approx(18.0)
        # EPS 2.5 → pb = 2.5
        assert result.pb == pytest.approx(2.5)
        assert result.profit_growth == 25.0
        assert result.revenue_growth == 20.0

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_empty_data(self, mock_fetch: MagicMock) -> None:
        """空数据返回默认值。"""
        mock_fetch.return_value = {}

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        assert result.pe_ttm == 0.0
        assert result.pb == 0.0
        assert result.profit_growth is None

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_missing_fields(self, mock_fetch: MagicMock) -> None:
        """缺少字段时返回默认值。"""
        mock_fetch.return_value = {"roeAvg": 0.15}

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        assert result.pe_ttm == pytest.approx(15.0)
        assert result.pb == 0.0
        assert result.profit_growth is None

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_api_failure(self, mock_fetch: MagicMock) -> None:
        """API失败时返回默认值。"""
        mock_fetch.side_effect = Exception("API 超时")

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        assert result.pe_ttm == 0.0
        assert result.profit_growth is None

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_nan_values(self, mock_fetch: MagicMock) -> None:
        """None 值处理。"""
        data = _make_financial_indicator()
        data["profit_growth"] = None
        mock_fetch.return_value = data

        result = get_fundamental_data("600519")

        assert result.profit_growth is None


class TestCalcFundamentalScore:
    """基本面评分测试。

    评分规则（适配 BaoStock 数据）：
    - ROE（pe_ttm字段）: >15% → +8, 10~15% → +3, <10% → 0
    - EPS（pb字段）: >0 → +5
    - 净利润同比: >20% → +10, 0~20% → +5, <0% → 0
    - 营收同比: >15% → +7, 0~15% → +3, <0% → 0
    """

    def test_full_score(self) -> None:
        """满分场景：ROE=20, EPS=2.5, 净利润+25%, 营收+20%。"""
        data = FundamentalData(
            pe_ttm=20.0,    # ROE 20% → +8
            pb=2.5,         # EPS > 0 → +5
            market_cap=100e8,
            profit_growth=25.0,   # >20% → +10
            revenue_growth=20.0,  # >15% → +7
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # 8 + 5 + 10 + 7 = 30
        assert score == 30.0

    def test_zero_score(self) -> None:
        """零分场景：ROE=5%, EPS=-1, 净利润-10%, 营收-5%。"""
        data = FundamentalData(
            pe_ttm=5.0,     # ROE 5% → 0
            pb=-1.0,        # EPS < 0 → 0
            market_cap=100e8,
            profit_growth=-10.0,  # 下降 → 0
            revenue_growth=-5.0,  # 下降 → 0
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        assert score == 0.0

    def test_roe_mid_range(self) -> None:
        """ROE 中等场景：ROE=12%, EPS=3, 净利润+25%, 营收+20%。"""
        data = FundamentalData(
            pe_ttm=12.0,    # ROE 12% → +3
            pb=3.0,         # EPS > 0 → +5
            market_cap=100e8,
            profit_growth=25.0,   # >20% → +10
            revenue_growth=20.0,  # >15% → +7
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # 3 + 5 + 10 + 7 = 25
        assert score == 25.0

    def test_missing_data(self) -> None:
        """数据缺失场景：ROE=20, EPS=3, 无增长率数据。"""
        data = FundamentalData(
            pe_ttm=20.0,    # ROE 20% → +8
            pb=3.0,         # EPS > 0 → +5
            market_cap=100e8,
            profit_growth=None,   # 缺失 → 0
            revenue_growth=None,  # 缺失 → 0
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # 8 + 5 + 0 + 0 = 13
        assert score == 13.0

    def test_profit_stable_growth(self) -> None:
        """净利润稳定增长场景。"""
        data = FundamentalData(
            pe_ttm=20.0,    # ROE 20% → +8
            pb=3.0,         # EPS > 0 → +5
            market_cap=100e8,
            profit_growth=10.0,   # 0~20% → +5
            revenue_growth=20.0,  # >15% → +7
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # 8 + 5 + 5 + 7 = 25
        assert score == 25.0

    def test_revenue_stable_growth(self) -> None:
        """营收稳定增长场景。"""
        data = FundamentalData(
            pe_ttm=20.0,    # ROE 20% → +8
            pb=3.0,         # EPS > 0 → +5
            market_cap=100e8,
            profit_growth=25.0,   # >20% → +10
            revenue_growth=10.0,  # 0~15% → +3
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # 8 + 5 + 10 + 3 = 26
        assert score == 26.0
