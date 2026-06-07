"""fundamental_analysis.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import FundamentalWeightConfig
from fundamental_analysis import FundamentalData, calc_fundamental_score, get_fundamental_data


def _make_financial_data() -> pd.DataFrame:
    """创建测试用财务数据。"""
    return pd.DataFrame(
        {
            "摊薄每股收益": [2.5],
            "净资产收益率": [15.0],
            "净利润同比增长率": [25.0],
            "营收同比增长率": [20.0],
        }
    )


class TestGetFundamentalData:
    """基本面数据获取测试。"""

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_normal_data(self, mock_fetch: MagicMock) -> None:
        """正常获取基本面数据。"""
        mock_fetch.return_value = _make_financial_data()

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        assert result.profit_growth == 25.0
        assert result.revenue_growth == 20.0

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_empty_data(self, mock_fetch: MagicMock) -> None:
        """空数据返回默认值。"""
        mock_fetch.return_value = pd.DataFrame()

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
        assert result.pe_ttm == 0.0
        assert result.profit_growth is None

    @patch("fundamental_analysis._fetch_financial_indicator")
    def test_missing_columns(self, mock_fetch: MagicMock) -> None:
        """缺少列时返回默认值。"""
        mock_fetch.return_value = pd.DataFrame({"其他列": [1.0]})

        result = get_fundamental_data("600519")

        assert isinstance(result, FundamentalData)
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
        """NaN值处理。"""
        data = _make_financial_data()
        data.loc[0, "净利润同比增长率"] = float("nan")
        mock_fetch.return_value = data

        result = get_fundamental_data("600519")

        assert result.profit_growth is None


class TestCalcFundamentalScore:
    """基本面评分测试。"""

    def test_full_score(self) -> None:
        """满分场景。"""
        data = FundamentalData(
            pe_ttm=25.0,
            pb=3.0,
            market_cap=100e8,
            profit_growth=25.0,
            revenue_growth=20.0,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # PE: 8, PB: 5, 净利润: 10, 营收: 7 = 30
        assert score == 30.0

    def test_zero_score(self) -> None:
        """零分场景。"""
        data = FundamentalData(
            pe_ttm=80.0,
            pb=10.0,
            market_cap=100e8,
            profit_growth=-10.0,
            revenue_growth=-5.0,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        assert score == 0.0

    def test_pe_mid_range(self) -> None:
        """PE偏高场景。"""
        data = FundamentalData(
            pe_ttm=45.0,
            pb=3.0,
            market_cap=100e8,
            profit_growth=25.0,
            revenue_growth=20.0,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # PE: 3, PB: 5, 净利润: 10, 营收: 7 = 25
        assert score == 25.0

    def test_missing_data(self) -> None:
        """数据缺失场景。"""
        data = FundamentalData(
            pe_ttm=25.0,
            pb=3.0,
            market_cap=100e8,
            profit_growth=None,
            revenue_growth=None,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # PE: 8, PB: 5, 净利润: 0, 营收: 0 = 13
        assert score == 13.0

    def test_profit_stable_growth(self) -> None:
        """净利润稳定增长场景。"""
        data = FundamentalData(
            pe_ttm=25.0,
            pb=3.0,
            market_cap=100e8,
            profit_growth=10.0,
            revenue_growth=20.0,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # PE: 8, PB: 5, 净利润: 5, 营收: 7 = 25
        assert score == 25.0

    def test_revenue_stable_growth(self) -> None:
        """营收稳定增长场景。"""
        data = FundamentalData(
            pe_ttm=25.0,
            pb=3.0,
            market_cap=100e8,
            profit_growth=25.0,
            revenue_growth=10.0,
        )
        weights = FundamentalWeightConfig()
        score = calc_fundamental_score(data, weights)
        # PE: 8, PB: 5, 净利润: 10, 营收: 3 = 26
        assert score == 26.0
