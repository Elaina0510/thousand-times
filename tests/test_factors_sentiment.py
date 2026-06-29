"""情绪面因子测试。"""

from __future__ import annotations

import pandas as pd


class TestMarketSentiment:
    """市场情绪得分测试。"""

    def test_balanced_market(self):
        from src.factors.sentiment import _calc_market_sentiment
        score = _calc_market_sentiment(50, 50, 1.0)
        assert 40 <= score <= 60

    def test_bullish_market(self):
        from src.factors.sentiment import _calc_market_sentiment
        score = _calc_market_sentiment(100, 10, 3.0)
        assert score >= 70

    def test_bearish_market(self):
        from src.factors.sentiment import _calc_market_sentiment
        score = _calc_market_sentiment(10, 100, 0.3)
        assert score <= 30

    def test_no_data(self):
        from src.factors.sentiment import _calc_market_sentiment
        score = _calc_market_sentiment(0, 0, 1.0)
        assert 40 <= score <= 60


class TestNewsSentiment:
    """新闻情绪得分测试。"""

    def test_empty_returns_neutral(self):
        from src.factors.sentiment import _calc_news_sentiment
        assert _calc_news_sentiment([]) == 50.0

    def test_positive_news(self):
        from src.factors.sentiment import _calc_news_sentiment
        class MockImpact:
            sentiment_score = 80
        score = _calc_news_sentiment([MockImpact()])
        assert score >= 70

    def test_negative_news(self):
        from src.factors.sentiment import _calc_news_sentiment
        class MockImpact:
            sentiment_score = 20
        score = _calc_news_sentiment([MockImpact()])
        assert score <= 30

    def test_dict_impact(self):
        from src.factors.sentiment import _calc_news_sentiment
        impacts = [{"sentiment_score": 75}, {"sentiment_score": 65}]
        score = _calc_news_sentiment(impacts)
        assert score >= 60


class TestStockSentiment:
    """个股情绪得分测试。"""

    def _make_kline(self, closes, volumes=None):
        """构造测试用K线 DataFrame。"""
        n = len(closes)
        if volumes is None:
            volumes = [1e7] * n
        return pd.DataFrame({"close": closes, "volume": volumes})

    def test_empty_returns_neutral(self):
        from src.factors.sentiment import _calc_stock_sentiment
        assert _calc_stock_sentiment(pd.DataFrame()) == 50.0

    def test_limit_up(self):
        """涨停检测（涨幅>9.5%）→ 情绪极度乐观。"""
        from src.factors.sentiment import _calc_stock_sentiment
        closes = [10.0] * 19 + [10.98]  # 约+9.8%
        kline = self._make_kline(closes)
        score = _calc_stock_sentiment(kline)
        assert score > 60, f"涨停应偏高，实际: {score}"

    def test_limit_down(self):
        """跌停检测（跌幅>9.5%）→ 情绪极度悲观。"""
        from src.factors.sentiment import _calc_stock_sentiment
        closes = [10.0] * 19 + [9.02]  # 约-9.8%
        kline = self._make_kline(closes)
        score = _calc_stock_sentiment(kline)
        assert score < 40, f"跌停应偏低，实际: {score}"

    def test_continuous_up(self):
        """连续上涨 → 情绪高涨。"""
        from src.factors.sentiment import _calc_stock_sentiment
        closes = [10.0] * 14 + [10.1, 10.2, 10.3, 10.4, 10.5, 10.7]
        kline = self._make_kline(closes)
        score = _calc_stock_sentiment(kline)
        assert score >= 55, f"连续上涨应偏高，实际: {score}"

    def test_volume_spike_up(self):
        """放量大涨 → 情绪爆发。"""
        from src.factors.sentiment import _calc_stock_sentiment
        closes = [10.0] * 14 + [10.1, 10.2, 10.3, 10.5, 10.8, 11.2]
        vols = [1e7] * 14 + [5e7] * 6  # 5倍量
        kline = self._make_kline(closes, vols)
        score = _calc_stock_sentiment(kline)
        assert score >= 60, f"放量大涨应偏高，实际: {score}"


class TestCalcSentimentFactor:
    """综合情绪因子测试。"""

    def test_returns_dict(self):
        from src.factors.sentiment import calc_sentiment_factor
        result = calc_sentiment_factor(50, 50, 1.0)
        assert isinstance(result, dict)
        assert "market_sentiment" in result
        assert "news_sentiment" in result
        assert "stock_sentiment" in result
        assert "score" in result

    def test_with_policy_impacts(self):
        from src.factors.sentiment import calc_sentiment_factor
        class MockImpact:
            sentiment_score = 70
        result = calc_sentiment_factor(50, 50, 1.0, policy_impacts=[MockImpact()])
        assert result["news_sentiment"] >= 60

    def test_all_scores_in_range(self):
        from src.factors.sentiment import calc_sentiment_factor
        result = calc_sentiment_factor(100, 10, 3.0)
        for key, val in result.items():
            assert 0 <= val <= 100, f"{key} = {val} out of range"

    def test_with_kline_differentiation(self):
        """传入逐股K线后，涨停股 vs 跌停股应有显著分化。"""
        from src.factors.sentiment import calc_sentiment_factor

        # 涨停股
        up_closes = [10.0] * 19 + [11.0]
        up_kline = pd.DataFrame({"close": up_closes, "volume": [1e7] * 20})

        # 跌停股
        down_closes = [10.0] * 19 + [9.0]
        down_kline = pd.DataFrame({"close": down_closes, "volume": [1e7] * 20})

        up_result = calc_sentiment_factor(50, 50, 1.0, kline=up_kline)
        down_result = calc_sentiment_factor(50, 50, 1.0, kline=down_kline)

        assert up_result["stock_sentiment"] > down_result["stock_sentiment"], \
            f"涨停股情绪应>跌停股，实际: up={up_result['stock_sentiment']}, down={down_result['stock_sentiment']}"
        assert up_result["score"] > down_result["score"], \
            f"涨停股综合情绪应>跌停股，实际: up={up_result['score']}, down={down_result['score']}"
