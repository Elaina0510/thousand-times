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
    """综合评分维度权重配置（四维度加权模型）。

    个股四维度：技术指标 35% + 趋势判断 25% + 量价配合 20% + 基本面 20% = 100%
    ETF 三维度：技术指标 55% + 政策新闻 35% + 资金流向 10% = 100%
    """

    # 个股四维度权重
    stock_technical: float = 0.35
    stock_trend: float = 0.25
    stock_volume_price: float = 0.20
    stock_fundamental: float = 0.20
    # 兼容旧字段（个股政策新闻、行业，映射到趋势维度）
    stock_news: float = 0.25  # 等同于 stock_trend
    stock_industry: float = 0.20  # 等同于 stock_volume_price
    # ETF 三维度权重
    etf_technical: float = 0.55
    etf_news: float = 0.35
    etf_fund_flow: float = 0.10


@dataclass
class BuySellSignalConfig:
    """买卖信号配置。"""
    # 三档阈值
    buy_threshold: float = 70.0      # 买入区阈值
    sell_threshold: float = 30.0     # 卖出区阈值
    # 关键价位计算权重
    ma_weight: float = 0.4           # 均线权重（支撑位/压力位中均线的占比，剩余为近期高低点）
    # 历史准确率周期
    history_days: list[int] = field(default_factory=lambda: [30, 90, 180])


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
class RegimeConfig:
    """市场环境判断配置。"""

    ma_short: int = 20
    ma_long: int = 60
    volume_bull_ratio: float = 1.2
    volume_bear_ratio: float = 0.8
    north_flow_threshold: float = 100e8  # 100亿
    advance_decline_bull: float = 1.5
    advance_decline_bear: float = 0.7
    pe_percentile_low: float = 0.4
    pe_percentile_high: float = 0.7


@dataclass
class FactorWeightConfig:
    """因子权重配置（按市场环境）。"""

    bull: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.30,
        "fundamental": 0.15,
        "capital": 0.15,
        "sentiment": 0.10,
        "momentum": 0.30,
    })
    bear: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.25,
        "fundamental": 0.30,
        "capital": 0.15,
        "sentiment": 0.15,
        "momentum": 0.15,
    })
    sideways: dict[str, float] = field(default_factory=lambda: {
        "technical": 0.30,
        "fundamental": 0.20,
        "capital": 0.15,
        "sentiment": 0.15,
        "momentum": 0.20,
    })


@dataclass
class SignalConfig:
    """信号生成配置。"""

    min_buy_votes: int = 3
    min_sell_votes: int = 3
    factor_buy_threshold: float = 70.0
    factor_sell_threshold: float = 30.0
    technical_buy_threshold: float = 75.0
    technical_sell_threshold: float = 25.0
    atr_target_multiplier: float = 2.0
    atr_stop_multiplier: float = 1.5
    min_risk_reward: float = 2.0


@dataclass
class RealtimeConfig:
    """实时提醒配置。"""

    check_interval_minutes: int = 30
    score_jump_threshold: float = 25.0
    north_flow_alert: float = 100e8


@dataclass
class BacktestConfig:
    """回测配置。"""

    start_date: str = "2024-01-01"
    end_date: str = "2025-12-31"
    pool_size: int = 50
    hold_days: list[int] = field(default_factory=lambda: [1, 3, 5, 10])
    buy_threshold: float = 70.0
    sell_threshold: float = 30.0
    commission_rate: float = 0.001
    slippage: float = 0.001
    initial_capital: float = 100000.0


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
    buy_sell_signal: BuySellSignalConfig = field(default_factory=BuySellSignalConfig)
    request_delay_range: tuple[float, float] = (1.0, 5.0)
    max_retries: int = 3
    lookback_days: int = 60
    llm_api_url: str = ""
    llm_api_key: str = ""
    # V2 管道配置
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    factor_weights: FactorWeightConfig = field(default_factory=FactorWeightConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    realtime: RealtimeConfig = field(default_factory=RealtimeConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    use_v2_pipeline: bool = False


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
