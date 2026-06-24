"""情绪面因子测试。"""

from __future__ import annotations

import pytest


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
        # 模拟 PolicyImpact 对象
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


class TestCalcSentimentFactor:
    """综合情绪因子测试。"""

    def test_returns_dict(self):
        from src.factors.sentiment import calc_sentiment_factor
        result = calc_sentiment_factor(50, 50, 1.0)
        assert isinstance(result, dict)
        assert "market_sentiment" in result
        assert "news_sentiment" in result
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
