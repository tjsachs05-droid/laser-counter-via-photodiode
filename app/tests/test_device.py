import queue
import time

from laser_counter import protocol as p
from laser_counter.device import Device, Disconnected, SimTransport, Unparsed
from laser_counter.simulator import SimulatedFirmware


def drain(device: Device, seconds: float) -> list:
    messages, deadline = [], time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            messages.append(device.messages.get(timeout=0.05))
        except queue.Empty:
            pass
    return messages


class ScriptedTransport:
    label = "scripted"

    def __init__(self, lines, then_fail=False):
        self._lines = list(lines)
        self._then_fail = then_fail
        self.written = []

    def write_line(self, line):
        self.written.append(line)

    def read_line(self, timeout):
        if self._lines:
            return self._lines.pop(0)
        if self._then_fail:
            raise OSError("device unplugged")
        time.sleep(timeout)
        return None

    def close(self):
        pass


def test_device_talks_to_simulator():
    device = Device(SimTransport(SimulatedFirmware(rep_rate_hz=200, weak_shot_fraction=0.0)))
    device.open()
    try:
        device.send(p.START)
        messages = drain(device, 0.5)
    finally:
        device.close()
    assert p.Ack("START") in messages
    counted = [m for m in messages if isinstance(m, p.Event) and m.counted]
    assert len(counted) >= 20
    assert [e.count for e in counted] == list(range(counted[0].count, counted[0].count + len(counted)))


def test_non_protocol_lines_are_passed_through_as_unparsed():
    device = Device(ScriptedTransport(["MicroPython v1.24.0", "", "OK START"]))
    device.open()
    try:
        messages = drain(device, 0.3)
    finally:
        device.close()
    assert messages == [Unparsed("MicroPython v1.24.0"), p.Ack("START")]


def test_read_failure_reports_disconnect():
    device = Device(ScriptedTransport([], then_fail=True))
    device.open()
    try:
        messages = drain(device, 0.3)
    finally:
        device.close()
    assert messages == [Disconnected("device unplugged")]
