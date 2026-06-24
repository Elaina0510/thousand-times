"""资金面因子测试。"""

from __future__ import annotations

import pandas as pd
import pytest


class TestNorthFlowScore:
    """北向资金得分测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.capital import _calc_north_flow_score
        assert _calc_north_flow_score(pd.DataFrame()) == 50.0

    def test_large_inflow(self):
        from src.factors.capital import _calc_north_flow_score
        df = pd.DataFrame({"当日成交净买额": [100e8] * 5})
        score = _calc_north_flow_score(df)
        assert score >= 70

    def test_large_outflow(self):
        from src.factors.capital import _calc_north_flow_score
        df = pd.DataFrame({"当日成交净买额": [-100e8] * 5})
        score = _calc_north_flow_score(df)
        assert score <= 30

    def test_moderate_inflow(self):
        from src.factors.capital import _calc_north_flow_score
        df = pd.DataFrame({"净流入": [10e8] * 5})
        score = _calc_north_flow_score(df)
        assert 50 < score < 70


class TestMainFlowScore:
    """主力资金得分测试（stub）。"""

    def test_returns_50(self):
        from src.factors.capital import _calc_main_flow_score
        assert _calc_main_flow_score() == 50.0


class TestCalcCapitalFactor:
    """综合资金因子测试。"""

    def test_returns_dict(self):
        from src.factors.capital import calc_capital_factor
        result = calc_capital_factor(pd.DataFrame())
        assert isinstance(result, dict)
        assert "north_flow" in result
        assert "main_flow" in result
        assert "score" in result

    def test_all_scores_in_range(self):
        from src.factors.capital import calc_capital_factor
        result = calc_capital_factor(pd.DataFrame())
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"
