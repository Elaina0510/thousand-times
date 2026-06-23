"""多因子引擎 — 计算和聚合所有因子。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class FactorScores:
    """单只股票的因子评分汇总。"""

    code: str = ""
    name: str = ""
    technical: float = 50.0
    fundamental: float = 50.0
    capital: float = 50.0
    sentiment: float = 50.0
    momentum: float = 50.0
    total: float = 50.0
    rank_percentile: float = 50.0


def calc_factors(data: object, config: object, regime_state: str = "sideways") -> list[FactorScores]:
    """计算所有股票的因子评分.

    Args:
        data: DataBundle 数据包。
        config: AppConfig 配置。
        regime_state: 市场环境状态。

    Returns:
        FactorScores 列表，按 total 降序排列。
    """
    from src.factors.technical import calc_technical_factor
    from src.factors.fundamental import calc_fundamental_factor
    from src.factors.capital import calc_capital_factor
    from src.factors.sentiment import calc_sentiment_factor
    from src.factors.momentum import calc_momentum_factor

    stock_pool = getattr(data, "stock_pool", pd.DataFrame())
    kline_cache = getattr(data, "kline_cache", {})
    fundamental_cache = getattr(data, "fundamental_cache", {})
    north_flow = getattr(data, "north_flow", pd.DataFrame())
    limit_up = getattr(data, "limit_up_count", 0)
    limit_down = getattr(data, "limit_down_count", 0)
    ad_ratio = getattr(data, "advance_decline_ratio", 1.0)

    # 获取权重
    factor_weights = getattr(config, "factor_weights", None)
    if factor_weights:
        weights_map = {"bull": factor_weights.bull, "bear": factor_weights.bear, "sideways": factor_weights.sideways}
        weights = weights_map.get(regime_state, factor_weights.sideways)
    else:
        weights = {"technical": 0.30, "fundamental": 0.20, "capital": 0.15, "sentiment": 0.15, "momentum": 0.20}

    results: list[FactorScores] = []

    for _, row in stock_pool.iterrows():
        code = str(row.get("code", ""))
        name = str(row.get("name", ""))

        kline = kline_cache.get(code, pd.DataFrame())
        fund = fundamental_cache.get(code, None)

        tech_score = calc_technical_factor(kline)
        fund_score = calc_fundamental_factor(
            roe=fund.roe if fund else 0.0,
            eps=fund.eps if fund else 0.0,
            profit_growth=fund.profit_growth if fund else 0.0,
            pe_ttm=fund.pe_ttm if fund else 50.0,
        )
        cap_score = calc_capital_factor(north_flow)
        sent_score = calc_sentiment_factor(limit_up, limit_down, ad_ratio)
        mom_score = calc_momentum_factor(kline)

        total = (
            tech_score * weights.get("technical", 0.30)
            + fund_score * weights.get("fundamental", 0.20)
            + cap_score * weights.get("capital", 0.15)
            + sent_score * weights.get("sentiment", 0.15)
            + mom_score * weights.get("momentum", 0.20)
        )

        results.append(FactorScores(
            code=code, name=name,
            technical=tech_score, fundamental=fund_score,
            capital=cap_score, sentiment=sent_score,
            momentum=mom_score, total=round(total, 2),
        ))

    # 百分位排名
    if results:
        results.sort(key=lambda x: x.total, reverse=True)
        n = len(results)
        for i, fs in enumerate(results):
            fs.rank_percentile = round((1 - i / n) * 100, 1)

    return results
