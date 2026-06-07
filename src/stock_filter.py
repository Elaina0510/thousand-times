"""股票池筛选模块 — 从A股全市场中筛选符合条件的股票。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import akshare as ak  # type: ignore[import-untyped]
import pandas as pd

from config import FilterConfig
from utils import random_delay, retry

logger = logging.getLogger("thousand-times")


@retry(max_attempts=3, backoff_factor=2.0)
def _fetch_stock_spot() -> pd.DataFrame:
    """获取全市场股票实时行情（带重试）。

    Returns:
        包含股票实时行情的 DataFrame。
    """
    # 优先使用远程 API
    try:
        from remote_data import is_remote_available, get_stock_spot_remote
        if is_remote_available():
            logger.info("使用远程 API 获取股票数据")
            return get_stock_spot_remote()
    except Exception as e:
        logger.warning(f"远程 API 调用失败，回退到 AKShare: {e}")

    # 回退到 AKShare
    result: pd.DataFrame = ak.stock_zh_a_spot_em()
    return result


@retry(max_attempts=3, backoff_factor=2.0)
def _fetch_stock_info() -> pd.DataFrame:
    """获取股票基本信息（含上市日期）（带重试）。

    Returns:
        包含股票基本信息的 DataFrame。
    """
    result: pd.DataFrame = ak.stock_info_a_code_name()
    return result


def get_stock_pool(config: FilterConfig) -> pd.DataFrame:
    """获取筛选后的股票池。

    筛选流程：
    1. 获取全市场股票实时行情
    2. 过滤：市值 >= 20亿
    3. 过滤：名称不含 "ST"
    4. 过滤：PE-TTM > 0
    5. 过滤：上市 >= 3个月
    6. 按市值降序排序
    7. 取前 pool_size 条

    Args:
        config: 股票池筛选配置。

    Returns:
        DataFrame，包含列：code, name, market_cap, pe_ttm, pb, listing_date, industry
        按 market_cap 降序，取前 config.pool_size 条。

    Raises:
        RuntimeError: AKShare 接口多次重试后仍失败。
    """
    logger.info("开始获取股票池...")

    # 获取全市场实时行情
    df = _fetch_stock_spot()
    random_delay()

    # 重命名列（AKShare 返回的列名可能是中文）
    column_mapping = {
        "代码": "code",
        "名称": "name",
        "总市值": "market_cap",
        "市盈率-动态": "pe_ttm",
        "市净率": "pb",
        "最新价": "close",
        "涨跌幅": "change_pct",
    }

    # 只保留存在的列
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)

    # 确保必要的列存在
    required_columns = ["code", "name", "market_cap", "pe_ttm"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"AKShare 返回数据缺少必要列: {col}")

    # 过滤：市值 >= 20亿
    df = df[df["market_cap"] >= config.min_market_cap]

    # 过滤：名称不含 "ST"
    df = df[~df["name"].str.contains("ST", case=False, na=False)]

    # 过滤：PE-TTM > 0
    df = df[df["pe_ttm"] > 0]

    # 获取上市日期信息
    try:
        stock_info = _fetch_stock_info()
        random_delay()

        # 重命名列
        if "上市日期" in stock_info.columns:
            stock_info = stock_info.rename(columns={"代码": "code", "上市日期": "listing_date"})
            # 合并上市日期
            df = df.merge(stock_info[["code", "listing_date"]], on="code", how="left")

            # 过滤：上市 >= 3个月
            cutoff_date = datetime.now() - timedelta(days=config.min_listing_months * 30)
            if "listing_date" in df.columns:
                df["listing_date"] = pd.to_datetime(df["listing_date"], errors="coerce")
                df = df[df["listing_date"].isna() | (df["listing_date"] <= cutoff_date)]
    except Exception as e:
        logger.warning(f"获取上市日期信息失败，跳过上市时间过滤: {e}")

    # 按市值降序排序
    df = df.sort_values("market_cap", ascending=False)

    # 取前 pool_size 条
    df = df.head(config.pool_size)

    # 确保返回的列存在
    result_columns = ["code", "name", "market_cap", "pe_ttm"]
    if "pb" in df.columns:
        result_columns.append("pb")
    if "listing_date" in df.columns:
        result_columns.append("listing_date")
    if "industry" in df.columns:
        result_columns.append("industry")

    # 只保留存在的列
    result_columns = [col for col in result_columns if col in df.columns]
    result_df: pd.DataFrame = df[result_columns].reset_index(drop=True)

    logger.info(f"股票池筛选完成，共 {len(result_df)} 只股票")
    return result_df
