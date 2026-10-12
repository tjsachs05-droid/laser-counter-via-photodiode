import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeClock:
    """Stand-in for the firmware's µs clock, advanced by hand."""

    def __init__(self):
        self.us = 0

    def __call__(self) -> int:
        return self.us

    def advance(self, seconds: float) -> None:
        self.us += round(seconds * 1e6)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def wait_until(condition, timeout: float = 3.0) -> None:
    """Run the Qt event loop until `condition()` is true, or fail after `timeout` seconds."""
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for condition")
        QApplication.processEvents()
        time.sleep(0.01)
