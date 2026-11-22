"""tray.py relies on pystray's Win32 internals. These fail loudly if an upgrade moves them."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="pystray Win32 backend")


def test_pystray_win32_internals_used_by_the_tray() -> None:
    from pystray._util import win32
    from pystray._win32 import Icon

    icon = Icon("m900-battery-tray-contract-test")

    assert isinstance(icon._message_handlers, dict)
    assert icon._icon_handle is None
    assert callable(Icon._assert_icon_handle)
    assert callable(Icon._release_icon)
    for name in ("LoadImage", "DestroyIcon", "PostMessage", "IMAGE_ICON", "LR_LOADFROMFILE"):
        assert hasattr(win32, name), name
