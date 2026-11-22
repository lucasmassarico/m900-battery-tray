"""--probe: list the receiver's HID collections and print raw battery frames with timestamps.

Read-only: it opens only the battery collection (usage page 0x000A) and never writes to it.
It also re-enumerates every few seconds and logs when the receiver (FA65) or the wired-mode
device (FA60) appears or disappears, to answer the open questions in docs/research.md.
"""

import contextlib
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from m900_battery_tray.capture import (
    format_collection_line,
    format_event_line,
    format_frame_line,
)
from m900_battery_tray.hid_transport import (
    RECEIVER_PRODUCT_ID,
    RECEIVER_VENDOR_ID,
    WIRED_PRODUCT_ID,
    HidCollection,
    HidReader,
    HidTransport,
    find_battery_collection,
)

READ_SIZE = 64
READ_TIMEOUT_MS = 1000
RESCAN_INTERVAL_S = 2.0

WATCHED_PRODUCTS = {
    RECEIVER_PRODUCT_ID: "receiver FA65",
    WIRED_PRODUCT_ID: "wired device FA60",
}


def run_probe(
    transport: HidTransport, out: Callable[[str], None], duration_s: float | None
) -> None:
    start = time.monotonic()

    def elapsed() -> float:
        return time.monotonic() - start

    def event(message: str) -> None:
        out(format_event_line(datetime.now(), elapsed(), message))

    def scan() -> list[HidCollection]:
        found: list[HidCollection] = []
        for product_id in WATCHED_PRODUCTS:
            found.extend(transport.enumerate(RECEIVER_VENDOR_ID, product_id))
        return found

    collections = scan()
    event(f"{len(collections)} collection(s) found")
    for collection in collections:
        out(format_collection_line(collection))

    present = {pid: _is_present(collections, pid) for pid in WATCHED_PRODUCTS}
    for pid, name in WATCHED_PRODUCTS.items():
        event(f"{name} {'present' if present[pid] else 'absent'}")

    reader: HidReader | None = None
    last_frame_at: float | None = None
    next_scan_at = elapsed() + RESCAN_INTERVAL_S
    try:
        while duration_s is None or elapsed() < duration_s:
            if elapsed() >= next_scan_at:
                collections = scan()
                for pid, name in WATCHED_PRODUCTS.items():
                    now_present = _is_present(collections, pid)
                    if now_present != present[pid]:
                        present[pid] = now_present
                        event(f"{name} {'appeared' if now_present else 'disappeared'}")
                next_scan_at = elapsed() + RESCAN_INTERVAL_S

            if reader is None:
                reader = _try_open(transport, collections, event)
                if reader is None:
                    time.sleep(max(0.0, next_scan_at - elapsed()))
                    continue

            try:
                data = reader.read(READ_SIZE, READ_TIMEOUT_MS)
            except OSError as error:
                event(f"read error: {error}")
                reader.close()
                reader = None
                continue

            if data:
                frame_at = elapsed()
                delta = frame_at - last_frame_at if last_frame_at is not None else None
                last_frame_at = frame_at
                out(format_frame_line(datetime.now(), frame_at, delta, data))
    except KeyboardInterrupt:
        event("stopped by user")
    finally:
        if reader is not None:
            reader.close()
    event("probe finished")


def _is_present(collections: list[HidCollection], product_id: int) -> bool:
    return any(collection.product_id == product_id for collection in collections)


def _try_open(
    transport: HidTransport, collections: list[HidCollection], event: Callable[[str], None]
) -> HidReader | None:
    battery = find_battery_collection(collections)
    if battery is None:
        return None
    try:
        reader = transport.open(battery.path)
    except OSError as error:
        event(f"open failed: {error}")
        return None
    event(f"opened battery collection {battery.path.decode(errors='replace')}")
    return reader


def main(duration_s: float | None, out_path: Path | None) -> int:
    from m900_battery_tray.hidapi_transport import HidapiTransport

    with contextlib.ExitStack() as stack:
        capture_file = None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            capture_file = stack.enter_context(out_path.open("a", encoding="utf-8"))

        def out(line: str) -> None:
            print(line, flush=True)
            if capture_file is not None:
                capture_file.write(line + "\n")
                capture_file.flush()

        run_probe(HidapiTransport(), out, duration_s)
    return 0
