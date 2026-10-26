"""Draws docs/img/board-a.svg and board-b.svg (Perma-Proto half-size layouts) from the placements below.

Run from the repo folder:  .venv/Scripts/python docs/img/make_board_diagrams.py
Coordinates are (column, row). Columns: "-L" "+L" a..e | f..j "+R" "-R"; rows 1..30.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent
P = 22  # hole pitch in px
X0, Y0 = 210, 70  # board origin (top-left of the -L rail, row 0)
COLS = {"-L": 0, "+L": 1, "a": 2.5, "b": 3.5, "c": 4.5, "d": 5.5, "e": 6.5,
        "f": 9.5, "g": 10.5, "h": 11.5, "i": 12.5, "j": 13.5, "+R": 15, "-R": 16}
RED, BLACK, BLUE, GREEN, PURPLE, ORANGE, BROWN = "#D62828", "#222222", "#1D63C9", "#1E8C4E", "#7A3EB1", "#E07A00", "#8C5A2B"


def xy(col, row):
    return X0 + COLS[col] * P, Y0 + row * P


class Svg:
    def __init__(self, title, width=780, height=820):
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            'font-family="Segoe UI, Helvetica, Arial, sans-serif">',
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
            f'<text x="{width / 2}" y="28" font-size="18" font-weight="600" text-anchor="middle" fill="#111">{title}</text>',
        ]

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=11, anchor="start", color="#222", weight="400"):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{color}" '
                 f'font-weight="{weight}" dominant-baseline="middle">{s}</text>')

    def save(self, name):
        self.parts.append("</svg>")
        (OUT / name).write_text("\n".join(self.parts), encoding="utf-8")


def draw_board(svg):
    top, bottom = Y0 + 0.4 * P, Y0 + 30.6 * P
    svg.add(f'<rect x="{X0 - 0.8 * P}" y="{top - 0.4 * P}" width="{17.6 * P}" height="{bottom - top + 0.8 * P}" '
            'rx="8" fill="#F4E9C8" stroke="#C9B27A"/>')
    for rail, color in (("-L", BLUE), ("+L", RED), ("+R", RED), ("-R", BLUE)):
        x = X0 + COLS[rail] * P
        svg.add(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="{color}" stroke-width="7" opacity="0.18"/>')
        svg.text(x, top - 0.9 * P, rail[0], 14, "middle", color, "700")
    for row in range(1, 31):
        y = Y0 + row * P
        for left, right in (("a", "e"), ("f", "j")):
            svg.add(f'<line x1="{xy(left, row)[0]}" y1="{y}" x2="{xy(right, row)[0]}" y2="{y}" stroke="#D9C79A" stroke-width="9" '
                    'stroke-linecap="round"/>')
        for col in COLS:
            x = X0 + COLS[col] * P
            svg.add(f'<circle cx="{x}" cy="{y}" r="3.2" fill="#6B5B3A"/>')
        svg.text(X0 - 1.35 * P, y, str(row), 10, "end", "#7A6A45")
        svg.text(X0 + 17.35 * P, y, str(row), 10, "start", "#7A6A45")
    for col in "abcdefghij":
        svg.text(xy(col, 0)[0], top - 0.9 * P, col, 11, "middle", "#7A6A45")


def wire(svg, points, color, dashed=False, width=3):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (xy(*p) if isinstance(p[0], str) else p for p in points))
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    svg.add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
            f'stroke-linejoin="round"{dash}/>')
    for p in (points[0], points[-1]):
        if isinstance(p[0], str):
            x, y = xy(*p)
            svg.add(f'<circle cx="{x}" cy="{y}" r="4.2" fill="{color}"/>')


def part(svg, a, b, kind, label, color=BROWN, label_dx=0, label_dy=0, dashed=False):
    """A two-lead part between holes a and b, drawn as a body in the middle of the leads."""
    (x1, y1), (x2, y2) = xy(*a), xy(*b)
    wire(svg, [a, b], "#777", dashed=dashed, width=2)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    horizontal = abs(x2 - x1) > abs(y2 - y1)
    w, h = (18, 9) if horizontal else (9, 18)
    if kind == "R":
        svg.add(f'<rect x="{mx - w / 2}" y="{my - h / 2}" width="{w}" height="{h}" rx="3" fill="#E7C38A" stroke="{color}" stroke-width="1.5"/>')
    elif kind == "C":
        svg.add(f'<circle cx="{mx}" cy="{my}" r="7" fill="#7FB3E8" stroke="#1D63C9" stroke-width="1.5"/>')
    elif kind == "D":  # body with a stripe at the cathode end, which is b
        svg.add(f'<rect x="{mx - w / 2}" y="{my - h / 2}" width="{w}" height="{h}" rx="2" fill="#F2B8B8" stroke="#A33" stroke-width="1.5"/>')
        sx, sy = mx + (x2 - x1) / max(abs(x2 - x1), abs(y2 - y1), 1) * (w / 2 - 3), my + (y2 - y1) / max(abs(x2 - x1), abs(y2 - y1), 1) * (h / 2 - 3)
        if horizontal:
            svg.add(f'<line x1="{sx}" y1="{my - h / 2}" x2="{sx}" y2="{my + h / 2}" stroke="#222" stroke-width="3"/>')
        else:
            svg.add(f'<line x1="{mx - w / 2}" y1="{sy}" x2="{mx + w / 2}" y2="{sy}" stroke="#222" stroke-width="3"/>')
    for p in (a, b):
        x, y = xy(*p)
        svg.add(f'<circle cx="{x}" cy="{y}" r="3.6" fill="#555"/>')
    svg.text(mx + label_dx, my + label_dy, label, 10.5, "middle", "#111", "600")


def chip(svg, rows, name, left_pins, right_pins):
    """A DIP adapter straddling the center gap with its pins in columns c and g (0.6" rows), pin 1 at top left."""
    first, last = rows
    x1, y1 = xy("c", first)
    x2, y2 = xy("g", last)
    svg.add(f'<rect x="{x1 - 0.5 * P}" y="{y1 - 0.5 * P}" width="{x2 - x1 + P}" height="{y2 - y1 + P}" rx="4" fill="#2F3A2F" opacity="0.92"/>')
    svg.add(f'<circle cx="{x1 + 6}" cy="{y1 - 6}" r="3" fill="#fff"/>')
    svg.text((x1 + x2) / 2, y1 - 0.5 * P - 10, name, 12, "middle", "#2F3A2F", "700")
    for i, label in enumerate(left_pins):
        x, y = xy("c", first + i)
        svg.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#C0C0C0"/>')
        svg.text(x + 9, y, label, 9, "start", "#E8F0E8")
    for i, label in enumerate(right_pins):
        x, y = xy("g", first + i)
        svg.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#C0C0C0"/>')
        svg.text(x - 9, y, label, 9, "end", "#E8F0E8")


def offboard(svg, hole, side, label, color, dashed=False):
    """A wire leaving the board from a hole, ending in a label in the margin.

    It runs between rows (half a pitch above the hole), so it can't be mistaken for a connection to a rail it crosses.
    """
    x, y = xy(*hole)
    edge = X0 - 2.6 * P if side == "left" else X0 + 18.6 * P
    turn = x - 0.5 * P if side == "left" else x + 0.5 * P
    y = y - 0.5 * P
    wire(svg, [hole, (turn, y), (edge, y)], color, dashed)
    svg.add(f'<circle cx="{edge}" cy="{y}" r="4" fill="#fff" stroke="{color}" stroke-width="2"/>')
    if side == "left":
        svg.text(edge - 8, y, label, 10.5, "end", color, "600")
    else:
        svg.text(edge + 8, y, label, 10.5, "start", color, "600")


def legend(svg, y, items):
    x = 20
    for color, label, dashed in items:
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        svg.add(f'<line x1="{x}" y1="{y}" x2="{x + 26}" y2="{y}" stroke="{color}" stroke-width="3"{dash}/>')
        svg.text(x + 32, y, label, 11)
        x += 40 + 7 * len(label)


def board_a():
    svg = Svg("Board A: Pico + DAC board (USB end at the top)")
    draw_board(svg)
    # Pico in two 20-pin female headers, columns c and h.
    x1, y1 = xy("c", 1)
    x2, y2 = xy("h", 20)
    svg.add(f'<rect x="{x1 - 10}" y="{y1 - 16}" width="{x2 - x1 + 20}" height="{y2 - y1 + 30}" rx="6" fill="#1F7A3A" opacity="0.9"/>')
    svg.add(f'<rect x="{(x1 + x2) / 2 - 18}" y="{y1 - 30}" width="36" height="22" rx="3" fill="#B8B8B8" stroke="#777"/>')
    svg.text((x1 + x2) / 2, y1 - 19, "USB", 9, "middle", "#222", "700")
    svg.text((x1 + x2) / 2, (y1 + y2) / 2, "Raspberry Pi Pico H", 13, "middle", "#fff", "700")
    svg.text((x1 + x2) / 2, (y1 + y2) / 2 + 18, "(in female headers)", 10, "middle", "#DFF3E4")
    left = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9", "GND", "GP10",
            "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
    right = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3 OUT", "ADC_VREF", "GP28", "AGND", "GP27", "GP26", "RUN", "GP22",
             "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"]
    for row in range(1, 21):
        for col, name, anchor, dx in (("c", left[row - 1], "start", 9), ("h", right[row - 1], "end", -9)):
            x, y = xy(col, row)
            svg.add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#111"/>')
            svg.text(x + dx, y, name, 8.5, anchor, "#F3FFF5")
    # Power: board A uses only the right-hand rails
    wire(svg, [("j", 5), ("+R", 5)], RED)
    wire(svg, [("j", 3), ("-R", 3)], BLACK)
    wire(svg, [("j", 8), ("-R", 8)], BLACK)
    # DAC board area; its pin order depends on the board, so its wires are labelled by DAC pin name
    xa, ya = xy("a", 20.6)
    xb, yb = xy("e", 30.4)
    svg.add(f'<rect x="{xa - 8}" y="{ya}" width="{xb - xa + 16}" height="{yb - ya}" rx="4" fill="#3B5BA8" opacity="0.85"/>')
    svg.text((xa + xb) / 2, ya + 34, "DAC board", 12, "middle", "#fff", "700")
    for i, line in enumerate(["rows 21-30, each pin", "in its own row", "", "VA: wire to row 10 right", "  + wire to board B row 2",
                              "VB: wire to row 9 right", "  + wire to board B row 16"]):
        svg.text((xa + xb) / 2, ya + 54 + i * 14, line, 9.5, "middle", "#E8EEFF")
    offboard(svg, ("a", 6), "left", "wire from DAC SDA", PURPLE)
    offboard(svg, ("a", 7), "left", "wire from DAC SCL", GREEN)
    offboard(svg, ("i", 10), "right", "wire from DAC VA", ORANGE)
    offboard(svg, ("i", 9), "right", "wire from DAC VB", BLUE)
    offboard(svg, ("+R", 21), "right", "wire from DAC VCC", RED)
    offboard(svg, ("-R", 22), "right", "wire from DAC GND", BLACK)
    offboard(svg, ("-R", 23), "right", "wire from DAC LDAC", BLACK)
    # To board B
    offboard(svg, ("a", 4), "left", "Q from board B row 23", GREEN)
    offboard(svg, ("a", 5), "left", "CLR to board B row 19", PURPLE)
    offboard(svg, ("a", 15), "left", "TEST to board B row 2 right (temporary)", ORANGE, dashed=True)
    offboard(svg, ("+R", 26), "right", "3.3 V to board B + rail", RED)
    offboard(svg, ("-R", 27), "right", "GND to board B − rail", BLACK)
    legend(svg, 800, [(RED, "3.3 V", False), (BLACK, "GND", False), (PURPLE, "signal", False), (ORANGE, "temporary test wire", True)])
    svg.save("board-a.svg")


def board_b():
    svg = Svg("Board B: input stage, comparator U1, latch U2 (BNC end at the top)")
    draw_board(svg)
    chip(svg, (11, 14), "U1", ["1 NC", "2 −IN", "3 +IN", "4 V−"], ["8 SHDN", "7 V+", "6 OUT", "5 NC"])
    chip(svg, (19, 25), "U2", ["1 1CLR", "2 1D", "3 1CLK", "4 1PRE", "5 1Q", "6 1Q̄", "7 GND"],
         ["14 VCC", "13 2CLR", "12 2D", "11 2CLK", "10 2PRE", "9 2Q", "8 2Q̄"])
    # Node labels
    for row, name in ((2, "VA in"), (4, "IN"), (6, "BIAS"), (8, "CMP"), (16, "VB in")):
        svg.text(xy("e", row)[0] + 12, xy("e", row)[1] - 9, name, 10.5, "start", "#7A3E00", "700")
    # Input network
    offboard(svg, ("a", 2), "left", "VA from board A", ORANGE)
    offboard(svg, ("a", 4), "left", "BNC centre pin (J1)", BLACK)
    offboard(svg, ("-L", 5), "left", "BNC ground tab (J1)", BLACK)
    part(svg, ("b", 4), ("-L", 4), "R", "R1 100k", label_dy=12)
    part(svg, ("c", 4), ("c", 6), "C", "C1 10n", label_dx=-32)
    part(svg, ("d", 2), ("d", 6), "R", "R2 10k", label_dx=22, label_dy=-26)
    part(svg, ("b", 6), ("b", 8), "R", "R3 100", label_dx=-24)
    part(svg, ("a", 8), ("+L", 8), "D", "D1", label_dy=-11)
    part(svg, ("-L", 9), ("c", 8), "D", "D2", label_dy=12)  # stripe (cathode) at CMP
    wire(svg, [("d", 8), ("d", 9.5), ("b", 9.5), ("b", 12)], PURPLE)
    # Threshold
    offboard(svg, ("a", 16), "left", "VB from board A", BLUE)
    part(svg, ("b", 16), ("b", 13), "R", "R4 1k", label_dx=-22)
    part(svg, ("a", 13), ("-L", 13), "C", "C2 100n", label_dy=-12)
    wire(svg, [("a", 14), ("-L", 14)], BLACK)
    # U1 right side
    wire(svg, [("j", 11), ("-R", 11)], BLACK)
    wire(svg, [("j", 12), ("+R", 12)], RED)
    part(svg, ("i", 12), ("-R", 13), "C", "C3 100n", label_dx=30, label_dy=8)
    wire(svg, [("i", 13), ("i", 17), ("b", 17), ("b", 21)], PURPLE)
    part(svg, ("+R", 16), ("-R", 16), "C", "C5 10µ", label_dx=0, label_dy=-14)
    # U2 left side
    offboard(svg, ("a", 19), "left", "CLR from board A (GP3)", PURPLE)
    wire(svg, [("a", 20), ("+L", 20)], RED)
    wire(svg, [("a", 22), ("+L", 22)], RED)
    offboard(svg, ("a", 23), "left", "Q to board A (GP2)", GREEN)
    wire(svg, [("a", 25), ("-L", 25)], BLACK)
    # U2 right side
    wire(svg, [("j", 19), ("+R", 19)], RED)
    part(svg, ("i", 19), ("-R", 18), "C", "C4 100n", label_dx=30, label_dy=-6)
    wire(svg, [("j", 20), ("+R", 20)], RED)
    wire(svg, [("j", 21), ("-R", 21)], BLACK)
    wire(svg, [("j", 22), ("-R", 22)], BLACK)
    wire(svg, [("j", 23), ("+R", 23)], RED)
    # Rails and power in
    wire(svg, [("+L", 29), ("+R", 29)], RED)
    wire(svg, [("-L", 30), ("-R", 30)], BLACK)
    offboard(svg, ("+L", 27), "left", "3.3 V from board A", RED)
    offboard(svg, ("-L", 28), "left", "GND from board A", BLACK)
    # Temporary test divider, right half rows 2-6
    offboard(svg, ("i", 2), "right", "TEST (GP11) from board A, temporary", ORANGE, dashed=True)
    part(svg, ("h", 2), ("h", 4), "R", "1k", label_dx=-16, dashed=True)
    part(svg, ("i", 4), ("i", 6), "R", "100", label_dx=18, dashed=True)
    part(svg, ("j", 6), ("-R", 7), "R", "100", label_dx=16, label_dy=-10, dashed=True)
    wire(svg, [("f", 4), ("e", 4)], ORANGE, dashed=True)
    legend(svg, 800, [(RED, "3.3 V", False), (BLACK, "GND", False), (PURPLE, "signal", False), (ORANGE, "temporary test parts", True)])
    svg.save("board-b.svg")


if __name__ == "__main__":
    board_a()
    board_b()
    print("wrote", OUT / "board-a.svg", "and", OUT / "board-b.svg")
