"""情绪面因子计算.

子因子：
- 市场情绪得分（涨跌停比、涨跌家数比）
- 新闻情绪得分（LLM 政策分析结果）
"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def _calc_market_sentiment(limit_up: int, limit_down: int, advance_decline_ratio: float) -> float:
    """市场情绪得分.

    Args:
        limit_up: 涨停家数。
        limit_down: 跌停家数。
        advance_decline_ratio: 涨跌家数比。

    Returns:
        评分 0~100。
    """
    score = 50.0

    # 涨跌停比
    total = limit_up + limit_down
    if total > 0:
        up_ratio = limit_up / total
        # 涨停占比越高越乐观
        score += (up_ratio - 0.5) * 40

    # 涨跌家数比
    if advance_decline_ratio > 3.0:
        score += 15
    elif advance_decline_ratio > 2.0:
        score += 10
    elif advance_decline_ratio > 1.5:
        score += 5
    elif advance_decline_ratio > 1.0:
        score += 2
    elif advance_decline_ratio > 0.7:
        score -= 2
    elif advance_decline_ratio > 0.5:
        score -= 5
    elif advance_decline_ratio > 0.3:
        score -= 10
    else:
        score -= 15

    return min(max(score, 0), 100)


def _calc_news_sentiment(policy_impacts: list) -> float:
    """新闻情绪得分.

    从 LLM 政策分析结果中提取情绪分数。

    Args:
        policy_impacts: 政策影响分析结果列表。
            每个元素应有 sentiment_score (0-100) 或 impact_score (-1~1) 属性。

    Returns:
        评分 0~100。
    """
    if not policy_impacts:
        return 50.0

    try:
        scores = []
        for impact in policy_impacts:
            # 尝试直接获取 sentiment_score
            if hasattr(impact, "sentiment_score"):
                scores.append(float(impact.sentiment_score))
            # 尝试从 dict 获取
            elif isinstance(impact, dict):
                if "sentiment_score" in impact:
                    scores.append(float(impact["sentiment_score"]))
                elif "impact_score" in impact:
                    # impact_score 范围 -1~1，映射到 0~100
                    scores.append((float(impact["impact_score"]) + 1) * 50)
            # PolicyImpact 对象的 impact 属性
            elif hasattr(impact, "impact"):
                val = float(getattr(impact, "impact", 0))
                # 假设 impact 范围 -1~1
                scores.append((val + 1) * 50)

        if not scores:
            return 50.0

        # 取平均值
        avg = sum(scores) / len(scores)
        return round(min(max(avg, 0), 100), 2)
    except Exception as e:
        logger.warning(f"新闻情绪计算异常: {e}")
        return 50.0


def calc_sentiment_factor(
    limit_up: int = 0,
    limit_down: int = 0,
    advance_decline_ratio: float = 1.0,
    policy_impacts: list | None = None,
) -> dict[str, float]:
    """计算情绪面因子综合评分.

    Args:
        limit_up: 涨停家数。
        limit_down: 跌停家数。
        advance_decline_ratio: 涨跌家数比。
        policy_impacts: 政策影响分析结果列表。

    Returns:
        dict with keys: market_sentiment, news_sentiment, score。
    """
    try:
        market = _calc_market_sentiment(limit_up, limit_down, advance_decline_ratio)
        news = _calc_news_sentiment(policy_impacts or [])

        # 市场情绪权重 60%，新闻情绪 40%
        score = round(market * 0.6 + news * 0.4, 2)

        return {
            "market_sentiment": market,
            "news_sentiment": news,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"情绪因子计算异常: {e}")
        return {"market_sentiment": 50.0, "news_sentiment": 50.0, "score": 50.0}
