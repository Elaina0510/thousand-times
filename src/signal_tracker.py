"""信号跟踪模块 — 记录推荐历史并计算回顾表现。"""
from __future__ import annotations
import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("thousand-times")

DB_PATH = "cache/recommendations.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动创建表。

    Returns:
        SQLite 连接对象。
    """
    os.makedirs("cache", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            date TEXT, code TEXT, name TEXT, action TEXT,
            score REAL, price REAL,
            PRIMARY KEY (date, code)
        )
    """)
    return conn


def record_signals(signals: list[dict]) -> None:
    """批量记录信号。

    Args:
        signals: 信号列表，每个元素包含 code, name, action, score, price, date 字段。
    """
    if not signals:
        return
    try:
        conn = _get_conn()
        for s in signals:
            conn.execute(
                "INSERT OR REPLACE INTO recommendations VALUES (?,?,?,?,?,?)",
                (s["date"], s["code"], s["name"], s["action"], s["score"], s["price"])
            )
        conn.commit()
        conn.close()
        logger.info(f"信号记录完成: {len(signals)} 条")
    except Exception as e:
        logger.warning(f"信号记录失败: {e}")


def get_yesterday_recommendations(today: str) -> list[dict]:
    """获取昨日的推荐信号。

    Args:
        today: 今天的日期字符串，格式 YYYY-MM-DD。

    Returns:
        昨日推荐信号列表，每个元素包含 code, name, action, score, price。
    """
    try:
        yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = _get_conn()
        cur = conn.execute(
            "SELECT code, name, action, score, price FROM recommendations WHERE date = ?",
            (yesterday,)
        )
        rows = [{"code": r[0], "name": r[1], "action": r[2], "score": r[3], "price": r[4]}
                for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []
