"""配置管理模块 — 集中管理所有可配置参数。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class TechnicalWeightConfig:
    """技术指标评分权重配置。"""

    ma_golden_cross: float = 5.0  # MA5/10金叉
    ma20_60_golden_cross: float = 5.0  # MA20/60金叉
    bullish_alignment: float = 5.0  # 多头排列
    above_ma20: float = 3.0  # 股价站上MA20
    macd_golden_cross: float = 5.0  # MACD金叉
    macd_above_zero: float = 5.0  # 零轴上方金叉
    macd_divergence: float = 5.0  # MACD底背离
    volume_up: float = 4.0  # 放量上涨
    pullback_ok: float = 3.0  # 缩量回调到位
    # 扣分项（存储为正数，计算时取负）
    ma_death_cross: float = 5.0  # MA5/10死叉
    macd_death_cross: float = 5.0  # MACD死叉
    volume_peak: float = 5.0  # 天量见天价
    volume_drop: float = 4.0  # 放量下跌


@dataclass
class FundamentalWeightConfig:
    """基本面评分权重配置（仅个股）。"""

    pe_low: float = 8.0  # PE合理偏低
    pe_mid: float = 3.0  # PE偏高
    pe_high: float = 0.0  # PE过高
    pb_ok: float = 5.0  # PB合理
    profit_high_growth: float = 10.0  # 净利润高增长
    profit_stable_growth: float = 5.0  # 净利润稳定增长
    profit_decline: float = 0.0  # 净利润下降
    revenue_high_growth: float = 7.0  # 营收高增长
    revenue_stable_growth: float = 3.0  # 营收稳定增长
    revenue_decline: float = 0.0  # 营收下降


@dataclass
class NewsWeightConfig:
    """政策新闻评分权重配置。"""

    direct_positive: float = 17.5  # 直接利好（取中间值）
    indirect_positive: float = 11.0  # 间接利好
    neutral: float = 5.0  # 中性
    indirect_negative: float = -2.5  # 间接利空
    direct_negative: float = -7.5  # 直接利空


@dataclass
class IndustryTrendWeightConfig:
    """行业趋势评分权重配置（仅个股）。"""

    uptrend: float = 9.0  # 上升趋势
    sideways: float = 4.5  # 横盘震荡
    downtrend: float = 1.0  # 下降趋势


@dataclass
class EtfFundFlowWeightConfig:
    """ETF资金流向评分权重配置。"""

    continuous_growth: float = 9.0  # 份额持续增长
    slight_growth: float = 5.5  # 份额小幅增长
    flat: float = 3.0  # 份额基本持平
    continuous_decline: float = 1.0  # 份额持续减少


@dataclass
class ScoreWeightConfig:
    """综合评分维度权重配置。"""

    # 个股
    stock_technical: float = 0.40
    stock_fundamental: float = 0.30
    stock_news: float = 0.20
    stock_industry: float = 0.10
    # ETF
    etf_technical: float = 0.55
    etf_news: float = 0.35
    etf_fund_flow: float = 0.10


@dataclass
class FilterConfig:
    """股票池筛选配置。"""

    min_market_cap: float = 20e8  # 最低市值（20亿）
    min_listing_months: int = 3  # 最低上市月数
    pool_size: int = 200  # 筛选后保留数量（从1000减少到200以提高性能）


# 默认ETF池
DEFAULT_ETF_POOL: list[str] = [
    # 大盘宽基ETF
    "510300",  # 沪深300ETF
    "510500",  # 中证500ETF
    "159915",  # 创业板ETF
    "588000",  # 科创50ETF
    # 细分行业ETF
    "512480",  # 半导体ETF
    "516160",  # 新能源ETF
    "512010",  # 医药ETF
    "159928",  # 消费ETF
    "512660",  # 军工ETF
    "510230",  # 金融ETF
    "512200",  # 地产ETF
]


@dataclass
class AppConfig:
    """应用总配置。"""

    filter: FilterConfig = field(default_factory=FilterConfig)
    score_weight: ScoreWeightConfig = field(default_factory=ScoreWeightConfig)
    technical_weight: TechnicalWeightConfig = field(default_factory=TechnicalWeightConfig)
    fundamental_weight: FundamentalWeightConfig = field(default_factory=FundamentalWeightConfig)
    news_weight: NewsWeightConfig = field(default_factory=NewsWeightConfig)
    industry_trend_weight: IndustryTrendWeightConfig = field(default_factory=IndustryTrendWeightConfig)
    etf_fund_flow_weight: EtfFundFlowWeightConfig = field(default_factory=EtfFundFlowWeightConfig)
    etf_pool: list[str] = field(default_factory=lambda: list(DEFAULT_ETF_POOL))
    score_threshold_high: float = 70.0
    score_threshold_low: float = 30.0
    request_delay_range: tuple[float, float] = (1.0, 5.0)
    max_retries: int = 3
    lookback_days: int = 60
    llm_api_url: str = ""
    llm_api_key: str = ""


def load_config() -> AppConfig:
    """加载配置，优先级：环境变量 > 默认值。

    Returns:
        完整的 AppConfig 实例。
    """
    config = AppConfig()
    # 从环境变量读取敏感信息
    config.llm_api_url = os.environ.get("LLM_API_URL", "")
    config.llm_api_key = os.environ.get("LLM_API_KEY", "")

    # CI 环境：使用默认配置（1000只股票）
    # 如果需要调整，可以通过环境变量覆盖
    ci_pool_size = os.environ.get("CI_POOL_SIZE")
    if ci_pool_size:
        config.filter.pool_size = int(ci_pool_size)

    ci_delay_min = os.environ.get("CI_DELAY_MIN")
    ci_delay_max = os.environ.get("CI_DELAY_MAX")
    if ci_delay_min and ci_delay_max:
        config.request_delay_range = (float(ci_delay_min), float(ci_delay_max))

    return config
