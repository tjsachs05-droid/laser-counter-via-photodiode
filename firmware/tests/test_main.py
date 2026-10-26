"""Runs firmware/main.py under CPython, with stand-ins for the Pico's pins, I2C, ADC, timers and clock."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from laser_counter import protocol as p

FIRMWARE = Path(__file__).resolve().parents[1] / "main.py"
TICKS_PERIOD = 1 << 30  # MicroPython's ticks_us()/ticks_ms() wrap here on the RP2040


class FakeTime:
    def __init__(self, start_us):
        self.us = start_us

    def module(self):
        mod = types.ModuleType("time")
        mod.ticks_us = lambda: self.us % TICKS_PERIOD
        mod.ticks_ms = lambda: (self.us // 1000) % TICKS_PERIOD
        mod.ticks_add = lambda ticks, delta: (ticks + delta) % TICKS_PERIOD
        mod.ticks_diff = self.ticks_diff
        mod.sleep_us = self.sleep_us
        mod.sleep_ms = lambda ms: self.sleep_us(ms * 1000)
        return mod

    @staticmethod
    def ticks_diff(a, b):
        diff = (a - b) % TICKS_PERIOD
        return diff - TICKS_PERIOD if diff >= TICKS_PERIOD // 2 else diff

    def sleep_us(self, us):
        self.us += us


class FakePin:
    IN, OUT, PULL_DOWN, IRQ_RISING = 0, 1, 2, 1

    def __init__(self, *args, value=0, log=None, name="", **kwargs):
        self._value = value
        self.handler = None
        self.history = []
        self._log = log
        self._name = name

    def value(self, v=None):
        if v is None:
            return self._value
        self._value = v
        self.history.append(v)
        if self._log is not None:
            self._log.append(f"{self._name}={v}")

    def irq(self, handler, trigger, hard=False):
        self.handler = handler


class FakeI2C:
    def __init__(self, present, log):
        self.present = present
        self.writes = []
        self._log = log

    def scan(self):
        return [0x60] if self.present else []

    def writeto(self, addr, data):
        if not self.present:
            raise OSError("ENODEV")
        self.writes.append(bytes(data))
        self._log.append("i2c")


class FakeADC:
    def __init__(self, mv):
        self._raw = round(mv / 3300 * 65535)

    def read_u16(self):
        return self._raw


class FakeTimer:
    PERIODIC = 1
    created = []

    def __init__(self, mode=None, period=None, callback=None):
        self.period = period
        self.callback = callback
        self.active = True
        FakeTimer.created.append(self)

    def deinit(self):
        self.active = False


class FakeStateMachine:
    created = []

    def __init__(self, sm_id, program, freq=None, set_base=None):
        self.program = program
        self.freq = freq
        self.puts = []
        self.running = False
        FakeStateMachine.created.append(self)

    def active(self, on):
        self.running = bool(on)

    def put(self, word):
        self.puts.append(word)


def fake_rp2():
    rp2 = types.ModuleType("rp2")
    rp2.PIO = types.SimpleNamespace(OUT_HIGH=1)
    rp2.asm_pio = lambda **kwargs: (lambda program: program)  # the PIO program body never runs on a PC
    rp2.StateMachine = FakeStateMachine
    return rp2


def load_firmware(fake_time):
    machine = types.ModuleType("machine")
    machine.Pin, machine.I2C, machine.ADC, machine.Timer = FakePin, FakeI2C, FakeADC, FakeTimer
    machine.disable_irq = lambda: 0
    machine.enable_irq = lambda state: None
    machine.freq = lambda: 125_000_000
    micropython = types.ModuleType("micropython")
    micropython.alloc_emergency_exception_buf = lambda size: None
    fakes = {"time": fake_time.module(), "machine": machine, "micropython": micropython, "rp2": fake_rp2()}
    saved = {name: sys.modules.get(name) for name in fakes}
    sys.modules.update(fakes)
    try:
        spec = importlib.util.spec_from_file_location("pico_main", FIRMWARE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return module


class Rig:
    """The firmware's Box wired to a pretend latch: CLR low forces Q low, and a pulse sets Q unless it's already set."""

    def __init__(self, dac_present=True, start_us=1_000_000):
        self.time = FakeTime(start_us)
        self.fw = load_firmware(self.time)
        self.log = []
        self.q = FakePin(name="q")
        self.clr = FakePin(value=0, log=self.log, name="clr")
        self.i2c = FakeI2C(dac_present, self.log)
        self.box = self.fw.Box(self.q, self.clr, FakePin(), self.fw.Dac(self.i2c), FakeADC(1500), FakeADC(1100))
        original_value = self.clr.value

        def clr_value(v=None):
            if v == 0:
                self.q._value = 0
            return original_value(v)

        self.clr.value = clr_value
        self.box.start()

    def pulse(self):
        if self.clr.value() == 1 and self.q.value() == 0:
            self.q._value = 1
            self.q.handler(self.q)

    def run(self, seconds, step_us=200):
        out, end = [], self.time.us + round(seconds * 1e6)
        while self.time.us < end:
            out += self.box.service()
            self.time.us += step_us
        return out

    def send(self, line):
        return self.box.handle(line)


def parsed(lines):
    return [p.parse_line(line) for line in lines]


def events(lines):
    return [m for m in parsed(lines) if isinstance(m, p.Event)]


def test_latch_held_clear_until_dac_is_set():
    rig = Rig()
    assert rig.log == ["clr=0", "i2c", "i2c", "clr=1"]


def test_dac_codes_for_bias_and_default_threshold():
    rig = Rig()
    # 1500 mV -> code 3000 = 0xBB8 on channel A; 1500 - 400 = 1100 mV -> 2200 = 0x898 on channel B
    assert rig.i2c.writes == [bytes((0x40, 0x8B, 0xB8)), bytes((0x42, 0x88, 0x98))]


def test_threshold_moves_channel_b():
    rig = Rig()
    assert rig.send("THR -250")[0] == "OK THR -250"
    assert rig.i2c.writes[-1] == bytes((0x42, 0x89, 0xC4))  # 1250 mV -> 2500 = 0x9C4


def test_boots_paused_and_reports_pulses_without_counting():
    rig = Rig()
    rig.pulse()
    seen = events(rig.run(0.01))
    assert seen == [p.Event(0, seen[0].t_us, False)]


def test_counts_once_per_pulse_and_rearms_after_holdoff():
    rig = Rig()
    rig.send("START")
    rig.pulse()
    out = rig.run(0.0005)
    rig.pulse()  # still inside the 1 ms holdoff: the latch is still set, so nothing new happens
    out += rig.run(0.002)
    rig.pulse()  # after the holdoff the latch has been cleared and re-armed
    out += rig.run(0.002)
    assert [(e.count, e.counted) for e in events(out)] == [(1, True), (2, True)]


def test_longer_holdoff_skips_shots_inside_it():
    rig = Rig()
    rig.send("START")
    assert rig.send("HOLD 150000")[0] == "OK HOLD 150000"
    out = []
    for _ in range(10):  # 10 Hz pulses, 150 ms holdoff: every other one is ignored
        rig.pulse()
        out += rig.run(0.1)
    assert [e.count for e in events(out)] == [1, 2, 3, 4, 5]


def test_pause_and_reset():
    rig = Rig()
    rig.send("START")
    for _ in range(3):
        rig.pulse()
        rig.run(0.01)
    assert rig.send("PAUSE")[0] == "OK PAUSE"
    rig.pulse()
    paused = events(rig.run(0.01))
    assert paused[-1] == p.Event(3, paused[-1].t_us, False)
    status = parsed(rig.send("RESET"))[1]
    assert status.count == 0 and status.running is False


def test_timestamps_survive_the_ticks_wraparound():
    rig = Rig(start_us=TICKS_PERIOD - 3_000_000)  # the Pico's tick counter wraps 3 s in
    out = []
    for _ in range(30):
        rig.pulse()
        out += rig.run(0.2)
    times = [e.t_us for e in events(out)]
    assert len(times) == 30
    assert all(b - a == pytest.approx(200_000, abs=400) for a, b in zip(times, times[1:]))


def test_missed_edge_is_caught_by_the_level_check():
    rig = Rig()
    rig.q._value = 1  # latch set, but the interrupt never ran
    assert len(events(rig.run(1.1))) == 1


def test_status_once_a_second_with_readback():
    rig = Rig()
    stats = [m for m in parsed(rig.run(3.05)) if isinstance(m, p.Status)]
    assert len(stats) == 3
    assert stats[0].bias_mv == pytest.approx(1500, abs=0.1)
    assert stats[0].thr_meas_mv == pytest.approx(-400, abs=0.1)


def test_without_dac_threshold_is_kept_and_reported():
    rig = Rig(dac_present=False)
    reply = rig.send("THR -300")
    assert reply[0].startswith("ERR DAC not found")
    status = p.parse_line(reply[1])
    assert status.thr_mv == -300 and status.bias_mv is None
    assert "dac=0" in reply[1]


def test_pulse_defaults_and_actual_width():
    rig = Rig()
    assert rig.send("PULSE 5") == ["OK PULSE 5 48 0"]  # 50 ns asked; nearest whole PIO cycles is 6 x 8 ns
    sm = FakeStateMachine.created[-1]
    assert sm.running and sm.freq == 125_000_000
    assert FakeTimer.created[-1].period == 200


def test_pulse_sends_exactly_count_pulses_then_stops():
    rig = Rig()
    assert rig.send("PULSE 100 16 3") == ["OK PULSE 100 16 3"]
    sm, timer = FakeStateMachine.created[-1], FakeTimer.created[-1]
    for _ in range(6):
        if timer.active:
            timer.callback(timer)
    assert sm.puts == [0, 0, 0]  # 16 ns = 2 cycles = width word 0
    assert not timer.active


def test_pulse_zero_and_test_both_stop_the_pio():
    rig = Rig()
    rig.send("PULSE 5 1000")
    sm = FakeStateMachine.created[-1]
    assert sm.puts == [] and FakeTimer.created[-1].period == 200
    assert rig.send("PULSE 0") == ["OK PULSE 0 0 0"]
    assert not sm.running
    rig.send("PULSE 5 1000")
    sm = FakeStateMachine.created[-1]
    rig.send("TEST 5")
    assert not sm.running


@pytest.mark.parametrize(
    "bad", ["PULSE", "PULSE 2000", "PULSE 5 10", "PULSE 5 2000000", "PULSE 5 50 -1", "PULSE 500 1000000", "PULSE a b c", "PULSE 1 2 3 4"]
)
def test_pulse_rejects_bad_arguments(bad):
    assert Rig().send(bad)[0].startswith("ERR"), bad


def test_commands_match_the_protocol():
    rig = Rig()
    assert p.parse_line(rig.send("ID?")[0]) == p.Ident("laser-counter", "0.2.0")
    assert isinstance(p.parse_line(rig.send("STATUS?")[0]), p.Status)
    for bad in ("THR 50", "THR -2000", "THR abc", "HOLD 5", "HOLD 2000000", "TEST -1", "FIRE"):
        assert rig.send(bad)[0].startswith("ERR"), bad
    assert rig.send("") == []


class Follower:
    """GP2 wired straight to another pin (the bench jumper)."""

    def __init__(self, source):
        self.source = source

    def value(self, v=None):
        return self.source.value()


def test_bench_jumper_detected_only_when_fitted():
    rig = Rig()
    gp15 = FakePin()
    assert rig.fw.bench_jumper_present(gp15, Follower(gp15))
    assert gp15.value() == 0
    lonely = FakePin()
    assert not rig.fw.bench_jumper_present(lonely, FakePin())  # nothing on GP2, as in the finished box
    assert lonely.value() == 0


def test_test_pulse_timer():
    rig = Rig()
    assert rig.send("TEST 5") == ["OK TEST 5"]
    timer = FakeTimer.created[-1]
    assert timer.period == 200 and timer.active
    rig.fw._test_out = FakePin()
    timer.callback(timer)
    assert rig.fw._test_out.history == [1, 0]
    rig.send("TEST 0")
    assert not timer.active
