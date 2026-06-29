"""情绪面因子计算.

子因子：
- 市场情绪得分（涨跌停比、涨跌家数比）
- 行业新闻情绪得分（LLM 政策分析结果，按行业区分）
- 个股情绪得分（K线形态：涨跌停/量能异常/连续涨跌）
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _get_close(kline: pd.DataFrame) -> pd.Series:
    """获取收盘价列。"""
    close_col = "收盘" if "收盘" in kline.columns else "close"
    return kline[close_col].astype(float)


def _get_volume(kline: pd.DataFrame) -> pd.Series:
    """获取成交量列。"""
    vol_col = "成交量" if "成交量" in kline.columns else "volume"
    return kline[vol_col].astype(float)


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
    """新闻情绪得分（全市场）.

    从 LLM 政策分析结果中提取情绪分数。

    Args:
        policy_impacts: 政策影响分析结果列表。

    Returns:
        评分 0~100。
    """
    if not policy_impacts:
        return 50.0

    try:
        scores = []
        for impact in policy_impacts:
            if hasattr(impact, "sentiment_score"):
                scores.append(float(impact.sentiment_score))
            elif isinstance(impact, dict):
                if "sentiment_score" in impact:
                    scores.append(float(impact["sentiment_score"]))
                elif "impact_score" in impact:
                    scores.append((float(impact["impact_score"]) + 1) * 50)
            elif hasattr(impact, "impact"):
                val = float(getattr(impact, "impact", 0))
                scores.append((val + 1) * 50)

        if not scores:
            return 50.0

        avg = sum(scores) / len(scores)
        return round(min(max(avg, 0), 100), 2)
    except Exception as e:
        logger.warning(f"新闻情绪计算异常: {e}")
        return 50.0


def _calc_industry_news_sentiment(industry: str, policy_impacts: list) -> float:
    """行业新闻情绪得分.

    根据股票所属行业，从 policy_impacts 中提取该行业相关的政策情绪。

    Args:
        industry: 股票所属行业名称。
        policy_impacts: 政策影响分析结果列表。

    Returns:
        评分 0~100。
    """
    if not industry or not policy_impacts:
        return 50.0

    try:
        from news_analysis import get_industry_impact_score

        raw = get_industry_impact_score(industry, policy_impacts)
        # impact_score 范围 -20~+20，映射到 0~100
        score = 50 + raw * 2.5
        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.debug(f"行业新闻情绪计算异常: {e}")
        return 50.0


def _calc_stock_sentiment(kline: pd.DataFrame) -> float:
    """个股情绪得分.

    基于K线形态判断个股情绪的极端程度：
    - 涨跌停检测（±9.5%以上为极端情绪）
    - 连续涨跌天数（趋势强度）
    - 量能异常（放量 = 情绪放大器）

    Args:
        kline: 个股K线数据。

    Returns:
        评分 0~100。
    """
    if kline is None or kline.empty or len(kline) < 5:
        return 50.0

    try:
        closes = _get_close(kline)
        volumes = _get_volume(kline)

        score = 50.0

        # 1. 近期涨跌停检测
        if len(closes) >= 2:
            daily_change = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
            if daily_change > 9.5:
                score += 20
            elif daily_change > 7:
                score += 12
            elif daily_change > 5:
                score += 6
            elif daily_change < -9.5:
                score -= 20
            elif daily_change < -7:
                score -= 12
            elif daily_change < -5:
                score -= 6

        # 2. 连续涨跌天数（近5日）
        if len(closes) >= 6:
            up_days = sum(1 for i in range(-5, 0) if closes.iloc[i] > closes.iloc[i - 1])
            if up_days >= 4:
                score += 8
            elif up_days <= 1:
                score -= 8

        # 3. 量能异常（情绪放大器）
        avg_vol = volumes.tail(20).mean() if len(volumes) >= 20 else volumes.mean()
        if avg_vol > 0:
            vol_ratio = volumes.iloc[-1] / avg_vol
            if vol_ratio > 3:
                if len(closes) >= 2 and closes.iloc[-1] > closes.iloc[-2]:
                    score += 10
                else:
                    score -= 10
            elif vol_ratio > 2:
                if len(closes) >= 2 and closes.iloc[-1] > closes.iloc[-2]:
                    score += 5
                else:
                    score -= 5

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"个股情绪计算异常: {e}")
        return 50.0


def calc_sentiment_factor(
    limit_up: int = 0,
    limit_down: int = 0,
    advance_decline_ratio: float = 1.0,
    policy_impacts: list | None = None,
    kline: pd.DataFrame | None = None,
    industry: str = "",
) -> dict[str, float]:
    """计算情绪面因子综合评分（逐股差异化）.

    Args:
        limit_up: 涨停家数。
        limit_down: 跌停家数。
        advance_decline_ratio: 涨跌家数比。
        policy_impacts: 政策影响分析结果列表。
        kline: 个股K线数据（用于个股情绪计算）。
        industry: 股票所属行业（用于行业级新闻情绪）。

    Returns:
        dict with keys: market_sentiment, news_sentiment, stock_sentiment, score。
    """
    try:
        market = _calc_market_sentiment(limit_up, limit_down, advance_decline_ratio)

        # 行业新闻情绪（有行业+政策数据时使用行业级，否则用全市场）
        if industry and policy_impacts:
            news = _calc_industry_news_sentiment(industry, policy_impacts)
        else:
            news = _calc_news_sentiment(policy_impacts or [])

        # 个股情绪（_calc_stock_sentiment 内部处理空DataFrame）
        stock_sent = _calc_stock_sentiment(kline) if kline is not None else 50.0

        # 权重: 市场40%, 行业新闻30%, 个股30%
        score = round(market * 0.4 + news * 0.3 + stock_sent * 0.3, 2)

        return {
            "market_sentiment": market,
            "news_sentiment": news,
            "stock_sentiment": stock_sent,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"情绪因子计算异常: {e}")
        return {"market_sentiment": 50.0, "news_sentiment": 50.0, "stock_sentiment": 50.0, "score": 50.0}
