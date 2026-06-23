"""测试 pipeline/collect.py 数据采集模块。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.pipeline.collect import DataBundle, FundamentalData, fetch_index_kline


class TestDataBundle:
    """DataBundle 数据结构测试。"""

    def test_create_empty_bundle(self) -> None:
        """测试创建空的 DataBundle。"""
        bundle = DataBundle()
        assert bundle.index_kline.empty
        assert bundle.stock_pool.empty
        assert bundle.limit_up_count == 0

    def test_bundle_has_all_fields(self) -> None:
        """测试 DataBundle 包含所有必要字段。"""
        fields = [
            "index_kline", "stock_pool", "kline_cache", "fundamental_cache",
            "north_flow", "margin_data", "limit_up_count", "limit_down_count",
            "advance_decline_ratio", "macro_indicators", "sector_flow",
            "news_items", "policy_impacts", "etf_pool", "etf_kline_cache",
        ]
        for f in fields:
            assert f in DataBundle.__dataclass_fields__, f"Missing field: {f}"


class TestFundamentalData:
    """FundamentalData 数据结构测试。"""

    def test_create_fundamental_data(self) -> None:
        """测试创建 FundamentalData。"""
        data = FundamentalData(
            roe=15.0, eps=2.5, profit_growth=10.0,
            revenue_growth=8.0, pe_ttm=20.0, pb=3.0,
        )
        assert data.roe == 15.0
        assert data.eps == 2.5
        assert data.pe_ttm == 20.0

    def test_default_values(self) -> None:
        """测试默认值。"""
        data = FundamentalData()
        assert data.roe == 0.0
        assert data.eps == 0.0
        assert data.pe_ttm == 50.0


class TestFetchIndexKline:
    """指数K线数据采集测试。"""

    @patch("src.baostock_data.get_index_hist_baostock")
    def test_returns_dataframe(self, mock_fetch: MagicMock) -> None:
        """测试返回 DataFrame。"""
        mock_df = pd.DataFrame({
            "日期": ["2024-01-01", "2024-01-02"],
            "开盘": [100.0, 101.0],
            "收盘": [101.0, 102.0],
        })
        mock_fetch.return_value = mock_df

        result = fetch_index_kline("sh000001", days=60)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch("src.baostock_data.get_index_hist_baostock", side_effect=Exception("fail"))
    def test_handles_api_error(self, mock_fetch: MagicMock) -> None:
        """测试异常时返回空 DataFrame。"""
        result = fetch_index_kline("sh000001", days=60)
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestStageCollect:
    """stage_collect 主函数测试。"""

    @patch("src.pipeline.collect._fetch_news_data", return_value=([], []))
    @patch("src.pipeline.collect._fetch_etf_data", return_value=([], {}))
    @patch("src.pipeline.collect._fetch_fundamentals_batch", return_value={})
    @patch("src.pipeline.collect._batch_fetch_klines", return_value={})
    @patch("src.pipeline.collect._fetch_stock_pool", return_value=pd.DataFrame())
    @patch("src.pipeline.collect.fetch_index_kline", return_value=pd.DataFrame())
    @patch("src.data_sources.sentiment.fetch_limit_stats", return_value={"limit_up_count": 10, "limit_down_count": 5, "max_consecutive": 3})
    @patch("src.data_sources.capital_flow.fetch_north_flow", return_value=pd.DataFrame())
    def test_returns_data_bundle(
        self,
        mock_north: MagicMock,
        mock_limit: MagicMock,
        mock_index: MagicMock,
        mock_pool: MagicMock,
        mock_klines: MagicMock,
        mock_fund: MagicMock,
        mock_etf: MagicMock,
        mock_news: MagicMock,
    ) -> None:
        """测试返回 DataBundle。"""
        from src.pipeline.collect import stage_collect
        from src.config import AppConfig

        config = AppConfig()
        result = stage_collect(config, regime=None)

        assert isinstance(result, DataBundle)
        assert result.limit_up_count == 10
        assert result.limit_down_count == 5
