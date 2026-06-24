"""新增数据源测试（sector_flow, macro）。"""

from __future__ import annotations

import pandas as pd
import pytest


class TestSectorFlow:
    """行业资金流向测试。"""

    def test_calc_sector_flow_score_empty(self):
        from src.data_sources.sector_flow import calc_sector_flow_score
        score = calc_sector_flow_score(pd.DataFrame(), pd.DataFrame())
        assert score == 50.0

    def test_calc_sector_flow_score_positive(self):
        """大部分行业净流入为正时应得高分。"""
        from src.data_sources.sector_flow import calc_sector_flow_score
        df = pd.DataFrame({
            "名称": ["银行", "证券", "医药", "科技", "消费"],
            "主力净流入-净额": [10e8, 5e8, 3e8, -1e8, -2e8],
        })
        score = calc_sector_flow_score(pd.DataFrame(), df)
        assert score > 50

    def test_calc_sector_flow_score_negative(self):
        """大部分行业净流入为负时应得低分。"""
        from src.data_sources.sector_flow import calc_sector_flow_score
        df = pd.DataFrame({
            "名称": ["银行", "证券", "医药", "科技", "消费"],
            "主力净流入-净额": [-10e8, -5e8, -3e8, 1e8, 2e8],
        })
        score = calc_sector_flow_score(pd.DataFrame(), df)
        assert score < 50

    def test_fetch_sector_flow_top_n_empty(self):
        from src.data_sources.sector_flow import fetch_sector_flow_top_n
        # 无法连接外部API时，应返回空列表
        result = fetch_sector_flow_top_n(3)
        assert isinstance(result, list)


class TestMacroIndicators:
    """宏观指标测试。"""

    def test_calc_macro_score_empty(self):
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({})
        assert score == 50.0

    def test_calc_macro_score_all_none(self):
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({"cpi": None, "pmi": None, "m2_growth": None})
        assert score == 50.0

    def test_calc_macro_score_bullish(self):
        """PMI > 50 + 温和通胀 + 适度宽松 → 看多。"""
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({"pmi": 52, "cpi": 2.0, "m2_growth": 10})
        assert score >= 70

    def test_calc_macro_score_bearish(self):
        """PMI < 50 + 通缩 + 偏紧 → 看空。"""
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({"pmi": 47, "cpi": -1.0, "m2_growth": 4})
        assert score <= 30

    def test_calc_macro_score_pmi_only(self):
        """只有 PMI 数据。"""
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({"pmi": 51, "cpi": None, "m2_growth": None})
        assert score > 50

    def test_calc_macro_score_high_cpi(self):
        """高通胀应减分。"""
        from src.data_sources.macro import calc_macro_score
        score = calc_macro_score({"pmi": None, "cpi": 6.0, "m2_growth": None})
        assert score < 50


class TestConfigYAML:
    """YAML 配置加载测试。"""

    def test_load_config_default(self):
        """默认加载（不传 yaml_path）应正常工作。"""
        from src.config import load_config
        config = load_config(yaml_path="nonexistent.yaml")
        assert config is not None
        assert config.use_v2_pipeline is False

    def test_apply_yaml_overrides(self, tmp_path):
        """从 YAML 文件加载配置覆盖。"""
        import yaml
        from src.config import AppConfig, _apply_yaml_overrides

        yaml_data = {
            "use_v2_pipeline": True,
            "lookback_days": 90,
            "regime": {"ma_short": 10},
            "signal": {"min_buy_votes": 2},
            "factor_weights": {
                "bull": {"technical": 0.40},
            },
        }
        yaml_file = tmp_path / "test_config.yaml"
        yaml_file.write_text(yaml.dump(yaml_data), encoding="utf-8")

        config = AppConfig()
        _apply_yaml_overrides(config, str(yaml_file))

        assert config.use_v2_pipeline is True
        assert config.lookback_days == 90
        assert config.regime.ma_short == 10
        assert config.signal.min_buy_votes == 2
        assert config.factor_weights.bull["technical"] == 0.40

    def test_apply_yaml_missing_file(self):
        """不存在的 YAML 文件不应报错。"""
        from src.config import AppConfig, _apply_yaml_overrides
        config = AppConfig()
        _apply_yaml_overrides(config, "/nonexistent/path.yaml")
        assert config.use_v2_pipeline is False
