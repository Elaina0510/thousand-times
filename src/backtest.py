"""回测引擎 — 与生产共用因子计算代码.

使用 pipeline/factors.py 和 pipeline/signal.py 进行信号计算，
消除回测与生产之间的信号不一致。

用法：
    python src/backtest.py [--pool-size 20] [--days 60] [--hold-days 1,3,5,10]
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
class BacktestTrade:
    """单笔交易记录。"""

    date: str
    code: str
    action: str  # "buy" or "sell"
    price: float
    shares: int = 0
    amount: float = 0.0
    commission: float = 0.0


@dataclass
class BacktestResult:
    """回测汇总结果。"""

    period: str = ""
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0


def calc_sharpe(returns: list[float], risk_free: float = 0.03, periods_per_year: int = 252) -> float:
    """计算年化夏普比率.

    Args:
        returns: 收益率序列（每个周期）。
        risk_free: 无风险利率（年化）。
        periods_per_year: 每年周期数。

    Returns:
        夏普比率。
    """
    if not returns or len(returns) < 2:
        return 0.0

    arr = np.array(returns)
    mean_ret = np.mean(arr)
    std_ret = np.std(arr, ddof=1)

    if std_ret == 0:
        return 0.0

    # 年化
    annualized_mean = mean_ret * periods_per_year
    annualized_std = std_ret * np.sqrt(periods_per_year)

    return (annualized_mean - risk_free) / annualized_std


def calc_max_drawdown(equity_curve: list[float]) -> float:
    """计算最大回撤.

    Args:
        equity_curve: 权益曲线。

    Returns:
        最大回撤（正数表示回撤比例）。
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def calc_calmar(avg_annual_return: float, max_dd: float) -> float:
    """计算卡玛比率.

    Args:
        avg_annual_return: 年化平均收益率。
        max_dd: 最大回撤。

    Returns:
        卡玛比率。
    """
    if max_dd == 0:
        return 0.0
    return avg_annual_return / max_dd


def calc_profit_factor(returns: list[float]) -> float:
    """计算盈亏比.

    Args:
        returns: 收益率序列。

    Returns:
        总盈利 / 总亏损，0 表示无亏损。
    """
    if not returns:
        return 0.0

    profits = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))

    if losses == 0:
        return float("inf") if profits > 0 else 0.0

    return profits / losses


def _fetch_historical_data(code: str, days: int = 300) -> pd.DataFrame:
    """获取历史行情数据.

    Args:
        code: 股票代码。
        days: 回溯天数。

    Returns:
        K线 DataFrame。
    """
    try:
        from src.baostock_data import get_stock_hist_baostock

        df = get_stock_hist_baostock(code, days=days)
        if df is None or df.empty:
            # 降级到 AKShare
            return _fetch_historical_data_akshare(code, days)
        return df
    except Exception:
        return _fetch_historical_data_akshare(code, days)


def _fetch_historical_data_akshare(code: str, days: int = 300) -> pd.DataFrame:
    """使用 AKShare 获取历史行情（降级方案）."""
    try:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",
        )

        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
        })
        return df
    except Exception as e:
        logger.warning(f"AKShare 获取 {code} 历史数据失败: {e}")
        return pd.DataFrame()


def _fetch_stock_pool_for_backtest(size: int = 50) -> pd.DataFrame:
    """获取回测用股票池."""
    try:
        import akshare as ak  # type: ignore[import-untyped]

        df = ak.stock_zh_a_spot_em()
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "代码": "code", "名称": "name",
            "总市值": "market_cap", "市盈率-动态": "pe_ttm",
        })

        df = df[~df["name"].str.contains("ST", na=False)]
        df = df[df["pe_ttm"] > 0]
        df = df[df["market_cap"] > 20e8]
        df = df.sort_values("market_cap", ascending=False).head(size)

        logger.info(f"回测股票池: {len(df)} 只")
        return df[["code", "name", "market_cap"]].reset_index(drop=True)
    except Exception as e:
        logger.warning(f"获取回测股票池失败: {e}")
        return pd.DataFrame()


def _build_data_bundle_for_date(
    code: str,
    kline_up_to_date: pd.DataFrame,
    stock_pool: pd.DataFrame,
) -> object:
    """为指定日期构造 DataBundle（最小化版本）.

    Args:
        code: 股票代码。
        kline_up_to_date: 截至当日的K线数据。
        stock_pool: 股票池 DataFrame。

    Returns:
        DataBundle 对象。
    """
    from src.pipeline.collect import DataBundle, FundamentalData

    return DataBundle(
        stock_pool=stock_pool,
        kline_cache={code: kline_up_to_date},
        fundamental_cache={code: FundamentalData()},
        index_kline=pd.DataFrame(),
        north_flow=pd.DataFrame(),
        limit_up_count=0,
        limit_down_count=0,
        advance_decline_ratio=1.0,
    )


def run_backtest(config: object) -> list[BacktestResult]:
    """运行回测.

    与生产共用 pipeline/factors.py + pipeline/signal.py。

    Args:
        config: BacktestConfig 或 AppConfig。

    Returns:
        BacktestResult 列表（按 hold_days 分组）。
    """
    # 从 config 中提取参数
    if hasattr(config, "backtest"):
        bt_config = config.backtest
    else:
        bt_config = config

    pool_size = getattr(bt_config, "pool_size", 50)
    hold_days_list = getattr(bt_config, "hold_days", [1, 3, 5, 10])
    commission_rate = getattr(bt_config, "commission_rate", 0.001)
    slippage = getattr(bt_config, "slippage", 0.001)
    initial_capital = getattr(bt_config, "initial_capital", 100000.0)

    logger.info(f"开始回测: 股票池 {pool_size} 只, 持仓天数 {hold_days_list}")

    # 获取股票池
    pool = _fetch_stock_pool_for_backtest(pool_size)
    if pool.empty:
        logger.error("股票池为空，无法回测")
        return []

    # 收集每个持仓周期的所有交易收益
    period_returns: dict[int, list[float]] = {h: [] for h in hold_days_list}
    period_equity: dict[int, list[float]] = {h: [initial_capital] for h in hold_days_list}

    for _, stock in pool.iterrows():
        code = str(stock["code"])
        name = str(stock["name"])

        # 获取历史数据
        df = _fetch_historical_data(code, 300)
        if df.empty or len(df) < 80:
            continue

        # 标准化列名
        if "收盘" in df.columns:
            close_col = "收盘"
        elif "close" in df.columns:
            close_col = "close"
        else:
            continue

        closes = df[close_col].astype(float).values
        dates = df["date"].astype(str).values if "date" in df.columns else [str(i) for i in range(len(df))]

        # 逐日扫描（从第60天开始，确保有足够数据计算指标）
        for i in range(60, len(closes) - max(hold_days_list)):
            # 构造截至当日的K线
            kline_slice = df.iloc[:i + 1].copy()

            # 构造最小 DataBundle
            single_pool = pd.DataFrame([{"code": code, "name": name}])
            bundle = _build_data_bundle_for_date(code, kline_slice, single_pool)

            # 计算因子分数（复用生产代码）
            try:
                from src.pipeline.factors import calc_factors
                scores = calc_factors(bundle, config, "sideways")
                if not scores:
                    continue
                fs = scores[0]
            except Exception:
                continue

            # 生成信号（复用生产代码）
            try:
                from src.pipeline.signal import generate_signals
                signals = generate_signals([fs], bundle, config, "sideways")
                if not signals:
                    continue
                signal = signals[0]
            except Exception:
                continue

            # 只处理买入和卖出信号
            if signal.action not in ("buy", "sell"):
                continue

            current_price = closes[i]

            # 计算各持仓周期收益
            for hold in hold_days_list:
                if i + hold < len(closes):
                    future_price = closes[i + hold]

                    # 考虑手续费和滑点
                    if signal.action == "buy":
                        entry_price = current_price * (1 + slippage)
                        exit_price = future_price * (1 - slippage)
                        cost = entry_price * commission_rate + exit_price * commission_rate
                        ret = (exit_price - entry_price) / entry_price - cost / entry_price
                    else:  # sell (做空逻辑简化为反向)
                        entry_price = current_price * (1 - slippage)
                        exit_price = future_price * (1 + slippage)
                        cost = entry_price * commission_rate + exit_price * commission_rate
                        ret = (entry_price - exit_price) / entry_price - cost / entry_price

                    period_returns[hold].append(ret * 100)  # 转为百分比

    # 汇总结果
    results = []
    for hold in hold_days_list:
        returns = period_returns[hold]
        if not returns:
            results.append(BacktestResult(period=f"{hold}天", total_signals=0))
            continue

        win_count = sum(1 for r in returns if r > 0)
        win_rate = win_count / len(returns) * 100
        avg_return = float(np.mean(returns))

        # 权益曲线
        equity = [initial_capital]
        for r in returns:
            equity.append(equity[-1] * (1 + r / 100))

        max_dd = calc_max_drawdown(equity) * 100
        sharpe = calc_sharpe(returns, periods_per_year=252 // max(hold, 1))
        pf = calc_profit_factor(returns)
        calmar = calc_calmar(avg_return * 252 / max(hold, 1), max_dd / 100)

        results.append(BacktestResult(
            period=f"{hold}天",
            total_signals=len(returns),
            buy_signals=sum(1 for r in returns if r > 0),
            sell_signals=sum(1 for r in returns if r <= 0),
            win_rate=round(win_rate, 1),
            avg_return=round(avg_return, 2),
            max_drawdown=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
            profit_factor=round(pf, 2),
            calmar_ratio=round(calmar, 2),
        ))

    return results


def print_backtest_report(results: list[BacktestResult]) -> None:
    """打印回测报告.

    Args:
        results: BacktestResult 列表。
    """
    print("\n" + "=" * 70)
    print("  V2 策略回测报告（与生产共用因子代码）")
    print("=" * 70)

    for r in results:
        print(f"\n--- {r.period} ---")
        if r.total_signals == 0:
            print("  无信号")
            continue
        print(f"  总信号数: {r.total_signals}")
        print(f"  胜率: {r.win_rate:.1f}%")
        print(f"  平均收益: {r.avg_return:+.2f}%")
        print(f"  最大回撤: {r.max_drawdown:.2f}%")
        print(f"  夏普比率: {r.sharpe_ratio:.2f}")
        print(f"  盈亏比: {r.profit_factor:.2f}")
        print(f"  卡玛比率: {r.calmar_ratio:.2f}")

    print("\n" + "=" * 70)


def main() -> None:
    """回测 CLI 入口。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="A股策略回测（V2 管道版）")
    parser.add_argument("--pool-size", type=int, default=20, help="股票池大小")
    parser.add_argument("--hold-days", type=str, default="1,3,5,10", help="持仓天数（逗号分隔）")
    parser.add_argument("--commission", type=float, default=0.001, help="手续费率")
    parser.add_argument("--slippage", type=float, default=0.001, help="滑点")
    args = parser.parse_args()

    hold_days = [int(d) for d in args.hold_days.split(",")]

    from src.config import BacktestConfig, AppConfig

    bt_config = BacktestConfig(
        pool_size=args.pool_size,
        hold_days=hold_days,
        commission_rate=args.commission,
        slippage=args.slippage,
    )
    # 包装为 AppConfig 以兼容 pipeline
    app_config = AppConfig(backtest=bt_config)

    results = run_backtest(app_config)
    print_backtest_report(results)


if __name__ == "__main__":
    main()
