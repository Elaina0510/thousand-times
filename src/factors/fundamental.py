"""基本面因子计算.

子因子：
- 估值得分（PE/PB 分位数）
- 盈利能力（ROE、毛利率）
- 成长性（利润增速、营收增速）
"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def _calc_valuation_score(pe_ttm: float) -> float:
    """估值得分.

    PE 越低越好（价值型）。

    Args:
        pe_ttm: 市盈率(TTM)。

    Returns:
        评分 0~100。
    """
    if pe_ttm <= 0:
        return 30.0  # 负PE通常意味着亏损

    if pe_ttm < 10:
        return 80.0
    elif pe_ttm < 15:
        return 70.0
    elif pe_ttm < 20:
        return 60.0
    elif pe_ttm < 30:
        return 50.0
    elif pe_ttm < 50:
        return 35.0
    elif pe_ttm < 100:
        return 20.0
    else:
        return 10.0


def _calc_profitability_score(roe: float, eps: float) -> float:
    """盈利能力得分.

    Args:
        roe: 净资产收益率 (%)。
        eps: 每股收益。

    Returns:
        评分 0~100。
    """
    score = 50.0

    # ROE 评分
    if roe > 20:
        score += 20
    elif roe > 15:
        score += 15
    elif roe > 10:
        score += 8
    elif roe > 5:
        score += 3
    elif roe < 0:
        score -= 15

    # EPS 评分
    if eps > 1.0:
        score += 10
    elif eps > 0.5:
        score += 7
    elif eps > 0:
        score += 3
    else:
        score -= 10

    return min(max(score, 0), 100)


def _calc_growth_score(profit_growth: float, revenue_growth: float = 0.0) -> float:
    """成长性得分.

    Args:
        profit_growth: 净利润增速 (%)。
        revenue_growth: 营收增速 (%)。

    Returns:
        评分 0~100。
    """
    score = 50.0

    # 利润增速
    if profit_growth > 50:
        score += 20
    elif profit_growth > 30:
        score += 15
    elif profit_growth > 20:
        score += 10
    elif profit_growth > 10:
        score += 5
    elif profit_growth > 0:
        score += 2
    elif profit_growth > -10:
        score -= 5
    elif profit_growth > -30:
        score -= 10
    else:
        score -= 20

    # 营收增速（辅助）
    if revenue_growth > 20:
        score += 5
    elif revenue_growth > 10:
        score += 3
    elif revenue_growth < 0:
        score -= 3

    return min(max(score, 0), 100)


def calc_fundamental_factor(
    roe: float = 0.0,
    eps: float = 0.0,
    profit_growth: float = 0.0,
    pe_ttm: float = 50.0,
    revenue_growth: float = 0.0,
) -> dict[str, float]:
    """计算基本面因子综合评分.

    Args:
        roe: 净资产收益率 (%)。
        eps: 每股收益。
        profit_growth: 净利润增速 (%)。
        pe_ttm: 市盈率(TTM)。
        revenue_growth: 营收增速 (%)。

    Returns:
        dict with keys: valuation, profitability, growth, score。
    """
    try:
        valuation = _calc_valuation_score(pe_ttm)
        profitability = _calc_profitability_score(roe, eps)
        growth = _calc_growth_score(profit_growth, revenue_growth)

        # 等权平均
        score = round((valuation + profitability + growth) / 3, 2)

        return {
            "valuation": valuation,
            "profitability": profitability,
            "growth": growth,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"基本面因子计算异常: {e}")
        return {"valuation": 50.0, "profitability": 50.0, "growth": 50.0, "score": 50.0}
