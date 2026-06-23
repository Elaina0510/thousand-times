"""测试 data_sources 模块。"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def _setup_mock_akshare(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """注册 mock akshare 模块。"""
    mock_ak = ModuleType("akshare")
    monkeypatch.setitem(sys.modules, "akshare", mock_ak)
    return mock_ak


class TestFetchNorthFlow:
    """北向资金整体流向测试。"""

    def test_returns_dataframe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试返回 DataFrame。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_df = pd.DataFrame({
            "日期": ["2024-01-01", "2024-01-02"],
            "当日成交净买额": [1e8, 2e8],
            "当日资金流入": [3e8, 4e8],
        })
        mock_ak.stock_hsgt_hist_em = MagicMock(return_value=mock_df)

        from src.data_sources.capital_flow import fetch_north_flow

        result = fetch_north_flow(days=2)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_handles_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试 API 异常时返回空 DataFrame。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_ak.stock_hsgt_hist_em = MagicMock(side_effect=Exception("API Error"))

        from src.data_sources.capital_flow import fetch_north_flow

        result = fetch_north_flow()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_limits_rows_by_days(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试按 days 参数限制返回行数。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_df = pd.DataFrame({
            "日期": [f"2024-01-{i:02d}" for i in range(1, 11)],
            "当日成交净买额": [1e8] * 10,
        })
        mock_ak.stock_hsgt_hist_em = MagicMock(return_value=mock_df)

        from src.data_sources.capital_flow import fetch_north_flow

        result = fetch_north_flow(days=5)

        assert len(result) == 5


class TestFetchNorthFlowStock:
    """个股北向持仓测试。"""

    def test_returns_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试返回浮点数。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_df = pd.DataFrame({
            "代码": ["600519"],
            "名称": ["贵州茅台"],
            "今日持股-股数": [1000000],
        })
        mock_ak.stock_hsgt_hold_stock_em = MagicMock(return_value=mock_df)

        from src.data_sources.capital_flow import fetch_north_flow_stock

        result = fetch_north_flow_stock("600519")

        assert isinstance(result, float)
        assert result == 1000000.0

    def test_stock_not_found_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试股票不存在时返回 0。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_df = pd.DataFrame({
            "代码": ["000001"],
            "名称": ["平安银行"],
            "今日持股-股数": [500000],
        })
        mock_ak.stock_hsgt_hold_stock_em = MagicMock(return_value=mock_df)

        from src.data_sources.capital_flow import fetch_north_flow_stock

        result = fetch_north_flow_stock("600519")

        assert result == 0.0

    def test_api_error_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试 API 异常时返回 0。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_ak.stock_hsgt_hold_stock_em = MagicMock(side_effect=Exception("Network Error"))

        from src.data_sources.capital_flow import fetch_north_flow_stock

        result = fetch_north_flow_stock("600519")

        assert result == 0.0


class TestFetchLimitStats:
    """涨跌停统计测试。"""

    def test_returns_dict_with_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试返回包含涨跌停数量的字典。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_zt = pd.DataFrame({
            "代码": ["600519", "000858"],
            "名称": ["贵州茅台", "五粮液"],
            "涨停统计": ["2天", "3天"],
        })
        mock_dt = pd.DataFrame({
            "代码": ["000001"],
            "名称": ["平安银行"],
        })
        mock_ak.stock_zt_pool_em = MagicMock(return_value=mock_zt)
        mock_ak.stock_zt_pool_dtgc_em = MagicMock(return_value=mock_dt)

        from src.data_sources.sentiment import fetch_limit_stats

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 2
        assert result["limit_down_count"] == 1
        assert result["max_consecutive"] == 3

    def test_handles_empty_zt_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试涨停池为空的情况。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_ak.stock_zt_pool_em = MagicMock(return_value=pd.DataFrame())
        mock_ak.stock_zt_pool_dtgc_em = MagicMock(return_value=pd.DataFrame())

        from src.data_sources.sentiment import fetch_limit_stats

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 0
        assert result["limit_down_count"] == 0
        assert result["max_consecutive"] == 0

    def test_handles_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试 API 异常时返回默认值。"""
        mock_ak = _setup_mock_akshare(monkeypatch)
        mock_ak.stock_zt_pool_em = MagicMock(side_effect=Exception("API Error"))
        mock_ak.stock_zt_pool_dtgc_em = MagicMock(side_effect=Exception("API Error"))

        from src.data_sources.sentiment import fetch_limit_stats

        result = fetch_limit_stats("20240101")

        assert result["limit_up_count"] == 0
        assert result["limit_down_count"] == 0
        assert result["max_consecutive"] == 0
