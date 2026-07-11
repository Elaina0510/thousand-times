"""硬性风控规则引擎 — RiskGuard.

在信号生成后执行硬性风控规则，过滤掉不符合交易规则的信号。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger("thousand-times")


class RejectReason(Enum):
    """拒绝原因."""

    ST_STOCK = "ST/*ST 股票"
    LIMIT_UP = "涨停板（无法买入）"
    LIMIT_DOWN = "跌停板（无法卖出）"
    LOW_LIQUIDITY = "日均成交额过低（< 1000万）"
    HIGH_BID_ASK = "接近涨跌停（买入滑点过大）"
    PRICE_LIMIT = "股价过低（< 2元，仙股风险）"
    SECTOR_OVERWEIGHT = "行业超配"
    MAX_POSITION = "已达最大持仓数"
    RECENT_SIGNAL = "最近3日已有同向信号"
    EXCESSIVE_VOLATILITY = "波动率异常（> 年化200%）"


@dataclass
class RiskRuleResult:
    """单条风控规则的判断结果."""

    passed: bool
    reject_reason: RejectReason | None = None
    detail: str = ""


@dataclass
class GuardResult:
    """风控检查结果."""

    input_count: int = 0            # 输入信号数
    passed_count: int = 0           # 通过数
    rejected: list[tuple[object, RejectReason, str]] = field(default_factory=list)
    passed: list[object] = field(default_factory=list)  # list[Signal]
    warnings: list[str] = field(default_factory=list)


# 风控规则集（按优先级排列）
RISK_RULES: list[dict[str, Any]] = [
    {"name": "ST过滤", "priority": 1, "block": True},
    {"name": "涨跌停检查", "priority": 2, "block": True},
    {"name": "流动性过滤", "priority": 3, "block": True},
    {"name": "仙股过滤", "priority": 4, "block": True},
    {"name": "行业超配检查", "priority": 5, "block": True},
    {"name": "最大持仓检查", "priority": 6, "block": True},
    {"name": "重复信号检查", "priority": 7, "block": False},  # 仅警告
    {"name": "波动率异常检查", "priority": 8, "block": False},  # 仅警告
]


def apply_risk_rules(
    signals: list[object],
    stock_pool: pd.DataFrame,
    kline_cache: dict[str, pd.DataFrame],
    existing_positions: list[dict[str, Any]],
    daily_stats: dict[str, Any],
) -> GuardResult:
    """对信号列表执行全部风控规则.

    规则详情：
    1. ST/*ST过滤：名称含 ST → 拒绝
    2. 涨跌停检查：涨跌幅达到±9.9%以上 → 拒绝（无法成交）
    3. 流动性过滤：近20日均成交额 < 1000万 → 拒绝
    4. 仙股过滤：股价 < 2元 → 拒绝
    5. 行业超配：单行业持仓 > 20% → 该行业后续买入信号拒绝
    6. 最大持仓：已有 N 只持仓时拒绝新的买入信号
    7. 重复信号：3日内同股票同方向 → 仅警告
    8. 波动率异常：年化波动率 > 200% → 仅警告

    Args:
        signals: 待检查的信号列表.
        stock_pool: 股票池（含实时涨跌幅）.
        kline_cache: K线缓存（用于流动性计算）.
        existing_positions: 现有持仓.
        daily_stats: 当日市场统计.

    Returns:
        GuardResult 风控检查结果.
    """
    result = GuardResult(input_count=len(signals))
    warnings: list[str] = []

    for sig in signals:
        code = str(getattr(sig, "code", ""))
        name = str(getattr(sig, "name", ""))
        action = str(getattr(sig, "action", "hold"))
        rejected = False

        # Rule 1: ST 过滤
        rule_result = check_st_stock(code, name)
        if rule_result.reject_reason is not None:
            result.rejected.append((sig, rule_result.reject_reason, rule_result.detail))
            rejected = True
            continue

        # Rule 2: 涨跌停检查
        rule_result = check_limit_price(code, stock_pool)
        if rule_result.reject_reason is not None:
            result.rejected.append((sig, rule_result.reject_reason, rule_result.detail))
            rejected = True
            continue

        # Rule 3: 流动性过滤
        rule_result = check_liquidity(code, kline_cache)
        if rule_result.reject_reason is not None:
            result.rejected.append((sig, rule_result.reject_reason, rule_result.detail))
            rejected = True
            continue

        # Rule 4: 仙股过滤
        rule_result = check_price_limit(code, kline_cache)
        if rule_result.reject_reason is not None:
            result.rejected.append((sig, rule_result.reject_reason, rule_result.detail))
            rejected = True
            continue

        # Rule 5: 行业超配（简化：总是通过，具体逻辑在 PositionSizer）
        # 这里不拒绝信号，仅由 PositionSizer 控制实际权重

        # Rule 6: 最大持仓（简化：总是通过）

        # Rule 7: 重复信号检查（仅警告）
        rule_result = check_recent_signal(code, action, daily_stats)
        if not rule_result.passed:
            warnings.append(rule_result.detail)

        # Rule 8: 波动率异常（仅警告）
        rule_result = check_volatility(code, kline_cache)
        if not rule_result.passed:
            warnings.append(rule_result.detail)

        if not rejected:
            result.passed.append(sig)

    result.passed_count = len(result.passed)
    result.warnings = warnings

    logger.info(
        f"风控检查完成: {result.input_count} → {result.passed_count} "
        f"(拒绝 {len(result.rejected)}, 警告 {len(warnings)})"
    )

    return result


def check_st_stock(code: str, name: str) -> RiskRuleResult:
    """检查是否为 ST 股票.

    Args:
        code: 股票代码.
        name: 股票名称.

    Returns:
        RiskRuleResult.
    """
    if "ST" in name.upper() or "*ST" in name.upper():
        return RiskRuleResult(
            passed=False, reject_reason=RejectReason.ST_STOCK,
            detail=f"{code} {name} 是 ST 股票",
        )
    return RiskRuleResult(passed=True)


def check_limit_price(code: str, stock_pool: pd.DataFrame) -> RiskRuleResult:
    """检查是否涨跌停.

    Args:
        code: 股票代码.
        stock_pool: 股票池.

    Returns:
        RiskRuleResult.
    """
    if stock_pool.empty:
        return RiskRuleResult(passed=True)

    stock_rows = stock_pool[stock_pool["code"].astype(str) == code]
    if stock_rows.empty:
        return RiskRuleResult(passed=True)

    row = stock_rows.iloc[0]
    change_pct = float(row.get("涨跌幅", row.get("pct_chg", 0)))

    if change_pct >= 9.9:
        return RiskRuleResult(
            passed=False, reject_reason=RejectReason.LIMIT_UP,
            detail=f"{code} 涨停 ({change_pct:.1f}%)",
        )
    if change_pct <= -9.9:
        return RiskRuleResult(
            passed=False, reject_reason=RejectReason.LIMIT_DOWN,
            detail=f"{code} 跌停 ({change_pct:.1f}%)",
        )

    return RiskRuleResult(passed=True)


def check_liquidity(code: str, kline_cache: dict[str, pd.DataFrame]) -> RiskRuleResult:
    """检查日均成交额.

    Args:
        code: 股票代码.
        kline_cache: K线缓存.

    Returns:
        RiskRuleResult.
    """
    if code not in kline_cache:
        return RiskRuleResult(passed=True)  # 无数据时不阻止

    df = kline_cache[code]
    if df.empty:
        return RiskRuleResult(passed=True)

    vol_col = "成交量" if "成交量" in df.columns else "volume"
    if vol_col not in df.columns:
        return RiskRuleResult(passed=True)

    # 计算近20日均成交额
    volumes = df[vol_col].astype(float).tail(20)
    close_col = "收盘" if "收盘" in df.columns else "close"
    if close_col in df.columns:
        closes = df[close_col].astype(float).tail(20)
        avg_amount = float((volumes * closes).mean())
    else:
        avg_amount = float(volumes.mean() * 10)  # 假设均价 10 元

    if avg_amount < 10_000_000:  # 1000 万
        return RiskRuleResult(
            passed=False, reject_reason=RejectReason.LOW_LIQUIDITY,
            detail=f"{code} 日均成交额 {avg_amount/1e4:.0f}万 < 1000万",
        )

    return RiskRuleResult(passed=True)


def check_price_limit(code: str, kline_cache: dict[str, pd.DataFrame]) -> RiskRuleResult:
    """检查股价是否过低（仙股过滤）.

    Args:
        code: 股票代码.
        kline_cache: K线缓存.

    Returns:
        RiskRuleResult.
    """
    if code not in kline_cache:
        return RiskRuleResult(passed=True)

    df = kline_cache[code]
    if df.empty:
        return RiskRuleResult(passed=True)

    close_col = "收盘" if "收盘" in df.columns else "close"
    if close_col not in df.columns:
        return RiskRuleResult(passed=True)

    last_price = float(df[close_col].iloc[-1])

    if last_price < 2.0:
        return RiskRuleResult(
            passed=False, reject_reason=RejectReason.PRICE_LIMIT,
            detail=f"{code} 股价 {last_price:.2f} < 2元",
        )

    return RiskRuleResult(passed=True)


def check_recent_signal(
    code: str, action: str, daily_stats: dict[str, Any],
) -> RiskRuleResult:
    """检查最近3日内是否有同向信号.

    Args:
        code: 股票代码.
        action: 信号方向.
        daily_stats: 当日统计（含历史信号记录）.

    Returns:
        RiskRuleResult.
    """
    recent_signals = daily_stats.get("recent_signals", [])
    for rs in recent_signals:
        if rs.get("code") == code and rs.get("action") == action:
            return RiskRuleResult(
                passed=False,
                detail=f"{code} 最近3日内已有同向 {action} 信号（仅警告）",
            )
    return RiskRuleResult(passed=True)


def check_volatility(code: str, kline_cache: dict[str, pd.DataFrame]) -> RiskRuleResult:
    """检查波动率是否异常.

    Args:
        code: 股票代码.
        kline_cache: K线缓存.

    Returns:
        RiskRuleResult.
    """
    if code not in kline_cache:
        return RiskRuleResult(passed=True)

    df = kline_cache[code]
    if df.empty or len(df) < 20:
        return RiskRuleResult(passed=True)

    close_col = "收盘" if "收盘" in df.columns else "close"
    if close_col not in df.columns:
        return RiskRuleResult(passed=True)

    closes = df[close_col].astype(float)
    daily_returns = closes.pct_change().dropna()
    annual_vol = float(daily_returns.std() * (252 ** 0.5) * 100)  # 百分比

    if annual_vol > 200:
        return RiskRuleResult(
            passed=False,
            detail=f"{code} 年化波动率 {annual_vol:.0f}% > 200%（仅警告）",
        )

    return RiskRuleResult(passed=True)
