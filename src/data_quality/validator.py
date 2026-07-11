"""数据完整性校验模块 — DataValidator.

校验 DataBundle 中各类数据的完整性和合理性，产出数据质量报告，
标记异常数据供下游模块降级处理。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

logger = logging.getLogger("thousand-times")


class QualityLevel(Enum):
    """数据质量等级."""

    GOOD = "good"        # 数据完整可用
    DEGRADED = "degraded"  # 部分缺失，可降级使用
    BAD = "bad"           # 严重缺失，建议跳过


@dataclass
class FieldQuality:
    """单个字段的质量报告."""

    field_name: str
    level: QualityLevel
    valid_count: int        # 有效值数量
    total_count: int        # 总数
    default_count: int      # 疑似默认值的数量
    mean_value: float | None
    std_value: float | None
    anomalies: list[str] = field(default_factory=list)  # 异常描述列表


@dataclass
class DataQualityReport:
    """完整数据质量报告."""

    timestamp: str
    # 各数据集质量
    kline_quality: dict[str, FieldQuality] = field(default_factory=dict)    # code → quality
    fundamental_quality: dict[str, FieldQuality] = field(default_factory=dict)
    capital_flow_quality: FieldQuality | None = None
    sentiment_quality: FieldQuality | None = None
    # 汇总
    overall_level: QualityLevel = QualityLevel.GOOD
    recommendation: str = ""    # 对下游管道的建议
    details: list[str] = field(default_factory=list)  # 详细问题列表


def detect_default_values(
    series: list[float],
    suspicious_values: set[float] | None = None,
) -> int:
    """检测疑似默认值填充.

    当某个值在数据集中出现比例过高（>30%），标记为疑似默认值.

    Args:
        series: 数值序列.
        suspicious_values: 预定义的疑似默认值集合.

    Returns:
        疑似默认值的数量.
    """
    if suspicious_values is None:
        suspicious_values = {60.0, 50.0, 0.0}

    if not series:
        return 0

    total = len(series)
    default_count = 0

    for val in suspicious_values:
        count = sum(1 for v in series if v == val)
        if count / total > 0.3:
            default_count += count

    return default_count


def flag_anomalous_stocks(report: DataQualityReport) -> list[str]:
    """返回应被跳过或降级处理的股票代码列表.

    Args:
        report: 质量报告.

    Returns:
        股票代码列表.
    """
    anomalous: list[str] = []

    # 汇总 K 线质量中 BAD 等级的股票
    for code, quality in report.kline_quality.items():
        if quality.level == QualityLevel.BAD:
            anomalous.append(code)

    # 汇总基本面质量中 BAD 等级的股票
    for code, quality in report.fundamental_quality.items():
        if quality.level == QualityLevel.BAD and code not in anomalous:
            anomalous.append(code)

    return anomalous


def validate_bundle(data: object) -> DataQualityReport:
    """对 DataBundle 进行完整性校验.

    校验内容：
    1. K线数据：检查每只股票的K线行数、是否存在全空、列是否齐全
    2. 基本面数据：检查 ROE/EPS/增长率是否使用了默认值（精确匹配）
    3. 资金面数据：检查北向资金、行业资金流向是否为空
    4. 情绪数据：检查涨跌停数据是否合理（非负，非异常大）

    Args:
        data: 统一数据包（DataBundle）.

    Returns:
        DataQualityReport 质量报告.
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details: list[str] = []

    # 1. K线质量校验
    kline_cache = getattr(data, "kline_cache", {})
    kline_quality = _validate_kline(kline_cache)

    # 2. 基本面质量校验
    fundamental_cache = getattr(data, "fundamental_cache", {})
    fundamental_quality = _validate_fundamental(fundamental_cache)

    # 3. 资金面质量校验
    north_flow = getattr(data, "north_flow", pd.DataFrame())
    sector_flow = getattr(data, "sector_flow", pd.DataFrame())
    capital_flow_quality = _validate_capital_flow(north_flow, sector_flow)

    # 4. 情绪面质量校验
    limit_up = getattr(data, "limit_up_count", 0)
    limit_down = getattr(data, "limit_down_count", 0)
    ad_ratio = getattr(data, "advance_decline_ratio", 1.0)
    sentiment_quality = _validate_sentiment(limit_up, limit_down, ad_ratio)

    # 5. 汇总判定
    all_qualities: list[FieldQuality] = []
    all_qualities.extend(kline_quality.values())
    all_qualities.extend(fundamental_quality.values())
    if capital_flow_quality:
        all_qualities.append(capital_flow_quality)
    if sentiment_quality:
        all_qualities.append(sentiment_quality)

    bad_count = sum(1 for q in all_qualities if q.level == QualityLevel.BAD)
    degraded_count = sum(1 for q in all_qualities if q.level == QualityLevel.DEGRADED)

    if bad_count > len(all_qualities) * 0.3:
        overall_level = QualityLevel.BAD
        recommendation = "数据严重缺失，建议暂停今日分析或仅使用离线缓存"
    elif bad_count > 0 or degraded_count > len(all_qualities) * 0.3:
        overall_level = QualityLevel.DEGRADED
        recommendation = "部分数据异常，下游模块应使用降级策略"
    else:
        overall_level = QualityLevel.GOOD
        recommendation = "数据质量良好，正常执行分析管道"

    # 收集详情
    for q in all_qualities:
        if q.level != QualityLevel.GOOD:
            for anomaly in q.anomalies:
                details.append(anomaly)

    return DataQualityReport(
        timestamp=timestamp,
        kline_quality=kline_quality,
        fundamental_quality=fundamental_quality,
        capital_flow_quality=capital_flow_quality,
        sentiment_quality=sentiment_quality,
        overall_level=overall_level,
        recommendation=recommendation,
        details=details,
    )


def _validate_kline(kline_cache: dict[str, pd.DataFrame]) -> dict[str, FieldQuality]:
    """校验 K 线数据质量.

    Args:
        kline_cache: code → K线 DataFrame 映射.

    Returns:
        code → FieldQuality 映射.
    """
    result: dict[str, FieldQuality] = {}

    for code, df in kline_cache.items():
        anomalies: list[str] = []

        if df is None or df.empty:
            result[code] = FieldQuality(
                field_name=f"kline_{code}",
                level=QualityLevel.BAD,
                valid_count=0,
                total_count=0,
                default_count=0,
                mean_value=None,
                std_value=None,
                anomalies=["K线数据为空"],
            )
            continue

        total_rows = len(df)
        valid_count = total_rows

        # 检查最少行数
        if total_rows < 20:
            anomalies.append(f"K线数据仅 {total_rows} 行，少于 20 行最低要求")
            valid_count = 0

        # 检查列完整性
        has_close = "收盘" in df.columns or "close" in df.columns
        if not has_close:
            anomalies.append("K线缺少收盘价列")

        # 检查空数据比例
        if total_rows > 0:
            close_col = "收盘" if "收盘" in df.columns else "close"
            if close_col in df.columns:
                null_ratio = df[close_col].isna().sum() / total_rows
                if null_ratio > 0.3:
                    anomalies.append(f"收盘价空数据比例 {null_ratio:.0%} > 30%")
                    valid_count = total_rows - df[close_col].isna().sum()

        # 检查数值异常（收盘价突变）
        if total_rows >= 2 and has_close:
            close_col = "收盘" if "收盘" in df.columns else "close"
            closes = df[close_col].astype(float)
            if len(closes) >= 2:
                pct_changes = closes.pct_change().dropna().abs()
                extreme = (pct_changes > 0.5).sum()
                if extreme > 0:
                    anomalies.append(f"收盘价单日波动 >50% 出现 {extreme} 次")

        # 计算均值/标准差
        mean_val: float | None = None
        std_val: float | None = None
        if has_close and total_rows > 0:
            close_col = "收盘" if "收盘" in df.columns else "close"
            mean_val = float(df[close_col].astype(float).mean())
            std_val = float(df[close_col].astype(float).std())

        # 判定等级
        if valid_count == 0 or not has_close:
            level = QualityLevel.BAD
        elif anomalies:
            level = QualityLevel.DEGRADED
        else:
            level = QualityLevel.GOOD

        result[code] = FieldQuality(
            field_name=f"kline_{code}",
            level=level,
            valid_count=valid_count,
            total_count=total_rows,
            default_count=0,
            mean_value=mean_val,
            std_value=std_val,
            anomalies=anomalies,
        )

    return result


def _validate_fundamental(
    fundamental_cache: dict[str, object],
) -> dict[str, FieldQuality]:
    """校验基本面数据质量.

    Args:
        fundamental_cache: code → FundamentalData 映射.

    Returns:
        code → FieldQuality 映射.
    """
    result: dict[str, FieldQuality] = {}

    for code, fd in fundamental_cache.items():
        anomalies: list[str] = []

        roe = getattr(fd, "roe", 0.0)
        eps = getattr(fd, "eps", 0.0)
        profit_growth = getattr(fd, "profit_growth", None)
        revenue_growth = getattr(fd, "revenue_growth", None)

        # ROE 默认值检测
        if roe == 0.0 or roe == 0:
            anomalies.append("ROE 为 0（疑似默认值）")

        # EPS 默认值检测
        if eps == 0.0 or eps == 0:
            anomalies.append("EPS 为 0（疑似默认值）")

        # 增长率默认值检测
        if profit_growth is None:
            anomalies.append("净利润增长率为 None（数据缺失）")

        if revenue_growth is None:
            anomalies.append("营收增长率为 None（数据缺失）")

        # 判定等级
        # 如果 ROE 和 EPS 同时为 0，判定为 BAD
        if (roe == 0.0 or roe == 0) and (eps == 0.0 or eps == 0):
            level = QualityLevel.BAD
        elif len(anomalies) >= 2 or anomalies:
            level = QualityLevel.DEGRADED
        else:
            level = QualityLevel.GOOD

        result[code] = FieldQuality(
            field_name=f"fundamental_{code}",
            level=level,
            valid_count=1 if level != QualityLevel.BAD else 0,
            total_count=1,
            default_count=len(anomalies),
            mean_value=roe if roe != 0.0 else None,
            std_value=None,
            anomalies=anomalies,
        )

    return result


def _validate_capital_flow(
    north_flow: pd.DataFrame,
    sector_flow: pd.DataFrame,
) -> FieldQuality:
    """校验资金面数据质量.

    Args:
        north_flow: 北向资金数据.
        sector_flow: 行业资金流向数据.

    Returns:
        FieldQuality.
    """
    anomalies: list[str] = []

    # 北向资金
    if north_flow.empty:
        anomalies.append("北向资金数据为空")
        north_valid = False
    else:
        north_valid = True
        # 检查是否有净流入列
        has_net_col = any(
            col in north_flow.columns
            for col in ["当日成交净买额", "净流入", "net_flow"]
        )
        if not has_net_col:
            anomalies.append("北向资金缺少净流入列")

    # 行业资金流向
    if sector_flow.empty:
        anomalies.append("行业资金流向数据为空")
        sector_valid = False
    else:
        sector_valid = True

    valid_count = (1 if north_valid else 0) + (1 if sector_valid else 0)
    total_count = 2

    level = QualityLevel.DEGRADED if valid_count == 0 or anomalies else QualityLevel.GOOD

    return FieldQuality(
        field_name="capital_flow",
        level=level,
        valid_count=valid_count,
        total_count=total_count,
        default_count=0,
        mean_value=None,
        std_value=None,
        anomalies=anomalies,
    )


def _validate_sentiment(
    limit_up: int,
    limit_down: int,
    ad_ratio: float,
) -> FieldQuality:
    """校验情绪面数据质量.

    Args:
        limit_up: 涨停数.
        limit_down: 跌停数.
        ad_ratio: 涨跌比.

    Returns:
        FieldQuality.
    """
    anomalies: list[str] = []

    # 检查是否为非负
    if limit_up < 0:
        anomalies.append(f"涨停数异常: {limit_up}")
    if limit_down < 0:
        anomalies.append(f"跌停数异常: {limit_down}")

    # 检查是否异常大（A 股总共约 5000 只）
    if limit_up > 5500:
        anomalies.append(f"涨停数异常大: {limit_up} > 5500")
    if limit_down > 5500:
        anomalies.append(f"跌停数异常大: {limit_down} > 5500")

    # 检查涨跌比是否为默认值
    if limit_up == 0 and limit_down == 0:
        anomalies.append("涨跌停数据均为 0（疑似未获取到数据）")

    # 检查涨跌比
    if ad_ratio == 1.0 and limit_up == 0 and limit_down == 0:
        anomalies.append("涨跌比为默认值 1.0（疑似未计算）")

    valid_count = 2  # limit_up, limit_down
    if limit_up == 0 and limit_down == 0:
        valid_count = 0

    total_count = 2

    level = QualityLevel.DEGRADED if valid_count == 0 or anomalies else QualityLevel.GOOD

    return FieldQuality(
        field_name="sentiment",
        level=level,
        valid_count=valid_count,
        total_count=total_count,
        default_count=0,
        mean_value=None,
        std_value=None,
        anomalies=anomalies,
    )
