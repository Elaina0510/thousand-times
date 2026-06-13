"""sector_analysis.py 单元测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from buy_sell_signal import SectorComparison
from sector_analysis import (
    SectorStock,
    analyze_sector_comparison,
    build_sector_stocks,
    calc_sector_rank,
    calc_vs_etf_return,
)


def _make_sector_stocks() -> list[SectorStock]:
    """创建测试用板块股票列表。"""
    return [
        SectorStock(code="600519", name="贵州茅台", industry="白酒", total_score=80.0, change_pct=3.0),
        SectorStock(code="000858", name="五粮液", industry="白酒", total_score=75.0, change_pct=2.5),
        SectorStock(code="000568", name="泸州老窖", industry="白酒", total_score=70.0, change_pct=2.0),
        SectorStock(code="002304", name="洋河股份", industry="白酒", total_score=65.0, change_pct=1.5),
        SectorStock(code="600809", name="山西汾酒", industry="白酒", total_score=60.0, change_pct=1.0),
    ]


class TestCalcSectorRank:
    """板块排名计算测试。"""

    def test_top_rank(self) -> None:
        """排名第一。"""
        stocks = _make_sector_stocks()
        rank, total, percentile = calc_sector_rank("600519", 80.0, stocks)
        assert rank == 1
        assert total == 5
        assert percentile == 80.0

    def test_middle_rank(self) -> None:
        """中间排名。"""
        stocks = _make_sector_stocks()
        rank, total, percentile = calc_sector_rank("000568", 70.0, stocks)
        assert rank == 3
        assert total == 5
        assert percentile == 40.0

    def test_bottom_rank(self) -> None:
        """排名最后。"""
        stocks = _make_sector_stocks()
        rank, total, percentile = calc_sector_rank("600809", 60.0, stocks)
        assert rank == 5
        assert total == 5
        assert percentile == 0.0

    def test_empty_stocks(self) -> None:
        """空股票列表。"""
        rank, total, percentile = calc_sector_rank("600519", 80.0, [])
        assert rank == 1
        assert total == 1
        assert percentile == 100.0

    def test_single_stock(self) -> None:
        """单只股票。"""
        stocks = [SectorStock(code="600519", name="贵州茅台", industry="白酒", total_score=80.0, change_pct=3.0)]
        rank, total, percentile = calc_sector_rank("600519", 80.0, stocks)
        assert rank == 1
        assert total == 1
        assert percentile == 100.0


class TestCalcVsEtfReturn:
    """ETF超额收益计算测试。"""

    def test_outperform(self) -> None:
        """跑赢ETF。"""
        result = calc_vs_etf_return(3.0, 1.5)
        assert result == 1.5

    def test_underperform(self) -> None:
        """跑输ETF。"""
        result = calc_vs_etf_return(1.0, 2.5)
        assert result == -1.5

    def test_etf_none(self) -> None:
        """ETF数据不可用。"""
        result = calc_vs_etf_return(3.0, None)
        assert result is None


class TestAnalyzeSectorComparison:
    """板块对比分析测试。"""

    def test_normal_analysis(self) -> None:
        """正常板块对比分析。"""
        stocks = _make_sector_stocks()
        result = analyze_sector_comparison(
            target_code="600519",
            target_name="贵州茅台",
            target_industry="白酒",
            target_score=80.0,
            target_change_pct=3.0,
            sector_stocks=stocks,
            etf_pool=["159928"],
        )

        assert isinstance(result, SectorComparison)
        assert result.sector_name == "白酒"
        assert result.rank_in_sector == 1
        assert result.total_in_sector == 5
        assert result.percentile == 80.0

    def test_no_industry(self) -> None:
        """无行业信息时返回 None。"""
        result = analyze_sector_comparison(
            target_code="600519",
            target_name="贵州茅台",
            target_industry="",
            target_score=80.0,
            target_change_pct=3.0,
            sector_stocks=[],
            etf_pool=["159928"],
        )
        assert result is None

    def test_with_etf_return(self) -> None:
        """包含ETF超额收益。"""
        stocks = _make_sector_stocks()
        etf_cache = {
            "159928": pd.DataFrame({
                "收盘": [1.0, 1.1, 1.2, 1.3, 1.4],
            })
        }
        result = analyze_sector_comparison(
            target_code="600519",
            target_name="贵州茅台",
            target_industry="白酒",
            target_score=80.0,
            target_change_pct=5.0,
            sector_stocks=stocks,
            etf_pool=["159928"],
            etf_kline_cache=etf_cache,
        )

        assert isinstance(result, SectorComparison)
        # ETF涨跌幅 = (1.4 - 1.0) / 1.0 * 100 = 40%
        # 超额收益 = 5.0 - 40.0 = -35.0
        assert result.vs_etf_return == -35.0


class TestBuildSectorStocks:
    """构建板块股票列表测试。"""

    def test_group_by_industry(self) -> None:
        """按行业分组。"""
        stock_pool = pd.DataFrame({
            "code": ["600519", "000858", "512480"],
            "name": ["贵州茅台", "五粮液", "半导体ETF"],
            "industry": ["白酒", "白酒", "半导体"],
        })
        scores = {"600519": 80.0, "000858": 75.0, "512480": 70.0}
        changes = {"600519": 3.0, "000858": 2.5, "512480": 1.0}

        result = build_sector_stocks(stock_pool, scores, changes)

        assert "白酒" in result
        assert "半导体" in result
        assert len(result["白酒"]) == 2
        assert len(result["半导体"]) == 1

    def test_empty_industry(self) -> None:
        """无行业信息的股票被跳过。"""
        stock_pool = pd.DataFrame({
            "code": ["600519"],
            "name": ["贵州茅台"],
            "industry": [""],
        })
        scores = {"600519": 80.0}
        changes = {"600519": 3.0}

        result = build_sector_stocks(stock_pool, scores, changes)

        assert len(result) == 0

    def test_baostock_industry_format(self) -> None:
        """BaoStock 行业格式清理。"""
        stock_pool = pd.DataFrame({
            "code": ["600519"],
            "name": ["贵州茅台"],
            "industry": ["C15酒、饮料和精制茶制造业"],
        })
        scores = {"600519": 80.0}
        changes = {"600519": 3.0}

        result = build_sector_stocks(stock_pool, scores, changes)

        assert "酒、饮料和精制茶制造业" in result
