"""报告生成模块 — 组装推送文本内容。"""

from __future__ import annotations

from news_analysis import PolicyImpact
from scoring import ScoreResult


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
    sections.append(
        f"{index}. {impact.news_title} → {direction}{industries}"
    )


def _format_stock_item(result: ScoreResult, index: int) -> str:
    """格式化单只个股的输出。

    Args:
        result: 评分结果。
        index: 序号。

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

    return (
        f"【{index}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分\n"
        f"├ 技术信号：{tech_str}\n"
        f"├ 基本面：{fund_str}\n"
        f"├ 政策影响：{news_str}\n"
        f"├ 盈利概率：约 {result.profit_probability:.0f}%\n"
        f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/\n"
        f"[附K线图 + MACD图]"
    )


def _format_etf_item(result: ScoreResult, index: int) -> str:
    """格式化单只ETF的输出。

    Args:
        result: 评分结果。
        index: 序号。

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

    return (
        f"【{index}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分\n"
        f"├ 技术信号：{tech_str}\n"
        f"├ 政策影响：{news_str}\n"
        f"├ 资金流向：{flow_str}\n"
        f"├ 盈利概率：约 {result.profit_probability:.0f}%\n"
        f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/\n"
        f"[附K线图 + MACD图]"
    )


def generate_report(
    stock_results: list[ScoreResult],
    etf_results: list[ScoreResult],
    policy_impacts: list[PolicyImpact],
    report_date: str,
) -> str:
    """生成推送报告文本。

    Args:
        stock_results: 个股评分结果（已筛选，仅包含推送项）。
        etf_results: ETF评分结果（已筛选，仅包含推送项）。
        policy_impacts: 政策影响分析结果。
        report_date: 报告日期。

    Returns:
        Markdown格式的推送文本。
    """
    # 分类：推荐（≥70）和风险（<30）
    stock_recommend = [r for r in stock_results if r.total_score >= 70]
    stock_risk = [r for r in stock_results if r.total_score < 30]
    etf_recommend = [r for r in etf_results if r.total_score >= 70]
    etf_risk = [r for r in etf_results if r.total_score < 30]

    # 按评分排序
    stock_recommend.sort(key=lambda x: x.total_score, reverse=True)
    stock_risk.sort(key=lambda x: x.total_score)
    etf_recommend.sort(key=lambda x: x.total_score, reverse=True)
    etf_risk.sort(key=lambda x: x.total_score)

    sections: list[str] = []

    # 无推荐场景
    if not stock_recommend and not stock_risk and not etf_recommend and not etf_risk:
        sections.append(f"📊 A股每日分析报告 — {report_date}")
        sections.append("")
        sections.append("今日无符合条件的推荐标的。")
        sections.append("所有股票和ETF的综合评分均在观望区间（30~70分）。")
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

    # 个股推荐
    if stock_recommend:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append("📈 今日个股推荐关注（综合评分 ≥ 70）")
        sections.append("")
        for i, result in enumerate(stock_recommend, 1):
            sections.append(_format_stock_item(result, i))
            sections.append("")
        sections.append("")

    # ETF推荐
    if etf_recommend:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append("📈 今日ETF推荐关注（综合评分 ≥ 70）")
        sections.append("")
        for i, result in enumerate(etf_recommend, 1):
            sections.append(_format_etf_item(result, i))
            sections.append("")
        sections.append("")

    # 个股风险警示
    if stock_risk:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append("⚠️ 个股风险警示（综合评分 < 30）")
        sections.append("")
        for i, result in enumerate(stock_risk, 1):
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

            sections.append(
                f"【{i}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分\n"
                f"├ 风险信号：{tech_str}\n"
                f"├ 基本面：{fund_str}\n"
                f"├ 政策影响：{news_str}\n"
                f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/"
            )
            sections.append("")
        sections.append("")

    # ETF风险警示
    if etf_risk:
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        sections.append("⚠️ ETF风险警示（综合评分 < 30）")
        sections.append("")
        for i, result in enumerate(etf_risk, 1):
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

            sections.append(
                f"【{i}】{result.name} ({result.code}) — 综合评分：{result.total_score:.0f}分\n"
                f"├ 风险信号：{tech_str}\n"
                f"├ 政策影响：{news_str}\n"
                f"├ 资金流向：{flow_str}\n"
                f"└ 🔗 同花顺详情：https://stockpage.10jqka.com.cn/{result.code}/"
            )
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
