"""历史信号追踪模块 — 记录买卖信号并计算历史准确率。"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from buy_sell_signal import HistoricalAccuracy

logger = logging.getLogger("thousand-times")

# 历史数据存储路径
HISTORY_DIR = "data"
HISTORY_FILE = os.path.join(HISTORY_DIR, "signal_history.json")


def load_signal_history() -> dict[str, list[dict]]:
    """加载历史信号数据。

    Returns:
        股票代码到信号记录列表的映射。
    """
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"加载历史数据失败: {e}")
        return {}


def save_signal_history(history: dict[str, list[dict]]) -> None:
    """保存历史信号数据。

    Args:
        history: 股票代码到信号记录列表的映射。
    """
    # 确保目录存在（包括子目录）
    dir_path = os.path.dirname(HISTORY_FILE)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    else:
        os.makedirs(HISTORY_DIR, exist_ok=True)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存历史数据失败: {e}")


def record_signal(
    code: str,
    signal_score: int,
    price: float,
    date: str,
) -> None:
    """记录单只股票的信号。

    Args:
        code: 股票代码。
        signal_score: 信号评分（0-100）。
        price: 信号时的价格。
        date: 信号日期（YYYY-MM-DD 格式）。
    """
    history = load_signal_history()

    if code not in history:
        history[code] = []

    history[code].append({
        "date": date,
        "signal_score": signal_score,
        "price": price,
    })

    # 只保留最近365天的数据
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    history[code] = [r for r in history[code] if r["date"] >= cutoff]

    save_signal_history(history)


def record_signals_batch(records: list[tuple[str, int, float, str]]) -> None:
    """批量记录多只股票的信号。只读写文件一次，避免多次I/O。

    Args:
        records: [(code, signal_score, price, date), ...] 元组列表。
    """
    if not records:
        return

    history = load_signal_history()
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    for code, signal_score, price, date in records:
        if code not in history:
            history[code] = []
        history[code].append({
            "date": date,
            "signal_score": signal_score,
            "price": price,
        })
        # 清理过期数据
        history[code] = [r for r in history[code] if r["date"] >= cutoff]

    save_signal_history(history)
    logger.info(f"批量记录 {len(records)} 条信号完成")


def calculate_historical_accuracy(
    code: str,
    periods: list[int] | None = None,
) -> list[HistoricalAccuracy]:
    """计算历史准确率。

    使用区间最优价计算：
    - 买入信号（>=70）：看5天内最高价，如果最高价 > 信号时价格 → 准确
    - 卖出信号（<30）：看5天内最低价，如果最低价 < 信号时价格 → 准确
    - 观望信号：不计入准确率

    Args:
        code: 股票代码。
        periods: 计算周期列表（天数），默认 [30, 90, 180]。

    Returns:
        各周期的历史准确率列表。
    """
    if periods is None:
        periods = [30, 90, 180]

    history = load_signal_history()
    if code not in history:
        return [HistoricalAccuracy(p, 0.0, 0.0, 0) for p in periods]

    records = history[code]
    # 按日期排序，方便查找区间数据
    records_by_date: dict[str, dict] = {r["date"]: r for r in records}

    results: list[HistoricalAccuracy] = []
    for period in periods:
        cutoff = (datetime.now() - timedelta(days=period)).strftime("%Y-%m-%d")
        period_records = [r for r in records if r["date"] >= cutoff]

        if not period_records:
            results.append(HistoricalAccuracy(period, 0.0, 0.0, 0))
            continue

        correct = 0
        total_return = 0.0
        valid_signals = 0

        for record in period_records:
            signal_score = record["signal_score"]
            signal_price = record["price"]

            # 只统计买入或卖出信号
            if signal_score >= 70 or signal_score < 30:
                # 获取信号后5天内的所有价格数据（排除信号当天）
                signal_date = datetime.strptime(record["date"], "%Y-%m-%d")
                future_prices: list[float] = []
                for day_offset in range(1, 6):
                    future_date = (signal_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                    if future_date in records_by_date:
                        future_prices.append(records_by_date[future_date]["price"])

                if not future_prices:
                    # 没有后续价格数据，跳过此信号
                    continue

                if signal_score >= 70:
                    # 买入信号：看5天内最高价
                    best_price = max(future_prices)
                    actual_return = (best_price / signal_price - 1) * 100
                    if best_price > signal_price:
                        correct += 1
                else:
                    # 卖出信号：看5天内最低价
                    best_price = min(future_prices)
                    actual_return = (best_price / signal_price - 1) * 100
                    if best_price < signal_price:
                        correct += 1

                total_return += actual_return
                valid_signals += 1

        accuracy_rate = (correct / valid_signals * 100) if valid_signals > 0 else 0.0
        avg_return = (total_return / valid_signals) if valid_signals > 0 else 0.0

        results.append(HistoricalAccuracy(
            period_days=period,
            accuracy_rate=round(accuracy_rate, 1),
            avg_return=round(avg_return, 2),
            total_signals=valid_signals,
        ))

    return results
