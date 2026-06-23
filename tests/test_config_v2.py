"""测试 config.py 新增 V2 配置类。"""

from __future__ import annotations

from src.config import (
    AppConfig,
    BacktestConfig,
    FactorWeightConfig,
    RealtimeConfig,
    RegimeConfig,
    SignalConfig,
)


class TestRegimeConfig:
    """市场环境判断配置测试。"""

    def test_default_values(self) -> None:
        config = RegimeConfig()
        assert config.ma_short == 20
        assert config.ma_long == 60
        assert config.volume_bull_ratio == 1.2
        assert config.volume_bear_ratio == 0.8
        assert config.north_flow_threshold == 100e8
        assert config.advance_decline_bull == 1.5
        assert config.advance_decline_bear == 0.7
        assert config.pe_percentile_low == 0.4
        assert config.pe_percentile_high == 0.7

    def test_custom_values(self) -> None:
        config = RegimeConfig(ma_short=10, ma_long=30)
        assert config.ma_short == 10
        assert config.ma_long == 30


class TestFactorWeightConfig:
    """因子权重配置测试。"""

    def test_default_weights(self) -> None:
        config = FactorWeightConfig()
        assert config.bull == {
            "technical": 0.30,
            "fundamental": 0.15,
            "capital": 0.15,
            "sentiment": 0.10,
            "momentum": 0.30,
        }
        assert config.bear == {
            "technical": 0.25,
            "fundamental": 0.30,
            "capital": 0.15,
            "sentiment": 0.15,
            "momentum": 0.15,
        }
        assert config.sideways == {
            "technical": 0.30,
            "fundamental": 0.20,
            "capital": 0.15,
            "sentiment": 0.15,
            "momentum": 0.20,
        }

    def test_weights_sum_to_one(self) -> None:
        config = FactorWeightConfig()
        assert abs(sum(config.bull.values()) - 1.0) < 1e-6
        assert abs(sum(config.bear.values()) - 1.0) < 1e-6
        assert abs(sum(config.sideways.values()) - 1.0) < 1e-6


class TestSignalConfig:
    """信号生成配置测试。"""

    def test_default_values(self) -> None:
        config = SignalConfig()
        assert config.min_buy_votes == 3
        assert config.min_sell_votes == 3
        assert config.factor_buy_threshold == 70.0
        assert config.factor_sell_threshold == 30.0
        assert config.technical_buy_threshold == 75.0
        assert config.technical_sell_threshold == 25.0
        assert config.atr_target_multiplier == 2.0
        assert config.atr_stop_multiplier == 1.5
        assert config.min_risk_reward == 2.0


class TestRealtimeConfig:
    """实时提醒配置测试。"""

    def test_default_values(self) -> None:
        config = RealtimeConfig()
        assert config.check_interval_minutes == 30
        assert config.score_jump_threshold == 25.0
        assert config.north_flow_alert == 100e8


class TestBacktestConfig:
    """回测配置测试。"""

    def test_default_values(self) -> None:
        config = BacktestConfig()
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2025-12-31"
        assert config.pool_size == 50
        assert config.hold_days == [1, 3, 5, 10]
        assert config.buy_threshold == 70.0
        assert config.sell_threshold == 30.0
        assert config.commission_rate == 0.001
        assert config.slippage == 0.001
        assert config.initial_capital == 100000.0


class TestAppConfigV2:
    """AppConfig V2 扩展测试。"""

    def test_has_new_config_fields(self) -> None:
        config = AppConfig()
        assert hasattr(config, "regime")
        assert hasattr(config, "factor_weights")
        assert hasattr(config, "signal")
        assert hasattr(config, "realtime")
        assert hasattr(config, "backtest")
        assert hasattr(config, "use_v2_pipeline")

    def test_default_v2_pipeline_disabled(self) -> None:
        config = AppConfig()
        assert config.use_v2_pipeline is False

    def test_v2_configs_are_correct_types(self) -> None:
        config = AppConfig()
        assert isinstance(config.regime, RegimeConfig)
        assert isinstance(config.factor_weights, FactorWeightConfig)
        assert isinstance(config.signal, SignalConfig)
        assert isinstance(config.realtime, RealtimeConfig)
        assert isinstance(config.backtest, BacktestConfig)
