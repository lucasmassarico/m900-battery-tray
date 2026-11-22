from m900_battery_tray.config import Config
from m900_battery_tray.frame import STATUS_CHARGING, STATUS_ON_BATTERY, BatteryFrame
from m900_battery_tray.presenter import Presenter, TrayView
from m900_battery_tray.state import (
    DeviceState,
    FrameReceived,
    ReceiverLost,
    ReceiverOpened,
    Snapshot,
    Tick,
)
from m900_battery_tray.texts import Notification


class FakeDisplay:
    def __init__(self) -> None:
        self.views: list[TrayView] = []
        self.notifications: list[Notification] = []

    def show(self, view: TrayView) -> None:
        self.views.append(view)

    def notify(self, notification: Notification) -> None:
        self.notifications.append(notification)


def on_battery(percent: int) -> BatteryFrame:
    return BatteryFrame(percent=percent, status=STATUS_ON_BATTERY)


def started(config: Config | None = None) -> tuple[Presenter, FakeDisplay]:
    display = FakeDisplay()
    presenter = Presenter(config or Config(), display)
    presenter.start()
    return presenter, display


def feed_level(presenter: Presenter, frame: BatteryFrame, at: float) -> None:
    presenter.handle(FrameReceived(frame=frame, at=at))
    presenter.handle(FrameReceived(frame=frame, at=at + 2.0))


def test_start_shows_the_receiver_as_missing() -> None:
    _, display = started()

    assert display.views == [
        TrayView(
            snapshot=Snapshot(state=DeviceState.NO_RECEIVER, percent=None),
            tooltip="M900 Pro\nUSB receiver not found",
            status="USB receiver not found",
        )
    ]


def test_shows_each_change_once() -> None:
    presenter, display = started()

    presenter.handle(ReceiverOpened(at=0.0))
    feed_level(presenter, on_battery(85), at=1.0)
    presenter.handle(Tick(at=4.0))
    presenter.handle(FrameReceived(frame=on_battery(85), at=5.0))

    assert [view.snapshot for view in display.views] == [
        Snapshot(state=DeviceState.NO_RECEIVER, percent=None),
        Snapshot(state=DeviceState.WAITING, percent=None),
        Snapshot(state=DeviceState.CONNECTED, percent=85),
    ]
    assert display.views[-1].tooltip == "M900 Pro: 85%\nOn battery"
    assert display.views[-1].status == "Battery 85% · On battery"


def test_notifies_when_the_battery_runs_low() -> None:
    presenter, display = started()
    presenter.handle(ReceiverOpened(at=0.0))
    feed_level(presenter, on_battery(21), at=1.0)
    assert display.notifications == []

    feed_level(presenter, on_battery(20), at=5.0)

    assert display.notifications == [
        Notification(title="M900 battery low", message="20% left. Plug in the cable soon.")
    ]


def test_notifies_once_at_start_when_the_battery_is_already_critical() -> None:
    presenter, display = started()
    presenter.handle(ReceiverOpened(at=0.0))

    feed_level(presenter, on_battery(8), at=1.0)
    feed_level(presenter, on_battery(8), at=5.0)

    assert [notification.title for notification in display.notifications] == [
        "M900 battery critical"
    ]


def test_never_notifies_while_charging() -> None:
    presenter, display = started()
    presenter.handle(ReceiverOpened(at=0.0))

    feed_level(presenter, BatteryFrame(percent=5, status=STATUS_CHARGING), at=1.0)

    assert display.views[-1].snapshot == Snapshot(state=DeviceState.CHARGING, percent=5)
    assert display.notifications == []


def test_uses_the_configured_thresholds_and_sleep_time() -> None:
    config = Config(low_battery_percent=40, critical_battery_percent=15, sleep_after_seconds=30)
    presenter, display = started(config)
    presenter.handle(ReceiverOpened(at=0.0))
    feed_level(presenter, on_battery(40), at=1.0)

    presenter.handle(Tick(at=3.0 + 29.0))
    assert display.views[-1].snapshot.state is DeviceState.CONNECTED
    presenter.handle(Tick(at=3.0 + 30.0))

    assert display.views[-1].snapshot == Snapshot(state=DeviceState.ASLEEP, percent=40)
    assert [notification.title for notification in display.notifications] == ["M900 battery low"]


def test_losing_the_receiver_is_shown() -> None:
    presenter, display = started()
    presenter.handle(ReceiverOpened(at=0.0))
    feed_level(presenter, on_battery(85), at=1.0)

    presenter.handle(ReceiverLost(at=10.0))

    assert display.views[-1].snapshot == Snapshot(state=DeviceState.NO_RECEIVER, percent=85)
    assert display.views[-1].tooltip == "M900 Pro\nUSB receiver not found\nLast known: 85%"
