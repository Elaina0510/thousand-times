"""资金面因子计算。"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def calc_capital_factor(north_flow: pd.DataFrame, fund_flow_score: float = 5.0) -> float:
    """计算资金面因子评分.

    Args:
        north_flow: 北向资金数据。
        fund_flow_score: ETF资金流向评分 0~10。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    try:
        score = 50.0

        # 北向资金
        if not north_flow.empty:
            net_col = None
            for col in ["当日成交净买额", "净流入"]:
                if col in north_flow.columns:
                    net_col = col
                    break
            if net_col:
                recent = north_flow[net_col].astype(float).tail(5).sum()
                if recent > 50e8:
                    score += 20
                elif recent > 0:
                    score += 10
                elif recent < -50e8:
                    score -= 20
                elif recent < 0:
                    score -= 10

        # ETF资金流向
        score += (fund_flow_score - 5) * 2

        return min(max(score, 0), 100)
    except Exception as e:
        logger.warning(f"资金因子计算异常: {e}")
        return 50.0
