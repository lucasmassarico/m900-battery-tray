"""The tray app: wires the reader thread, the presenter and the tray icon together."""

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pystray import Icon, Menu, MenuItem

from m900_battery_tray.autostart import RegistryAutostart, launch_command
from m900_battery_tray.config import Config, ConfigError, default_config_path, load_or_create
from m900_battery_tray.hidapi_transport import HidapiTransport
from m900_battery_tray.presenter import Presenter
from m900_battery_tray.reader import Reader
from m900_battery_tray.texts import MODEL_NAME, Notification
from m900_battery_tray.tray import TrayDisplay, TrayIcon
from m900_battery_tray.windows import SingleInstance, enable_dpi_awareness, read_taskbar_theme

log = logging.getLogger(__name__)

APP_NAME = "m900-battery-tray"
MUTEX_NAME = rf"Local\{APP_NAME}"
LOG_FILE_NAME = "app.log"
READER_JOIN_TIMEOUT_S = 3.0


def main() -> int:
    enable_dpi_awareness()
    config_path = default_config_path()
    _setup_logging(config_path.parent / LOG_FILE_NAME)
    try:
        return _run(config_path)
    except Exception:
        log.exception("the app crashed")
        raise


def _run(config_path: Path) -> int:
    instance = SingleInstance(MUTEX_NAME)
    if not instance.acquired:
        log.info("another instance is already running")
        return 0

    config, config_problem = _load_config(config_path)
    autostart = RegistryAutostart()
    command = launch_command(sys.executable, frozen=getattr(sys, "frozen", False))
    try:
        autostart.keep_current(command)
    except OSError:
        log.exception("cannot update the autostart command")

    stop = threading.Event()

    def toggle_autostart(icon: Icon, item: MenuItem) -> None:
        try:
            if autostart.is_enabled():
                autostart.disable()
            else:
                autostart.enable(command)
        except OSError:
            log.exception("cannot change the autostart setting")
            icon.notify("Couldn't change the startup setting.", MODEL_NAME)

    def exit_app(icon: Icon, item: MenuItem) -> None:
        stop.set()
        icon.stop()

    menu = Menu(
        MenuItem(lambda item: display.status, None, enabled=False),
        Menu.SEPARATOR,
        MenuItem(
            "Start with Windows", toggle_autostart, checked=lambda item: autostart.is_enabled()
        ),
        MenuItem("Exit", exit_app),
    )
    icon = TrayIcon(APP_NAME, title=MODEL_NAME, menu=menu)
    display = TrayDisplay(icon, read_taskbar_theme)
    presenter = Presenter(config, display)
    reader = Reader(HidapiTransport(), presenter.handle, stop)
    reader_thread = threading.Thread(target=reader.run, name="hid-reader", daemon=True)

    def setup(icon: Icon) -> None:
        presenter.start()
        if config_problem is not None:
            display.notify(config_problem)
        reader_thread.start()

    log.info("starting")
    icon.run(setup)
    stop.set()
    reader_thread.join(timeout=READER_JOIN_TIMEOUT_S)
    log.info("stopped")
    return 0


def _load_config(path: Path) -> tuple[Config, Notification | None]:
    try:
        return load_or_create(path), None
    except ConfigError as error:
        log.error("%s; using the default settings", error)
        problem = Notification(
            title="M900 tray settings", message=f"{error}. Using the default settings."
        )
        return Config(), problem


def _setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
