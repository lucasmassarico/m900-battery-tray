from datetime import datetime

from m900_battery_tray.capture import (
    format_collection_line,
    format_event_line,
    format_frame_line,
)
from m900_battery_tray.hid_transport import HidCollection

WALL_TIME = datetime(2026, 11, 22, 14, 2, 3, 123456)


def test_format_frame_line_shows_time_delta_and_hex_bytes() -> None:
    line = format_frame_line(WALL_TIME, 3.74, 2.0, bytes.fromhex("033040014c"))

    assert line == "2026-11-22T14:02:03.123  t=    3.74  dt=  2.00  03 30 40 01 4c"


def test_format_frame_line_without_previous_frame_has_no_delta() -> None:
    line = format_frame_line(WALL_TIME, 1.74, None, bytes.fromhex("033040014c"))

    assert line == "2026-11-22T14:02:03.123  t=    1.74  dt=     -  03 30 40 01 4c"


def test_format_event_line_is_a_comment() -> None:
    line = format_event_line(WALL_TIME, 12.5, "receiver FA65 disappeared")

    assert line == "# 2026-11-22T14:02:03.123  t=   12.50  receiver FA65 disappeared"


def test_format_collection_line_is_a_comment_with_ids_and_usage() -> None:
    collection = HidCollection(
        path=b"\\\\?\\hid#vid_1d57&pid_fa65&mi_02&col03",
        vendor_id=0x1D57,
        product_id=0xFA65,
        interface_number=2,
        usage_page=0x000A,
        usage=0x00,
        product="2.4G 8K HS Receiver",
    )

    assert format_collection_line(collection) == (
        "# 1D57:FA65  MI_02  usage 0x000a:0x00  '2.4G 8K HS Receiver'"
        "  \\\\?\\hid#vid_1d57&pid_fa65&mi_02&col03"
    )
