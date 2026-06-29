"""资金面因子测试。"""

from __future__ import annotations

import pandas as pd


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


class TestStockFlowScore:
    """个股资金流向得分测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.capital import _calc_stock_flow_score
        assert _calc_stock_flow_score(pd.DataFrame()) == 50.0

    def _make_kline(self, closes, volumes=None):
        """构造测试用K线DataFrame。"""
        n = len(closes)
        if volumes is None:
            volumes = [1e7] * n
        return pd.DataFrame({
            "close": closes,
            "volume": volumes,
        })

    def test_volume_up_with_price_up(self):
        """放量上涨 → 资金流入，分数应偏高。"""
        from src.factors.capital import _calc_stock_flow_score
        closes = [10.0] * 14 + [10.2, 10.3, 10.5, 10.8, 11.0, 11.5]  # 连续涨
        vols = [1e7] * 14 + [3e7] * 6  # 放量
        kline = self._make_kline(closes, vols)
        score = _calc_stock_flow_score(kline)
        assert score >= 60, f"放量上涨应偏高，实际: {score}"

    def test_volume_up_with_price_down(self):
        """放量下跌 → 资金出逃，分数应偏低。"""
        from src.factors.capital import _calc_stock_flow_score
        closes = [10.0] * 14 + [9.8, 9.7, 9.5, 9.3, 9.0, 8.5]
        vols = [1e7] * 14 + [3e7] * 6
        kline = self._make_kline(closes, vols)
        score = _calc_stock_flow_score(kline)
        assert score <= 40, f"放量下跌应偏低，实际: {score}"

    def test_short_data_returns_neutral(self):
        from src.factors.capital import _calc_stock_flow_score
        kline = self._make_kline([10.0, 10.1, 10.2])
        assert _calc_stock_flow_score(kline) == 50.0


class TestSectorFlowScore:
    """行业资金流向得分测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.capital import _calc_sector_flow_score
        assert _calc_sector_flow_score("", pd.DataFrame()) == 50.0

    def test_no_industry_returns_neutral(self):
        from src.factors.capital import _calc_sector_flow_score
        df = pd.DataFrame({"名称": ["银行", "医药"], "主力净流入-净额": [10e8, -5e8]})
        assert _calc_sector_flow_score("", df) == 50.0

    def test_industry_matched(self):
        """匹配到行业后应返回非50的分数。"""
        from src.factors.capital import _calc_sector_flow_score
        df = pd.DataFrame({
            "名称": ["银行", "医药", "计算机"],
            "主力净流入-净额": [30e8, 10e8, -5e8],
        })
        score = _calc_sector_flow_score("银行", df)
        # 银行净流入最高，分数应偏高
        assert score >= 50, f"银行业资金流入最高，分数应≥50，实际: {score}"

    def test_industry_not_found(self):
        """行业未匹配时返回中性。"""
        from src.factors.capital import _calc_sector_flow_score
        df = pd.DataFrame({
            "名称": ["银行", "医药"],
            "主力净流入-净额": [10e8, -5e8],
        })
        assert _calc_sector_flow_score("航空航天", df) == 50.0


class TestCalcCapitalFactor:
    """综合资金因子测试。"""

    def test_returns_dict(self):
        from src.factors.capital import calc_capital_factor
        result = calc_capital_factor(pd.DataFrame())
        assert isinstance(result, dict)
        assert "north_flow" in result
        assert "stock_flow" in result
        assert "sector_flow" in result
        assert "score" in result

    def test_all_scores_in_range(self):
        from src.factors.capital import calc_capital_factor
        result = calc_capital_factor(pd.DataFrame())
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"

    def test_with_kline_and_industry(self):
        """传入逐股数据后分数应有分化。"""
        from src.factors.capital import calc_capital_factor
        # 构造放量上涨的K线
        closes = [10.0] * 14 + [10.2, 10.3, 10.5, 10.8, 11.0, 11.5]
        vols = [1e7] * 14 + [3e7] * 6
        kline = pd.DataFrame({"close": closes, "volume": vols})

        sector_df = pd.DataFrame({
            "名称": ["银行", "医药", "计算机"],
            "主力净流入-净额": [30e8, 10e8, -5e8],
        })

        result = calc_capital_factor(
            north_flow=pd.DataFrame(),
            kline=kline,
            industry="银行",
            sector_flow=sector_df,
        )
        # 放量上涨 + 银行业资金流入最高 → 综合分应显著偏离50
        assert result["score"] != 50.0, "传入逐股数据后分数不应再是中性的50"
        assert result["stock_flow"] >= 60, "放量上涨个股资金流向应偏高"
