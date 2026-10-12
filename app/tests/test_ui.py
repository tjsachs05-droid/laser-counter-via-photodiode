import pytest
from conftest import wait_until

from laser_counter.ui import SIMULATOR, MainWindow


@pytest.fixture
def window(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    win = MainWindow(settings, sim_rate_hz=200)
    win.show()
    yield win
    win.close()


def test_starts_disconnected(window):
    assert window.state_pill.property("state") == "disconnected"
    assert not window.start_button.isEnabled()
    assert window.rate_label.text() == "— shots/s"


def test_count_pause_reset_with_simulator(window):
    assert window.connect_device(SIMULATOR)
    wait_until(lambda: window.state_pill.property("state") == "paused")
    assert window.count == 0

    window.toggle_running()
    wait_until(lambda: window.running and window.count >= 40)
    assert window.start_button.text() == "Pause"
    rate = float(window.rate_label.text().split()[0])
    assert 150 < rate < 250

    window.toggle_running()
    wait_until(lambda: not window.running)
    paused_at = window.count
    wait_until(window.banner.isVisible)  # pulses keep arriving while paused
    assert window.count == paused_at

    window.reset_count()
    wait_until(lambda: window.count == 0)


def test_threshold_change_reaches_the_box(window):
    window.connect_device(SIMULATOR)
    window.threshold_spin.setValue(-700)
    wait_until(lambda: window.device.transport.firmware.thr_mv == -700)
    assert window.settings.value("threshold_mv", type=int) == -700


def test_disconnect(window):
    window.connect_device(SIMULATOR)
    wait_until(lambda: window.state_pill.property("state") == "paused")
    window.disconnect_device()
    assert window.state_pill.property("state") == "disconnected"
    assert window.connect_button.text() == "Connect"
