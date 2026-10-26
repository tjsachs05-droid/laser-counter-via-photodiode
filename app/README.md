# Laser Shot Counter app

Desktop app for the counter box. It shows the live shot count and shots per second, has Start/Pause and
Reset buttons, and sets the trigger threshold. Talks to the box over USB serial (see
[docs/protocol.md](../docs/protocol.md)), or to a built-in simulator so you can try it with no hardware.

![Running, light theme](../docs/app-light.png)

## Run it

From the repo folder (Windows, Python 3.10+):

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e "app[dev]"
```

```bash
.venv/Scripts/python -m laser_counter --simulate
```

Without `--simulate` it reconnects to the last box used (or the only Pico plugged in). You can also pick
the device in the bottom-right corner, or pass `--port COM5`.

## Controls

| Control | What it does |
|---|---|
| **Start / Pause** (Space) | Start or pause adding shots to the count. While paused the box still detects shots, and a banner reminds you they aren't being counted. |
| **Reset…** (R) | Set the count to 0, after a confirmation |
| **Threshold** | A shot counts when the photodiode signal dips below this, e.g. −400 mV (the same as the PI-MAX4 trigger). The box's own measurement is shown next to it. |
| **Holdoff** | Dead time after each shot, so ringing can't be counted twice. Default 1 ms. |
| **trigger** dot | Flashes on every detected shot |
| **◐** | Light / dark theme |

Settings (threshold, holdoff, last device, theme) are remembered between runs.

## Make the .exe (for PCs without Python)

```bash
.venv/Scripts/python -m pip install -e "app[dev]"
```

```bash
.venv/Scripts/python app/build_exe.py
```

This produces **`dist/LaserShotCounter.exe`** (~37 MB): one file with Python, Qt and the app inside. Copy it to any
64-bit Windows 10/11 PC (USB stick, network share) and double-click it. Nothing needs installing.

- The first launch takes a few seconds while it unpacks itself.
- Windows may show *"Windows protected your PC"* because the file isn't code-signed. Click **More info → Run anyway**.
  On a managed lab PC, IT may need to allow it.
- Settings (threshold, holdoff, last device, theme) are saved per Windows user on each PC.
- `LaserShotCounter.exe --simulate` runs it with the pretend laser (make a desktop shortcut with that argument).
- Windows only. A Mac or Linux version would need to be built on that system.

Rebuild after any change to the app. The `dist/` and `build/` folders aren't committed to git.

## Tests

```bash
.venv/Scripts/python -m pytest app
```
