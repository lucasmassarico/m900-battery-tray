import logging
from dataclasses import replace

import pytest

from m900_battery_tray.frame import STATUS_ON_BATTERY, BatteryFrame
from m900_battery_tray.hid_transport import HidCollection
from m900_battery_tray.reader import REOPEN_AFTER_SILENCE_S, Reader
from m900_battery_tray.state import Event, FrameReceived, ReceiverLost, ReceiverOpened, Tick

BATTERY = HidCollection(
    path=b"col03",
    vendor_id=0x1D57,
    product_id=0xFA65,
    interface_number=2,
    usage_page=0x000A,
    usage=0x00,
    product="2.4G 8K HS Receiver",
)
VENDOR_CHANNEL = replace(BATTERY, path=b"col04", usage_page=0xFF00, usage=0x01)
REPORT_74 = bytes.fromhex("033040014a")
FRAME_74 = BatteryFrame(percent=74, status=STATUS_ON_BATTERY)

Script = list[tuple[float, bytes | OSError]]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeStop:
    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self._set = False

    def set(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def wait(self, timeout: float) -> bool:
        self._clock.advance(timeout)
        return self._set


class FakeHidReader:
    """Plays a script of (delay, report or error); once it runs out, every read times out."""

    def __init__(self, clock: FakeClock, script: Script) -> None:
        self._clock = clock
        self._script = list(script)
        self.closed = False

    def read(self, size: int, timeout_ms: int) -> bytes:
        delay, payload = self._script.pop(0) if self._script else (timeout_ms / 1000, b"")
        self._clock.advance(delay)
        if isinstance(payload, OSError):
            raise payload
        return payload

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.collections: list[HidCollection] = []
        self.scripts: list[Script] = []
        self.open_error: OSError | None = None
        self.opened: list[bytes] = []
        self.readers: list[FakeHidReader] = []

    def enumerate(self, vendor_id: int, product_id: int) -> list[HidCollection]:
        return [
            collection
            for collection in self.collections
            if collection.vendor_id == vendor_id and collection.product_id == product_id
        ]

    def open(self, path: bytes) -> FakeHidReader:
        self.opened.append(path)
        if self.open_error is not None:
            raise self.open_error
        reader = FakeHidReader(self.clock, self.scripts.pop(0) if self.scripts else [])
        self.readers.append(reader)
        return reader


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def transport(clock: FakeClock) -> FakeTransport:
    return FakeTransport(clock)


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def reader(transport: FakeTransport, clock: FakeClock, events: list[Event]) -> Reader:
    return Reader(transport, events.append, FakeStop(clock), clock=clock)


def steps(reader: Reader, count: int) -> None:
    for _ in range(count):
        reader.step()


def test_waits_for_the_receiver(reader: Reader, clock: FakeClock, events: list[Event]) -> None:
    reader.step()

    assert events == []
    assert clock.now == 2.0


def test_opens_only_the_battery_collection(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [VENDOR_CHANNEL, BATTERY]

    reader.step()

    assert events == [ReceiverOpened(at=0.0)]
    assert transport.opened == [b"col03"]


def test_battery_reports_become_frames(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(2.0, REPORT_74)]]

    steps(reader, 2)

    assert events == [ReceiverOpened(at=0.0), FrameReceived(frame=FRAME_74, at=2.0)]


def test_a_read_timeout_becomes_a_tick(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]

    steps(reader, 2)

    assert events == [ReceiverOpened(at=0.0), Tick(at=1.0)]


def test_other_reports_become_ticks(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(2.0, bytes.fromhex("04") + bytes(63))]]

    steps(reader, 2)

    assert events == [ReceiverOpened(at=0.0), Tick(at=2.0)]


def test_a_read_error_closes_the_handle_and_reports_the_receiver_lost(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(0.5, OSError("read error"))]]

    steps(reader, 2)

    assert events == [ReceiverOpened(at=0.0), ReceiverLost(at=0.5)]
    assert transport.readers[0].closed


def test_reconnects_when_the_receiver_comes_back(
    reader: Reader, transport: FakeTransport, clock: FakeClock, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(0.5, OSError("read error"))]]
    steps(reader, 2)
    transport.collections = []

    reader.step()
    assert events[-1] == ReceiverLost(at=0.5)

    transport.collections = [BATTERY]
    reader.step()
    assert events[-1] == ReceiverOpened(at=clock.now)
    assert len(transport.readers) == 2


def test_an_open_failure_is_retried_later(
    reader: Reader, transport: FakeTransport, clock: FakeClock, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.open_error = OSError("open failed")

    reader.step()
    assert events == []
    assert clock.now == 2.0

    transport.open_error = None
    reader.step()
    assert events == [ReceiverOpened(at=2.0)]


def test_a_long_silence_reopens_the_handle_quietly(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]

    steps(reader, 1 + int(REOPEN_AFTER_SILENCE_S) + 1)

    assert transport.readers[0].closed
    assert len(transport.readers) == 2
    assert not transport.readers[1].closed
    assert events[0] == ReceiverOpened(at=0.0)
    assert all(isinstance(event, Tick) for event in events[1:])


def test_a_long_silence_without_the_receiver_reports_it_lost(
    reader: Reader, transport: FakeTransport, clock: FakeClock, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    steps(reader, 1 + int(REOPEN_AFTER_SILENCE_S))
    transport.collections = []

    reader.step()

    assert events[-1] == ReceiverLost(at=clock.now)
    assert transport.readers[0].closed
    assert len(transport.readers) == 1


def test_a_failed_reopen_reports_the_receiver_lost(
    reader: Reader, transport: FakeTransport, clock: FakeClock, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    steps(reader, 1 + int(REOPEN_AFTER_SILENCE_S))
    transport.open_error = OSError("open failed")

    reader.step()

    assert events[-1] == ReceiverLost(at=clock.now)


def test_regular_reports_keep_the_same_handle(
    reader: Reader, transport: FakeTransport, events: list[Event]
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(2.0, REPORT_74)] * 60]

    steps(reader, 61)

    assert len(transport.readers) == 1
    assert sum(isinstance(event, FrameReceived) for event in events) == 60


def test_run_stops_when_asked_and_closes_the_handle(
    transport: FakeTransport, clock: FakeClock
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(2.0, REPORT_74)]]
    stop = FakeStop(clock)
    events: list[Event] = []

    def emit(event: Event) -> None:
        events.append(event)
        if isinstance(event, FrameReceived):
            stop.set()

    Reader(transport, emit, stop, clock=clock).run()

    assert events == [ReceiverOpened(at=0.0), FrameReceived(frame=FRAME_74, at=2.0)]
    assert transport.readers[0].closed


def test_run_without_a_receiver_stops_cleanly(transport: FakeTransport, clock: FakeClock) -> None:
    stop = FakeStop(clock)
    stop.set()

    Reader(transport, lambda event: None, stop, clock=clock).run()

    assert transport.opened == []


def test_run_logs_a_failing_step_and_keeps_going(
    transport: FakeTransport, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    transport.collections = [BATTERY]
    transport.scripts = [[(2.0, REPORT_74)]]
    stop = FakeStop(clock)
    events: list[Event] = []

    def emit(event: Event) -> None:
        if isinstance(event, ReceiverOpened) and not events:
            events.append(event)
            raise RuntimeError("consumer bug")
        events.append(event)
        stop.set()

    with caplog.at_level(logging.ERROR):
        Reader(transport, emit, stop, clock=clock).run()

    assert "HID reader step failed" in caplog.text
    assert events[-1] == FrameReceived(frame=FRAME_74, at=3.0)
