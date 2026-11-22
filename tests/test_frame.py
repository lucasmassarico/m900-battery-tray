from pathlib import Path

import pytest

from m900_battery_tray.capture import read_capture
from m900_battery_tray.frame import (
    STATUS_CHARGING,
    STATUS_FULL,
    STATUS_ON_BATTERY,
    BatteryFrame,
    confirm_frame,
    parse_frame,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("hex_frame", "expected"),
    [
        ("033040014a", BatteryFrame(percent=74, status=STATUS_ON_BATTERY)),
        ("033040034a", BatteryFrame(percent=74, status=STATUS_CHARGING)),
        ("033040014c", BatteryFrame(percent=76, status=STATUS_ON_BATTERY)),
        ("0350410145", BatteryFrame(percent=69, status=STATUS_ON_BATTERY)),
        ("0373410164", BatteryFrame(percent=100, status=STATUS_ON_BATTERY)),
        ("0330400100", BatteryFrame(percent=0, status=STATUS_ON_BATTERY)),
        ("0330400264", BatteryFrame(percent=100, status=STATUS_FULL)),
    ],
)
def test_parse_frame_accepts_battery_reports(hex_frame: str, expected: BatteryFrame) -> None:
    assert parse_frame(bytes.fromhex(hex_frame)) == expected


@pytest.mark.parametrize(
    "hex_frame",
    [
        pytest.param("", id="empty"),
        pytest.param("03304001", id="too-short"),
        pytest.param("033040014a00", id="too-long"),
        pytest.param("043040014a", id="vendor-report-id"),
        pytest.param("033042014a", id="unknown-event"),
        pytest.param("033000014a", id="zero-event"),
        pytest.param("0300c00000", id="replug-junk"),
        pytest.param("0330400165", id="percent-101"),
        pytest.param("03304001ff", id="percent-255"),
    ],
)
def test_parse_frame_rejects_other_reports(hex_frame: str) -> None:
    assert parse_frame(bytes.fromhex(hex_frame)) is None


@pytest.mark.parametrize("model", [0x00, 0x30, 0x3D, 0x50, 0x73, 0xFF])
def test_parse_frame_ignores_the_model_byte(model: int) -> None:
    frame = parse_frame(bytes([0x03, model, 0x40, 0x01, 0x4A]))

    assert frame == BatteryFrame(percent=74, status=STATUS_ON_BATTERY)


@pytest.mark.parametrize(
    ("status", "charging"),
    [(STATUS_ON_BATTERY, False), (STATUS_FULL, False), (STATUS_CHARGING, True), (0x07, False)],
)
def test_is_charging_only_for_status_3(status: int, charging: bool) -> None:
    assert BatteryFrame(percent=50, status=status).is_charging is charging


def test_confirm_frame_needs_a_previous_frame() -> None:
    assert confirm_frame(None, BatteryFrame(percent=74, status=STATUS_ON_BATTERY)) is None


def test_confirm_frame_confirms_two_equal_frames() -> None:
    frame = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)

    assert confirm_frame(frame, BatteryFrame(percent=74, status=STATUS_ON_BATTERY)) == frame


def test_confirm_frame_rejects_a_different_percent() -> None:
    previous = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)

    assert confirm_frame(previous, BatteryFrame(percent=73, status=STATUS_ON_BATTERY)) is None


def test_confirm_frame_rejects_a_different_status() -> None:
    previous = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)

    assert confirm_frame(previous, BatteryFrame(percent=74, status=STATUS_CHARGING)) is None


def test_alternating_frames_are_never_confirmed() -> None:
    a = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)
    b = BatteryFrame(percent=12, status=STATUS_ON_BATTERY)
    previous = None
    confirmed = []
    for frame in [a, b, a, b]:
        confirmed.append(confirm_frame(previous, frame))
        previous = frame

    assert confirmed == [None, None, None, None]


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("on_battery.txt", BatteryFrame(percent=74, status=STATUS_ON_BATTERY)),
        ("charging.txt", BatteryFrame(percent=74, status=STATUS_CHARGING)),
        ("receiver_replug.txt", BatteryFrame(percent=74, status=STATUS_CHARGING)),
    ],
)
def test_real_captures_parse_to_the_observed_level(fixture: str, expected: BatteryFrame) -> None:
    frames = [parse_frame(captured.data) for captured in read_capture(FIXTURES / fixture)]

    assert frames
    assert all(frame == expected for frame in frames)
