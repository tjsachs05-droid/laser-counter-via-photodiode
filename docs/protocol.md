# Serial protocol: app ↔ counter box

The Pico shows up as a USB serial port (CDC). Baud rate doesn't matter over USB CDC; the app opens it at
115200. Every message is one line of plain ASCII ending in `\n`, so you can debug the box with any serial
terminal (PuTTY, Thonny, `python -m serial.tools.miniterm COM5`).

## App → box (commands)

| Command | Meaning | Reply |
|---|---|---|
| `ID?` | Identify | `ID laser-counter fw=<version>` |
| `STATUS?` | Report state now | `STAT …` |
| `START` | Start or resume adding pulses to the count | `OK START`, then `STAT …` |
| `PAUSE` | Stop adding pulses to the count (pulses are still detected and reported) | `OK PAUSE`, then `STAT …` |
| `RESET` | Set the count to 0. Running/paused state is unchanged. | `OK RESET`, then `STAT …` |
| `THR <mV>` | Trigger threshold, integer mV relative to the 0 V baseline, from **-1400 to -5** | `OK THR <mV>`, then `STAT …` |
| `HOLD <µs>` | Holdoff (dead time) after each detected pulse, integer µs, from **10 to 1000000** | `OK HOLD <µs>`, then `STAT …` |

Anything else gets `ERR <message>`.

## Box → app

### `EVT`: one per detected pulse
```
EVT count=1234 t=98765432 counted=1
```
| Field | Meaning |
|---|---|
| `count` | Count **after** this pulse |
| `t` | Box time of the pulse in µs since power-up. Never wraps, and only goes down when the box reboots. |
| `counted` | `1` if the pulse was added to the count (running), `0` if it was detected while paused |

### `STAT`: state snapshot
Sent once per second, and right after every command.
```
STAT running=1 count=1234 thr=-400 hold=1000 t=98765432 bias=1500.3 thr_meas=-398.9
```
| Field | Meaning |
|---|---|
| `running` | `1` = counting, `0` = paused |
| `count` | Current count |
| `thr` | Threshold setting, mV |
| `hold` | Holdoff setting, µs |
| `t` | Box time now, µs since power-up |
| `bias` | *(optional)* Measured bias voltage, mV (should be ≈ 1500) |
| `thr_meas` | *(optional)* Measured threshold relative to bias, mV (should be ≈ `thr`) |

Readers must ignore fields they don't recognize, so fields can be added later without breaking anything.

### Other
- `OK <command>`: command accepted
- `ERR <message>`: command rejected, with a human-readable reason
- Any other line (MicroPython boot banner, tracebacks) is ignored by the app

## Behavior the app relies on
- The box owns the count. The app never counts on its own; it displays what the box reports.
- The box powers up **paused** with count 0.
- Pulses are detected (and `EVT` is sent) whether running or paused.
- Within one holdoff after a detected pulse, further edges are ignored: no `EVT`, no count.
