"""Thin Win32 helpers: DPI awareness, tray icon size, taskbar theme, single instance."""

import ctypes
import winreg
from ctypes import wintypes

from m900_battery_tray.icon import TaskbarTheme

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
SM_CXSMICON = 49
SPI_GETCLIENTAREAANIMATION = 0x1042
ERROR_ALREADY_EXISTS = 183

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
_user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
_user32.GetDpiForWindow.argtypes = [wintypes.HWND]
_user32.GetDpiForWindow.restype = wintypes.UINT
_user32.GetDpiForSystem.argtypes = []
_user32.GetDpiForSystem.restype = wintypes.UINT
_user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
_user32.GetSystemMetricsForDpi.restype = ctypes.c_int
_user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
_user32.SetTimer.restype = ctypes.c_size_t
_user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
_user32.KillTimer.restype = wintypes.BOOL
_user32.SystemParametersInfoW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    wintypes.UINT,
]
_user32.SystemParametersInfoW.restype = wintypes.BOOL
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE


def enable_dpi_awareness() -> None:
    """Render for the real DPI instead of letting Windows stretch a 96-DPI bitmap.

    Must run before any window is created. Fails harmlessly if a manifest already set it.
    """
    _user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)


def small_icon_size(hwnd: int | None) -> int:
    """The notification-area icon size, in pixels, for the DPI of the given window."""
    dpi = _user32.GetDpiForWindow(hwnd) if hwnd else 0
    return _user32.GetSystemMetricsForDpi(SM_CXSMICON, dpi or _user32.GetDpiForSystem())


def animations_enabled() -> bool:
    """Windows' 'Animation effects' setting (Settings > Accessibility > Visual effects)."""
    enabled = wintypes.BOOL(True)
    _user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0)
    return bool(enabled.value)


def set_timer(hwnd: int, timer_id: int, interval_ms: int) -> None:
    """Post WM_TIMER to the window every `interval_ms`. Call from the window's thread."""
    _user32.SetTimer(hwnd, timer_id, interval_ms, None)


def kill_timer(hwnd: int, timer_id: int) -> None:
    _user32.KillTimer(hwnd, timer_id)


def read_taskbar_theme() -> TaskbarTheme:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
    except OSError:
        value = None
    return TaskbarTheme.from_system_uses_light_theme(value)


class SingleInstance:
    """A named mutex held for the life of the process."""

    def __init__(self, name: str) -> None:
        self._handle = _kernel32.CreateMutexW(None, False, name)
        self.acquired = bool(self._handle) and ctypes.get_last_error() != ERROR_ALREADY_EXISTS
