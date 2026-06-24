"""Data sources package - 外部数据源模块.

模块:
    capital_flow - 北向资金、融资融券
    sentiment - 涨跌停统计、市场情绪
    sector_flow - 行业资金流向、板块轮动
    macro - 宏观指标（CPI、PMI、M2）
"""

from __future__ import annotations

from src.data_sources.capital_flow import fetch_north_flow, fetch_north_flow_stock
from src.data_sources.sentiment import fetch_limit_stats
from src.data_sources.sector_flow import fetch_sector_flow, fetch_sector_flow_top_n, calc_sector_flow_score
from src.data_sources.macro import fetch_macro_indicators, calc_macro_score

__all__ = [
    "capital_flow",
    "sentiment",
    "sector_flow",
    "macro",
    "fetch_north_flow",
    "fetch_north_flow_stock",
    "fetch_limit_stats",
    "fetch_sector_flow",
    "fetch_sector_flow_top_n",
    "calc_sector_flow_score",
    "fetch_macro_indicators",
    "calc_macro_score",
]
