"""板块对比分析模块 — 计算个股在所属板块内的排名和对比。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from buy_sell_signal import SectorComparison
from scoring import clean_industry_name, find_etf_for_industry

logger = logging.getLogger("thousand-times")


@dataclass
class SectorStock:
    """板块内个股信息。"""
    code: str
    name: str
    industry: str
    total_score: float
    change_pct: float  # 涨跌幅


def calc_sector_rank(
    target_code: str,
    target_score: float,
    sector_stocks: list[SectorStock],
) -> tuple[int, int, float]:
    """计算个股在板块内的排名。

    Args:
        target_code: 目标股票代码。
        target_score: 目标股票综合评分。
        sector_stocks: 板块内所有股票列表。

    Returns:
        (排名, 总数, 百分位) 元组。
    """
    if not sector_stocks:
        return 1, 1, 100.0

    # 按评分排序（降序）
    sorted_stocks = sorted(sector_stocks, key=lambda x: x.total_score, reverse=True)

    # 找到目标股票的排名
    rank = 1
    for i, stock in enumerate(sorted_stocks):
        if stock.code == target_code:
            rank = i + 1
            break

    total = len(sorted_stocks)
    # 百分位 = 超过的股票比例
    percentile = round((total - rank) / total * 100, 1) if total > 1 else 100.0

    return rank, total, percentile


def calc_vs_etf_return(
    stock_change_pct: float,
    etf_change_pct: float | None,
) -> float | None:
    """计算相对板块ETF的超额收益。

    Args:
        stock_change_pct: 个股涨跌幅。
        etf_change_pct: 板块ETF涨跌幅。

    Returns:
        超额收益（百分点），无法计算返回 None。
    """
    if etf_change_pct is None:
        return None
    return round(stock_change_pct - etf_change_pct, 2)


def analyze_sector_comparison(
    target_code: str,
    target_name: str,
    target_industry: str,
    target_score: float,
    target_change_pct: float,
    sector_stocks: list[SectorStock],
    etf_pool: list[str],
    etf_kline_cache: dict[str, "pd.DataFrame"] | None = None,
) -> SectorComparison | None:
    """分析个股的板块对比。

    Args:
        target_code: 目标股票代码。
        target_name: 目标股票名称。
        target_industry: 目标股票所属行业。
        target_score: 目标股票综合评分。
        target_change_pct: 目标股票涨跌幅。
        sector_stocks: 板块内所有股票列表。
        etf_pool: 可用的ETF代码列表。
        etf_kline_cache: ETF K线数据缓存（可选）。

    Returns:
        SectorComparison 对象，无法分析返回 None。
    """
    if not target_industry:
        logger.warning(f"股票 {target_code} 无行业信息，跳过板块对比")
        return None

    # 计算板块内排名
    rank, total, percentile = calc_sector_rank(
        target_code, target_score, sector_stocks
    )

    # 查找板块ETF
    etf_code = find_etf_for_industry(target_industry, etf_pool)

    # 计算相对ETF的超额收益
    vs_etf_return: float | None = None
    if etf_code and etf_kline_cache and etf_code in etf_kline_cache:
        try:
            etf_df = etf_kline_cache[etf_code]
            if not etf_df.empty and len(etf_df) >= 2:
                # 计算ETF近5日涨跌幅
                etf_closes = etf_df["收盘"].astype(float).tolist()
                if len(etf_closes) >= 5:
                    etf_change = (etf_closes[-1] - etf_closes[-5]) / etf_closes[-5] * 100
                else:
                    etf_change = (etf_closes[-1] - etf_closes[0]) / etf_closes[0] * 100
                vs_etf_return = calc_vs_etf_return(target_change_pct, etf_change)
        except Exception as e:
            logger.warning(f"计算ETF {etf_code} 涨跌幅失败: {e}")

    clean_industry = clean_industry_name(target_industry)

    return SectorComparison(
        sector_name=clean_industry,
        rank_in_sector=rank,
        total_in_sector=total,
        percentile=percentile,
        vs_etf_return=vs_etf_return if vs_etf_return is not None else 0.0,
    )


def build_sector_stocks(
    stock_pool: "pd.DataFrame",
    scores: dict[str, float],
    changes: dict[str, float],
) -> dict[str, list[SectorStock]]:
    """构建按行业分组的股票列表。

    Args:
        stock_pool: 股票池 DataFrame（包含 code, name, industry 列）。
        scores: 股票代码→综合评分 映射。
        changes: 股票代码→涨跌幅 映射。

    Returns:
        行业名称→板块内股票列表 映射。
    """
    sector_map: dict[str, list[SectorStock]] = {}

    for _, row in stock_pool.iterrows():
        code = str(row.get("code", ""))
        name = str(row.get("name", ""))
        industry = str(row.get("industry", ""))
        score = scores.get(code, 0.0)
        change = changes.get(code, 0.0)

        if not industry:
            continue

        # 清理行业名称
        clean_ind = clean_industry_name(industry)

        if clean_ind not in sector_map:
            sector_map[clean_ind] = []

        sector_map[clean_ind].append(SectorStock(
            code=code,
            name=name,
            industry=industry,
            total_score=score,
            change_pct=change,
        ))

    return sector_map
