"""磁盘缓存管理模块 — 使用 JSON 格式持久化数据，避免重复网络请求。

支持增量缓存：K线数据可跨天复用，仅拉取新增日期。
支持缓存统计：跟踪命中/未命中次数，计算命中率。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger("thousand-times")

CACHE_DIR = "cache"
CACHE_TTL = 86400  # 24小时（秒）
# 季报数据每季度更新一次，90天TTL确保同一季度内复用缓存
FUND_CACHE_TTL = 7776000  # 90天（秒）

# 缓存统计计数器
_cache_stats = {"hit": 0, "miss": 0}


def _ensure_cache_dir() -> None:
    """确保缓存目录存在。"""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    """获取缓存文件路径。"""
    # 替换不安全的文件名字符
    safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def _record_hit() -> None:
    """记录缓存命中。"""
    _cache_stats["hit"] += 1


def _record_miss() -> None:
    """记录缓存未命中。"""
    _cache_stats["miss"] += 1


def get_cache_stats() -> dict[str, int]:
    """获取缓存统计信息。

    Returns:
        包含 hit、miss、total 和 hit_rate 的字典。
    """
    total = _cache_stats["hit"] + _cache_stats["miss"]
    hit_rate = (_cache_stats["hit"] / total * 100) if total > 0 else 0.0
    return {
        "hit": _cache_stats["hit"],
        "miss": _cache_stats["miss"],
        "total": total,
        "hit_rate": round(hit_rate, 1),
    }


def log_cache_stats() -> None:
    """输出缓存统计日志。"""
    stats = get_cache_stats()
    logger.info(
        f"缓存统计 — 命中: {stats['hit']}, 未命中: {stats['miss']}, "
        f"总计: {stats['total']}, 命中率: {stats['hit_rate']}%"
    )


def get_cached_data(key: str, ttl: int = CACHE_TTL) -> dict | list | None:
    """获取缓存数据。

    Args:
        key: 缓存键名。
        ttl: 缓存有效期（秒），默认 24 小时。

    Returns:
        缓存的数据，如果不存在或已过期则返回 None。
    """
    cache_file = _cache_path(key)
    if not os.path.exists(cache_file):
        _record_miss()
        return None

    mtime = os.path.getmtime(cache_file)
    if datetime.now().timestamp() - mtime >= ttl:
        logger.debug(f"缓存已过期: {key}")
        _record_miss()
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"缓存命中: {key}")
        _record_hit()
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取缓存失败 {key}: {e}")
        _record_miss()
        return None


def set_cached_data(key: str, data) -> None:
    """设置缓存数据。

    Args:
        key: 缓存键名。
        data: 要缓存的数据（支持 dict、list、DataFrame）。
    """
    _ensure_cache_dir()
    cache_file = _cache_path(key)

    try:
        # DataFrame 转换为 records 格式
        if isinstance(data, pd.DataFrame):
            serializable = {
                "_type": "DataFrame",
                "records": data.to_dict(orient="records"),
                "columns": list(data.columns),
            }
        elif isinstance(data, dict):
            # 检查字典的值是否为 DataFrame
            sample_values = list(data.values())[:1]
            if sample_values and isinstance(sample_values[0], pd.DataFrame):
                serializable = {
                    "_type": "dict[DataFrame]",
                    "items": {
                        k: {"records": v.to_dict(orient="records"), "columns": list(v.columns)}
                        for k, v in data.items()
                        if isinstance(v, pd.DataFrame) and not v.empty
                    },
                }
            else:
                serializable = data
        else:
            serializable = data

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, default=str)
        logger.debug(f"缓存写入: {key}")
    except Exception as e:
        logger.warning(f"写入缓存失败 {key}: {e}")


def load_cached_dataframe(key: str) -> dict[str, pd.DataFrame] | None:
    """从缓存加载 DataFrame 字典。

    Args:
        key: 缓存键名。

    Returns:
        {code: DataFrame} 字典，如果缓存不存在或过期则返回 None。
    """
    data = get_cached_data(key)
    if data is None:
        return None

    try:
        if isinstance(data, dict) and data.get("_type") == "dict[DataFrame]":
            result = {}
            for code, item in data.get("items", {}).items():
                result[code] = pd.DataFrame(item["records"], columns=item["columns"])
            return result
        elif isinstance(data, dict) and data.get("_type") == "DataFrame":
            return {"_single": pd.DataFrame(data["records"], columns=data["columns"])}
    except Exception as e:
        logger.warning(f"反序列化 DataFrame 缓存失败 {key}: {e}")

    return None


def load_previous_kline_cache(today: str, max_days: int = 7) -> dict[str, pd.DataFrame] | None:
    """加载最近几天的K线缓存，用于增量更新。

    按日期倒序查找，找到第一个未过期的缓存即返回。
    缓存键格式: kline_{YYYY-MM-DD}
    K线缓存使用 7 天 TTL（而非默认 24 小时），以便跨天复用。

    Args:
        today: 今天的日期字符串，如 '2026-06-13'。
        max_days: 向前查找的最大天数。

    Returns:
        之前的缓存数据 {code: DataFrame}，未找到返回 None。
    """
    from datetime import timedelta

    kline_ttl = CACHE_TTL * 7  # K线缓存 7 天有效期
    today_date = datetime.strptime(today, "%Y-%m-%d")
    for i in range(1, max_days + 1):
        prev_date = today_date - timedelta(days=i)
        prev_key = f"kline_{prev_date.strftime('%Y-%m-%d')}"
        data = get_cached_data(prev_key, ttl=kline_ttl)
        if data is not None:
            try:
                if isinstance(data, dict) and data.get("_type") == "dict[DataFrame]":
                    result = {}
                    for code, item in data.get("items", {}).items():
                        result[code] = pd.DataFrame(item["records"], columns=item["columns"])
                    logger.info(f"找到前序K线缓存: {prev_key}，共 {len(result)} 只股票")
                    return result
            except Exception as e:
                logger.warning(f"反序列化前序K线缓存失败 {prev_key}: {e}")
    return None


def get_latest_date_in_kline(df: pd.DataFrame) -> str | None:
    """获取K线 DataFrame 中最新的日期。

    Args:
        df: K线数据 DataFrame，包含 '日期' 列。

    Returns:
        最新日期字符串，如 '2026-06-12'，无数据返回 None。
    """
    if df is None or df.empty or "日期" not in df.columns:
        return None
    try:
        return str(df["日期"].iloc[-1])
    except (IndexError, KeyError):
        return None


def needs_kline_update(df: pd.DataFrame, today: str) -> bool:
    """判断K线数据是否需要更新。

    如果最新数据日期早于今天（且今天是交易日），则需要更新。
    简化逻辑：只要最新日期不是今天，就认为需要更新。

    Args:
        df: K线数据 DataFrame。
        today: 今天的日期字符串。

    Returns:
        是否需要更新。
    """
    latest = get_latest_date_in_kline(df)
    if latest is None:
        return True
    # 比较日期（只取日期部分，忽略时间）
    return latest[:10] != today


def get_kline_update_start(df: pd.DataFrame, report_date: str) -> str | None:
    """返回增量更新的起始日期。如果不需要更新返回 None。

    用于增量更新策略：从「最后缓存日期」到「今天」拉取增量 K 线，
    与已有缓存拼接，避免全量重拉。

    Args:
        df: 已缓存的 K 线 DataFrame。
        report_date: 报告日期（今日），如 '2026-07-06'。

    Returns:
        增量起始日期字符串，或 None 表示无需更新。
    """
    if df is None or df.empty:
        return None
    date_col = "日期" if "日期" in df.columns else "date"
    if date_col not in df.columns:
        return None
    last_date = str(df[date_col].iloc[-1])[:10]
    if last_date >= report_date:
        return None  # 已是最新
    return last_date  # 从这个日期开始拉增量


def save_kline_cache_with_meta(
    key: str,
    data: dict[str, pd.DataFrame],
    codes: list[str],
) -> None:
    """保存K线缓存，附带元数据（股票列表、保存时间）。

    Args:
        key: 缓存键名。
        data: {code: DataFrame} 数据。
        codes: 请求的股票代码列表（用于后续判断完整性）。
    """
    _ensure_cache_dir()
    cache_file = _cache_path(key)

    try:
        serializable = {
            "_type": "dict[DataFrame]",
            "_meta": {
                "codes": codes,
                "saved_at": datetime.now().isoformat(),
                "count": len(data),
            },
            "items": {
                k: {"records": v.to_dict(orient="records"), "columns": list(v.columns)}
                for k, v in data.items()
                if isinstance(v, pd.DataFrame) and not v.empty
            },
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, default=str)
        logger.debug(f"K线缓存写入: {key}，包含 {len(data)} 只股票")
    except Exception as e:
        logger.warning(f"写入K线缓存失败 {key}: {e}")


def load_kline_cache_with_meta(key: str) -> tuple[dict[str, pd.DataFrame] | None, dict | None]:
    """加载K线缓存及其元数据。

    K线缓存使用 7 天 TTL（而非默认 24 小时），以便跨天复用。

    Args:
        key: 缓存键名。

    Returns:
        (数据字典, 元数据字典) 的元组，缓存不存在或过期返回 (None, None)。
    """
    kline_ttl = CACHE_TTL * 7  # K线缓存 7 天有效期
    data = get_cached_data(key, ttl=kline_ttl)
    if data is None:
        return None, None

    try:
        if isinstance(data, dict) and data.get("_type") == "dict[DataFrame]":
            result = {}
            for code, item in data.get("items", {}).items():
                result[code] = pd.DataFrame(item["records"], columns=item["columns"])
            meta = data.get("_meta")
            return result, meta
    except Exception as e:
        logger.warning(f"反序列化K线缓存失败 {key}: {e}")

    return None, None


def clear_expired_cache() -> int:
    """清理过期的缓存文件。

    Returns:
        清理的文件数量。
    """
    if not os.path.exists(CACHE_DIR):
        return 0

    count = 0
    now = datetime.now().timestamp()
    for filename in os.listdir(CACHE_DIR):
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(filepath) and filename.endswith(".json"):
            if now - os.path.getmtime(filepath) >= CACHE_TTL:
                try:
                    os.remove(filepath)
                    count += 1
                except OSError:
                    pass

    if count > 0:
        logger.info(f"清理了 {count} 个过期缓存文件")
    return count
