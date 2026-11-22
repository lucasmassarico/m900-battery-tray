from datetime import datetime
from pathlib import Path

import pytest

from m900_battery_tray.capture import (
    CapturedFrame,
    format_collection_line,
    format_event_line,
    format_frame_line,
    parse_frame_line,
    read_capture,
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


def test_parse_frame_line_reads_elapsed_time_and_bytes() -> None:
    line = "2026-11-22T14:01:34.147  t=    3.82  dt=  2.01  03 30 40 01 4a"

    assert parse_frame_line(line) == CapturedFrame(elapsed_s=3.82, data=bytes.fromhex("033040014a"))


def test_parse_frame_line_reads_what_format_frame_line_writes() -> None:
    data = bytes.fromhex("033040034a")
    line = format_frame_line(WALL_TIME, 125.23, None, data)

    assert parse_frame_line(line) == CapturedFrame(elapsed_s=125.23, data=data)


@pytest.mark.parametrize("line", ["", "   ", "# 2026-11-22T14:07:12.027  t=  9.97  read error"])
def test_parse_frame_line_skips_comments_and_blank_lines(line: str) -> None:
    assert parse_frame_line(line) is None


def test_parse_frame_line_rejects_a_malformed_line() -> None:
    with pytest.raises(ValueError, match="not a capture line"):
        parse_frame_line("03 30 40 01 4a")


def test_read_capture_returns_only_the_frames(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    capture.write_text(
        "# 2026-11-22T14:07:02.164  t=    0.11  opened battery collection <path>\n"
        "2026-11-22T14:07:02.369  t=    0.31  dt=     -  03 30 40 03 4a\n"
        "# 2026-11-22T14:07:12.027  t=    9.97  read error: read error\n"
        "2026-11-22T14:07:18.377  t=   16.32  dt= 10.01  03 30 40 03 4a\n",
        encoding="utf-8",
    )

    assert read_capture(capture) == [
        CapturedFrame(elapsed_s=0.31, data=bytes.fromhex("033040034a")),
        CapturedFrame(elapsed_s=16.32, data=bytes.fromhex("033040034a")),
    ]
