"""stock_filter.py 单元测试。"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import FilterConfig


def _make_stock_data() -> pd.DataFrame:
    """创建测试用股票数据（AKShare 格式）。"""
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
    """创建测试用股票上市日期信息（AKShare 格式）。"""
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


def _setup_mock_modules(
    monkeypatch: pytest.MonkeyPatch,
    spot_data: pd.DataFrame | None = None,
    info_data: pd.DataFrame | None = None,
    spot_side_effect: Exception | None = None,
) -> None:
    """设置 mock 模块，阻止真实网络请求。

    Args:
        monkeypatch: pytest monkeypatch fixture。
        spot_data: 模拟 stock_zh_a_spot_em 返回数据。
        info_data: 模拟 stock_info_a_code_name 返回数据。
        spot_side_effect: 模拟 stock_zh_a_spot_em 抛出异常。
    """
    # Mock remote_data 模块（is_remote_available 返回 False）
    mock_remote = ModuleType("remote_data")
    mock_remote.is_remote_available = MagicMock(return_value=False)  # type: ignore[attr-defined]
    mock_remote.get_stock_spot_remote = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "remote_data", mock_remote)

    # Mock akshare 模块
    mock_ak = ModuleType("akshare")
    if spot_side_effect is not None:
        mock_ak.stock_zh_a_spot_em = MagicMock(side_effect=spot_side_effect)  # type: ignore[attr-defined]
    else:
        mock_ak.stock_zh_a_spot_em = MagicMock(return_value=spot_data)  # type: ignore[attr-defined]
    mock_ak.stock_info_a_code_name = MagicMock(return_value=info_data)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "akshare", mock_ak)


class TestGetStockPool:
    """股票池筛选测试。"""

    def test_normal_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """正常数据返回正确列和数量。"""
        _setup_mock_modules(
            monkeypatch,
            spot_data=_make_stock_data(),
            info_data=_make_stock_info(),
        )
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)

        from stock_filter import get_stock_pool

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert "code" in result.columns
        assert "name" in result.columns
        assert "market_cap" in result.columns
        assert len(result) <= 1000

    def test_no_st_stocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """结果中无ST股票。"""
        data = _make_stock_data()
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

        _setup_mock_modules(monkeypatch, spot_data=data, info_data=_make_stock_info())
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)

        from stock_filter import get_stock_pool

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert not result["name"].str.contains("ST", case=False).any()

    def test_market_cap_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """结果中市值均 ≥ 20亿。"""
        data = _make_stock_data()
        small_cap = pd.DataFrame(
            {
                "代码": ["000007"],
                "名称": ["全好股份"],
                "总市值": [10e8],
                "市盈率-动态": [15.0],
                "市净率": [1.5],
                "最新价": [5.0],
                "涨跌幅": [0.0],
            }
        )
        data = pd.concat([data, small_cap], ignore_index=True)

        _setup_mock_modules(monkeypatch, spot_data=data, info_data=_make_stock_info())
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)

        from stock_filter import get_stock_pool

        config = FilterConfig(min_market_cap=20e8, pool_size=1000)
        result = get_stock_pool(config)

        assert (result["market_cap"] >= 20e8).all()

    def test_pe_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """结果中PE均 > 0。"""
        data = _make_stock_data()
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

        _setup_mock_modules(monkeypatch, spot_data=data, info_data=_make_stock_info())
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)

        from stock_filter import get_stock_pool

        config = FilterConfig(pool_size=1000)
        result = get_stock_pool(config)

        assert (result["pe_ttm"] > 0).all()

    def test_pool_size_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """结果数量不超过 pool_size。"""
        _setup_mock_modules(
            monkeypatch,
            spot_data=_make_stock_data(),
            info_data=_make_stock_info(),
        )
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)

        from stock_filter import get_stock_pool

        config = FilterConfig(pool_size=3)
        result = get_stock_pool(config)

        assert len(result) <= 3

    def test_api_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """所有数据源失败时抛出异常。"""
        _setup_mock_modules(
            monkeypatch,
            spot_side_effect=Exception("API 超时"),
        )
        monkeypatch.setattr("stock_filter.random_delay", lambda *a, **kw: None)
        monkeypatch.setattr(
            "stock_filter._fetch_stock_data_baostock",
            MagicMock(side_effect=Exception("BaoStock 也失败")),
        )

        from stock_filter import get_stock_pool

        config = FilterConfig()
        with pytest.raises(Exception):
            get_stock_pool(config)
