"""stock_filter.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import FilterConfig
from stock_filter import get_stock_pool


def _make_stock_data() -> pd.DataFrame:
    """创建测试用股票数据。"""
    return pd.DataFrame(
        {
            "代码": ["000001", "600519", "000002", "601318", "000858"],
            "名称": ["平安银行", "贵州茅台", "万科A", "中国平安", "五粮液"],
            "总市值": [300e8, 2000e8, 250e8, 1500e8, 800e8],
            "市盈率-动态": [8.5, 28.5, 12.0, 15.0, 25.0],
            "市净率": [0.8, 10.5, 1.2, 2.0, 8.0],
            "最新价": [12.5, 1800.0, 15.0, 50.0, 150.0],
            "涨跌幅": [1.5, -0.5, 2.0, 0.8, -1.2],
        }
    )


def _make_stock_info() -> pd.DataFrame:
    """创建测试用股票信息。"""
    return pd.DataFrame(
        {
            "代码": ["000001", "600519", "000002", "601318", "000858"],
            "上市日期": [
                "1991-04-03",
                "2001-08-27",
                "1991-01-29",
                "2007-03-01",
                "1998-04-27",
            ],
        }
    )


class TestGetStockPool:
    """股票池筛选测试。"""

    @patch("stock_filter._fetch_stock_info")
    @patch("stock_filter._fetch_stock_spot")
    def test_normal_data(
        self,
        mock_spot: MagicMock,
        mock_info: MagicMock,
    ) -> None:
        """正常数据返回正确列和数量。"""
        mock_spot.return_value = _make_stock_data()
        mock_info.return_value = _make_stock_info()

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert "code" in result.columns
        assert "name" in result.columns
        assert "market_cap" in result.columns
        assert len(result) <= 1000

    @patch("stock_filter._fetch_stock_info")
    @patch("stock_filter._fetch_stock_spot")
    def test_no_st_stocks(
        self,
        mock_spot: MagicMock,
        mock_info: MagicMock,
    ) -> None:
        """结果中无ST股票。"""
        data = _make_stock_data()
        # 添加ST股票
        st_stock = pd.DataFrame(
            {
                "代码": ["000006"],
                "名称": ["*ST深振"],
                "总市值": [50e8],
                "市盈率-动态": [15.0],
                "市净率": [1.5],
                "最新价": [5.0],
                "涨跌幅": [-2.0],
            }
        )
        data = pd.concat([data, st_stock], ignore_index=True)
        mock_spot.return_value = data
        mock_info.return_value = _make_stock_info()

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert not result["name"].str.contains("ST", case=False).any()

    @patch("stock_filter._fetch_stock_info")
    @patch("stock_filter._fetch_stock_spot")
    def test_market_cap_filter(
        self,
        mock_spot: MagicMock,
        mock_info: MagicMock,
    ) -> None:
        """结果中市值均 ≥ 20亿。"""
        data = _make_stock_data()
        # 添加小市值股票
        small_cap = pd.DataFrame(
            {
                "代码": ["000007"],
                "名称": ["全好股份"],
                "总市值": [10e8],  # 10亿
                "市盈率-动态": [15.0],
                "市净率": [1.5],
                "最新价": [5.0],
                "涨跌幅": [0.0],
            }
        )
        data = pd.concat([data, small_cap], ignore_index=True)
        mock_spot.return_value = data
        mock_info.return_value = _make_stock_info()

        config = FilterConfig(min_market_cap=20e8, pool_size=1000)
        result = get_stock_pool(config)

        assert (result["market_cap"] >= 20e8).all()

    @patch("stock_filter._fetch_stock_info")
    @patch("stock_filter._fetch_stock_spot")
    def test_pe_filter(
        self,
        mock_spot: MagicMock,
        mock_info: MagicMock,
    ) -> None:
        """结果中PE均 > 0。"""
        data = _make_stock_data()
        # 添加负PE股票
        negative_pe = pd.DataFrame(
            {
                "代码": ["000008"],
                "名称": ["亏损股份"],
                "总市值": [50e8],
                "市盈率-动态": [-10.0],
                "市净率": [1.5],
                "最新价": [5.0],
                "涨跌幅": [0.0],
            }
        )
        data = pd.concat([data, negative_pe], ignore_index=True)
        mock_spot.return_value = data
        mock_info.return_value = _make_stock_info()

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert (result["pe_ttm"] > 0).all()

    @patch("stock_filter._fetch_stock_info")
    @patch("stock_filter._fetch_stock_spot")
    def test_pool_size_limit(
        self,
        mock_spot: MagicMock,
        mock_info: MagicMock,
    ) -> None:
        """结果数量不超过 pool_size。"""
        mock_spot.return_value = _make_stock_data()
        mock_info.return_value = _make_stock_info()

        config = FilterConfig(pool_size=3)
        result = get_stock_pool(config)

        assert len(result) <= 3

    @patch("stock_filter._fetch_stock_spot")
    def test_api_failure(self, mock_spot: MagicMock) -> None:
        """AKShare失败时抛出异常。"""
        mock_spot.side_effect = Exception("API 超时")

        config = FilterConfig()
        with pytest.raises(Exception, match="API 超时"):
            get_stock_pool(config)
