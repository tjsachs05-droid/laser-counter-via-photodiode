# Laser Ablation Counter — Project Plan

Goal: count laser ablation shots from a photodiode watching the beam. The app shows the **live count**
and **live shots per second**, has **Start/Pause** and **Reset** buttons, and lets you **adjust the
trigger threshold**. The photodiode keeps triggering the PI-MAX4 exactly as it does today, and counting
does not require the camera to be on.

Ordering list with part numbers and sources: **[BOM.md](BOM.md)**

---

## 1. What we know about the signal

| Item | Value | Source |
|---|---|---|
| Photodiode | Thorlabs **SM05PD2B**: unbiased Si, 200–1100 nm, ~1 ns rise, SMA output, **anode grounded** | Thorlabs / third-party spec listing |
| Polarity | **Negative-going pulse.** Anode grounded means the signal pin (cathode) swings negative. | Confirmed by you |
| Load | PI-MAX4 trigger input, **50 Ω**, falling edge, threshold ≈ **−0.4 V** | Confirmed by you |
| Implied amplitude | At least ~−0.4 V into 50 Ω, probably under ~−1 V (an unbiased photodiode saturates around its forward voltage) | Inferred; confirm on a scope (Phase 0) |
| Pulse width | ns-scale (laser pulse plus photodiode tail) | Confirm on a scope |

### What this changes compared with the first draft
1. **No high-voltage protection or input divider.** The signal is under ~1 V. Light Schottky clamps are kept only for ESD and accidents.
2. **Negative pulses need a level shift.** A single-supply 3.3 V comparator can't take inputs below
   −0.2 V. So the input is **AC-coupled and re-biased to +1.5 V**: a −0.4 V pulse arrives at the
   comparator as a dip from 1.5 V to 1.1 V. AC coupling also rejects slow changes such as room lights
   on the photodiode.
3. **Threshold and bias both come from one DAC chip** (MCP4728: four channels, internal 2.048 V
   reference). Channel A = 1.500 V bias, channel B = 1.500 V − |threshold|. Both share one reference,
   so the threshold doesn't drift with the Pico's noisy 3.3 V rail. Resolution is 0.5 mV, range 0 to
   about −1.4 V. The app shows it as a negative number (e.g. **−400 mV**), matching how the camera's
   threshold is set.
4. **Put the BNC tee on the counter box, not at the camera.** A 50 Ω-terminated camera input plus a
   cable dangling off a tee forms a stub. Until the reflection returns from the open end of the stub,
   the camera sees only **2/3 of the pulse**. A 1 ft stub gives ~3 ns of reduced amplitude. With a
   −0.4 V camera threshold and a pulse that may be only a little larger, that could add a few ns of
   trigger jitter or even miss shots. With the tee plugged directly into the box, the stub is only about
   2 cm, so the effect is negligible.
5. **Faster latch: SN74LVC74A instead of 74AC74.** At 3.3 V the 74AC74 is only guaranteed to catch
   pulses ≥ 7 ns. The LVC74A catches pulses ≥ 3.3 ns, which covers even ~5 ns Nd:YAG pulses. It comes
   in SOIC-14, so it sits on a $3.49 DIP adapter just like the comparator.

---

## 2. Signal chain

```
 SM05PD2B ─SMA→BNC─ [existing cable] ─► BNC TEE ─► [new 3 ft RG-58] ─► PI-MAX4 Trigger In
                                      (plugged     (50 Ω, falling edge, −0.4 V — unchanged)
                                       straight
                                       into box)
                                          │ ≈2 cm, no stub
                                          ▼
 ┌──────────────────────────── COUNTER BOX (aluminum) ─────────────────────────────┐
 │                                                                                  │
 │  BNC ─┬─ 100k ─ GND               MCP4728 ch A = 1.500 V (bias)                  │
 │       │                                   │                                      │
 │       └─ 10 nF C0G ──┬──── 10k ───────────┘                                      │
 │                      │                                                           │
 │                     100 Ω                                                        │
 │                      ├─ BAT41 → 3V3   (clamp high)                               │
 │                      ├─ BAT41 ← GND   (clamp low)                                │
 │                      └──► TLV3501 IN−                                            │
 │   MCP4728 ch B ─ 1k ─┬──► TLV3501 IN+   (threshold = 1.500 V − |Vthr|)           │
 │                    100 nF                                                        │
 │                      ┴                                                           │
 │   TLV3501 OUT ──► 74LVC74 CLK   (D = 3V3, PRE = 3V3)                             │
 │   74LVC74 Q   ──► Pico GP2   (rising edge = one shot)                            │
 │   74LVC74 CLR ◄── Pico GP3   (Pico re-arms the latch after the holdoff)          │
 │   MCP4728 SDA/SCL ◄─► Pico GP4/GP5 (I²C)                                         │
 │   Pico GP26/27 (ADC) ◄── DAC ch B / ch A   (readback, sanity check)              │
 │   Pico 3V3(OUT) powers the comparator, latch, and DAC (< 5 mA total)            │
 │                                                                                  │
 └─────────────────────────────────── USB ──► lab PC (display app) ─────────────────┘
```

How it works: the pulse dips the comparator input below the threshold, and the comparator output goes
high for a few ns. The latch catches that edge and holds it, the Pico counts it and timestamps it in
µs, then after the holdoff (default 1 ms) it clears the latch. Ringing or EMI during the holdoff can't
double count.

The camera's signal is unaffected: the tap adds ~10 kΩ in parallel with the camera's 50 Ω (< 1%
loading). **Note:** the new 3 ft cable adds ~4.6 ns of delay to the camera trigger (RG-58 ≈ 1.5 ns/ft).
Re-check the PI-MAX4 gate delay after rewiring if your timing is referenced to the laser.

---

## 3. Requirements

**v1 (must have)**
- Live **count**, large and readable from across the lab
- Live **shots per second**, computed from the Pico's µs timestamps (not PC arrival times, which jitter)
- **Start/Pause** toggle and **Reset** (with confirm) buttons, plus keyboard shortcuts (Space, R)
- **Adjustable threshold** in mV (negative), default **−400 mV** so it matches the camera
  (count = shots that would trigger the camera), saved between sessions
- No missed or extra counts (validated, see Phase 4). Camera triggering unchanged.

**Later (optional)**: target-count alert, per-shot CSV log, threshold-plateau scan, standalone box display.

---

## 4. Key design decisions

1. **The Pico owns the count.** If the app crashes or the USB cable is bumped, no shots are lost. The app re-syncs on reconnect.
2. **Paused means "don't add to the count," not "stop listening."** Pulses are still detected while
   paused, which drives a "trigger seen" indicator, and the app shows a warning banner if shots arrive
   while paused, so a forgotten Start is obvious.
3. **The box boots paused, with count 0.** Counting starts only when you press Start.
4. **Holdoff** (dead time) is configurable, default 1 ms. That's fine up to ~500 Hz.
5. **Plain-text serial protocol**, debuggable from any serial terminal. Full spec: [docs/protocol.md](docs/protocol.md).

   | PC → box | Meaning |
   |---|---|
   | `START` / `PAUSE` / `RESET` | control counting |
   | `THR -400` | threshold = −400 mV |
   | `HOLD 1000` | holdoff = 1000 µs |
   | `STATUS?` / `ID?` | query |

   | Box → PC | Meaning |
   |---|---|
   | `EVT count=… t=… counted=0/1` | one per detected pulse |
   | `STAT running=… count=… thr=… hold=… t=… bias=… thr_meas=…` | state, at 1 Hz and after every command |
   | `OK <cmd>` / `ERR <msg>` | command replies |

6. **App: Python + PySide6 (Qt)**, packaged as a single `.exe`. It includes a **simulator** so the UI can be built and tested before the hardware arrives.

### Display layout (v1)
```
┌──────────────────────────────────────────────────────┐
│  ● RUNNING                          ▲ trigger   USB ✓ │
│                                                      │
│                    12,438                            │   ← huge, monospaced digits
│                    shots                             │
│                                                      │
│                  10.0 shots/s                        │   ← large, secondary
│                                                      │
│   [  ❚❚  Pause  ]        [  ↺  Reset…  ]             │
│                                                      │
│   Threshold  [ −400 ] mV   ───────●──────            │
└──────────────────────────────────────────────────────┘
```
Neutral background, one accent color for RUNNING (green) and PAUSED (amber), no clutter, light and dark themes.

---

## 5. Repo layout

```
laser-counter-via-photodiode/
├── README.md
├── PLAN.md                  ← this file
├── BOM.md                   parts list + where to buy
├── docs/
│   ├── hardware.md          schematic, wiring, build notes
│   └── protocol.md          serial protocol spec
├── hardware/                KiCad schematic, end-cap drill template
├── firmware/
│   └── main.py              MicroPython for the Pico
└── app/
    ├── pyproject.toml
    ├── laser_counter/
    │   ├── __main__.py
    │   ├── device.py        SerialDevice + SimulatedDevice (same interface)
    │   ├── ui.py
    │   └── theme.qss
    └── tests/
```

---

## 6. Phases

### Phase 0: Scope the real signal (≈30 min, can overlap with ordering)
With the camera connected as normal, scope the photodiode line at the camera end (50 Ω):
- [ ] Peak amplitude, min and max over ~100 shots. How much margin is there beyond −0.4 V?
- [ ] Pulse width at the −0.4 V level, and tail length
- [ ] Laser model and rep rate (sets the default holdoff)
- [ ] With the beam blocked and the laser firing: any EMI spikes on the line?

### Phase 1: App and simulator ✅ done (see [app/README.md](app/README.md))
- [x] `docs/protocol.md`
- [x] `device.py`: serial and simulator transports behind one interface; `simulator.py` mimics the firmware
- [x] `ui.py`: count, shots/s, Start/Pause, Reset with confirm, threshold + holdoff, trigger indicator, paused-but-seeing-pulses banner, light/dark
- [x] Settings persistence and tests (34, including an end-to-end UI test against the simulator)

### Phase 2: Firmware (Pico on its own)
- [ ] MicroPython: latch IRQ → timestamp → count → holdoff → clear latch
- [ ] MCP4728 driver (bias + threshold), ADC readback, command parser, 1 Hz heartbeat
- [ ] Test with the real app over USB

### Phase 3: Front end (bench)
- [ ] Solder the TLV3501 and 74LVC74A onto their DIP adapters, then build on the perma-proto board with short leads and a solid ground
- [ ] Test with a pulse/function generator: negative 20 ns pulses at −0.2, −0.4, −0.6 V. The count should switch on and off cleanly as the threshold crosses the pulse height.
- [ ] Mount in the enclosure: BNC jack in one end cap, USB in the other

### Phase 4: Lab validation
- [ ] Wire as in §2. Re-check the PI-MAX4 gate delay (+~4.6 ns of cable).
- [ ] **Camera unaffected:** it triggers on every shot with the box connected
- [ ] **Accuracy:** 1,000 and 10,000 shots vs. the laser's own counter → **0 missed, 0 extra**
- [ ] **Plateau:** sweep the threshold from −50 to −800 mV and confirm a flat region where count = shots. Pick the default inside it.
- [ ] **Beam blocked:** count stays at 0 (no EMI counts)
- [ ] Pause, resume, and reset mid-run behave correctly

### Phase 5: Package
- [ ] PyInstaller `.exe` and a one-page user guide
- [ ] Optional extras from §3

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Pulse barely exceeds −0.4 V, so the camera triggers marginally | Not caused by the counter, but Phase 0 will show it. The counter can run a lower threshold than the camera if you want to count every shot regardless. |
| Laser discharge EMI | Aluminum box, comparator hysteresis (6 mV built in), holdoff, beam-blocked test |
| Ground loop (camera / PC / laser) | Keep the BNC shield bonded to the box. If noisy, add a USB isolator (~$20). |
| Fast comparator oscillates near threshold | Built-in hysteresis, 100 nF decoupling right at the pins, short leads. No solderless breadboard for the final build. |
| Cable added to the camera path shifts trigger timing | Re-zero the gate delay once (Phase 4) |

---

## 8. Remaining questions
1. Laser model and rep rate?
2. Lab PC OS? (Windows assumed)
3. Should the count match "shots that triggered the camera" (threshold = camera's) or "every laser shot" (lower threshold)? Default is the former.
