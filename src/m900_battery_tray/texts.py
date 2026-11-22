"""User-facing text: tooltip, menu status line and notifications."""

from dataclasses import dataclass
from typing import assert_never

from m900_battery_tray.alerts import Alert, AlertLevel
from m900_battery_tray.state import DeviceState, Snapshot

MODEL_NAME = "M900 Pro"
# NOTIFYICONDATAW.szTip holds 128 characters including the terminating null.
TOOLTIP_MAX_LENGTH = 127
SETTINGS_TITLE = "M900 tray settings"


@dataclass(frozen=True)
class Notification:
    title: str
    message: str


def tooltip(snapshot: Snapshot, low_percent: int, critical_percent: int) -> str:
    state, percent = snapshot.state, snapshot.percent
    last_known = [] if percent is None else [f"Last known: {percent}%"]
    match state:
        case DeviceState.CONNECTED:
            lines = [_with_percent(percent), _battery_band(percent, low_percent, critical_percent)]
        case DeviceState.CHARGING:
            # The mouse freezes the level while charging, so it isn't shown.
            lines = [MODEL_NAME, "Charging", "Level shown after unplugging"]
        case DeviceState.ASLEEP:
            lines = [_with_percent(percent), "Asleep"]
        case DeviceState.WAITING:
            lines = [MODEL_NAME, "Waiting for the battery level", *last_known]
        case DeviceState.NO_RECEIVER:
            lines = [MODEL_NAME, "USB receiver not found", *last_known]
        case _:
            assert_never(state)
    return "\n".join(lines)


def status_line(snapshot: Snapshot) -> str:
    state, percent = snapshot.state, snapshot.percent
    match state:
        case DeviceState.CONNECTED:
            return f"Battery {percent}% · On battery"
        case DeviceState.CHARGING:
            return "Charging"
        case DeviceState.ASLEEP:
            return "Mouse asleep" if percent is None else f"Battery {percent}% · Asleep"
        case DeviceState.WAITING:
            return "Waiting for the battery level"
        case DeviceState.NO_RECEIVER:
            return "USB receiver not found"
        case _:
            assert_never(state)


def alert_notification(alert: Alert) -> Notification:
    if alert.level is AlertLevel.CRITICAL:
        return Notification(
            title="M900 battery critical",
            message=f"{alert.percent}% left. Charge it now, before the mouse turns off.",
        )
    return Notification(
        title="M900 battery low", message=f"{alert.percent}% left. Plug in the cable soon."
    )


def settings_applied() -> Notification:
    return Notification(title=SETTINGS_TITLE, message="New settings applied.")


def settings_rejected(reason: str, *, at_start: bool) -> Notification:
    fallback = "Using the default settings." if at_start else "Keeping the previous settings."
    return Notification(title=SETTINGS_TITLE, message=f"{reason}. {fallback}")


def _with_percent(percent: int | None) -> str:
    return MODEL_NAME if percent is None else f"{MODEL_NAME}: {percent}%"


def _battery_band(percent: int | None, low_percent: int, critical_percent: int) -> str:
    if percent is not None and percent <= critical_percent:
        return "Critical battery"
    if percent is not None and percent <= low_percent:
        return "Low battery"
    return "On battery"
