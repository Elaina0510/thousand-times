"""基本面分析模块 — 获取并评估基本面数据。

新增指标：
- 资产负债率（debt_ratio）：衡量财务杠杆风险
- 每股经营现金流（cash_flow）：衡量盈利质量
- 毛利率（gross_margin）：衡量核心业务盈利能力
"""

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

    roe: float  # 平均净资产收益率（%），如 15.0 表示 15%
    eps: float  # 每股收益（元）
    market_cap: float  # 总市值（元）
    profit_growth: float | None  # 净利润同比增长率（%）
    revenue_growth: float | None  # 营收同比增长率（%）
    debt_ratio: float | None  # 资产负债率（%），如 60.0 表示 60%
    cash_flow: float | None  # 每股经营现金流（元）
    gross_margin: float | None  # 毛利率（%）


def _fetch_single_with_session(
    bs: object, code: str, current_year: int, current_quarter: int
) -> dict:
    """在已有 BaoStock 会话中获取单只股票的财务指标。

    获取三类数据：
    1. 盈利能力（profitability）：ROE、EPS
    2. 成长能力（growth）：净利润同比、营收同比
    3. 偿债能力（balance）：资产负债率
    4. 现金流（cashflow）：每股经营现金流

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

        result: dict = {}

        # 尝试最近 2 个季度
        quarters_to_try = [(current_year, current_quarter)]
        if current_quarter == 1:
            quarters_to_try.append((current_year - 1, 4))
        else:
            quarters_to_try.append((current_year, current_quarter - 1))

        for year, quarter in quarters_to_try:
            # ── 盈利能力 ──
            rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
            if rs_profit.error_code == '0':
                profit_list = []
                while (rs_profit.error_code == '0') & rs_profit.next():
                    profit_list.append(rs_profit.get_row_data())

                if profit_list:
                    latest = profit_list[-1]
                    fields = rs_profit.fields

                    if 'epsTTM' in fields:
                        eps_idx = fields.index('epsTTM')
                        result['epsTTM'] = float(latest[eps_idx]) if latest[eps_idx] else 0

                    if 'roeAvg' in fields:
                        roe_idx = fields.index('roeAvg')
                        result['roeAvg'] = float(latest[roe_idx]) if latest[roe_idx] else 0

                    # 毛利率
                    if 'grossProfitMargin' in fields:
                        gpm_idx = fields.index('grossProfitMargin')
                        val = latest[gpm_idx]
                        if val:
                            result['gross_margin'] = float(val) * 100  # 转为百分比

                    logger.debug(f"BaoStock 获取 {code} 盈利数据成功（{year}Q{quarter}）")

            # ── 成长能力 ──
            rs_growth = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
            if rs_growth.error_code == '0':
                growth_list = []
                while (rs_growth.error_code == '0') & rs_growth.next():
                    growth_list.append(rs_growth.get_row_data())

                if growth_list:
                    latest = growth_list[-1]
                    fields = rs_growth.fields

                    if 'YOYNI' in fields:
                        yoy_ni_idx = fields.index('YOYNI')
                        val = latest[yoy_ni_idx]
                        if val:
                            result['profit_growth'] = float(val) * 100

                    if 'YOYPNI' in fields:
                        yoy_pni_idx = fields.index('YOYPNI')
                        val = latest[yoy_pni_idx]
                        if val:
                            result['revenue_growth'] = float(val) * 100

                    logger.debug(f"BaoStock 获取 {code} 成长数据成功（{year}Q{quarter}）")

            # ── 偿债能力 ──
            rs_balance = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
            if rs_balance.error_code == '0':
                balance_list = []
                while (rs_balance.error_code == '0') & rs_balance.next():
                    balance_list.append(rs_balance.get_row_data())

                if balance_list:
                    latest = balance_list[-1]
                    fields = rs_balance.fields

                    # 资产负债率 = 总负债 / 总资产
                    if 'liabilityToAsset' in fields:
                        la_idx = fields.index('liabilityToAsset')
                        val = latest[la_idx]
                        if val:
                            result['debt_ratio'] = float(val) * 100  # 转为百分比

                    logger.debug(f"BaoStock 获取 {code} 偿债数据成功（{year}Q{quarter}）")

            # ── 现金流 ──
            rs_cashflow = bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)
            if rs_cashflow.error_code == '0':
                cashflow_list = []
                while (rs_cashflow.error_code == '0') & rs_cashflow.next():
                    cashflow_list.append(rs_cashflow.get_row_data())

                if cashflow_list:
                    latest = cashflow_list[-1]
                    fields = rs_cashflow.fields

                    # 每股经营现金流
                    if 'CAToAsset' in fields:
                        cta_idx = fields.index('CAToAsset')
                        val = latest[cta_idx]
                        if val:
                            result['cash_flow'] = float(val)

                    logger.debug(f"BaoStock 获取 {code} 现金流数据成功（{year}Q{quarter}）")

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


def _dict_to_fundamental_data(data: dict) -> FundamentalData:
    """将 BaoStock 返回的字典转换为 FundamentalData。

    Args:
        data: BaoStock 返回的财务指标字典。

    Returns:
        FundamentalData 对象。
    """
    return FundamentalData(
        roe=data.get('roeAvg', 0) * 100,  # 小数转百分比，如 0.15 → 15.0
        eps=data.get('epsTTM', 0),
        market_cap=0.0,
        profit_growth=data.get('profit_growth'),
        revenue_growth=data.get('revenue_growth'),
        debt_ratio=data.get('debt_ratio'),
        cash_flow=data.get('cash_flow'),
        gross_margin=data.get('gross_margin'),
    )


def _empty_fundamental_data() -> FundamentalData:
    """返回空的基本面数据。"""
    return FundamentalData(
        roe=0.0, eps=0.0, market_cap=0.0,
        profit_growth=None, revenue_growth=None,
        debt_ratio=None, cash_flow=None, gross_margin=None,
    )


def get_fundamental_data_batch(codes: list[str]) -> dict[str, FundamentalData]:
    """批量获取多只股票的基本面数据（共享单个 BaoStock 会话）。

    Args:
        codes: 股票代码列表。

    Returns:
        字典，键为股票代码，值为 FundamentalData 对象。
    """
    if not codes:
        return {}

    try:
        import baostock as bs
        from datetime import datetime

        lg = bs.login()
        if lg.error_code != '0':
            logger.warning(f"BaoStock 登录失败: {lg.error_msg}")
            return {code: _empty_fundamental_data() for code in codes}

        try:
            current_year = datetime.now().year
            current_quarter = (datetime.now().month - 1) // 3 + 1
            results: dict[str, FundamentalData] = {}

            for code in codes:
                try:
                    data = _fetch_single_with_session(bs, code, current_year, current_quarter)
                    if not data:
                        results[code] = _empty_fundamental_data()
                    else:
                        results[code] = _dict_to_fundamental_data(data)
                except Exception as e:
                    logger.warning(f"获取 {code} 基本面数据失败: {e}")
                    results[code] = _empty_fundamental_data()

            return results

        finally:
            bs.logout()

    except Exception as e:
        logger.warning(f"BaoStock 批量获取基本面数据失败: {e}")
        return {code: _empty_fundamental_data() for code in codes}


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
            return _empty_fundamental_data()
        return _dict_to_fundamental_data(data)

    except Exception as e:
        logger.warning(f"获取股票 {code} 基本面数据失败: {e}")
        return _empty_fundamental_data()


def calc_fundamental_score(data: FundamentalData, weights: FundamentalWeightConfig) -> float:
    """计算基本面评分（满分 30 分）。

    评分规则：
    - ROE > 15% → +8, 10~15% → +3, < 10% → 0
    - EPS > 0（盈利） → +5
    - 净利润同比 > 20% → +10, 0~20% → +5, < 0% → 0
    - 营收同比 > 15% → +7, 0~15% → +3, < 0% → 0

    新增调节因子（不改变满分，作为乘数）：
    - 资产负债率 > 70% → 打 0.8 折（高杠杆风险）
    - 毛利率 > 30% → 额外 +2 分（优质业务）
    - 每股经营现金流 > 0 → 额外 +2 分（盈利质量好）

    Args:
        data: 基本面数据。
        weights: 基本面权重配置。

    Returns:
        评分（0~34分，含新增调节项）。
    """
    score = 0.0

    # ── ROE 评分 ──
    if data.roe > 15:
        score += weights.pe_low  # 8分
    elif data.roe > 10:
        score += weights.pe_mid  # 3分

    # ── EPS 评分 ──
    if data.eps > 0:
        score += weights.pb_ok  # 5分

    # ── 净利润同比增长率 ──
    if data.profit_growth is not None:
        if data.profit_growth > 20:
            score += weights.profit_high_growth  # 10分
        elif data.profit_growth > 0:
            score += weights.profit_stable_growth  # 5分

    # ── 营收同比增长率 ──
    if data.revenue_growth is not None:
        if data.revenue_growth > 15:
            score += weights.revenue_high_growth  # 7分
        elif data.revenue_growth > 0:
            score += weights.revenue_stable_growth  # 3分

    # ── 新增：资产负债率惩罚 ──
    if data.debt_ratio is not None and data.debt_ratio > 70:
        score *= 0.8  # 高杠杆打折

    # ── 新增：毛利率奖励 ──
    if data.gross_margin is not None and data.gross_margin > 30:
        score += 2.0  # 优质业务加分

    # ── 新增：经营现金流奖励 ──
    if data.cash_flow is not None and data.cash_flow > 0:
        score += 2.0  # 盈利质量加分

    return score
