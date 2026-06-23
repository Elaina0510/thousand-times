"""基本面因子计算。"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def calc_fundamental_factor(roe: float, eps: float, profit_growth: float, pe_ttm: float) -> float:
    """计算基本面因子评分.

    Args:
        roe: 净资产收益率 (%).
        eps: 每股收益。
        profit_growth: 净利润增速 (%).
        pe_ttm: 市盈率(TTM)。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    try:
        score = 50.0

        # ROE 评分
        if roe > 15:
            score += 15
        elif roe > 10:
            score += 5

        # EPS 评分
        if eps > 0:
            score += 10

        # 成长性
        if profit_growth > 20:
            score += 15
        elif profit_growth > 0:
            score += 5

        # 估值（PE 越低越好）
        if pe_ttm < 20:
            score += 10
        elif pe_ttm < 40:
            score += 0
        else:
            score -= 10

        return min(max(score, 0), 100)
    except Exception as e:
        logger.warning(f"基本面因子计算异常: {e}")
        return 50.0
