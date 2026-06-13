"""cache_manager 模块测试。"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _reset_cache_stats():
    """每个测试前重置缓存统计。"""
    from cache_manager import _cache_stats
    _cache_stats["hit"] = 0
    _cache_stats["miss"] = 0
    yield
    _cache_stats["hit"] = 0
    _cache_stats["miss"] = 0


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """使用临时目录作为缓存目录。"""
    with patch("cache_manager.CACHE_DIR", str(tmp_path)):
        yield tmp_path


class TestCacheStats:
    """缓存统计功能测试。"""

    def test_initial_stats(self):
        from cache_manager import get_cache_stats
        stats = get_cache_stats()
        assert stats["hit"] == 0
        assert stats["miss"] == 0
        assert stats["total"] == 0
        assert stats["hit_rate"] == 0.0

    def test_hit_rate_calculation(self):
        from cache_manager import _cache_stats, get_cache_stats
        _cache_stats["hit"] = 3
        _cache_stats["miss"] = 1
        stats = get_cache_stats()
        assert stats["total"] == 4
        assert stats["hit_rate"] == 75.0

    def test_record_hit_miss(self):
        from cache_manager import _record_hit, _record_miss, _cache_stats
        _record_hit()
        _record_hit()
        _record_miss()
        assert _cache_stats["hit"] == 2
        assert _cache_stats["miss"] == 1


class TestGetCachedData:
    """get_cached_data 基础功能测试。"""

    def test_cache_hit(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data
        set_cached_data("test_key", {"a": 1})
        result = get_cached_data("test_key")
        assert result == {"a": 1}

    def test_cache_miss(self, tmp_cache_dir):
        from cache_manager import get_cached_data
        result = get_cached_data("nonexistent")
        assert result is None

    def test_cache_expired(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data, CACHE_TTL
        set_cached_data("old_key", {"a": 1})
        # 模拟文件过期
        path = os.path.join(str(tmp_cache_dir), "old_key.json")
        old_time = datetime.now().timestamp() - CACHE_TTL - 100
        os.utime(path, (old_time, old_time))
        result = get_cached_data("old_key")
        assert result is None

    def test_custom_ttl(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data
        set_cached_data("short_ttl", {"a": 1})
        # 使用极短 TTL 模拟过期
        path = os.path.join(str(tmp_cache_dir), "short_ttl.json")
        old_time = datetime.now().timestamp() - 200
        os.utime(path, (old_time, old_time))
        result = get_cached_data("short_ttl", ttl=100)
        assert result is None

    def test_stats_recorded(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data, _cache_stats
        set_cached_data("key1", {"a": 1})
        get_cached_data("key1")
        get_cached_data("nonexistent")
        assert _cache_stats["hit"] == 1
        assert _cache_stats["miss"] == 1


class TestSetCachedData:
    """set_cached_data 测试。"""

    def test_dict_data(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data
        set_cached_data("dict_key", {"x": 10, "y": 20})
        assert get_cached_data("dict_key") == {"x": 10, "y": 20}

    def test_list_data(self, tmp_cache_dir):
        from cache_manager import get_cached_data, set_cached_data
        set_cached_data("list_key", [1, 2, 3])
        assert get_cached_data("list_key") == [1, 2, 3]

    def test_dataframe_data(self, tmp_cache_dir):
        from cache_manager import load_cached_dataframe, set_cached_data
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        set_cached_data("df_key", df)
        result = load_cached_dataframe("df_key")
        assert result is not None
        assert "_single" in result
        assert list(result["_single"].columns) == ["a", "b"]

    def test_dict_of_dataframes(self, tmp_cache_dir):
        from cache_manager import load_cached_dataframe, set_cached_data
        data = {
            "code1": pd.DataFrame({"close": [10, 11]}),
            "code2": pd.DataFrame({"close": [20, 21]}),
        }
        set_cached_data("dict_df_key", data)
        result = load_cached_dataframe("dict_df_key")
        assert result is not None
        assert "code1" in result
        assert "code2" in result
        assert list(result["code1"].columns) == ["close"]


class TestLoadPreviousKlineCache:
    """load_previous_kline_cache 测试。"""

    def test_finds_previous_day(self, tmp_cache_dir):
        from cache_manager import load_previous_kline_cache, save_kline_cache_with_meta
        # 写入昨天的缓存
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        data = {"600519": pd.DataFrame({"close": [100], "日期": ["2026-06-12"]})}
        save_kline_cache_with_meta(f"kline_{yesterday}", data, ["600519"])

        result = load_previous_kline_cache(datetime.now().strftime("%Y-%m-%d"))
        assert result is not None
        assert "600519" in result

    def test_returns_none_when_no_previous(self, tmp_cache_dir):
        from cache_manager import load_previous_kline_cache
        result = load_previous_kline_cache("2026-06-13")
        assert result is None

    def test_respects_max_days(self, tmp_cache_dir):
        from cache_manager import load_previous_kline_cache, save_kline_cache_with_meta
        # 写入 10 天前的缓存
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        data = {"600519": pd.DataFrame({"close": [100], "日期": [old_date]})}
        save_kline_cache_with_meta(f"kline_{old_date}", data, ["600519"])

        # max_days=5 应该找不到
        result = load_previous_kline_cache(datetime.now().strftime("%Y-%m-%d"), max_days=5)
        assert result is None


class TestKlineHelpers:
    """K线缓存辅助函数测试。"""

    def test_get_latest_date(self):
        from cache_manager import get_latest_date_in_kline
        df = pd.DataFrame({"日期": ["2026-06-10", "2026-06-11", "2026-06-12"]})
        assert get_latest_date_in_kline(df) == "2026-06-12"

    def test_get_latest_date_empty(self):
        from cache_manager import get_latest_date_in_kline
        assert get_latest_date_in_kline(pd.DataFrame()) is None
        assert get_latest_date_in_kline(None) is None

    def test_needs_update_stale(self):
        from cache_manager import needs_kline_update
        df = pd.DataFrame({"日期": ["2026-06-10", "2026-06-11"]})
        assert needs_kline_update(df, "2026-06-13") is True

    def test_needs_update_fresh(self):
        from cache_manager import needs_kline_update
        df = pd.DataFrame({"日期": ["2026-06-12", "2026-06-13"]})
        assert needs_kline_update(df, "2026-06-13") is False

    def test_needs_update_empty(self):
        from cache_manager import needs_kline_update
        assert needs_kline_update(pd.DataFrame(), "2026-06-13") is True


class TestSaveLoadKlineMeta:
    """save/load_kline_cache_with_meta 测试。"""

    def test_roundtrip(self, tmp_cache_dir):
        from cache_manager import save_kline_cache_with_meta, load_kline_cache_with_meta
        data = {
            "600519": pd.DataFrame({"close": [100, 101], "日期": ["2026-06-12", "2026-06-13"]}),
            "000001": pd.DataFrame({"close": [10, 11], "日期": ["2026-06-12", "2026-06-13"]}),
        }
        save_kline_cache_with_meta("kline_2026-06-13", data, ["600519", "000001"])

        loaded, meta = load_kline_cache_with_meta("kline_2026-06-13")
        assert loaded is not None
        assert len(loaded) == 2
        assert "600519" in loaded
        assert meta is not None
        assert meta["count"] == 2
        assert "600519" in meta["codes"]

    def test_returns_none_for_missing(self, tmp_cache_dir):
        from cache_manager import load_kline_cache_with_meta
        loaded, meta = load_kline_cache_with_meta("nonexistent")
        assert loaded is None
        assert meta is None


class TestClearExpiredCache:
    """clear_expired_cache 测试。"""

    def test_clears_expired(self, tmp_cache_dir):
        from cache_manager import clear_expired_cache, CACHE_TTL, set_cached_data
        set_cached_data("expired", {"a": 1})
        set_cached_data("fresh", {"b": 2})

        # 将 "expired" 设为过期
        path = os.path.join(str(tmp_cache_dir), "expired.json")
        old_time = datetime.now().timestamp() - CACHE_TTL - 100
        os.utime(path, (old_time, old_time))

        count = clear_expired_cache()
        assert count == 1
        assert not os.path.exists(path)
        assert os.path.exists(os.path.join(str(tmp_cache_dir), "fresh.json"))
