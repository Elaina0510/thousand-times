"""统一管道入口 — UnifiedPipeline.

废弃 V1 管道（main.py），以 V2 五阶段管道为基础注入全部新模块，
形成唯一的执行入口。

V3 管道流程:
    collect → data_quality → regime → factors(calibrated) → signal+risk → output+feedback
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("thousand-times")


@dataclass
class PipelineResult:
    """统一管道执行结果."""

    report_date: str = ""
    regime: object | None = None          # MarketRegime
    quality_report: object | None = None  # DataQualityReport
    signals: list[object] = field(default_factory=list)  # list[Signal]
    report_text: str = ""
    report_html_path: str | None = None
    push_success: bool = False
    execution_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


def run(config: object) -> PipelineResult:
    """执行统一管道（V3）.

    废弃 V1 的 main() 函数，这是唯一的分析入口。

    Args:
        config: 应用配置（AppConfig）.

    Returns:
        PipelineResult 完整执行结果.
    """
    start_time = time.time()
    result = PipelineResult()
    errors: list[str] = []

    logger.info("=" * 60)
    logger.info("V3 统一管道开始执行")
    logger.info("=" * 60)

    # ── 阶段 1: 数据采集 ──
    data_bundle = None
    try:
        logger.info("阶段 1: 数据采集...")
        from pipeline.collect import stage_collect
        data_bundle = stage_collect(config)
        logger.info("阶段 1 完成: 数据采集成功")
    except Exception as e:
        err_msg = f"阶段 1 数据采集失败: {e}"
        logger.error(err_msg)
        errors.append(err_msg)
        # 数据采集失败是致命的，后续阶段无法继续
        result.errors = errors
        result.execution_time_seconds = time.time() - start_time
        return result

    # ── 阶段 1.5: 数据质量 ──
    quality_report = None
    try:
        logger.info("阶段 1.5: 数据质量校验...")
        from data_quality.validator import validate_bundle
        quality_report = validate_bundle(data_bundle)
        result.quality_report = quality_report
        logger.info(
            f"阶段 1.5 完成: 数据质量等级={quality_report.overall_level.value}"
        )
    except Exception as e:
        err_msg = f"阶段 1.5 数据质量校验失败: {e}"
        logger.warning(err_msg + "，跳过质量校验继续执行")
        errors.append(err_msg)

    # ── 阶段 2: 市场环境 ──
    regime = None
    try:
        logger.info("阶段 2: 市场环境判断...")
        from pipeline.regime import judge_market_regime
        regime = judge_market_regime(data_bundle, config)
        result.regime = regime
        logger.info(f"阶段 2 完成: 市场环境={regime.state}")
    except Exception as e:
        err_msg = f"阶段 2 市场环境判断失败: {e}"
        logger.warning(err_msg + "，使用默认震荡市")
        errors.append(err_msg)
        from pipeline.regime import MarketRegime
        regime = MarketRegime(state="sideways", confidence=0.3)

    # ── 阶段 3: 因子计算 ──
    raw_scores: list[Any] = []
    calibrated_scores: list[Any] = []
    try:
        logger.info("阶段 3: 因子计算...")
        from pipeline.factors import calc_factors
        raw_scores = calc_factors(data_bundle, config, regime.state)
        logger.info(f"阶段 3a 完成: 计算了 {len(raw_scores)} 只股票的因子")

        # V3: 百分位校准
        try:
            from factors.calibrator import calibrate_scores
            calibrated_scores = calibrate_scores(raw_scores)  # type: ignore[arg-type]
            logger.info(f"阶段 3b 完成: 校准了 {len(calibrated_scores)} 只股票的评分")
        except Exception as e:
            err_msg = f"阶段 3b 因子校准失败: {e}"
            logger.warning(err_msg + "，使用原始评分")
            errors.append(err_msg)
            calibrated_scores = raw_scores
    except Exception as e:
        err_msg = f"阶段 3 因子计算失败: {e}"
        logger.error(err_msg)
        errors.append(err_msg)

    # ── 阶段 4: 信号生成 + 风控 ──
    signals: list[Any] = []
    try:
        logger.info("阶段 4: 信号生成（自适应投票）...")
        from pipeline.signal import generate_signals
        signals = generate_signals(calibrated_scores, data_bundle, config, regime.state)
        logger.info(
            f"阶段 4a 完成: 生成 {len(signals)} 个信号 "
            f"(buy={sum(1 for s in signals if s.action == 'buy')}, "
            f"sell={sum(1 for s in signals if s.action == 'sell')}, "
            f"hold={sum(1 for s in signals if s.action == 'hold')})"
        )

        # V3: 风控过滤
        try:
            from risk.guard import apply_risk_rules
            guard_result = apply_risk_rules(  # type: ignore[arg-type]
                signals, data_bundle.stock_pool, data_bundle.kline_cache, [], {},
            )
            signals = guard_result.passed
            logger.info(
                f"阶段 4b 完成: 风控过滤后 {len(signals)} 个信号 "
                f"(拒绝 {guard_result.rejected_count() if hasattr(guard_result, 'rejected_count') else len(guard_result.rejected)})"  # noqa: E501
            )
        except Exception as e:
            err_msg = f"阶段 4b 风控过滤失败: {e}"
            logger.warning(err_msg + "，跳过风控")
            errors.append(err_msg)
    except Exception as e:
        err_msg = f"阶段 4 信号生成失败: {e}"
        logger.error(err_msg)
        errors.append(err_msg)

    result.signals = signals

    # ── 阶段 5: 输出 ──
    try:
        logger.info("阶段 5: 报告生成...")
        from datetime import datetime
        result.report_date = datetime.now().strftime("%Y-%m-%d")

        try:
            from pipeline.output import stage_output
            report_text = stage_output(signals, data_bundle, config, regime)
            result.report_text = report_text
            logger.info("阶段 5 完成: 报告生成成功")
        except Exception as e:
            err_msg = f"阶段 5 报告生成失败: {e}"
            logger.warning(err_msg)
            errors.append(err_msg)
    except Exception as e:
        err_msg = f"阶段 5 输出失败: {e}"
        logger.error(err_msg)
        errors.append(err_msg)

    result.errors = errors
    result.execution_time_seconds = round(time.time() - start_time, 2)

    logger.info(
        f"V3 统一管道执行完成 "
        f"(耗时 {result.execution_time_seconds}s, "
        f"错误 {len(errors)} 个)"
    )

    return result


def run_paper_trading(config: object) -> PipelineResult:
    """纸交易模式：运行完整管道但不产生真实交易.

    所有信号仅记录到 SignalTracker 用于后续验证。

    Args:
        config: 应用配置（AppConfig）.

    Returns:
        PipelineResult.
    """
    logger.info("纸交易模式启动（不推送实盘信号）")
    result = run(config)
    result.push_success = False  # 纸交易不推送

    # 记录到 SignalTracker
    try:
        from feedback.tracker import record_signals_v3
        count = record_signals_v3(result.signals, result.report_date)
        logger.info(f"纸交易信号已记录: {count} 条")
    except Exception as e:
        logger.warning(f"纸交易信号记录失败: {e}")

    return result
