"""Text format of probe captures.

Frame lines double as test fixtures. Every other line starts with "#" so a fixture reader can
skip it.
"""

from datetime import datetime

from m900_battery_tray.hid_transport import HidCollection


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
