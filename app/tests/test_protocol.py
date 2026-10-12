import pytest

from laser_counter import protocol as p


def test_parse_event():
    assert p.parse_line("EVT count=12 t=345678 counted=1\n") == p.Event(12, 345678, True)
    assert p.parse_line("EVT count=12 t=345678 counted=0") == p.Event(12, 345678, False)


def test_parse_status_with_readback():
    status = p.parse_line("STAT running=1 count=7 thr=-400 hold=1000 t=99 bias=1500.3 thr_meas=-398.9")
    assert status == p.Status(True, 7, -400, 1000, 99, 1500.3, -398.9)


def test_parse_status_without_readback_and_with_unknown_fields():
    status = p.parse_line("STAT running=0 count=0 thr=-250 hold=10 t=5 bias=nan future_field=3")
    assert status == p.Status(False, 0, -250, 10, 5, None, None)


def test_parse_replies():
    assert p.parse_line("OK START") == p.Ack("START")
    assert p.parse_line("ERR threshold must be -1400..-5 mV") == p.Error("threshold must be -1400..-5 mV")
    assert p.parse_line("ID laser-counter fw=0.1.0") == p.Ident("laser-counter", "0.1.0")


@pytest.mark.parametrize(
    "line",
    ["", "MicroPython v1.24.0 on 2024-10-25; Raspberry Pi Pico", "EVT count=1", "STAT running=1 count=x", "EVT 1 2 3"],
)
def test_parse_rejects_junk(line):
    with pytest.raises(p.ProtocolError):
        p.parse_line(line)


def test_format_round_trips():
    event = p.Event(3, 1_000_001, True)
    status = p.Status(False, 3, -400, 1000, 2_000_000, 1500.0, -399.5)
    assert p.parse_line(p.format_event(event)) == event
    assert p.parse_line(p.format_status(status)) == status


def test_command_ranges():
    assert p.cmd_threshold(-400) == "THR -400"
    assert p.cmd_holdoff(1000) == "HOLD 1000"
    for bad in (-1401, -4, 0, 100):
        with pytest.raises(ValueError):
            p.cmd_threshold(bad)
    for bad in (9, 1_000_001):
        with pytest.raises(ValueError):
            p.cmd_holdoff(bad)
