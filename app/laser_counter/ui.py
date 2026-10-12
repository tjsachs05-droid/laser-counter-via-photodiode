"""Main window: live count, shots per second, start/pause, reset, and the trigger threshold."""

from __future__ import annotations

import queue
import time

from PySide6 import QtSvg  # noqa: F401  Qt's SVG image plugin (arrow icons) only loads once this is imported
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import protocol as p
from .device import Device, Disconnected, SerialTransport, SimTransport, Unparsed, list_serial_ports
from .rate import RateMeter
from .simulator import SimulatedFirmware
from .theme import stylesheet

SIMULATOR = "Simulator"
POLL_MS = 30
TRIGGER_FLASH_MS = 120
PAUSED_PULSE_WARNING_S = 3.0
DEFAULT_THRESHOLD_MV = -400
DEFAULT_HOLDOFF_MS = 1.0
DISPLAY_FONTS = ["Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", "Arial"]

STATE_TEXT = {"running": "●  RUNNING", "paused": "●  PAUSED", "disconnected": "○  NOT CONNECTED"}


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


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None, sim_rate_hz: float = 10.0):
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        self.sim_rate_hz = sim_rate_hz
        self.device: Device | None = None
        self.running = False
        self.count = 0
        self.rate_meter = RateMeter()
        self._last_paused_pulse_s: float | None = None

        self._trigger_timer = QTimer(self, singleShot=True, interval=TRIGGER_FLASH_MS)
        self._trigger_timer.timeout.connect(lambda: self._set_trigger_lit(False))
        self._threshold_timer = QTimer(self, singleShot=True, interval=200)
        self._threshold_timer.timeout.connect(self._send_threshold)
        self._holdoff_timer = QTimer(self, singleShot=True, interval=200)
        self._holdoff_timer.timeout.connect(self._send_holdoff)

        self.setWindowTitle("Laser Shot Counter")
        self.setMinimumSize(600, 460)
        self.resize(860, 620)
        self._build()
        self._dark = self._initial_dark()
        self._apply_theme()
        self._refresh_ports()
        self._set_connected(False)

        self._poll_timer = QTimer(self, interval=POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

    # ---- layout ---------------------------------------------------------------------------------

    def _build(self) -> None:
        root = QWidget(objectName="root")
        root.setFocusPolicy(Qt.ClickFocus)  # clicking the background takes focus out of the fields
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(0)

        top = QHBoxLayout()
        self.state_pill = QLabel(objectName="statePill")
        self.trigger_dot = QLabel("●", objectName="triggerDot", toolTip="Flashes on every detected pulse")
        dot_font = self.trigger_dot.font()
        dot_font.setPixelSize(18)
        self.trigger_dot.setFont(dot_font)
        self.conn_label = QLabel(objectName="muted")
        theme_button = QToolButton(text="◐", toolTip="Switch between light and dark")
        theme_button.clicked.connect(self._toggle_theme)
        top.addWidget(self.state_pill)
        top.addStretch()
        top.addWidget(self.trigger_dot)
        top.addSpacing(4)
        top.addWidget(QLabel("trigger", objectName="muted"))
        top.addSpacing(20)
        top.addWidget(self.conn_label)
        top.addSpacing(8)
        top.addWidget(theme_button)
        layout.addLayout(top)

        layout.addSpacing(12)
        self.banner = QLabel(
            "Shots are being detected while paused. Press Start to count them.",
            objectName="banner",
            alignment=Qt.AlignCenter,
        )
        policy = self.banner.sizePolicy()
        policy.setRetainSizeWhenHidden(True)  # keep the count from jumping when the banner appears
        self.banner.setSizePolicy(policy)
        self.banner.hide()
        layout.addWidget(self.banner)
        layout.addStretch(2)

        self.count_label = QLabel("0", objectName="count", alignment=Qt.AlignCenter)
        self.count_label.setFont(display_font(QFont.Weight.Medium))
        self.caption_label = QLabel("shots", objectName="caption", alignment=Qt.AlignCenter)
        self.caption_label.setFont(display_font())
        self.rate_label = QLabel(objectName="rate", alignment=Qt.AlignCenter)
        self.rate_label.setFont(display_font())
        layout.addWidget(self.count_label)
        layout.addWidget(self.caption_label)
        layout.addSpacing(20)
        layout.addWidget(self.rate_label)
        layout.addStretch(2)

        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        self.start_button = QPushButton("Start", objectName="primary", toolTip="Start / pause counting (Space)")
        self.start_button.clicked.connect(self.toggle_running)
        self.reset_button = QPushButton("Reset…", toolTip="Set the count to 0 (R)")
        self.reset_button.clicked.connect(self._confirm_reset)
        buttons.addStretch()
        for button, width in ((self.start_button, 200), (self.reset_button, 160)):
            font = button.font()
            font.setPointSizeF(font.pointSizeF() * 1.25)
            button.setFont(font)
            button.setMinimumWidth(width)
            button.setFocusPolicy(Qt.NoFocus)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        layout.addSpacing(26)
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
        self.threshold_meas = QLabel(objectName="muted", toolTip="Threshold as measured inside the box")
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

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_running)
        QShortcut(QKeySequence(Qt.Key_R), self, activated=self._confirm_reset)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        size = int(max(56, min(self.height() * 0.24, self.width() * 0.15)))
        for label, factor in ((self.count_label, 1.0), (self.rate_label, 0.30), (self.caption_label, 0.16)):
            font = label.font()
            font.setPixelSize(max(14, int(size * factor)))
            label.setFont(font)

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
        self.device = Device(transport)
        self.device.open()
        self.settings.setValue("device", name)
        index = self.port_combo.findData(name)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
        self._set_connected(True)
        for line in (p.ID_QUERY, p.cmd_threshold(self.threshold_spin.value()), p.cmd_holdoff(self._holdoff_us()), p.STATUS_QUERY):
            self.device.send(line)
        self.statusBar().showMessage(f"Connected to {transport.label}", 4000)
        return True

    def disconnect_device(self) -> None:
        if self.device is None:
            return
        device, self.device = self.device, None
        device.close()
        self._set_connected(False)

    def _toggle_connection(self) -> None:
        if self.device is not None:
            self.disconnect_device()
        else:
            self.connect_device(self.port_combo.currentData())

    def _set_connected(self, connected: bool) -> None:
        self.start_button.setEnabled(connected)
        self.reset_button.setEnabled(connected)
        self.port_combo.setEnabled(not connected)
        self.connect_button.setText("Disconnect" if connected else "Connect")
        self.rate_meter.clear()
        self._last_paused_pulse_s = None
        if connected:
            self.conn_label.setText(self.device.label)
        else:
            self.running = False
            self.conn_label.setText("")
            self.threshold_meas.setText("")
            self._set_state("disconnected")
        self._refresh_live(time.monotonic())

    # ---- commands -------------------------------------------------------------------------------

    def toggle_running(self) -> None:
        if self.device is not None:
            self.device.send(p.PAUSE if self.running else p.START)

    def reset_count(self) -> None:
        if self.device is not None:
            self.device.send(p.RESET)

    def _confirm_reset(self) -> None:
        if self.device is None:
            return
        answer = QMessageBox.question(
            self,
            "Reset count",
            f"Reset the count to 0?\n\nCurrent count: {self.count:,}",
            QMessageBox.Reset | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Reset:
            self.reset_count()

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
        while self.device is not None:
            try:
                message = self.device.messages.get_nowait()
            except queue.Empty:
                break
            self._handle(message, now)
        self._refresh_live(now)

    def _handle(self, message, now: float) -> None:
        match message:
            case p.Event():
                self._set_count(message.count)
                self.rate_meter.add(message.t_us, now)
                if not message.counted:
                    self._last_paused_pulse_s = now
                self._set_trigger_lit(True)
                self._trigger_timer.start()
            case p.Status():
                self._set_count(message.count)
                self._set_running(message.running)
                if message.thr_meas_mv is not None:
                    self.threshold_meas.setText(_minus(f"measured {message.thr_meas_mv:.0f} mV"))
            case p.Ident():
                self.conn_label.setText(f"{self.device.label}  ·  firmware {message.firmware}")
            case p.Error():
                self.statusBar().showMessage(f"Counter box: {message.message}", 6000)
            case Disconnected():
                self.disconnect_device()
                self.statusBar().showMessage(f"Connection lost: {message.reason}")
            case p.Ack() | Unparsed():
                pass

    def _set_count(self, count: int) -> None:
        self.count = count
        text = f"{count:,}"
        if self.count_label.text() != text:
            self.count_label.setText(text)

    def _set_running(self, running: bool) -> None:
        self.running = running
        self._set_state("running" if running else "paused")

    def _set_state(self, state: str) -> None:
        self.state_pill.setText(STATE_TEXT[state])
        self.state_pill.setProperty("state", state)
        _repolish(self.state_pill)
        self.start_button.setText("Pause" if state == "running" else "Start")
        self.start_button.setProperty("kind", "pause" if state == "running" else "start")
        _repolish(self.start_button)

    def _set_trigger_lit(self, lit: bool) -> None:
        self.trigger_dot.setProperty("lit", "true" if lit else "false")
        _repolish(self.trigger_dot)

    def _refresh_live(self, now: float) -> None:
        rate = self.rate_meter.rate(now) if self.device is not None else None
        self.rate_label.setText(f"{'—' if rate is None else f'{rate:.1f}'} shots/s")
        paused_pulses = (
            self.device is not None
            and not self.running
            and self._last_paused_pulse_s is not None
            and now - self._last_paused_pulse_s < PAUSED_PULSE_WARNING_S
        )
        self.banner.setVisible(paused_pulses)

    def closeEvent(self, event) -> None:
        self.disconnect_device()
        super().closeEvent(event)
