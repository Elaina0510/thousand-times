"""信号生成模块测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.pipeline.signal import (
    KeyPrices,
    Signal,
    SignalVote,
    _decide_action,
    _vote_capital,
    _vote_factor,
    _vote_momentum,
    _vote_regime,
    _vote_technical,
    calc_key_prices,
    generate_signals,
)


class MockFactorScores:
    """模拟 FactorScores。"""

    def __init__(self, **kwargs):
        self.code = kwargs.get("code", "000001")
        self.name = kwargs.get("name", "测试股票")
        self.technical = kwargs.get("technical", 50.0)
        self.fundamental = kwargs.get("fundamental", 50.0)
        self.capital = kwargs.get("capital", 50.0)
        self.sentiment = kwargs.get("sentiment", 50.0)
        self.momentum = kwargs.get("momentum", 50.0)
        self.total = kwargs.get("total", 50.0)
        self.rank_percentile = kwargs.get("rank_percentile", 50.0)


class MockSignalConfig:
    def __init__(self):
        self.factor_buy_threshold = 70.0
        self.factor_sell_threshold = 30.0
        self.technical_buy_threshold = 75.0
        self.technical_sell_threshold = 25.0
        self.min_buy_votes = 3
        self.min_sell_votes = 3
        self.atr_target_multiplier = 3.0
        self.atr_stop_multiplier = 1.0
        self.min_risk_reward = 1.5


class MockConfig:
    def __init__(self):
        self.signal = MockSignalConfig()


class TestVoteFactor:
    """因子综合投票测试。"""

    def test_buy_signal(self):
        fs = MockFactorScores(total=75)
        vote = _vote_factor(fs, MockConfig())
        assert vote.vote == "buy"
        assert vote.source == "factor"

    def test_sell_signal(self):
        fs = MockFactorScores(total=25)
        vote = _vote_factor(fs, MockConfig())
        assert vote.vote == "sell"

    def test_neutral(self):
        fs = MockFactorScores(total=50)
        vote = _vote_factor(fs, MockConfig())
        assert vote.vote == "neutral"


class TestVoteTechnical:
    """技术面投票测试。"""

    def test_buy_signal(self):
        fs = MockFactorScores(technical=80)
        vote = _vote_technical(fs, MockConfig())
        assert vote.vote == "buy"

    def test_sell_signal(self):
        fs = MockFactorScores(technical=20)
        vote = _vote_technical(fs, MockConfig())
        assert vote.vote == "sell"


class TestVoteCapital:
    """资金面投票测试。"""

    def test_buy_signal(self):
        fs = MockFactorScores(capital=75)
        vote = _vote_capital(fs, MockConfig())
        assert vote.vote == "buy"

    def test_sell_signal(self):
        fs = MockFactorScores(capital=25)
        vote = _vote_capital(fs, MockConfig())
        assert vote.vote == "sell"


class TestVoteMomentum:
    """动量投票测试。"""

    def test_buy_signal(self):
        fs = MockFactorScores(momentum=75)
        vote = _vote_momentum(fs, MockConfig())
        assert vote.vote == "buy"

    def test_sell_signal(self):
        fs = MockFactorScores(momentum=25)
        vote = _vote_momentum(fs, MockConfig())
        assert vote.vote == "sell"


class TestVoteRegime:
    """市场环境投票测试。"""

    def test_bull_with_good_technical(self):
        fs = MockFactorScores(technical=70)
        vote = _vote_regime(fs, "bull", MockConfig())
        assert vote.vote == "buy"

    def test_bear_with_bad_technical(self):
        fs = MockFactorScores(technical=30)
        vote = _vote_regime(fs, "bear", MockConfig())
        assert vote.vote == "sell"

    def test_sideways_neutral(self):
        fs = MockFactorScores(technical=50)
        vote = _vote_regime(fs, "sideways", MockConfig())
        assert vote.vote == "neutral"


class TestDecideAction:
    """投票决策测试。"""

    def test_buy_when_3_buy(self):
        votes = [
            SignalVote("f1", "buy"),
            SignalVote("f2", "buy"),
            SignalVote("f3", "buy"),
            SignalVote("f4", "neutral"),
            SignalVote("f5", "neutral"),
        ]
        action, conf = _decide_action(votes, MockConfig())
        assert action == "buy"
        assert conf > 0

    def test_sell_when_3_sell(self):
        votes = [
            SignalVote("f1", "sell"),
            SignalVote("f2", "sell"),
            SignalVote("f3", "sell"),
            SignalVote("f4", "neutral"),
            SignalVote("f5", "neutral"),
        ]
        action, conf = _decide_action(votes, MockConfig())
        assert action == "sell"

    def test_hold_when_mixed(self):
        votes = [
            SignalVote("f1", "buy"),
            SignalVote("f2", "buy"),
            SignalVote("f3", "sell"),
            SignalVote("f4", "sell"),
            SignalVote("f5", "neutral"),
        ]
        action, conf = _decide_action(votes, MockConfig())
        assert action == "hold"


class TestCalcKeyPrices:
    """关键价位测试。"""

    def test_empty_kline(self):
        result = calc_key_prices(pd.DataFrame(), MockConfig())
        assert result.current_price == 0.0

    def test_normal_kline(self):
        n = 60
        prices = np.linspace(10, 15, n)
        kline = pd.DataFrame({
            "close": prices,
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "volume": np.ones(n) * 1e6,
        })
        result = calc_key_prices(kline, MockConfig())
        assert result.current_price > 0
        assert result.support > 0
        assert result.resistance > 0
        assert result.target > result.current_price
        assert result.stop_loss < result.current_price


class TestGenerateSignals:
    """信号生成集成测试。"""

    def test_generates_signals(self):
        factors = [MockFactorScores(total=80, technical=80, momentum=75)]
        data = type("Data", (), {"kline_cache": {}})()
        signals = generate_signals(factors, data, MockConfig())
        assert len(signals) == 1
        assert isinstance(signals[0], Signal)

    def test_buy_signal_with_strong_factors(self):
        """强因子应产生买入信号（但需满足盈亏比条件）."""
        factors = [MockFactorScores(
            total=80, technical=80, capital=75, momentum=75,
        )]
        # 无K线数据时，key_prices 全为0，盈亏比不满足 → hold
        data_no_kline = type("Data", (), {"kline_cache": {}})()
        signals = generate_signals(factors, data_no_kline, MockConfig())
        # 没有K线数据时，因为盈亏比为0 < min_risk_reward(2.0)，会被降级为 hold
        assert signals[0].action == "hold"

        # 有K线数据时，应能正确计算盈亏比并产生 buy 信号
        import numpy as np
        n = 60
        prices = np.linspace(10, 15, n)
        kline = pd.DataFrame({
            "close": prices, "open": prices * 0.99,
            "high": prices * 1.02, "low": prices * 0.98,
            "volume": np.ones(n) * 1e6,
        })
        data_with_kline = type("Data", (), {"kline_cache": {"000001": kline}})()
        signals = generate_signals(factors, data_with_kline, MockConfig())
        assert signals[0].action == "buy"
