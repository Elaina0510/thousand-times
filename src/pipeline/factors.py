"""多因子引擎 — 计算和聚合所有因子.

调用各因子模块计算类别分数，通过百分位排名标准化，
再根据市场环境动态加权合成总分。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class FactorScores:
    """单只股票的因子评分汇总。"""

    code: str = ""
    name: str = ""

    # 各因子类别分数（0-100）
    technical: float = 50.0
    fundamental: float = 50.0
    capital: float = 50.0
    sentiment: float = 50.0
    momentum: float = 50.0

    # 各因子子项详情（用于报告展示）
    technical_detail: dict[str, float] = field(default_factory=dict)
    fundamental_detail: dict[str, float] = field(default_factory=dict)
    capital_detail: dict[str, float] = field(default_factory=dict)
    sentiment_detail: dict[str, float] = field(default_factory=dict)
    momentum_detail: dict[str, float] = field(default_factory=dict)

    # 最终分数
    total: float = 50.0
    rank_percentile: float = 50.0


def calc_factors(data: object, config: object, regime_state: str = "sideways") -> list[FactorScores]:
    """计算所有股票的因子评分.

    Args:
        data: DataBundle 数据包。
        config: AppConfig 配置。
        regime_state: 市场环境状态 ("bull", "bear", "sideways")。

    Returns:
        FactorScores 列表，按 total 降序排列。
    """
    from factors.capital import calc_capital_factor
    from factors.fundamental import calc_fundamental_factor
    from factors.momentum import calc_momentum_factor
    from factors.sentiment import calc_sentiment_factor
    from factors.technical import calc_technical_factor

    stock_pool = getattr(data, "stock_pool", pd.DataFrame())
    kline_cache = getattr(data, "kline_cache", {})
    fundamental_cache = getattr(data, "fundamental_cache", {})
    north_flow = getattr(data, "north_flow", pd.DataFrame())
    limit_up = getattr(data, "limit_up_count", 0)
    limit_down = getattr(data, "limit_down_count", 0)
    ad_ratio = getattr(data, "advance_decline_ratio", 1.0)
    policy_impacts = getattr(data, "policy_impacts", [])
    index_kline = getattr(data, "index_kline", pd.DataFrame())
    sector_flow = getattr(data, "sector_flow", pd.DataFrame())

    # 获取权重
    factor_weights = getattr(config, "factor_weights", None)
    if factor_weights:
        weights_map = {
            "bull": factor_weights.bull,
            "bear": factor_weights.bear,
            "sideways": factor_weights.sideways,
        }
        weights = weights_map.get(regime_state, factor_weights.sideways)
    else:
        weights = {
            "technical": 0.30,
            "fundamental": 0.20,
            "capital": 0.15,
            "sentiment": 0.15,
            "momentum": 0.20,
        }

    results: list[FactorScores] = []

    for _, row in stock_pool.iterrows():
        code = str(row.get("code", ""))
        name = str(row.get("name", ""))
        industry = str(row.get("industry", "")) if "industry" in stock_pool.columns else ""

        kline = kline_cache.get(code, pd.DataFrame())
        fund = fundamental_cache.get(code, None)

        # 计算各因子（返回 dict，包含子因子详情和总分）
        tech_result = calc_technical_factor(kline)
        fund_result = calc_fundamental_factor(
            roe=fund.roe if fund else 0.0,
            eps=fund.eps if fund else 0.0,
            profit_growth=fund.profit_growth if fund else 0.0,
            pe_ttm=fund.pe_ttm if fund else 50.0,
            revenue_growth=fund.revenue_growth if fund else 0.0,
        )
        cap_result = calc_capital_factor(
            north_flow=north_flow,
            kline=kline,
            industry=industry,
            sector_flow=sector_flow,
        )
        sent_result = calc_sentiment_factor(
            limit_up=limit_up,
            limit_down=limit_down,
            advance_decline_ratio=ad_ratio,
            policy_impacts=policy_impacts,
            kline=kline,
            industry=industry,
        )
        mom_result = calc_momentum_factor(kline, benchmark_kline=index_kline)

        # 提取类别分数
        tech_score = tech_result.get("score", 50.0)
        fund_score = fund_result.get("score", 50.0)
        cap_score = cap_result.get("score", 50.0)
        sent_score = sent_result.get("score", 50.0)
        mom_score = mom_result.get("score", 50.0)

        # 加权合成
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
            # 存储子因子详情
            technical_detail={k: v for k, v in tech_result.items() if k != "score"},
            fundamental_detail={k: v for k, v in fund_result.items() if k != "score"},
            capital_detail={k: v for k, v in cap_result.items() if k != "score"},
            sentiment_detail={k: v for k, v in sent_result.items() if k != "score"},
            momentum_detail={k: v for k, v in mom_result.items() if k != "score"},
        ))

    # 百分位排名
    if results:
        results.sort(key=lambda x: x.total, reverse=True)
        n = len(results)
        for i, fs in enumerate(results):
            fs.rank_percentile = round((1 - i / n) * 100, 1)

    return results
