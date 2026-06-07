"""etf_analyzer.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import AppConfig, EtfFundFlowWeightConfig
from etf_analyzer import EtfInfo, calc_fund_flow_score, get_etf_fund_flow, get_etf_pool


def _make_etf_hist() -> pd.DataFrame:
    """创建测试用ETF历史数据。"""
    return pd.DataFrame(
        {
            "日期": pd.date_range("2026-01-01", periods=10, freq="B"),
            "名称": ["半导体ETF"] * 10,
            "最新价": [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4],
            "涨跌幅": [1.0, 2.0, 1.5, 2.5, 1.8, 2.2, 1.6, 2.0, 1.9, 2.1],
        }
    )


def _make_etf_fund_daily() -> pd.DataFrame:
    """创建测试用ETF份额数据。"""
    return pd.DataFrame(
        {
            "日期": pd.date_range("2026-01-01", periods=5, freq="B"),
            "份额变化": [1000000, 2000000, 1500000, 3000000, 2500000],
        }
    )


class TestGetEtfPool:
    """ETF池获取测试。"""

    @patch("etf_analyzer._fetch_etf_hist")
    def test_normal_data(self, mock_hist: MagicMock) -> None:
        """正常获取ETF池。"""
        mock_hist.return_value = _make_etf_hist()

        config = AppConfig(etf_pool=["512480", "516160"])
        result = get_etf_pool(config)

        assert len(result) == 2
        assert all(isinstance(etf, EtfInfo) for etf in result)
        assert result[0].code == "512480"
        assert result[1].code == "516160"

    @patch("etf_analyzer._fetch_etf_hist")
    def test_empty_data(self, mock_hist: MagicMock) -> None:
        """空数据时跳过该ETF。"""
        mock_hist.return_value = pd.DataFrame()

        config = AppConfig(etf_pool=["512480"])
        result = get_etf_pool(config)

        assert len(result) == 0

    @patch("etf_analyzer._fetch_etf_hist")
    def test_api_failure(self, mock_hist: MagicMock) -> None:
        """API失败时跳过该ETF。"""
        mock_hist.side_effect = Exception("API 超时")

        config = AppConfig(etf_pool=["512480"])
        result = get_etf_pool(config)

        assert len(result) == 0


class TestCalcFundFlowScore:
    """资金流向评分测试。"""

    def test_continuous_growth(self) -> None:
        """连续增长评分在 8~10 范围。"""
        share_changes = [1000000, 2000000, 1500000, 3000000, 2500000]
        score = calc_fund_flow_score(share_changes)
        assert 8 <= score <= 10

    def test_continuous_decline(self) -> None:
        """连续减少评分在 0~2 范围。"""
        share_changes = [-1000000, -2000000, -1500000, -3000000, -2500000]
        score = calc_fund_flow_score(share_changes)
        assert 0 <= score <= 2

    def test_flat(self) -> None:
        """持平评分 = 3。"""
        share_changes = [0, 0, 0, 0, 0]
        score = calc_fund_flow_score(share_changes)
        assert score == 3.0

    def test_overall_growth_with_fluctuation(self) -> None:
        """总体增长但有波动。"""
        share_changes = [1000000, -500000, 2000000, -1000000, 3000000]
        score = calc_fund_flow_score(share_changes)
        assert 4 <= score <= 7

    def test_overall_decline_with_fluctuation(self) -> None:
        """总体减少但有波动。"""
        share_changes = [-1000000, 500000, -2000000, 1000000, -3000000]
        score = calc_fund_flow_score(share_changes)
        assert 0 <= score <= 2

    def test_empty_list(self) -> None:
        """空列表返回默认持平。"""
        score = calc_fund_flow_score([])
        assert score == 3.0


class TestGetEtfFundFlow:
    """ETF资金流向获取测试。"""

    @patch("etf_analyzer._fetch_etf_fund_daily")
    def test_normal_data(self, mock_fetch: MagicMock) -> None:
        """正常获取资金流向评分。"""
        mock_fetch.return_value = _make_etf_fund_daily()

        score = get_etf_fund_flow("512480", days=5)

        assert 0 <= score <= 10

    @patch("etf_analyzer._fetch_etf_fund_daily")
    def test_empty_data(self, mock_fetch: MagicMock) -> None:
        """空数据返回默认持平。"""
        mock_fetch.return_value = pd.DataFrame()

        score = get_etf_fund_flow("512480", days=5)

        assert score == 3.0

    @patch("etf_analyzer._fetch_etf_fund_daily")
    def test_api_failure(self, mock_fetch: MagicMock) -> None:
        """API失败返回默认持平。"""
        mock_fetch.side_effect = Exception("API 超时")

        score = get_etf_fund_flow("512480", days=5)

        assert score == 3.0
