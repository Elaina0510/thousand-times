"""输出模块 — 报告生成、推送、实时提醒.

功能：
- stage_output(): 阶段5入口，生成报告并推送
- generate_report_md(): 生成完整 Markdown 报告
- push_report(): 推送报告到微信
- push_alerts(): 推送实时提醒
- run_realtime(): 实时监控主循环
- _is_trading_session(): 判断是否在交易时段
- _quick_collect(): 轻量数据采集
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("thousand-times")


@dataclass
class ScoreAlert:
    """分数跳变提醒。"""

    code: str
    delta: float
    score: object  # FactorScores
    message: str


@dataclass
class RegimeAlert:
    """市场环境切换提醒。"""

    old_state: str
    new_regime: object  # MarketRegime
    message: str


def generate_report_md(
    signals: list,
    scores: list,
    regime: object,
    data: object,
) -> str:
    """生成完整 Markdown 报告.

    Args:
        signals: Signal 列表。
        scores: FactorScores 列表。
        regime: MarketRegime。
        data: DataBundle。

    Returns:
        Markdown 报告文本。
    """
    lines: list[str] = []
    report_date = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"# A股智能选股分析报告 — {report_date}\n")

    # 1. 市场环境摘要
    state = getattr(regime, "state", "unknown")
    confidence = getattr(regime, "confidence", 0.0)
    position = getattr(regime, "position_advice", 0.5)
    desc = getattr(regime, "description", "未知")

    state_emoji = {"bull": "🐂", "bear": "🐻", "sideways": "↔️"}.get(state, "❓")
    state_cn = {"bull": "牛市", "bear": "熊市", "sideways": "震荡市"}.get(state, "未知")

    lines.append(f"## {state_emoji} 市场环境: {state_cn}\n")
    lines.append(f"- 置信度: {confidence:.0%}")
    lines.append(f"- 建议仓位: {position:.0%}")
    lines.append(f"- {desc}\n")

    # 投票详情
    regime_signals = getattr(regime, "signals", {})
    if regime_signals:
        lines.append("### 信号投票详情\n")
        lines.append("| 信号 | 判定 |")
        lines.append("|------|------|")
        for sig_name, vote in regime_signals.items():
            vote_cn = {"bull": "🐂 牛", "bear": "🐻 熊", "neutral": "↔️ 中"}.get(vote, vote)
            lines.append(f"| {sig_name} | {vote_cn} |")
        lines.append("")

    # 2. 买入信号
    buy_signals = [s for s in signals if getattr(s, "action", "") == "buy"]
    if buy_signals:
        lines.append(f"## 🟢 买入信号 ({len(buy_signals)} 只)\n")
        for s in buy_signals[:10]:
            kp = getattr(s, "key_prices", None)
            fs = getattr(s, "factor_scores", None)
            lines.append(f"### {s.name} ({s.code}) — 置信度 {s.confidence:.0%}\n")

            if fs:
                lines.append(f"- 综合分: {getattr(fs, 'total', 0):.1f} | "
                           f"技术: {getattr(fs, 'technical', 0):.0f} | "
                           f"基本面: {getattr(fs, 'fundamental', 0):.0f} | "
                           f"资金: {getattr(fs, 'capital', 0):.0f} | "
                           f"情绪: {getattr(fs, 'sentiment', 0):.0f} | "
                           f"动量: {getattr(fs, 'momentum', 0):.0f}")

            if kp and kp.current_price > 0:
                lines.append(f"- 当前价: {kp.current_price:.2f} | "
                           f"支撑: {kp.support:.2f} | "
                           f"压力: {kp.resistance:.2f}")
                lines.append(f"- 目标价: {kp.target:.2f} | "
                           f"止损: {kp.stop_loss:.2f} | "
                           f"盈亏比: {kp.risk_reward_ratio:.1f}")

            # 投票详情
            votes = getattr(s, "votes", [])
            if votes:
                vote_strs = [f"{v.source}:{v.vote}" for v in votes]
                lines.append(f"- 投票: {' | '.join(vote_strs)}")

            lines.append(f"- 理由: {s.reason}\n")
    else:
        lines.append("## 🟢 买入信号: 无\n")

    # 3. 卖出信号
    sell_signals = [s for s in signals if getattr(s, "action", "") == "sell"]
    if sell_signals:
        lines.append(f"## 🔴 卖出信号 ({len(sell_signals)} 只)\n")
        for s in sell_signals[:10]:
            kp = getattr(s, "key_prices", None)
            fs = getattr(s, "factor_scores", None)
            lines.append(f"### {s.name} ({s.code}) — 置信度 {s.confidence:.0%}\n")

            if fs:
                lines.append(f"- 综合分: {getattr(fs, 'total', 0):.1f} | "
                           f"技术: {getattr(fs, 'technical', 0):.0f} | "
                           f"基本面: {getattr(fs, 'fundamental', 0):.0f} | "
                           f"资金: {getattr(fs, 'capital', 0):.0f} | "
                           f"情绪: {getattr(fs, 'sentiment', 0):.0f} | "
                           f"动量: {getattr(fs, 'momentum', 0):.0f}")

            if kp and kp.current_price > 0:
                lines.append(f"- 当前价: {kp.current_price:.2f} | "
                           f"支撑: {kp.support:.2f} | "
                           f"压力: {kp.resistance:.2f}")

            votes = getattr(s, "votes", [])
            if votes:
                vote_strs = [f"{v.source}:{v.vote}" for v in votes]
                lines.append(f"- 投票: {' | '.join(vote_strs)}")

            lines.append(f"- 理由: {s.reason}\n")
    else:
        lines.append("## 🔴 卖出信号: 无\n")

    # 4. 重点关注（置信度最高的 3 只）
    top_signals = [s for s in signals if s.action in ("buy", "sell")][:3]
    if top_signals:
        lines.append("## ⭐ 重点关注\n")
        for s in top_signals:
            fs = getattr(s, "factor_scores", None)
            action_cn = "买入" if s.action == "buy" else "卖出"
            lines.append(f"**{s.name}** ({s.code}) — {action_cn} 置信度 {s.confidence:.0%}")

            if fs:
                # 子因子详情
                tech_detail = getattr(fs, "technical_detail", {})
                if tech_detail:
                    detail_str = " | ".join(f"{k}: {v:.0f}" for k, v in tech_detail.items())
                    lines.append(f"  - 技术面: {detail_str}")

                fund_detail = getattr(fs, "fundamental_detail", {})
                if fund_detail:
                    detail_str = " | ".join(f"{k}: {v:.0f}" for k, v in fund_detail.items())
                    lines.append(f"  - 基本面: {detail_str}")

            lines.append("")

    # 5. 统计摘要
    total = len(signals)
    hold_count = sum(1 for s in signals if s.action == "hold")
    lines.append("## 📊 统计摘要\n")
    lines.append(f"- 分析股票总数: {total}")
    lines.append(f"- 买入信号: {len(buy_signals)}")
    lines.append(f"- 卖出信号: {len(sell_signals)}")
    lines.append(f"- 观望: {hold_count}\n")

    return "\n".join(lines)


def push_report(report: str, config: object) -> bool:
    """推送报告到微信.

    Args:
        report: 报告文本。
        config: AppConfig。

    Returns:
        是否推送成功。
    """
    try:
        pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
        if not pushplus_token:
            logger.warning("PUSHPLUS_TOKEN 未设置，跳过推送")
            return False

        from src.push_service import push_to_wechat
        report_date = datetime.now().strftime("%Y-%m-%d")
        success = push_to_wechat(
            title=f"A股智能选股分析报告 — {report_date}",
            content=report,
            token=pushplus_token,
        )
        if success:
            logger.info("报告推送成功")
        else:
            logger.error("报告推送失败")
        return success
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False


def push_alerts(alerts: list, config: object) -> bool:
    """推送实时提醒.

    Args:
        alerts: 提醒列表（ScoreAlert 或 RegimeAlert）。
        config: AppConfig。

    Returns:
        是否推送成功。
    """
    if not alerts:
        return True

    try:
        pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "")
        if not pushplus_token:
            logger.warning("PUSHPLUS_TOKEN 未设置，跳过提醒推送")
            return False

        from src.push_service import push_to_wechat

        # 合并提醒为一条消息
        lines = ["# ⚡ 实时提醒\n"]
        for alert in alerts:
            if isinstance(alert, ScoreAlert):
                lines.append(f"- {alert.message}")
            elif isinstance(alert, RegimeAlert):
                lines.append(f"- 🔄 {alert.message}")

        content = "\n".join(lines)
        success = push_to_wechat(
            title=f"A股实时提醒 — {datetime.now().strftime('%H:%M')}",
            content=content,
            token=pushplus_token,
        )
        return success
    except Exception as e:
        logger.error(f"提醒推送异常: {e}")
        return False


def stage_output(signals: list, regime: object, data: object, config: object) -> str:
    """阶段5: 生成报告并推送.

    Args:
        signals: Signal 列表。
        regime: MarketRegime。
        data: DataBundle。
        config: AppConfig。

    Returns:
        报告文本。
    """
    logger.info("=== 阶段5: 报告生成 ===")

    # 生成报告
    scores = []  # 从 signals 中提取
    report = generate_report_md(signals, scores, regime, data)

    # 保存到文件
    report_date = datetime.now().strftime("%Y-%m-%d")
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    report_path = os.path.join(logs_dir, f"report_v2_{report_date}.md")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"报告已保存: {report_path}")
    except Exception as e:
        logger.warning(f"报告保存失败: {e}")

    # 推送
    push_report(report, config)

    return report


def _is_trading_session() -> bool:
    """判断是否在交易时段（9:30-15:00 工作日）。"""
    now = datetime.now()
    # 周末
    if now.weekday() >= 5:
        return False
    # 交易时段
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute
    # 9:30 = 570, 15:00 = 900
    return 570 <= current_minutes <= 900


def _quick_collect(config: object) -> object:
    """轻量数据采集（用于实时监控）.

    只采集最新K线和资金流，不重新获取基本面数据。

    Args:
        config: AppConfig。

    Returns:
        DataBundle。
    """
    from src.pipeline.collect import stage_collect
    # 复用 stage_collect，但可以通过缓存加速
    return stage_collect(config)


def run_realtime(config: object) -> None:
    """实时监控主循环.

    在交易时段内每 N 分钟检查一次：
    1. 快速采集数据
    2. 计算因子分数
    3. 检查分数跳变
    4. 检查市场环境变化
    5. 推送提醒

    Args:
        config: AppConfig。
    """
    from src.pipeline.collect import stage_collect
    from src.pipeline.regime import judge_market_regime
    from src.pipeline.factors import calc_factors

    realtime_config = getattr(config, "realtime", None)
    check_interval = getattr(realtime_config, "check_interval_minutes", 30) if realtime_config else 30
    score_threshold = getattr(realtime_config, "score_jump_threshold", 25.0) if realtime_config else 25.0

    last_scores: dict[str, float] = {}
    last_regime_state: str | None = None

    logger.info(f"启动实时监控，检查间隔: {check_interval}分钟")

    while True:
        # 检查是否在交易时段
        if not _is_trading_session():
            logger.info("非交易时段，等待 5 分钟后重试")
            time.sleep(300)
            continue

        try:
            # 1. 快速采集
            data = stage_collect(config)

            # 2. 计算因子分数
            regime = judge_market_regime(data, config)
            scores = calc_factors(data, config, regime.state)

            # 3. 检查分数跳变
            alerts: list = []
            for fs in scores:
                if fs.code in last_scores:
                    delta = fs.total - last_scores[fs.code]
                    if abs(delta) >= score_threshold:
                        direction = "↑" if delta > 0 else "↓"
                        alerts.append(ScoreAlert(
                            code=fs.code,
                            delta=delta,
                            score=fs,
                            message=f"{fs.name} 分数{direction}{abs(delta):.1f} → {fs.total:.1f}",
                        ))
                last_scores[fs.code] = fs.total

            # 4. 检查市场环境变化
            if last_regime_state is not None and regime.state != last_regime_state:
                alerts.append(RegimeAlert(
                    old_state=last_regime_state,
                    new_regime=regime,
                    message=f"市场环境切换: {last_regime_state} → {regime.state}",
                ))
            last_regime_state = regime.state

            # 5. 推送提醒
            if alerts:
                logger.info(f"检测到 {len(alerts)} 个提醒")
                push_alerts(alerts, config)

        except Exception as e:
            logger.error(f"实时监控异常: {e}")

        # 等待下一轮
        logger.info(f"等待 {check_interval} 分钟后进行下一轮检查")
        time.sleep(check_interval * 60)
