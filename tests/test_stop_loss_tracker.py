"""StopLossTracker 单元测试."""

from __future__ import annotations

import pandas as pd

from risk.stop_loss import (
    StopLossRecord,
    StopLossSummary,
    check_stop_losses,
    generate_stop_loss_alert,
    init_tracking,
    update_stop_price,
)


class MockSignal:
    def __init__(self, code="000001", name="test", action="buy",
                 current_price=10.0, stop_loss=9.0, target=12.0):
        self.code = code
        self.name = name
        self.action = action
        self.confidence = 0.8
        self.key_prices = MockKeyPrices(current_price, stop_loss, target)


class MockKeyPrices:
    def __init__(self, current_price=10.0, stop_loss=9.0, target=12.0):
        self.current_price = current_price
        self.stop_loss = stop_loss
        self.target = target


def _make_kline(price=10.0, rows=60):
    dates = pd.date_range("2026-01-01", periods=rows, freq="B")
    return pd.DataFrame({
        "日期": dates,
        "收盘": [price] * rows,
        "成交量": [5000000] * rows,
    })


# ── init_tracking ──
def test_init_tracking():
    signals = [MockSignal(code="000001", action="buy")]
    records = init_tracking(signals, "2026-07-11")
    assert len(records) == 1
    assert records[0].code == "000001"
    assert records[0].status == "active"
    assert records[0].stop_loss_price == 9.0
    assert records[0].target_price == 12.0


def test_init_tracking_holds_ignored():
    signals = [MockSignal(code="000001", action="hold")]
    records = init_tracking(signals, "2026-07-11")
    assert len(records) == 0


def test_init_tracking_empty():
    records = init_tracking([], "2026-07-11")
    assert records == []


# ── check_stop_losses ──
def test_check_stop_loss_triggered():
    records = [
        StopLossRecord(code="000001", name="测试A", entry_date="2026-07-01",
                       entry_price=10.0, stop_loss_price=9.0, target_price=12.0,
                       current_price=10.0, status="active"),
    ]
    kline = {"000001": _make_kline(price=8.5)}  # 低于止损
    summary = check_stop_losses(records, kline, "2026-07-11")
    assert len(summary.stopped_out_today) >= 1


def test_check_stop_loss_target_hit():
    records = [
        StopLossRecord(code="000001", name="测试A", entry_date="2026-07-01",
                       entry_price=10.0, stop_loss_price=9.0, target_price=12.0,
                       current_price=10.0, status="active"),
    ]
    kline = {"000001": _make_kline(price=13.0)}  # 高于目标
    summary = check_stop_losses(records, kline, "2026-07-11")
    assert len(summary.target_hit_today) >= 1


def test_check_stop_loss_near_warning():
    records = [
        StopLossRecord(code="000001", name="测试A", entry_date="2026-07-01",
                       entry_price=10.0, stop_loss_price=9.0, target_price=12.0,
                       current_price=10.0, status="active"),
    ]
    kline = {"000001": _make_kline(price=9.2)}  # 距止损 2.2%
    summary = check_stop_losses(records, kline, "2026-07-11")
    assert len(summary.near_stop_loss) >= 1


def test_check_stop_loss_expired():
    """持仓超过30天."""
    records = [
        StopLossRecord(code="000001", name="测试A", entry_date="2026-06-01",
                       entry_price=10.0, stop_loss_price=9.0, target_price=12.0,
                       current_price=10.0, status="active"),
    ]
    kline = {"000001": _make_kline(price=10.0)}
    summary = check_stop_losses(records, kline, "2026-07-11")
    # 41 天后应该过期
    assert records[0].status == "expired"


def test_check_stop_loss_empty():
    summary = check_stop_losses([], {}, "2026-07-11")
    assert summary.active_count == 0


# ── update_stop_price ──
def test_update_stop_trailing():
    record = StopLossRecord(code="000001", entry_price=10.0, stop_loss_price=9.0)
    updated = update_stop_price(record, 10.0, "盈利 > 10%，保本止损")
    assert updated.stop_loss_price == 10.0


def test_trailing_stop_rules():
    """测试追踪止损规则."""
    # 盈利 25% → 止损上移到 entry + 10%
    record = StopLossRecord(code="000001", entry_price=10.0, stop_loss_price=9.0,
                            current_price=12.5, pnl_pct=25.0)
    pnl = record.pnl_pct
    if pnl > 30:
        new_stop = record.entry_price * 1.20
    elif pnl > 20:
        new_stop = record.entry_price * 1.10
    elif pnl > 10:
        new_stop = record.entry_price
    else:
        new_stop = record.stop_loss_price

    updated = update_stop_price(record, new_stop, f"盈利 {pnl:.0f}%")
    assert updated.stop_loss_price == 11.0  # entry * 1.10


# ── generate_stop_loss_alert ──
def test_generate_alert():
    summary = StopLossSummary(
        active_count=3,
        stopped_out_today=[
            StopLossRecord(code="000001", name="A", entry_price=10.0,
                           stop_loss_price=9.0, pnl_pct=-10.0),
        ],
        avg_pnl=2.5,
        win_rate=0.6,
    )
    alert = generate_stop_loss_alert(summary)
    assert "止损提醒" in alert
    assert "A" in alert
