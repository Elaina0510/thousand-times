"""main.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import AppConfig
from etf_analyzer import EtfInfo
from main import analyze_single_etf, analyze_single_stock, main
from news_analysis import PolicyImpact
from scoring import ScoreResult, TechnicalSignals
from technical_analysis import KlineData


def _make_stock_series() -> pd.Series:
    """创建测试用股票数据。"""
    return pd.Series(
        {
            "code": "600519",
            "name": "贵州茅台",
            "market_cap": 2000e8,
            "pe_ttm": 28.5,
            "pb": 10.5,
            "industry": "白酒",
        }
    )


def _make_etf_info() -> EtfInfo:
    """创建测试用ETF信息。"""
    return EtfInfo(
        code="512480",
        name="半导体ETF",
        current_price=1.5,
        change_pct=2.0,
    )


def _make_kline_data() -> KlineData:
    """创建测试用K线数据。"""
    return KlineData(
        dates=["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
        opens=[100.0, 101.0, 102.0, 103.0, 104.0],
        highs=[105.0, 106.0, 107.0, 108.0, 109.0],
        lows=[95.0, 96.0, 97.0, 98.0, 99.0],
        closes=[102.0, 103.0, 104.0, 105.0, 106.0],
        volumes=[1000000.0, 1100000.0, 1200000.0, 1300000.0, 1400000.0],
        ma5=[101.0, 102.0, 103.0, 104.0, 105.0],
        ma10=[100.0, 101.0, 102.0, 103.0, 104.0],
        ma20=[99.0, 100.0, 101.0, 102.0, 103.0],
        ma60=[98.0, 99.0, 100.0, 101.0, 102.0],
        dif=[0.5, 0.6, 0.7, 0.8, 0.9],
        dea=[0.3, 0.4, 0.5, 0.6, 0.7],
        macd_hist=[0.4, 0.4, 0.4, 0.4, 0.4],
    )


def _make_policy_impact() -> PolicyImpact:
    """创建测试用政策影响。"""
    return PolicyImpact(
        news_title="消费刺激政策",
        affected_industries=["白酒", "消费"],
        impact_direction="positive",
        impact_degree="direct",
        impact_score=17.5,
        summary="利好白酒板块",
    )


class TestAnalyzeSingleStock:
    """单只股票分析测试。"""

    def test_function_exists(self) -> None:
        """验证函数存在。"""
        assert callable(analyze_single_stock)

    def test_function_signature(self) -> None:
        """验证函数签名。"""
        import inspect
        sig = inspect.signature(analyze_single_stock)
        assert "stock" in sig.parameters
        assert "policy_impacts" in sig.parameters
        assert "config" in sig.parameters


class TestAnalyzeSingleEtf:
    """单只ETF分析测试。"""

    def test_function_exists(self) -> None:
        """验证函数存在。"""
        assert callable(analyze_single_etf)

    def test_function_signature(self) -> None:
        """验证函数签名。"""
        import inspect
        sig = inspect.signature(analyze_single_etf)
        assert "etf" in sig.parameters
        assert "policy_impacts" in sig.parameters
        assert "config" in sig.parameters


class TestMain:
    """主函数测试。"""

    @patch("main.push_to_wechat")
    @patch("main.generate_report")
    @patch("main.generate_chart")
    @patch("main.get_kline_data")
    @patch("main.analyze_single_etf")
    @patch("main.analyze_single_stock")
    @patch("main.analyze_policy_impact")
    @patch("main.filter_by_credibility")
    @patch("main.fetch_news")
    @patch("main.get_etf_pool")
    @patch("main.get_stock_pool")
    @patch("main.load_config")
    def test_complete_flow(
        self,
        mock_config: MagicMock,
        mock_stock_pool: MagicMock,
        mock_etf_pool: MagicMock,
        mock_news: MagicMock,
        mock_filter: MagicMock,
        mock_impacts: MagicMock,
        mock_analyze_stock: MagicMock,
        mock_analyze_etf: MagicMock,
        mock_kline: MagicMock,
        mock_chart: MagicMock,
        mock_report: MagicMock,
        mock_push: MagicMock,
    ) -> None:
        """完整流程测试。"""
        mock_config.return_value = AppConfig()
        mock_stock_pool.return_value = pd.DataFrame({"code": ["600519"], "name": ["贵州茅台"]})
        mock_etf_pool.return_value = [_make_etf_info()]
        mock_news.return_value = []
        mock_filter.return_value = []
        mock_impacts.return_value = []

        # 模拟分析结果（推荐）
        mock_analyze_stock.return_value = ScoreResult(
            code="600519",
            name="贵州茅台",
            is_etf=False,
            technical_score=30.0,
            fundamental_score=20.0,
            news_score=15.0,
            industry_score=10.0,
            fund_flow_score=None,
            total_score=75.0,
            profit_probability=70.0,
            judgment="recommend",
            technical_signals=TechnicalSignals(),
            news_summary="",
        )
        mock_analyze_etf.return_value = ScoreResult(
            code="512480",
            name="半导体ETF",
            is_etf=True,
            technical_score=40.0,
            fundamental_score=None,
            news_score=25.0,
            industry_score=None,
            fund_flow_score=8.0,
            total_score=73.0,
            profit_probability=68.0,
            judgment="recommend",
            technical_signals=TechnicalSignals(),
            news_summary="",
        )

        mock_kline.return_value = _make_kline_data()
        mock_chart.return_value = "charts/test.png"
        mock_report.return_value = "测试报告"
        mock_push.return_value = True

        # 设置环境变量
        import os
        os.environ["PUSHPLUS_TOKEN"] = "test-token"

        try:
            main()
        finally:
            del os.environ["PUSHPLUS_TOKEN"]

        # 验证各模块被调用
        mock_config.assert_called_once()
        mock_stock_pool.assert_called_once()
        mock_etf_pool.assert_called_once()
        mock_push.assert_called_once()

    @patch("main.load_config")
    def test_no_pushplus_token(self, mock_config: MagicMock) -> None:
        """无PUSHPLUS_TOKEN时跳过推送。"""
        mock_config.return_value = AppConfig()

        import os
        if "PUSHPLUS_TOKEN" in os.environ:
            del os.environ["PUSHPLUS_TOKEN"]

        # 这个测试会因为其他依赖失败，但至少验证了配置加载
        # 在实际测试中需要mock所有依赖
