"""图表生成模块 — 生成K线+MACD图表。"""

from __future__ import annotations

import logging
import os
from typing import Any

import matplotlib

matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import mplfinance as mpf  # type: ignore[import-untyped]
import pandas as pd

from technical_analysis import KlineData

logger = logging.getLogger("thousand-times")

# 配置中文字体
def _setup_chinese_font() -> None:
    """设置中文字体支持。"""
    import matplotlib.font_manager as fm

    # 尝试查找系统中可用的中文字体
    chinese_fonts = [
        'WenQuanYi Zen Hei',
        'WenQuanYi Micro Hei',
        'SimHei',
        'Microsoft YaHei',
        'STSong',
        'STHeiti',
        'PingFang SC',
        'Noto Sans CJK SC',
        'Source Han Sans CN',
    ]

    available_fonts = [f.name for f in fm.fontManager.ttflist]

    for font_name in chinese_fonts:
        if font_name in available_fonts:
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            logger.info(f"使用中文字体: {font_name}")
            return

    # 如果没有找到中文字体，尝试使用系统默认
    logger.warning("未找到中文字体，图表中文可能显示异常")
    plt.rcParams['axes.unicode_minus'] = False

# 初始化字体
_setup_chinese_font()

# 图表样式配置
CHART_STYLE: dict[str, Any] = {
    "figsize": (12, 8),
    "kline_ratio": 3,  # K线区域占比
    "macd_ratio": 1,  # MACD区域占比
    "colors": {
        "up": "#FF4444",  # 涨 - 红色
        "down": "#00CC00",  # 跌 - 绿色
        "ma5": "#FFD700",  # MA5 - 金色
        "ma10": "#4169E1",  # MA10 - 蓝色
        "ma20": "#9370DB",  # MA20 - 紫色
        "ma60": "#32CD32",  # MA60 - 绿色
        "dif": "#FFFFFF",  # DIF - 白色
        "dea": "#FFD700",  # DEA - 金色
        "macd_up": "#FF4444",  # MACD柱涨 - 红色
        "macd_down": "#00CC00",  # MACD柱跌 - 绿色
    },
    "background": "#1A1A2E",  # 深色背景
    "grid": "#333355",  # 网格颜色
}


def generate_chart(
    code: str,
    name: str,
    kline: KlineData,
    save_path: str,
) -> str:
    """生成K线+MACD图表。

    Args:
        code: 股票/ETF代码。
        name: 名称。
        kline: K线数据。
        save_path: 图片保存路径。

    Returns:
        图片文件路径。
    """
    # 创建DataFrame
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(kline.dates),
            "Open": kline.opens,
            "High": kline.highs,
            "Low": kline.lows,
            "Close": kline.closes,
            "Volume": kline.volumes,
        }
    )
    df.set_index("Date", inplace=True)

    # 创建均线数据
    ma5 = pd.Series(kline.ma5, index=df.index)
    ma10 = pd.Series(kline.ma10, index=df.index)
    ma20 = pd.Series(kline.ma20, index=df.index)
    ma60 = pd.Series(kline.ma60, index=df.index)

    # 创建MACD数据
    dif = pd.Series(kline.dif, index=df.index)
    dea = pd.Series(kline.dea, index=df.index)
    macd_hist = pd.Series(kline.macd_hist, index=df.index)

    # 创建均线叠加
    add_plots = [
        mpf.make_addplot(ma5, color=CHART_STYLE["colors"]["ma5"], width=1.0, label="MA5"),
        mpf.make_addplot(ma10, color=CHART_STYLE["colors"]["ma10"], width=1.0, label="MA10"),
        mpf.make_addplot(ma20, color=CHART_STYLE["colors"]["ma20"], width=1.0, label="MA20"),
        mpf.make_addplot(ma60, color=CHART_STYLE["colors"]["ma60"], width=1.0, label="MA60"),
    ]

    # 创建MACD子图
    # MACD柱状图颜色
    macd_colors = [
        CHART_STYLE["colors"]["macd_up"] if v >= 0 else CHART_STYLE["colors"]["macd_down"]
        for v in macd_hist
    ]

    add_plots.append(
        mpf.make_addplot(
            macd_hist,
            type="bar",
            color=macd_colors,
            panel=2,
            width=0.7,
            ylabel="MACD",
        )
    )
    add_plots.append(
        mpf.make_addplot(
            dif,
            color=CHART_STYLE["colors"]["dif"],
            panel=2,
            width=1.0,
        )
    )
    add_plots.append(
        mpf.make_addplot(
            dea,
            color=CHART_STYLE["colors"]["dea"],
            panel=2,
            width=1.0,
        )
    )

    # 零轴虚线
    zero_line = pd.Series(0, index=df.index)
    add_plots.append(
        mpf.make_addplot(
            zero_line,
            color="#666666",
            panel=2,
            width=0.5,
            linestyle="--",
        )
    )

    # 创建样式
    mc = mpf.make_marketcolors(
        up=CHART_STYLE["colors"]["up"],
        down=CHART_STYLE["colors"]["down"],
        edge="inherit",
        wick="inherit",
        volume="in",
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        figcolor=str(CHART_STYLE["background"]),
        facecolor=str(CHART_STYLE["background"]),
        edgecolor=str(CHART_STYLE["grid"]),
        gridcolor=str(CHART_STYLE["grid"]),
        gridstyle="--",
        y_on_right=True,
    )

    # 设置面板比例
    panel_ratios = (
        int(CHART_STYLE["kline_ratio"]),
        1,
        int(CHART_STYLE["macd_ratio"]),
    )

    # 确保保存目录存在
    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)

    # 生成图表
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=add_plots,
        figsize=tuple(CHART_STYLE["figsize"]),
        title=f"{name} ({code}) — K线图 + MA均线",
        panel_ratios=panel_ratios,
        returnfig=True,
        volume=True,
        volume_panel=1,
    )

    # 保存图片
    fig.savefig(save_path, dpi=100, bbox_inches="tight", facecolor=str(CHART_STYLE["background"]))
    plt.close(fig)

    logger.info(f"图表已保存: {save_path}")
    return save_path
