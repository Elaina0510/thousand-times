"""Data sources package - 外部数据源模块.

模块:
    capital_flow - 北向资金、融资融券
    sentiment - 涨跌停统计、市场情绪
    sector_flow - 行业资金流向（P1）
    macro - 宏观指标（P2）
"""

from __future__ import annotations

from src.data_sources.capital_flow import fetch_north_flow, fetch_north_flow_stock
from src.data_sources.sentiment import fetch_limit_stats

__all__ = [
    "capital_flow",
    "sentiment",
    "fetch_north_flow",
    "fetch_north_flow_stock",
    "fetch_limit_stats",
]
