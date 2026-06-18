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
    try:
        from baostock_data import get_etf_hist_baostock
        logger.info(f"使用 BaoStock 获取 ETF {code} 历史数据")
        df = get_etf_hist_baostock(code, days=60)
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"BaoStock 获取 ETF {code} 失败: {e}")

    return pd.DataFrame()


def _fetch_etf_fund_daily(code: str, timeout: int = 30) -> pd.DataFrame:
    """获取ETF份额数据（带超时保护）。

    AKShare fund_etf_fund_daily_em() 现在无参数，返回全量数据。
    需要按代码筛选后使用。

    Args:
        code: ETF代码。
        timeout: 超时时间（秒），默认30秒。

    Returns:
        包含份额数据的 DataFrame。
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    def _fetch_akshare() -> pd.DataFrame:
        import akshare as ak  # type: ignore[import-untyped]
        # fund_etf_fund_daily_em() 无参数，返回所有ETF数据
        all_etfs = ak.fund_etf_fund_daily_em()
        # 按代码筛选
        if all_etfs.empty:
            return all_etfs
        code_col = all_etfs.columns[0]  # 第一列是基金代码
        return all_etfs[all_etfs[code_col].astype(str) == code]

    # 使用超时保护获取AKShare数据
    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info(f"使用 AKShare 获取 ETF {code} 份额数据")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_akshare)
            result: pd.DataFrame = future.result(timeout=timeout)
            return result
    except FuturesTimeoutError:
        logger.warning(f"AKShare 获取 ETF {code} 份额数据超时 ({timeout}秒)")
    except Exception as e:
        logger.warning(f"AKShare 获取 ETF {code} 份额数据失败: {e}")

    # 回退到BaoStock获取成交量数据作为代理
    try:
        from baostock_data import get_etf_hist_baostock
        logger.info(f"使用 BaoStock 获取 ETF {code} 成交量数据作为代理")
        df = get_etf_hist_baostock(code, days=60)
        if not df.empty:
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


def get_etf_pool(config: AppConfig) -> tuple[list[EtfInfo], dict[str, pd.DataFrame]]:
    """获取ETF池中各ETF的当前行情，同时返回K线数据缓存。

    使用 BaoStock 单会话批量获取，避免并行 login/logout 冲突。

    Args:
        config: 应用配置。

    Returns:
        (ETF信息列表, ETF K线数据缓存 {code: DataFrame})
    """
    etf_list: list[EtfInfo] = []
    kline_cache: dict[str, pd.DataFrame] = {}

    # 批量获取所有ETF的K线数据（单会话，避免并发冲突）
    try:
        from baostock_data import get_etf_hist_batch_baostock
        logger.info(f"批量获取 {len(config.etf_pool)} 只ETF的K线数据...")
        kline_cache = get_etf_hist_batch_baostock(config.etf_pool, days=60)
    except Exception as e:
        logger.warning(f"批量获取ETF失败，回退到逐只获取: {e}")
        for code in config.etf_pool:
            try:
                kline_cache[code] = _fetch_etf_hist(code)
            except Exception:
                kline_cache[code] = pd.DataFrame()

    # 构建 ETF 信息列表
    for code in config.etf_pool:
        df = kline_cache.get(code, pd.DataFrame())
        if df.empty:
            logger.warning(f"ETF {code} 数据为空")
            continue

        # 重命名列（支持 BaoStock 格式）
        column_mapping = {
            "名称": "name", "最新价": "close", "涨跌幅": "change_pct",
            "收盘": "close", "日期": "date",
        }
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df_renamed = df.rename(columns=existing_columns)

        latest = df_renamed.iloc[-1]
        name = ETF_NAME_MAP.get(code, str(latest.get("name", f"ETF_{code}")))
        current_price = float(latest.get("close", 0.0))
        change_pct = float(latest.get("change_pct", 0.0))

        etf_list.append(EtfInfo(
            code=code, name=name,
            current_price=current_price, change_pct=change_pct,
        ))

    logger.info(f"ETF池获取完成，共 {len(etf_list)} 只ETF")
    return etf_list, kline_cache


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
            "涨跌额": "share_change",  # AKShare 新格式
            "日增长": "share_change",
        }
        existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=existing_columns)

        # 获取份额变化列
        if "share_change" not in df.columns:
            # 尝试用数值列的最后一列作为份额变化代理
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if not numeric_cols:
                # AKShare 可能返回文本列，尝试强制转换
                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='raise')
                    except (ValueError, TypeError):
                        continue
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                logger.info(f"ETF {code} 使用数值列 '{numeric_cols[-1]}' 作为份额变化代理")
                df["share_change"] = df[numeric_cols[-1]]
            else:
                logger.warning(f"ETF {code} 份额数据无可用数值列，使用默认持平评分")
                return 3.0

        # 取最近 days 天的数据
        share_changes = df["share_change"].tail(days).astype(float).tolist()

        return calc_fund_flow_score(share_changes)

    except Exception as e:
        logger.warning(f"获取ETF {code} 资金流向数据失败: {e}")
        return 3.0
