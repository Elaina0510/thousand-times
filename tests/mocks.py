"""测试 Mock 基础设施 — 无 BaoStock 运行核心流程。

提供工厂函数和 mock 模块，使测试可以在没有 BaoStock/AKShare 网络连接的情况下
运行完整的分析流水线。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from config import AppConfig, FilterConfig
from etf_analyzer import EtfInfo
from fundamental_analysis import FundamentalData
from news_analysis import NewsItem, PolicyImpact
from scoring import ScoreResult, TechnicalSignals
from technical_analysis import KlineData


# ─────────────────────────────────────────────
# 1. 数据工厂函数
# ─────────────────────────────────────────────


def make_stock_pool_df(n: int = 5) -> pd.DataFrame:
    """创建测试用股票池 DataFrame。

    Args:
        n: 股票数量。

    Returns:
        包含 code, name, market_cap, pe_ttm, pb, industry 列的 DataFrame。
    """
    stocks = [
        ("600519", "贵州茅台", 2000e8, 28.5, 10.5, "白酒"),
        ("000858", "五粮液", 800e8, 25.0, 8.0, "白酒"),
        ("601318", "中国平安", 1500e8, 15.0, 2.0, "金融"),
        ("000001", "平安银行", 300e8, 8.5, 0.8, "银行"),
        ("002475", "立讯精密", 600e8, 35.0, 6.0, "电子"),
        ("300750", "宁德时代", 1200e8, 40.0, 8.0, "新能源"),
        ("601012", "隆基绿能", 400e8, 20.0, 3.0, "光伏"),
        ("002594", "比亚迪", 900e8, 30.0, 5.0, "汽车"),
        ("600036", "招商银行", 700e8, 10.0, 1.5, "银行"),
        ("000333", "美的集团", 500e8, 12.0, 3.0, "家电"),
    ]
    rows = stocks[:n]
    return pd.DataFrame(rows, columns=["code", "name", "market_cap", "pe_ttm", "pb", "industry"])


def make_kline_data(
    n: int = 60,
    trend: str = "up",
    base_price: float = 100.0,
) -> KlineData:
    """创建测试用 K 线数据。

    Args:
        n: 数据天数。
        trend: 趋势方向 ("up", "down", "sideways")。
        base_price: 基准价格。

    Returns:
        KlineData 对象。
    """
    np.random.seed(42)
    dates = [(datetime.now() - timedelta(days=n - i)).strftime("%Y-%m-%d") for i in range(n)]

    if trend == "up":
        closes = base_price + np.cumsum(np.abs(np.random.randn(n)) * 0.5)
    elif trend == "down":
        closes = base_price - np.cumsum(np.abs(np.random.randn(n)) * 0.5)
    else:
        closes = base_price + np.cumsum(np.random.randn(n) * 0.3)

    closes = np.maximum(closes, 1.0)  # 确保价格为正
    opens = closes + np.random.randn(n) * 0.2
    highs = np.maximum(closes, opens) + np.abs(np.random.randn(n) * 0.5)
    lows = np.minimum(closes, opens) - np.abs(np.random.randn(n) * 0.5)
    volumes = np.random.randint(500000, 3000000, n).astype(float)

    # 计算 MA
    close_series = pd.Series(closes)
    ma5 = close_series.rolling(5, min_periods=1).mean().tolist()
    ma10 = close_series.rolling(10, min_periods=1).mean().tolist()
    ma20 = close_series.rolling(20, min_periods=1).mean().tolist()
    ma60 = close_series.rolling(60, min_periods=60).mean().tolist()

    # 计算 MACD
    ema12 = close_series.ewm(span=12, adjust=False).mean()
    ema26 = close_series.ewm(span=26, adjust=False).mean()
    dif = (ema12 - ema26).tolist()
    dea = pd.Series(dif).ewm(span=9, adjust=False).mean().tolist()
    macd_hist = [(d - e) * 2 for d, e in zip(dif, dea)]

    # 计算 ATR
    high_s = pd.Series(highs)
    low_s = pd.Series(lows)
    prev_close = close_series.shift(1)
    tr = pd.concat([high_s - low_s, (high_s - prev_close).abs(), (low_s - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean().tolist()

    # 布林带
    mid = close_series.rolling(20, min_periods=1).mean()
    std = close_series.rolling(20, min_periods=1).std()
    bb_upper = (mid + 2 * std).tolist()
    bb_lower = (mid - 2 * std).tolist()
    bb_width = (((mid + 2 * std) - (mid - 2 * std)) / mid * 100).tolist()

    return KlineData(
        dates=dates,
        opens=opens.tolist(),
        highs=highs.tolist(),
        lows=lows.tolist(),
        closes=closes.tolist(),
        volumes=volumes.tolist(),
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        dif=dif,
        dea=dea,
        macd_hist=macd_hist,
        atr=atr,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        bb_width=bb_width,
    )


def make_kline_dataframe(n: int = 60, trend: str = "up") -> pd.DataFrame:
    """创建测试用 K 线 DataFrame（BaoStock 格式）。

    Args:
        n: 数据天数。
        trend: 趋势方向。

    Returns:
        包含 日期, 开盘, 收盘, 最高, 最低, 成交量 列的 DataFrame。
    """
    kline = make_kline_data(n=n, trend=trend)
    return pd.DataFrame({
        "日期": kline.dates,
        "开盘": kline.opens,
        "收盘": kline.closes,
        "最高": kline.highs,
        "最低": kline.lows,
        "成交量": kline.volumes,
    })


def make_etf_info(code: str = "512480", name: str = "半导体ETF") -> EtfInfo:
    """创建测试用 ETF 信息。"""
    return EtfInfo(code=code, name=name, current_price=1.5, change_pct=2.0)


def make_fundamental_data(
    roe: float = 18.0,
    eps: float = 2.5,
    profit_growth: float | None = 25.0,
    revenue_growth: float | None = 20.0,
) -> FundamentalData:
    """创建测试用基本面数据。"""
    return FundamentalData(
        roe=roe, eps=eps, market_cap=100e8,
        profit_growth=profit_growth, revenue_growth=revenue_growth,
        debt_ratio=55.0, cash_flow=1.2, gross_margin=45.0,
    )


def make_policy_impact(
    industries: list[str] | None = None,
    score: float = 17.5,
    direction: str = "positive",
) -> PolicyImpact:
    """创建测试用政策影响。"""
    return PolicyImpact(
        news_title="消费刺激政策",
        affected_industries=industries or ["白酒", "消费"],
        impact_direction=direction,
        impact_degree="direct",
        impact_score=score,
        summary="利好白酒板块",
    )


def make_score_result(
    code: str = "600519",
    name: str = "贵州茅台",
    is_etf: bool = False,
    total_score: float = 75.0,
) -> ScoreResult:
    """创建测试用评分结果。"""
    return ScoreResult(
        code=code, name=name, is_etf=is_etf,
        technical_score=35.0,
        fundamental_score=25.0 if not is_etf else None,
        news_score=17.5,
        industry_score=9.0 if not is_etf else None,
        fund_flow_score=8.0 if is_etf else None,
        total_score=total_score,
        profit_probability=68.0,
        judgment="strong_buy" if total_score >= 75 else "buy" if total_score >= 60 else "hold",
        technical_signals=TechnicalSignals(
            ma5_10_golden=True,
            macd_golden=True,
            above_ma20=True,
            volume_up=True,
        ),
        news_summary="利好",
    )


# ─────────────────────────────────────────────
# 2. Mock 模块注册
# ─────────────────────────────────────────────


def register_mock_baostock(monkeypatch: "pytest.MonkeyPatch") -> MagicMock:
    """注册 mock baostock 模块到 sys.modules。

    Args:
        monkeypatch: pytest monkeypatch fixture。

    Returns:
        mock baostock 模块对象。
    """
    mock_bs = ModuleType("baostock")

    # 模拟 login/logout
    mock_result = MagicMock()
    mock_result.error_code = "0"
    mock_result.error_msg = ""
    mock_result.fields = ["date", "open", "high", "low", "close", "volume"]
    mock_result.next = MagicMock(return_value=False)
    mock_result.get_row_data = MagicMock(return_value=[])

    mock_bs.login = MagicMock(return_value=mock_result)
    mock_bs.logout = MagicMock()
    mock_bs.query_history_k_data_plus = MagicMock(return_value=mock_result)
    mock_bs.query_stock_basic = MagicMock(return_value=mock_result)
    mock_bs.query_stock_industry = MagicMock(return_value=mock_result)
    mock_bs.query_profit_data = MagicMock(return_value=mock_result)
    mock_bs.query_growth_data = MagicMock(return_value=mock_result)

    monkeypatch.setitem(sys.modules, "baostock", mock_bs)
    return mock_bs


def register_mock_akshare(monkeypatch: "pytest.MonkeyPatch") -> MagicMock:
    """注册 mock akshare 模块到 sys.modules。

    Args:
        monkeypatch: pytest monkeypatch fixture。

    Returns:
        mock akshare 模块对象。
    """
    mock_ak = ModuleType("akshare")
    mock_ak.stock_zh_a_spot_em = MagicMock(return_value=pd.DataFrame())
    mock_ak.stock_info_a_code_name = MagicMock(return_value=pd.DataFrame())
    mock_ak.stock_news_em = MagicMock(return_value=pd.DataFrame())
    mock_ak.fund_etf_fund_daily_em = MagicMock(return_value=pd.DataFrame())

    monkeypatch.setitem(sys.modules, "akshare", mock_ak)
    return mock_ak


def register_mock_remote_data(monkeypatch: "pytest.MonkeyPatch") -> None:
    """注册 mock remote_data 模块到 sys.modules。"""
    mock_remote = ModuleType("remote_data")
    mock_remote.is_remote_available = MagicMock(return_value=False)  # type: ignore[attr-defined]
    mock_remote.get_stock_spot_remote = MagicMock()  # type: ignore[attr-defined]
    mock_remote.get_news_remote = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "remote_data", mock_remote)


def register_all_mocks(monkeypatch: "pytest.MonkeyPatch") -> tuple[MagicMock, MagicMock]:
    """注册所有外部依赖的 mock 模块。

    Args:
        monkeypatch: pytest monkeypatch fixture。

    Returns:
        (mock_baostock, mock_akshare) 元组。
    """
    mock_bs = register_mock_baostock(monkeypatch)
    mock_ak = register_mock_akshare(monkeypatch)
    register_mock_remote_data(monkeypatch)
    return mock_bs, mock_ak


# ─────────────────────────────────────────────
# 3. 端到端运行辅助
# ─────────────────────────────────────────────


def run_main_mocked(monkeypatch: "pytest.MonkeyPatch", config: AppConfig | None = None) -> None:
    """在完全 mock 环境中运行 main()。

    所有外部 API 调用都被 mock，不需要网络连接。

    Args:
        monkeypatch: pytest monkeypatch fixture。
        config: 可选的 AppConfig 覆盖。
    """
    register_all_mocks(monkeypatch)

    if config is None:
        config = AppConfig()

    monkeypatch.setattr("main.load_config", lambda: config)
    monkeypatch.setattr("main.get_stock_pool", lambda cfg: make_stock_pool_df(5))
    monkeypatch.setattr("main.get_etf_pool", lambda cfg: ([make_etf_info()], {}))
    monkeypatch.setattr("main.fetch_news", lambda: [])
    monkeypatch.setattr("main.filter_by_credibility", lambda news: news)
    monkeypatch.setattr("main.analyze_policy_impact", lambda news, cfg: [])
    monkeypatch.setattr("main.push_to_wechat", lambda **kwargs: True)
    monkeypatch.setattr("main.generate_chart", lambda *a, **kw: "charts/test.png")

    # Mock K线数据获取
    kline_df = make_kline_dataframe(60, "up")
    monkeypatch.setattr(
        "main.get_stock_hist_batch_baostock",
        lambda codes, days=60: {code: kline_df for code in codes},
    )

    # Mock 基本面数据获取
    fund_data = make_fundamental_data()
    monkeypatch.setattr(
        "main.get_fundamental_data_batch",
        lambda codes: {code: fund_data for code in codes},
    )

    # Mock 缓存
    monkeypatch.setattr("main.clear_expired_cache", lambda: None)
    monkeypatch.setattr("main.load_kline_cache_with_meta", lambda key: (None, None))
    monkeypatch.setattr("main.save_kline_cache_with_meta", lambda *a: None)
    monkeypatch.setattr("main.load_previous_kline_cache", lambda date: None)
    monkeypatch.setattr("main.get_cached_data", lambda *a, **kw: None)
    monkeypatch.setattr("main.set_cached_data", lambda *a, **kw: None)
    monkeypatch.setattr("main.log_cache_stats", lambda: None)

    # Mock HTML 报告
    monkeypatch.setattr("main.generate_html_report", lambda **kw: "public/report.html")

    from main import main
    main()
