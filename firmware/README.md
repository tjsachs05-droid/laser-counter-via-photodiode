# Counter box firmware (Raspberry Pi Pico, MicroPython)

`main.py` is the whole firmware. It counts the shots the latch catches, timestamps them, re-arms the latch
after the holdoff, sets the threshold through the DAC, and talks to the app over USB using
[docs/protocol.md](../docs/protocol.md). It's tested on the PC against a simulated Pico
(`.venv/Scripts/python -m pytest firmware`).

## Phase 2: bench test with only the Pico

You need: a Pico H, the USB **data** cable, and **one jumper wire** (female–female is easiest; a bare wire
wrapped tightly around two header pins also works). No soldering. Run all commands from the project folder.

### 1. Put MicroPython on the Pico (one time)
1. Download the latest **stable** `.uf2` for the **Raspberry Pi Pico (RPI_PICO)**, not the Pico W or Pico 2, from
   <https://micropython.org/download/RPI_PICO/>.
2. Hold the **BOOTSEL** button on the Pico while plugging it into the PC, then let go. A drive called **RPI-RP2** appears.
3. Drag the `.uf2` file onto that drive. The drive disappears and the Pico restarts running MicroPython.

### 2. Copy the firmware onto it
```bash
.venv/Scripts/python -m mpremote cp firmware/main.py :main.py
```
```bash
.venv/Scripts/python -m mpremote reset
```
The green LED on the Pico blinks **three times**: the firmware is running. It runs on its own every time the
Pico powers up from now on.

### 3. Talk to it directly
Find the Pico's port name (something like `COM5`):
```bash
.venv/Scripts/python -m serial.tools.list_ports
```
Open a simple serial terminal (replace COM5):
```bash
.venv/Scripts/python -m serial.tools.miniterm --echo --eol LF COM5 115200
```
You'll see a `STAT …` line every second. Type these, pressing Enter after each:
- `ID?` → `ID laser-counter fw=0.1.0`
- `STATUS?` → `STAT running=0 count=0 thr=-400 hold=1000 t=… dac=0`. `dac=0` is expected, since the DAC board isn't connected yet.
- `TEST 5` → `OK TEST 5`. The Pico now outputs a short test pulse 5 times a second on **GP11**.

### 4. Feed the test pulses into the input
Hold the Pico with the USB connector pointing up and the chip side facing you. The **left** column of pins
is 1–20 from top to bottom.

| Connect | Pin | Position |
|---|---|---|
| **GP11** (test pulse out) | **pin 15** | 15th pin on the left column, same edge as GP2 |
| **GP2** (counter input) | **pin 4** | 4th from the top on the left; pin 3 just above it is GND, so skip it |

Jumper pin 15 to pin 4. In the terminal:
- `EVT count=0 t=… counted=0` lines appear 5 times a second, because the box starts **paused**. The LED flickers with each one.
- `START` → the count climbs: `EVT count=1 … counted=1`, `count=2`, …
- `PAUSE` → the count stops, but `EVT … counted=0` lines keep coming
- `RESET` → the count goes back to 0

Quit the terminal with **Ctrl+]**. Only one program can use the port at a time.

### 5. Try it with the app
```bash
.venv/Scripts/python -m laser_counter
```
The app finds the Pico on its own. Check that:
- the top right shows the port and **firmware 0.1.0**
- **shots/s reads 5.0**, and the trigger dot flashes
- **Start**, **Pause** and **Reset…** behave like the terminal commands
- the bottom shows *"Counter box: DAC not found…"* when it connects or the threshold changes. That's normal until the DAC board is wired up in Phase 3.

The test pulses keep running until you send `TEST 0` or unplug the Pico. Remove the jumper when you're done.

**Bench mode:** if the GP11–GP2 wire is already connected when the Pico powers up, the firmware detects it and starts
5 Hz test pulses by itself (it prints `OK TEST 5`). That way the app alone is enough to test, with no terminal needed.
In the finished box GP11 is never connected, so this can't happen there.

## Testing on a computer without Python
Use **Thonny** (thonny.org; the Windows installer can install "for me only", which needs no admin rights). It can install
MicroPython (Tools → Options → Interpreter → *Install or update MicroPython*), copy `main.py` onto the Pico
(File → Save as → Raspberry Pi Pico), and act as the terminal (Run, then type commands in its Shell). For the app,
copy `dist/LaserShotCounter.exe` across. **Close Thonny before starting the app**, since only one program can use the port.

## Updating the firmware later
Close the app (it holds the port), then repeat step 2. If mpremote can't connect, unplug and replug the Pico and try again.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| No new port appears | Charge-only USB cable, or MicroPython isn't installed yet (step 1) |
| "could not open port" / "access denied" | The app or a terminal already has the port open |
| No `EVT` lines with the jumper on | Jumper on the wrong pins (count again from the top-left), or `TEST 5` not sent |
| LED never blinked three times | `main.py` didn't copy. Run step 2 again and look for errors. |
