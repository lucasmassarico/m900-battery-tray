"""Command-line entry point."""

import argparse
import sys
from pathlib import Path


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m900-battery-tray",
        description="Tray app that shows the battery level of the Delux M900 Pro mouse.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="list the receiver's HID collections and print raw battery frames",
    )
    parser.add_argument(
        "--seconds",
        type=_positive_seconds,
        help="stop the probe after this many seconds (default: run until Ctrl+C)",
    )
    parser.add_argument("--out", type=Path, help="also append the probe output to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.probe:
        if args.seconds is not None or args.out is not None:
            parser.error("--seconds and --out require --probe")
        parser.error("the tray app is not implemented yet; use --probe")

    from m900_battery_tray import probe

    return probe.main(args.seconds, args.out)


if __name__ == "__main__":
    sys.exit(main())
