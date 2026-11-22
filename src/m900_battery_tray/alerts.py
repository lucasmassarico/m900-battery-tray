"""Low-battery alert rules. Pure: the tray decides how to show an Alert.

Each threshold alerts once when the level on battery drops to it or below, and is rearmed
when the level rises above it again (on battery or while charging). A drop past both
thresholds at once sends only the critical alert. Charging never alerts.
"""

from dataclasses import dataclass, replace
from enum import Enum

from m900_battery_tray.config import Config
from m900_battery_tray.state import DeviceState, Snapshot


class AlertLevel(Enum):
    LOW = "low"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Alert:
    level: AlertLevel
    percent: int


@dataclass(frozen=True)
class ThresholdAlerts:
    low_percent: int
    critical_percent: int
    armed: frozenset[AlertLevel] = frozenset(AlertLevel)

    @classmethod
    def from_config(cls, config: Config) -> "ThresholdAlerts":
        return cls(
            low_percent=config.low_battery_percent,
            critical_percent=config.critical_battery_percent,
        )

    def update(self, snapshot: Snapshot) -> tuple["ThresholdAlerts", Alert | None]:
        percent = snapshot.percent
        if percent is None or snapshot.state not in (DeviceState.CONNECTED, DeviceState.CHARGING):
            return self, None

        thresholds = {AlertLevel.LOW: self.low_percent, AlertLevel.CRITICAL: self.critical_percent}
        rearmed = {level for level, threshold in thresholds.items() if percent > threshold}
        if snapshot.state is DeviceState.CHARGING:
            return replace(self, armed=self.armed | rearmed), None

        crossed = {level for level in self.armed if percent <= thresholds[level]}
        updated = replace(self, armed=frozenset((self.armed | rearmed) - crossed))
        if not crossed:
            return updated, None
        level = AlertLevel.CRITICAL if AlertLevel.CRITICAL in crossed else AlertLevel.LOW
        return updated, Alert(level=level, percent=percent)
