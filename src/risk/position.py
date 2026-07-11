"""仓位计算与组合优化 — PositionSizer.

根据信号置信度、波动率和组合约束，
为每个买入信号计算建议仓位大小。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class PositionAllocation:
    """单只股票的仓位分配."""

    code: str = ""
    name: str = ""
    signal_confidence: float = 0.0   # 信号置信度 (0~1)
    volatility_pct: float = 0.0      # 年化波动率（%）
    base_weight: float = 0.0         # 基础权重（%）
    adjusted_weight: float = 0.0     # 调整后权重（%）
    shares: int = 0                  # 建议股数（100股整数倍）
    capital: float = 0.0             # 建议投入资金（元）
    max_loss: float = 0.0            # 最大亏损金额（止损触发时）
    reason: str = ""                 # 仓位计算理由


@dataclass
class PortfolioSummary:
    """组合汇总."""

    total_capital: float = 0.0       # 总资金
    allocated_capital: float = 0.0   # 已分配资金
    cash_reserve: float = 0.0        # 现金储备
    position_count: int = 0          # 持仓数量
    sector_exposure: dict[str, float] = field(default_factory=dict)  # 行业暴露
    risk_contribution: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def calc_volatility(kline: pd.DataFrame, annualize: bool = True) -> float:
    """计算年化波动率.

    Args:
        kline: K线数据.
        annualize: 是否年化.

    Returns:
        波动率（%）.
    """
    if kline.empty or len(kline) < 5:
        return 30.0  # 默认波动率

    close_col = "收盘" if "收盘" in kline.columns else "close"
    if close_col not in kline.columns:
        return 30.0

    daily_returns = kline[close_col].astype(float).pct_change().dropna()
    daily_vol = float(float(daily_returns.std()) * 100)  # 百分比

    if annualize:
        return float(daily_vol * (252 ** 0.5))

    return float(daily_vol)


def check_sector_limits(
    allocations: list[PositionAllocation],
    industry_map: dict[str, str],
    max_sector_pct: float = 0.20,
) -> list[str]:
    """检查行业集中度是否超限.

    Args:
        allocations: 仓位分配列表.
        industry_map: code → industry 映射.
        max_sector_pct: 单行业最大比例.

    Returns:
        警告列表.
    """
    warnings: list[str] = []
    sector_weights: dict[str, float] = {}

    for alloc in allocations:
        industry = industry_map.get(alloc.code, "未知")
        sector_weights[industry] = sector_weights.get(industry, 0.0) + alloc.adjusted_weight / 100

    for industry, weight in sector_weights.items():
        if weight > max_sector_pct:
            warnings.append(f"行业 {industry} 持仓 {weight:.1%} 超过上限 {max_sector_pct:.0%}")

    return warnings


def assign_positions(
    buy_signals: list[object],
    stock_pool: pd.DataFrame,
    total_capital: float,
    regime: object,
    kline_cache: dict[str, pd.DataFrame],
    config: object | None = None,
) -> tuple[list[PositionAllocation], PortfolioSummary]:
    """为买入信号分配仓位.

    分配算法（Kelly启发式 + 波动率调整）：
    1. 基础权重 = 信号置信度 / sum(所有信号置信度)
    2. 波动率惩罚：高波动股票降低权重
       adj_weight = base_weight / (volatility / median_volatility)
    3. 市场环境调整：牛市乘1.2，熊市乘0.4
    4. 单只上限：不超过总资金的 10%
    5. 单行业上限：不超过总资金的 20%
    6. 总仓位上限：牛市80%，震荡60%，熊市30%
    7. 向下取整到100股（A股1手=100股）

    Args:
        buy_signals: 买入信号列表.
        stock_pool: 股票池.
        total_capital: 总资金.
        regime: 市场环境 (MarketRegime).
        kline_cache: K线缓存.
        config: 配置.

    Returns:
        (仓位分配列表, 组合汇总)
    """
    allocations: list[PositionAllocation] = []
    summary = PortfolioSummary(total_capital=total_capital)

    if not buy_signals:
        summary.cash_reserve = total_capital
        return allocations, summary

    regime_state = str(getattr(regime, "state", "sideways"))
    regime_multipliers: dict[str, float] = {
        "bull": 1.2, "sideways": 0.8, "bear": 0.4,
    }
    position_caps: dict[str, float] = {
        "bull": 0.80, "sideways": 0.60, "bear": 0.30,
    }

    regime_mult = regime_multipliers.get(regime_state, 0.8)
    max_total_pct = position_caps.get(regime_state, 0.60)

    # Step 1: 计算波动率
    vols: dict[str, float] = {}
    for sig in buy_signals:
        code = str(getattr(sig, "code", ""))
        kline = kline_cache.get(code, pd.DataFrame())
        vols[code] = calc_volatility(kline)

    median_vol = float(np.median(list(vols.values()))) if vols else 30.0
    if median_vol < 0.01:
        median_vol = 30.0

    # Step 2: 计算基础权重
    confidences = [float(getattr(s, "confidence", 0.5)) for s in buy_signals]
    total_conf = sum(confidences)
    if total_conf == 0:
        total_conf = len(buy_signals)

    # Step 3: 逐个分配
    for i, sig in enumerate(buy_signals):
        code = str(getattr(sig, "code", ""))
        name = str(getattr(sig, "name", ""))
        confidence = confidences[i]
        vol = vols.get(code, 30.0)

        # 基础权重
        base_weight = (confidence / total_conf) * 100  # 百分比

        # 波动率惩罚
        vol_penalty = median_vol / max(vol, 0.01)
        risk_adj_weight = base_weight * vol_penalty

        # 市场环境调整
        env_adj_weight = risk_adj_weight * regime_mult

        # 硬上限裁剪
        adjusted_weight = min(env_adj_weight, 10.0)  # 单只 ≤ 10%

        # 价格
        kline = kline_cache.get(code, pd.DataFrame())
        price = _get_latest_price(kline)

        # 换算股数
        shares = int(adjusted_weight / 100 * total_capital / max(price, 0.01) / 100) * 100
        capital = shares * price

        # 最大亏损
        key_prices = getattr(sig, "key_prices", None)
        stop_loss = getattr(key_prices, "stop_loss", 0.0) if key_prices else 0.0
        max_loss = (price - stop_loss) * shares if stop_loss > 0 else capital * 0.1

        reason_parts = [
            f"置信度={confidence:.2f}",
            f"波动率={vol:.1f}%",
            f"基础权重={base_weight:.1f}%",
            f"调整后={adjusted_weight:.1f}%",
        ]
        reason = ", ".join(reason_parts)

        allocations.append(PositionAllocation(
            code=code,
            name=name,
            signal_confidence=confidence,
            volatility_pct=round(vol, 1),
            base_weight=round(base_weight, 2),
            adjusted_weight=round(adjusted_weight, 2),
            shares=shares,
            capital=round(capital, 2),
            max_loss=round(max_loss, 2),
            reason=reason,
        ))

    # Step 4: 总仓位裁剪
    total_weight = sum(a.adjusted_weight for a in allocations) / 100
    if total_weight > max_total_pct:
        scale = max_total_pct / total_weight
        for a in allocations:
            a.adjusted_weight = round(a.adjusted_weight * scale, 2)
            a.shares = int(a.adjusted_weight / 100 * total_capital / max(
                _get_latest_price(kline_cache.get(a.code, pd.DataFrame())), 0.01
            ) / 100) * 100
            a.capital = round(a.shares * _get_latest_price(kline_cache.get(a.code, pd.DataFrame())), 2)

    # Step 5: 汇总
    allocated = sum(a.capital for a in allocations)
    summary.allocated_capital = round(allocated, 2)
    summary.cash_reserve = round(total_capital - allocated, 2)
    summary.position_count = len(allocations)

    # 行业暴露
    if "industry" in stock_pool.columns:
        industry_map: dict[str, str] = {}
        for _, row in stock_pool.iterrows():
            code = str(row.get("code", ""))
            industry_map[code] = str(row.get("industry", ""))
        summary.sector_exposure = _calc_sector_exposure(allocations, industry_map)

    logger.info(
        f"仓位分配完成: {len(allocations)} 只, "
        f"分配 {allocated:.0f}/{total_capital:.0f} "
        f"({allocated/total_capital*100:.1f}%)"
    )

    return allocations, summary


def _get_latest_price(kline: pd.DataFrame) -> float:
    """获取最新价格."""
    if kline.empty:
        return 10.0  # 默认价格
    close_col = "收盘" if "收盘" in kline.columns else "close"
    if close_col in kline.columns:
        return float(kline[close_col].iloc[-1])
    return 10.0


def _calc_sector_exposure(
    allocations: list[PositionAllocation],
    industry_map: dict[str, str],
) -> dict[str, float]:
    """计算行业暴露."""
    exposure: dict[str, float] = {}
    total = sum(a.capital for a in allocations)
    if total == 0:
        return exposure

    for a in allocations:
        industry = industry_map.get(a.code, "未知")
        exposure[industry] = exposure.get(industry, 0.0) + a.capital / total

    return {k: round(v, 3) for k, v in exposure.items()}
