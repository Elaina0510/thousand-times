"""基本面分析模块 — 获取并评估基本面数据。"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

import pandas as pd

from config import FundamentalWeightConfig
from utils import random_delay

logger = logging.getLogger("thousand-times")

# 全局标志：AKShare 是否可用
_akshare_available = True


@dataclass
class FundamentalData:
    """基本面数据。"""

    pe_ttm: float  # 滚动市盈率
    pb: float  # 市净率
    market_cap: float  # 总市值（元）
    profit_growth: float | None  # 净利润同比增长率（%）
    revenue_growth: float | None  # 营收同比增长率（%）


def _fetch_financial_indicator(code: str) -> pd.DataFrame:
    """获取个股财务指标。

    Args:
        code: 股票代码。

    Returns:
        包含财务指标的 DataFrame。
    """
    global _akshare_available

    if not _akshare_available:
        return pd.DataFrame()

    try:
        import akshare as ak  # type: ignore[import-untyped]
        logger.info(f"使用 AKShare 获取 {code} 财务指标")
        result: pd.DataFrame = ak.stock_financial_analysis_indicator(symbol=code)
        return result
    except Exception as e:
        logger.warning(f"AKShare 获取 {code} 财务指标失败: {e}")
        # 如果是网络错误，标记 AKShare 不可用
        if "ProxyError" in str(e) or "Connection" in str(e) or "RemoteDisconnected" in str(e):
            logger.warning("检测到网络问题，后续将跳过 AKShare 财务数据获取")
            _akshare_available = False
        return pd.DataFrame()


def get_fundamental_data(code: str) -> FundamentalData:
    """获取个股基本面数据。

    Args:
        code: 股票代码。

    Returns:
        FundamentalData 对象。
    """
    try:
        df = _fetch_financial_indicator(code)

        if df.empty:
            logger.debug(f"股票 {code} 财务数据为空")
            return FundamentalData(
                pe_ttm=0.0,
                pb=0.0,
                market_cap=0.0,
                profit_growth=None,
                revenue_growth=None,
            )

        # 获取最新一行数据
        latest = df.iloc[0]

        # 提取数据（列名可能是中文）
        pe_ttm = 0.0
        pb = 0.0
        profit_growth = None
        revenue_growth = None

        # 尝试不同的列名
        for col_name in ["摊薄每股收益", "每股收益"]:
            if col_name in df.columns:
                with contextlib.suppress(ValueError, TypeError):
                    pe_ttm = float(latest[col_name]) if pd.notna(latest[col_name]) else 0.0
                break

        for col_name in ["净资产收益率", "加权净资产收益率"]:
            if col_name in df.columns:
                with contextlib.suppress(ValueError, TypeError):
                    pb = float(latest[col_name]) if pd.notna(latest[col_name]) else 0.0
                break

        # 净利润同比增长率
        for col_name in ["净利润同比增长率", "归属净利润同比", "净利润同比"]:
            if col_name in df.columns:
                with contextlib.suppress(ValueError, TypeError):
                    val = latest[col_name]
                    if pd.notna(val):
                        profit_growth = float(val)
                break

        # 营收同比增长率
        for col_name in ["营收同比增长率", "营业收入同比", "营收同比"]:
            if col_name in df.columns:
                with contextlib.suppress(ValueError, TypeError):
                    val = latest[col_name]
                    if pd.notna(val):
                        revenue_growth = float(val)
                break

        return FundamentalData(
            pe_ttm=pe_ttm,
            pb=pb,
            market_cap=0.0,  # 市值从 stock_filter 获取
            profit_growth=profit_growth,
            revenue_growth=revenue_growth,
        )

    except Exception as e:
        logger.warning(f"获取股票 {code} 基本面数据失败: {e}")

        return FundamentalData(
            pe_ttm=0.0,
            pb=0.0,
            market_cap=0.0,
            profit_growth=None,
            revenue_growth=None,
        )


def calc_fundamental_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float:
    """计算基本面评分。

    评分规则：
    - PE-TTM: 10 < PE < 30 → +8, 30 ≤ PE < 60 → +3, PE ≥ 60 → 0
    - PB: 1 < PB < 5 → +5
    - 净利润同比: >20% → +10, 0~20% → +5, <0% → 0
    - 营收同比: >15% → +7, 0~15% → +3, <0% → 0

    Args:
        data: 基本面数据。
        weights: 基本面权重配置。

    Returns:
        评分（0~30分）。
    """
    score = 0.0

    # PE 评分
    if 10 < data.pe_ttm < 30:
        score += weights.pe_low
    elif 30 <= data.pe_ttm < 60:
        score += weights.pe_mid
    # PE >= 60 或 PE <= 10: 0分

    # PB 评分
    if 1 < data.pb < 5:
        score += weights.pb_ok

    # 净利润同比增长率评分
    if data.profit_growth is not None:
        if data.profit_growth > 20:
            score += weights.profit_high_growth
        elif data.profit_growth > 0:
            score += weights.profit_stable_growth
        # 净利润下降: 0分

    # 营收同比增长率评分
    if data.revenue_growth is not None:
        if data.revenue_growth > 15:
            score += weights.revenue_high_growth
        elif data.revenue_growth > 0:
            score += weights.revenue_stable_growth
        # 营收下降: 0分

    return score
