# Phase 0: Scope the photodiode signal

**Goal:** measure the real pulse once, about 30–45 minutes at the scope, so the counter box's threshold
range, latch and holdoff are set from data instead of guesses. Nothing here changes your camera setup
except temporarily adding a BNC tee.

Fill in the [results table](#results) as you go. Scope screenshots (USB stick or phone photo) are just as
good; send them over and they can be read off directly.

---

## What you need
- The oscilloscope. 100 MHz or more is ideal; 50 MHz still works for amplitude but will round off the width.
- A BNC tee and one extra BNC cable (any from the lab; the McMaster ones don't need to have arrived)
- The laser at its **normal** settings, with the photodiode in its **normal** position. The pulse height depends on both.
- Optional: a 50 Ω BNC terminator, and the laser's sync/trigger output if it has one

**Safety:** usual laser eyewear and interlocks. Don't move the photodiode while the beam is live. The
signal is under ~1–2 V, so it's safe for any scope input, including 50 Ω.

---

## Hook-up

**Option A (recommended): camera connected.** This is exactly how the counter box will see the signal.
```
SM05PD2B ─SMA→BNC─ cable ─► [BNC tee on scope CH1] ─► cable ─► PI-MAX4 Trigger In (50 Ω)
                                    │
                              scope CH1 set to 1 MΩ
```

**Option B: camera off or not available.** The line still needs a 50 Ω load, or the pulse stretches out
(from ns to µs) and the measurements mean nothing. If your scope has a 50 Ω input setting, run the cable straight
in and use it. **The TDS1001B (and most basic scopes) can't do this: they're 1 MΩ only.** Instead, keep the tee
and put a **50 Ω BNC terminator** on the tee's free side, in place of the camera.

**Tektronix TDS1001B notes:** DEFAULT SETUP resets the probe to **10X**, so set CH1 MENU → Probe → **1X** again
afterward. There are no measurement statistics, so use DISPLAY → Persist → Infinite and the cursors to read the
weakest and strongest shots. Use ACQUIRE → **Peak Detect** so narrow pulses aren't missed at slow sweep speeds.
Screenshots: insert a USB stick and press PRINT (the green SAVE light means PRINT saves an image).

⚠ **Never use the tee and the camera with the scope set to 50 Ω.** Two 50 Ω loads cut the signal to 2/3,
the camera may miss triggers, and the numbers will be wrong.

---

## Scope settings to start from

| Setting | Value | Why |
|---|---|---|
| CH1 input | 1 MΩ (Option A) or 50 Ω (Option B), **DC** coupling | |
| CH1 probe / attenuation | **1×** | It's a cable, not a 10× probe. At 10× every reading is 10× too big. |
| Bandwidth limit | **Off** | A 20 MHz limit shrinks and stretches a ns pulse |
| Vertical | 200 mV/div, baseline about 2 divisions above center | Pulse goes negative |
| Horizontal | 50 ns/div, trigger point ~20% from the left | |
| Trigger | Edge, CH1, **falling**, level **−100 mV**, mode **Normal** | Normal = screen only updates on real pulses |

---

## Steps

### 1. Find the pulse
Fire the laser at its normal rep rate. You should see a sharp negative dip. Adjust the vertical scale so
the dip fills most of the screen.
- [ ] Polarity confirmed negative?

### 2. Peak height: the most important number
Turn on the **Min** (sometimes "Vmin" or "Minimum") measurement with **statistics** on. Let it run for at
least **200 shots**. Turning on persistence (infinite) shows the spread of shots as an envelope.
- [ ] Record the Min statistics: **mean, and the full spread** (least negative = weakest shot, most negative = strongest)
- [ ] Screenshot with persistence on

### 3. Pulse width
Zoom to 10–20 ns/div.
- [ ] **−Width** measurement (negative pulse width at 50% of its height)
- [ ] **Width below −0.4 V:** put a horizontal cursor at −0.4 V, then vertical cursors at the two points where the
      pulse crosses it, and read Δt. Use **Single** to freeze one typical shot, then one of the weakest shots you can catch.
- [ ] Optional: fall time (90%→10%)

### 4. Tail and ringing
Zoom out step by step: 200 ns/div, then 2 µs/div, then 50 µs/div.
- [ ] Does the signal **dip below −0.4 V again** after the main pulse (reflections, ringing)? If so, how long after, and how deep?
- [ ] Largest **positive** overshoot after the pulse
- [ ] How long until it's back at baseline?

### 5. Rep rate
Set 20–100 ms/div, or use the **Frequency** measurement.
- [ ] Shots per second, and whether it matches the laser setting

### 6. Baseline noise (laser idle)
Laser **not** firing, trigger mode **Auto**, 20 mV/div, 1 µs/div.
- [ ] Peak-to-peak noise
- [ ] Baseline offset from 0 V, with room lights on and off

### 7. EMI test (beam blocked, laser firing)
Block the beam with your normal lab procedure (shutter / beam block) while the laser keeps firing.
Trigger **Normal**, falling, at **−50 mV**, then try **−20 mV**.
- [ ] Any triggers at all? If yes, the largest spike (Min) and what it looks like (usually fast up-down ringing)
- [ ] Optional: if the laser has a **sync/trigger output**, put it on CH2 and trigger from CH2. You'll then see what CH1 does at the exact
      moment of firing, even when nothing crosses the threshold.

### 8. Optional: camera margin
- [ ] Over ~100 shots, does the camera trigger on every one? (frame count, or its trigger indicator)

---

## Results

| # | Measurement | Value |
|---|---|---|
| | Scope model / bandwidth | |
| | Hook-up used (A or B) | |
| | Laser model, settings | |
| 2 | Peak (Min): weakest / mean / strongest, over N shots | |
| 3 | −Width (50%) | |
| 3 | Width below −0.4 V (typical shot / weak shot) | |
| 3 | Fall time (optional) | |
| 4 | Secondary dips below −0.4 V? (delay, depth) | |
| 4 | Max positive overshoot; time back to baseline | |
| 5 | Rep rate | |
| 6 | Baseline noise p-p; offset (lights on / off) | |
| 7 | EMI with beam blocked: triggers? largest spike | |
| 8 | Camera triggered on every shot? | |

---

## What each number decides

| Measurement | Decides | Watch for |
|---|---|---|
| Weakest peak | Default threshold, and how much margin the camera has | If weak shots are within ~0.1 V of −0.4 V, the camera may already miss some |
| Width below −0.4 V | Whether the latch chip is fast enough (needs ≥ 3.3 ns) | Anything under ~4 ns, flag it |
| Strongest peak | Input clamp behavior | Above ~−1.8 V gets clamped (harmless). Above −1.4 V is past the threshold range, but you'd never set it that high. |
| Secondary dips / ringing | Holdoff default (planned 1 ms) | Dips below −0.4 V more than 1 ms after the shot |
| Rep rate | Holdoff upper limit, simulator default | |
| Noise and EMI | Lowest threshold that's safe to use | EMI spikes approaching −0.4 V |
