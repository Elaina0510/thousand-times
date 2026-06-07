"""远程数据源模块 — 通过国内 VPS API 获取数据。"""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd
import requests  # type: ignore[import-untyped]

logger = logging.getLogger("thousand-times")

# 远程 API 地址（从环境变量读取）
REMOTE_API_URL = os.environ.get("STOCK_API_URL", "")


def is_remote_available() -> bool:
    """检查远程 API 是否可用。"""
    return bool(REMOTE_API_URL)


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """调用远程 API。"""
    if not REMOTE_API_URL:
        raise RuntimeError("STOCK_API_URL 未配置")

    url = f"{REMOTE_API_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_stock_spot_remote() -> pd.DataFrame:
    """从远程 API 获取全市场实时行情。"""
    result = _get("/api/stock/spot")
    return pd.DataFrame(result["data"])


def get_stock_hist_remote(symbol: str, days: int = 60) -> pd.DataFrame:
    """从远程 API 获取个股历史行情。"""
    result = _get(f"/api/stock/{symbol}", {"days": days})
    return pd.DataFrame(result["data"])


def get_etf_hist_remote(symbol: str, days: int = 60) -> pd.DataFrame:
    """从远程 API 获取 ETF 历史行情。"""
    result = _get(f"/api/etf/{symbol}", {"days": days})
    return pd.DataFrame(result["data"])


def get_news_remote() -> pd.DataFrame:
    """从远程 API 获取财经新闻。"""
    result = _get("/api/news")
    return pd.DataFrame(result["data"])
