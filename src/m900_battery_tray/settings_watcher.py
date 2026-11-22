"""Applies the settings file again each time it is saved, so edits need no restart.

Polls the file's modification time and size. A change is loaded only once it has held for one
poll, so an editor caught halfway through a save isn't read as a broken file.
"""

import logging
import os
from collections.abc import Callable
from pathlib import Path

from m900_battery_tray.config import Config, ConfigError, load_or_create
from m900_battery_tray.reader import StopSignal

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 1.0

FileStamp = tuple[int, int]


class SettingsWatcher:
    def __init__(
        self,
        path: Path,
        apply: Callable[[Config], None],
        reject: Callable[[ConfigError], None],
    ) -> None:
        """Start from the file as it is now, which the app has already loaded."""
        self._path = path
        self._apply = apply
        self._reject = reject
        self._loaded = self._stamp()
        self._last_seen = self._loaded

    def check(self) -> None:
        stamp = self._stamp()
        settled = stamp == self._last_seen
        self._last_seen = stamp
        if stamp is None or stamp == self._loaded or not settled:
            return
        self._loaded = stamp
        try:
            config = load_or_create(self._path)
        except ConfigError as error:
            log.error("%s; keeping the previous settings", error)
            self._reject(error)
            return
        log.info("settings applied: %s", config)
        self._apply(config)

    def run(self, stop: StopSignal) -> None:
        while not stop.wait(POLL_INTERVAL_S):
            try:
                self.check()
            except Exception:
                log.exception("cannot apply the settings file")

    def _stamp(self) -> FileStamp | None:
        try:
            status = os.stat(self._path)
        except OSError:
            return None
        return status.st_mtime_ns, status.st_size
