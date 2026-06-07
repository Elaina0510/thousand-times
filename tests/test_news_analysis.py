"""news_analysis.py 单元测试。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from news_analysis import (
    NewsItem,
    PolicyImpact,
    analyze_policy_impact,
    fetch_news,
    filter_by_credibility,
    get_industry_impact_score,
)


def _make_news_item(
    title: str = "央行宣布降准0.5个百分点",
    source: str = "新浪财经",
) -> NewsItem:
    """创建测试用新闻。"""
    return NewsItem(
        title=title,
        source=source,
        url="https://finance.sina.com.cn/test",
        publish_time=datetime.now(),
        content="测试新闻内容",
    )


def _make_policy_impact(
    title: str = "央行宣布降准0.5个百分点",
    industries: list[str] | None = None,
    direction: str = "positive",
    score: float = 17.5,
) -> PolicyImpact:
    """创建测试用政策影响。"""
    return PolicyImpact(
        news_title=title,
        affected_industries=industries or ["银行", "地产"],
        impact_direction=direction,
        impact_degree="direct",
        impact_score=score,
        summary="利好银行、地产板块",
    )


class TestFilterByCredibility:
    """可信度过滤测试。"""

    def test_credible_sources(self) -> None:
        """可信来源保留。"""
        news = [
            _make_news_item(source="新浪财经"),
            _make_news_item(source="东方财富"),
            _make_news_item(source="同花顺"),
        ]
        result = filter_by_credibility(news)
        assert len(result) == 3

    def test_non_credible_sources(self) -> None:
        """不可信来源过滤。"""
        news = [
            _make_news_item(source="新浪财经"),
            _make_news_item(source="某自媒体"),
            _make_news_item(source="论坛传闻"),
        ]
        result = filter_by_credibility(news)
        assert len(result) == 1

    def test_empty_source(self) -> None:
        """空来源保留。"""
        news = [_make_news_item(source="")]
        result = filter_by_credibility(news)
        assert len(result) == 1

    def test_empty_list(self) -> None:
        """空列表。"""
        result = filter_by_credibility([])
        assert len(result) == 0


class TestAnalyzePolicyImpact:
    """政策影响分析测试。"""

    def test_no_news(self) -> None:
        """无新闻返回空列表。"""
        result = analyze_policy_impact([], {"api_url": "", "api_key": ""})
        assert result == []

    def test_no_llm_config(self) -> None:
        """无LLM配置返回默认中性评分。"""
        news = [_make_news_item()]
        result = analyze_policy_impact(news, {"api_url": "", "api_key": ""})

        assert len(result) == 1
        assert result[0].impact_direction == "neutral"
        assert result[0].impact_score == 5.0

    @patch("news_analysis.requests.post")
    def test_llm_success(self, mock_post: MagicMock) -> None:
        """LLM成功返回解析结果。"""
        news = [_make_news_item()]

        # 模拟LLM返回
        llm_response = [
            {
                "news_title": "央行宣布降准0.5个百分点",
                "affected_industries": ["银行", "地产"],
                "impact_direction": "positive",
                "impact_degree": "direct",
                "impact_score": 17.5,
                "summary": "利好银行、地产板块",
            }
        ]
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": json.dumps(llm_response)}}]},
        )

        result = analyze_policy_impact(
            news,
            {"api_url": "https://api.example.com", "api_key": "test-key"},
        )

        assert len(result) == 1
        assert result[0].impact_direction == "positive"
        assert result[0].impact_score == 17.5

    @patch("news_analysis.requests.post")
    def test_llm_failure(self, mock_post: MagicMock) -> None:
        """LLM调用失败返回默认中性评分。"""
        news = [_make_news_item()]
        mock_post.side_effect = Exception("网络超时")

        result = analyze_policy_impact(
            news,
            {"api_url": "https://api.example.com", "api_key": "test-key"},
        )

        assert len(result) == 1
        assert result[0].impact_direction == "neutral"
        assert result[0].impact_score == 5.0

    @patch("news_analysis.requests.post")
    def test_llm_invalid_json(self, mock_post: MagicMock) -> None:
        """LLM返回无效JSON返回默认中性评分。"""
        news = [_make_news_item()]
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "这不是JSON"}}]},
        )

        result = analyze_policy_impact(
            news,
            {"api_url": "https://api.example.com", "api_key": "test-key"},
        )

        assert len(result) == 1
        assert result[0].impact_direction == "neutral"


class TestGetIndustryImpactScore:
    """行业影响评分测试。"""

    def test_direct_impact(self) -> None:
        """直接影响。"""
        impacts = [_make_policy_impact(industries=["银行"], score=17.5)]
        score = get_industry_impact_score("银行", impacts)
        assert score == 17.5

    def test_indirect_impact(self) -> None:
        """间接影响（整体市场）。"""
        impacts = [_make_policy_impact(industries=["整体市场"], score=5.0)]
        score = get_industry_impact_score("银行", impacts)
        assert score == 5.0

    def test_no_impact(self) -> None:
        """无影响返回默认中性。"""
        impacts = [_make_policy_impact(industries=["半导体"], score=17.5)]
        score = get_industry_impact_score("银行", impacts)
        assert score == 5.0

    def test_multiple_impacts(self) -> None:
        """多条影响取平均。"""
        impacts = [
            _make_policy_impact(industries=["银行"], score=17.5),
            _make_policy_impact(industries=["银行"], score=10.0),
        ]
        score = get_industry_impact_score("银行", impacts)
        assert score == 13.75

    def test_empty_impacts(self) -> None:
        """空影响列表返回默认中性。"""
        score = get_industry_impact_score("银行", [])
        assert score == 5.0

    def test_score_clamped(self) -> None:
        """评分限制在 [-20, 20] 范围。"""
        impacts = [_make_policy_impact(industries=["银行"], score=30.0)]
        score = get_industry_impact_score("银行", impacts)
        assert score == 20.0
