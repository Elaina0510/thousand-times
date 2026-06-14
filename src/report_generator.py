"""报告生成模块 — 组装推送文本内容。"""

from __future__ import annotations

from buy_sell_signal import BuySellSignal
from news_analysis import PolicyImpact
from scoring import ScoreResult


def _find_signal(
    code: str, signals: list[BuySellSignal]
) -> BuySellSignal | None:
    """在信号列表中查找指定代码的信号。"""
    for s in signals:
        if s.code == code:
            return s
    return None


def _direction_label(direction: str) -> str:
    """将影响方向转换为中文标签。"""
    if direction == "positive":
        return "利好"
    if direction == "negative":
        return "利空"
    return "中性"


def _append_impact_line(
    sections: list[str], index: int, impact: PolicyImpact
) -> None:
    """将单条政策影响追加到报告中。"""
    direction = _direction_label(impact.impact_direction)
    industries = (
        "、".join(impact.affected_industries)
        if impact.affected_industries
        else "整体市场"
    )
    line = f"{index}. {impact.news_title} → {direction}{industries}"
    if impact.news_url:
        line += f" [详情]({impact.news_url})"
    sections.append(line)


def _format_stock_item(
    result: ScoreResult,
    index: int,
    signal: BuySellSignal | None = None,
) -> str:
    """格式化单只个股的输出。

    Args:
        result: 评分结果。
        index: 序号。
        signal: 买卖信号（可选）。

    Returns:
        格式化的文本。
    """
    tech_signals = []
    if result.technical_signals.ma5_10_golden:
        tech_signals.append("MA5/10金叉")
    if result.technical_signals.ma20_60_golden:
        tech_signals.append("MA20/60金叉")
    if result.technical_signals.bullish_alignment:
        tech_signals.append("多头排列")
    if result.technical_signals.macd_golden:
        tech_signals.append("MACD金叉")
    if result.technical_signals.macd_above_zero:
        tech_signals.append("零轴上方金叉")
    if result.technical_signals.macd_divergence:
        tech_signals.append("MACD底背离")
    if result.technical_signals.volume_up:
        tech_signals.append("放量上涨")
    if result.technical_signals.pullback_ok:
        tech_signals.append("缩量回调到位")
    if result.technical_signals.ma5_10_death:
        tech_signals.append("MA5/10死叉")
    if result.technical_signals.macd_death:
        tech_signals.append("MACD死叉")
    if result.technical_signals.volume_peak:
        tech_signals.append("天量见天价")
    if result.technical_signals.volume_down:
        tech_signals.append("放量下跌")

    tech_str = "，".join(tech_signals) if tech_signals else "无明显信号"
    fund_str = f"评分{result.fundamental_score:.0f}分" if result.fundamental_score is not None else "无数据"
    news_str = result.news_summary if result.news_summary else "无政策影响"

    lines = [
        f"【{index}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分",
        f"├ 技术信号：{tech_str}",
        f"├ 基本面：{fund_str}",
        f"├ 政策影响：{news_str}",
        f"├ 盈利概率：约 {result.profit_probability:.0f}%",
    ]

    # 买卖信号信息
    if signal:
        lines.append(f"├ 信号区间：{signal.signal_emoji} {signal.signal_zone}（{signal.signal_score}分）")
        kp = signal.key_prices
        lines.append(
            f"├ 关键价位：支撑 {kp.support_price} / 压力 {kp.resistance_price}"
            f" / 目标 {kp.target_price} / 止损 {kp.stop_loss}"
        )
        # 板块对比
        if signal.sector_comparison:
            sc = signal.sector_comparison
            lines.append(
                f"├ 板块对比：{sc.sector_name} 第{sc.rank_in_sector}/{sc.total_in_sector}"
                f"（超过{sc.percentile:.0f}%同行）"
            )
            if sc.vs_etf_return != 0:
                direction = "跑赢" if sc.vs_etf_return > 0 else "跑输"
                lines.append(f"├ vs板块ETF：{direction} {abs(sc.vs_etf_return):.1f}%")

    lines.append(f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/")
    lines.append("[附K线图 + MACD图]")

    return "\n".join(lines)


def _format_etf_item(
    result: ScoreResult,
    index: int,
    signal: BuySellSignal | None = None,
) -> str:
    """格式化单只ETF的输出。

    Args:
        result: 评分结果。
        index: 序号。
        signal: 买卖信号（可选）。

    Returns:
        格式化的文本。
    """
    tech_signals = []
    if result.technical_signals.ma5_10_golden:
        tech_signals.append("MA5/10金叉")
    if result.technical_signals.ma20_60_golden:
        tech_signals.append("MA20/60金叉")
    if result.technical_signals.bullish_alignment:
        tech_signals.append("多头排列")
    if result.technical_signals.macd_golden:
        tech_signals.append("MACD金叉")
    if result.technical_signals.macd_above_zero:
        tech_signals.append("零轴上方金叉")
    if result.technical_signals.macd_divergence:
        tech_signals.append("MACD底背离")
    if result.technical_signals.volume_up:
        tech_signals.append("放量上涨")
    if result.technical_signals.pullback_ok:
        tech_signals.append("缩量回调到位")
    if result.technical_signals.ma5_10_death:
        tech_signals.append("MA5/10死叉")
    if result.technical_signals.macd_death:
        tech_signals.append("MACD死叉")
    if result.technical_signals.volume_peak:
        tech_signals.append("天量见天价")
    if result.technical_signals.volume_down:
        tech_signals.append("放量下跌")

    tech_str = "，".join(tech_signals) if tech_signals else "无明显信号"
    news_str = result.news_summary if result.news_summary else "无政策影响"

    # 资金流向描述
    if result.fund_flow_score is not None:
        if result.fund_flow_score >= 8:
            flow_str = "近5日份额持续增长"
        elif result.fund_flow_score >= 4:
            flow_str = "近5日份额小幅增长"
        elif result.fund_flow_score >= 3:
            flow_str = "近5日份额基本持平"
        else:
            flow_str = "近5日份额持续减少"
    else:
        flow_str = "无数据"

    lines = [
        f"【{index}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分",
        f"├ 技术信号：{tech_str}",
        f"├ 政策影响：{news_str}",
        f"├ 资金流向：{flow_str}",
        f"├ 盈利概率：约 {result.profit_probability:.0f}%",
    ]

    # 买卖信号信息
    if signal:
        lines.append(f"├ 信号区间：{signal.signal_emoji} {signal.signal_zone}（{signal.signal_score}分）")
        kp = signal.key_prices
        lines.append(
            f"├ 关键价位：支撑 {kp.support_price} / 压力 {kp.resistance_price}"
            f" / 目标 {kp.target_price} / 止损 {kp.stop_loss}"
        )
        # 板块对比
        if signal.sector_comparison:
            sc = signal.sector_comparison
            lines.append(
                f"├ 板块对比：{sc.sector_name} 第{sc.rank_in_sector}/{sc.total_in_sector}"
                f"（超过{sc.percentile:.0f}%同行）"
            )
            if sc.vs_etf_return != 0:
                direction = "跑赢" if sc.vs_etf_return > 0 else "跑输"
                lines.append(f"├ vs板块ETF：{direction} {abs(sc.vs_etf_return):.1f}%")

    lines.append(f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/")
    lines.append("[附K线图 + MACD图]")

    return "\n".join(lines)


def generate_report(
    stock_results: list[ScoreResult],
    etf_results: list[ScoreResult],
    policy_impacts: list[PolicyImpact],
    report_date: str,
    stock_signals: list[BuySellSignal] | None = None,
    etf_signals: list[BuySellSignal] | None = None,
    max_recommend: int = 10,
    max_risk: int = 5,
    score_threshold_high: float = 70.0,
    score_threshold_low: float = 30.0,
) -> str:
    """生成推送报告文本。

    使用三档划分展示所有结果：
    - 买入区（≥70分）：推荐关注
    - 观望区（30-69分）：观望等待
    - 卖出区（<30分）：风险警示

    Args:
        stock_results: 个股评分结果（已筛选，仅包含推送项）。
        etf_results: ETF评分结果（已筛选，仅包含推送项）。
        policy_impacts: 政策影响分析结果。
        report_date: 报告日期。
        stock_signals: 个股买卖信号列表（可选）。
        etf_signals: ETF买卖信号列表（可选）。
        max_recommend: 最大推荐股票数量。
        max_risk: 最大风险警示股票数量。
        score_threshold_high: 推荐阈值（默认70）。
        score_threshold_low: 风险阈值（默认30）。

    Returns:
        Markdown格式的推送文本。
    """
    # 默认空列表
    if stock_signals is None:
        stock_signals = []
    if etf_signals is None:
        etf_signals = []

    # 三档划分
    stock_buy = [r for r in stock_results if r.total_score >= score_threshold_high]
    stock_watch = [r for r in stock_results if score_threshold_low <= r.total_score < score_threshold_high]
    stock_sell = [r for r in stock_results if r.total_score < score_threshold_low]

    etf_buy = [r for r in etf_results if r.total_score >= score_threshold_high]
    etf_watch = [r for r in etf_results if score_threshold_low <= r.total_score < score_threshold_high]
    etf_sell = [r for r in etf_results if r.total_score < score_threshold_low]

    # 按评分排序
    stock_buy.sort(key=lambda x: x.total_score, reverse=True)
    stock_watch.sort(key=lambda x: x.total_score, reverse=True)
    stock_sell.sort(key=lambda x: x.total_score)
    etf_buy.sort(key=lambda x: x.total_score, reverse=True)
    etf_watch.sort(key=lambda x: x.total_score, reverse=True)
    etf_sell.sort(key=lambda x: x.total_score)

    # 限制数量
    stock_buy = stock_buy[:max_recommend]
    stock_watch = stock_watch[:max_recommend]
    stock_sell = stock_sell[:max_risk]
    etf_buy = etf_buy[:max_recommend]
    etf_watch = etf_watch[:max_recommend]
    etf_sell = etf_sell[:max_risk]

    sections: list[str] = []

    # 无推荐场景
    if not stock_buy and not stock_watch and not stock_sell and not etf_buy and not etf_watch and not etf_sell:
        sections.append(f"📊 A股每日分析报告 — {report_date}")
        sections.append("")
        sections.append("今日无符合条件的推荐标的。")
        sections.append(f"所有股票和ETF的综合评分均在观望区间（{score_threshold_low:.0f}~{score_threshold_high:.0f}分）。")
        sections.append("")

        # 政策要闻
        if policy_impacts:
            sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            sections.append("")
            sections.append("📰 今日政策要闻")
            sections.append("")
            for i, impact in enumerate(policy_impacts, 1):
                _append_impact_line(sections, i, impact)
            sections.append("")

        sections.append("⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        return "\n".join(sections)

    sections.append(f"📊 A股每日分析报告 — {report_date}")
    sections.append("")

    # 买入区
    if stock_buy or etf_buy:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append(f"🟢 买入区（综合评分 ≥ {score_threshold_high:.0f}）")
        sections.append("")
        for i, result in enumerate(stock_buy, 1):
            signal = _find_signal(result.code, stock_signals)
            sections.append(_format_stock_item(result, i, signal))
            sections.append("")
        for i, result in enumerate(etf_buy, 1):
            signal = _find_signal(result.code, etf_signals)
            sections.append(_format_etf_item(result, i, signal))
            sections.append("")
        sections.append("")

    # 观望区
    if stock_watch or etf_watch:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append(f"🟡 观望区（综合评分 {score_threshold_low:.0f}~{score_threshold_high:.0f}）")
        sections.append("")
        for i, result in enumerate(stock_watch, 1):
            signal = _find_signal(result.code, stock_signals)
            sections.append(_format_stock_item(result, i, signal))
            sections.append("")
        for i, result in enumerate(etf_watch, 1):
            signal = _find_signal(result.code, etf_signals)
            sections.append(_format_etf_item(result, i, signal))
            sections.append("")
        sections.append("")

    # 卖出区
    if stock_sell or etf_sell:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append(f"🔴 卖出区（综合评分 < {score_threshold_low:.0f}）")
        sections.append("")
        for i, result in enumerate(stock_sell, 1):
            tech_signals = []
            if result.technical_signals.ma5_10_death:
                tech_signals.append("MA5/10死叉")
            if result.technical_signals.macd_death:
                tech_signals.append("MACD死叉")
            if result.technical_signals.volume_peak:
                tech_signals.append("天量见天价")
            if result.technical_signals.volume_down:
                tech_signals.append("放量下跌")

            tech_str = "，".join(tech_signals) if tech_signals else "无明显风险信号"
            fund_str = f"评分{result.fundamental_score:.0f}分" if result.fundamental_score is not None else "无数据"
            news_str = result.news_summary if result.news_summary else "无政策影响"

            signal = _find_signal(result.code, stock_signals)

            lines = [
                f"【{i}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分",
                f"├ 风险信号：{tech_str}",
                f"├ 基本面：{fund_str}",
                f"├ 政策影响：{news_str}",
            ]

            if signal:
                lines.append(f"├ 信号区间：{signal.signal_emoji} {signal.signal_zone}（{signal.signal_score}分）")
                kp = signal.key_prices
                lines.append(
                    f"├ 关键价位：支撑 {kp.support_price} / 止损 {kp.stop_loss}"
                )

            lines.append(f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/")
            sections.append("\n".join(lines))
            sections.append("")

        for i, result in enumerate(etf_sell, 1):
            tech_signals = []
            if result.technical_signals.ma5_10_death:
                tech_signals.append("MA5/10死叉")
            if result.technical_signals.macd_death:
                tech_signals.append("MACD死叉")
            if result.technical_signals.volume_peak:
                tech_signals.append("天量见天价")
            if result.technical_signals.volume_down:
                tech_signals.append("放量下跌")

            tech_str = "，".join(tech_signals) if tech_signals else "无明显风险信号"
            news_str = result.news_summary if result.news_summary else "无政策影响"

            # 资金流向描述
            if result.fund_flow_score is not None:
                flow_str = (
                    "近5日份额持续减少"
                    if result.fund_flow_score < 3
                    else "份额变化平稳"
                )
            else:
                flow_str = "无数据"

            signal = _find_signal(result.code, etf_signals)

            lines = [
                f"【{i}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分",
                f"├ 风险信号：{tech_str}",
                f"├ 政策影响：{news_str}",
                f"├ 资金流向：{flow_str}",
            ]

            if signal:
                lines.append(f"├ 信号区间：{signal.signal_emoji} {signal.signal_zone}（{signal.signal_score}分）")
                kp = signal.key_prices
                lines.append(
                    f"├ 关键价位：支撑 {kp.support_price} / 止损 {kp.stop_loss}"
                )

            lines.append(f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/")
            sections.append("\n".join(lines))
            sections.append("")
        sections.append("")

    # 政策要闻
    if policy_impacts:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append("📰 今日政策要闻")
        sections.append("")
        for i, impact in enumerate(policy_impacts, 1):
            _append_impact_line(sections, i, impact)
        sections.append("")

    # 免责声明
    sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    sections.append("⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。")

    return "\n".join(sections)
