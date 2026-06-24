"""宏观经济指标数据源.

获取 CPI、PMI、利率等宏观指标，用于市场环境判断和宏观面因子。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("thousand-times")


def fetch_macro_indicators() -> dict[str, float | None]:
    """获取最新宏观经济指标.

    Returns:
        dict with keys:
            - cpi: CPI 同比增速 (%)
            - pmi: 制造业 PMI 指数
            - m2_growth: M2 同比增速 (%)
        获取失败的指标值为 None。
    """
    result: dict[str, float | None] = {
        "cpi": None,
        "pmi": None,
        "m2_growth": None,
    }

    try:
        import akshare as ak  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("AKShare 不可用，无法获取宏观指标")
        return result

    # CPI
    try:
        cpi_df = ak.macro_china_cpi_monthly()
        if cpi_df is not None and not cpi_df.empty:
            # 列名: 商品, 日期, 今值, 预测值, 前值
            if "今值" in cpi_df.columns:
                result["cpi"] = float(cpi_df.iloc[-1]["今值"])
            elif len(cpi_df.columns) >= 3:
                result["cpi"] = float(cpi_df.iloc[-1].iloc[2])
            logger.info(f"CPI: {result['cpi']}")
    except Exception as e:
        logger.warning(f"获取CPI失败: {e}")

    # PMI
    try:
        pmi_df = ak.macro_china_pmi()
        if pmi_df is not None and not pmi_df.empty:
            # 列名: 月份, 制造业-指数, 制造业-同比增长, ...
            if "制造业-指数" in pmi_df.columns:
                result["pmi"] = float(pmi_df.iloc[-1]["制造业-指数"])
            elif len(pmi_df.columns) >= 2:
                result["pmi"] = float(pmi_df.iloc[-1].iloc[1])
            logger.info(f"PMI: {result['pmi']}")
    except Exception as e:
        logger.warning(f"获取PMI失败: {e}")

    # M2 增速
    try:
        m2_df = ak.macro_china_money_supply()
        if m2_df is not None and not m2_df.empty:
            # 列名可能包含 "M2-同比" 或类似
            m2_col = None
            for col in m2_df.columns:
                if "M2" in str(col) and "同比" in str(col):
                    m2_col = col
                    break
            if m2_col:
                result["m2_growth"] = float(m2_df.iloc[-1][m2_col])
            logger.info(f"M2增速: {result['m2_growth']}")
    except Exception as e:
        logger.warning(f"获取M2增速失败: {e}")

    return result


def calc_macro_score(indicators: dict[str, float | None]) -> float:
    """基于宏观指标计算评分.

    评分逻辑：
    - PMI > 50（扩张）加分，< 50（收缩）减分
    - CPI 适中（1-3%）加分，过高或通缩减分
    - M2 增速适中加分

    Args:
        indicators: fetch_macro_indicators() 的返回值。

    Returns:
        评分 0~100，数据不足返回 50（中性）。
    """
    score = 50.0
    has_data = False

    # PMI 评分
    pmi = indicators.get("pmi")
    if pmi is not None:
        has_data = True
        if pmi > 52:
            score += 15
        elif pmi > 50:
            score += 10
        elif pmi > 49:
            score += 0
        elif pmi > 48:
            score -= 10
        else:
            score -= 15

    # CPI 评分
    cpi = indicators.get("cpi")
    if cpi is not None:
        has_data = True
        if 1.0 <= cpi <= 3.0:
            score += 10  # 温和通胀
        elif 0 <= cpi < 1.0:
            score += 0   # 低通胀
        elif cpi < 0:
            score -= 10  # 通缩
        elif cpi > 3.0:
            score -= 5   # 通胀偏高
        if cpi > 5.0:
            score -= 10  # 高通胀

    # M2 增速评分
    m2 = indicators.get("m2_growth")
    if m2 is not None:
        has_data = True
        if 8 <= m2 <= 12:
            score += 5   # 适度宽松
        elif m2 > 12:
            score += 0   # 过度宽松
        elif m2 < 6:
            score -= 5   # 偏紧

    if not has_data:
        return 50.0

    return round(min(max(score, 0), 100), 2)
