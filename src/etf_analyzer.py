"""ETF分析模块 — 获取ETF池并分析资金流向。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from config import AppConfig
from utils import random_delay

logger = logging.getLogger("thousand-times")


@dataclass
class EtfInfo:
    """ETF基本信息。"""

    code: str
    name: str
    current_price: float
    change_pct: float


def _fetch_etf_hist(code: str) -> pd.DataFrame:
    """获取ETF历史行情。

    Args:
        code: ETF代码。

    Returns:
        包含历史行情的 DataFrame。
    """
    # 优先使用 BaoStock（更稳定）
    try:
        from baostock_data import get_etf_hist_baostock
        logger.info(f"使用 BaoStock 获取 ETF {code} 历史数据")
        df = get_etf_hist_baostock(code, days=60)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"BaoStock 获取 ETF {code} 失败: {e}")

    # 回退到 AKShare
    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info(f"使用 AKShare 获取 ETF {code} 历史数据")
        result: pd.DataFrame = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            adjust="qfq",
        )
        return result
    except Exception as e:
        logger.warning(f"AKShare 获取 ETF {code} 失败: {e}")
        return pd.DataFrame()


def _fetch_etf_fund_daily(code: str) -> pd.DataFrame:
    """获取ETF份额数据。

    Args:
        code: ETF代码。

    Returns:
        包含份额数据的 DataFrame。
    """
    # BaoStock 不提供份额数据，直接使用 AKShare
    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info(f"使用 AKShare 获取 ETF {code} 份额数据")
        result: pd.DataFrame = ak.fund_etf_fund_daily_em(symbol=code)
        return result
    except Exception as e:
        logger.warning(f"AKShare 获取 ETF {code} 份额数据失败: {e}")

        # 尝试使用 BaoStock 获取历史数据（成交量作为代理）
        try:
            from baostock_data import get_etf_hist_baostock
            logger.info(f"使用 BaoStock 获取 ETF {code} 成交量数据作为代理")
            df = get_etf_hist_baostock(code, days=60)
            if not df.empty:
                # BaoStock 不提供份额数据，但我们可以使用成交量作为代理
                df = df.rename(columns={
                    '日期': 'date',
                    '成交量': 'share_change',
                })
                return df
        except Exception as e2:
            logger.warning(f"BaoStock 获取 ETF {code} 成交量数据失败: {e2}")

        return pd.DataFrame()


# ETF 名称映射表
ETF_NAME_MAP: dict[str, str] = {
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "159915": "创业板ETF",
    "588000": "科创50ETF",
    "512480": "半导体ETF",
    "516160": "新能源ETF",
    "512010": "医药ETF",
    "159928": "消费ETF",
    "512660": "军工ETF",
    "510230": "金融ETF",
    "512200": "地产ETF",
}


def get_etf_pool(config: AppConfig) -> list[EtfInfo]:
    """获取ETF池中各ETF的当前行情。

    Args:
        config: 应用配置。

    Returns:
        ETF信息列表。
    """
    etf_list: list[EtfInfo] = []

    for code in config.etf_pool:
        try:
            df = _fetch_etf_hist(code)

            if df.empty:
                logger.warning(f"ETF {code} 数据为空")
                continue

            # 重命名列（支持 AKShare 和 BaoStock 两种格式）
            column_mapping = {
                "名称": "name",
                "最新价": "close",
                "涨跌幅": "change_pct",
                # BaoStock 格式
                "收盘": "close",
                "日期": "date",
            }
            existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=existing_columns)

            # 获取最新数据
            latest = df.iloc[-1]

            # 优先使用映射表中的名称
            name = ETF_NAME_MAP.get(code, str(latest.get("name", f"ETF_{code}")))
            current_price = float(latest.get("close", 0.0))
            change_pct = float(latest.get("change_pct", 0.0))

            etf_list.append(
                EtfInfo(
                    code=code,
                    name=name,
                    current_price=current_price,
                    change_pct=change_pct,
                )
            )

        except Exception as e:
            logger.warning(f"获取ETF {code} 数据失败: {e}")
            continue

    logger.info(f"ETF池获取完成，共 {len(etf_list)} 只ETF")
    return etf_list


def calc_fund_flow_score(share_changes: list[float]) -> float:
    """根据近N日份额变化计算评分。

    评分规则：
    - 连续N日份额增长：8~10分
    - 总体增长但有波动：4~7分
    - 基本持平：3分
    - 连续N日份额减少：0~2分

    Args:
        share_changes: 每日份额变化量列表（正数=增长，负数=减少）。

    Returns:
        评分（0~10）。
    """
    if not share_changes:
        return 3.0  # 默认持平

    n = len(share_changes)

    # 统计增长和减少的天数
    growth_days = sum(1 for x in share_changes if x > 0)
    decline_days = sum(1 for x in share_changes if x < 0)
    total_change = sum(share_changes)

    # 连续增长
    if all(x > 0 for x in share_changes):
        if n >= 5:
            return 10.0
        return 8.0 + (n / 5) * 2.0

    # 连续减少
    if all(x < 0 for x in share_changes):
        if n >= 5:
            return 0.0
        return 2.0 - (n / 5) * 2.0

    # 总体增长但有波动
    if total_change > 0:
        ratio = growth_days / n
        return 4.0 + ratio * 3.0

    # 总体减少但有波动
    if total_change < 0:
        ratio = decline_days / n
        return 2.0 - ratio * 2.0

    # 基本持平
    return 3.0


def get_etf_fund_flow(code: str, days: int = 5) -> float:
    """获取ETF资金流向评分。

    Args:
        code: ETF代码。
        days: 回溯天数。

    Returns:
        资金流向评分（0~10分）。
    """
    try:
        df = _fetch_etf_fund_daily(code)
        random_delay(0.2, 1.0)

        if df.empty:
            logger.warning(f"ETF {code} 份额数据为空")
            return 3.0

        # 重命名列
        column_mapping = {
            "份额变化": "share_change",
            "日份额变化": "share_change",
        }
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_columns)

        # 获取份额变化列
        if "share_change" not in df.columns:
            logger.warning(f"ETF {code} 份额数据缺少份额变化列")
            return 3.0

        # 取最近 days 天的数据
        share_changes = df["share_change"].tail(days).astype(float).tolist()

        return calc_fund_flow_score(share_changes)

    except Exception as e:
        logger.warning(f"获取ETF {code} 资金流向数据失败: {e}")
        return 3.0
