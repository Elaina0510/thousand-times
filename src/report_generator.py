"""报告生成模块 — 组装推送文本内容。"""

from __future__ import annotations

from etf_analyzer import ETF_NAME_MAP
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


def _normalize_etf_name(name: str) -> str:
    """统一ETF名称格式。

    对于以 "ETF_" 开头的内部名称，去掉前缀并查映射表；
    对于其他名称，原样返回。

    Args:
        name: ETF 原始名称。

    Returns:
        规范化的显示名称。
    """
    stripped = name
    if name.startswith("ETF_"):
        stripped = name[4:]
    # 尝试通过代码查找映射表
    for code, mapped_name in ETF_NAME_MAP.items():
        if mapped_name == stripped or code == stripped:
            return mapped_name
    return stripped


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
        f"【{index}】{_normalize_etf_name(result.name)} ({result.code}) — 综合评分：{result.total_score:.0f}分",
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


def _build_retrospective_section(report_date: str, stock_changes: dict[str, float] | None = None) -> str:
    """构建昨日推荐回顾章节。

    从 signal_tracker 查询昨日推荐信号，与今日价格对比计算涨跌幅。

    Args:
        report_date: 报告日期（格式 YYYY-MM-DD）。
        stock_changes: 股票代码到今日涨跌幅的映射（可选）。

    Returns:
        格式化的回顾文本，无昨日推荐时返回空字符串。
    """
    try:
        from signal_tracker import get_yesterday_recommendations

        records = get_yesterday_recommendations(report_date)
        if not records:
            return ""

        buy_records = [r for r in records if r["action"] == "buy"]
        sell_records = [r for r in records if r["action"] == "sell"]

        lines = ["📈 昨日推荐回顾", ""]

        # 买入信号汇总
        if buy_records:
            changes = []
            for r in buy_records:
                code = r["code"]
                if stock_changes and code in stock_changes:
                    changes.append(stock_changes[code])
            if changes:
                avg_change = sum(changes) / len(changes)
                lines.append(f"  买入信号 {len(buy_records)} 只，今日平均涨跌幅 {avg_change:+.2f}%")
            else:
                lines.append(f"  买入信号 {len(buy_records)} 只（涨跌幅数据待更新）")
        else:
            lines.append("  买入信号 0 只")

        # 风险警示汇总
        if sell_records:
            changes = []
            for r in sell_records:
                code = r["code"]
                if stock_changes and code in stock_changes:
                    changes.append(stock_changes[code])
            if changes:
                avg_change = sum(changes) / len(changes)
                lines.append(f"  风险警示 {len(sell_records)} 只，今日平均涨跌幅 {avg_change:+.2f}%")
            else:
                lines.append(f"  风险警示 {len(sell_records)} 只（涨跌幅数据待更新）")
        else:
            lines.append("  风险警示 0 只")

        lines.append("")
        return "\n".join(lines)
    except ImportError:
        return ""
    except Exception:
        return ""


def _build_top_ranking(stock_results: list[ScoreResult], n: int = 10) -> str:
    """构建评分排名 Top N 章节。

    Args:
        stock_results: 个股评分结果列表。
        n: 显示前 N 名，默认 10。

    Returns:
        格式化的排名文本。
    """
    if not stock_results:
        return ""

    sorted_results = sorted(stock_results, key=lambda x: x.total_score, reverse=True)
    top_n = sorted_results[:n]

    lines = ["🏆 评分排名 Top " + str(len(top_n)), ""]
    for i, r in enumerate(top_n, 1):
        tech = f"技术{r.technical_score:.0f}"
        fund = f"基本面{r.fundamental_score:.0f}" if r.fundamental_score is not None else "基本面-"
        news = f"新闻{r.news_score:.0f}"
        lines.append(
            f"  {i}. {r.name} ({r.code}) — {r.total_score:.0f}分 {r.judgment} | {tech} {fund} {news}"
        )
    lines.append("")
    return "\n".join(lines)


def _build_market_overview(
    market_regime: str | None = None,
    north_flow: float | None = None,
    pmi: float | None = None,
    m2: float | None = None,
    advance_decline: float | None = None,
) -> str:
    """构建市场概况章节。

    Args:
        market_regime: 市场状态描述（如 "震荡偏多"）。
        north_flow: 北向资金净流入（亿元）。
        pmi: PMI 数据。
        m2: M2 增速（%）。
        advance_decline: 涨跌比。

    Returns:
        格式化的市场概况文本。
    """
    lines = ["📊 市场概况", ""]

    if market_regime:
        lines.append(f"  市场状态：{market_regime}")
    if north_flow is not None:
        signal = "流入" if north_flow >= 0 else "流出"
        lines.append(f"  北向资金：{signal} {abs(north_flow):.2f} 亿")
    if pmi is not None:
        lines.append(f"  PMI：{pmi:.1f}")
    if m2 is not None:
        lines.append(f"  M2 增速：{m2:.1f}%")
    if advance_decline is not None:
        lines.append(f"  涨跌比：{advance_decline:.2f}")

    lines.append("")
    return "\n".join(lines)


def _build_sector_heatmap(
    etf_results: list[ScoreResult],
    etf_changes: dict[str, float] | None = None,
    max_bars: int = 20,
) -> str:
    """构建行业热力图章节。

    按 ETF 涨幅排序，使用 ASCII 柱状图展示。

    Args:
        etf_results: ETF 评分结果列表。
        etf_changes: ETF 代码到涨跌幅的映射（可选），无数据时使用评分作为参考。
        max_bars: 柱状图最大长度。

    Returns:
        格式化的热力图文本。
    """
    if not etf_results:
        return ""

    # 构建 (名称, 涨跌幅) 列表
    items: list[tuple[str, float]] = []
    for r in etf_results:
        change = None
        if etf_changes and r.code in etf_changes:
            change = etf_changes[r.code]
        elif r.total_score:
            # 无涨跌幅数据时，用评分减 50 作为近似参考
            change = (r.total_score - 50) / 10.0
        if change is not None:
            name = _normalize_etf_name(r.name)
            items.append((name, change))

    if not items:
        return ""

    # 按涨跌幅降序
    items.sort(key=lambda x: x[1], reverse=True)
    max_abs = max(abs(v) for _, v in items) if items else 1.0

    lines = ["🔥 行业热力图", ""]
    for name, change in items:
        bar_len = int(abs(change) / max_abs * max_bars) if max_abs > 0 else 0
        bar = "█" * bar_len
        if change >= 0:
            lines.append(f"  {name} +{change:.1f}% {bar}")
        else:
            lines.append(f"  {name} {change:.1f}% {bar}")
    lines.append("")
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
    market_regime: str | None = None,
    north_flow: float | None = None,
    pmi: float | None = None,
    m2: float | None = None,
    advance_decline: float | None = None,
    etf_changes: dict[str, float] | None = None,
    stock_changes: dict[str, float] | None = None,
) -> str:
    """生成推送报告文本。

    使用三档划分展示所有结果：
    - 买入区（≥70分）：推荐关注
    - 观望区（30-69分）：观望等待
    - 卖出区（<30分）：风险警示

    报告中包含：市场概况、昨日推荐回顾、评分排名 Top 10、
    行业热力图、各档位详细列表、政策要闻。

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
        market_regime: 市场状态描述（可选）。
        north_flow: 北向资金净流入（可选）。
        pmi: PMI 数据（可选）。
        m2: M2 增速（可选）。
        advance_decline: 涨跌比（可选）。
        etf_changes: ETF代码→涨跌幅映射（可选）。
        stock_changes: 股票代码→涨跌幅映射（可选）。

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

        # 市场概况（即使无推荐也展示）
        overview = _build_market_overview(
            market_regime=market_regime,
            north_flow=north_flow,
            pmi=pmi,
            m2=m2,
            advance_decline=advance_decline,
        )
        if overview.strip():
            sections.append(overview)

        # 昨日推荐回顾
        retro = _build_retrospective_section(report_date, stock_changes)
        if retro.strip():
            sections.append(retro)

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

    # 市场概况
    overview = _build_market_overview(
        market_regime=market_regime,
        north_flow=north_flow,
        pmi=pmi,
        m2=m2,
        advance_decline=advance_decline,
    )
    if overview.strip():
        sections.append(overview)

    # 昨日推荐回顾
    retro = _build_retrospective_section(report_date, stock_changes)
    if retro.strip():
        sections.append(retro)

    # 评分排名 Top 10
    ranking = _build_top_ranking(stock_results, n=10)
    if ranking.strip():
        sections.append(ranking)

    # 行业热力图
    heatmap = _build_sector_heatmap(etf_results, etf_changes)
    if heatmap.strip():
        sections.append(heatmap)

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
                f"【{i}】{_normalize_etf_name(result.name)} ({result.code}) — 综合评分：{result.total_score:.0f}分",
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
