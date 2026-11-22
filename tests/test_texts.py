import pytest

from m900_battery_tray.alerts import Alert, AlertLevel
from m900_battery_tray.state import DeviceState, Snapshot
from m900_battery_tray.texts import (
    TOOLTIP_MAX_LENGTH,
    Notification,
    alert_notification,
    status_line,
    tooltip,
)

LOW, CRITICAL = 20, 10


def tip(state: DeviceState, percent: int | None) -> str:
    return tooltip(Snapshot(state=state, percent=percent), LOW, CRITICAL)


@pytest.mark.parametrize(
    ("state", "percent", "expected"),
    [
        (DeviceState.CONNECTED, 85, "M900 Pro: 85%\nOn battery"),
        (DeviceState.CONNECTED, 20, "M900 Pro: 20%\nLow battery"),
        (DeviceState.CONNECTED, 10, "M900 Pro: 10%\nCritical battery"),
        (DeviceState.CHARGING, 64, "M900 Pro\nCharging\nLevel shown after unplugging"),
        (DeviceState.CHARGING, None, "M900 Pro\nCharging\nLevel shown after unplugging"),
        (DeviceState.ASLEEP, 42, "M900 Pro: 42%\nAsleep"),
        (DeviceState.ASLEEP, None, "M900 Pro\nAsleep"),
        (DeviceState.WAITING, None, "M900 Pro\nWaiting for the battery level"),
        (DeviceState.WAITING, 42, "M900 Pro\nWaiting for the battery level\nLast known: 42%"),
        (DeviceState.NO_RECEIVER, None, "M900 Pro\nUSB receiver not found"),
        (DeviceState.NO_RECEIVER, 63, "M900 Pro\nUSB receiver not found\nLast known: 63%"),
    ],
)
def test_tooltip(state: DeviceState, percent: int | None, expected: str) -> None:
    assert tip(state, percent) == expected


@pytest.mark.parametrize("state", list(DeviceState))
def test_tooltips_fit_the_windows_limit(state: DeviceState) -> None:
    assert len(tip(state, 100)) <= TOOLTIP_MAX_LENGTH


@pytest.mark.parametrize(
    ("state", "percent", "expected"),
    [
        (DeviceState.CONNECTED, 85, "Battery 85% · On battery"),
        (DeviceState.CHARGING, 64, "Charging"),
        (DeviceState.ASLEEP, 42, "Battery 42% · Asleep"),
        (DeviceState.ASLEEP, None, "Mouse asleep"),
        (DeviceState.WAITING, 42, "Waiting for the battery level"),
        (DeviceState.NO_RECEIVER, 63, "USB receiver not found"),
    ],
)
def test_status_line(state: DeviceState, percent: int | None, expected: str) -> None:
    assert status_line(Snapshot(state=state, percent=percent)) == expected


def test_low_alert_notification() -> None:
    assert alert_notification(Alert(level=AlertLevel.LOW, percent=18)) == Notification(
        title="M900 battery low", message="18% left. Plug in the cable soon."
    )


def test_critical_alert_notification() -> None:
    assert alert_notification(Alert(level=AlertLevel.CRITICAL, percent=7)) == Notification(
        title="M900 battery critical",
        message="7% left. Charge it now, before the mouse turns off.",
    )
