"""Start the app: `python -m laser_counter` (or `laser-counter` once installed)."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .ui import DISPLAY_FONTS, SIMULATOR, MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="laser-counter", description="Live laser ablation shot counter.")
    parser.add_argument("--simulate", action="store_true", help="connect to the built-in pretend laser")
    parser.add_argument("--sim-rate", type=float, default=5.0, metavar="HZ", help="simulated rep rate (default 5)")
    parser.add_argument("--port", help="serial port of the counter box, e.g. COM5")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setOrganizationName("laser-counter")
    app.setApplicationName("Laser Shot Counter")
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(DISPLAY_FONTS)
    font.setPointSizeF(10.5)
    app.setFont(font)

    window = MainWindow(sim_rate_hz=args.sim_rate)
    window.show()
    if args.simulate:
        window.connect_device(SIMULATOR)
    elif args.port:
        window.connect_device(args.port)
    else:
        window.auto_connect()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
