"""Connection to the counter box (or the simulator) with a background reader thread.

Parsed messages land on `Device.messages`, a thread-safe queue the UI drains on a timer.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from .protocol import ProtocolError, parse_line
from .simulator import SimulatedFirmware

PICO_USB_VID = 0x2E8A  # Raspberry Pi


@dataclass(frozen=True)
class Disconnected:
    reason: str


@dataclass(frozen=True)
class Unparsed:
    """A line that isn't protocol, e.g. the MicroPython boot banner."""

    line: str


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    is_pico: bool


def list_serial_ports() -> list[PortInfo]:
    from serial.tools import list_ports

    return [
        PortInfo(port.device, port.description or port.device, port.vid == PICO_USB_VID)
        for port in sorted(list_ports.comports(), key=lambda port: port.device)
    ]


class Transport(Protocol):
    label: str

    def write_line(self, line: str) -> None: ...

    def read_line(self, timeout: float) -> str | None: ...

    def close(self) -> None: ...


class SerialTransport:
    def __init__(self, port: str, baudrate: int = 115200):
        import serial

        self.label = port
        self._serial = serial.Serial(port, baudrate, timeout=0.1, write_timeout=1.0)
        self._buffer = bytearray()

    def write_line(self, line: str) -> None:
        self._serial.write(line.encode("ascii") + b"\n")

    def read_line(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[:newline])
                del self._buffer[: newline + 1]
                return raw.decode("ascii", "replace").rstrip("\r")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self._serial.timeout = remaining
            self._buffer += self._serial.read(max(1, self._serial.in_waiting))

    def close(self) -> None:
        self._serial.close()


class SimTransport:
    def __init__(self, firmware: SimulatedFirmware | None = None):
        self.label = "Simulator"
        self.firmware = firmware or SimulatedFirmware()
        self._pending: deque[str] = deque()
        self._lock = threading.Lock()

    def write_line(self, line: str) -> None:
        with self._lock:
            self._pending.extend(self.firmware.handle(line))

    def read_line(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._pending.extend(self.firmware.poll())
                if self._pending:
                    return self._pending.popleft()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.005, remaining))

    def close(self) -> None:
        pass


class Device:
    def __init__(self, transport: Transport):
        self.transport = transport
        self.messages: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read_loop, name="device-reader", daemon=True)

    @property
    def label(self) -> str:
        return self.transport.label

    def open(self) -> None:
        self._thread.start()

    def send(self, line: str) -> None:
        try:
            self.transport.write_line(line)
        except Exception as exc:  # serial errors vary by platform
            self.messages.put(Disconnected(str(exc)))

    def close(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.transport.close()

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                line = self.transport.read_line(0.1)
            except Exception as exc:
                if not self._stop.is_set():
                    self.messages.put(Disconnected(str(exc)))
                return
            if not line or not line.strip():
                continue
            try:
                self.messages.put(parse_line(line))
            except ProtocolError:
                self.messages.put(Unparsed(line))
