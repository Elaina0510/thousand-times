"""输出模块 — 生成报告。"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def stage_output(signals: list, regime: object, data: object, config: object) -> str:
    """阶段5: 生成报告.

    Args:
        signals: Signal 列表。
        regime: MarketRegime。
        data: DataBundle。
        config: AppConfig。

    Returns:
        报告文本。
    """
    lines: list[str] = []
    lines.append("# A股智能选股分析报告\n")

    # 市场环境
    state = getattr(regime, "state", "unknown")
    desc = getattr(regime, "description", "未知")
    lines.append(f"## 市场环境: {desc}\n")

    # 买入信号
    buy_signals = [s for s in signals if getattr(s, "action", "") == "buy"]
    if buy_signals:
        lines.append(f"## 买入信号 ({len(buy_signals)} 只)\n")
        for s in buy_signals[:10]:
            lines.append(f"- **{s.name}** ({s.code}): 置信度 {s.confidence:.0%}")
    else:
        lines.append("## 买入信号: 无\n")

    # 卖出信号
    sell_signals = [s for s in signals if getattr(s, "action", "") == "sell"]
    if sell_signals:
        lines.append(f"\n## 卖出信号 ({len(sell_signals)} 只)\n")
        for s in sell_signals[:10]:
            lines.append(f"- **{s.name}** ({s.code}): 置信度 {s.confidence:.0%}")
    else:
        lines.append("\n## 卖出信号: 无\n")

    return "\n".join(lines)
