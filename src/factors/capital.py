"""资金面因子计算.

子因子：
- 北向资金得分（近5日净流入）
- 主力资金得分（stub，待接入数据源）
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _calc_north_flow_score(north_flow: pd.DataFrame) -> float:
    """北向资金得分.

    基于近5日北向资金累计净流入。

    Args:
        north_flow: 北向资金数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if north_flow.empty:
        return 50.0

    try:
        net_col = None
        for col in ["当日成交净买额", "净流入"]:
            if col in north_flow.columns:
                net_col = col
                break

        if net_col is None:
            return 50.0

        recent = north_flow[net_col].astype(float).tail(5).sum()

        if recent > 100e8:
            return 85.0
        elif recent > 50e8:
            return 75.0
        elif recent > 20e8:
            return 65.0
        elif recent > 0:
            return 55.0
        elif recent > -20e8:
            return 45.0
        elif recent > -50e8:
            return 35.0
        elif recent > -100e8:
            return 25.0
        else:
            return 15.0
    except Exception as e:
        logger.warning(f"北向资金计算异常: {e}")
        return 50.0


def _calc_main_flow_score() -> float:
    """主力资金得分（stub）.

    待接入数据源（如 AKShare 资金流向数据）后实现。
    当前返回中性分数。

    Returns:
        评分 0~100，默认 50。
    """
    return 50.0


def calc_capital_factor(north_flow: pd.DataFrame) -> dict[str, float]:
    """计算资金面因子综合评分.

    Args:
        north_flow: 北向资金数据 DataFrame。

    Returns:
        dict with keys: north_flow, main_flow, score。
    """
    try:
        north_score = _calc_north_flow_score(north_flow)
        main_score = _calc_main_flow_score()

        # 北向资金权重 70%，主力资金 30%
        score = round(north_score * 0.7 + main_score * 0.3, 2)

        return {
            "north_flow": north_score,
            "main_flow": main_score,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"资金因子计算异常: {e}")
        return {"north_flow": 50.0, "main_flow": 50.0, "score": 50.0}
