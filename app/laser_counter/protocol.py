"""Line protocol between the app and the counter box. The spec is docs/protocol.md."""

from __future__ import annotations

from dataclasses import dataclass

THR_MIN_MV = -1400
THR_MAX_MV = -5
HOLD_MIN_US = 10
HOLD_MAX_US = 1_000_000

START = "START"
PAUSE = "PAUSE"
RESET = "RESET"
STATUS_QUERY = "STATUS?"
ID_QUERY = "ID?"


@dataclass(frozen=True)
class Event:
    """One detected pulse."""

    count: int
    t_us: int
    counted: bool


@dataclass(frozen=True)
class Status:
    running: bool
    count: int
    thr_mv: int
    hold_us: int
    t_us: int
    bias_mv: float | None = None
    thr_meas_mv: float | None = None


@dataclass(frozen=True)
class Ack:
    command: str


@dataclass(frozen=True)
class Error:
    message: str


@dataclass(frozen=True)
class Ident:
    name: str
    firmware: str


Message = Event | Status | Ack | Error | Ident


class ProtocolError(ValueError):
    pass


def _fields(tokens: list[str]) -> dict[str, str]:
    fields = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep:
            raise ProtocolError(f"expected key=value, got {token!r}")
        fields[key] = value
    return fields


def _optional_float(value: str | None) -> float | None:
    if value is None or value.lower() == "nan":
        return None
    return float(value)


def parse_line(line: str) -> Message:
    """Parse one line from the box. Raises ProtocolError for anything unrecognized."""
    line = line.strip()
    kind, _, rest = line.partition(" ")
    try:
        if kind == "EVT":
            f = _fields(rest.split())
            return Event(count=int(f["count"]), t_us=int(f["t"]), counted=f["counted"] == "1")
        if kind == "STAT":
            f = _fields(rest.split())
            return Status(
                running=f["running"] == "1",
                count=int(f["count"]),
                thr_mv=int(f["thr"]),
                hold_us=int(f["hold"]),
                t_us=int(f["t"]),
                bias_mv=_optional_float(f.get("bias")),
                thr_meas_mv=_optional_float(f.get("thr_meas")),
            )
        if kind == "OK":
            return Ack(rest.strip())
        if kind == "ERR":
            return Error(rest.strip())
        if kind == "ID":
            name, _, fw = rest.partition(" ")
            return Ident(name=name, firmware=_fields(fw.split()).get("fw", ""))
    except (KeyError, ValueError) as exc:
        raise ProtocolError(f"malformed {kind} line: {line!r}") from exc
    raise ProtocolError(f"unrecognized line: {line!r}")


def cmd_threshold(mv: int) -> str:
    if not THR_MIN_MV <= mv <= THR_MAX_MV:
        raise ValueError(f"threshold must be {THR_MIN_MV}..{THR_MAX_MV} mV, got {mv}")
    return f"THR {mv}"


def cmd_holdoff(us: int) -> str:
    if not HOLD_MIN_US <= us <= HOLD_MAX_US:
        raise ValueError(f"holdoff must be {HOLD_MIN_US}..{HOLD_MAX_US} µs, got {us}")
    return f"HOLD {us}"


def format_event(event: Event) -> str:
    return f"EVT count={event.count} t={event.t_us} counted={int(event.counted)}"


def format_status(status: Status) -> str:
    line = (
        f"STAT running={int(status.running)} count={status.count} thr={status.thr_mv}"
        f" hold={status.hold_us} t={status.t_us}"
    )
    if status.bias_mv is not None:
        line += f" bias={status.bias_mv:.1f}"
    if status.thr_meas_mv is not None:
        line += f" thr_meas={status.thr_meas_mv:.1f}"
    return line
