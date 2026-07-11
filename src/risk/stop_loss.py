"""止损跟踪模块 — StopLossTracker.

跟踪已推荐信号的止损状态，在价格触及止损价时主动推送提醒。
支持移动止损（追踪止损）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class StopLossRecord:
    """止损跟踪记录."""

    code: str = ""
    name: str = ""
    entry_date: str = ""          # 推荐日期
    entry_price: float = 0.0      # 推荐时价格
    stop_loss_price: float = 0.0  # 止损价
    target_price: float = 0.0     # 目标价
    current_price: float = 0.0    # 当前价（每日更新）
    status: str = "active"        # "active", "stopped_out", "target_hit", "expired"
    days_held: int = 0            # 已持仓天数
    pnl_pct: float = 0.0          # 当前盈亏（%）
    hit_date: str | None = None   # 触发日期


@dataclass
class StopLossSummary:
    """止损汇总."""

    active_count: int = 0
    stopped_out_today: list[StopLossRecord] = field(default_factory=list)
    target_hit_today: list[StopLossRecord] = field(default_factory=list)
    near_stop_loss: list[StopLossRecord] = field(default_factory=list)  # 距离止损 < 3%
    avg_pnl: float = 0.0          # 平均盈亏（%）
    win_rate: float = 0.0         # 胜率（目标价先触发 vs 止损先触发）


def init_tracking(
    signals: list[object],
    today: str,
) -> list[StopLossRecord]:
    """为所有买入/卖出信号初始化止损跟踪记录.

    Args:
        signals: 交易信号列表.
        today: 今日日期.

    Returns:
        止损记录列表.
    """
    records: list[StopLossRecord] = []

    for sig in signals:
        action = str(getattr(sig, "action", "hold"))
        if action not in ("buy", "sell"):
            continue

        code = str(getattr(sig, "code", ""))
        name = str(getattr(sig, "name", ""))
        key_prices = getattr(sig, "key_prices", None)

        entry_price = getattr(key_prices, "current_price", 0.0) if key_prices else 0.0
        stop_loss = getattr(key_prices, "stop_loss", 0.0) if key_prices else 0.0
        target = getattr(key_prices, "target", 0.0) if key_prices else 0.0

        record = StopLossRecord(
            code=code,
            name=name,
            entry_date=today,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            target_price=target,
            current_price=entry_price,
            status="active",
            days_held=0,
            pnl_pct=0.0,
        )
        records.append(record)

    logger.info(f"止损跟踪初始化: {len(records)} 条记录")
    return records


def check_stop_losses(
    records: list[StopLossRecord],
    kline_cache: dict[str, pd.DataFrame],
    today: str,
) -> StopLossSummary:
    """检查所有活跃记录的止损状态.

    检查规则：
    - 当前价 <= 止损价 → status = "stopped_out"
    - 当前价 >= 目标价 → status = "target_hit"
    - 持仓超过30天 → status = "expired"
    - 当前价距止损 < 3% → 加入 near_stop_loss 预警

    Args:
        records: 所有止损记录.
        kline_cache: K线缓存（获取最新价格）.
        today: 今日日期.

    Returns:
        止损汇总.
    """
    summary = StopLossSummary()
    today_date = _parse_date(today)

    for record in records:
        if record.status != "active":
            continue

        # 更新当前价格
        kline = kline_cache.get(record.code, pd.DataFrame())
        current_price = _get_price(kline)
        if current_price > 0:
            record.current_price = current_price

        # 更新持仓天数
        entry_date = _parse_date(record.entry_date)
        if entry_date:
            record.days_held = (today_date - entry_date).days
        record.pnl_pct = (
            (record.current_price - record.entry_price) / record.entry_price * 100
            if record.entry_price > 0 else 0.0
        )

        # 检查止损/目标
        if record.current_price <= record.stop_loss_price and record.stop_loss_price > 0:
            record.status = "stopped_out"
            record.hit_date = today
            summary.stopped_out_today.append(record)
            logger.info(f"{record.code} {record.name} 触及止损 {record.stop_loss_price:.2f}")
            continue

        if record.current_price >= record.target_price and record.target_price > 0:
            record.status = "target_hit"
            record.hit_date = today
            summary.target_hit_today.append(record)
            logger.info(f"{record.code} {record.name} 触及目标 {record.target_price:.2f}")
            continue

        if record.days_held > 30:
            record.status = "expired"
            logger.info(f"{record.code} {record.name} 持仓超过30天，已过期")
            continue

        # 接近止损预警
        if record.stop_loss_price > 0:
            distance = (record.current_price - record.stop_loss_price) / record.stop_loss_price * 100
            if distance < 3.0:
                summary.near_stop_loss.append(record)

        summary.active_count += 1

    # 统计
    if records:
        active_records = [r for r in records if r.status == "active"]
        summary.avg_pnl = float(sum(r.pnl_pct for r in active_records) / max(len(active_records), 1))

    # 胜率
    targets = sum(1 for r in records if r.status == "target_hit")
    stops = sum(1 for r in records if r.status == "stopped_out")
    if targets + stops > 0:
        summary.win_rate = targets / (targets + stops)

    return summary


def update_stop_price(
    record: StopLossRecord,
    new_stop: float,
    reason: str,
) -> StopLossRecord:
    """移动止损：当价格上涨后，上移止损价锁定利润.

    移动规则（追踪止损）：
    - 盈利 > 10%：止损上移到 入场价（保本止损）
    - 盈利 > 20%：止损上移到 入场价 + 10%（锁定10%利润）
    - 盈利 > 30%：止损上移到 入场价 + 20%

    Args:
        record: 当前止损记录.
        new_stop: 新止损价.
        reason: 移动理由.

    Returns:
        更新后的止损记录.
    """
    old_stop = record.stop_loss_price
    record.stop_loss_price = new_stop
    logger.info(
        f"{record.code} 止损上移: {old_stop:.2f} → {new_stop:.2f} ({reason})"
    )
    return record


def generate_stop_loss_alert(summary: StopLossSummary) -> str:
    """生成止损提醒消息文本.

    Args:
        summary: 止损汇总.

    Returns:
        Markdown 格式提醒消息.
    """
    lines = ["## ⚠️ 止损提醒", ""]

    if summary.stopped_out_today:
        lines.append("### 🔴 今日止损触发")
        for r in summary.stopped_out_today:
            lines.append(
                f"- **{r.name}** ({r.code}): 入场 {r.entry_price:.2f}, "
                f"止损 {r.stop_loss_price:.2f}, 盈亏 {r.pnl_pct:.1f}%"
            )
        lines.append("")

    if summary.target_hit_today:
        lines.append("### 🟢 今日目标价触达")
        for r in summary.target_hit_today:
            lines.append(
                f"- **{r.name}** ({r.code}): 入场 {r.entry_price:.2f}, "
                f"目标 {r.target_price:.2f}, 盈利 {r.pnl_pct:.1f}%"
            )
        lines.append("")

    if summary.near_stop_loss:
        lines.append("### 🟡 接近止损预警（距止损 < 3%）")
        for r in summary.near_stop_loss:
            distance = (
                (r.current_price - r.stop_loss_price) / r.stop_loss_price * 100
                if r.stop_loss_price > 0 else 0
            )
            lines.append(
                f"- **{r.name}** ({r.code}): 当前 {r.current_price:.2f}, "
                f"止损 {r.stop_loss_price:.2f} (距离 {distance:.1f}%)"
            )
        lines.append("")

    lines.append(f"- 活跃持仓: {summary.active_count}")
    lines.append(f"- 平均盈亏: {summary.avg_pnl:.1f}%")
    lines.append(f"- 胜率: {summary.win_rate:.1%}")

    return "\n".join(lines)


def _parse_date(date_str: str) -> date:
    """解析日期字符串."""
    if not date_str:
        return datetime.now().date()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return datetime.now().date()


def _get_price(kline: pd.DataFrame) -> float:
    """获取最新价格."""
    if kline.empty:
        return 0.0
    close_col = "收盘" if "收盘" in kline.columns else "close"
    if close_col in kline.columns:
        return float(kline[close_col].iloc[-1])
    return 0.0
