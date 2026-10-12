"""Light and dark styling. Colors only; fonts are set in code so the big count can scale with the window."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).with_name("assets").as_posix()

LIGHT = {
    "bg": "#F6F6F4",
    "field": "#FFFFFF",
    "text": "#161616",
    "muted": "#6E6E6A",
    "faint": "#C4C4BF",
    "border": "#DCDCD8",
    "chip": "#ECECE9",
    "green": "#17804A",
    "green_bg": "#E3F3EA",
    "amber": "#8F5400",
    "amber_bg": "#FBEFD9",
    "primary": "#161616",
    "primary_text": "#FFFFFF",
    "led": "#1FA463",
    "arrows": "light",
}

DARK = {
    "bg": "#111111",
    "field": "#1B1B1A",
    "text": "#F2F2F0",
    "muted": "#9B9B96",
    "faint": "#3E3E3B",
    "border": "#2E2E2C",
    "chip": "#232322",
    "green": "#46D38A",
    "green_bg": "#12301F",
    "amber": "#F4B740",
    "amber_bg": "#33260C",
    "primary": "#F2F2F0",
    "primary_text": "#111111",
    "led": "#46D38A",
    "arrows": "dark",
}

_TEMPLATE = """
QMainWindow, QWidget#root, QStatusBar, QDialog, QMessageBox {{ background: {bg}; }}
QLabel {{ color: {text}; }}
QLabel#muted, QLabel#caption, QLabel#fieldLabel {{ color: {muted}; }}
QLabel#statePill {{ padding: 4px 12px; border-radius: 12px; font-weight: 600; }}
QLabel#statePill[state="running"] {{ color: {green}; background: {green_bg}; }}
QLabel#statePill[state="paused"] {{ color: {amber}; background: {amber_bg}; }}
QLabel#statePill[state="disconnected"] {{ color: {muted}; background: {chip}; }}
QLabel#triggerDot {{ color: {faint}; }}
QLabel#triggerDot[lit="true"] {{ color: {led}; }}
QLabel#banner {{ color: {amber}; background: {amber_bg}; border-radius: 8px; padding: 10px 14px; }}
QStatusBar {{ color: {muted}; }}
QFrame#divider {{ background: {border}; border: none; }}
QPushButton {{
    color: {text}; background: {field}; border: 1px solid {border};
    border-radius: 10px; padding: 10px 24px;
}}
QPushButton:hover {{ border-color: {muted}; }}
QPushButton:disabled {{ color: {faint}; border-color: {border}; }}
QPushButton#primary {{ background: {primary}; color: {primary_text}; border: 1px solid {primary}; }}
QPushButton#primary[kind="pause"] {{ background: {amber_bg}; color: {amber}; border: 1px solid {amber}; }}
QPushButton#primary:disabled {{ background: {chip}; color: {faint}; border-color: {chip}; }}
QPushButton#small {{ padding: 4px 14px; border-radius: 6px; }}
QSpinBox, QDoubleSpinBox, QComboBox {{
    color: {text}; background: {field}; border: 1px solid {border};
    border-radius: 6px; padding: 3px 22px 3px 8px; min-height: 22px;
}}
QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: {faint}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{assets}/chevron-up-{arrows}.svg"); width: 10px; height: 6px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QComboBox::down-arrow {{
    image: url("{assets}/chevron-down-{arrows}.svg"); width: 10px; height: 6px;
}}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }}
QComboBox QAbstractItemView {{
    color: {text}; background: {field}; selection-background-color: {chip}; selection-color: {text};
}}
QToolButton {{ color: {muted}; background: transparent; border: none; padding: 2px 6px; }}
QToolButton:hover {{ color: {text}; }}
"""


def stylesheet(dark: bool) -> str:
    return _TEMPLATE.format(assets=ASSETS, **(DARK if dark else LIGHT))
