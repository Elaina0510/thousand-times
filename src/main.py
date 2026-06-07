"""主程序模块 — 编排整个分析流水线。"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

import pandas as pd

from chart_generator import generate_chart
from config import AppConfig, load_config
from etf_analyzer import EtfInfo, get_etf_fund_flow, get_etf_pool
from fundamental_analysis import calc_fundamental_score, get_fundamental_data
from news_analysis import PolicyImpact, analyze_policy_impact, fetch_news, filter_by_credibility
from push_service import push_to_wechat
from report_generator import generate_report
from scoring import ScoreResult, calc_technical_score, calc_total_score, judge_score, score_to_probability
from stock_filter import get_stock_pool
from technical_analysis import calc_technical_signals, get_kline_data

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


def analyze_single_stock(
    stock: pd.Series,
    policy_impacts: list[PolicyImpact],
    config: AppConfig,
) -> ScoreResult:
    """分析单只股票。

    Args:
        stock: 股票数据（包含 code, name, market_cap, pe_ttm, pb, industry 等）。
        policy_impacts: 政策影响分析结果。
        config: 应用配置。

    Returns:
        评分结果。
    """
    code = str(stock["code"])
    name = str(stock["name"])
    industry = str(stock.get("industry", ""))

    # 获取K线数据
    kline = get_kline_data(code, config.lookback_days, is_etf=False)

    # 技术指标
    signals = calc_technical_signals(kline)
    tech_score = calc_technical_score(signals, config.technical_weight)

    # 基本面
    fund_data = get_fundamental_data(code)
    fund_score = calc_fundamental_score(fund_data, config.fundamental_weight)

    # 政策新闻
    from news_analysis import get_industry_impact_score
    news_score = get_industry_impact_score(industry, policy_impacts)

    # 行业趋势
    from scoring import get_industry_trend_score
    industry_score = get_industry_trend_score(industry, config.etf_pool, config)

    # 综合评分
    total = calc_total_score(
        tech_score, fund_score, news_score, industry_score,
        None, False, config.score_weight,
    )

    # 生成新闻摘要
    news_summary = ""
    for impact in policy_impacts:
        if industry in impact.affected_industries or "整体市场" in impact.affected_industries:
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
        judgment=judge_score(total, config.score_threshold_high, config.score_threshold_low),
        technical_signals=signals,
        news_summary=news_summary,
    )


def analyze_single_etf(
    etf: EtfInfo,
    policy_impacts: list[PolicyImpact],
    config: AppConfig,
) -> ScoreResult:
    """分析单只ETF。

    Args:
        etf: ETF信息。
        policy_impacts: 政策影响分析结果。
        config: 应用配置。

    Returns:
        评分结果。
    """
    code = etf.code
    name = etf.name

    # 获取K线数据
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
        judgment=judge_score(total, config.score_threshold_high, config.score_threshold_low),
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

    # 2. 获取股票池
    logger.info("开始获取股票池...")
    stock_pool = None
    try:
        stock_pool = get_stock_pool(config.filter)
        logger.info(f"股票池获取完成，共 {len(stock_pool)} 只股票")
    except Exception as e:
        logger.error(f"获取股票池失败: {e}")
        if is_ci:
            logger.info("CI 环境中股票池获取失败，将生成空报告")
            stock_pool = pd.DataFrame()
        else:
            raise

    # 3. 获取ETF池
    logger.info("开始获取ETF池...")
    etf_pool: list[EtfInfo] = []
    try:
        etf_pool = get_etf_pool(config)
        logger.info(f"ETF池获取完成，共 {len(etf_pool)} 只ETF")
    except Exception as e:
        logger.error(f"获取ETF池失败: {e}")
        if is_ci:
            logger.info("CI 环境中ETF池获取失败，将跳过ETF分析")
        else:
            raise

    # 4. 抓取并分析新闻（全局只执行一次）
    logger.info("开始抓取新闻...")
    news = []
    try:
        news = fetch_news()
        news = filter_by_credibility(news)
        logger.info(f"新闻抓取完成，共 {len(news)} 条")
    except Exception as e:
        logger.error(f"抓取新闻失败: {e}")
        if is_ci:
            logger.info("CI 环境中新闻抓取失败，将使用空新闻列表")
        else:
            raise

    # LLM分析政策影响
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

    # 5. 分析个股
    logger.info("开始分析个股...")
    stock_results: list[ScoreResult] = []
    if stock_pool is not None and not stock_pool.empty:
        for idx, (_, stock) in enumerate(stock_pool.iterrows()):
            try:
                result = analyze_single_stock(stock, policy_impacts, config)
                if (
                    result.total_score >= config.score_threshold_high
                    or result.total_score < config.score_threshold_low
                ):
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
    for idx, etf in enumerate(etf_pool):
        try:
            result = analyze_single_etf(etf, policy_impacts, config)
            if (
                result.total_score >= config.score_threshold_high
                or result.total_score < config.score_threshold_low
            ):
                etf_results.append(result)
                logger.info(
                    f"[{idx + 1}/{len(etf_pool)}] {result.name} ({result.code}): "
                    f"{result.total_score:.0f}分 ({result.judgment})"
                )
        except Exception as e:
            logger.warning(f"分析ETF {etf.code} 失败: {e}")

    logger.info(f"ETF分析完成，共 {len(etf_results)} 只符合条件")

    # 7. 生成图表
    logger.info("开始生成图表...")
    os.makedirs("charts", exist_ok=True)
    for result in stock_results + etf_results:
        try:
            kline = get_kline_data(result.code, config.lookback_days, result.is_etf)
            chart_path = f"charts/{result.code}.png"
            generate_chart(result.code, result.name, kline, chart_path)
        except Exception as e:
            logger.warning(f"生成图表 {result.code} 失败: {e}")

    # 8. 生成报告
    logger.info("开始生成报告...")
    report_date = datetime.now().strftime("%Y-%m-%d")
    report = generate_report(stock_results, etf_results, policy_impacts, report_date)

    # 9. 推送
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

    logger.info("=" * 50)
    logger.info("A股每日分析完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
