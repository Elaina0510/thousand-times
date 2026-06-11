"""综合评分模块 — 汇总各维度评分并排序。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from config import (
    AppConfig,
    ScoreWeightConfig,
    TechnicalWeightConfig,
)


@dataclass
class TechnicalSignals:
    """技术指标信号汇总。"""

    ma5_10_golden: bool = False  # MA5/10金叉（近3日）
    ma5_10_death: bool = False  # MA5/10死叉（近3日）
    ma20_60_golden: bool = False  # MA20/60金叉（近5日）
    bullish_alignment: bool = False  # 多头排列
    above_ma20: bool = False  # 股价站上MA20
    macd_golden: bool = False  # MACD金叉（近3日）
    macd_death: bool = False  # MACD死叉（近3日）
    macd_above_zero: bool = False  # 零轴上方金叉
    macd_divergence: bool = False  # MACD底背离（近10日）
    volume_up: bool = False  # 放量上涨
    volume_down: bool = False  # 放量下跌
    volume_peak: bool = False  # 天量见天价
    pullback_ok: bool = False  # 缩量回调到位


@dataclass
class ScoreResult:
    """评分结果。"""

    code: str
    name: str
    is_etf: bool
    technical_score: float
    fundamental_score: float | None  # ETF为None
    news_score: float
    industry_score: float | None  # ETF为None
    fund_flow_score: float | None  # 个股为None
    total_score: float
    profit_probability: float
    judgment: str
    technical_signals: TechnicalSignals
    news_summary: str


def calc_total_score(
    technical: float,
    fundamental: float | None,
    news: float,
    industry: float | None,
    fund_flow: float | None,
    is_etf: bool,
    config: ScoreWeightConfig,
) -> float:
    """计算综合评分。

    各维度评分已在各自的满分范围内（技术0-40/55、基本面0-30、政策-20~+20、行业0-10、资金流向0-10），
    直接求和得到总分。

    Args:
        technical: 技术指标评分（个股0~40，ETF0~55）。
        fundamental: 基本面评分（0~30，ETF为None）。
        news: 政策新闻评分（-20~+20）。
        industry: 行业趋势评分（0~10，ETF为None）。
        fund_flow: 资金流向评分（0~10，个股为None）。
        is_etf: 是否为ETF。
        config: 评分权重配置。

    Returns:
        综合评分（0~100）。
    """
    total = technical
    if fundamental is not None:
        total += fundamental
    total += news
    if industry is not None:
        total += industry
    if fund_flow is not None:
        total += fund_flow

    # 截断到 [0, 100] 范围
    return max(0.0, min(100.0, total))


def score_to_probability(score: float) -> float:
    """将综合评分转换为盈利概率。

    使用 sigmoid 函数：P = 1 / (1 + e^(-0.1*(x-50)))
    归一化到 0~100% 范围。

    Args:
        score: 综合评分（0~100）。

    Returns:
        盈利概率百分比（0~100）。
    """
    k = 0.1
    x0 = 50
    raw = 1 / (1 + math.exp(-k * (score - x0)))
    # 归一化：sigmoid(0) ~ sigmoid(100) 映射到 0% ~ 100%
    low = 1 / (1 + math.exp(-k * (0 - x0)))
    high = 1 / (1 + math.exp(-k * (100 - x0)))
    normalized = (raw - low) / (high - low)
    return round(normalized * 100, 0)


def judge_score(score: float, high_threshold: float, low_threshold: float) -> str:
    """判定评分等级。

    Args:
        score: 综合评分。
        high_threshold: 高概率阈值（默认70）。
        low_threshold: 风险警示阈值（默认30）。

    Returns:
        "recommend" (≥70), "watch" (50~69), "bearish" (30~49), "risk" (<30)
    """
    if score >= high_threshold:
        return "recommend"
    elif score >= 50:
        return "watch"
    elif score >= low_threshold:
        return "bearish"
    else:
        return "risk"


def get_industry_trend_score(
    industry: str,
    etf_pool: list[str],
    config: AppConfig,
) -> float:
    """获取所属行业的趋势评分（仅个股使用）。

    通过查找该行业对应的ETF，分析ETF的均线排列状态来评估行业趋势。

    Args:
        industry: 股票所属行业名称。
        etf_pool: ETF代码列表。
        config: 应用配置。

    Returns:
        评分（0~10分）。
    """
    if not industry:
        return config.industry_trend_weight.sideways

    # 行业→ETF映射表（支持多种格式）
    industry_etf_map: dict[str, str] = {
        # 中文行业名称
        "半导体": "512480",
        "芯片": "512480",
        "新能源": "516160",
        "光伏": "516160",
        "锂电": "516160",
        "医药": "512010",
        "医药生物": "512010",
        "消费": "159928",
        "食品饮料": "159928",
        "白酒": "159928",
        "军工": "512660",
        "国防军工": "512660",
        "金融": "510230",
        "银行": "510230",
        "证券": "510230",
        "地产": "512200",
        "房地产": "512200",
        # BaoStock 证监会行业分类关键词
        "计算机": "512480",
        "通信": "512480",
        "电子": "512480",
        "软件": "512480",
        "信息": "512480",
        "医药制造": "512010",
        "医疗": "512010",
        "食品": "159928",
        "饮料": "159928",
        "酒": "159928",
        "航空航天": "512660",
        "保险": "510230",
        "证券期货": "510230",
        "建筑": "512200",
    }

    # 清理行业名称（去除 BaoStock 格式前缀，如 "J66货币金融服务" → "货币金融服务"）
    clean_industry = industry
    if len(industry) > 3 and industry[0].isalpha() and industry[1:3].isdigit():
        clean_industry = industry[3:]

    # 查找对应的ETF（精确匹配）
    etf_code = industry_etf_map.get(clean_industry)

    # 模糊匹配
    if etf_code is None:
        for key, value in industry_etf_map.items():
            if key in clean_industry or clean_industry in key:
                etf_code = value
                break

    if etf_code is None or etf_code not in etf_pool:
        # 无法匹配行业，默认横盘评分
        return config.industry_trend_weight.sideways

    # 注意：实际的K线数据获取和均线判断需要依赖 technical_analysis 模块
    # 这里返回默认值，实际使用时会在 main.py 中调用 technical_analysis 模块
    # 来获取ETF的K线数据并判断趋势
    return config.industry_trend_weight.sideways


def calc_technical_score(signals: TechnicalSignals, weights: TechnicalWeightConfig) -> float:
    """根据技术信号和权重计算技术指标评分。

    Args:
        signals: 技术信号汇总。
        weights: 技术指标权重配置。

    Returns:
        评分（0~40分，负分截断到0）。
    """
    score = 0.0

    # 加分项
    if signals.ma5_10_golden:
        score += weights.ma_golden_cross
    if signals.ma20_60_golden:
        score += weights.ma20_60_golden_cross
    if signals.bullish_alignment:
        score += weights.bullish_alignment
    if signals.above_ma20:
        score += weights.above_ma20
    if signals.macd_golden:
        score += weights.macd_golden_cross
    if signals.macd_above_zero:
        score += weights.macd_above_zero
    if signals.macd_divergence:
        score += weights.macd_divergence
    if signals.volume_up:
        score += weights.volume_up
    if signals.pullback_ok:
        score += weights.pullback_ok

    # 扣分项
    if signals.ma5_10_death:
        score -= weights.ma_death_cross
    if signals.macd_death:
        score -= weights.macd_death_cross
    if signals.volume_peak:
        score -= weights.volume_peak
    if signals.volume_down:
        score -= weights.volume_drop

    # 截断到 0
    return max(0.0, score)
