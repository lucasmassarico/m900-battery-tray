from pathlib import Path

from m900_battery_tray.capture import read_capture
from m900_battery_tray.frame import STATUS_CHARGING, STATUS_ON_BATTERY, BatteryFrame, parse_frame
from m900_battery_tray.state import (
    DeviceState,
    FrameReceived,
    Monitor,
    ReceiverLost,
    ReceiverOpened,
    Snapshot,
    Tick,
)

FIXTURES = Path(__file__).parent / "fixtures"
SLEEP_AFTER_S = 15.0
TICK_S = 1.0

ON_BATTERY_74 = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)
ON_BATTERY_73 = BatteryFrame(percent=73, status=STATUS_ON_BATTERY)
CHARGING_74 = BatteryFrame(percent=74, status=STATUS_CHARGING)

Timeline = list[tuple[float, Snapshot]]


def opened_monitor(at: float = 0.0) -> Monitor:
    return Monitor(sleep_after_s=SLEEP_AFTER_S).handle(ReceiverOpened(at=at))


def feed(monitor: Monitor, *frames: tuple[BatteryFrame, float]) -> Monitor:
    for frame, at in frames:
        monitor = monitor.handle(FrameReceived(frame=frame, at=at))
    return monitor


def connected_monitor() -> Monitor:
    return feed(opened_monitor(), (ON_BATTERY_74, 1.0), (ON_BATTERY_74, 3.0))


def replay(fixture: str, opened_at: float, ticks: bool = True) -> Timeline:
    """Feed a real capture through the monitor, with a Tick every second between reports,
    the way the reader thread does with its 1 s read timeout. `ticks=False` models a
    suspended PC, where no Tick happens while the process is frozen."""
    monitor = opened_monitor(at=opened_at)
    timeline: Timeline = [(opened_at, monitor.snapshot)]
    now = opened_at
    for captured in read_capture(FIXTURES / fixture):
        while ticks and now + TICK_S < captured.elapsed_s:
            now += TICK_S
            monitor = monitor.handle(Tick(at=now))
            timeline.append((now, monitor.snapshot))
        frame = parse_frame(captured.data)
        now = captured.elapsed_s
        # Like the reader thread: a report that isn't a battery frame only counts as a Tick.
        event = Tick(at=now) if frame is None else FrameReceived(frame=frame, at=now)
        monitor = monitor.handle(event)
        timeline.append((now, monitor.snapshot))
    return timeline


def snapshot_at(timeline: Timeline, at: float) -> Snapshot:
    return [snapshot for time, snapshot in timeline if time <= at][-1]


def test_starts_without_a_receiver() -> None:
    assert Monitor(sleep_after_s=SLEEP_AFTER_S).snapshot == Snapshot(
        state=DeviceState.NO_RECEIVER, percent=None
    )


def test_opening_the_receiver_waits_for_a_level() -> None:
    assert opened_monitor().snapshot == Snapshot(state=DeviceState.WAITING, percent=None)


def test_a_single_frame_is_not_shown() -> None:
    monitor = feed(opened_monitor(), (ON_BATTERY_74, 1.0))

    assert monitor.snapshot == Snapshot(state=DeviceState.WAITING, percent=None)


def test_two_equal_frames_show_the_level() -> None:
    assert connected_monitor().snapshot == Snapshot(state=DeviceState.CONNECTED, percent=74)


def test_two_charging_frames_show_charging() -> None:
    monitor = feed(opened_monitor(), (CHARGING_74, 1.0), (CHARGING_74, 3.0))

    assert monitor.snapshot == Snapshot(state=DeviceState.CHARGING, percent=74)


def test_a_new_level_needs_two_equal_frames() -> None:
    monitor = feed(connected_monitor(), (ON_BATTERY_73, 5.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.CONNECTED, percent=74)

    monitor = feed(monitor, (ON_BATTERY_73, 7.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.CONNECTED, percent=73)


def test_plugging_the_cable_needs_two_charging_frames() -> None:
    monitor = feed(connected_monitor(), (CHARGING_74, 5.0))
    assert monitor.snapshot.state is DeviceState.CONNECTED

    monitor = feed(monitor, (CHARGING_74, 7.0))
    assert monitor.snapshot.state is DeviceState.CHARGING


def test_silence_shorter_than_the_timeout_keeps_the_mouse_connected() -> None:
    monitor = connected_monitor().handle(Tick(at=3.0 + SLEEP_AFTER_S - 0.5))

    assert monitor.snapshot == Snapshot(state=DeviceState.CONNECTED, percent=74)


def test_silence_for_the_timeout_shows_asleep_and_keeps_the_level() -> None:
    monitor = connected_monitor().handle(Tick(at=3.0 + SLEEP_AFTER_S))

    assert monitor.snapshot == Snapshot(state=DeviceState.ASLEEP, percent=74)


def test_a_charging_mouse_can_fall_asleep() -> None:
    monitor = feed(opened_monitor(), (CHARGING_74, 1.0), (CHARGING_74, 3.0))

    monitor = monitor.handle(Tick(at=3.0 + SLEEP_AFTER_S))

    assert monitor.snapshot == Snapshot(state=DeviceState.ASLEEP, percent=74)


def test_a_silent_receiver_after_opening_shows_asleep_without_a_level() -> None:
    monitor = opened_monitor(at=10.0).handle(Tick(at=10.0 + SLEEP_AFTER_S))

    assert monitor.snapshot == Snapshot(state=DeviceState.ASLEEP, percent=None)


def test_waking_up_needs_two_equal_frames() -> None:
    asleep = connected_monitor().handle(Tick(at=30.0))

    monitor = feed(asleep, (ON_BATTERY_73, 40.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.ASLEEP, percent=74)

    monitor = feed(monitor, (ON_BATTERY_73, 42.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.CONNECTED, percent=73)


def test_a_frame_before_a_long_silence_does_not_confirm_one_after_it() -> None:
    monitor = feed(opened_monitor(), (ON_BATTERY_74, 1.0), (ON_BATTERY_74, 1.0 + SLEEP_AFTER_S))

    assert monitor.snapshot == Snapshot(state=DeviceState.WAITING, percent=None)


def test_losing_the_receiver_keeps_the_last_level() -> None:
    monitor = connected_monitor().handle(ReceiverLost(at=4.0))

    assert monitor.snapshot == Snapshot(state=DeviceState.NO_RECEIVER, percent=74)


def test_ticks_without_a_receiver_change_nothing() -> None:
    lost = connected_monitor().handle(ReceiverLost(at=4.0))

    assert lost.handle(Tick(at=100.0)) == lost


def test_reopening_the_receiver_needs_two_new_frames() -> None:
    monitor = connected_monitor().handle(ReceiverLost(at=4.0)).handle(ReceiverOpened(at=8.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.WAITING, percent=74)

    monitor = feed(monitor, (ON_BATTERY_74, 9.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.WAITING, percent=74)

    monitor = feed(monitor, (ON_BATTERY_74, 11.0))
    assert monitor.snapshot == Snapshot(state=DeviceState.CONNECTED, percent=74)


def test_replay_mouse_sleep_capture() -> None:
    timeline = replay("mouse_sleep.txt", opened_at=0.11)
    connected_79 = Snapshot(state=DeviceState.CONNECTED, percent=79)
    asleep_79 = Snapshot(state=DeviceState.ASLEEP, percent=79)

    assert snapshot_at(timeline, 1.17) == Snapshot(state=DeviceState.WAITING, percent=None)
    assert snapshot_at(timeline, 3.17) == connected_79
    # Reports every 4 s while the mouse dozes off are not sleep.
    assert all(snapshot == connected_79 for time, snapshot in timeline if 3.17 <= time < 131.0)
    assert snapshot_at(timeline, 134.0) == asleep_79
    # The first report after waking up is not trusted on its own.
    assert snapshot_at(timeline, 137.15) == asleep_79
    assert snapshot_at(timeline, 139.15) == connected_79


def test_replay_cable_unplug_capture_hides_the_junk_report() -> None:
    timeline = replay("cable_unplug.txt", opened_at=263.0)

    assert snapshot_at(timeline, 265.84) == Snapshot(state=DeviceState.CHARGING, percent=74)
    assert snapshot_at(timeline, 280.11) == Snapshot(state=DeviceState.CHARGING, percent=74)
    assert snapshot_at(timeline, 282.11) == Snapshot(state=DeviceState.CONNECTED, percent=83)
    assert {snapshot.percent for _, snapshot in timeline} == {None, 74, 83}


def test_replay_cable_plug_in_capture_hides_the_junk_report() -> None:
    timeline = replay("cable_plug_in.txt", opened_at=0.11)

    assert snapshot_at(timeline, 4.17) == Snapshot(state=DeviceState.CONNECTED, percent=78)
    assert snapshot_at(timeline, 6.17) == Snapshot(state=DeviceState.CONNECTED, percent=78)
    assert snapshot_at(timeline, 8.18) == Snapshot(state=DeviceState.CHARGING, percent=78)
    assert snapshot_at(timeline, 32.22) == Snapshot(state=DeviceState.CHARGING, percent=78)
    assert snapshot_at(timeline, 34.22) == Snapshot(state=DeviceState.CHARGING, percent=81)
    assert {snapshot.percent for _, snapshot in timeline} == {None, 78, 81}


def test_replay_pc_sleep_capture_keeps_the_level_after_resume() -> None:
    timeline = replay("pc_sleep.txt", opened_at=0.11, ticks=False)
    connected_78 = Snapshot(state=DeviceState.CONNECTED, percent=78)

    assert snapshot_at(timeline, 27.70) == connected_78
    # The first report after resume is not trusted on its own, so nothing changes.
    assert snapshot_at(timeline, 130.00) == connected_78
    assert snapshot_at(timeline, 142.01) == connected_78
    assert {snapshot.state for time, snapshot in timeline if time >= 9.70} == {
        DeviceState.CONNECTED
    }


def test_replay_charging_until_full_ignores_the_lone_status_2_report() -> None:
    timeline = replay("charging_until_full.txt", opened_at=986.0, ticks=False)
    charging_81 = Snapshot(state=DeviceState.CHARGING, percent=81)

    assert snapshot_at(timeline, 988.86) == charging_81
    assert snapshot_at(timeline, 990.87) == charging_81
    assert snapshot_at(timeline, 2766.96) == charging_81
    assert snapshot_at(timeline, 2768.96) == Snapshot(state=DeviceState.CONNECTED, percent=100)


def test_replay_receiver_replug_burst_ignores_the_junk_reports() -> None:
    timeline = replay("receiver_replug_burst.txt", opened_at=748.94)

    assert snapshot_at(timeline, 749.39) == Snapshot(state=DeviceState.WAITING, percent=None)
    assert snapshot_at(timeline, 750.71) == Snapshot(state=DeviceState.CHARGING, percent=81)


def test_replay_receiver_replug_capture() -> None:
    frames = {
        captured.elapsed_s: parse_frame(captured.data)
        for captured in read_capture(FIXTURES / "receiver_replug.txt")
    }
    monitor = opened_monitor(at=0.11)
    for at in (0.31, 2.31, 4.31, 6.31):
        monitor = monitor.handle(FrameReceived(frame=frames[at], at=at))
    assert monitor.snapshot == Snapshot(state=DeviceState.CHARGING, percent=74)

    monitor = monitor.handle(ReceiverLost(at=9.97))
    assert monitor.snapshot == Snapshot(state=DeviceState.NO_RECEIVER, percent=74)

    monitor = monitor.handle(ReceiverOpened(at=14.60))
    monitor = monitor.handle(FrameReceived(frame=frames[16.32], at=16.32))
    assert monitor.snapshot == Snapshot(state=DeviceState.WAITING, percent=74)

    monitor = monitor.handle(FrameReceived(frame=frames[18.32], at=18.32))
    assert monitor.snapshot == Snapshot(state=DeviceState.CHARGING, percent=74)
