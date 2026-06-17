"""chart_generator.py 单元测试。"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from chart_generator import generate_chart
from technical_analysis import KlineData


def _make_kline_data(n: int = 60) -> KlineData:
    """创建测试用K线数据。"""
    import numpy as np
    import pandas as pd

    np.random.seed(42)
    dates = [d.strftime("%Y-%m-%d") for d in pd.date_range("2026-01-01", periods=n, freq="B")]
    closes = 100 + np.cumsum(np.random.randn(n) * 2)
    opens = closes + np.random.randn(n) * 0.5
    highs = closes + np.abs(np.random.randn(n) * 2)
    lows = closes - np.abs(np.random.randn(n) * 2)
    volumes = np.random.randint(500000, 2000000, n).astype(float)

    # 计算MA
    def _calc_ma(data: np.ndarray, window: int) -> np.ndarray:
        """计算移动平均线，保持长度一致。"""
        ma = np.convolve(data, np.ones(window) / window, mode="valid")
        # 前面用第一个值填充
        return np.concatenate([np.full(window - 1, ma[0]), ma])

    ma5 = _calc_ma(closes, min(5, n))
    ma10 = _calc_ma(closes, min(10, n))
    ma20 = _calc_ma(closes, min(20, n))
    ma60 = _calc_ma(closes, min(60, n))

    # 计算MACD
    ema12 = closes.copy()
    ema26 = closes.copy()
    for i in range(1, n):
        ema12[i] = ema12[i - 1] * (1 - 2 / 13) + closes[i] * 2 / 13
        ema26[i] = ema26[i - 1] * (1 - 2 / 27) + closes[i] * 2 / 27
    dif = ema12 - ema26
    dea = dif.copy()
    for i in range(1, n):
        dea[i] = dea[i - 1] * (1 - 2 / 10) + dif[i] * 2 / 10
    macd_hist = (dif - dea) * 2

    return KlineData(
        dates=dates,
        opens=opens.tolist(),
        highs=highs.tolist(),
        lows=lows.tolist(),
        closes=closes.tolist(),
        volumes=volumes.tolist(),
        ma5=ma5.tolist(),
        ma10=ma10.tolist(),
        ma20=ma20.tolist(),
        ma60=ma60.tolist(),
        dif=dif.tolist(),
        dea=dea.tolist(),
        macd_hist=macd_hist.tolist(),
        atr=[0.0] * n,
        bb_upper=[105.0] * n,
        bb_lower=[95.0] * n,
        bb_width=[10.0] * n,
    )


class TestGenerateChart:
    """图表生成测试。"""

    def test_normal_data(self) -> None:
        """正常数据生成PNG文件。"""
        kline = _make_kline_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test_chart.png")
            result = generate_chart("600519", "贵州茅台", kline, save_path)

            assert result == save_path
            assert os.path.exists(save_path)
            assert os.path.getsize(save_path) > 0

    def test_insufficient_data(self) -> None:
        """数据不足时不崩溃。"""
        kline = _make_kline_data(15)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test_chart.png")
            result = generate_chart("600519", "贵州茅台", kline, save_path)

            assert result == save_path
            assert os.path.exists(save_path)

    def test_chinese_name(self) -> None:
        """中文名称处理。"""
        kline = _make_kline_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "贵州茅台.png")
            result = generate_chart("600519", "贵州茅台", kline, save_path)

            assert result == save_path
            assert os.path.exists(save_path)

    def test_etf_chart(self) -> None:
        """ETF图表生成。"""
        kline = _make_kline_data(60)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "512480.png")
            result = generate_chart("512480", "半导体ETF", kline, save_path)

            assert result == save_path
            assert os.path.exists(save_path)
