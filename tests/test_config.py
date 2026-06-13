"""config.py 单元测试。"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from config import (
    AppConfig,
    BuySellSignalConfig,
    DEFAULT_ETF_POOL,
    EtfFundFlowWeightConfig,
    FilterConfig,
    FundamentalWeightConfig,
    IndustryTrendWeightConfig,
    NewsWeightConfig,
    ScoreWeightConfig,
    TechnicalWeightConfig,
    load_config,
)


class TestTechnicalWeightConfig:
    """技术指标权重配置测试。"""

    def test_default_values(self) -> None:
        config = TechnicalWeightConfig()
        assert config.ma_golden_cross == 5.0
        assert config.ma_death_cross == 5.0
        assert config.macd_golden_cross == 5.0
        assert config.volume_up == 4.0

    def test_custom_values(self) -> None:
        config = TechnicalWeightConfig(ma_golden_cross=6.0)
        assert config.ma_golden_cross == 6.0


class TestFundamentalWeightConfig:
    """基本面权重配置测试。"""

    def test_default_values(self) -> None:
        config = FundamentalWeightConfig()
        assert config.pe_low == 8.0
        assert config.profit_high_growth == 10.0
        assert config.revenue_high_growth == 7.0


class TestScoreWeightConfig:
    """综合评分权重配置测试。"""

    def test_stock_weights_sum_to_one(self) -> None:
        config = ScoreWeightConfig()
        total = (
            config.stock_technical
            + config.stock_fundamental
            + config.stock_news
            + config.stock_industry
        )
        assert abs(total - 1.0) < 1e-6

    def test_etf_weights_sum_to_one(self) -> None:
        config = ScoreWeightConfig()
        total = config.etf_technical + config.etf_news + config.etf_fund_flow
        assert abs(total - 1.0) < 1e-6


class TestFilterConfig:
    """股票池筛选配置测试。"""

    def test_default_values(self) -> None:
        config = FilterConfig()
        assert config.min_market_cap == 20e8
        assert config.min_listing_months == 3
        assert config.pool_size == 200


class TestDefaultEtfPool:
    """默认ETF池测试。"""

    def test_etf_pool_not_empty(self) -> None:
        assert len(DEFAULT_ETF_POOL) > 0

    def test_etf_pool_contains_11(self) -> None:
        assert len(DEFAULT_ETF_POOL) == 11

    def test_etf_pool_contains_broad_based(self) -> None:
        broad_based = ["510300", "510500", "159915", "588000"]
        for code in broad_based:
            assert code in DEFAULT_ETF_POOL


class TestAppConfig:
    """应用总配置测试。"""

    def test_default_config_complete(self) -> None:
        config = AppConfig()
        assert config.filter is not None
        assert config.score_weight is not None
        assert config.technical_weight is not None
        assert config.fundamental_weight is not None
        assert config.news_weight is not None
        assert config.industry_trend_weight is not None
        assert config.etf_fund_flow_weight is not None
        assert len(config.etf_pool) > 0

    def test_default_thresholds(self) -> None:
        config = AppConfig()
        assert config.buy_sell_signal is not None
        assert config.buy_sell_signal.buy_threshold == 70.0
        assert config.buy_sell_signal.sell_threshold == 30.0


class TestLoadConfig:
    """配置加载函数测试。"""

    def test_load_config_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            assert isinstance(config, AppConfig)
            assert config.llm_api_url == ""
            assert config.llm_api_key == ""

    def test_load_config_from_env(self) -> None:
        env = {
            "LLM_API_URL": "https://api.example.com",
            "LLM_API_KEY": "test-key-123",
        }
        with patch.dict(os.environ, env, clear=True):
            config = load_config()
            assert config.llm_api_url == "https://api.example.com"
            assert config.llm_api_key == "test-key-123"
