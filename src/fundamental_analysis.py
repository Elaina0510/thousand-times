"""基本面分析模块 — 获取并评估基本面数据。

新增指标：
- 资产负债率（debt_ratio）：衡量财务杠杆风险
- 每股经营现金流（cash_flow）：衡量盈利质量
- 毛利率（gross_margin）：衡量核心业务盈利能力
"""

from __future__ import annotations

import contextlib
import logging
import math
from dataclasses import dataclass
from typing import Any

from config import FundamentalWeightConfig

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


def _get_quarters_to_try(current_year: int, current_quarter: int) -> list[tuple[int, int]]:
    """生成回退季度列表：当前季度 → Q1 → 上一年 Q4 → Q3 → Q2 → Q1。

    Args:
        current_year: 当前年份。
        current_quarter: 当前季度 (1-4)。

    Returns:
        [(year, quarter), ...] 按优先级排列的季度列表。
    """
    quarters: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    # 当前季度
    q = current_quarter
    y = current_year
    while q >= 1 and len(quarters) < 5:
        key = (y, q)
        if key not in seen:
            seen.add(key)
            quarters.append(key)
        q -= 1
        if q < 1:
            y -= 1
            q = 4

    return quarters


def _fetch_single_with_session(
    bs: object, code: str, current_year: int, current_quarter: int
) -> dict:
    """在已有 BaoStock 会话中获取单只股票的财务指标。

    季度回退：当前季度 → Q1 → 上一年 Q4 → Q3 → Q2 → Q1。
    找到第一个有数据的季度即停止。

    Args:
        bs: 已登录的 baostock 模块。
        code: 股票代码。
        current_year: 当前年份。
        current_quarter: 当前季度。

    Returns:
        包含财务指标的字典，无数据或 API 失败返回空字典。
    """
    try:
        bs_code = f'sh.{code}' if code.startswith(('6', '5')) else f'sz.{code}'

        quarters = _get_quarters_to_try(current_year, current_quarter)

        for year, quarter in quarters:
            # ── 盈利能力 ──
            rs_profit = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
            if rs_profit.error_code != '0':
                # API 层面失败，非"无数据"，继续尝试下一季度
                continue

            profit_list = []
            while (rs_profit.error_code == '0') & rs_profit.next():
                profit_list.append(rs_profit.get_row_data())

            if not profit_list:
                # 该季度无数据，尝试下一季度
                continue

            # 有数据，提取
            latest = profit_list[-1]
            fields = rs_profit.fields
            result: dict = {}

            if 'epsTTM' in fields:
                eps_idx = fields.index('epsTTM')
                result['epsTTM'] = float(latest[eps_idx]) if latest[eps_idx] else 0

            if 'roeAvg' in fields:
                roe_idx = fields.index('roeAvg')
                result['roeAvg'] = float(latest[roe_idx]) if latest[roe_idx] else 0

            if 'grossProfitMargin' in fields:
                gpm_idx = fields.index('grossProfitMargin')
                val = latest[gpm_idx]
                if val:
                    result['gross_margin'] = float(val) * 100

            # ── 成长能力（同季度）──
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

            return result

        # 所有季度都无数据
        return {}

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
        from datetime import datetime

        import baostock as bs

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


def _fetch_fundamental_akshare(code: str) -> dict[str, Any]:
    """使用 AKShare 东方财富业绩报表接口获取个股基本面数据。

    支持季度回退：当前季度 → Q1 → 上一年 Q4 → ... → Q1。
    找到第一个有数据的季度即返回。

    Args:
        code: 股票代码（6位数字字符串，如 "600000"）。

    Returns:
        包含财务指标的字典，键名与 BaoStock 兼容：
        roeAvg (小数), epsTTM, profit_growth (%), revenue_growth (%),
        debt_ratio (%), gross_margin (%), cash_flow。
        失败或无数据返回空字典 {}。
    """
    result = _fetch_fundamental_akshare_batch([code])
    return result.get(code, {})


def _fetch_fundamental_akshare_batch(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量获取基本面数据（内部优化：每次 API 调用获取全市场数据后本地过滤）。

    AKShare 的 stock_yjbb_em 接口返回全市场数据，逐只调用会重复下载。
    本函数每个季度只调用一次 API，然后在本地按股票代码过滤，
    避免对同一数据集发起数百次 HTTP 请求。

    Args:
        codes: 股票代码列表。

    Returns:
        {code: data_dict} 映射，未找到的 code 不在返回字典中。
    """
    if not codes:
        return {}

    try:
        from datetime import datetime

        import akshare as ak

        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1
        quarters = _get_quarters_to_try(current_year, current_quarter)
        quarter_end_days = {1: "31", 2: "30", 3: "30", 4: "31"}

        results: dict[str, dict[str, Any]] = {}
        remaining: set[str] = {str(c).zfill(6) for c in codes}

        for year, quarter in quarters:
            if not remaining:
                break

            month = quarter * 3
            date_str = f"{year}{month:02d}{quarter_end_days[quarter]}"

            try:
                df = ak.stock_yjbb_em(date=date_str)
            except Exception as e:
                logger.debug(f"AKShare stock_yjbb_em({date_str}) 失败: {e}")
                continue

            if df is None or df.empty:
                continue

            code_col = "股票代码"
            if code_col not in df.columns:
                logger.warning(f"AKShare 返回数据缺少 '{code_col}' 列，可用列: {list(df.columns)}")
                continue

            # 为每只剩余股票查找数据
            for code in list(remaining):
                stock_mask = df[code_col].astype(str).str.strip().str.zfill(6) == code
                stock_rows = df[stock_mask]

                if stock_rows.empty:
                    continue

                row = stock_rows.iloc[-1]
                data = _extract_akshare_row(row)
                if data:
                    results[code] = data
                    remaining.discard(code)

        if remaining:
            logger.debug(
                f"AKShare 未找到 {len(remaining)} 只股票的基本面数据（已尝试回退至 {quarters[-1]})"
            )

        return results

    except ImportError:
        logger.debug("AKShare 未安装，跳过")
        return {}
    except Exception as e:
        logger.warning(f"AKShare 批量获取基本面数据失败: {e}")
        return {}


def _extract_akshare_row(row: Any) -> dict[str, Any]:
    """从 AKShare stock_yjbb_em 返回的行数据中提取财务指标。

    将 AKShare 的列名映射为 BaoStock 兼容的键名，并标准化数值单位。
    - 净资产收益率：AKShare 返回百分比（如 3.2 表示 3.2%），转为小数（0.032）
    - 增长率指标：AKShare 已是百分比，直接透传
    - 资产负债率：yjbb 接口不包含此字段，设为 None
    - 数值为 NaN/None/非数字时，跳过该字段

    Args:
        row: pandas Series，stock_yjbb_em 返回的一行数据。

    Returns:
        标准化后的字典，键名与 BaoStock _fetch_single_with_session 兼容。
    """
    result: dict[str, Any] = {}

    def _safe_float(val: Any) -> float | None:
        """安全转换值为 float，NaN/None/非数字返回 None。"""
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    # ── 净资产收益率 → roeAvg（小数格式，与 BaoStock 兼容）──
    roe = _safe_float(row.get("净资产收益率"))
    if roe is not None:
        # AKShare 返回百分比（如 3.2 = 3.2%），转为小数（0.032）
        result["roeAvg"] = roe / 100.0

    # ── 每股收益 → epsTTM ──
    eps = _safe_float(row.get("每股收益"))
    if eps is not None:
        result["epsTTM"] = eps

    # ── 净利润同比增长率（已是百分比）──
    pg = _safe_float(row.get("净利润-同比增长"))
    if pg is not None:
        result["profit_growth"] = pg

    # ── 营收同比增长率（已是百分比）──
    rg = _safe_float(row.get("营业总收入-同比增长"))
    if rg is not None:
        result["revenue_growth"] = rg

    # ── 资产负债率（yjbb 接口无此字段，不设置，由下游 .get() 返回 None）──

    # ── 销售毛利率（已是百分比）──
    gm = _safe_float(row.get("销售毛利率"))
    if gm is not None:
        result["gross_margin"] = gm

    # ── 每股经营现金流（元）──
    cf = _safe_float(row.get("每股经营现金流量"))
    if cf is not None:
        result["cash_flow"] = cf

    return result


def get_fundamental_data_batch(codes: list[str]) -> dict[str, FundamentalData]:
    """批量获取多只股票的基本面数据（AKShare 优先，BaoStock 回退）。

    优先级：AKShare（HTTP，CI 环境稳定）→ BaoStock（TCP，需登录）。
    对每只股票：先调 AKShare，如果返回非空数据则直接用，
    否则 fallback 到 BaoStock。

    Args:
        codes: 股票代码列表。

    Returns:
        字典，键为股票代码，值为 FundamentalData 对象。
    """
    if not codes:
        return {}

    results: dict[str, FundamentalData] = {}
    need_baostock: list[str] = []

    # ── 第一轮：AKShare（HTTP，无需登录，CI 友好）──
    logger.info(f"开始使用 AKShare 获取 {len(codes)} 只股票基本面数据...")
    akshare_data = _fetch_fundamental_akshare_batch(codes)
    akshare_success = 0

    for code in codes:
        data = akshare_data.get(code, {})
        # 非空字典即表示 AKShare 找到了该股票的财务数据（含负盈利情况）
        if data:
            results[code] = _dict_to_fundamental_data(data)
            akshare_success += 1
        else:
            need_baostock.append(code)

    logger.info(
        f"AKShare 获取完成: {akshare_success}/{len(codes)} 只成功，"
        f"{len(need_baostock)} 只需回退到 BaoStock"
    )

    # ── 第二轮：BaoStock 回退（保留原有重连逻辑）──
    if not need_baostock:
        success = sum(1 for v in results.values() if v.roe > 0 or v.eps > 0)
        logger.info(f"基本面数据获取完成: {success}/{len(codes)} 只有效")
        return results

    from datetime import datetime

    import baostock as bs

    def _login() -> bool:
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"BaoStock 登录失败: {lg.error_msg}")
            return False
        return True

    def _logout() -> None:
        with contextlib.suppress(Exception):
            bs.logout()

    if not _login():
        logger.warning("BaoStock 登录失败，AKShare 未覆盖的股票将使用空数据")
        for code in need_baostock:
            results[code] = _empty_fundamental_data()
        return results

    current_year = datetime.now().year
    current_quarter = (datetime.now().month - 1) // 3 + 1

    consecutive_api_errors = 0  # 仅计数 API 层错误（连接断开等）
    max_consecutive_api_errors = 10  # 连续 API 错误阈值
    total_reconnects = 0
    max_reconnects = 3
    no_data_count = 0  # 统计无财报数据的股票数

    for code in need_baostock:
        api_error = False
        bs_data: dict[str, Any] = {}
        try:
            bs_data = _fetch_single_with_session(bs, code, current_year, current_quarter)
            if not bs_data:
                no_data_count += 1
        except Exception as e:
            api_error = True
            logger.warning(f"获取 {code} 基本面数据异常: {e}")

        if bs_data:
            results[code] = _dict_to_fundamental_data(bs_data)
            consecutive_api_errors = 0  # 有数据回来，重置 API 错误计数
        else:
            results[code] = _empty_fundamental_data()
            if api_error:
                consecutive_api_errors += 1
            # 无数据不增加 consecutive_api_errors（不等于连接断开）

        # 仅在连续 API 错误时重连
        if consecutive_api_errors >= max_consecutive_api_errors:
            total_reconnects += 1
            if total_reconnects > max_reconnects:
                logger.error(
                    f"基本面 API 连续 {consecutive_api_errors} 次错误，"
                    f"已重连 {total_reconnects - 1} 次仍不稳定，放弃剩余股票"
                )
                for remaining in need_baostock[len(results) - akshare_success:]:
                    if remaining not in results:
                        results[remaining] = _empty_fundamental_data()
                break

            logger.warning(
                f"基本面 API 连续 {consecutive_api_errors} 次错误，"
                f"尝试重连 ({total_reconnects}/{max_reconnects})..."
            )
            _logout()
            import time
            time.sleep(1)
            if _login():
                logger.info("基本面重连成功")
                consecutive_api_errors = 0
            else:
                logger.error("基本面重连失败，跳过剩余股票")
                for remaining in need_baostock:
                    if remaining not in results:
                        results[remaining] = _empty_fundamental_data()
                break

    _logout()

    success = sum(1 for v in results.values() if v.roe > 0 or v.eps > 0)
    logger.info(
        f"基本面数据获取完成: {success}/{len(codes)} 只有效"
        + (f"（{no_data_count} 只暂无财报数据）" if no_data_count > 0 else "")
    )
    return results


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
