"""Text format of probe captures.

Frame lines double as test fixtures. Every other line starts with "#" so a fixture reader can
skip it.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from m900_battery_tray.hid_transport import HidCollection

_FRAME_LINE = re.compile(
    r"^\S+\s+t=\s*(?P<elapsed>\d+(?:\.\d+)?)\s+dt=\s*\S+\s+(?P<hex>[0-9a-f]{2}(?: [0-9a-f]{2})*)$"
)


@dataclass(frozen=True)
class CapturedFrame:
    elapsed_s: float
    data: bytes


def format_frame_line(
    wall_time: datetime, elapsed_s: float, delta_s: float | None, data: bytes
) -> str:
    delta = f"{delta_s:6.2f}" if delta_s is not None else "     -"
    timestamp = wall_time.isoformat(timespec="milliseconds")
    return f"{timestamp}  t={elapsed_s:8.2f}  dt={delta}  {data.hex(' ')}"


def format_event_line(wall_time: datetime, elapsed_s: float, message: str) -> str:
    timestamp = wall_time.isoformat(timespec="milliseconds")
    return f"# {timestamp}  t={elapsed_s:8.2f}  {message}"


def format_collection_line(collection: HidCollection) -> str:
    return (
        f"# {collection.vendor_id:04X}:{collection.product_id:04X}"
        f"  MI_{collection.interface_number:02d}"
        f"  usage {collection.usage_page:#06x}:{collection.usage:#04x}"
        f"  {collection.product!r}"
        f"  {collection.path.decode(errors='replace')}"
    )


def parse_frame_line(line: str) -> CapturedFrame | None:
    """Return the frame on a capture line, None for a blank or "#" line.

    Raises ValueError for anything else, so a corrupted fixture fails loudly.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = _FRAME_LINE.match(stripped)
    if match is None:
        raise ValueError(f"not a capture line: {line!r}")
    return CapturedFrame(elapsed_s=float(match["elapsed"]), data=bytes.fromhex(match["hex"]))


def read_capture(path: Path) -> list[CapturedFrame]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [frame for frame in map(parse_frame_line, lines) if frame is not None]
