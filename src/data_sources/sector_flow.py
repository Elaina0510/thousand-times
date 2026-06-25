"""行业资金流向数据源.

获取行业板块资金净流入排名，用于行业轮动分析和资金面因子。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import pandas as pd

logger = logging.getLogger("thousand-times")

# API 超时时间（秒）
_API_TIMEOUT = 15


def fetch_sector_flow(indicator: str = "今日") -> pd.DataFrame:
    """获取行业板块资金流向排名.

    Args:
        indicator: 时间维度，可选 "今日"、"5日"、"10日"。

    Returns:
        DataFrame with columns:
            - 名称: 行业名称
            - 主力净流入-净额: 主力净流入金额
            - 主力净流入-净占比: 主力净流入占比
            - 主力净流入最大股: 该行业主力净流入最大的个股
        API 失败时返回空 DataFrame。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("AKShare 不可用，无法获取行业资金流向")
        return pd.DataFrame()

    try:
        # 使用线程池添加超时保护，防止 AKShare 请求卡死
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ak.stock_sector_fund_flow_rank, indicator=indicator, sector_type="行业资金流")
            df = future.result(timeout=_API_TIMEOUT)

        if df is None or df.empty:
            logger.warning("行业资金流向数据为空")
            return pd.DataFrame()

        # 过滤掉列名为 "-" 的无用列
        df = df.loc[:, df.columns != "-"]

        logger.info(f"获取行业资金流向成功: {len(df)} 个行业")
        return df.reset_index(drop=True)
    except FuturesTimeout:
        logger.warning(f"获取行业资金流向超时 ({_API_TIMEOUT}s)")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"获取行业资金流向失败: {e}")
        return pd.DataFrame()


def fetch_sector_flow_top_n(n: int = 5, indicator: str = "今日") -> list[dict[str, object]]:
    """获取资金净流入前 N 的行业.

    Args:
        n: 返回前 N 个行业。
        indicator: 时间维度。

    Returns:
        list of dict, 每个 dict 包含:
            - name: 行业名称
            - net_flow: 主力净流入金额
            - net_ratio: 主力净流入占比
            - top_stock: 主力净流入最大股
    """
    df = fetch_sector_flow(indicator)
    if df.empty:
        return []

    # 查找净流入列
    net_col = None
    for col in df.columns:
        if "净流入" in str(col) and "净额" in str(col):
            net_col = col
            break

    if net_col is None:
        logger.warning(f"行业资金流向数据中未找到净流入列: {df.columns.tolist()}")
        return []

    # 按净流入降序排列
    df_sorted = df.sort_values(net_col, ascending=False).head(n)

    results = []
    for _, row in df_sorted.iterrows():
        name_col = "名称" if "名称" in df.columns else df.columns[0]
        ratio_col = None
        stock_col = None
        for col in df.columns:
            if "净占比" in str(col):
                ratio_col = col
            if "最大股" in str(col):
                stock_col = col

        results.append({
            "name": str(row.get(name_col, "")),
            "net_flow": float(row.get(net_col, 0)) if pd.notna(row.get(net_col)) else 0.0,
            "net_ratio": float(row.get(ratio_col, 0)) if ratio_col and pd.notna(row.get(ratio_col)) else 0.0,
            "top_stock": str(row.get(stock_col, "")) if stock_col else "",
        })

    return results


def calc_sector_flow_score(north_flow: pd.DataFrame, sector_flow: pd.DataFrame) -> float:
    """基于行业资金流向计算评分.

    Args:
        north_flow: 北向资金数据（可选，用于辅助判断）。
        sector_flow: 行业资金流向数据。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    if sector_flow.empty:
        return 50.0

    try:
        # 查找净流入列
        net_col = None
        for col in sector_flow.columns:
            if "净流入" in str(col) and "净额" in str(col):
                net_col = col
                break

        if net_col is None:
            return 50.0

        flows = sector_flow[net_col].astype(float)

        # 统计净流入为正的行业占比
        positive_count = (flows > 0).sum()
        total_count = len(flows)
        positive_ratio = positive_count / total_count if total_count > 0 else 0.5

        # 映射到 0-100
        score = 50 + (positive_ratio - 0.5) * 60

        return round(min(max(score, 0), 100), 2)
    except Exception as e:
        logger.warning(f"行业资金流向评分计算异常: {e}")
        return 50.0
