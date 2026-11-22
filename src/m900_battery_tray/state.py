"""Device state machine. Pure: time comes in with each event, nothing here does I/O.

The receiver goes silent while the mouse sleeps (see docs/protocol.md), so "asleep" means
"no battery report for `sleep_after_s` seconds". It needs neither the mouse's own sleep
setting nor the vendor app.
"""

from dataclasses import dataclass, replace
from enum import Enum
from typing import assert_never

from m900_battery_tray.frame import BatteryFrame, confirm_frame


class DeviceState(Enum):
    NO_RECEIVER = "receiver not found"
    WAITING = "waiting for the mouse"
    CONNECTED = "connected"
    CHARGING = "charging"
    ASLEEP = "asleep"


AWAKE_STATES = frozenset({DeviceState.WAITING, DeviceState.CONNECTED, DeviceState.CHARGING})


@dataclass(frozen=True)
class ReceiverOpened:
    at: float


@dataclass(frozen=True)
class ReceiverLost:
    at: float


@dataclass(frozen=True)
class FrameReceived:
    frame: BatteryFrame
    at: float


@dataclass(frozen=True)
class Tick:
    at: float


Event = ReceiverOpened | ReceiverLost | FrameReceived | Tick


@dataclass(frozen=True)
class Snapshot:
    """What the tray shows. `percent` is the last confirmed level, kept while the mouse
    sleeps or the receiver is missing, and None until a level has been confirmed."""

    state: DeviceState
    percent: int | None


@dataclass(frozen=True)
class Monitor:
    sleep_after_s: float
    state: DeviceState = DeviceState.NO_RECEIVER
    percent: int | None = None
    previous_frame: BatteryFrame | None = None
    last_activity_at: float | None = None

    @property
    def snapshot(self) -> Snapshot:
        return Snapshot(state=self.state, percent=self.percent)

    def handle(self, event: Event) -> "Monitor":
        match event:
            case ReceiverOpened(at=at):
                return replace(
                    self, state=DeviceState.WAITING, previous_frame=None, last_activity_at=at
                )
            case ReceiverLost():
                return replace(
                    self, state=DeviceState.NO_RECEIVER, previous_frame=None, last_activity_at=None
                )
            case Tick(at=at):
                if self.state in AWAKE_STATES and self._is_silent_at(at):
                    return replace(self, state=DeviceState.ASLEEP, previous_frame=None)
                return self
            case FrameReceived(frame=frame, at=at):
                return self._on_frame(frame, at)
            case _:
                assert_never(event)

    def _on_frame(self, frame: BatteryFrame, at: float) -> "Monitor":
        # A report that follows a long silence starts over: the first one after a relink
        # can be junk, even when no Tick marked the silence.
        previous = None if self._is_silent_at(at) else self.previous_frame
        updated = replace(self, previous_frame=frame, last_activity_at=at)
        confirmed = confirm_frame(previous, frame)
        if confirmed is None:
            return updated
        state = DeviceState.CHARGING if confirmed.is_charging else DeviceState.CONNECTED
        return replace(updated, state=state, percent=confirmed.percent)

    def _is_silent_at(self, at: float) -> bool:
        return (
            self.last_activity_at is not None and at - self.last_activity_at >= self.sleep_after_s
        )
