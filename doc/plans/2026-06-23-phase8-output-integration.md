# Phase 8: 输出与集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现输出模块 `pipeline/output.py`，精简 `main.py` 为管道编排器，实现实时提醒模式，完成新旧双轨切换

**Architecture:** output.py 负责报告生成和推送，main.py 精简为五阶段管道编排 + 命令行参数支持

**Tech Stack:** Python 3.10+, argparse, Markdown, PushPlus

## Global Constraints

- 报告格式: Markdown (微信推送) + HTML (详细版)
- 新旧切换通过 `use_v2_pipeline` 配置开关控制
- 实时监控仅在交易时段运行（9:30-15:00）
- 每阶段独立异常处理，单阶段失败不终止管道

## 文件结构

```
src/
├── main.py              ← 修改：精简+增加v2管道+--realtime模式
├── pipeline/
│   └── output.py         ← 新建：报告生成+推送

tests/
└── test_pipeline_output.py  ← 新建
```

---

### Task 1: 实现输出模块 (pipeline/output.py)

**Files:**
- Create: `src/pipeline/output.py`
- Create: `tests/test_pipeline_output.py`

**Interfaces:**
- Produces: `generate_report_md(signals: list[Signal], scores: dict[str, FactorScores], regime: MarketRegime) -> str`
- Produces: `push_report(report: str) -> bool`
- Produces: `stage_output(signals: list[Signal], scores: dict[str, FactorScores], data: DataBundle, config: AppConfig, regime: MarketRegime) -> None`

- [ ] **Step 1: 编写输出模块测试**

```python
# tests/test_pipeline_output.py
"""测试 pipeline/output.py 报告输出模块."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.output import (
    ScoreAlert,
    RegimeAlert,
    generate_report_md,
    push_alerts,
    push_report,
)


class TestGenerateReportMd:
    """Markdown报告生成测试."""

    def test_returns_string(self) -> None:
        """返回字符串."""
        from src.pipeline.regime import MarketRegime
        regime = MarketRegime(
            state="sideways", confidence=0.5, position_advice=0.5,
            signals={}, description="震荡市"
        )
        result = generate_report_md([], {}, regime)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_regime_info(self) -> None:
        """包含市场环境信息."""
        from src.pipeline.regime import MarketRegime
        regime = MarketRegime(
            state="bull", confidence=0.8, position_advice=0.94,
            signals={}, description="牛市"
        )
        result = generate_report_md([], {}, regime)
        assert "牛市" in result
        assert "80%" in result  # confidence

    def test_includes_signal_list(self) -> None:
        """包含信号列表."""
        from src.pipeline.regime import MarketRegime
        from src.pipeline.signal import KeyPrices, Signal, SignalVote
        from src.pipeline.factors import FactorScores

        regime = MarketRegime(
            state="bull", confidence=0.8, position_advice=0.94,
            signals={}, description="牛市"
        )
        fs = FactorScores("600519", "贵州茅台", 80, 70, 65, 60, 85, total_score=75)
        kp = KeyPrices(10.0, 9.0, 11.5, 11.0, 9.2, 2.5)
        signals = [
            Signal("600519", "贵州茅台", False, "buy", 0.8,
                   [SignalVote("factor", "buy", 0.8, "")],
                   kp, fs, "3/5票买入"),
        ]
        result = generate_report_md(signals, {}, regime)
        assert "贵州茅台" in result
        assert "600519" in result


class TestPushReport:
    """推送报告测试."""

    @patch("src.pipeline.output.push_to_wechat")
    def test_returns_true_on_success(self, mock_push: MagicMock) -> None:
        """成功返回 True."""
        mock_push.return_value = True
        result = push_report("test report")
        assert result is True

    @patch("src.pipeline.output.push_to_wechat")
    def test_returns_false_on_failure(self, mock_push: MagicMock) -> None:
        """失败返回 False."""
        mock_push.side_effect = Exception("Push failed")
        result = push_report("test report")
        assert result is False


class TestAlerts:
    """提醒数据结构测试."""

    def test_score_alert(self) -> None:
        alert = ScoreAlert(code="600519", delta=25.0, score=None, message="test")
        assert alert.delta == 25.0

    def test_regime_alert(self) -> None:
        alert = RegimeAlert(old_state="sideways", new_regime=None, message="切换")
        assert alert.old_state == "sideways"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_output.py -v`

Expected: FAIL

- [ ] **Step 3: 实现输出模块**

```python
# src/pipeline/output.py
"""输出模块.

生成每日报告，推送到微信。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import AppConfig
from src.pipeline.collect import DataBundle
from src.pipeline.factors import FactorScores
from src.pipeline.regime import MarketRegime
from src.pipeline.signal import Signal

logger = logging.getLogger("thousand-times")


@dataclass
class ScoreAlert:
    """分数跳变提醒."""

    code: str
    delta: float
    score: FactorScores | None
    message: str


@dataclass
class RegimeAlert:
    """市场环境切换提醒."""

    old_state: str
    new_regime: MarketRegime | None
    message: str


def generate_report_md(
    signals: list[Signal],
    scores: dict[str, FactorScores],
    regime: MarketRegime,
) -> str:
    """生成 Markdown 格式的每日报告.

    Args:
        signals: 信号列表
        scores: 因子分数
        regime: 市场环境

    Returns:
        str: Markdown 报告
    """
    buy_signals = [s for s in signals if s.action == "buy"]
    sell_signals = [s for s in signals if s.action == "sell"]

    lines = []
    lines.append("# A股量化分析日报")
    lines.append("")
    lines.append("## 一、市场环境")
    lines.append(f"- 状态：**{regime.description}**")
    lines.append(f"- 置信度：{regime.confidence*100:.0f}%")
    lines.append(f"- 建议仓位：**{regime.position_advice*100:.0f}%**")
    lines.append("")

    # 信号详情（前5个）
    signal_summary = [f"{v.name}:{v.vote}" for v in signals[0].votes] if signals else []
    lines.append(f"- 信号详情：{', '.join(signal_summary)}")
    lines.append("")

    lines.append("## 二、买入信号")
    if buy_signals:
        for i, s in enumerate(buy_signals[:10], 1):
            lines.append(f"{i}. **{s.name}** ({s.code})")
            lines.append(f"   - 置信度: {s.confidence*100:.0f}%")
            lines.append(f"   - 价格: {s.key_prices.current_price}")
            lines.append(f"   - 目标: {s.key_prices.target_price} / 止损: {s.key_prices.stop_loss}")
            lines.append(f"   - 因子分: 技术{s.factor_scores.technical_score} "
                         f"基本{s.factor_scores.fundamental_score} "
                         f"动量{s.factor_scores.momentum_score}")
            lines.append("")
    else:
        lines.append("无买入信号")
        lines.append("")

    lines.append("## 三、卖出信号")
    if sell_signals:
        for i, s in enumerate(sell_signals[:10], 1):
            lines.append(f"{i}. **{s.name}** ({s.code}) - 置信度 {s.confidence*100:.0f}%")
            lines.append(f"   - 因子分: 技术{s.factor_scores.technical_score} "
                         f"基本{s.factor_scores.fundamental_score}")
            lines.append("")
    else:
        lines.append("无卖出信号")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告由千倍系统自动生成*")

    return "\n".join(lines)


def push_report(report: str) -> bool:
    """推送报告到微信.

    Args:
        report: Markdown 报告内容

    Returns:
        bool: 推送是否成功
    """
    try:
        from src.push_service import push_to_wechat
        return push_to_wechat(report)
    except Exception as e:
        logger.error(f"推送报告失败: {e}")
        return False


def push_alerts(alerts: list[ScoreAlert | RegimeAlert], config: AppConfig) -> bool:
    """推送实时提醒.

    Args:
        alerts: ScoreAlert 或 RegimeAlert 列表
        config: AppConfig

    Returns:
        bool: 推送是否成功
    """
    if not alerts:
        return True

    lines = ["# ⚡ 实时提醒"]
    for alert in alerts:
        lines.append(f"- {alert.message}")

    return push_report("\n".join(lines))


def stage_output(
    signals: list[Signal],
    scores: dict[str, FactorScores],
    data: DataBundle,
    config: AppConfig,
    regime: MarketRegime,
) -> None:
    """阶段5: 报告生成和推送.

    Args:
        signals: 信号列表
        scores: 因子分数
        data: 数据包
        config: 应用配置
        regime: 市场环境
    """
    logger.info("=== 阶段5: 报告输出 ===")

    # 生成报告
    report = generate_report_md(signals, scores, regime)
    logger.info(f"报告生成完成 ({len(report)} 字符)")

    # 保存本地
    try:
        import os
        os.makedirs("logs", exist_ok=True)
        filename = f"logs/report_{pd.Timestamp.now().strftime('%Y%m%d')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"报告已保存: {filename}")
    except Exception as e:
        logger.error(f"保存报告失败: {e}")

    # 推送到微信
    success = push_report(report)
    if success:
        logger.info("报告推送成功")
    else:
        logger.warning("报告推送失败")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_output.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/output.py tests/test_pipeline_output.py
git commit -m "feat: 实现报告生成和推送模块 (pipeline/output.py)"
```

---

### Task 2: 精简 main.py 为管道编排器

**Files:**
- Modify: `src/main.py`
- Modify: `tests/test_pipeline_output.py` (增加管道编排测试)

**Interfaces:**
- Produces: `run_pipeline(config: AppConfig) -> None` (V2管道)
- Produces: `run_realtime(config: AppConfig) -> None` (实时监控)

- [ ] **Step 1: 编写管道编排测试**

在 `tests/test_pipeline_output.py` 末尾添加：

```python
from unittest.mock import MagicMock, patch


class TestPipeline:
    """管道编排测试."""

    @patch("src.main.stage_collect")
    @patch("src.main.judge_market_regime")
    @patch("src.main.calc_factors")
    @patch("src.main.generate_signals")
    @patch("src.main.stage_output")
    def test_run_pipeline_calls_all_stages(
        self,
        mock_output: MagicMock,
        mock_signals: MagicMock,
        mock_factors: MagicMock,
        mock_regime: MagicMock,
        mock_collect: MagicMock,
    ) -> None:
        """管道编排调用所有5个阶段."""
        from src.main import run_pipeline
        from src.pipeline.collect import DataBundle
        from src.pipeline.regime import MarketRegime

        mock_collect.return_value = DataBundle(
            index_kline=pd.DataFrame(), stock_pool=pd.DataFrame(),
            kline_cache={}, fundamental_cache={},
            north_flow=pd.DataFrame(), margin_data=None,
            limit_up_count=0, limit_down_count=0, advance_decline_ratio=1.0,
            macro_indicators={}, sector_flow=pd.DataFrame(),
            news_items=[], policy_impacts=[], etf_pool=[], etf_kline_cache={},
        )
        mock_regime.return_value = MarketRegime(
            state="sideways", confidence=0.5, position_advice=0.5,
            signals={}, description="震荡"
        )
        mock_factors.return_value = {}
        mock_signals.return_value = []

        config = AppConfig()
        run_pipeline(config)

        mock_collect.assert_called_once()
        mock_regime.assert_called_once()
        mock_factors.assert_called_once()
        mock_signals.assert_called_once()
        mock_output.assert_called_once()

    @patch("src.main.stage_collect")
    def test_run_pipeline_handles_stage_failure(self, mock_collect: MagicMock) -> None:
        """阶段失败不崩溃."""
        from src.main import run_pipeline
        mock_collect.side_effect = Exception("数据采集失败")

        config = AppConfig()
        # 不应抛异常
        run_pipeline(config)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_output.py::TestPipeline -v`

Expected: FAIL

- [ ] **Step 3: 在 main.py 中添加 V2 管道函数**

在 `src/main.py` 中添加：

```python
def run_pipeline(config: AppConfig) -> None:
    """V2 管道主函数：五阶段编排.

    Args:
        config: 应用配置
    """
    logger.info("=" * 60)
    logger.info("千倍系统 V2 管道启动")
    logger.info("=" * 60)

    # 阶段1: 市场环境判断
    try:
        # 先用轻量数据做环境判断
        # 完整数据在阶段2采集
        regime = MarketRegime(
            state="sideways", confidence=0.5, position_advice=0.5,
            signals={}, description="默认震荡（数据采集前）"
        )
        logger.info("阶段1完成: 使用默认环境（数据采集后重新判断）")
    except Exception as e:
        logger.error(f"市场环境判断失败: {e}，使用默认震荡")
        regime = MarketRegime(
            state="sideways", confidence=0.5, position_advice=0.5,
            signals={}, description="默认震荡"
        )

    # 阶段2: 数据采集
    try:
        data = stage_collect(config, regime)
    except Exception as e:
        logger.error(f"数据采集失败: {e}，终止本次运行")
        return

    # 重新判断市场环境（基于完整数据）
    try:
        regime = judge_market_regime(data, config)
    except Exception as e:
        logger.error(f"市场环境判断失败: {e}，使用默认震荡")
        regime = MarketRegime(
            state="sideways", confidence=0.5, position_advice=0.5,
            signals={}, description="默认震荡"
        )

    # 阶段3: 多因子计算
    try:
        scores = calc_factors(data, config, regime_state=regime.state)
    except Exception as e:
        logger.error(f"因子计算失败: {e}，终止本次运行")
        return

    # 阶段4: 信号生成
    try:
        signals = generate_signals(scores, data, config, regime.state)
    except Exception as e:
        logger.error(f"信号生成失败: {e}，终止本次运行")
        return

    # 阶段5: 输出
    try:
        stage_output(signals, scores, data, config, regime)
    except Exception as e:
        logger.error(f"输出失败: {e}")

    logger.info("=" * 60)
    logger.info("千倍系统 V2 管道完成")
    logger.info("=" * 60)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd "h:/code/thousand times" && python -m pytest tests/test_pipeline_output.py::TestPipeline -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd "h:/code/thousand times"
git add src/main.py tests/test_pipeline_output.py
git commit -m "feat: 实现 V2 管道编排 run_pipeline"
```

---

### Task 3: 实现实时监控模式和命令行入口

**Files:**
- Modify: `src/main.py`

**Interfaces:**
- Produces: `run_realtime(config: AppConfig) -> None` (实时监控)
- Produces: `main()` 增加 --realtime 和 --v2 参数

- [ ] **Step 1: 实现实时监控函数**

在 `src/main.py` 中添加：

```python
import time
from datetime import datetime


def _is_trading_session() -> bool:
    """检查是否在交易时段（9:30-15:00）."""
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    current_time = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= current_time <= 15 * 60  # 9:30-15:00


def _quick_collect(config: AppConfig) -> DataBundle:
    """快速数据采集（仅采集实时监控所需的最小数据集）.

    Args:
        config: 应用配置

    Returns:
        DataBundle: 精简数据包
    """
    from src.data_sources.capital_flow import fetch_north_flow
    from src.data_sources.sentiment import fetch_limit_stats

    # 仅采集实时变化的数据
    today = datetime.now().strftime("%Y%m%d")
    north_flow = fetch_north_flow(days=5)
    limit_stats = fetch_limit_stats(today)

    return DataBundle(
        index_kline=pd.DataFrame(),
        stock_pool=pd.DataFrame(),
        kline_cache={},
        fundamental_cache={},
        north_flow=north_flow,
        margin_data=None,
        limit_up_count=limit_stats["limit_up_count"],
        limit_down_count=limit_stats["limit_down_count"],
        advance_decline_ratio=(
            limit_stats["limit_up_count"] / max(limit_stats["limit_down_count"], 1)
        ),
        macro_indicators={},
        sector_flow=pd.DataFrame(),
        news_items=[],
        policy_impacts=[],
        etf_pool=[],
        etf_kline_cache={},
    )


def run_realtime(config: AppConfig) -> None:
    """实时监控主循环.

    Args:
        config: 应用配置
    """
    logger.info("实时监控模式启动")
    last_scores: dict[str, float] = {}
    last_regime: str | None = None

    while True:
        if not _is_trading_session():
            wait_minutes = 10
            logger.debug(f"非交易时段，{wait_minutes}分钟后检查")
            time.sleep(wait_minutes * 60)
            continue

        try:
            # 1. 快速采集
            data = _quick_collect(config)

            # 2. 判断市场环境
            regime = judge_market_regime(data, config)

            # 3. 检查市场环境切换
            if last_regime is not None and regime.state != last_regime:
                alert = RegimeAlert(
                    old_state=last_regime,
                    new_regime=regime,
                    message=f"⚠ 市场环境切换：{last_regime} → {regime.state}",
                )
                push_alerts([alert], config)
                logger.info(f"环境切换: {last_regime} → {regime.state}")

            last_regime = regime.state

        except Exception as e:
            logger.error(f"实时监控轮次异常: {e}")

        # 等待下一轮
        interval = config.realtime.check_interval_minutes * 60
        logger.debug(f"等待 {config.realtime.check_interval_minutes} 分钟")
        time.sleep(interval)


def main() -> None:
    """程序入口."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="千倍量化分析系统")
    parser.add_argument("--realtime", action="store_true", help="实时监控模式")
    parser.add_argument("--v2", action="store_true", help="使用 V2 管道")
    parser.add_argument("--backtest", action="store_true", help="运行回测")
    args = parser.parse_args()

    config = AppConfig()

    if args.realtime:
        run_realtime(config)
    elif args.backtest:
        results = run_backtest(config)
        for r in results:
            logger.info(f"回测结果: {r.period} 胜率={r.win_rate:.1%} 夏普={r.sharpe_ratio:.2f}")
    elif args.v2 or config.use_v2_pipeline:
        run_pipeline(config)
    else:
        # 旧流程兼容
        logger.info("使用旧版流程")
        try:
            from src.main_old import run_old_pipeline
            run_old_pipeline(config)
        except ImportError:
            logger.info("旧版流程不可用，自动切换到 V2 管道")
            run_pipeline(config)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证命令行参数**

Run: `cd "h:/code/thousand times" && python -m src.main --help`

Expected: 显示 --realtime, --v2, --backtest 选项

- [ ] **Step 3: Commit**

```bash
cd "h:/code/thousand times"
git add src/main.py
git commit -m "feat: 实现实时监控和命令行入口，支持 --realtime/--v2/--backtest"
```

---

### Task 4: 更新 pipeline 包导出

**Files:**
- Modify: `src/pipeline/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
# src/pipeline/__init__.py
"""Pipeline package - 五阶段管道架构."""
from __future__ import annotations

from src.pipeline.regime import MarketRegime, RegimeVote, judge_market_regime
from src.pipeline.collect import DataBundle, FundamentalData, stage_collect
from src.pipeline.factors import FactorScores, calc_factors, calc_ic, calc_ic_ir
from src.pipeline.signal import Signal, SignalVote, KeyPrices, generate_signals
from src.pipeline.output import stage_output, push_report

__all__ = [
    "MarketRegime",
    "RegimeVote",
    "judge_market_regime",
    "DataBundle",
    "FundamentalData",
    "stage_collect",
    "FactorScores",
    "calc_factors",
    "calc_ic",
    "calc_ic_ir",
    "Signal",
    "SignalVote",
    "KeyPrices",
    "generate_signals",
    "stage_output",
    "push_report",
]
```

- [ ] **Step 2: 验证导入**

Run: `cd "h:/code/thousand times" && python -c "from src.pipeline import MarketRegime, DataBundle, FactorScores, Signal, stage_collect, calc_factors, generate_signals, stage_output; print('ALL OK')"`

Expected: ALL OK

- [ ] **Step 3: 最终 Commit**

```bash
cd "h:/code/thousand times"
git add src/pipeline/__init__.py
git commit -m "feat: 更新 pipeline 包完整导出"
```

---

## 自检清单

- [ ] 所有测试通过: `pytest tests/test_pipeline_output.py tests/test_backtest_v2.py -v`
- [ ] 命令 `python -m src.main --help` 正常输出
- [ ] V2 管道 5 阶段正确串联
- [ ] 实时监控在非交易时段自动休眠
- [ ] 每阶段独立异常处理，单阶段失败不崩溃
- [ ] 报告包含环境、买入信号、卖出信号三部分
- [ ] 新旧双轨通过 `use_v2_pipeline` 切换
