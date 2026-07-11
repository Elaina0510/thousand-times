"""多数据源值域统一模块 — DataSourceUnifier.

统一 AKShare 和 BaoStock 双数据源的值域，确保 ROE/EPS/增长率等
关键指标在相同尺度上进行比较和评分。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("thousand-times")


class DataSource(Enum):
    """数据来源."""

    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    UNKNOWN = "unknown"


@dataclass
class NormalizedFundamental:
    """标准化后的基本面数据."""

    code: str
    source: DataSource

    # 以下所有值均使用统一尺度
    roe: float = 0.0                # 百分比，如 15.0 表示 15%
    eps: float = 0.0                # 元/股
    market_cap: float = 0.0         # 亿元
    profit_growth: float | None = None   # 百分比
    revenue_growth: float | None = None  # 百分比
    debt_ratio: float | None = None      # 百分比
    cash_flow: float | None = None       # 元/股
    gross_margin: float | None = None    # 百分比

    # 元数据
    data_period: str = ""           # 数据所属财报期，如 "2026Q1"
    is_estimated: bool = False      # 是否为预估值（非正式财报）


@dataclass
class UnificationReport:
    """统一化处理报告."""

    total_stocks: int = 0
    from_akshare: int = 0
    from_baostock: int = 0
    conflicts: list[dict[str, Any]] = field(default_factory=list)      # 两源数据冲突的记录
    corrections: list[dict[str, Any]] = field(default_factory=list)    # 修正的记录
    fallback_count: int = 0         # 回退到空数据的数量


def get_preferred_source(
    code: str,
    akshare_available: bool,
    baostock_available: bool,
) -> DataSource:
    """确定首选数据源.

    AKShare > BaoStock > 空数据.

    Args:
        code: 股票代码.
        akshare_available: AKShare 是否有数据.
        baostock_available: BaoStock 是否有数据.

    Returns:
        首选数据源.
    """
    if akshare_available:
        return DataSource.AKSHARE
    elif baostock_available:
        return DataSource.BAOSTOCK
    else:
        return DataSource.UNKNOWN


def validate_value_range(data: NormalizedFundamental) -> list[str]:
    """验证标准化后的数据是否在合理范围内.

    合理范围：
    - ROE: [-100%, 100%]
    - EPS: [-100, 1000] 元
    - profit_growth: [-500%, 500%]
    - debt_ratio: [0%, 200%]
    - gross_margin: [-50%, 100%]

    Args:
        data: 标准化基本面数据.

    Returns:
        异常描述列表，无异常为空.
    """
    anomalies: list[str] = []

    if data.roe < -100 or data.roe > 100:
        anomalies.append(f"ROE 越界: {data.roe} (合理范围 [-100, 100])")

    if data.eps < -100 or data.eps > 1000:
        anomalies.append(f"EPS 越界: {data.eps} (合理范围 [-100, 1000])")

    if data.profit_growth is not None and (data.profit_growth < -500 or data.profit_growth > 500):
        anomalies.append(
            f"profit_growth 越界: {data.profit_growth} (合理范围 [-500, 500])"
        )

    if data.revenue_growth is not None and (data.revenue_growth < -500 or data.revenue_growth > 500):
        anomalies.append(
            f"revenue_growth 越界: {data.revenue_growth} (合理范围 [-500, 500])"
        )

    if data.debt_ratio is not None and (data.debt_ratio < 0 or data.debt_ratio > 200):
        anomalies.append(
            f"debt_ratio 越界: {data.debt_ratio} (合理范围 [0, 200])"
        )

    if data.gross_margin is not None and (data.gross_margin < -50 or data.gross_margin > 100):
        anomalies.append(
            f"gross_margin 越界: {data.gross_margin} (合理范围 [-50, 100])"
        )

    return anomalies


def unify_fundamental_data(
    akshare_results: dict[str, dict[str, Any]],
    baostock_results: dict[str, dict[str, Any]],
    quality_report: object | None = None,
) -> tuple[dict[str, NormalizedFundamental], UnificationReport]:
    """统一 AKShare 和 BaoStock 的基本面数据.

    统一规则：
    1. ROE: 统一为百分比（如 15.0 表示 15%）
       - AKShare stock_yjbb_em 返回 roeAvg 为小数，乘以 100
       - BaoStock query_profit_data 返回 roeAvg 小数 (0.15)，乘以 100
    2. EPS: 统一为元/股，不做转换
    3. 增长率: 统一为百分比
       - AKShare growth_rate 已为百分比，直接使用
       - BaoStock YOYNI/YOYPNI 返回小数，乘以 100
    4. 优先使用 AKShare 数据（HTTP 直接获取），BaoStock 作为补充
    5. 当两源数据差异 > 30% 时，记录冲突，优先使用最近财报期数据

    Args:
        akshare_results: AKShare 原始数据 {code: dict}.
        baostock_results: BaoStock 原始数据 {code: dict}.
        quality_report: 数据质量报告（可选）.

    Returns:
        (标准化数据映射, 处理报告)
    """
    report = UnificationReport()

    all_codes: set[str] = set(akshare_results.keys()) | set(baostock_results.keys())
    report.total_stocks = len(all_codes)

    result: dict[str, NormalizedFundamental] = {}

    for code in all_codes:
        ak_data = akshare_results.get(code, {})
        bs_data = baostock_results.get(code, {})

        ak_available = bool(ak_data)
        bs_available = bool(bs_data)

        source = get_preferred_source(code, ak_available, bs_available)

        if source == DataSource.UNKNOWN:
            # 两源都无数据
            report.fallback_count += 1
            result[code] = NormalizedFundamental(
                code=code,
                source=DataSource.UNKNOWN,
            )
            continue

        if source == DataSource.AKSHARE:
            normalized = _normalize_akshare(code, ak_data)
            report.from_akshare += 1

            # 如果 BaoStock 也有数据，检测冲突
            if bs_available:
                bs_normalized = _normalize_baostock(code, bs_data)
                _detect_conflict(normalized, bs_normalized, report)
        else:
            normalized = _normalize_baostock(code, bs_data)
            report.from_baostock += 1

        result[code] = normalized

    return result, report


def _normalize_akshare(code: str, data: dict[str, Any]) -> NormalizedFundamental:
    """标准化 AKShare 数据.

    AKShare stock_yjbb_em 的 _extract_akshare_row 已返回字典格式：
    - roeAvg: 小数（0.032 = 3.2%），需 ×100
    - epsTTM: 元/股（直用）
    - profit_growth: 百分比（直用）
    - revenue_growth: 百分比（直用）
    - gross_margin: 百分比（直用）
    - cash_flow: 元/股（直用）

    Args:
        code: 股票代码.
        data: AKShare 返回的原始字典.

    Returns:
        NormalizedFundamental.
    """
    # AKShare 的 roeAvg 存为小数（0.032），需 ×100 转为百分比
    roe = data.get("roeAvg", 0.0)
    if isinstance(roe, (int, float)) and roe != 0 and abs(roe) < 1.0:
        roe = roe * 100
    # 否则已是百分数形式

    eps = data.get("epsTTM", 0.0)

    pg = data.get("profit_growth")
    rg = data.get("revenue_growth")
    gm = data.get("gross_margin")
    cf = data.get("cash_flow")

    # 增长率：AKShare 中已是百分比，直接使用
    if pg is not None and isinstance(pg, (int, float)):
        # 如果是小数形式（如 0.25 = 25%），乘以 100
        if abs(pg) < 1.0 and pg != 0:
            pg = pg * 100
        pg = float(pg)
    if rg is not None and isinstance(rg, (int, float)):
        if abs(rg) < 1.0 and rg != 0:
            rg = rg * 100
        rg = float(rg)
    if gm is not None and isinstance(gm, (int, float)):
        # 毛利率：小数转百分比
        if abs(gm) < 1.0 and gm != 0:
            gm = gm * 100
        gm = float(gm)

    return NormalizedFundamental(
        code=code,
        source=DataSource.AKSHARE,
        roe=float(roe),
        eps=float(eps),
        market_cap=0.0,
        profit_growth=float(pg) if pg is not None else None,
        revenue_growth=float(rg) if rg is not None else None,
        debt_ratio=None,  # AKShare yjbb 不包含此字段
        cash_flow=float(cf) if cf is not None else None,
        gross_margin=float(gm) if gm is not None else None,
        data_period=data.get("data_period", ""),
        is_estimated=False,
    )


def _normalize_baostock(code: str, data: dict[str, Any]) -> NormalizedFundamental:
    """标准化 BaoStock 数据.

    BaoStock query_profit_data 返回小数：
    - roeAvg: 小数（0.15 = 15%），需 ×100
    - epsTTM: 元/股（直用）
    - YOYNI: 小数（0.25 = 25%），需 ×100
    - gross_margin: 已由 fundamental_analysis 转为百分比（×100）
    - 增长率: YOYNI/YOYPNI 为小数，需 ×100

    Args:
        code: 股票代码.
        data: BaoStock 返回的原始字典.

    Returns:
        NormalizedFundamental.
    """
    # BaoStock 的 roeAvg 为小数，乘以 100 转为百分比
    roe = data.get("roeAvg", 0.0)
    if isinstance(roe, (int, float)) and abs(roe) < 1.0 and roe != 0:
        roe = roe * 100

    eps = data.get("epsTTM", 0.0)

    pg = data.get("profit_growth")
    rg = data.get("revenue_growth")

    # BaoStock 增长率可能是小数或已转换，检查后处理
    if pg is not None and isinstance(pg, (int, float)):
        # fundamental_analysis.py 已经将 YOYNI 乘以 100
        # 如果值仍然很小（小数），再乘 100
        if abs(pg) < 1.0 and pg != 0:
            pg = pg * 100
        pg = float(pg)
    if rg is not None and isinstance(rg, (int, float)):
        if abs(rg) < 1.0 and rg != 0:
            rg = rg * 100
        rg = float(rg)

    gm = data.get("gross_margin")
    if gm is not None and isinstance(gm, (int, float)):
        if abs(gm) < 1.0 and gm != 0:
            gm = gm * 100
        gm = float(gm)

    cf = data.get("cash_flow")

    return NormalizedFundamental(
        code=code,
        source=DataSource.BAOSTOCK,
        roe=float(roe),
        eps=float(eps),
        market_cap=0.0,
        profit_growth=float(pg) if pg is not None else None,
        revenue_growth=float(rg) if rg is not None else None,
        debt_ratio=data.get("debt_ratio"),
        cash_flow=float(cf) if cf is not None else None,
        gross_margin=float(gm) if gm is not None else None,
        data_period=data.get("data_period", ""),
        is_estimated=False,
    )


def _detect_conflict(
    ak: NormalizedFundamental,
    bs: NormalizedFundamental,
    report: UnificationReport,
) -> None:
    """检测 AKShare 与 BaoStock 数据冲突.

    当两源差异 > 30% 时记录冲突.

    Args:
        ak: AKShare 标准化数据.
        bs: BaoStock 标准化数据.
        report: 处理报告（会被修改）.
    """
    fields_to_check = [
        ("roe", "ROE"),
        ("eps", "EPS"),
        ("profit_growth", "净利润增长率"),
        ("revenue_growth", "营收增长率"),
        ("gross_margin", "毛利率"),
    ]

    for attr, label in fields_to_check:
        ak_val = getattr(ak, attr)
        bs_val = getattr(bs, attr)

        if ak_val is None or bs_val is None:
            continue
        if ak_val == 0 and bs_val == 0:
            continue

        # 计算差异百分比
        max_val = max(abs(ak_val), abs(bs_val))
        if max_val == 0:
            continue

        diff_pct = abs(ak_val - bs_val) / max_val

        if diff_pct > 0.3:
            report.conflicts.append({
                "code": ak.code,
                "field": label,
                "akshare_value": ak_val,
                "baostock_value": bs_val,
                "diff_pct": round(diff_pct * 100, 1),
            })
            logger.debug(
                f"数据冲突 {ak.code} {label}: "
                f"AKShare={ak_val:.2f}, BaoStock={bs_val:.2f}, "
                f"差异={diff_pct:.1%}"
            )
