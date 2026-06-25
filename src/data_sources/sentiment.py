"""涨跌停统计数据源.

获取涨停、跌停家数及连板高度。
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def fetch_limit_stats(date: str) -> dict[str, int]:
    """获取涨跌停统计.

    Args:
        date: 交易日期，格式 YYYYMMDD。

    Returns:
        dict with keys:
            - limit_up_count: 涨停家数
            - limit_down_count: 跌停家数
            - max_consecutive: 最高连板天数
    """
    result: dict[str, int] = {"limit_up_count": 0, "limit_down_count": 0, "max_consecutive": 0}

    try:
        import akshare as ak  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("AKShare 不可用")
        return result

    # 获取涨停池
    try:
        zt = ak.stock_zt_pool_em(date=date)
        if zt is not None and not zt.empty:
            result["limit_up_count"] = len(zt)
            # 解析连板天数: "2天" -> 2, "5/5天" -> 5
            if "涨停统计" in zt.columns:
                try:
                    raw = zt["涨停统计"].astype(str).str.split("天").str[0]
                    # 处理 "5/5" 格式（取斜杠前的数字）
                    raw = raw.str.split("/").str[0]
                    # 转为数值，忽略无法解析的值
                    numeric = pd.to_numeric(raw, errors="coerce")
                    valid = numeric.dropna()
                    if not valid.empty:
                        result["max_consecutive"] = int(valid.max())
                except Exception as parse_e:
                    logger.debug(f"连板天数解析异常: {parse_e}")
    except Exception as e:
        logger.warning(f"获取涨停统计失败: {e}")

    # 获取跌停池
    try:
        dt = ak.stock_zt_pool_dtgc_em(date=date)
        if dt is not None and not dt.empty:
            result["limit_down_count"] = len(dt)
    except Exception as e:
        logger.warning(f"获取跌停统计失败: {e}")

    return result
