"""Build dist/LaserShotCounter.exe: one file that runs on 64-bit Windows 10/11 with nothing installed.

Run from the repo folder:  .venv/Scripts/python app/build_exe.py
"""

import os
from pathlib import Path

import PyInstaller.__main__

APP = Path(__file__).resolve().parent
ROOT = APP.parent

PyInstaller.__main__.run(
    [
        str(APP / "launcher.py"),
        "--name=LaserShotCounter",
        "--onefile",
        "--windowed",
        f"--add-data={APP / 'laser_counter' / 'assets'}{os.pathsep}laser_counter/assets",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build'}",
        f"--specpath={ROOT / 'build'}",
        "--noconfirm",
        "--clean",
    ]
)
