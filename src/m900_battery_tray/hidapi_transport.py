"""HidTransport implementation on top of the `hidapi` package. Read-only by design."""

import hid

from m900_battery_tray.hid_transport import HidCollection, collection_from_entry


class HidapiReader:
    def __init__(self, device: hid.device) -> None:
        self._device = device

    def read(self, size: int, timeout_ms: int) -> bytes:
        return bytes(self._device.read(size, timeout_ms))

    def close(self) -> None:
        self._device.close()


class HidapiTransport:
    def enumerate(self, vendor_id: int, product_id: int) -> list[HidCollection]:
        return [collection_from_entry(entry) for entry in hid.enumerate(vendor_id, product_id)]

    def open(self, path: bytes) -> HidapiReader:
        device = hid.device()
        device.open_path(path)
        return HidapiReader(device)
