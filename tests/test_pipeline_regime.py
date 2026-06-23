"""测试 pipeline/regime.py 市场环境判断模块。"""

from __future__ import annotations

import pandas as pd
import pytest

from src.pipeline.regime import MarketRegime, RegimeVote, judge_market_regime


class TestMarketRegime:
    """MarketRegime 数据结构测试。"""

    def test_create_bull_regime(self) -> None:
        regime = MarketRegime(state="bull", confidence=0.8, position_advice=0.94)
        assert regime.state == "bull"
        assert regime.confidence == 0.8

    def test_create_bear_regime(self) -> None:
        regime = MarketRegime(state="bear", confidence=0.6, position_advice=0.12)
        assert regime.state == "bear"

    def test_create_sideways_regime(self) -> None:
        regime = MarketRegime(state="sideways", confidence=0.5, position_advice=0.5)
        assert regime.state == "sideways"


class TestRegimeVote:
    """RegimeVote 数据结构测试。"""

    def test_create_vote(self) -> None:
        vote = RegimeVote(signal_name="trend", vote="bull", confidence=0.8, reason="test")
        assert vote.signal_name == "trend"
        assert vote.vote == "bull"


class TestJudgeMarketRegime:
    """judge_market_regime 主函数测试。"""

    def test_returns_market_regime(self) -> None:
        """测试返回 MarketRegime。"""
        from src.pipeline.collect import DataBundle
        from src.config import AppConfig

        data = DataBundle()
        config = AppConfig()
        result = judge_market_regime(data, config)

        assert isinstance(result, MarketRegime)
        assert result.state in ("bull", "bear", "sideways")
        assert 0 <= result.confidence <= 1
        assert 0 <= result.position_advice <= 1

    def test_bull_trend_signal(self) -> None:
        """测试上升趋势产生牛市信号。"""
        from src.pipeline.collect import DataBundle
        from src.config import AppConfig

        # 创建上升趋势的K线数据
        closes = [100 + i * 0.5 for i in range(120)]
        index_kline = pd.DataFrame({"收盘": closes, "成交量": [1e6] * 120})

        data = DataBundle(index_kline=index_kline, advance_decline_ratio=2.0)
        config = AppConfig()
        result = judge_market_regime(data, config)

        assert isinstance(result, MarketRegime)
        # 趋势信号应该是 bull
        assert result.signals.get("trend") == "bull"

    def test_bear_trend_signal(self) -> None:
        """测试下降趋势产生熊市信号。"""
        from src.pipeline.collect import DataBundle
        from src.config import AppConfig

        closes = [200 - i * 0.5 for i in range(120)]
        index_kline = pd.DataFrame({"收盘": closes, "成交量": [1e6] * 120})

        data = DataBundle(index_kline=index_kline, advance_decline_ratio=0.3)
        config = AppConfig()
        result = judge_market_regime(data, config)

        assert isinstance(result, MarketRegime)
        assert result.signals.get("trend") == "bear"

    def test_empty_data_returns_neutral(self) -> None:
        """测试空数据返回中性。"""
        from src.pipeline.collect import DataBundle
        from src.config import AppConfig

        data = DataBundle()
        config = AppConfig()
        result = judge_market_regime(data, config)

        assert isinstance(result, MarketRegime)
        assert result.state == "sideways"
