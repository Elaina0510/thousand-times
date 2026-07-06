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
    ma60_data_days: int = 60  # MA60有效数据天数（<60时金叉/多头排列权重减半）


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


class ScoreCalculator:
    """综合评分计算器 — 四维度加权模型。

    个股：技术指标(35%) + 趋势判断(25%) + 量价配合(20%) + 基本面(20%)
    ETF：  技术指标(55%) + 政策新闻(35%) + 资金流向(10%)
    """

    # 各维度满分常量（用于归一化）
    TECHNICAL_MAX = 55.0      # 技术指标满分（ETF维度，个股也用此归一化）
    TREND_MAX = 10.0           # 趋势判断满分（行业趋势 0~10）
    VOLUME_PRICE_MAX = 20.0    # 量价配合满分（政策新闻 -20~+20 映射到 0~20）
    FUNDAMENTAL_MAX = 30.0     # 基本面满分
    ETF_NEWS_MAX = 35.0        # ETF政策新闻满分
    ETF_FUND_FLOW_MAX = 10.0   # ETF资金流向满分

    def __init__(self, config: ScoreWeightConfig) -> None:
        self.config = config

    def normalize_score(self, score: float, max_score: float) -> float:
        """将各维度评分归一化到 0~100 范围。

        Args:
            score: 原始评分。
            max_score: 该维度的满分。

        Returns:
            归一化后的评分（0~100）。
        """
        if max_score <= 0:
            return 0.0
        return max(0.0, min(100.0, (score / max_score) * 100))

    def calc_total_score(
        self,
        technical: float,
        fundamental: float | None,
        news: float,
        industry: float | None,
        fund_flow: float | None,
        is_etf: bool,
    ) -> float:
        """计算加权综合评分。

        Args:
            technical: 技术指标评分（个股0~55，ETF0~55）。
            fundamental: 基本面评分（0~30，ETF为None）。
            news: 政策新闻评分（-20~+20）。
            industry: 行业趋势评分（0~10，ETF为None）。
            fund_flow: 资金流向评分（0~10，个股为None）。
            is_etf: 是否为ETF。

        Returns:
            综合评分（0~100）。
        """
        if is_etf:
            tech_norm = self.normalize_score(technical, self.TECHNICAL_MAX)
            news_norm = self.normalize_score(max(0, news), self.ETF_NEWS_MAX)
            fund_norm = self.normalize_score(fund_flow or 0.0, self.ETF_FUND_FLOW_MAX)
            total = (
                tech_norm * self.config.etf_technical
                + news_norm * self.config.etf_news
                + fund_norm * self.config.etf_fund_flow
            )
        else:
            tech_norm = self.normalize_score(technical, self.TECHNICAL_MAX)
            fund_norm = self.normalize_score(fundamental or 0.0, self.FUNDAMENTAL_MAX)
            # 趋势维度：使用行业趋势评分（0~10）
            trend_norm = self.normalize_score(industry or 0.0, self.TREND_MAX)
            # 量价维度：使用政策新闻评分（-20~+20 映射到 0~100）
            vp_norm = self.normalize_score(max(0, news), self.VOLUME_PRICE_MAX)
            total = (
                tech_norm * self.config.stock_technical
                + trend_norm * self.config.stock_trend
                + vp_norm * self.config.stock_volume_price
                + fund_norm * self.config.stock_fundamental
            )

        return max(0.0, min(100.0, round(total, 2)))

    @staticmethod
    def classify(score: float) -> str:
        """根据综合评分分类投资建议。

        Args:
            score: 综合评分（0~100）。

        Returns:
            "strong_buy" (≥75), "buy" (60~74), "hold" (45~59), "avoid" (<45)
        """
        if score >= 75:
            return "strong_buy"
        elif score >= 60:
            return "buy"
        elif score >= 45:
            return "hold"
        else:
            return "avoid"


def calc_total_score(
    technical: float,
    fundamental: float | None,
    news: float,
    industry: float | None,
    fund_flow: float | None,
    is_etf: bool,
    config: ScoreWeightConfig,
) -> float:
    """计算综合评分（加权模型）。

    使用四维度加权计算：
    - 个股：技术指标(35%) + 趋势判断(25%) + 量价配合(20%) + 基本面(20%)
    - ETF：  技术指标(55%) + 政策新闻(35%) + 资金流向(10%)

    Args:
        technical: 技术指标评分。
        fundamental: 基本面评分（ETF为None）。
        news: 政策新闻评分。
        industry: 行业趋势评分（ETF为None）。
        fund_flow: 资金流向评分（个股为None）。
        is_etf: 是否为ETF。
        config: 评分权重配置。

    Returns:
        综合评分（0~100）。
    """
    calculator = ScoreCalculator(config)
    return calculator.calc_total_score(
        technical=technical,
        fundamental=fundamental,
        news=news,
        industry=industry,
        fund_flow=fund_flow,
        is_etf=is_etf,
    )


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


def judge_score(score: float, high_threshold: float = 75.0, low_threshold: float = 45.0) -> str:
    """判定评分等级（四档分类）。

    Args:
        score: 综合评分。
        high_threshold: 强烈买入阈值（默认75）。
        low_threshold: 回避阈值（默认45）。

    Returns:
        "strong_buy" (≥75), "buy" (60~74), "hold" (45~59), "avoid" (<45)
    """
    if score >= high_threshold:
        return "strong_buy"
    elif score >= 60:
        return "buy"
    elif score >= low_threshold:
        return "hold"
    else:
        return "avoid"


# 行业→ETF映射表（支持多种格式）
INDUSTRY_ETF_MAP: dict[str, str] = {
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


def clean_industry_name(industry: str) -> str:
    """清理行业名称（去除 BaoStock 格式前缀）。

    Args:
        industry: 原始行业名称，如 "J66货币金融服务"。

    Returns:
        清理后的行业名称，如 "货币金融服务"。
    """
    if len(industry) > 3 and industry[0].isalpha() and industry[1:3].isdigit():
        return industry[3:]
    return industry


def find_etf_for_industry(industry: str, etf_pool: list[str]) -> str | None:
    """查找行业对应的ETF代码。

    Args:
        industry: 行业名称。
        etf_pool: 可用的ETF代码列表。

    Returns:
        ETF代码，未找到返回 None。
    """
    clean_industry = clean_industry_name(industry)

    # 精确匹配
    etf_code = INDUSTRY_ETF_MAP.get(clean_industry)
    if etf_code and etf_code in etf_pool:
        return etf_code

    # 模糊匹配
    for key, value in INDUSTRY_ETF_MAP.items():
        if key in clean_industry or clean_industry in key:
            if value in etf_pool:
                return value

    return None


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

    etf_code = find_etf_for_industry(industry, etf_pool)

    if etf_code is None:
        # 无法匹配行业，默认横盘评分
        return config.industry_trend_weight.sideways

    # 注意：实际的K线数据获取和均线判断需要依赖 technical_analysis 模块
    # 这里返回默认值，实际使用时会在 main.py 中调用 technical_analysis 模块
    # 来获取ETF的K线数据并判断趋势
    return config.industry_trend_weight.sideways


def calc_technical_score(
    signals: TechnicalSignals,
    weights: TechnicalWeightConfig,
    kline: object | None = None,
) -> float:
    """根据技术信号和权重计算技术指标评分。

    Args:
        signals: 技术信号汇总。
        weights: 技术指标权重配置。
        kline: K线数据（可选，需有 closes 属性，用于计算基线分）。

    Returns:
        评分（0~40分，负分截断到0）。
    """
    score = 0.0

    # MA60 数据不足时，相关信号权重减半
    ma60_days = getattr(signals, 'ma60_data_days', 60)
    ma60_penalty = 0.5 if ma60_days < 60 else 1.0

    # 加分项
    if signals.ma5_10_golden:
        score += weights.ma_golden_cross
    if signals.ma20_60_golden:
        score += weights.ma20_60_golden_cross * ma60_penalty
    if signals.bullish_alignment:
        score += weights.bullish_alignment * ma60_penalty
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

    # 基线分：近期涨跌幅（有K线数据时）
    if kline is not None and hasattr(kline, 'closes'):
        closes_list: list[float] = getattr(kline, 'closes', [])
        if len(closes_list) >= 5:
            change_5d = (closes_list[-1] - closes_list[-5]) / closes_list[-5] * 100 if closes_list[-5] > 0 else 0
            change_20d = 0.0
            if len(closes_list) >= 20 and closes_list[-20] > 0:
                change_20d = (closes_list[-1] - closes_list[-20]) / closes_list[-20] * 100
            if change_5d > 0:
                score += 5.0
            if change_20d > 0:
                score += 3.0

    # 截断到 0
    return max(0.0, score)
