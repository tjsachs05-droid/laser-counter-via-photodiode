import pytest
from conftest import wait_until

from laser_counter import ui
from laser_counter.device import SimTransport
from laser_counter.simulator import SimulatedFirmware
from laser_counter.ui import SIMULATOR, MainWindow


class FakeBox:
    """A pretend counter box on a serial port, 10 shots/s on a hand-driven clock. It stays powered between
    connections, so it keeps counting while the app is closed, until `power_cycle()`."""

    def __init__(self, clock):
        self.clock = clock
        self.power_cycle()

    def power_cycle(self) -> None:
        self.firmware = SimulatedFirmware(rep_rate_hz=10, pulse_sd_mv=0, weak_shot_fraction=0, clock_us=self.clock)

    def transport(self, port: str) -> SimTransport:
        transport = SimTransport(self.firmware)
        transport.label = port
        return transport


@pytest.fixture
def settings(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)


@pytest.fixture
def box(monkeypatch, clock):
    fake = FakeBox(clock)
    monkeypatch.setattr(ui, "SerialTransport", fake.transport)
    return fake


@pytest.fixture
def make_window(qapp, settings):
    windows = []

    def make():
        win = MainWindow(settings, sim_rate_hz=200)
        win.show()
        windows.append(win)
        return win

    yield make
    for win in windows:
        win.close()


@pytest.fixture
def window(make_window):
    return make_window()


def counts(window) -> list[int]:
    return [lap.count for lap in window.laps]


def test_starts_disconnected(window):
    assert window.state_pill.isVisible()
    assert [lap.name for lap in window.laps] == ["Lap1"]
    row = window.lap_list.rows[0]
    assert not row.toggle_button.isEnabled() and not row.reset_button.isEnabled()
    assert not row.delete_button.isEnabled()  # the only lap
    assert not window.new_lap_button.isEnabled()
    assert window.rate_label.text() == "— shots/s"
    assert window.threshold_spin.value() == -1000


def test_laps_count_side_by_side(window, box):
    assert window.connect_device("COM9")
    assert not window.state_pill.isVisible()
    lap1 = window.laps[0]
    box.clock.advance(1.0)
    wait_until(lambda: lap1.count == 10)

    lap2 = window.new_lap()
    assert (lap2.name, lap2.count, lap2.running) == ("Lap2", 0, True)
    box.clock.advance(0.5)
    wait_until(lambda: counts(window) == [15, 5])

    window.toggle_lap(lap1)
    assert window.lap_list.rows[0].toggle_button.text() == "Start"
    box.clock.advance(0.3)
    wait_until(lambda: counts(window) == [15, 8])

    window.reset_lap(lap2)
    box.clock.advance(0.2)
    wait_until(lambda: counts(window) == [15, 2])
    assert window.lap_list.rows[1].count_label.text() == "2"


def test_lap_limits(window, box):
    window.connect_device("COM9")
    for _ in range(8):
        window.new_lap()
    assert [lap.name for lap in window.laps] == [f"Lap{n}" for n in range(1, 10)]
    assert window.new_lap() is None
    assert not window.new_lap_button.isEnabled()
    assert window.lap_total.text() == "9 of 9 laps"
    for lap in list(window.laps)[1:]:
        assert window.delete_lap(lap)
    assert not window.delete_lap(window.laps[0])
    assert not window.lap_list.rows[0].delete_button.isEnabled()
    assert window.new_lap_button.isEnabled()


def test_rename_from_the_row(window):
    edit = window.lap_list.rows[0].name_edit
    edit.setText("  Sample   A ")
    edit.editingFinished.emit()
    assert window.laps[0].name == "Sample A"
    assert edit.text() == "Sample A"
    edit.setText("   ")
    edit.editingFinished.emit()
    assert window.laps[0].name == "Sample A"


def test_escape_undoes_a_rename(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    edit = window.lap_list.rows[0].name_edit
    edit.setFocus()
    edit.setText("Oops")
    QTest.keyClick(edit, Qt.Key_Escape)
    assert edit.text() == "Lap1"
    assert window.laps[0].name == "Lap1"


def test_reset_and_delete_ask_first_only_when_shots_would_be_lost(window, box, monkeypatch):
    window.connect_device("COM9")
    box.clock.advance(1.0)
    wait_until(lambda: counts(window) == [10])
    empty = window.new_lap()
    asked = []
    monkeypatch.setattr(window, "_confirm", lambda title, text, action: asked.append(action) and False)

    window._confirm_reset_lap(window.laps[0])  # declined
    window._confirm_delete_lap(empty)  # nothing to lose, so no question
    assert asked == ["Reset"]
    assert counts(window) == [10]

    monkeypatch.setattr(window, "_confirm", lambda title, text, action: True)
    window._confirm_reset_lap(window.laps[0])
    assert counts(window) == [0]


def test_laps_survive_closing_and_catch_up(make_window, box):
    first = make_window()
    first.connect_device("COM9")
    box.clock.advance(1.0)
    wait_until(lambda: counts(first) == [10])
    sample = first.new_lap()
    first.rename_lap(sample, "Sample B")
    first.toggle_lap(first.laps[0])
    first.close()

    box.clock.advance(2.0)  # 20 shots while the app is closed

    second = make_window()
    assert [(lap.name, lap.count, lap.running) for lap in second.laps] == [("Lap1", 10, False), ("Sample B", 0, True)]
    second.connect_device("COM9")
    wait_until(lambda: counts(second) == [10, 20])


def test_no_catch_up_after_the_box_restarts(make_window, box):
    first = make_window()
    first.connect_device("COM9")
    box.clock.advance(1.0)
    wait_until(lambda: counts(first) == [10])
    first.close()

    box.clock.advance(1.0)
    box.power_cycle()  # unplugged: its total is back to 0, and it starts up paused

    second = make_window()
    second.connect_device("COM9")
    box.clock.advance(1.0)
    wait_until(lambda: counts(second) == [20])
    assert box.firmware.running


def test_simulator_laps_are_just_for_practice(window, box):
    window.connect_device("COM9")
    box.clock.advance(1.0)
    wait_until(lambda: counts(window) == [10])
    window.rename_lap(window.laps[0], "Real")

    window.connect_device(SIMULATOR)
    assert [(lap.name, lap.count) for lap in window.laps] == [("Lap1", 0)]
    wait_until(lambda: window.laps[0].count >= 40)
    rate = float(window.rate_label.text().split()[0])
    assert 150 < rate < 250

    window.disconnect_device()
    assert [(lap.name, lap.count) for lap in window.laps] == [("Real", 10)]


def test_banner_when_every_lap_is_paused(window):
    window.connect_device(SIMULATOR)
    wait_until(lambda: window.laps[0].count >= 5)
    window.toggle_lap(window.laps[0])
    paused_at = window.laps[0].count
    wait_until(window.banner.isVisible)
    assert window.laps[0].count == paused_at


def test_threshold_change_reaches_the_box(window):
    window.connect_device(SIMULATOR)
    window.threshold_spin.setValue(-700)
    wait_until(lambda: window.device.transport.firmware.thr_mv == -700)
    assert window.settings.value("threshold_mv", type=int) == -700


def test_disconnect(window):
    window.connect_device(SIMULATOR)
    window.disconnect_device()
    assert window.state_pill.isVisible()
    assert window.connect_button.text() == "Connect"
    assert not window.lap_list.rows[0].toggle_button.isEnabled()
