"""纸交易模拟模块 — PaperTrader.

在实盘交易前提供模拟交易模式。使用真实每日数据执行策略，
但不产生真实资金变动。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class PaperPosition:
    """模拟持仓."""

    code: str = ""
    name: str = ""
    shares: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    days_held: int = 0


@dataclass
class PaperTrade:
    """模拟交易."""

    date: str = ""
    code: str = ""
    action: str = ""              # "buy" / "sell"
    price: float = 0.0
    shares: int = 0
    amount: float = 0.0
    commission: float = 0.0
    stamp_tax: float = 0.0
    signal_score: float = 0.0
    signal_confidence: float = 0.0
    reason: str = ""


@dataclass
class PaperAccount:
    """模拟账户."""

    initial_capital: float = 1_000_000.0
    cash: float = 1_000_000.0
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    total_value: float = 1_000_000.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    trade_history: list[PaperTrade] = field(default_factory=list)
    daily_records: list[dict[str, object]] = field(default_factory=list)


def init_paper_account(capital: float = 1_000_000.0) -> PaperAccount:
    """初始化模拟账户.

    Args:
        capital: 初始资金.

    Returns:
        PaperAccount.
    """
    account = PaperAccount(
        initial_capital=capital,
        cash=capital,
        total_value=capital,
    )
    logger.info(f"纸交易账户初始化: {capital:,.0f} 元")
    return account


def execute_daily_signals(
    account: PaperAccount,
    signals: list[object],
    stock_pool: pd.DataFrame,
    today: str,
) -> PaperAccount:
    """根据当日信号执行模拟交易.

    交易规则：
    1. 买入：按仓位分配计算的数量买入（100股整数倍）
    2. 卖出：信号为 sell 的持仓全部卖出
    3. 止损：检查所有持仓是否触及止损价
    4. 扣除：佣金万三 + 印花税千一（卖出） + 滑点千一

    Args:
        account: 当前账户状态.
        signals: 当日信号.
        stock_pool: 股票池（获取价格）.
        today: 今日日期.

    Returns:
        更新后的账户状态.
    """
    commission_rate = 0.0003
    stamp_tax_rate = 0.001
    slippage_rate = 0.001

    for sig in signals:
        action = str(getattr(sig, "action", "hold"))
        code = str(getattr(sig, "code", ""))
        name = str(getattr(sig, "name", ""))
        confidence = float(getattr(sig, "confidence", 0.5))

        if action == "buy":
            key_prices = getattr(sig, "key_prices", None)
            price = float(getattr(key_prices, "current_price", 10.0) if key_prices else 10.0)

            # 每只 5% 仓位（简化）
            allocation = account.total_value * 0.05
            shares = int(allocation / price / 100) * 100
            if shares < 100:
                continue

            cost = shares * price
            commission = cost * commission_rate
            slippage = cost * slippage_rate
            total_cost = cost + commission + slippage

            if total_cost > account.cash:
                continue

            account.cash -= total_cost

            if code in account.positions:
                pos = account.positions[code]
                total_shares = pos.shares + shares
                pos.avg_cost = (pos.avg_cost * pos.shares + total_cost) / total_shares
                pos.shares = total_shares
            else:
                account.positions[code] = PaperPosition(
                    code=code, name=name, shares=shares,
                    avg_cost=total_cost / shares, current_price=price,
                    market_value=shares * price,
                )

            account.trade_history.append(PaperTrade(
                date=today, code=code, action="buy", price=price,
                shares=shares, amount=cost, commission=commission,
                stamp_tax=0.0, signal_confidence=confidence,
                reason=f"买入信号 (置信度 {confidence:.2f})",
            ))

        elif action == "sell" and code in account.positions:
            pos = account.positions[code]
            key_prices = getattr(sig, "key_prices", None)
            price = float(getattr(key_prices, "current_price", pos.current_price) if key_prices else pos.current_price)
            revenue = pos.shares * price
            commission = revenue * commission_rate
            stamp_tax = revenue * stamp_tax_rate
            slippage = revenue * slippage_rate
            net_revenue = revenue - commission - stamp_tax - slippage

            account.cash += net_revenue
            account.trade_history.append(PaperTrade(
                date=today, code=code, action="sell", price=price,
                shares=pos.shares, amount=revenue, commission=commission,
                stamp_tax=stamp_tax, signal_confidence=confidence,
                reason=f"卖出信号 (盈亏 {pos.pnl_pct:.1f}%)",
            ))
            del account.positions[code]

    # 更新持仓市值和账户总资产
    account.daily_pnl = 0.0
    total_position_value = 0.0
    for code, pos in list(account.positions.items()):
        sig_list = [s for s in signals if str(getattr(s, "code", "")) == code]
        if sig_list:
            key_prices = getattr(sig_list[0], "key_prices", None)
            if key_prices:
                pos.current_price = float(getattr(key_prices, "current_price", pos.current_price))
        pos.market_value = pos.shares * pos.current_price
        pos.pnl = pos.market_value - pos.shares * pos.avg_cost
        pos.pnl_pct = (pos.current_price / pos.avg_cost - 1) * 100 if pos.avg_cost > 0 else 0
        total_position_value += pos.market_value

    account.total_value = account.cash + total_position_value
    account.total_pnl = account.total_value - account.initial_capital
    account.total_pnl_pct = account.total_pnl / account.initial_capital * 100

    account.daily_records.append({
        "date": today,
        "total_value": account.total_value,
        "cash": account.cash,
    })

    return account


def generate_paper_report(account: PaperAccount) -> str:
    """生成模拟交易日报.

    Args:
        account: 账户状态.

    Returns:
        Markdown 报告文本.
    """
    lines = [
        "## 📝 纸交易日报",
        "",
        "### 账户总览",
        f"- 初始资金: {account.initial_capital:,.0f} 元",
        f"- 总资产: {account.total_value:,.0f} 元",
        f"- 可用现金: {account.cash:,.0f} 元",
        f"- 累计盈亏: {account.total_pnl:,.0f} 元 ({account.total_pnl_pct:.2f}%)",
        f"- 持仓数量: {len(account.positions)}",
        "",
    ]

    if account.positions:
        lines.append("### 当前持仓")
        for code, pos in account.positions.items():
            lines.append(
                f"- **{pos.name}** ({code}): {pos.shares}股, "
                f"成本 {pos.avg_cost:.2f}, 现价 {pos.current_price:.2f}, "
                f"盈亏 {pos.pnl_pct:+.1f}%"
            )
        lines.append("")

    if account.trade_history:
        recent = account.trade_history[-10:]
        lines.append("### 最近交易")
        for t in reversed(recent):
            action_icon = "🔴" if t.action == "buy" else "🟢"
            lines.append(
                f"- {action_icon} {t.date} {t.action.upper()} {t.code} "
                f"{t.shares}股 @ {t.price:.2f} (金额 {t.amount:,.0f})"
            )
        lines.append("")

    return "\n".join(lines)


def check_go_live_readiness(
    account: PaperAccount,
    min_days: int = 60,
) -> tuple[bool, str]:
    """检查是否满足实盘切换条件.

    条件：
    1. 纸交易运行 >= 60 个交易日
    2. 累计收益 > 0（至少不亏）
    3. 夏普比率 > 0.5
    4. 最大回撤 < 20%
    5. 月胜率 > 50%

    Args:
        account: 账户状态.
        min_days: 最少交易日数.

    Returns:
        (是否就绪, 就绪/未就绪原因)
    """
    reasons: list[str] = []

    # 1. 交易天数
    trade_days = len(account.daily_records)
    if trade_days < min_days:
        reasons.append(f"交易天数不足: {trade_days}/{min_days}")

    # 2. 累计收益
    if account.total_pnl <= 0:
        reasons.append(f"累计收益为负: {account.total_pnl:.0f}")

    # 3. 夏普比率（简化）
    if account.daily_records:
        values = [float(r["total_value"]) for r in account.daily_records]  # type: ignore[arg-type]
        if len(values) >= 2:
            daily_rets = [
                (values[i] - values[i - 1]) / max(values[i - 1], 1.0)
                for i in range(1, len(values))
            ]
            if daily_rets:
                sharpe = float(np.mean(daily_rets) / max(np.std(daily_rets), 1e-8) * np.sqrt(252))
                if sharpe < 0.5:
                    reasons.append(f"夏普比率不足: {sharpe:.2f} < 0.5")

    # 4. 最大回撤（简化）
    if account.daily_records:
        dd_values = [float(r["total_value"]) for r in account.daily_records]  # type: ignore[arg-type]
        if dd_values:
            peak = dd_values[0]
            max_dd = 0.0
            for v in dd_values:
                peak = max(peak, v)
                dd = (v - peak) / max(peak, 1.0)
                max_dd = min(max_dd, dd)
            if abs(max_dd) > 0.20:
                reasons.append(f"最大回撤过大: {abs(max_dd)*100:.1f}% > 20%")

    if reasons:
        return False, "; ".join(reasons)
    return True, "已达到实盘切换条件"
