"""回测框架 — 基于AKShare历史数据验证策略有效性。

使用AKShare获取历史数据，模拟策略在历史区间的表现：
- 胜率（买入后N日上涨的概率）
- 平均收益
- 最大回撤
- 夏普比率

用法：
    python src/backtest.py [--days 90] [--pool-size 50]
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger("thousand-times")


@dataclass
class BacktestConfig:
    """回测配置。"""

    lookback_days: int = 120  # 历史数据回溯天数
    hold_days: list[int] = field(default_factory=lambda: [1, 3, 5, 10])  # 持仓天数
    pool_size: int = 50  # 回测股票池大小（减少计算量）
    buy_threshold: float = 70.0  # 买入阈值
    sell_threshold: float = 30.0  # 卖出阈值


@dataclass
class BacktestResult:
    """单只股票的回测结果。"""

    code: str
    name: str
    signal_date: str  # 信号触发日期
    signal_score: float  # 信号评分
    signal_zone: str  # 买入区/观望区/卖出区
    # 各持仓周期的收益
    returns: dict[int, float]  # {hold_days: return_pct}
    # 是否触发信号
    triggered: bool


@dataclass
class BacktestSummary:
    """回测汇总。"""

    total_signals: int  # 总信号数
    buy_signals: int  # 买入信号数
    sell_signals: int  # 卖出信号数
    # 各持仓周期的统计
    period_stats: dict[int, dict]  # {hold_days: {win_rate, avg_return, max_drawdown, sharpe}}
    # 按信号分区的统计
    zone_stats: dict[str, dict]  # {zone: {count, avg_return_5d}}
    # 所有结果
    results: list[BacktestResult] = field(default_factory=list)


def _fetch_historical_data(code: str, days: int = 120) -> pd.DataFrame:
    """使用AKShare获取历史行情。

    Args:
        code: 股票代码。
        days: 回溯天数。

    Returns:
        历史行情DataFrame。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped]

        # AKShare 需要带市场前缀
        if code.startswith("6") or code.startswith("5"):
            symbol = f"sh{code}"
        else:
            symbol = f"sz{code}"

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",  # 前复权
        )

        if df.empty:
            return pd.DataFrame()

        # 标准化列名
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        })

        return df

    except Exception as e:
        logger.warning(f"AKShare 获取 {code} 历史数据失败: {e}")
        return pd.DataFrame()


def _fetch_stock_pool_for_backtest(size: int = 50) -> pd.DataFrame:
    """获取回测用的股票池。

    使用AKShare获取当前A股股票列表，按市值取前N只。

    Args:
        size: 股票池大小。

    Returns:
        股票池DataFrame。
    """
    try:
        import akshare as ak  # type: ignore[import-untyped

        # 获取A股实时行情（含市值）
        df = ak.stock_zh_a_spot_em()

        if df.empty:
            return pd.DataFrame()

        # 标准化列名
        df = df.rename(columns={
            "代码": "code",
            "名称": "name",
            "总市值": "market_cap",
            "市盈率-动态": "pe_ttm",
        })

        # 过滤：非ST、PE>0、市值>20亿
        df = df[~df["name"].str.contains("ST", na=False)]
        df = df[df["pe_ttm"] > 0]
        df = df[df["market_cap"] > 20e8]

        # 按市值降序取前N只
        df = df.sort_values("market_cap", ascending=False).head(size)

        logger.info(f"回测股票池: {len(df)} 只")
        return df[["code", "name", "market_cap"]].reset_index(drop=True)

    except Exception as e:
        logger.warning(f"获取回测股票池失败: {e}")
        return pd.DataFrame()


def _calc_signals_at_date(
    closes: np.ndarray,
    volumes: np.ndarray,
    date_idx: int,
) -> dict:
    """在指定日期计算技术信号（简化版，用于回测）。

    Args:
        closes: 收盘价序列。
        volumes: 成交量序列。
        date_idx: 当前日期索引。

    Returns:
        技术信号字典。
    """
    if date_idx < 20:
        return {"score": 0, "signals": {}}

    window = closes[:date_idx + 1]
    vol_window = volumes[:date_idx + 1]

    # MA
    ma5 = np.mean(window[-5:])
    ma10 = np.mean(window[-10:])
    ma20 = np.mean(window[-20:])

    # MACD (简化)
    ema12 = window[-1]  # 简化
    ema26 = window[-1]
    if len(window) >= 12:
        ema12 = np.mean(window[-12:])
    if len(window) >= 26:
        ema26 = np.mean(window[-26:])
    dif = ema12 - ema26

    # 量比
    avg_vol_5 = np.mean(vol_window[-6:-1]) if len(vol_window) >= 6 else np.mean(vol_window[-5:])
    vol_ratio = vol_window[-1] / avg_vol_5 if avg_vol_5 > 0 else 0

    # 涨跌幅
    change_pct = (window[-1] - window[-2]) / window[-2] * 100 if len(window) >= 2 else 0

    # 评分
    score = 0.0
    signals = {}

    if ma5 > ma10:
        score += 5.0
        signals["ma_golden"] = True

    if window[-1] > ma20:
        score += 3.0
        signals["above_ma20"] = True

    if ma5 > ma10 > ma20:
        score += 5.0
        signals["bullish_alignment"] = True

    if dif > 0:
        score += 3.0
        signals["dif_positive"] = True

    if change_pct > 0 and vol_ratio > 1.5:
        score += 4.0
        signals["volume_up"] = True

    if change_pct < -2 and vol_ratio > 2.0:
        score -= 4.0
        signals["volume_down"] = True

    return {"score": max(0, score), "signals": signals}


def run_backtest(config: BacktestConfig) -> BacktestSummary:
    """运行回测。

    Args:
        config: 回测配置。

    Returns:
        回测汇总结果。
    """
    logger.info(f"开始回测: 回溯{config.lookback_days}天, 股票池{config.pool_size}只")

    # 获取股票池
    pool = _fetch_stock_pool_for_backtest(config.pool_size)
    if pool.empty:
        logger.error("股票池为空，无法回测")
        return BacktestSummary(
            total_signals=0, buy_signals=0, sell_signals=0,
            period_stats={}, zone_stats={},
        )

    all_results: list[BacktestResult] = []

    for _, stock in pool.iterrows():
        code = str(stock["code"])
        name = str(stock["name"])

        # 获取历史数据
        df = _fetch_historical_data(code, config.lookback_days + 30)  # 多取30天用于计算指标
        if df.empty or len(df) < 30:
            continue

        closes = df["close"].astype(float).values
        volumes = df["volume"].astype(float).values
        dates = df["date"].astype(str).values

        # 逐日扫描信号
        for i in range(60, len(closes) - max(config.hold_days)):
            signal = _calc_signals_at_date(closes, volumes, i)
            score = signal["score"]

            # 判断信号区间
            if score >= config.buy_threshold:
                zone = "买入区"
            elif score >= config.sell_threshold:
                zone = "观望区"
            else:
                zone = "卖出区"

            # 只记录买入区和卖出区的信号
            if zone in ("买入区", "卖出区"):
                # 计算各持仓周期的收益
                returns = {}
                for hold in config.hold_days:
                    if i + hold < len(closes):
                        ret = (closes[i + hold] - closes[i]) / closes[i] * 100
                        returns[hold] = round(ret, 2)

                all_results.append(BacktestResult(
                    code=code,
                    name=name,
                    signal_date=dates[i],
                    signal_score=score,
                    signal_zone=zone,
                    returns=returns,
                    triggered=True,
                ))

    # 汇总统计
    return _summarize_results(all_results, config)


def _summarize_results(
    results: list[BacktestResult], config: BacktestConfig
) -> BacktestSummary:
    """汇总回测结果。

    Args:
        results: 所有回测结果。
        config: 回测配置。

    Returns:
        回测汇总。
    """
    buy_results = [r for r in results if r.signal_zone == "买入区"]
    sell_results = [r for r in results if r.signal_zone == "卖出区"]

    # 各持仓周期统计
    period_stats: dict[int, dict] = {}
    for hold in config.hold_days:
        buy_returns = [r.returns.get(hold, 0) for r in buy_results if hold in r.returns]
        sell_returns = [r.returns.get(hold, 0) for r in sell_results if hold in r.returns]

        if buy_returns:
            win_rate = sum(1 for r in buy_returns if r > 0) / len(buy_returns) * 100
            avg_return = np.mean(buy_returns)
            max_drawdown = min(buy_returns) if buy_returns else 0

            # 夏普比率（简化：假设无风险利率3%年化）
            if len(buy_returns) > 1:
                std = np.std(buy_returns)
                sharpe = (avg_return - 3 * hold / 252) / std if std > 0 else 0
            else:
                sharpe = 0

            period_stats[hold] = {
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_return, 2),
                "max_drawdown": round(max_drawdown, 2),
                "sharpe": round(sharpe, 2),
                "sample_size": len(buy_returns),
            }

    # 按信号分区统计
    zone_stats: dict[str, dict] = {}
    for zone in ("买入区", "卖出区"):
        zone_results = [r for r in results if r.signal_zone == zone]
        zone_returns_5d = [r.returns.get(5, 0) for r in zone_results if 5 in r.returns]
        zone_stats[zone] = {
            "count": len(zone_results),
            "avg_return_5d": round(np.mean(zone_returns_5d), 2) if zone_returns_5d else 0,
        }

    return BacktestSummary(
        total_signals=len(results),
        buy_signals=len(buy_results),
        sell_signals=len(sell_results),
        period_stats=period_stats,
        zone_stats=zone_stats,
        results=results,
    )


def print_backtest_report(summary: BacktestSummary) -> None:
    """打印回测报告。

    Args:
        summary: 回测汇总结果。
    """
    print("\n" + "=" * 60)
    print("  策略回测报告")
    print("=" * 60)

    print(f"\n总信号数: {summary.total_signals}")
    print(f"  买入信号: {summary.buy_signals}")
    print(f"  卖出信号: {summary.sell_signals}")

    print("\n--- 买入信号各持仓周期表现 ---")
    print(f"{'持仓天数':>8} | {'胜率':>6} | {'平均收益':>8} | {'最大回撤':>8} | {'夏普比':>6} | {'样本数':>6}")
    print("-" * 60)
    for hold, stats in sorted(summary.period_stats.items()):
        print(
            f"{hold:>8}天 | "
            f"{stats['win_rate']:>5.1f}% | "
            f"{stats['avg_return']:>+7.2f}% | "
            f"{stats['max_drawdown']:>+7.2f}% | "
            f"{stats['sharpe']:>6.2f} | "
            f"{stats['sample_size']:>6}"
        )

    print("\n--- 信号分区统计 ---")
    for zone, stats in summary.zone_stats.items():
        print(f"  {zone}: {stats['count']}个信号, 5日平均收益 {stats['avg_return_5d']:+.2f}%")

    print("\n" + "=" * 60)


def main() -> None:
    """回测主入口。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="A股策略回测")
    parser.add_argument("--days", type=int, default=120, help="历史回溯天数")
    parser.add_argument("--pool-size", type=int, default=50, help="股票池大小")
    parser.add_argument("--buy-threshold", type=float, default=70.0, help="买入阈值")
    parser.add_argument("--sell-threshold", type=float, default=30.0, help="卖出阈值")
    args = parser.parse_args()

    config = BacktestConfig(
        lookback_days=args.days,
        pool_size=args.pool_size,
        buy_threshold=args.buy_threshold,
        sell_threshold=args.sell_threshold,
    )

    summary = run_backtest(config)
    print_backtest_report(summary)


if __name__ == "__main__":
    main()
