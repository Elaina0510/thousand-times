"""基本面分析模块 — 获取并评估基本面数据。"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

import pandas as pd

from config import FundamentalWeightConfig
from utils import random_delay

logger = logging.getLogger("thousand-times")

# 全局标志：AKShare 是否可用
_akshare_available = True


@dataclass
class FundamentalData:
    """基本面数据。"""

    pe_ttm: float  # 滚动市盈率
    pb: float  # 市净率
    market_cap: float  # 总市值（元）
    profit_growth: float | None  # 净利润同比增长率（%）
    revenue_growth: float | None  # 营收同比增长率（%）


def _fetch_single_with_session(bs, code: str, current_year: int, current_quarter: int) -> dict:
    """在已有 BaoStock 会话中获取单只股票的财务指标。

    Args:
        bs: 已登录的 baostock 模块。
        code: 股票代码。
        current_year: 当前年份。
        current_quarter: 当前季度。

    Returns:
        包含财务指标的字典，失败返回空字典。
    """
    try:
        # 转换代码格式
        if code.startswith('6') or code.startswith('5'):
            bs_code = f'sh.{code}'
        else:
            bs_code = f'sz.{code}'

        result = {}

        # 尝试最近几个季度
        for year in [current_year, current_year - 1]:
            for quarter in [current_quarter, 4, 3, 2, 1]:
                if year == current_year and quarter > current_quarter:
                    continue

                # 获取盈利能力数据
                rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs_profit.error_code == '0':
                    profit_list = []
                    while (rs_profit.error_code == '0') & rs_profit.next():
                        profit_list.append(rs_profit.get_row_data())

                    if profit_list:
                        latest = profit_list[-1]
                        fields = rs_profit.fields

                        # 提取 EPS 和 ROE
                        if 'epsTTM' in fields:
                            eps_idx = fields.index('epsTTM')
                            result['epsTTM'] = float(latest[eps_idx]) if latest[eps_idx] else 0

                        if 'roeAvg' in fields:
                            roe_idx = fields.index('roeAvg')
                            result['roeAvg'] = float(latest[roe_idx]) if latest[roe_idx] else 0

                        logger.debug(f"BaoStock 获取 {code} 盈利数据成功（{year}Q{quarter}）")

                # 获取成长能力数据
                rs_growth = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
                if rs_growth.error_code == '0':
                    growth_list = []
                    while (rs_growth.error_code == '0') & rs_growth.next():
                        growth_list.append(rs_growth.get_row_data())

                    if growth_list:
                        latest = growth_list[-1]
                        fields = rs_growth.fields

                        # 提取净利润同比增长率
                        if 'YOYNI' in fields:
                            yoy_ni_idx = fields.index('YOYNI')
                            val = latest[yoy_ni_idx]
                            if val:
                                result['profit_growth'] = float(val) * 100  # 转换为百分比

                        # 提取营收同比增长率
                        if 'YOYPNI' in fields:
                            yoy_pni_idx = fields.index('YOYPNI')
                            val = latest[yoy_pni_idx]
                            if val:
                                result['revenue_growth'] = float(val) * 100  # 转换为百分比

                        logger.debug(f"BaoStock 获取 {code} 成长数据成功（{year}Q{quarter}）")

                if result:
                    return result

        return result

    except Exception as e:
        logger.warning(f"BaoStock 获取 {code} 财务指标失败: {e}")
        return {}


def _fetch_financial_indicator(code: str) -> dict:
    """获取个股财务指标（使用 BaoStock，单次登录）。

    Args:
        code: 股票代码。

    Returns:
        包含财务指标的字典，失败返回空字典。
    """
    try:
        import baostock as bs
        from datetime import datetime

        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            logger.warning(f"BaoStock 登录失败: {lg.error_msg}")
            return {}

        try:
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            return _fetch_single_with_session(bs, code, current_year, current_quarter)
        finally:
            bs.logout()

    except Exception as e:
        logger.warning(f"BaoStock 获取 {code} 财务指标失败: {e}")
        return {}


def get_fundamental_data_batch(codes: list[str]) -> dict[str, FundamentalData]:
    """批量获取多只股票的基本面数据（共享单个 BaoStock 会话）。

    Args:
        codes: 股票代码列表。

    Returns:
        字典，键为股票代码，值为 FundamentalData 对象。
    """
    from datetime import datetime

    empty_data = FundamentalData(
        pe_ttm=0.0, pb=0.0, market_cap=0.0,
        profit_growth=None, revenue_growth=None,
    )

    if not codes:
        return {}

    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != '0':
            logger.warning(f"BaoStock 登录失败: {lg.error_msg}")
            return {code: empty_data for code in codes}

        try:
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            results: dict[str, FundamentalData] = {}

            for code in codes:
                try:
                    data = _fetch_single_with_session(bs, code, current_year, current_quarter)

                    if not data:
                        results[code] = empty_data
                        continue

                    roe = data.get('roeAvg', 0)
                    eps = data.get('epsTTM', 0)
                    profit_growth = data.get('profit_growth')
                    revenue_growth = data.get('revenue_growth')

                    results[code] = FundamentalData(
                        pe_ttm=roe * 100,  # ROE 转换为百分比，用作 pe_ttm 代理
                        pb=eps,  # EPS 用作 pb 代理
                        market_cap=0.0,
                        profit_growth=profit_growth,
                        revenue_growth=revenue_growth,
                    )
                except Exception as e:
                    logger.warning(f"获取 {code} 基本面数据失败: {e}")
                    results[code] = empty_data

            return results

        finally:
            bs.logout()

    except Exception as e:
        logger.warning(f"BaoStock 批量获取基本面数据失败: {e}")
        return {code: empty_data for code in codes}


def get_fundamental_data(code: str) -> FundamentalData:
    """获取个股基本面数据。

    Args:
        code: 股票代码。

    Returns:
        FundamentalData 对象。
    """
    try:
        data = _fetch_financial_indicator(code)

        if not data:
            logger.debug(f"股票 {code} 财务数据为空")
            return FundamentalData(
                pe_ttm=0.0,
                pb=0.0,
                market_cap=0.0,
                profit_growth=None,
                revenue_growth=None,
            )

        # BaoStock 返回的是 EPS 和 ROE，不是 PE 和 PB
        # 这里我们使用 ROE 作为基本面质量的代理指标
        # ROE 越高，基本面越好
        roe = data.get('roeAvg', 0)
        eps = data.get('epsTTM', 0)
        profit_growth = data.get('profit_growth')
        revenue_growth = data.get('revenue_growth')

        # 使用 ROE 作为 pe_ttm 的代理（用于评分）
        # ROE > 0.15 (15%) 视为优秀
        pe_ttm = roe * 100  # 转换为百分比

        # 使用 EPS 作为 pb 的代理（用于评分）
        # EPS > 0 视为盈利
        pb = eps

        return FundamentalData(
            pe_ttm=pe_ttm,
            pb=pb,
            market_cap=0.0,
            profit_growth=profit_growth,
            revenue_growth=revenue_growth,
        )

    except Exception as e:
        logger.warning(f"获取股票 {code} 基本面数据失败: {e}")

        return FundamentalData(
            pe_ttm=0.0,
            pb=0.0,
            market_cap=0.0,
            profit_growth=None,
            revenue_growth=None,
        )


def calc_fundamental_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float:
    """计算基本面评分。

    评分规则（适配 BaoStock 数据）：
    - ROE: > 15% → +8, 10~15% → +3, < 10% → 0
    - EPS: > 0 → +5
    - 净利润同比: >20% → +10, 0~20% → +5, <0% → 0
    - 营收同比: >15% → +7, 0~15% → +3, <0% → 0

    Args:
        data: 基本面数据。
        weights: 基本面权重配置。

    Returns:
        评分（0~30分）。
    """
    score = 0.0

    # ROE 评分（使用 pe_ttm 字段存储 ROE）
    if data.pe_ttm > 15:
        score += weights.pe_low  # 8分
    elif data.pe_ttm > 10:
        score += weights.pe_mid  # 3分
    # ROE < 10%: 0分

    # EPS 评分（使用 pb 字段存储 EPS）
    if data.pb > 0:
        score += weights.pb_ok  # 5分

    # 净利润同比增长率评分
    if data.profit_growth is not None:
        if data.profit_growth > 20:
            score += weights.profit_high_growth  # 10分
        elif data.profit_growth > 0:
            score += weights.profit_stable_growth  # 5分
        # 净利润下降: 0分

    # 营收同比增长率评分
    if data.revenue_growth is not None:
        if data.revenue_growth > 15:
            score += weights.revenue_high_growth  # 7分
        elif data.revenue_growth > 0:
            score += weights.revenue_stable_growth  # 3分
        # 营收下降: 0分

    return score
