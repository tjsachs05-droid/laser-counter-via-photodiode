"""Main window: laps of shot counts, shots per second, and the trigger threshold.

Each lap is its own count with Start/Pause, Reset and Delete (see laps.py). The box counts all the time;
the laps decide which shots they keep.
"""

from __future__ import annotations

import json
import queue
import time

from PySide6 import QtSvg  # noqa: F401  Qt's SVG image plugin (arrow icons) only loads once this is imported
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import protocol as p
from .device import Device, Disconnected, SerialTransport, SimTransport, Unparsed, list_serial_ports
from .laps import MAX_LAPS, MAX_NAME_LENGTH, Lap, Laps, ShotTally
from .rate import RateMeter
from .simulator import SimulatedFirmware
from .theme import stylesheet

SIMULATOR = "Simulator"
POLL_MS = 30
SAVE_MS = 1000
TRIGGER_FLASH_MS = 120
PAUSED_PULSE_WARNING_S = 3.0
DEFAULT_THRESHOLD_MV = -400
DEFAULT_HOLDOFF_MS = 1.0
DISPLAY_FONTS = ["Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", "Arial"]

LAP_STATE_TEXT = {"running": "●  RUNNING", "paused": "●  PAUSED"}


def display_font(weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(DISPLAY_FONTS)
    font.setWeight(weight)
    try:  # tabular figures, so digits don't shift sideways as the count changes (Qt 6.7+)
        font.setFeature(QFont.Tag("tnum"), 1)
    except (AttributeError, TypeError):
        pass
    return font


def _minus(text: str) -> str:
    return text.replace("-", "−")


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PortCombo(QComboBox):
    """Combo box that rescans serial ports every time it opens."""

    aboutToShowPopup = Signal()

    def showPopup(self) -> None:
        self.aboutToShowPopup.emit()
        super().showPopup()


class NameEdit(QLineEdit):
    """A lap's name. Looks like a label until clicked; Enter keeps the edit, Escape undoes it."""

    cancelled = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


class LapRow(QFrame):
    """One lap: its name, state and count, with its own Start/Pause, Reset and Delete buttons."""

    toggle_clicked = Signal(object)
    reset_clicked = Signal(object)
    delete_clicked = Signal(object)
    renamed = Signal(object, str)

    def __init__(self, lap: Lap):
        super().__init__(objectName="lapRow")
        self.lap = lap
        self._count_px_max = 40
        self.name_edit = NameEdit(lap.name, objectName="lapName", maxLength=MAX_NAME_LENGTH, toolTip="Click to rename")
        self.name_edit.editingFinished.connect(self._finish_rename)
        self.name_edit.cancelled.connect(self._cancel_rename)
        self.state_label = QLabel(objectName="lapState")
        self.count_label = QLabel(objectName="lapCount", alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.count_label.setFont(display_font(QFont.Weight.Medium))
        self.toggle_button = QPushButton(objectName="lapToggle", toolTip="Start or pause this lap")
        self.reset_button = QPushButton("Reset…", objectName="lapButton", toolTip="Set this lap to 0")
        self.delete_button = QToolButton(text="✕", objectName="lapDelete")
        self.toggle_button.clicked.connect(lambda: self.toggle_clicked.emit(self.lap))
        self.reset_button.clicked.connect(lambda: self.reset_clicked.emit(self.lap))
        self.delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.lap))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 10, 4)
        layout.setSpacing(10)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.state_label, 0, Qt.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self.count_label)
        layout.addSpacing(16)
        for button in (self.toggle_button, self.reset_button, self.delete_button):
            button.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(button)

    def refresh(self, connected: bool, can_delete: bool) -> None:
        lap = self.lap
        text = f"{lap.count:,}"
        if self.count_label.text() != text:
            self.count_label.setText(text)
            self._fit_count()
        state = "running" if lap.running else "paused"
        if self.state_label.property("state") != state:
            self.state_label.setText(LAP_STATE_TEXT[state])
            self.toggle_button.setText("Pause" if lap.running else "Start")
            self.toggle_button.setProperty("kind", "pause" if lap.running else "start")
            for widget in (self.state_label, self.count_label):
                widget.setProperty("state", state)
            for widget in (self.state_label, self.count_label, self.toggle_button):
                _repolish(widget)
            self._fit_count()
        if not self.name_edit.hasFocus():
            if self.name_edit.text() != lap.name:
                self.name_edit.setText(lap.name)
            self.name_edit.setCursorPosition(0)  # show a long name from its start
        self.toggle_button.setEnabled(connected)
        self.reset_button.setEnabled(connected)
        self.delete_button.setEnabled(can_delete)
        self.delete_button.setToolTip("Delete this lap" if can_delete else "There must be at least one lap")

    def set_height(self, height: int) -> None:
        self.setFixedHeight(height)
        name_font = self.name_edit.font()
        name_font.setPixelSize(max(14, min(22, int(height * 0.2))))
        name_font.setWeight(QFont.Weight.DemiBold)
        self.name_edit.setFont(name_font)
        self.name_edit.setFixedWidth(name_font.pixelSize() * 12)
        self._count_px_max = max(20, min(96, int(height * 0.48)))
        self._fit_count()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_count()

    def _fit_count(self) -> None:
        """The count as large as the row's height allows, but never wider than the room left for it."""
        layout = self.layout()
        margins = layout.contentsMargins()
        others = self.name_edit.width() + sum(
            widget.sizeHint().width()
            for widget in (self.state_label, self.toggle_button, self.reset_button, self.delete_button)
        )
        room = self.width() - margins.left() - margins.right() - others - 6 * layout.spacing() - 40
        font = self.count_label.font()
        font.setPixelSize(100)
        width_at_100 = max(1, QFontMetrics(font).horizontalAdvance(self.count_label.text() or "0"))
        font.setPixelSize(max(16, min(self._count_px_max, room * 100 // width_at_100)))
        if font != self.count_label.font():
            self.count_label.setFont(font)

    def _finish_rename(self) -> None:
        self.name_edit.clearFocus()  # first, so the cleaned-up name can be shown
        self.renamed.emit(self.lap, self.name_edit.text())

    def _cancel_rename(self) -> None:
        self.name_edit.setText(self.lap.name)
        self.name_edit.clearFocus()
        self.name_edit.setCursorPosition(0)


class LapList(QScrollArea):
    """The laps, one row each, sharing the height equally. Scrolls once they no longer fit."""

    ROW_MIN = 56
    ROW_MAX = 220
    GAP = 10

    def __init__(self):
        super().__init__(objectName="lapList", widgetResizable=True, frameShape=QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget(objectName="lapListInner")
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self.GAP)
        self._layout.addStretch()
        self.setWidget(inner)
        self.rows: list[LapRow] = []

    def set_rows(self, rows: list[LapRow]) -> None:
        for row in self.rows:
            self._layout.removeWidget(row)
            row.hide()  # deleteLater() leaves it drawn until the event loop gets to it
            row.deleteLater()
        self.rows = rows
        for index, row in enumerate(rows):
            self._layout.insertWidget(index, row)
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        count = max(1, len(self.rows))
        height = (self.viewport().height() - (count - 1) * self.GAP) // count
        for row in self.rows:
            row.set_height(max(self.ROW_MIN, min(self.ROW_MAX, height)))


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None, sim_rate_hz: float = 5.0):
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        self.sim_rate_hz = sim_rate_hz
        self.device: Device | None = None
        self.simulated = False
        self.laps, self.tally = self._load_laps()
        self._laps_dirty = False
        self.rate_meter = RateMeter()
        self._last_paused_pulse_s: float | None = None

        self._trigger_timer = QTimer(self, singleShot=True, interval=TRIGGER_FLASH_MS)
        self._trigger_timer.timeout.connect(lambda: self._set_trigger_lit(False))
        self._threshold_timer = QTimer(self, singleShot=True, interval=200)
        self._threshold_timer.timeout.connect(self._send_threshold)
        self._holdoff_timer = QTimer(self, singleShot=True, interval=200)
        self._holdoff_timer.timeout.connect(self._send_holdoff)

        self.setWindowTitle("Laser Shot Counter")
        self.setMinimumSize(860, 500)
        self.resize(900, 640)
        self._build()
        self._dark = self._initial_dark()
        self._apply_theme()
        self._refresh_ports()
        self._rebuild_lap_rows()
        self._set_connected(False)

        self._poll_timer = QTimer(self, interval=POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()
        self._save_timer = QTimer(self, interval=SAVE_MS)
        self._save_timer.timeout.connect(self._save_if_dirty)
        self._save_timer.start()

    # ---- layout ---------------------------------------------------------------------------------

    def _build(self) -> None:
        root = QWidget(objectName="root")
        root.setFocusPolicy(Qt.ClickFocus)  # clicking the background takes focus out of the fields
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(0)

        top = QHBoxLayout()
        self.trigger_dot = QLabel("●", objectName="triggerDot", toolTip="Flashes on every detected pulse")
        dot_font = self.trigger_dot.font()
        dot_font.setPixelSize(18)
        self.trigger_dot.setFont(dot_font)
        self.rate_label = QLabel(objectName="rate")
        rate_font = display_font(QFont.Weight.Medium)
        rate_font.setPixelSize(22)
        self.rate_label.setFont(rate_font)
        self.state_pill = QLabel("○  NOT CONNECTED", objectName="statePill")
        self.state_pill.setProperty("state", "disconnected")
        self.conn_label = QLabel(objectName="muted")
        theme_button = QToolButton(text="◐", toolTip="Switch between light and dark")
        theme_button.clicked.connect(self._toggle_theme)
        top.addWidget(self.trigger_dot)
        top.addSpacing(4)
        top.addWidget(QLabel("trigger", objectName="muted"))
        top.addSpacing(28)
        top.addWidget(self.rate_label)
        top.addStretch()
        top.addWidget(self.state_pill)
        top.addWidget(self.conn_label)
        top.addSpacing(8)
        top.addWidget(theme_button)
        layout.addLayout(top)

        layout.addSpacing(12)
        self.banner = QLabel(
            "Shots are being detected, but every lap is paused.",
            objectName="banner",
            alignment=Qt.AlignCenter,
        )
        policy = self.banner.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # keep the laps from jumping when the banner appears
        self.banner.setSizePolicy(policy)
        self.banner.hide()
        layout.addWidget(self.banner)
        layout.addSpacing(12)

        self.lap_list = LapList()
        layout.addWidget(self.lap_list, 1)
        layout.addSpacing(12)

        footer = QHBoxLayout()
        self.new_lap_button = QPushButton(
            "+  New lap", objectName="small", toolTip="Add a lap that counts from 0 while the others carry on"
        )
        self.new_lap_button.setFocusPolicy(Qt.NoFocus)
        self.new_lap_button.clicked.connect(self.new_lap)
        self.lap_total = QLabel(objectName="muted")
        footer.addWidget(self.new_lap_button)
        footer.addStretch()
        footer.addWidget(self.lap_total)
        layout.addLayout(footer)

        layout.addSpacing(16)
        divider = QFrame(objectName="divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(14)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.threshold_spin = QSpinBox(
            minimum=p.THR_MIN_MV,
            maximum=p.THR_MAX_MV,
            singleStep=5,
            suffix=" mV",
            toolTip="A pulse counts when the photodiode signal dips below this voltage",
        )
        self.threshold_spin.setValue(self.settings.value("threshold_mv", DEFAULT_THRESHOLD_MV, type=int))
        self.threshold_spin.valueChanged.connect(lambda _value: self._threshold_timer.start())
        self.threshold_spin.editingFinished.connect(self.threshold_spin.clearFocus)
        self.threshold_meas = QLabel(
            objectName="muted", toolTip="Threshold as measured inside the box (approximate, about ±15 mV)"
        )
        self.holdoff_spin = QDoubleSpinBox(
            minimum=p.HOLD_MIN_US / 1000,
            maximum=p.HOLD_MAX_US / 1000,
            decimals=2,
            singleStep=0.1,
            suffix=" ms",
            toolTip="Dead time after each pulse, so ringing can't be counted twice",
        )
        self.holdoff_spin.setValue(self.settings.value("holdoff_ms", DEFAULT_HOLDOFF_MS, type=float))
        self.holdoff_spin.valueChanged.connect(lambda _value: self._holdoff_timer.start())
        self.holdoff_spin.editingFinished.connect(self.holdoff_spin.clearFocus)
        self.threshold_spin.setFixedWidth(112)
        self.holdoff_spin.setFixedWidth(100)
        self.port_combo = PortCombo(minimumWidth=130)
        self.port_combo.aboutToShowPopup.connect(self._refresh_ports)
        self.connect_button = QPushButton("Connect", objectName="small")
        self.connect_button.setFocusPolicy(Qt.NoFocus)
        self.connect_button.clicked.connect(self._toggle_connection)

        controls.addWidget(QLabel("Threshold", objectName="fieldLabel"))
        controls.addWidget(self.threshold_spin)
        controls.addWidget(self.threshold_meas)
        controls.addSpacing(14)
        controls.addWidget(QLabel("Holdoff", objectName="fieldLabel"))
        controls.addWidget(self.holdoff_spin)
        controls.addStretch()
        controls.addWidget(QLabel("Device", objectName="fieldLabel"))
        controls.addWidget(self.port_combo)
        controls.addWidget(self.connect_button)
        layout.addLayout(controls)

    # ---- theme ----------------------------------------------------------------------------------

    def _initial_dark(self) -> bool:
        saved = self.settings.value("theme", "", type=str)
        if saved in ("light", "dark"):
            return saved == "dark"
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet(self._dark))

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self.settings.setValue("theme", "dark" if self._dark else "light")
        self._apply_theme()

    # ---- connection -----------------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        selected = self.port_combo.currentData() or self.settings.value("device", "", type=str)
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} (Pico)" if port.is_pico else port.device, port.device)
            self.port_combo.setItemData(self.port_combo.count() - 1, port.description, Qt.ToolTipRole)
        self.port_combo.addItem(SIMULATOR, SIMULATOR)
        self.port_combo.setItemData(self.port_combo.count() - 1, "Pretend laser, for trying the app", Qt.ToolTipRole)
        index = self.port_combo.findData(selected)
        self.port_combo.setCurrentIndex(max(index, 0))

    def auto_connect(self) -> bool:
        """Reconnect to the last box used, or to the only Pico plugged in."""
        ports = list_serial_ports()
        last = self.settings.value("device", "", type=str)
        if last and last != SIMULATOR and last in {port.device for port in ports}:
            return self.connect_device(last)
        picos = [port.device for port in ports if port.is_pico]
        return self.connect_device(picos[0]) if len(picos) == 1 else False

    def connect_device(self, name: str) -> bool:
        self.disconnect_device()
        try:
            if name == SIMULATOR:
                transport = SimTransport(SimulatedFirmware(rep_rate_hz=self.sim_rate_hz))
            else:
                transport = SerialTransport(name)
        except Exception as exc:  # serial errors vary by platform
            self.statusBar().showMessage(f"Could not open {name}: {exc}")
            return False
        if name == SIMULATOR:
            self._save_if_dirty()
            self.laps, self.tally = Laps(), ShotTally()  # practice laps, never saved
            self.simulated = True
            self._rebuild_lap_rows()
        self.tally.reconnected()
        self.device = Device(transport)
        self.device.open()
        self.settings.setValue("device", name)
        index = self.port_combo.findData(name)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
        self._set_connected(True)
        # The box counts all the time, even while the app is closed; pausing happens per lap.
        for line in (
            p.ID_QUERY,
            p.cmd_threshold(self.threshold_spin.value()),
            p.cmd_holdoff(self._holdoff_us()),
            p.START,
            p.STATUS_QUERY,
        ):
            self.device.send(line)
        self.statusBar().showMessage(f"Connected to {transport.label}", 4000)
        return True

    def disconnect_device(self) -> None:
        if self.device is None:
            return
        device, self.device = self.device, None
        device.close()
        if self.simulated:
            self.simulated = False
            self.laps, self.tally = self._load_laps()  # back to the real laps
            self._laps_dirty = False
            self._rebuild_lap_rows()
        else:
            self._save_laps()
        self._set_connected(False)

    def _toggle_connection(self) -> None:
        if self.device is not None:
            self.disconnect_device()
        else:
            self.connect_device(self.port_combo.currentData())

    def _set_connected(self, connected: bool) -> None:
        self.port_combo.setEnabled(not connected)
        self.connect_button.setText("Disconnect" if connected else "Connect")
        self.rate_meter.clear()
        self._last_paused_pulse_s = None
        self.state_pill.setVisible(not connected)
        self.conn_label.setText(self.device.label if connected else "")
        if not connected:
            self.threshold_meas.setText("")
        self._refresh_laps()
        self._refresh_live(time.monotonic())

    # ---- laps -----------------------------------------------------------------------------------

    def new_lap(self) -> Lap | None:
        if self.device is None:
            return None
        lap = self.laps.add()
        if lap is not None:
            self._laps_changed(rebuild=True)
        return lap

    def toggle_lap(self, lap: Lap) -> None:
        if self.device is not None:
            lap.running = not lap.running
            self._laps_changed()

    def reset_lap(self, lap: Lap) -> None:
        if self.device is not None:
            lap.count = 0
            self._laps_changed()

    def delete_lap(self, lap: Lap) -> bool:
        if not self.laps.remove(lap):
            return False
        self._laps_changed(rebuild=True)
        return True

    def rename_lap(self, lap: Lap, name: str) -> None:
        self.laps.rename(lap, name)
        self._laps_changed()

    def _confirm_reset_lap(self, lap: Lap) -> None:
        if lap.count and self._confirm("Reset lap", f"Reset {lap.name} to 0?\n\nCurrent count: {lap.count:,}", "Reset"):
            self.reset_lap(lap)

    def _confirm_delete_lap(self, lap: Lap) -> None:
        text = f"Delete {lap.name}?\n\nIts count of {lap.count:,} will be lost."
        if not lap.count or self._confirm("Delete lap", text, "Delete"):
            self.delete_lap(lap)

    def _confirm(self, title: str, text: str, action: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Cancel, self)
        accept = box.addButton(action, QMessageBox.AcceptRole)
        box.setDefaultButton(QMessageBox.Cancel)
        box.exec()
        return box.clickedButton() is accept

    def _rebuild_lap_rows(self) -> None:
        rows = []
        for lap in self.laps:
            row = LapRow(lap)
            row.toggle_clicked.connect(self.toggle_lap)
            row.reset_clicked.connect(self._confirm_reset_lap)
            row.delete_clicked.connect(self._confirm_delete_lap)
            row.renamed.connect(self.rename_lap)
            rows.append(row)
        self.lap_list.set_rows(rows)
        self._refresh_laps()

    def _refresh_laps(self) -> None:
        connected = self.device is not None
        for row in self.lap_list.rows:
            row.refresh(connected, self.laps.can_remove)
        self.new_lap_button.setEnabled(connected and self.laps.can_add)
        self.lap_total.setText(f"{len(self.laps)} of {MAX_LAPS} laps")

    def _laps_changed(self, rebuild: bool = False) -> None:
        if rebuild:
            self._rebuild_lap_rows()
        else:
            self._refresh_laps()
        self._save_laps()
        self._refresh_live(time.monotonic())

    def _load_laps(self) -> tuple[Laps, ShotTally]:
        try:
            state = json.loads(self.settings.value("laps", "", type=str) or "{}")
        except ValueError:
            state = {}
        if not isinstance(state, dict):
            state = {}
        try:
            mark = (int(state["box"][0]), int(state["box"][1]))
        except (KeyError, TypeError, ValueError, IndexError):
            mark = None
        return Laps.from_list(state.get("laps")), ShotTally(mark)

    def _save_laps(self) -> None:
        """Remember the laps, and where the box's total stood, for next time. Simulator laps aren't saved."""
        self._laps_dirty = False
        if not self.simulated:
            self.settings.setValue("laps", json.dumps({"laps": self.laps.to_list(), "box": self.tally.mark}))

    def _save_if_dirty(self) -> None:
        if self._laps_dirty:
            self._save_laps()

    # ---- commands -------------------------------------------------------------------------------

    def _holdoff_us(self) -> int:
        return min(max(round(self.holdoff_spin.value() * 1000), p.HOLD_MIN_US), p.HOLD_MAX_US)

    def _send_threshold(self) -> None:
        value = self.threshold_spin.value()
        self.settings.setValue("threshold_mv", value)
        if self.device is not None:
            self.device.send(p.cmd_threshold(value))

    def _send_holdoff(self) -> None:
        self.settings.setValue("holdoff_ms", self.holdoff_spin.value())
        if self.device is not None:
            self.device.send(p.cmd_holdoff(self._holdoff_us()))

    # ---- incoming messages ----------------------------------------------------------------------

    def _poll(self) -> None:
        now = time.monotonic()
        shots_before = [lap.count for lap in self.laps]
        while self.device is not None:
            try:
                message = self.device.messages.get_nowait()
            except queue.Empty:
                break
            self._handle(message, now)
        if [lap.count for lap in self.laps] != shots_before:
            self._refresh_laps()
        self._refresh_live(now)

    def _handle(self, message, now: float) -> None:
        match message:
            case p.Event():
                self._take_reading(message.count, message.t_us, message.counted)
                self.rate_meter.add(message.t_us, now)
                if not self.laps.any_running:
                    self._last_paused_pulse_s = now
                self._set_trigger_lit(True)
                self._trigger_timer.start()
            case p.Status():
                self._take_reading(message.count, message.t_us, message.running)
                if not message.running:
                    self.device.send(p.START)
                if message.thr_meas_mv is not None:
                    self.threshold_meas.setText(_minus(f"measured ≈ {message.thr_meas_mv:.0f} mV"))
            case p.Ident():
                self.conn_label.setText(f"{self.device.label}  ·  firmware {message.firmware}")
            case p.Error():
                self.statusBar().showMessage(f"Counter box: {message.message}", 6000)
            case Disconnected():
                self.disconnect_device()
                self.statusBar().showMessage(f"Connection lost: {message.reason}")
            case p.Ack() | Unparsed():
                pass

    def _take_reading(self, count: int, t_us: int, running: bool) -> None:
        self.laps.add_shots(self.tally.update(count, t_us, running))
        self._laps_dirty = True

    def _set_trigger_lit(self, lit: bool) -> None:
        self.trigger_dot.setProperty("lit", "true" if lit else "false")
        _repolish(self.trigger_dot)

    def _refresh_live(self, now: float) -> None:
        rate = self.rate_meter.rate(now) if self.device is not None else None
        self.rate_label.setText(f"{'—' if rate is None else f'{rate:.1f}'} shots/s")
        paused_pulses = (
            self.device is not None
            and not self.laps.any_running
            and self._last_paused_pulse_s is not None
            and now - self._last_paused_pulse_s < PAUSED_PULSE_WARNING_S
        )
        self.banner.setVisible(paused_pulses)

    def closeEvent(self, event) -> None:
        self.disconnect_device()
        self._save_if_dirty()
        super().closeEvent(event)
