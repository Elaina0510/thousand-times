"""历史信号追踪模块测试。"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from history_tracker import (
    calculate_historical_accuracy,
    load_signal_history,
    record_signal,
    record_signals_batch,
    save_signal_history,
)


@pytest.fixture
def temp_history_file(monkeypatch):
    """使用临时文件替代真实的历史文件。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
        f.write("{}")

    # 修改模块中的文件路径
    import history_tracker
    monkeypatch.setattr(history_tracker, "HISTORY_FILE", temp_path)
    monkeypatch.setattr(history_tracker, "HISTORY_DIR", os.path.dirname(temp_path))

    yield temp_path

    # 清理
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestLoadSignalHistory:
    """测试加载历史数据。"""

    def test_empty_file(self, temp_history_file):
        """空文件应返回空字典。"""
        result = load_signal_history()
        assert result == {}

    def test_valid_data(self, temp_history_file):
        """有效数据应正确加载。"""
        data = {
            "600519": [
                {"date": "2026-06-01", "signal_score": 75, "price": 1800.0},
                {"date": "2026-06-02", "signal_score": 80, "price": 1820.0},
            ]
        }
        with open(temp_history_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_signal_history()
        assert "600519" in result
        assert len(result["600519"]) == 2

    def test_missing_file(self, monkeypatch):
        """文件不存在应返回空字典。"""
        import history_tracker
        monkeypatch.setattr(history_tracker, "HISTORY_FILE", "/nonexistent/path.json")

        result = load_signal_history()
        assert result == {}

    def test_invalid_json(self, temp_history_file):
        """JSON格式错误应返回空字典。"""
        with open(temp_history_file, "w", encoding="utf-8") as f:
            f.write("invalid json")

        result = load_signal_history()
        assert result == {}


class TestSaveSignalHistory:
    """测试保存历史数据。"""

    def test_save_and_load(self, temp_history_file):
        """保存后应能正确加载。"""
        data = {
            "600519": [
                {"date": "2026-06-01", "signal_score": 75, "price": 1800.0},
            ]
        }
        save_signal_history(data)

        loaded = load_signal_history()
        assert loaded == data

    def test_create_directory(self, monkeypatch):
        """应自动创建目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            import history_tracker
            monkeypatch.setattr(history_tracker, "HISTORY_DIR", tmpdir)
            monkeypatch.setattr(history_tracker, "HISTORY_FILE", os.path.join(tmpdir, "sub", "history.json"))

            save_signal_history({"test": []})
            assert os.path.exists(os.path.join(tmpdir, "sub", "history.json"))


class TestRecordSignal:
    """测试记录单个信号。"""

    def test_new_signal(self, temp_history_file):
        """新信号应正确记录。"""
        record_signal("600519", 75, 1800.0, "2026-06-01")

        history = load_signal_history()
        assert "600519" in history
        assert len(history["600519"]) == 1
        assert history["600519"][0]["signal_score"] == 75

    def test_append_signal(self, temp_history_file):
        """多个信号应追加记录。"""
        record_signal("600519", 75, 1800.0, "2026-06-01")
        record_signal("600519", 80, 1820.0, "2026-06-02")

        history = load_signal_history()
        assert len(history["600519"]) == 2

    def test_old_data_cleanup(self, temp_history_file, monkeypatch):
        """应清理超过365天的旧数据。"""
        # 模拟当前时间为2027-06-01
        import history_tracker
        mock_now = datetime(2027, 6, 1)

        class MockDatetime:
            @staticmethod
            def now():
                return mock_now

            @staticmethod
            def strptime(*args, **kwargs):
                return datetime.strptime(*args, **kwargs)

        monkeypatch.setattr(history_tracker, "datetime", MockDatetime)

        # 记录一条旧数据（超过365天）
        record_signal("600519", 75, 1800.0, "2026-01-01")
        # 记录一条新数据
        record_signal("600519", 80, 1820.0, "2027-05-01")

        history = load_signal_history()
        # 旧数据应被清理
        assert len(history["600519"]) == 1
        assert history["600519"][0]["date"] == "2027-05-01"


class TestRecordSignalsBatch:
    """测试批量记录信号。"""

    def test_batch_record(self, temp_history_file):
        """批量记录应正确工作。"""
        records = [
            ("600519", 75, 1800.0, "2026-06-01"),
            ("600519", 80, 1820.0, "2026-06-02"),
            ("000001", 60, 15.0, "2026-06-01"),
        ]
        record_signals_batch(records)

        history = load_signal_history()
        assert len(history["600519"]) == 2
        assert len(history["000001"]) == 1

    def test_empty_records(self, temp_history_file):
        """空记录列表不应报错。"""
        record_signals_batch([])

        history = load_signal_history()
        assert history == {}


class TestCalculateHistoricalAccuracy:
    """测试历史准确率计算。"""

    def test_no_history(self, temp_history_file):
        """无历史数据应返回0准确率。"""
        results = calculate_historical_accuracy("600519", [30, 90])
        assert len(results) == 2
        assert all(r.accuracy_rate == 0 for r in results)
        assert all(r.total_signals == 0 for r in results)

    def test_buy_signal_accuracy(self, temp_history_file, monkeypatch):
        """买入信号准确率计算。"""
        import history_tracker
        mock_now = datetime(2026, 6, 15)

        class MockDatetime:
            @staticmethod
            def now():
                return mock_now

            @staticmethod
            def strptime(date_str, fmt):
                return datetime.strptime(date_str, fmt)

        monkeypatch.setattr(history_tracker, "datetime", MockDatetime)

        # 记录买入信号和后续价格（使用观望评分避免被计入信号）
        records = [
            ("600519", 75, 100.0, "2026-06-01"),  # 买入信号
            ("600519", 50, 105.0, "2026-06-02"),  # 后续价格上涨（观望评分不计入信号）
            ("600519", 50, 108.0, "2026-06-03"),  # 继续上涨
            ("600519", 50, 103.0, "2026-06-04"),  # 回调
            ("600519", 50, 106.0, "2026-06-05"),  # 反弹
            ("600519", 50, 107.0, "2026-06-06"),  # 继续
        ]
        record_signals_batch(records)

        results = calculate_historical_accuracy("600519", [30])
        assert len(results) == 1
        assert results[0].accuracy_rate == 100.0  # 最高价108 > 信号价100
        assert results[0].total_signals == 1

    def test_sell_signal_accuracy(self, temp_history_file, monkeypatch):
        """卖出信号准确率计算。"""
        import history_tracker
        mock_now = datetime(2026, 6, 15)

        class MockDatetime:
            @staticmethod
            def now():
                return mock_now

            @staticmethod
            def strptime(date_str, fmt):
                return datetime.strptime(date_str, fmt)

        monkeypatch.setattr(history_tracker, "datetime", MockDatetime)

        # 记录卖出信号和后续价格（使用观望评分避免被计入信号）
        records = [
            ("600519", 25, 100.0, "2026-06-01"),  # 卖出信号
            ("600519", 50, 95.0, "2026-06-02"),   # 后续价格下跌（观望评分）
            ("600519", 50, 92.0, "2026-06-03"),   # 继续下跌
            ("600519", 50, 98.0, "2026-06-04"),   # 反弹
        ]
        record_signals_batch(records)

        results = calculate_historical_accuracy("600519", [30])
        assert len(results) == 1
        assert results[0].accuracy_rate == 100.0  # 最低价92 < 信号价100
        assert results[0].total_signals == 1

    def test_watch_signal_excluded(self, temp_history_file, monkeypatch):
        """观望信号不应计入准确率。"""
        import history_tracker
        mock_now = datetime(2026, 6, 15)

        class MockDatetime:
            @staticmethod
            def now():
                return mock_now

            @staticmethod
            def strptime(date_str, fmt):
                return datetime.strptime(date_str, fmt)

        monkeypatch.setattr(history_tracker, "datetime", MockDatetime)

        # 记录观望信号
        records = [
            ("600519", 50, 100.0, "2026-06-01"),  # 观望信号
            ("600519", 55, 105.0, "2026-06-02"),
        ]
        record_signals_batch(records)

        results = calculate_historical_accuracy("600519", [30])
        assert results[0].total_signals == 0  # 观望信号不计入

    def test_multiple_periods(self, temp_history_file, monkeypatch):
        """多周期计算应正确工作。"""
        import history_tracker
        mock_now = datetime(2026, 6, 15)

        class MockDatetime:
            @staticmethod
            def now():
                return mock_now

            @staticmethod
            def strptime(date_str, fmt):
                return datetime.strptime(date_str, fmt)

        monkeypatch.setattr(history_tracker, "datetime", MockDatetime)

        # 记录不同时间的信号（使用观望评分作为后续价格，避免被计入信号）
        # 30天前 = 2026-05-16，90天前 = 2026-03-17，180天前 = 2025-12-17
        records = [
            ("600519", 75, 100.0, "2026-05-20"),  # 30天内的买入信号（5月20日）
            ("600519", 50, 110.0, "2026-05-25"),  # 后续价格（观望评分）
            ("600519", 78, 105.0, "2026-03-20"),  # 90天内的买入信号（3月20日）
            ("600519", 50, 115.0, "2026-03-25"),  # 后续价格（观望评分）
        ]
        record_signals_batch(records)

        results = calculate_historical_accuracy("600519", [30, 90, 180])
        assert len(results) == 3
        # 30天内有1个信号（5月20日）
        assert results[0].total_signals == 1
        # 90天内有2个信号（5月20日和3月20日）
        assert results[1].total_signals == 2
        # 180天内有2个信号
        assert results[2].total_signals == 2
