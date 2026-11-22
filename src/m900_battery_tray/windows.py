"""Thin Win32 helpers: DPI awareness, tray icon size, taskbar theme, menu theme, single
instance, opening a file for editing, and borrowing the console of the terminal that started
the app."""

import ctypes
import os
import subprocess
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

from m900_battery_tray.icon import TaskbarTheme

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
SM_CXSMICON = 49
SPI_GETCLIENTAREAANIMATION = 0x1042
ERROR_ALREADY_EXISTS = 183
ATTACH_PARENT_PROCESS = wintypes.DWORD(-1).value
# uxtheme's PreferredAppMode values: ForceDark and ForceLight.
MENU_APP_MODES = {TaskbarTheme.DARK: 2, TaskbarTheme.LIGHT: 3}

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
_kernel32.AttachConsole.argtypes = [wintypes.DWORD]
_kernel32.AttachConsole.restype = wintypes.BOOL

# Exported by ordinal only (Windows 10 1903+): there is no documented way to theme Win32 menus.
_uxtheme = ctypes.WinDLL("uxtheme")
_set_preferred_app_mode = _uxtheme[135]
_set_preferred_app_mode.argtypes = [ctypes.c_int]
_set_preferred_app_mode.restype = ctypes.c_int
_flush_menu_themes = _uxtheme[136]
_flush_menu_themes.argtypes = []
_flush_menu_themes.restype = None


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


def apply_menu_theme(theme: TaskbarTheme) -> None:
    """Draw this process's menus dark or light, to match the taskbar.

    Left alone, Win32 menus are always light, and on some systems the light menu doesn't show
    the hover highlight until something repaints it. Menus created afterwards use the theme.
    """
    _set_preferred_app_mode(MENU_APP_MODES[theme])
    _flush_menu_themes()


def attach_parent_console() -> None:
    """Send print() and errors to the terminal that started this windowed exe, if there is one.

    The packaged exe has no console of its own, so without this `--probe` and `--help` print
    nothing. Started from Explorer or at sign-in there is no terminal and nothing changes.
    """
    if not _kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        return
    sys.stdout = open("CONOUT$", "w", buffering=1)  # noqa: SIM115 - lives as long as the process
    sys.stderr = sys.stdout


def open_in_editor(path: Path) -> None:
    """Open a file with the user's default app for its type, or Notepad if there is none.

    Raises OSError if neither can be started.
    """
    try:
        os.startfile(path)
    except OSError:
        subprocess.Popen(["notepad.exe", str(path)])


class SingleInstance:
    """A named mutex held for the life of the process."""

    def __init__(self, name: str) -> None:
        self._handle = _kernel32.CreateMutexW(None, False, name)
        self.acquired = bool(self._handle) and ctypes.get_last_error() != ERROR_ALREADY_EXISTS
