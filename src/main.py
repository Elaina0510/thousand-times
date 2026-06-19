"""主程序模块 — 编排整个分析流水线。"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

import pandas as pd

from concurrent.futures import ThreadPoolExecutor, as_completed

from buy_sell_signal import BuySellSignal, generate_buy_sell_signal
from cache_manager import (
    FUND_CACHE_TTL,
    get_cached_data,
    set_cached_data,
    load_cached_dataframe,
    clear_expired_cache,
    load_previous_kline_cache,
    needs_kline_update,
    save_kline_cache_with_meta,
    load_kline_cache_with_meta,
    log_cache_stats,
)
from chart_generator import generate_chart
from config import AppConfig, ScoreWeightConfig, load_config
from etf_analyzer import EtfInfo, get_etf_fund_flow, get_etf_pool
from fundamental_analysis import calc_fundamental_score, get_fundamental_data, get_fundamental_data_batch
from news_analysis import PolicyImpact, analyze_policy_impact, fetch_news, filter_by_credibility
from push_service import push_to_wechat
from report_generator import generate_report
from scoring import ScoreResult, calc_technical_score, calc_total_score, judge_score, score_to_probability
from sector_analysis import SectorStock, analyze_sector_comparison, build_sector_stocks
from stock_filter import get_stock_pool
from technical_analysis import calc_technical_signals, get_kline_data, get_kline_data_from_cache

# 确保日志目录存在
os.makedirs("logs", exist_ok=True)
os.makedirs("charts", exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/analysis.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("thousand-times")


def parallel_batch_fetch(
    codes: list[str],
    fetch_func,
    workers: int = 4,
    **kwargs,
) -> dict:
    """将股票代码分组，并行获取数据。

    每个分组在独立线程中调用 fetch_func，各自创建独立的 BaoStock session。
    使用列表切片确保不丢失尾部元素。

    Args:
        codes: 股票/ETF 代码列表。
        fetch_func: 批量获取函数，签名为 fetch_func(codes, **kwargs) -> dict。
        workers: 并行线程数。
        **kwargs: 传递给 fetch_func 的额外参数。

    Returns:
        合并后的结果字典。
    """
    if not codes:
        return {}

    chunk_size = max(1, (len(codes) + workers - 1) // workers)  # 向上取整
    chunks = [codes[i:i + chunk_size] for i in range(0, len(codes), chunk_size)]

    results: dict = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_func, chunk, **kwargs): i for i, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            try:
                results.update(future.result())
            except Exception as e:
                logger.warning(f"批量获取部分失败 (chunk {futures[future]}): {e}")

    return results


def analyze_single_stock(
    stock: pd.Series,
    policy_impacts: list[PolicyImpact],
    config: AppConfig,
    kline_cache: dict[str, pd.DataFrame] | None = None,
    fund_cache: dict[str, any] | None = None,
    score_weight: ScoreWeightConfig | None = None,
) -> ScoreResult:
    """分析单只股票。

    Args:
        stock: 股票数据（包含 code, name, market_cap, pe_ttm, pb, industry 等）。
        policy_impacts: 政策影响分析结果。
        config: 应用配置。
        kline_cache: 预获取的K线数据缓存。
        fund_cache: 预获取的基本面数据缓存。
        score_weight: 评分权重（可选，用于市场环境动态调整）。

    Returns:
        评分结果。
    """
    code = str(stock["code"])
    name = str(stock["name"])
    industry = str(stock.get("industry", ""))

    # 获取K线数据（优先使用缓存）
    if kline_cache is not None and code in kline_cache:
        kline = get_kline_data_from_cache(kline_cache[code], code)
    else:
        kline = get_kline_data(code, config.lookback_days, is_etf=False)

    # 技术指标
    signals = calc_technical_signals(kline)
    tech_score = calc_technical_score(signals, config.technical_weight)

    # 基本面（优先使用缓存）
    if fund_cache is not None and code in fund_cache:
        fund_data = fund_cache[code]
    else:
        fund_data = get_fundamental_data(code)
    fund_score = calc_fundamental_score(fund_data, config.fundamental_weight)

    # 政策新闻
    from news_analysis import get_industry_impact_score
    news_score = get_industry_impact_score(industry, policy_impacts)

    # 行业趋势
    from scoring import get_industry_trend_score
    industry_score = get_industry_trend_score(industry, config.etf_pool, config)

    # 综合评分（使用动态调整后的权重）
    weights = score_weight if score_weight is not None else config.score_weight
    total = calc_total_score(
        tech_score, fund_score, news_score, industry_score,
        None, False, weights,
    )

    # 生成新闻摘要（支持 BaoStock 行业格式匹配）
    from news_analysis import _match_industry
    news_summary = ""
    # 清理行业名称（去除 BaoStock 格式前缀）
    clean_industry = industry
    if len(industry) > 3 and industry[0].isalpha() and industry[1:3].isdigit():
        clean_industry = industry[3:]

    for impact in policy_impacts:
        matched = False
        for affected in impact.affected_industries:
            if _match_industry(clean_industry, affected):
                matched = True
                break

        if matched or "整体市场" in impact.affected_industries:
            news_summary = impact.summary
            break

    return ScoreResult(
        code=code,
        name=name,
        is_etf=False,
        technical_score=tech_score,
        fundamental_score=fund_score,
        news_score=news_score,
        industry_score=industry_score,
        fund_flow_score=None,
        total_score=total,
        profit_probability=score_to_probability(total),
        judgment=judge_score(total, config.buy_sell_signal.buy_threshold, config.buy_sell_signal.sell_threshold),
        technical_signals=signals,
        news_summary=news_summary,
    )


def analyze_single_etf(
    etf: EtfInfo,
    policy_impacts: list[PolicyImpact],
    config: AppConfig,
    kline_cache: dict[str, pd.DataFrame] | None = None,
) -> ScoreResult:
    """分析单只ETF。

    Args:
        etf: ETF信息。
        policy_impacts: 政策影响分析结果。
        config: 应用配置。
        kline_cache: 预获取的K线数据缓存。

    Returns:
        评分结果。
    """
    code = etf.code
    name = etf.name

    # 获取K线数据（优先使用缓存）
    if kline_cache is not None and code in kline_cache:
        kline = get_kline_data_from_cache(kline_cache[code], code)
    else:
        kline = get_kline_data(code, config.lookback_days, is_etf=True)

    # 技术指标
    signals = calc_technical_signals(kline)
    tech_score = calc_technical_score(signals, config.technical_weight)

    # 政策新闻（ETF关联板块）
    from news_analysis import get_industry_impact_score
    # ETF名称中提取板块关键词
    etf_industry = name.replace("ETF", "").replace("基金", "")
    news_score = get_industry_impact_score(etf_industry, policy_impacts)

    # 资金流向
    fund_flow_score = get_etf_fund_flow(code, days=5)

    # 综合评分
    total = calc_total_score(
        tech_score, None, news_score, None,
        fund_flow_score, True, config.score_weight,
    )

    # 生成新闻摘要
    news_summary = ""
    for impact in policy_impacts:
        if etf_industry in impact.affected_industries or "整体市场" in impact.affected_industries:
            news_summary = impact.summary
            break

    return ScoreResult(
        code=code,
        name=name,
        is_etf=True,
        technical_score=tech_score,
        fundamental_score=None,
        news_score=news_score,
        industry_score=None,
        fund_flow_score=fund_flow_score,
        total_score=total,
        profit_probability=score_to_probability(total),
        judgment=judge_score(total, config.buy_sell_signal.buy_threshold, config.buy_sell_signal.sell_threshold),
        technical_signals=signals,
        news_summary=news_summary,
    )


def main() -> None:
    """主函数，编排整个分析流水线。"""
    logger.info("=" * 50)
    logger.info("开始A股每日分析")
    logger.info("=" * 50)

    # 检查是否在 CI 环境中
    is_ci = os.environ.get("CI", "false").lower() == "true"
    if is_ci:
        logger.info("检测到 CI 环境，将使用容错模式")

    # 1. 加载配置
    config = load_config()
    logger.info("配置加载完成")
    logger.info(f"  股票池大小: {config.filter.pool_size}")
    logger.info(f"  请求延迟: {config.request_delay_range[0]}-{config.request_delay_range[1]}秒")
    logger.info(f"  回溯天数: {config.lookback_days}")

    # 2. 并行获取股票池、ETF池、新闻（三者互不依赖）
    logger.info("开始并行获取股票池、ETF池、新闻...")
    stock_pool = None
    etf_pool: list[EtfInfo] = []
    etf_kline_prefetch: dict[str, pd.DataFrame] = {}
    news = []

    def _fetch_stock_pool():
        return get_stock_pool(config.filter)

    def _fetch_etf_pool():
        etf_list, etf_kline = get_etf_pool(config)
        return etf_list, etf_kline

    def _fetch_news():
        raw = fetch_news()
        return filter_by_credibility(raw)

    with ThreadPoolExecutor(max_workers=3) as executor:
        stock_future = executor.submit(_fetch_stock_pool)
        etf_future = executor.submit(_fetch_etf_pool)
        news_future = executor.submit(_fetch_news)

        # 等待股票池
        try:
            stock_pool = stock_future.result()
            logger.info(f"股票池获取完成，共 {len(stock_pool)} 只股票")
        except Exception as e:
            logger.error(f"获取股票池失败: {e}")
            if is_ci:
                logger.info("CI 环境中股票池获取失败，将生成空报告")
                stock_pool = pd.DataFrame()
            else:
                raise

        # 等待ETF池（返回 tuple[list, dict]）
        try:
            etf_pool, etf_kline_prefetch = etf_future.result()
            logger.info(f"ETF池获取完成，共 {len(etf_pool)} 只ETF")
        except Exception as e:
            logger.error(f"获取ETF池失败: {e}")
            if is_ci:
                logger.info("CI 环境中ETF池获取失败，将跳过ETF分析")
            else:
                raise

        # 等待新闻
        try:
            news = news_future.result()
            logger.info(f"新闻抓取完成，共 {len(news)} 条")
        except Exception as e:
            logger.error(f"抓取新闻失败: {e}")
            if is_ci:
                logger.info("CI 环境中新闻抓取失败，将使用空新闻列表")
            else:
                raise

    # LLM分析政策影响（依赖新闻结果，不能并行）
    llm_config = {
        "api_url": config.llm_api_url,
        "api_key": config.llm_api_key,
    }
    policy_impacts: list[PolicyImpact] = []
    try:
        policy_impacts = analyze_policy_impact(news, llm_config)
        logger.info(f"政策影响分析完成，共 {len(policy_impacts)} 条")
    except Exception as e:
        logger.error(f"政策影响分析失败: {e}")
        if is_ci:
            logger.info("CI 环境中政策影响分析失败，将使用空影响列表")
        else:
            raise

    # 5. 判断市场环境（基于中证全指，动态调整评分权重）
    try:
        from market_regime import judge_market_regime
        market_regime = judge_market_regime(config)
        logger.info(f"市场环境: {market_regime.description}")
    except Exception as e:
        logger.warning(f"市场环境判断失败，使用默认权重: {e}")

        class _FallbackRegime:
            state = "sideways"
            adjusted_weights = config.score_weight

        market_regime = _FallbackRegime()

    # 6. 分析个股
    logger.info("开始分析个股...")
    stock_results: list[ScoreResult] = []
    kline_cache: dict[str, pd.DataFrame] = {}
    report_date = datetime.now().strftime("%Y-%m-%d")
    if stock_pool is not None and not stock_pool.empty:
        # 清理过期缓存
        clear_expired_cache()

        stock_codes = [str(stock["code"]) for _, stock in stock_pool.iterrows()]
        from baostock_data import get_stock_hist_batch_baostock

        # K线数据：增量缓存策略
        # 1. 先查今天的缓存（完整命中）
        # 2. 再查前几天的缓存（增量更新，仅拉取新股票）
        # 3. 都没有则全量拉取
        kline_cache_key = f"kline_{report_date}"
        kline_cache, kline_meta = load_kline_cache_with_meta(kline_cache_key)

        if kline_cache is not None and kline_meta:
            # 今天缓存命中，检查是否包含所有请求的股票
            cached_codes = set(kline_cache.keys())
            missing_codes = [c for c in stock_codes if c not in cached_codes]
            if not missing_codes:
                logger.info(f"K线数据缓存命中（今日），共 {len(kline_cache)} 只")
            else:
                logger.info(
                    f"K线数据部分命中（今日），已有 {len(cached_codes)} 只，"
                    f"需补充 {len(missing_codes)} 只"
                )
                extra = get_stock_hist_batch_baostock(missing_codes, days=config.lookback_days)
                kline_cache.update(extra)
                save_kline_cache_with_meta(kline_cache_key, kline_cache, stock_codes)
        elif kline_cache is not None:
            # 旧格式缓存命中（无元数据），直接使用
            logger.info(f"K线数据缓存命中（旧格式），共 {len(kline_cache)} 只")
        else:
            # 今天缓存未命中，尝试加载前几天的缓存做增量更新
            prev_cache = load_previous_kline_cache(report_date)
            if prev_cache is not None:
                # 找出需要更新的股票（新股票 或 数据不够新）
                codes_to_update = [
                    c for c in stock_codes
                    if c not in prev_cache or needs_kline_update(prev_cache[c], report_date)
                ]
                if codes_to_update:
                    logger.info(
                        f"增量更新K线：复用 {len(prev_cache) - len(codes_to_update)} 只，"
                        f"需获取 {len(codes_to_update)} 只"
                    )
                    new_data = get_stock_hist_batch_baostock(codes_to_update, days=config.lookback_days)
                    kline_cache = {**prev_cache, **new_data}
                else:
                    logger.info(f"前序K线缓存完全可用，共 {len(prev_cache)} 只，无需更新")
                    kline_cache = prev_cache
                save_kline_cache_with_meta(kline_cache_key, kline_cache, stock_codes)
            else:
                # 无任何缓存，全量拉取
                logger.info(f"开始获取 {len(stock_codes)} 只股票的K线数据（单会话）...")
                kline_cache = get_stock_hist_batch_baostock(stock_codes, days=config.lookback_days)
                save_kline_cache_with_meta(kline_cache_key, kline_cache, stock_codes)
                logger.info(f"K线数据获取完成，成功 {sum(1 for v in kline_cache.values() if not v.empty)} 只")

        # 基本面数据：先查缓存（30天TTL，季度数据变化慢），未命中再并行获取
        fund_cache_key = "fund_latest"
        cached_fund = get_cached_data(fund_cache_key, ttl=FUND_CACHE_TTL)
        if cached_fund is not None and isinstance(cached_fund, dict):
            logger.info(f"基本面数据缓存命中，共 {len(cached_fund)} 只")
            from fundamental_analysis import FundamentalData, _empty_fundamental_data
            fund_cache = {}
            for code, d in cached_fund.items():
                if isinstance(d, dict):
                    # 兼容旧缓存格式（pe_ttm→roe, pb→eps）
                    if 'pe_ttm' in d and 'roe' not in d:
                        d = {
                            'roe': d.pop('pe_ttm'),
                            'eps': d.pop('pb', 0),
                            **d,
                        }
                    # 补充新增字段的默认值（旧缓存可能缺失）
                    for key, default in [
                        ('debt_ratio', None), ('cash_flow', None), ('gross_margin', None),
                    ]:
                        d.setdefault(key, default)
                    try:
                        fund_cache[code] = FundamentalData(**d)
                    except TypeError:
                        logger.warning(f"缓存数据格式异常: {code}，跳过")
                        fund_cache[code] = _empty_fundamental_data()
                else:
                    fund_cache[code] = d
        else:
            logger.info(f"开始获取 {len(stock_codes)} 只股票的基本面数据（单会话顺序获取）...")
            fund_cache = get_fundamental_data_batch(stock_codes)
            # 序列化 FundamentalData 为 dict 以便 JSON 存储
            fund_cacheSerializable = {
                k: {
                    "roe": v.roe, "eps": v.eps, "market_cap": v.market_cap,
                    "profit_growth": v.profit_growth, "revenue_growth": v.revenue_growth,
                    "debt_ratio": v.debt_ratio, "cash_flow": v.cash_flow,
                    "gross_margin": v.gross_margin,
                }
                for k, v in fund_cache.items()
            }
            set_cached_data(fund_cache_key, fund_cacheSerializable)
            logger.info(f"基本面数据获取完成，成功 {len(fund_cache)} 只")

        for idx, (_, stock) in enumerate(stock_pool.iterrows()):
            try:
                result = analyze_single_stock(
                    stock, policy_impacts, config, kline_cache, fund_cache,
                    score_weight=market_regime.adjusted_weights,
                )
                stock_results.append(result)
                logger.info(
                    f"[{idx + 1}/{len(stock_pool)}] {result.name} ({result.code}): "
                    f"{result.total_score:.0f}分 ({result.judgment})"
                )
            except Exception as e:
                logger.warning(f"分析股票 {stock.get('code', '未知')} 失败: {e}")
    else:
        logger.info("股票池为空，跳过个股分析")

    logger.info(f"个股分析完成，共 {len(stock_results)} 只符合条件")

    # 6. 分析ETF
    logger.info("开始分析ETF...")
    etf_results: list[ScoreResult] = []
    # 复用 get_etf_pool 阶段已获取的 ETF K线数据，避免重复获取
    etf_kline_cache: dict[str, pd.DataFrame] = etf_kline_prefetch
    if etf_pool:
        logger.info(f"复用ETF K线缓存，共 {len(etf_kline_cache)} 只")

    for idx, etf in enumerate(etf_pool):
        try:
            result = analyze_single_etf(etf, policy_impacts, config, etf_kline_cache)
            etf_results.append(result)
            logger.info(
                f"[{idx + 1}/{len(etf_pool)}] {result.name} ({result.code}): "
                f"{result.total_score:.0f}分 ({result.judgment})"
            )
        except Exception as e:
            logger.warning(f"分析ETF {etf.code} 失败: {e}")

    logger.info(f"ETF分析完成，共 {len(etf_results)} 只符合条件")

    # 7. 构建板块对比数据
    logger.info("开始构建板块对比数据...")
    sector_map: dict[str, list[SectorStock]] = {}
    stock_change_pcts: dict[str, float] = {}

    if stock_pool is not None and not stock_pool.empty:
        # 计算所有股票的涨跌幅（使用K线数据）
        for _, stock in stock_pool.iterrows():
            code = str(stock["code"])
            if code in kline_cache:
                try:
                    kline_df = kline_cache[code]
                    if not kline_df.empty and len(kline_df) >= 2:
                        closes = kline_df["收盘"].astype(float).tolist()
                        change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] > 0 else 0
                        stock_change_pcts[code] = change_pct
                except Exception:
                    pass

        # 构建评分映射（使用所有分析过的股票，包括未通过阈值的）
        all_stock_scores: dict[str, float] = {}
        for result in stock_results:
            all_stock_scores[result.code] = result.total_score

        # 构建板块分组
        sector_map = build_sector_stocks(stock_pool, all_stock_scores, stock_change_pcts)
        logger.info(f"板块对比数据构建完成，共 {len(sector_map)} 个板块")

    # 8. 生成买卖信号
    logger.info("开始生成买卖信号...")
    stock_signals: list[BuySellSignal] = []
    etf_signals: list[BuySellSignal] = []

    for result in stock_results:
        try:
            # 获取K线数据（优先使用缓存）
            if result.code in kline_cache:
                kline = get_kline_data_from_cache(kline_cache[result.code], result.code)
            else:
                kline = get_kline_data(result.code, config.lookback_days, is_etf=False)

            # 板块对比
            sector_comparison = None
            if stock_pool is not None and not stock_pool.empty:
                # 从股票池获取行业信息
                stock_row = stock_pool[stock_pool["code"].astype(str) == result.code]
                if not stock_row.empty:
                    industry = str(stock_row.iloc[0].get("industry", ""))
                    change_pct = stock_change_pcts.get(result.code, 0.0)

                    if industry:
                        # 获取板块内股票列表
                        sector_stocks = sector_map.get(industry, [])
                        sector_comparison = analyze_sector_comparison(
                            target_code=result.code,
                            target_name=result.name,
                            target_industry=industry,
                            target_score=result.total_score,
                            target_change_pct=change_pct,
                            sector_stocks=sector_stocks,
                            etf_pool=config.etf_pool,
                            etf_kline_cache=etf_kline_cache,
                        )

            signal = generate_buy_sell_signal(
                code=result.code,
                name=result.name,
                is_etf=False,
                total_score=result.total_score,
                technical_score=result.technical_score,
                fund_flow_score=None,
                fundamental_score=result.fundamental_score,
                news_score=result.news_score,
                kline=kline,
                config=config.buy_sell_signal,
                sector_comparison=sector_comparison,
            )
            stock_signals.append(signal)
        except Exception as e:
            logger.warning(f"生成个股买卖信号 {result.code} 失败: {e}")

    for result in etf_results:
        try:
            # 获取K线数据（优先使用缓存）
            if result.code in etf_kline_cache:
                kline = get_kline_data_from_cache(etf_kline_cache[result.code], result.code)
            else:
                kline = get_kline_data(result.code, config.lookback_days, is_etf=True)

            signal = generate_buy_sell_signal(
                code=result.code,
                name=result.name,
                is_etf=True,
                total_score=result.total_score,
                technical_score=result.technical_score,
                fund_flow_score=result.fund_flow_score,
                fundamental_score=None,
                news_score=result.news_score,
                kline=kline,
                config=config.buy_sell_signal,
            )
            etf_signals.append(signal)
        except Exception as e:
            logger.warning(f"生成ETF买卖信号 {result.code} 失败: {e}")

    logger.info(f"买卖信号生成完成：个股 {len(stock_signals)} 只，ETF {len(etf_signals)} 只")

    # 8. 生成图表（复用缓存 + 并行生成）
    logger.info("开始生成图表...")
    os.makedirs("charts", exist_ok=True)

    def _generate_chart_for_result(result: ScoreResult) -> str:
        """为单个评分结果生成图表。"""
        try:
            if result.is_etf:
                if result.code in etf_kline_cache:
                    kline = get_kline_data_from_cache(etf_kline_cache[result.code], result.code)
                else:
                    kline = get_kline_data(result.code, config.lookback_days, is_etf=True)
            else:
                if result.code in kline_cache:
                    kline = get_kline_data_from_cache(kline_cache[result.code], result.code)
                else:
                    kline = get_kline_data(result.code, config.lookback_days, is_etf=False)
            chart_path = f"charts/{result.code}.png"
            generate_chart(result.code, result.name, kline, chart_path)
            return result.code
        except Exception as e:
            logger.warning(f"生成图表 {result.code} 失败: {e}")
            return ""

    all_results = stock_results + etf_results
    if all_results:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_generate_chart_for_result, r): r for r in all_results}
            for future in as_completed(futures):
                future.result()
        logger.info(f"图表生成完成")

    # 9. 生成报告
    logger.info("开始生成报告...")
    report = generate_report(
        stock_results, etf_results, policy_impacts, report_date,
        stock_signals=stock_signals,
        etf_signals=etf_signals,
        score_threshold_high=config.buy_sell_signal.buy_threshold,
        score_threshold_low=config.buy_sell_signal.sell_threshold,
    )

    # 9.1 生成HTML报告（包含图表）
    try:
        from html_report import generate_html_report
        html_path = generate_html_report(
            report_text=report,
            chart_dir="charts",
            output_dir="public",
            report_date=report_date,
        )
        logger.info(f"HTML报告已生成: {html_path}")
    except Exception as e:
        logger.warning(f"HTML报告生成失败: {e}")

    # 10. 推送
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
    if pushplus_token:
        logger.info("开始推送...")
        try:
            success = push_to_wechat(
                title=f"A股每日分析报告 — {report_date}",
                content=report,
                token=pushplus_token,
            )
            if success:
                logger.info("推送成功")
            else:
                logger.error("推送失败")
        except Exception as e:
            logger.error(f"推送失败: {e}")
    else:
        logger.warning("PUSHPLUS_TOKEN 未设置，跳过推送")
        # 将报告保存到文件
        report_path = f"logs/report_{report_date}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"报告已保存到: {report_path}")

    # 输出缓存统计
    log_cache_stats()

    logger.info("=" * 50)
    logger.info("A股每日分析完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
