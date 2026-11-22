"""Battery report parsing, following the rules in docs/protocol.md."""

from dataclasses import dataclass

FRAME_LENGTH = 5
REPORT_ID = 0x03
BATTERY_EVENTS = frozenset({0x40, 0x41})
MAX_PERCENT = 100

STATUS_ON_BATTERY = 1
STATUS_FULL = 2
STATUS_CHARGING = 3


@dataclass(frozen=True)
class BatteryFrame:
    percent: int
    status: int

    @property
    def is_charging(self) -> bool:
        return self.status == STATUS_CHARGING


def parse_frame(data: bytes) -> BatteryFrame | None:
    """Return the battery frame in a raw COL03 report, or None if it isn't one.

    Byte 1 is the model code and is ignored on purpose: it differs between units.
    """
    if len(data) != FRAME_LENGTH or data[0] != REPORT_ID or data[2] not in BATTERY_EVENTS:
        return None
    percent = data[4]
    if percent > MAX_PERCENT:
        return None
    return BatteryFrame(percent=percent, status=data[3])


def confirm_frame(previous: BatteryFrame | None, current: BatteryFrame) -> BatteryFrame | None:
    """Return the current frame only if it equals the previous one.

    The first report after a relink can be junk, so a level is shown only after two
    consecutive equal frames. Pass None as `previous` after a relink to start over.
    """
    return current if current == previous else None
