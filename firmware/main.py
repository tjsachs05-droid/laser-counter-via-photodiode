# Laser shot counter firmware for the Raspberry Pi Pico (MicroPython).
# Serial protocol: docs/protocol.md. Wiring: docs/hardware.md.

import sys
import time
import select
import machine
import micropython
from machine import Pin, I2C, ADC, Timer

try:
    import rp2
except ImportError:  # the PC test suite runs this file without the Pico's PIO module
    rp2 = None

FW_VERSION = "0.2.0"

PIN_Q = 2  # latch output 1Q: goes high when a pulse is detected, stays high until cleared
PIN_CLR = 3  # latch clear 1CLR, active low
PIN_SDA = 4  # I2C0 to the DAC board
PIN_SCL = 5
PIN_TEST = 11  # bench-test pulse output (TEST command); leave unconnected in the box
PIN_SMPS_MODE = 23  # Pico regulator mode: high = PWM, less ripple on 3.3 V
PIN_ADC_BIAS = 26  # readback of DAC channel A
PIN_ADC_THR = 27  # readback of DAC channel B

DAC_ADDR = 0x60
DAC_CH_BIAS = 0
DAC_CH_THR = 1
BIAS_MV = 1500

THR_MIN_MV = -1400
THR_MAX_MV = -5
HOLD_MIN_US = 10
HOLD_MAX_US = 1000000
TEST_MAX_HZ = 1000
STATUS_PERIOD_MS = 1000
LED_ON_MS = 50
TEST_PULSE_US = 20
BENCH_TEST_HZ = 5  # test pulse rate when the GP11-GP2 bench jumper is fitted at power-up
PULSE_MIN_NS = 16  # two PIO cycles at 125 MHz
PULSE_MAX_NS = 1000000
PULSE_DEFAULT_NS = 50
PULSE_MAX_COUNT = 1000000

micropython.alloc_emergency_exception_buf(100)

# Shared with the edge interrupt. The interrupt only sets them; the main loop does the rest.
_pending = False
_pending_ticks = 0


def _on_edge(pin):
    global _pending, _pending_ticks
    if not _pending:
        _pending_ticks = time.ticks_us()
        _pending = True


_test_out = None


def _test_pulse(timer):
    _test_out.value(1)
    time.sleep_us(TEST_PULSE_US)
    _test_out.value(0)


if rp2 is not None:

    @rp2.asm_pio(set_init=rp2.PIO.OUT_HIGH)
    def _neg_pulse():
        # Wait for a width word x, hold the pin low for x + 2 cycles, then high again.
        pull(block)
        mov(x, osr)
        set(pins, 0)
        label("low")
        jmp(x_dec, "low")
        set(pins, 1)


# PULSE generator state, read by its timer interrupt.
_pulse_sm = None
_pulse_x = 0
_pulses_left = 0  # pulses still to send; -1 means no limit


def _pulse_tick(timer):
    global _pulses_left
    if _pulses_left == 0:
        timer.deinit()
        return
    _pulse_sm.put(_pulse_x)
    if _pulses_left > 0:
        _pulses_left -= 1


class Clock:
    """Microseconds since boot that never wrap (time.ticks_us() wraps every ~18 minutes)."""

    def __init__(self):
        self._last = time.ticks_us()
        self._us = 0

    def now(self):
        ticks = time.ticks_us()
        self._us += time.ticks_diff(ticks, self._last)
        self._last = ticks
        return self._us

    def at(self, ticks):
        """Convert a recent ticks_us() reading to microseconds since boot."""
        return self.now() + time.ticks_diff(ticks, self._last)


class Dac:
    """MCP4728 on its internal 2.048 V reference, gain 1: 0.5 mV per step."""

    def __init__(self, i2c):
        self._i2c = i2c
        try:
            self.ok = DAC_ADDR in i2c.scan()
        except OSError:
            self.ok = False

    def set_mv(self, channel, mv):
        code = min(max(round(mv * 2), 0), 4095)
        # Multi-write: 0b01000 DAC1 DAC0 UDAC, then VREF=1 PD=00 G=0 D11..D8, then D7..D0.
        data = bytes((0x40 | (channel << 1), 0x80 | (code >> 8), code & 0xFF))
        try:
            self._i2c.writeto(DAC_ADDR, data)
        except OSError:
            self.ok = False
        return self.ok


def bench_jumper_present(test, q):
    """True if GP11 is wired straight to GP2 (bench-test jumper). Call before the edge interrupt is on.

    In the finished box GP11 is unconnected and Q is held low by the cleared latch, so this is always False there.
    """
    for level in (1, 0, 1, 0):
        test.value(level)
        time.sleep_us(50)
        if q.value() != level:
            test.value(0)
            return False
    return True


def read_mv(adc, samples=16):
    total = 0
    for _ in range(samples):
        total += adc.read_u16()
    return total / samples * 3300 / 65535


def _parse_int(text, low, high):
    try:
        value = int(text)
    except ValueError:
        return None
    return value if low <= value <= high else None


class Box:
    def __init__(self, q, clr, led, dac, adc_bias, adc_thr):
        self.q = q
        self.clr = clr
        self.led = led
        self.dac = dac
        self.adc_bias = adc_bias
        self.adc_thr = adc_thr
        self.clock = Clock()
        self.running = False
        self.count = 0
        self.thr_mv = -400
        self.hold_us = 1000
        self._handled = False
        self._rearm_at = 0
        self._led_off_at = None
        self._next_status = time.ticks_add(time.ticks_ms(), STATUS_PERIOD_MS)
        self._test_timer = None

    def start(self):
        """Hold the latch cleared until the DAC voltages have settled, then start listening."""
        self.clr.value(0)
        self.apply_dac()
        time.sleep_ms(20)
        self.clr.value(1)
        self.q.irq(_on_edge, Pin.IRQ_RISING, hard=True)

    def apply_dac(self):
        if not self.dac.ok:
            return False
        return self.dac.set_mv(DAC_CH_BIAS, BIAS_MV) and self.dac.set_mv(DAC_CH_THR, BIAS_MV + self.thr_mv)

    def status(self):
        line = "STAT running={} count={} thr={} hold={} t={} dac={}".format(
            int(self.running), self.count, self.thr_mv, self.hold_us, self.clock.now(), int(self.dac.ok)
        )
        if self.dac.ok:
            bias = read_mv(self.adc_bias)
            line += " bias={:.1f} thr_meas={:.1f}".format(bias, read_mv(self.adc_thr) - bias)
        return line

    def handle(self, line):
        """Respond to one command line. Returns the lines to send back."""
        line = line.strip()
        if not line:
            return []
        parts = line.split(" ", 1)
        cmd = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd == "ID?":
            return ["ID laser-counter fw=" + FW_VERSION]
        if cmd == "STATUS?":
            return [self.status()]
        if cmd == "START":
            self.running = True
        elif cmd == "PAUSE":
            self.running = False
        elif cmd == "RESET":
            self.count = 0
        elif cmd == "THR":
            value = _parse_int(arg, THR_MIN_MV, THR_MAX_MV)
            if value is None:
                return ["ERR threshold must be {}..{} mV".format(THR_MIN_MV, THR_MAX_MV)]
            self.thr_mv = value
            if not self.apply_dac():
                return ["ERR DAC not found; threshold {} mV saved but not applied".format(value), self.status()]
            return ["OK THR {}".format(value), self.status()]
        elif cmd == "HOLD":
            value = _parse_int(arg, HOLD_MIN_US, HOLD_MAX_US)
            if value is None:
                return ["ERR holdoff must be {}..{} us".format(HOLD_MIN_US, HOLD_MAX_US)]
            self.hold_us = value
            return ["OK HOLD {}".format(value), self.status()]
        elif cmd == "TEST":
            value = _parse_int(arg, 0, TEST_MAX_HZ)
            if value is None:
                return ["ERR test rate must be 0..{} Hz".format(TEST_MAX_HZ)]
            self.set_test(value)
            return ["OK TEST {}".format(value)]
        elif cmd == "PULSE":
            return self._handle_pulse(arg.split())
        else:
            return ["ERR unknown command: " + line]
        return ["OK " + cmd, self.status()]

    def _handle_pulse(self, args):
        usage = "ERR usage: PULSE <0..{} Hz> [{}..{} ns] [count 0..{}]".format(
            TEST_MAX_HZ, PULSE_MIN_NS, PULSE_MAX_NS, PULSE_MAX_COUNT
        )
        if not 1 <= len(args) <= 3:
            return [usage]
        hz = _parse_int(args[0], 0, TEST_MAX_HZ)
        width = _parse_int(args[1], PULSE_MIN_NS, PULSE_MAX_NS) if len(args) > 1 else PULSE_DEFAULT_NS
        count = _parse_int(args[2], 0, PULSE_MAX_COUNT) if len(args) > 2 else 0
        if hz is None or width is None or count is None:
            return [usage]
        if hz and width * hz >= 500000000:
            return ["ERR pulse must be shorter than half the period"]
        if rp2 is None:
            return ["ERR PULSE needs the Pico's PIO"]
        actual = self.set_pulse(hz, width, count)
        return ["OK PULSE {} {} {}".format(hz, actual, count)]

    def _stop_test_output(self, idle_high):
        global _pulse_sm
        if self._test_timer is not None:
            self._test_timer.deinit()
            self._test_timer = None
        if _pulse_sm is not None:
            _pulse_sm.active(0)
            _pulse_sm = None
        Pin(PIN_TEST, Pin.OUT, value=1 if idle_high else 0)  # also takes the pin back from the PIO

    def set_test(self, hz):
        """Positive 20 us pulses on GP11 (idle low), for the GP11-GP2 bench jumper."""
        self._stop_test_output(idle_high=False)
        if hz > 0:
            self._test_timer = Timer(mode=Timer.PERIODIC, period=max(1, round(1000 / hz)), callback=_test_pulse)

    def set_pulse(self, hz, width_ns, count):
        """Negative pulses on GP11 (idle high), for driving the input stage through a divider.

        GP11 stays high when the pulses stop, so stopping can't fake a shot. Returns the actual width in ns.
        """
        global _pulse_sm, _pulse_x, _pulses_left
        self._stop_test_output(idle_high=True)
        if hz == 0:
            return 0
        cycles = max(2, round(width_ns * machine.freq() / 1e9))
        _pulse_x = cycles - 2
        _pulses_left = count if count > 0 else -1
        _pulse_sm = rp2.StateMachine(0, _neg_pulse, freq=machine.freq(), set_base=Pin(PIN_TEST))
        _pulse_sm.active(1)
        self._test_timer = Timer(mode=Timer.PERIODIC, period=max(1, round(1000 / hz)), callback=_pulse_tick)
        return round(cycles * 1e9 / machine.freq())

    def service(self):
        """Run often from the main loop. Returns the lines to send."""
        global _pending
        out = []
        if _pending and not self._handled:
            self._handled = True
            if self.running:
                self.count += 1
            out.append("EVT count={} t={} counted={}".format(self.count, self.clock.at(_pending_ticks), int(self.running)))
            self._rearm_at = time.ticks_add(_pending_ticks, self.hold_us)
            self.led.value(1)
            self._led_off_at = time.ticks_add(time.ticks_ms(), LED_ON_MS)
        if self._handled and time.ticks_diff(time.ticks_us(), self._rearm_at) >= 0:
            self.clr.value(0)
            time.sleep_us(2)
            self.clr.value(1)
            self._handled = False
            _pending = False
        now_ms = time.ticks_ms()
        if self._led_off_at is not None and time.ticks_diff(now_ms, self._led_off_at) >= 0:
            self.led.value(0)
            self._led_off_at = None
        if time.ticks_diff(now_ms, self._next_status) >= 0:
            self._next_status = time.ticks_add(now_ms, STATUS_PERIOD_MS)
            self._catch_missed_edge()
            out.append(self.status())
        return out

    def _catch_missed_edge(self):
        # The latch holds Q high until cleared, so Q high with nothing pending means an edge was missed.
        global _pending, _pending_ticks
        if _pending or not self.q.value():
            return
        state = machine.disable_irq()
        if not _pending:
            _pending_ticks = time.ticks_us()
            _pending = True
        machine.enable_irq(state)


def main():
    global _test_out
    Pin(PIN_SMPS_MODE, Pin.OUT, value=1)
    _test_out = Pin(PIN_TEST, Pin.OUT, value=0)
    led = Pin("LED", Pin.OUT, value=0)
    for _ in range(3):  # three blinks: firmware is running
        led.value(1)
        time.sleep_ms(80)
        led.value(0)
        time.sleep_ms(80)

    box = Box(
        q=Pin(PIN_Q, Pin.IN, Pin.PULL_DOWN),
        clr=Pin(PIN_CLR, Pin.OUT, value=0),
        led=led,
        dac=Dac(I2C(0, sda=Pin(PIN_SDA), scl=Pin(PIN_SCL), freq=100000)),
        adc_bias=ADC(Pin(PIN_ADC_BIAS)),
        adc_thr=ADC(Pin(PIN_ADC_THR)),
    )
    bench = bench_jumper_present(_test_out, box.q)
    box.start()
    print("ID laser-counter fw=" + FW_VERSION)
    if bench:
        box.set_test(BENCH_TEST_HZ)
        print("OK TEST {}".format(BENCH_TEST_HZ))
    print(box.status())

    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
    buf = ""
    while True:
        while poller.poll(0):
            ch = sys.stdin.read(1)
            if ch in "\r\n":
                for reply in box.handle(buf):
                    print(reply)
                buf = ""
            elif len(buf) < 80:
                buf += ch
        for line in box.service():
            print(line)


if __name__ == "__main__":
    main()
