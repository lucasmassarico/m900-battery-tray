"""The notification-area icon, on top of pystray's Win32 backend.

pystray needs two changes here, both through its Win32 internals (pinned to pystray 0.19.x
and checked by tests/test_tray_contract.py):

- crisp icon: pystray saves the image as a multi-size .ico and loads it at the large-icon
  size, so Windows scales it down and the pixel font blurs. Here the icon is drawn and loaded
  at exactly the small-icon size;
- one UI thread: the reader thread only queues work, and the icon's own message loop runs
  it, so Shell_NotifyIcon and menu calls never race.
"""

import ctypes
import logging
import os
import queue
import tempfile
from collections.abc import Callable

from pystray import Menu
from pystray._util import win32
from pystray._win32 import Icon as Win32Icon

from m900_battery_tray.icon import TaskbarTheme, render_icon
from m900_battery_tray.presenter import TrayView
from m900_battery_tray.texts import Notification
from m900_battery_tray.windows import small_icon_size

log = logging.getLogger(__name__)

WM_SETTINGCHANGE = 0x001A
WM_RUN_QUEUED = 0x8000 + 1  # WM_APP + 1
THEME_SETTING = "ImmersiveColorSet"


class TrayIcon(Win32Icon):
    def __init__(self, name: str, title: str, menu: Menu) -> None:
        super().__init__(name, title=title, menu=menu)
        self.on_theme_change: Callable[[], None] = lambda: None
        self._queued: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._message_handlers[WM_RUN_QUEUED] = self._run_queued
        self._message_handlers[WM_SETTINGCHANGE] = self._on_setting_change

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    def call_soon(self, action: Callable[[], None]) -> None:
        """Run `action` on the icon's thread. Safe to call from any thread once it runs."""
        self._queued.put(action)
        win32.PostMessage(self._hwnd, WM_RUN_QUEUED, 0, 0)

    def _run_queued(self, wparam: int, lparam: int) -> None:
        while True:
            try:
                action = self._queued.get_nowait()
            except queue.Empty:
                return
            try:
                action()
            except Exception:
                log.exception("tray update failed")

    def _on_setting_change(self, wparam: int, lparam: int) -> None:
        if lparam and ctypes.wstring_at(lparam) == THEME_SETTING:
            self.on_theme_change()

    def _assert_icon_handle(self) -> None:
        if self._icon_handle:
            return
        size = self.icon.width
        descriptor, path = tempfile.mkstemp(suffix=".ico")
        os.close(descriptor)
        try:
            self.icon.save(path, format="ICO", sizes=[(size, size)], bitmap_format="bmp")
            self._icon_handle = win32.LoadImage(
                None, path, win32.IMAGE_ICON, size, size, win32.LR_LOADFROMFILE
            )
        finally:
            os.remove(path)


class TrayDisplay:
    """The presenter's Display: draws views and shows notifications on the tray icon."""

    def __init__(self, icon: TrayIcon, read_theme: Callable[[], TaskbarTheme]) -> None:
        self._icon = icon
        self._read_theme = read_theme
        self._view: TrayView | None = None
        icon.on_theme_change = self._redraw

    @property
    def status(self) -> str:
        return self._view.status if self._view is not None else "Starting..."

    def show(self, view: TrayView) -> None:
        self._icon.call_soon(lambda: self._apply(view))

    def notify(self, notification: Notification) -> None:
        self._icon.call_soon(lambda: self._icon.notify(notification.message, notification.title))

    def _apply(self, view: TrayView) -> None:
        self._view = view
        self._redraw()

    def _redraw(self) -> None:
        view = self._view
        if view is None:
            return
        self._icon.icon = render_icon(
            view.snapshot,
            small_icon_size(self._icon.hwnd),
            self._read_theme(),
            low_percent=view.low_percent,
            critical_percent=view.critical_percent,
        )
        self._icon.title = view.tooltip
        self._icon.update_menu()
        if not self._icon.visible:
            self._icon.visible = True
