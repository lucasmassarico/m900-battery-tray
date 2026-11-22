"""Background HID reader: turns the receiver's battery reports into state-machine events.

It only reads. It runs in its own thread, separate from the tray's, and wakes up at least
once per read timeout so the tray can notice sleep and stop requests.
"""

import logging
import time
from collections.abc import Callable
from typing import Protocol

from m900_battery_tray.frame import parse_frame
from m900_battery_tray.hid_transport import (
    RECEIVER_PRODUCT_ID,
    RECEIVER_VENDOR_ID,
    HidReader,
    HidTransport,
    find_battery_collection,
)
from m900_battery_tray.state import Event, FrameReceived, ReceiverLost, ReceiverOpened, Tick

log = logging.getLogger(__name__)

READ_SIZE = 64
READ_TIMEOUT_MS = 1000
RESCAN_INTERVAL_S = 2.0
ERROR_BACKOFF_S = 1.0
# A sleeping mouse is silent, but so is a handle that went stale without an error (never seen
# so far, but hibernation is untested). After this much silence the handle is reopened.
REOPEN_AFTER_SILENCE_S = 60.0


class StopSignal(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float) -> bool: ...


class Reader:
    def __init__(
        self,
        transport: HidTransport,
        emit: Callable[[Event], None],
        stop: StopSignal,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._emit = emit
        self._stop = stop
        self._clock = clock
        self._reader: HidReader | None = None
        self._quiet_since = 0.0

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    self.step()
                except Exception:
                    log.exception("HID reader step failed")
                    self._stop.wait(ERROR_BACKOFF_S)
        finally:
            self._close()

    def step(self) -> None:
        if self._reader is None:
            self._open()
        elif self._clock() - self._quiet_since >= REOPEN_AFTER_SILENCE_S:
            self._reopen()
        else:
            self._read()

    def _open(self) -> None:
        self._reader = self._open_battery_collection()
        if self._reader is None:
            self._stop.wait(RESCAN_INTERVAL_S)
            return
        self._quiet_since = self._clock()
        log.info("receiver opened")
        self._emit(ReceiverOpened(at=self._quiet_since))

    def _reopen(self) -> None:
        """Swap the handle without telling the state machine, so a sleeping mouse stays asleep.
        Only a receiver that is really gone is reported."""
        self._close()
        self._reader = self._open_battery_collection()
        if self._reader is None:
            log.info("receiver lost while the mouse was silent")
            self._emit(ReceiverLost(at=self._clock()))
            return
        self._quiet_since = self._clock()

    def _read(self) -> None:
        assert self._reader is not None
        try:
            data = self._reader.read(READ_SIZE, READ_TIMEOUT_MS)
        except OSError as error:
            log.info("receiver lost: %s", error)
            self._close()
            self._emit(ReceiverLost(at=self._clock()))
            return

        now = self._clock()
        frame = parse_frame(data) if data else None
        if frame is None:
            if data:
                log.debug("ignored report %s", data.hex(" "))
            self._emit(Tick(at=now))
            return
        self._quiet_since = now
        self._emit(FrameReceived(frame=frame, at=now))

    def _open_battery_collection(self) -> HidReader | None:
        collections = self._transport.enumerate(RECEIVER_VENDOR_ID, RECEIVER_PRODUCT_ID)
        battery = find_battery_collection(collections)
        if battery is None:
            return None
        try:
            return self._transport.open(battery.path)
        except OSError as error:
            log.warning("cannot open the battery collection: %s", error)
            return None

    def _close(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None
