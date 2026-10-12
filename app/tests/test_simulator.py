from laser_counter import protocol as p
from laser_counter.simulator import SimulatedFirmware


def make(clock, rep_rate_hz: float = 10, **kwargs) -> SimulatedFirmware:
    kwargs.setdefault("weak_shot_fraction", 0.0)
    return SimulatedFirmware(rep_rate_hz=rep_rate_hz, clock_us=clock, seed=1, **kwargs)


def events(lines):
    return [m for m in map(p.parse_line, lines) if isinstance(m, p.Event)]


def run(fw, clock, seconds):
    clock.advance(seconds)
    return fw.poll()


def test_boots_paused_but_still_reports_pulses(clock):
    fw = make(clock)
    seen = events(run(fw, clock, 1.0))
    assert len(seen) == 10
    assert all(not e.counted and e.count == 0 for e in seen)


def test_start_pause_reset(clock):
    fw = make(clock)
    assert fw.handle("START")[0] == "OK START"
    assert events(run(fw, clock, 1.0))[-1].count == 10
    fw.handle("PAUSE")
    assert events(run(fw, clock, 1.0))[-1].count == 10
    reply = fw.handle("RESET")
    assert p.parse_line(reply[1]).count == 0
    assert fw.running is False


def test_threshold_below_the_pulses_detects_nothing(clock):
    fw = make(clock)
    assert fw.handle("THR -700")[0] == "OK THR -700"
    assert events(run(fw, clock, 1.0)) == []


def test_weak_shots_only_count_with_a_shallow_threshold(clock):
    fw = make(clock, weak_shot_fraction=1.0, weak_mv=-150)
    assert events(run(fw, clock, 1.0)) == []
    fw.handle("THR -100")
    assert len(events(run(fw, clock, 1.0))) == 10


def test_holdoff_longer_than_the_period_skips_shots(clock):
    fw = make(clock)
    fw.handle("HOLD 150000")
    assert len(events(run(fw, clock, 2.0))) == 10


def test_heartbeat_every_second(clock):
    fw = make(clock, rep_rate_hz=0)
    stats = [m for m in map(p.parse_line, run(fw, clock, 1.0)) if isinstance(m, p.Status)]
    assert len(stats) == 1


def test_bad_commands(clock):
    fw = make(clock)
    assert fw.handle("THR 50")[0].startswith("ERR")
    assert fw.handle("THR abc")[0].startswith("ERR")
    assert fw.handle("HOLD 5")[0].startswith("ERR")
    assert fw.handle("FIRE")[0].startswith("ERR")
    assert p.parse_line(fw.handle("ID?")[0]) == p.Ident("laser-counter", "sim-0.1.0")
