"""Entry point for the packaged .exe. PyInstaller needs a plain script, not the package's __main__."""

import sys

from laser_counter.__main__ import main

sys.exit(main())
