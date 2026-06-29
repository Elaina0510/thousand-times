"""资金面因子计算.

子因子：
- 北向资金得分（近5日市场净流入，基准）
- 个股资金流向得分（量价分析判断资金进出）
- 行业资金流向得分（行业板块资金净流入）
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("thousand-times")


def _get_close(kline: pd.DataFrame) -> pd.Series:
    """获取收盘价列。"""
    close_col = "收盘" if "收盘" in kline.columns else "close"
    return kline[close_col].astype(float)


def _get_volume(kline: pd.DataFrame) -> pd.Series:
    """获取成交量列。"""
    vol_col = "成交量" if "成交量" in kline.columns else "volume"
    return kline[vol_col].astype(float)


def _calc_north_flow_score(north_flow: pd.DataFrame) -> float:
    """北向资金得分（市场基准）.

    基于近5日北向资金累计净流入。

    Args:
        north_flow: 北向资金数据 DataFrame。

    Returns:
        评分 0~100。
    """
    if north_flow.empty:
        return 50.0

    try:
        net_col = None
        for col in ["当日成交净买额", "净流入"]:
            if col in north_flow.columns:
                net_col = col
                break

        if net_col is None:
            return 50.0

        recent = north_flow[net_col].astype(float).tail(5).sum()

        if recent > 100e8:
            return 85.0
        elif recent > 50e8:
            return 75.0
        elif recent > 20e8:
            return 65.0
        elif recent > 0:
            return 55.0
        elif recent > -20e8:
            return 45.0
        elif recent > -50e8:
            return 35.0
        elif recent > -100e8:
            return 25.0
        else:
            return 15.0
    except Exception as e:
        logger.warning(f"北向资金计算异常: {e}")
        return 50.0


def _calc_stock_flow_score(kline: pd.DataFrame) -> float:
    """个股资金流向得分.

    基于量价配合关系判断个股资金进出：
    - 放量上涨 → 资金流入
    - 放量下跌 → 资金出逃
    - 缩量下跌 → 资金未出逃（抛压减轻）
    - OBV 趋势辅助判断

    Args:
        kline: 个股K线数据。

    Returns:
        评分 0~100。
    """
    if kline is None or kline.empty or len(kline) < 5:
        return 50.0

    try:
        closes = _get_close(kline)
        volumes = _get_volume(kline)

        # 量比
        avg_vol = volumes.tail(20).mean() if len(volumes) >= 20 else volumes.mean()
        vol_ratio = volumes.iloc[-1] / avg_vol if avg_vol > 0 else 1.0

        score = 50.0

        if len(closes) >= 6:
            price_change = (closes.iloc[-1] / closes.iloc[-6] - 1) * 100

            # 量价配合分析
            if vol_ratio > 1.5 and price_change > 3:
                score = 80.0  # 放量大涨 → 资金大幅流入
            elif vol_ratio > 1.5 and price_change < -3:
                score = 20.0  # 放量大跌 → 资金大幅出逃
            elif vol_ratio > 1.2 and price_change > 1:
                score = 70.0  # 温和放量上涨
            elif vol_ratio > 1.2 and price_change < -1:
                score = 30.0  # 温和放量下跌
            elif vol_ratio < 0.7 and price_change < -1:
                score = 55.0  # 缩量下跌 → 抛压减轻
            elif vol_ratio < 0.7 and price_change > 0:
                score = 45.0  # 缩量上涨 → 动能不足
            elif vol_ratio > 1.0 and price_change > 0:
                score = 60.0  # 正常量能上涨
            elif vol_ratio < 1.0 and price_change < 0:
                score = 40.0  # 正常量能下跌

        # OBV 趋势（简易版）
        if len(closes) >= 20:
            obv_trend = 0
            for i in range(-19, 0):  # 从-19开始，确保 iloc[i-1] 不越界
                if closes.iloc[i] > closes.iloc[i - 1]:
                    obv_trend += 1
                elif closes.iloc[i] < closes.iloc[i - 1]:
                    obv_trend -= 1

            if obv_trend > 5:
                score = min(score + 5, 100)
            elif obv_trend < -5:
                score = max(score - 5, 0)

        return round(score, 2)
    except Exception as e:
        logger.warning(f"个股资金流向计算异常: {e}")
        return 50.0


def _calc_sector_flow_score(industry: str, sector_flow: pd.DataFrame) -> float:
    """行业资金流向得分.

    根据股票所属行业，从行业资金流向数据中获取该行业的资金净流入排名。

    Args:
        industry: 股票所属行业名称。
        sector_flow: 行业资金流向 DataFrame（来自 AKShare）。

    Returns:
        评分 0~100。
    """
    if sector_flow.empty or not industry:
        return 50.0

    try:
        from scoring import clean_industry_name

        clean_ind = clean_industry_name(industry)

        # 查找净流入列
        net_col = None
        for col in sector_flow.columns:
            if "净流入" in str(col) and "净额" in str(col):
                net_col = col
                break

        if net_col is None:
            return 50.0

        # 查找行业名称列
        name_col = "名称" if "名称" in sector_flow.columns else sector_flow.columns[0]

        # 在行业资金流向中匹配该行业
        flows = sector_flow[net_col].astype(float)
        all_flows = flows.dropna().sort_values(ascending=False)

        if all_flows.empty:
            return 50.0

        # 尝试匹配行业
        matched_flow = None
        for _idx, row in sector_flow.iterrows():
            row_name = str(row.get(name_col, ""))
            if clean_ind in row_name or row_name in clean_ind:
                matched_flow = float(row[net_col])
                break

        if matched_flow is None:
            # 无法匹配行业，使用中性分
            return 50.0

        # 计算该行业在所有行业中的百分位排名（排名越高=资金越流入）
        rank = (all_flows > matched_flow).sum()  # 比它高的行业数
        total = len(all_flows)
        # 排名最高的行业百分位=1.0（分数100），最低的→0.0
        percentile = (total - rank) / total if total > 0 else 0.5

        # 百分位映射到 0~100
        score = round(percentile * 100, 2)
        return min(max(score, 0), 100)

    except Exception as e:
        logger.warning(f"行业资金流向计算异常: {e}")
        return 50.0


def calc_capital_factor(
    north_flow: pd.DataFrame,
    kline: pd.DataFrame | None = None,
    industry: str = "",
    sector_flow: pd.DataFrame | None = None,
) -> dict[str, float]:
    """计算资金面因子综合评分（逐股差异化）.

    Args:
        north_flow: 北向资金数据 DataFrame（市场基准）。
        kline: 个股K线数据（用于个股量价分析）。
        industry: 股票所属行业（用于行业资金流向）。
        sector_flow: 行业资金流向 DataFrame（可选）。

    Returns:
        dict with keys: north_flow, stock_flow, sector_flow, score。
    """
    try:
        north_score = _calc_north_flow_score(north_flow)
        stock_score = _calc_stock_flow_score(kline) if kline is not None else 50.0
        if sector_flow is not None and not sector_flow.empty:
            sector_score = _calc_sector_flow_score(industry, sector_flow)
        else:
            sector_score = 50.0

        # 权重: 市场北向30%, 个股量价40%, 行业资金30%
        score = round(north_score * 0.3 + stock_score * 0.4 + sector_score * 0.3, 2)

        return {
            "north_flow": north_score,
            "stock_flow": stock_score,
            "sector_flow": sector_score,
            "score": score,
        }
    except Exception as e:
        logger.warning(f"资金因子计算异常: {e}")
        return {"north_flow": 50.0, "stock_flow": 50.0, "sector_flow": 50.0, "score": 50.0}
