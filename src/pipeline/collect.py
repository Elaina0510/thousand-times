"""统一数据采集模块.

整合所有数据源，返回结构化的 DataBundle 供下游使用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class FundamentalData:
    """个股基本面数据（V2 管道使用）。"""

    roe: float = 0.0
    eps: float = 0.0
    profit_growth: float = 0.0
    revenue_growth: float = 0.0
    pe_ttm: float = 50.0
    pb: float = 1.0


@dataclass
class DataBundle:
    """统一数据包，包含所有分析所需数据。"""

    # 指数数据
    index_kline: pd.DataFrame = field(default_factory=pd.DataFrame)

    # 股票池
    stock_pool: pd.DataFrame = field(default_factory=pd.DataFrame)

    # 个股数据
    kline_cache: dict[str, pd.DataFrame] = field(default_factory=dict)
    fundamental_cache: dict[str, FundamentalData] = field(default_factory=dict)

    # 资金面
    north_flow: pd.DataFrame = field(default_factory=pd.DataFrame)
    margin_data: pd.DataFrame | None = None

    # 情绪面
    limit_up_count: int = 0
    limit_down_count: int = 0
    advance_decline_ratio: float = 1.0

    # 宏观面
    macro_indicators: dict[str, float] = field(default_factory=dict)

    # 行业数据
    sector_flow: pd.DataFrame = field(default_factory=pd.DataFrame)

    # 新闻
    news_items: list = field(default_factory=list)
    policy_impacts: list = field(default_factory=list)

    # ETF
    etf_pool: list = field(default_factory=list)
    etf_kline_cache: dict[str, pd.DataFrame] = field(default_factory=dict)


def fetch_index_kline(symbol: str, days: int = 120) -> pd.DataFrame:
    """获取指数日K线数据.

    Args:
        symbol: 指数代码，如 "sh000001" (上证指数)。
        days: 获取最近 N 天的数据。

    Returns:
        DataFrame with columns: date, open, high, low, close, volume。
        API 失败时返回空 DataFrame。
    """
    try:
        from src.baostock_data import get_index_hist_baostock

        # 将 sh000001 格式转为 000001
        code = symbol.replace("sh", "").replace("sz", "")
        df = get_index_hist_baostock(code, days=days)
        if df is None or df.empty:
            logger.warning(f"指数 {symbol} K线数据为空")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"获取指数 {symbol} K线失败: {e}")
        return pd.DataFrame()


def stage_collect(config: object, regime: object | None = None) -> DataBundle:
    """阶段2: 统一数据采集.

    Args:
        config: 应用配置 (AppConfig)。
        regime: 市场环境判断结果（可选）。

    Returns:
        DataBundle: 包含所有分析所需数据。
    """
    logger.info("=== 阶段2: 数据采集 ===")

    # 1. 获取指数K线（中证全指）
    index_kline = fetch_index_kline("sh000985", days=120)

    # 2. 获取股票池
    stock_pool = _fetch_stock_pool(config)

    # 3. 批量获取个股K线
    codes = [str(c) for c in stock_pool["code"].tolist()] if not stock_pool.empty else []
    kline_cache = _batch_fetch_klines(codes, days=120)

    # 4. 获取基本面数据
    fundamental_cache = _fetch_fundamentals_batch(codes)

    # 5. 获取北向资金
    from src.data_sources.capital_flow import fetch_north_flow
    north_flow = fetch_north_flow(days=20)

    # 6. 获取涨跌停统计
    from src.data_sources.sentiment import fetch_limit_stats
    import datetime
    today = datetime.datetime.now().strftime("%Y%m%d")
    limit_stats = fetch_limit_stats(today)

    limit_up = limit_stats.get("limit_up_count", 0)
    limit_down = limit_stats.get("limit_down_count", 0)
    advance_decline_ratio = limit_up / max(limit_down, 1)

    # 7. ETF数据
    etf_pool, etf_kline_cache = _fetch_etf_data(config)

    # 8. 获取新闻和政策分析
    news_items, policy_impacts = _fetch_news_data(config)

    # 9. 获取行业资金流向
    sector_flow = _fetch_sector_flow()

    # 10. 获取宏观指标
    macro_indicators = _fetch_macro_indicators()

    return DataBundle(
        index_kline=index_kline,
        stock_pool=stock_pool,
        kline_cache=kline_cache,
        fundamental_cache=fundamental_cache,
        north_flow=north_flow,
        margin_data=None,
        limit_up_count=limit_up,
        limit_down_count=limit_down,
        advance_decline_ratio=advance_decline_ratio,
        macro_indicators=macro_indicators,
        sector_flow=sector_flow,
        news_items=news_items,
        policy_impacts=policy_impacts,
        etf_pool=etf_pool,
        etf_kline_cache=etf_kline_cache,
    )


def _fetch_stock_pool(config: object) -> pd.DataFrame:
    """获取股票池，复用现有 stock_filter 模块。"""
    try:
        from src.stock_filter import get_stock_pool
        from src.config import FilterConfig
        if hasattr(config, "filter"):
            return get_stock_pool(config.filter)
        return get_stock_pool(FilterConfig())
    except Exception as e:
        logger.error(f"获取股票池失败: {e}")
        return pd.DataFrame(columns=["code", "name"])


def _batch_fetch_klines(codes: list[str], days: int = 120) -> dict[str, pd.DataFrame]:
    """批量获取个股K线数据。"""
    if not codes:
        return {}
    try:
        from src.baostock_data import get_stock_hist_batch_baostock
        return get_stock_hist_batch_baostock(codes, days=days)
    except Exception as e:
        logger.error(f"批量获取K线失败: {e}")
        return {}


def _fetch_fundamentals_batch(codes: list[str]) -> dict[str, FundamentalData]:
    """批量获取基本面数据。"""
    if not codes:
        return {}
    try:
        from src.fundamental_analysis import get_fundamental_data_batch, FundamentalData as FundData

        raw = get_fundamental_data_batch(codes)
        result: dict[str, FundamentalData] = {}
        for code, fd in raw.items():
            if isinstance(fd, FundData):
                result[code] = FundamentalData(
                    roe=fd.roe,
                    eps=fd.eps,
                    profit_growth=fd.profit_growth or 0.0,
                    revenue_growth=fd.revenue_growth or 0.0,
                    pe_ttm=50.0,
                    pb=1.0,
                )
            else:
                result[code] = FundamentalData()
        return result
    except Exception as e:
        logger.error(f"获取基本面数据失败: {e}")
        return {}


def _fetch_etf_data(config: object) -> tuple[list, dict[str, pd.DataFrame]]:
    """获取 ETF 数据，复用现有 etf_analyzer 模块。"""
    try:
        from src.etf_analyzer import get_etf_pool
        return get_etf_pool(config)
    except Exception as e:
        logger.error(f"获取 ETF 数据失败: {e}")
        return [], {}


def _fetch_news_data(config: object) -> tuple[list, list]:
    """获取新闻和政策分析数据。"""
    try:
        from src.news_analysis import fetch_news, filter_by_credibility, analyze_policy_impact
        raw = fetch_news()
        news_items = filter_by_credibility(raw)

        llm_config = {
            "api_url": getattr(config, "llm_api_url", ""),
            "api_key": getattr(config, "llm_api_key", ""),
        }
        policy_impacts = analyze_policy_impact(news_items, llm_config) if news_items else []
        return news_items, policy_impacts
    except Exception as e:
        logger.warning(f"获取新闻数据失败，使用空列表: {e}")
        return [], []


def _fetch_sector_flow() -> pd.DataFrame:
    """获取行业资金流向数据。"""
    try:
        from src.data_sources.sector_flow import fetch_sector_flow
        return fetch_sector_flow(indicator="今日")
    except Exception as e:
        logger.warning(f"获取行业资金流向失败: {e}")
        return pd.DataFrame()


def _fetch_macro_indicators() -> dict[str, float]:
    """获取宏观经济指标。"""
    try:
        from src.data_sources.macro import fetch_macro_indicators
        raw = fetch_macro_indicators()
        # 过滤掉 None 值，只保留有效数据
        return {k: v for k, v in raw.items() if v is not None}
    except Exception as e:
        logger.warning(f"获取宏观指标失败: {e}")
        return {}
