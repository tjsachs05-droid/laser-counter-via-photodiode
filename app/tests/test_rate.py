import pytest

from laser_counter.rate import RateMeter


def feed(meter: RateMeter, hz: float, seconds: float, start_us: int = 0) -> float:
    """Add pulses at `hz` for `seconds`; returns the host time of the last pulse."""
    n = round(hz * seconds)
    for i in range(n):
        meter.add(start_us + round(i * 1e6 / hz), host_s=i / hz)
    return (n - 1) / hz


def test_no_data_is_unknown():
    assert RateMeter().rate(0.0) is None


def test_single_pulse_is_unknown():
    meter = RateMeter()
    meter.add(1000, host_s=0.0)
    assert meter.rate(0.01) is None


@pytest.mark.parametrize("hz", [1.0, 10.0, 50.0, 200.0])
def test_steady_rate(hz):
    meter = RateMeter()
    last = feed(meter, hz, seconds=10)
    assert meter.rate(last + 0.001) == pytest.approx(hz, rel=1e-6)


def test_drops_to_zero_when_pulses_stop():
    meter = RateMeter(stale_after_s=2.0)
    last = feed(meter, 10, seconds=3)
    assert meter.rate(last + 1.0) == pytest.approx(10)
    assert meter.rate(last + 2.5) == 0.0


def test_slow_laser_is_not_called_stale_between_pulses():
    meter = RateMeter(stale_after_s=2.0)
    last = feed(meter, 0.5, seconds=10)  # one shot every 2 s
    assert meter.rate(last + 2.5) == pytest.approx(0.5)


def test_box_reboot_restarts_the_average():
    meter = RateMeter()
    feed(meter, 10, seconds=2, start_us=50_000_000)
    meter.add(100, host_s=5.0)  # clock went backwards
    assert meter.rate(5.01) is None
