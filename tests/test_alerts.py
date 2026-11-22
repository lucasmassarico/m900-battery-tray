from m900_battery_tray.alerts import Alert, AlertLevel, ThresholdAlerts
from m900_battery_tray.config import Config
from m900_battery_tray.state import DeviceState, Snapshot

LOW = AlertLevel.LOW
CRITICAL = AlertLevel.CRITICAL


def on_battery(percent: int) -> Snapshot:
    return Snapshot(state=DeviceState.CONNECTED, percent=percent)


def charging(percent: int) -> Snapshot:
    return Snapshot(state=DeviceState.CHARGING, percent=percent)


def default_alerts() -> ThresholdAlerts:
    return ThresholdAlerts(low_percent=20, critical_percent=10)


def run(
    snapshots: list[Snapshot], alerts: ThresholdAlerts | None = None
) -> tuple[ThresholdAlerts, list[Alert | None]]:
    alerts = alerts if alerts is not None else default_alerts()
    fired: list[Alert | None] = []
    for snapshot in snapshots:
        alerts, alert = alerts.update(snapshot)
        fired.append(alert)
    return alerts, fired


def test_no_alert_above_the_thresholds() -> None:
    _, fired = run([on_battery(50), on_battery(40), on_battery(21)])

    assert fired == [None, None, None]


def test_crossing_the_low_threshold_alerts_once() -> None:
    _, fired = run([on_battery(50), on_battery(20), on_battery(19), on_battery(18)])

    assert fired == [None, Alert(level=LOW, percent=20), None, None]


def test_rising_above_the_threshold_rearms_it() -> None:
    levels = [50, 20, 19, 20, 21, 20]

    _, fired = run([on_battery(percent) for percent in levels])

    assert fired == [
        None,
        Alert(level=LOW, percent=20),
        None,
        None,
        None,
        Alert(level=LOW, percent=20),
    ]


def test_low_then_critical() -> None:
    _, fired = run([on_battery(25), on_battery(15), on_battery(10), on_battery(9)])

    assert fired == [None, Alert(level=LOW, percent=15), Alert(level=CRITICAL, percent=10), None]


def test_skipping_past_both_thresholds_sends_only_the_critical_alert() -> None:
    alerts, fired = run([on_battery(25), on_battery(8)])

    assert fired == [None, Alert(level=CRITICAL, percent=8)]
    _, fired = run([on_battery(7)], alerts)
    assert fired == [None]


def test_starting_below_the_low_threshold_alerts_once() -> None:
    _, fired = run([on_battery(15), on_battery(15)])

    assert fired == [Alert(level=LOW, percent=15), None]


def test_starting_below_the_critical_threshold_alerts_once() -> None:
    _, fired = run([on_battery(8), on_battery(8)])

    assert fired == [Alert(level=CRITICAL, percent=8), None]


def test_charging_never_alerts() -> None:
    _, fired = run([charging(8), charging(9), charging(15)])

    assert fired == [None, None, None]


def test_unplugging_the_cable_at_a_low_level_alerts() -> None:
    _, fired = run([charging(8), on_battery(8)])

    assert fired == [None, Alert(level=CRITICAL, percent=8)]


def test_charging_above_both_thresholds_rearms_both() -> None:
    _, fired = run([on_battery(8), charging(30), on_battery(19)])

    assert fired == [Alert(level=CRITICAL, percent=8), None, Alert(level=LOW, percent=19)]


def test_charging_above_only_the_critical_threshold_rearms_only_it() -> None:
    _, fired = run([on_battery(8), charging(15), on_battery(15), on_battery(9)])

    assert fired == [Alert(level=CRITICAL, percent=8), None, None, Alert(level=CRITICAL, percent=9)]


def test_states_without_a_live_level_change_nothing() -> None:
    alerts = default_alerts()
    snapshots = [
        Snapshot(state=DeviceState.ASLEEP, percent=5),
        Snapshot(state=DeviceState.NO_RECEIVER, percent=5),
        Snapshot(state=DeviceState.WAITING, percent=5),
        Snapshot(state=DeviceState.WAITING, percent=None),
    ]

    for snapshot in snapshots:
        assert alerts.update(snapshot) == (alerts, None)


def test_thresholds_come_from_the_config() -> None:
    alerts = ThresholdAlerts.from_config(
        Config(low_battery_percent=30, critical_battery_percent=15)
    )

    _, fired = run([on_battery(31), on_battery(30), on_battery(15)], alerts)

    assert fired == [None, Alert(level=LOW, percent=30), Alert(level=CRITICAL, percent=15)]
