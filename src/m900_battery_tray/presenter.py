"""Glue between the state machine, the alert rules and whatever displays them.

Runs on the reader thread: every event goes through the state machine, and the display is
told only about real changes (a new snapshot, or an alert to show).
"""

from dataclasses import dataclass
from typing import Protocol

from m900_battery_tray.alerts import ThresholdAlerts
from m900_battery_tray.config import Config
from m900_battery_tray.state import Event, Monitor, Snapshot
from m900_battery_tray.texts import Notification, alert_notification, status_line, tooltip


@dataclass(frozen=True)
class TrayView:
    """Everything the tray needs to draw itself."""

    snapshot: Snapshot
    tooltip: str
    status: str


class Display(Protocol):
    def show(self, view: TrayView) -> None: ...

    def notify(self, notification: Notification) -> None: ...


class Presenter:
    def __init__(self, config: Config, display: Display) -> None:
        self._config = config
        self._display = display
        self._monitor = Monitor(sleep_after_s=config.sleep_after_seconds)
        self._alerts = ThresholdAlerts.from_config(config)

    def start(self) -> None:
        self._show(self._monitor.snapshot)

    def handle(self, event: Event) -> None:
        before = self._monitor.snapshot
        self._monitor = self._monitor.handle(event)
        snapshot = self._monitor.snapshot
        if snapshot == before:
            return
        self._show(snapshot)
        self._alerts, alert = self._alerts.update(snapshot)
        if alert is not None:
            self._display.notify(alert_notification(alert))

    def _show(self, snapshot: Snapshot) -> None:
        low, critical = self._config.low_battery_percent, self._config.critical_battery_percent
        self._display.show(
            TrayView(
                snapshot=snapshot,
                tooltip=tooltip(snapshot, low, critical),
                status=status_line(snapshot),
            )
        )
