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


# ══════════════════════════════════════════════════════
# V3 AdaptiveVoter 测试
# ══════════════════════════════════════════════════════

from src.pipeline.signal import (
    AdaptiveThresholds,
    _decide_action_adaptive,
)


class TestAdaptiveThresholds:
    """自适应阈值测试."""

    def test_bull_thresholds(self):
        t = AdaptiveThresholds.for_regime("bull")
        assert t.min_buy_votes == 2
        assert t.min_sell_votes == 4
        assert t.factor_buy == 65.0
        assert t.min_risk_reward == 1.5

    def test_bear_thresholds(self):
        t = AdaptiveThresholds.for_regime("bear")
        assert t.min_buy_votes == 4
        assert t.min_sell_votes == 2
        assert t.factor_buy == 80.0
        assert t.min_risk_reward == 2.5

    def test_sideways_thresholds(self):
        t = AdaptiveThresholds.for_regime("sideways")
        assert t.min_buy_votes == 2
        assert t.min_sell_votes == 2
        assert t.factor_buy == 70.0

    def test_unknown_defaults_to_sideways(self):
        t = AdaptiveThresholds.for_regime("unknown")
        assert t.min_buy_votes == 2  # sideways default


class TestDecideActionAdaptive:
    """自适应投票决策测试."""

    def test_bull_2buy_0sell_is_buy(self):
        t = AdaptiveThresholds.for_regime("bull")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "buy"
        assert conf > 0.3

    def test_bear_2buy_0sell_is_hold(self):
        t = AdaptiveThresholds.for_regime("bear")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "hold"  # 熊市需要 4 票

    def test_sideways_2buy_0sell_is_buy(self):
        t = AdaptiveThresholds.for_regime("sideways")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "buy"

    def test_risk_reward_veto(self):
        t = AdaptiveThresholds.for_regime("bull")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "buy", 0.6),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 1.0)
        assert action == "hold"
        assert "盈亏比" in detail

    def test_oppose_votes_block_buy(self):
        t = AdaptiveThresholds.for_regime("sideways")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "buy", 0.6),
            SignalVote("momentum", "sell", 0.6),
            SignalVote("regime", "sell", 0.5),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "hold"  # sell=2 > max_oppose=1

    def test_all_neutral(self):
        t = AdaptiveThresholds.for_regime("bull")
        votes = [
            SignalVote("factor", "neutral"),
            SignalVote("technical", "neutral"),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "hold"
        assert "信号混合" in detail

    def test_near_buy_in_bear(self):
        t = AdaptiveThresholds.for_regime("bear")
        votes = [
            SignalVote("factor", "buy", 0.8),
            SignalVote("technical", "buy", 0.7),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "sell", 0.6),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "hold"

    def test_sell_in_bear(self):
        t = AdaptiveThresholds.for_regime("bear")
        votes = [
            SignalVote("factor", "sell", 0.8),
            SignalVote("technical", "sell", 0.7),
            SignalVote("capital", "neutral"),
            SignalVote("momentum", "neutral"),
            SignalVote("regime", "neutral"),
        ]
        action, conf, detail = _decide_action_adaptive(votes, t, 2.0)
        assert action == "sell"  # 熊市 2 票即可卖出


class TestVoteFactorAdaptive:
    """自适应因子投票测试."""

    def test_bull_lower_threshold(self):
        t = AdaptiveThresholds.for_regime("bull")
        fs = MockFactorScores(total=68.0)
        vote = _vote_factor(fs, MockConfig(), t)
        assert vote.vote == "buy"  # 68 >= 65

    def test_bear_higher_threshold(self):
        t = AdaptiveThresholds.for_regime("bear")
        fs = MockFactorScores(total=75.0)
        vote = _vote_factor(fs, MockConfig(), t)
        assert vote.vote == "neutral"  # 75 < 80


class TestGenerateSignalsV3:
    """V3 信号生成测试."""

    def test_v3_adaptive_mode(self):
        factors = [
            MockFactorScores(code="000001", total=75, technical=70, capital=65, momentum=60),
            MockFactorScores(code="000002", total=25, technical=30, capital=35, momentum=40),
        ]
        data = type("Data", (), {"kline_cache": {}})()
        signals = generate_signals(factors, data, MockConfig(), "bull", use_adaptive=True)
        assert len(signals) == 2
        assert all(s.action in ("buy", "sell", "hold") for s in signals)

    def test_v2_compat_mode(self):
        factors = [MockFactorScores(code="000001", total=75, technical=80, capital=65, momentum=60)]
        data = type("Data", (), {"kline_cache": {}})()
        signals = generate_signals(factors, data, MockConfig(), "sideways", use_adaptive=False)
        assert len(signals) == 1

    def test_adaptive_not_worse_than_v2(self):
        """V3 should not produce fewer actionable signals than V2."""
        factors = [
            MockFactorScores(code=f"{i:06d}",
                             total=40.0 + i * 0.6,
                             technical=45.0 + i * 0.5,
                             capital=40.0 + i * 0.55,
                             momentum=50.0 + i * 0.3)
            for i in range(50)
        ]
        data = type("Data", (), {"kline_cache": {}})()
        v3 = generate_signals(factors, data, MockConfig(), "sideways", use_adaptive=True)
        v2 = generate_signals(factors, data, MockConfig(), "sideways", use_adaptive=False)
        v3_buy_sell = sum(1 for s in v3 if s.action in ("buy", "sell"))
        v2_buy_sell = sum(1 for s in v2 if s.action in ("buy", "sell"))
        assert v3_buy_sell >= v2_buy_sell
