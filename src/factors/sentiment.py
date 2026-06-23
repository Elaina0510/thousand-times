"""情绪面因子计算。"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def calc_sentiment_factor(limit_up: int, limit_down: int, advance_decline_ratio: float) -> float:
    """计算情绪面因子评分.

    Args:
        limit_up: 涨停家数。
        limit_down: 跌停家数。
        advance_decline_ratio: 涨跌家数比。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    try:
        score = 50.0

        # 涨跌停比
        total = limit_up + limit_down
        if total > 0:
            up_ratio = limit_up / total
            score += (up_ratio - 0.5) * 40

        # 涨跌比
        if advance_decline_ratio > 2.0:
            score += 15
        elif advance_decline_ratio > 1.0:
            score += 5
        elif advance_decline_ratio < 0.5:
            score -= 15
        elif advance_decline_ratio < 1.0:
            score -= 5

        return min(max(score, 0), 100)
    except Exception as e:
        logger.warning(f"情绪因子计算异常: {e}")
        return 50.0
