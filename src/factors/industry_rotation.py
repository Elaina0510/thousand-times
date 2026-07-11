"""行业轮动分析模块 — IndustryRotationAnalyzer.

分析行业板块间的强弱关系，识别轮动方向，
为因子评分和仓位分配提供行业维度的 alpha。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")

# 扩展的行业→ETF 映射（覆盖 31 个申万一级行业）
EXTENDED_INDUSTRY_ETF_MAP: dict[str, str] = {
    # 现有映射
    "银行": "512800",
    "非银金融": "512070",
    "证券": "512880",
    "保险": "512070",
    "房地产": "512200",
    "地产": "512200",
    "煤炭": "515220",
    "石油石化": "159845",
    "钢铁": "515210",
    "有色金属": "512400",
    "有色": "512400",
    "化工": "516020",
    "建筑材料": "159745",
    "建筑装饰": "516970",
    "机械设备": "159886",
    "电力设备": "516160",
    "新能源": "516160",
    "国防军工": "512660",
    "军工": "512660",
    "汽车": "516110",
    "家用电器": "159996",
    "家电": "159996",
    "纺织服装": "159840",
    "纺织": "159840",
    "轻工制造": "159840",
    "商贸零售": "159766",
    "社会服务": "159766",
    "食品饮料": "515170",
    "白酒": "512690",
    "医药生物": "512010",
    "医药": "512010",
    "农林牧渔": "159825",
    "农业": "159825",
    "公用事业": "159611",
    "电力": "159611",
    "交通运输": "159662",
    "交运": "159662",
    "电子": "512480",
    "半导体": "512480",
    "计算机": "512720",
    "传媒": "512980",
    "通信": "515050",
    "环保": "516650",
    "美容护理": "159766",
    "综合": "510210",
}


@dataclass
class IndustryMomentum:
    """单个行业的动量数据."""

    industry_name: str
    etf_code: str | None = None     # 对应的 ETF 代码
    stock_count: int = 0            # 行业内股票数量

    # 各周期收益率（%）
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    ret_20d: float = 0.0
    ret_60d: float = 0.0

    # 排名（1=最强）
    rank_5d: int = 0
    rank_20d: int = 0

    # 趋势强度
    trend_strength: float = 0.0     # 0-100, 越高越强
    trend_direction: str = "sideways"  # "up", "down", "sideways"

    # 资金流向
    fund_flow_5d: float = 0.0       # 近5日资金净流入（亿元）


@dataclass
class RotationSignal:
    """轮动信号."""

    # 领涨行业（动量最强的前N个）
    leading_industries: list[str] = field(default_factory=list)
    # 转向行业（从弱转强的）
    turning_industries: list[str] = field(default_factory=list)
    # 衰减行业（从强转弱的）
    fading_industries: list[str] = field(default_factory=list)
    # 轮动方向描述
    description: str = ""
    # 建议超配行业
    overweight: list[str] = field(default_factory=list)
    # 建议低配行业
    underweight: list[str] = field(default_factory=list)


@dataclass
class IndustryScoreAdjustment:
    """行业维度对个股评分的调整量."""

    code: str
    industry: str
    # 行业 alpha：行业动量在全体行业中的百分位 (0~1)
    industry_alpha: float = 0.5
    # 调整量：加到总分上的分数 (-10 ~ +10)
    adjustment: float = 0.0
    # 理由
    reason: str = ""


def _calc_industry_returns(
    etf_kline: pd.DataFrame,
    days_list: list[int],
) -> dict[int, float]:
    """计算行业 ETF 各周期收益率.

    Args:
        etf_kline: ETF K 线数据.
        days_list: 周期列表，如 [1, 5, 20, 60].

    Returns:
        {days: return_pct} 映射.
    """
    result: dict[int, float] = {}
    if etf_kline.empty:
        for d in days_list:
            result[d] = 0.0
        return result

    close_col = "收盘" if "收盘" in etf_kline.columns else "close"
    if close_col not in etf_kline.columns:
        for d in days_list:
            result[d] = 0.0
        return result

    closes = etf_kline[close_col].astype(float)
    last_close = closes.iloc[-1]

    for d in days_list:
        if len(closes) <= d:
            result[d] = 0.0
        else:
            prev_close = closes.iloc[-(d + 1)]
            if prev_close and prev_close != 0:
                result[d] = float((last_close - prev_close) / prev_close * 100)
            else:
                result[d] = 0.0

    return result


def _calc_trend_strength(etf_kline: pd.DataFrame) -> tuple[float, str]:
    """计算趋势强度和方向.

    Args:
        etf_kline: ETF K 线数据.

    Returns:
        (trend_strength 0-100, trend_direction).
    """
    if etf_kline.empty or len(etf_kline) < 20:
        return 50.0, "sideways"

    close_col = "收盘" if "收盘" in etf_kline.columns else "close"
    if close_col not in etf_kline.columns:
        return 50.0, "sideways"

    closes = etf_kline[close_col].astype(float)
    last_close = closes.iloc[-1]
    ma5 = closes.rolling(5).mean().iloc[-1]
    ma10 = closes.rolling(10).mean().iloc[-1]
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1] if len(closes) >= 60 else ma20

    # 多头排列
    if last_close > ma5 > ma10 > ma20 > ma60:
        return 90.0, "up"
    elif last_close > ma5 > ma10 > ma20:
        return 70.0, "up"
    elif last_close > ma20:
        return 55.0, "up"
    # 空头排列
    elif last_close < ma5 < ma10 < ma20:
        return 30.0, "down"
    elif last_close < ma20:
        return 40.0, "down"
    else:
        return 50.0, "sideways"


def analyze_industry_rotation(
    etf_kline_cache: dict[str, pd.DataFrame],
    sector_flow: pd.DataFrame,
    industry_stocks: dict[str, list[str]],
    lookback_days: int = 60,
) -> tuple[list[IndustryMomentum], RotationSignal]:
    """分析行业轮动.

    分析流程：
    1. 通过行业 ETF 的 K 线计算各周期收益率
    2. 按 20 日收益率排名，识别领涨/领跌行业
    3. 对比 5 日和 20 日排名变化，识别转向行业
    4. 结合行业资金流向，确认轮动方向
    5. 生成超配/低配建议

    Args:
        etf_kline_cache: 行业 ETF 的 K 线缓存.
        sector_flow: 行业资金流向数据.
        industry_stocks: 行业→股票代码列表映射.
        lookback_days: 回溯天数.

    Returns:
        (行业动量列表, 轮动信号)
    """
    momentum_list: list[IndustryMomentum] = []

    # 获取行业资金流向映射
    fund_flow_map: dict[str, float] = {}
    if not sector_flow.empty:
        for _, row in sector_flow.iterrows():
            ind_name = str(row.get("名称", row.get("板块", "")))
            if ind_name:
                try:
                    fund_flow_map[ind_name] = float(
                        row.get("主力净流入-净额", row.get("净流入", 0))
                    )
                except (ValueError, TypeError):
                    fund_flow_map[ind_name] = 0.0

    for industry_name, stocks in industry_stocks.items():
        etf_code = EXTENDED_INDUSTRY_ETF_MAP.get(industry_name)
        etf_kline = pd.DataFrame()

        if etf_code and etf_code in etf_kline_cache:
            etf_kline = etf_kline_cache[etf_code]
        elif etf_code:
            # 尝试通过行业名模糊匹配
            for cache_code, cache_kline in etf_kline_cache.items():
                if cache_code == etf_code:
                    etf_kline = cache_kline
                    break

        # 计算收益率
        returns = _calc_industry_returns(etf_kline, [1, 5, 20, 60])
        trend_strength, trend_direction = _calc_trend_strength(etf_kline)

        # 资金流向
        fund_flow = fund_flow_map.get(industry_name, 0.0)

        momentum_list.append(IndustryMomentum(
            industry_name=industry_name,
            etf_code=etf_code,
            stock_count=len(stocks),
            ret_1d=returns[1],
            ret_5d=returns[5],
            ret_20d=returns[20],
            ret_60d=returns[60],
            trend_strength=trend_strength,
            trend_direction=trend_direction,
            fund_flow_5d=fund_flow,
        ))

    if not momentum_list:
        return [], RotationSignal(description="无行业数据")

    # 排名
    sorted_20d = sorted(momentum_list, key=lambda m: m.ret_20d, reverse=True)
    sorted_5d = sorted(momentum_list, key=lambda m: m.ret_5d, reverse=True)

    for rank, m in enumerate(sorted_20d, 1):
        m.rank_20d = rank
    for rank, m in enumerate(sorted_5d, 1):
        m.rank_5d = rank

    # 识别领涨/领跌行业
    n = len(momentum_list)
    leading = [m.industry_name for m in sorted_20d[:max(3, n // 5)]]

    # 识别转向行业（5日 vs 20日排名变化 ≥ 5）
    turning: list[str] = []
    fading: list[str] = []
    for m in momentum_list:
        rank_change = m.rank_20d - m.rank_5d
        if rank_change >= 5:
            turning.append(m.industry_name)  # 从弱转强
        elif rank_change <= -5:
            fading.append(m.industry_name)  # 从强转弱

    # 轮动模式
    momentum_history = [
        {"name": m.industry_name, "ret_20d": m.ret_20d, "ret_5d": m.ret_5d}
        for m in momentum_list
    ]
    pattern = detect_rotation_pattern(momentum_history)

    # 超配/低配
    overweight = [m.industry_name for m in sorted_20d[:max(3, n // 5)]]
    underweight = [m.industry_name for m in sorted_20d[-max(3, n // 5):]]

    desc_map = {
        "growth_rotation": "成长板块领涨，价值板块偏弱，建议超配科技/半导体",
        "defensive_rotation": "防御板块受青睐，市场风险偏好下降",
        "cyclical_rotation": "周期板块走强，经济复苏预期升温",
        "broad_up": "市场普涨，多数行业表现良好",
        "broad_down": "市场普跌，多数行业表现疲弱",
        "no_pattern": "行业轮动方向不明确，建议均衡配置",
    }

    rotation_signal = RotationSignal(
        leading_industries=leading,
        turning_industries=turning,
        fading_industries=fading,
        description=desc_map.get(pattern, "行业轮动分析"),
        overweight=overweight,
        underweight=underweight,
    )

    return momentum_list, rotation_signal


def detect_rotation_pattern(
    momentum_history: list[dict[str, Any]],
) -> str:
    """检测轮动模式.

    模式识别：
    - "growth_rotation": 从价值转向成长
    - "defensive_rotation": 从周期转向防御
    - "cyclical_rotation": 从防御转向周期
    - "broad_up": 普涨
    - "broad_down": 普跌
    - "no_pattern": 无明显模式

    Args:
        momentum_history: 各行业的历史动量数据.

    Returns:
        轮动模式标识.
    """
    if not momentum_history:
        return "no_pattern"

    ret_20d_list = [m.get("ret_20d", 0.0) for m in momentum_history]
    positive_20d = sum(1 for r in ret_20d_list if r > 0)
    n = len(ret_20d_list)

    if n == 0:
        return "no_pattern"

    # 80% 以上行业正收益 → 普涨
    if positive_20d / n >= 0.8:
        return "broad_up"

    # 80% 以上行业负收益 → 普跌
    if positive_20d / n <= 0.2:
        return "broad_down"

    # 成长板块 vs 防御板块
    growth_sectors = {"电子", "半导体", "计算机", "通信", "传媒", "新能源", "电力设备", "汽车"}
    defensive_sectors = {"医药生物", "医药", "食品饮料", "公用事业", "电力", "农林牧渔", "农业"}
    cyclical_sectors = {
        "有色金属", "有色", "钢铁", "化工", "煤炭", "石油石化",
        "房地产", "地产", "建筑材料", "非银金融", "证券", "银行",
    }

    growth_ret = _avg_ret_for_sectors(momentum_history, growth_sectors)
    defensive_ret = _avg_ret_for_sectors(momentum_history, defensive_sectors)
    cyclical_ret = _avg_ret_for_sectors(momentum_history, cyclical_sectors)

    if growth_ret > defensive_ret and growth_ret > cyclical_ret:
        return "growth_rotation"
    elif defensive_ret > growth_ret and defensive_ret > cyclical_ret:
        return "defensive_rotation"
    elif cyclical_ret > growth_ret and cyclical_ret > defensive_ret:
        return "cyclical_rotation"

    return "no_pattern"


def _avg_ret_for_sectors(
    momentum_history: list[dict[str, Any]],
    sector_names: set[str],
) -> float:
    """计算指定行业集的平均 20 日收益率.

    Args:
        momentum_history: 行业动量数据.
        sector_names: 行业名称集合.

    Returns:
        平均收益率（%）.
    """
    rets = [
        m.get("ret_20d", 0.0)
        for m in momentum_history
        if str(m.get("name", "")) in sector_names
    ]
    if not rets:
        return 0.0
    return float(np.mean(rets))


def calc_industry_adjustments(
    stock_pool: pd.DataFrame,
    momentum_list: list[IndustryMomentum],
) -> list[IndustryScoreAdjustment]:
    """为每只股票计算行业维度的评分调整.

    调整规则：
    - 行业 20 日动量排名前 10%：+5 ~ +10 分
    - 行业 20 日动量排名前 10%~30%：+2 ~ +5 分
    - 行业 20 日动量排名后 30%：0 ~ -5 分
    - 行业资金持续流入 + 动量向上：额外 +2 分
    - 行业资金持续流出 + 动量向下：额外 -2 分

    Args:
        stock_pool: 股票池.
        momentum_list: 行业动量列表.

    Returns:
        评分调整列表.
    """
    if momentum_list is None or len(momentum_list) == 0:
        return []

    n = len(momentum_list)
    adjustments: list[IndustryScoreAdjustment] = []

    # 构建行业名 → IndustryMomentum 映射
    mom_map: dict[str, IndustryMomentum] = {}
    for m in momentum_list:
        mom_map[m.industry_name] = m
        # 也添加简称匹配
        for alias in EXTENDED_INDUSTRY_ETF_MAP:
            if EXTENDED_INDUSTRY_ETF_MAP[alias] == m.etf_code:
                mom_map[alias] = m

    for _, row in stock_pool.iterrows():
        code = str(row.get("code", ""))
        industry = str(row.get("industry", "")) if "industry" in stock_pool.columns else ""
        name = str(row.get("name", ""))

        # 尝试匹配行业
        matched_momentum = _match_industry(industry, name, mom_map)
        if matched_momentum is None:
            # 无匹配，使用中性调整
            adjustments.append(IndustryScoreAdjustment(
                code=code,
                industry=industry,
                industry_alpha=0.5,
                adjustment=0.0,
                reason="无行业匹配数据",
            ))
            continue

        # 计算调整量
        rank_pct = (matched_momentum.rank_20d - 1) / n  # 0=最强, 1=最弱
        industry_alpha = 1.0 - rank_pct  # 1.0=最强

        if rank_pct < 0.1:
            # 前 10%: +5 ~ +10
            adjustment = 5.0 + (0.1 - rank_pct) / 0.1 * 5.0
        elif rank_pct < 0.3:
            # 前 10-30%: +2 ~ +5
            adjustment = 2.0 + (0.3 - rank_pct) / 0.2 * 3.0
        elif rank_pct > 0.7:
            # 后 30%: 0 ~ -5
            adjustment = -(rank_pct - 0.7) / 0.3 * 5.0
        else:
            # 中间: -1 ~ +1
            adjustment = 0.0

        # 资金流 + 动量调整
        if matched_momentum.fund_flow_5d > 0 and matched_momentum.trend_direction == "up":
            adjustment += 2.0
        elif matched_momentum.fund_flow_5d < 0 and matched_momentum.trend_direction == "down":
            adjustment -= 2.0

        # 裁剪到 [-10, +10]
        adjustment = float(np.clip(adjustment, -10.0, 10.0))

        adjustments.append(IndustryScoreAdjustment(
            code=code,
            industry=industry,
            industry_alpha=round(industry_alpha, 3),
            adjustment=round(adjustment, 1),
            reason=(
                f"行业 {matched_momentum.industry_name} 排名 {matched_momentum.rank_20d}/{n}"
                f", 20日收益 {matched_momentum.ret_20d:.1f}%"
            ),
        ))

    return adjustments


def _match_industry(
    industry: str,
    name: str,
    mom_map: dict[str, IndustryMomentum],
) -> IndustryMomentum | None:
    """匹配股票所属行业到动量数据.

    Args:
        industry: 行业字段.
        name: 股票名称.
        mom_map: 行业名 → 动量映射.

    Returns:
        匹配的 IndustryMomentum 或 None.
    """
    # 精确匹配
    if industry in mom_map:
        return mom_map[industry]

    # 模糊匹配：行业名包含关系
    for ind_name in mom_map:
        if ind_name in industry or industry in ind_name:
            return mom_map[ind_name]

    # 通过 EXTENDED_INDUSTRY_ETF_MAP 关键词匹配
    for map_name in EXTENDED_INDUSTRY_ETF_MAP:
        if (map_name in industry or map_name in name) and map_name in mom_map:
            return mom_map[map_name]

    return None
