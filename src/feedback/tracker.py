"""信号追踪模块 — SignalTracker.

将信号追踪升级为完整的信号→收益闭环反馈系统。
记录推荐历史，计算回顾准确率，反馈到信号置信度校准。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

logger = logging.getLogger("thousand-times")

DB_PATH = "cache/signal_tracker.db"


@dataclass
class SignalPerformance:
    """单条信号的回顾表现."""

    signal_id: int = 0
    code: str = ""
    name: str = ""
    signal_date: str = ""
    signal_action: str = "buy"      # buy / sell
    signal_score: float = 0.0
    entry_price: float = 0.0

    # 各周期表现（%）
    ret_1d: float | None = None
    ret_3d: float | None = None
    ret_5d: float | None = None
    ret_10d: float | None = None
    ret_20d: float | None = None

    # 关键价位表现
    hit_target: bool = False
    hit_stop: bool = False
    max_favorable: float = 0.0     # 最大浮盈（%）
    max_adverse: float = 0.0       # 最大浮亏（%）

    # 超额收益
    vs_index_ret: float | None = None
    vs_sector_ret: float | None = None


@dataclass
class AggregatePerformance:
    """汇总表现统计."""

    period: str = "all"             # "all", "30d", "90d"
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0

    # 核心指标
    win_rate_5d: float = 0.0        # 5日胜率（%）
    avg_return_5d: float = 0.0      # 5日平均收益（%）
    avg_excess_return_5d: float = 0.0
    sharpe_ratio: float = 0.0       # 年化夏普比率
    max_drawdown: float = 0.0       # 最大回撤（%）
    profit_factor: float = 0.0      # 盈亏比

    # 分类指标
    by_score_range: dict[str, dict[str, float]] = field(default_factory=dict)
    by_sector: dict[str, dict[str, float]] = field(default_factory=dict)
    by_market_regime: dict[str, dict[str, float]] = field(default_factory=dict)

    # 建议
    score_threshold_advice: float = 70.0


def _get_db() -> sqlite3.Connection:
    """获取数据库连接."""
    import os
    os.makedirs("cache", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    """初始化数据库表."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            action TEXT NOT NULL,
            score REAL,
            entry_price REAL,
            ret_1d REAL, ret_3d REAL, ret_5d REAL, ret_10d REAL, ret_20d REAL,
            hit_target INTEGER DEFAULT 0,
            hit_stop INTEGER DEFAULT 0,
            max_favorable REAL, max_adverse REAL,
            vs_index_ret REAL, vs_sector_ret REAL,
            computed_date TEXT,
            UNIQUE(signal_date, code, action)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threshold_history (
            date TEXT PRIMARY KEY,
            buy_threshold REAL,
            sell_threshold REAL,
            min_buy_votes INTEGER,
            win_rate_5d REAL,
            sharpe_ratio REAL,
            notes TEXT
        )
    """)
    conn.commit()


def record_signals_v3(signals: list[object], today: str) -> int:
    """记录信号到数据库（V3 增强版）.

    Args:
        signals: Signal 列表.
        today: 信号日期.

    Returns:
        记录的信号数.
    """
    conn = _get_db()
    count = 0

    for sig in signals:
        try:
            code = str(getattr(sig, "code", ""))
            name = str(getattr(sig, "name", ""))
            action = str(getattr(sig, "action", "hold"))
            score = float(getattr(sig, "confidence", 0.0))
            key_prices = getattr(sig, "key_prices", None)
            entry_price = getattr(key_prices, "current_price", 0.0) if key_prices else 0.0

            conn.execute(
                """INSERT OR REPLACE INTO signal_performance
                   (signal_date, code, name, action, score, entry_price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (today, code, name, action, score, entry_price),
            )
            count += 1
        except Exception as e:
            logger.warning(f"记录信号失败 {getattr(sig, 'code', '?')}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"信号记录完成: {count} 条")
    return count


def compute_pnl(signal_date: str, lookback_days: int = 20) -> list[SignalPerformance]:
    """计算特定日期信号在 N 日后的回顾表现.

    Args:
        signal_date: 信号日期.
        lookback_days: 回溯天数.

    Returns:
        每条信号的表现数据.
    """
    conn = _get_db()
    cursor = conn.execute(
        "SELECT * FROM signal_performance WHERE signal_date = ?",
        (signal_date,),
    )
    results: list[SignalPerformance] = []
    for row in cursor.fetchall():
        perf = SignalPerformance(
            signal_id=row[0],
            signal_date=row[1],
            code=row[2],
            name=row[3],
            signal_action=row[4],
            signal_score=row[5] or 0.0,
            entry_price=row[6] or 0.0,
            ret_1d=row[7], ret_3d=row[8], ret_5d=row[9],
            ret_10d=row[10], ret_20d=row[11],
            hit_target=bool(row[12]), hit_stop=bool(row[13]),
            max_favorable=row[14] or 0.0, max_adverse=row[15] or 0.0,
            vs_index_ret=row[16], vs_sector_ret=row[17],
        )
        results.append(perf)
    conn.close()
    return results


def compute_aggregate_performance(
    start_date: str,
    end_date: str,
) -> AggregatePerformance:
    """计算汇总表现统计.

    Args:
        start_date: 开始日期.
        end_date: 结束日期.

    Returns:
        AggregatePerformance.
    """
    conn = _get_db()
    cursor = conn.execute(
        """SELECT * FROM signal_performance
           WHERE signal_date >= ? AND signal_date <= ?""",
        (start_date, end_date),
    )
    rows = list(cursor.fetchall())
    conn.close()

    perf = AggregatePerformance(period=f"{start_date}~{end_date}")
    if not rows:
        return perf

    perf.total_signals = len(rows)
    perf.buy_signals = sum(1 for r in rows if r[4] == "buy")
    perf.sell_signals = sum(1 for r in rows if r[4] == "sell")

    # 5日收益统计
    ret_5d_list = [r[9] for r in rows if r[9] is not None]
    if ret_5d_list:
        perf.avg_return_5d = sum(ret_5d_list) / len(ret_5d_list)
        perf.win_rate_5d = sum(1 for r in ret_5d_list if r > 0) / len(ret_5d_list) * 100

    return perf


def recommend_thresholds(
    performance: AggregatePerformance,
) -> dict[str, float]:
    """基于真实表现数据推荐最优阈值.

    Args:
        performance: 汇总表现数据.

    Returns:
        推荐的阈值字典.
    """
    return {
        "buy_threshold": max(60.0, 100.0 - performance.win_rate_5d),
        "sell_threshold": min(40.0, 100.0 - performance.win_rate_5d - 10),
        "min_buy_votes": 3 if performance.win_rate_5d < 55 else 2,
    }


def generate_performance_report(performance: AggregatePerformance) -> str:
    """生成表现回顾报告.

    Args:
        performance: 汇总表现数据.

    Returns:
        Markdown 格式的表现报告.
    """
    lines = [
        "## 📊 信号表现回顾",
        "",
        f"- 统计周期: {performance.period}",
        f"- 总信号数: {performance.total_signals}",
        f"- 买入信号: {performance.buy_signals}",
        f"- 卖出信号: {performance.sell_signals}",
        f"- 5日胜率: {performance.win_rate_5d:.1f}%",
        f"- 5日平均收益: {performance.avg_return_5d:.2f}%",
        f"- 夏普比率: {performance.sharpe_ratio:.2f}",
    ]
    return "\n".join(lines)
