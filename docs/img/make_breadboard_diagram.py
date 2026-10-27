"""Draws docs/img/breadboard.svg: boards A and B together on one full-size solderless breadboard.

The breadboard (63 rows numbered bottom to top; rails W X | A-E | F-J | Y Z) holds both Perma-Proto layouts exactly as
drawn, so every chip keeps its real orientation: board B (BNC end up) in rows 34-63, board A (Pico + DAC) in rows 1-30.
Placements come from make_board_diagrams.py, so this drawing can't drift from the Perma-Proto ones.

Run from the repo folder:  .venv/Scripts/python docs/img/make_breadboard_diagram.py
"""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("boards", HERE / "make_board_diagrams.py")
boards = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(boards)

ROWS = 63
RAIL = {"-L": "W", "+L": "X", "+R": "Y", "-R": "Z"}
COLS = {"W": 0, "X": 1, "A": 2.5, "B": 3.5, "C": 4.5, "D": 5.5, "E": 6.5,
        "F": 9.5, "G": 10.5, "H": 11.5, "I": 12.5, "J": 13.5, "Y": 15, "Z": 16}
P, X0, Y0 = 20, 230, 70
RED, BLACK, BLUE, GREEN, PURPLE, ORANGE = boards.RED, boards.BLACK, boards.BLUE, boards.GREEN, boards.PURPLE, boards.ORANGE
ROW_OF = {"B": lambda r: 64 - r, "A": lambda r: 31 - r}  # board B rows 63..34, board A rows 30..1


def to_bb(board, hole):
    col, row = hole
    return (RAIL.get(col, col.upper()), ROW_OF[board](row))


def xy(hole):
    col, row = hole
    return X0 + COLS[col] * P, Y0 + (ROWS - row) * P


# ---- record the Perma-Proto placements -------------------------------------------------------------

items = []  # (kind, board, data...)
_board = None


def _rec_wire(svg, points, color, dashed=False, width=3):
    if all(isinstance(p[0], str) for p in points):
        items.append(("wire", _board, [to_bb(_board, p) for p in points], color, dashed))


def _rec_part(svg, a, b, kind, label, color=None, label_dx=0, label_dy=0, dashed=False):
    items.append(("part", _board, to_bb(_board, a), to_bb(_board, b), kind, label, dashed, label_dx, label_dy))


def _rec_chip(svg, rows, name, left_pins, right_pins):
    items.append(("chip", _board, rows, name, left_pins, right_pins))


def _rec_off(svg, hole, side, label, color, dashed=False):
    items.append(("off", _board, to_bb(_board, hole), label, color, dashed))


boards.wire, boards.part, boards.chip, boards.offboard = _rec_wire, _rec_part, _rec_chip, _rec_off
boards.legend = lambda *a, **k: None
boards.Svg.save = lambda self, name: None
_board = "A"
boards.board_a()
_board = "B"
boards.board_b()

# Off-board labels that join board A to board B become real wires on the shared breadboard.
JOIN = {
    "Q from board B row 23": ("Q to board A (GP2)", GREEN, False),
    "CLR to board B row 19": ("CLR from board A (GP3)", PURPLE, False),
    "TEST to board B row 2 right (temporary)": ("TEST (GP11) from board A, temporary", ORANGE, True),
}
SKIP = {"3.3 V to board B + rail", "GND to board B − rail", "3.3 V from board A", "GND from board A"}  # rails are shared
RENAME = {"VA from board A": "2nd wire from DAC VA", "VB from board A": "2nd wire from DAC VB",
          "BNC centre pin (J1)": "BNC jack centre pin", "BNC ground tab (J1)": "BNC jack ground tab"}


# ---- draw ------------------------------------------------------------------------------------------

svg = boards.Svg("Full breadboard: boards A and B together", width=860, height=Y0 + ROWS * P + 90)


def line(points, color, dashed=False, width=3, dots=True):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (xy(p) if isinstance(p[0], str) else p for p in points))
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    svg.add(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
            f'stroke-linejoin="round"{dash}/>')
    if dots:
        for p in (points[0], points[-1]):
            if isinstance(p[0], str):
                x, y = xy(p)
                svg.add(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')


def draw_breadboard():
    top, bottom = Y0 + 0.4 * P, Y0 + (ROWS - 0.6) * P + 12
    svg.add(f'<rect x="{X0 - 0.8 * P}" y="{top - 0.5 * P}" width="{17.6 * P}" height="{bottom - top + P}" rx="8" '
            'fill="#F7F7F2" stroke="#BBB"/>')
    for rail, color in (("W", BLUE), ("X", RED), ("Y", RED), ("Z", BLUE)):
        x = X0 + COLS[rail] * P
        svg.add(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{bottom}" stroke="{color}" stroke-width="7" opacity="0.18"/>')
    for row in range(1, ROWS + 1):
        y = Y0 + (ROWS - row) * P
        for left, right in (("A", "E"), ("F", "J")):
            svg.add(f'<line x1="{xy((left, row))[0]}" y1="{y}" x2="{xy((right, row))[0]}" y2="{y}" stroke="#E2E2D8" '
                    'stroke-width="9" stroke-linecap="round"/>')
        for col in COLS:
            svg.add(f'<circle cx="{X0 + COLS[col] * P}" cy="{y}" r="3" fill="#777"/>')
        svg.text(X0 - 1.3 * P, y, str(row), 9.5, "end", "#888")
        svg.text(X0 + 17.3 * P, y, str(row), 9.5, "start", "#888")
    for col in COLS:
        svg.text(X0 + COLS[col] * P, top - 1.0 * P, col, 11, "middle", "#666", "700")
        svg.text(X0 + COLS[col] * P, bottom + 0.9 * P, col, 11, "middle", "#666", "700")
    svg.text(430, 46, "Top half = board B (input + chips, BNC end at row 63) · bottom half = board A (Pico + DAC, USB faces the middle)",
             10.5, "middle", "#B05A00", "600")


def draw_chip(rows, name, left_pins, right_pins):
    first, last = ROW_OF["B"](rows[0]), ROW_OF["B"](rows[1])  # pin 1 at the top (higher row number)
    x1, y1 = xy(("C", first))
    x2, y2 = xy(("G", last))
    svg.add(f'<rect x="{x1 - 0.5 * P}" y="{y1 - 0.5 * P}" width="{x2 - x1 + P}" height="{y2 - y1 + P}" rx="4" fill="#2F3A2F" opacity="0.92"/>')
    svg.add(f'<circle cx="{x1 + 6}" cy="{y1 - 6}" r="3" fill="#fff"/>')
    svg.text((x1 + x2) / 2, y1 - 0.5 * P - 9, name + "  (pin 1 dot top-left)", 10.5, "middle", "#2F3A2F", "700")
    for i, label in enumerate(left_pins):
        x, y = xy(("C", first - i))
        svg.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#C0C0C0"/>')
        svg.text(x + 9, y, label, 8.5, "start", "#E8F0E8")
    for i, label in enumerate(right_pins):
        x, y = xy(("G", first - i))
        svg.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="#C0C0C0"/>')
        svg.text(x - 9, y, label, 8.5, "end", "#E8F0E8")


def draw_pico():
    x1, y1 = xy(("C", 30))
    x2, y2 = xy(("H", 11))
    svg.add(f'<rect x="{x1 - 10}" y="{y1 - 14}" width="{x2 - x1 + 20}" height="{y2 - y1 + 28}" rx="6" fill="#1F7A3A" opacity="0.9"/>')
    svg.add(f'<rect x="{(x1 + x2) / 2 - 16}" y="{y1 - 28}" width="32" height="18" rx="3" fill="#B8B8B8" stroke="#777"/>')
    svg.text((x1 + x2) / 2, y1 - 19, "USB", 8.5, "middle", "#222", "700")
    svg.text((x1 + x2) / 2, (y1 + y2) / 2, "Pico H", 13, "middle", "#fff", "700")
    svg.text((x1 + x2) / 2, (y1 + y2) / 2 + 16, "pins straight in", 9.5, "middle", "#DFF3E4")
    left = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9", "GND", "GP10",
            "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
    right = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3 OUT", "ADC_VREF", "GP28", "AGND", "GP27", "GP26", "RUN", "GP22",
             "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"]
    for i in range(20):
        for col, name, anchor, dx in (("C", left[i], "start", 8), ("H", right[i], "end", -8)):
            x, y = xy((col, 30 - i))
            svg.add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#111"/>')
            svg.text(x + dx, y, name, 8, anchor, "#F3FFF5")


def draw_dac():
    x1, y1 = xy(("A", 10))
    x2, y2 = xy(("E", 1))
    svg.add(f'<rect x="{x1 - 8}" y="{y1 - 9}" width="{x2 - x1 + 16}" height="{y2 - y1 + 18}" rx="4" fill="#3B5BA8" opacity="0.85"/>')
    for i, text in enumerate(["DAC board, rows 1–10", "pins in ONE column,", "one pin per row", "(never along a row)"]):
        svg.text((x1 + x2) / 2, y1 + 12 + i * 15, text, 9.5 if i else 10.5, "middle", "#fff", "700" if i == 0 else "400")


def margin_label(hole, label, color, dashed, side):
    x, y = xy(hole)
    edge = X0 - 3.0 * P if side == "left" else X0 + 19.0 * P
    turn = x - 0.5 * P if side == "left" else x + 0.5 * P
    line([hole, (turn, y - 0.5 * P), (edge, y - 0.5 * P)], color, dashed)
    svg.add(f'<circle cx="{edge}" cy="{y - 0.5 * P}" r="4" fill="#fff" stroke="{color}" stroke-width="2"/>')
    anchor, dx = ("end", -8) if side == "left" else ("start", 8)
    svg.text(edge + dx, y - 0.5 * P, label, 10, anchor, color, "600")


def join(a, b, color, dashed):
    """A board-to-board wire. Same-side ends run down the left margin; a right-hand end crosses in the empty gap rows."""
    ax, ay = xy(a)
    bx, by = xy(b)
    lane = X0 - (2.0 + 0.35 * len(joined)) * P
    joined.append(1)
    if b[0] in ("W", "X", "A", "B", "C", "D", "E"):
        pts = [a, (ax - 0.5 * P, ay - 0.5 * P), (lane, ay - 0.5 * P), (lane, by - 0.5 * P), (bx - 0.5 * P, by - 0.5 * P), b]
    else:
        gap_y = xy(("A", 32))[1]
        right_lane = X0 + 17.9 * P
        pts = [a, (ax - 0.5 * P, ay - 0.5 * P), (lane, ay - 0.5 * P), (lane, gap_y), (right_lane, gap_y),
               (right_lane, by - 0.5 * P), (bx + 0.5 * P, by - 0.5 * P), b]
    line(pts, color, dashed)


draw_breadboard()
draw_pico()
draw_dac()
joined = []
off = {(it[1], it[3]): it for it in items if it[0] == "off"}
for it in items:
    if it[0] == "chip":
        draw_chip(*it[2:])
for it in items:
    if it[0] == "wire":
        line(it[2], it[3], it[4])
    elif it[0] == "part":
        _, board, a, b, kind, label, dashed, ldx, ldy = it
        line([a, b], "#777", dashed, width=2, dots=False)
        (x1, y1), (x2, y2) = xy(a), xy(b)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        horiz = abs(x2 - x1) > abs(y2 - y1)
        w, h = (18, 9) if horiz else (9, 18)
        if kind == "C":
            svg.add(f'<circle cx="{mx}" cy="{my}" r="7" fill="#7FB3E8" stroke="#1D63C9" stroke-width="1.5"/>')
        else:
            fill, stroke = ("#E7C38A", "#8C5A2B") if kind == "R" else ("#F2B8B8", "#A33")
            svg.add(f'<rect x="{mx - w / 2}" y="{my - h / 2}" width="{w}" height="{h}" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            if kind == "D":  # stripe at the cathode end (b)
                k = 0.32
                sx, sy = mx + (x2 - mx) * k, my + (y2 - my) * k
                if horiz:
                    svg.add(f'<line x1="{sx}" y1="{my - h / 2}" x2="{sx}" y2="{my + h / 2}" stroke="#222" stroke-width="3"/>')
                else:
                    svg.add(f'<line x1="{mx - w / 2}" y1="{sy}" x2="{mx + w / 2}" y2="{sy}" stroke="#222" stroke-width="3"/>')
        for p in (a, b):
            x, y = xy(p)
            svg.add(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#555"/>')
        svg.text(mx + ldx, my + ldy, label, 10, "middle", "#111", "600")
for (board, label), it in off.items():
    if label in SKIP:
        continue
    if board == "A" and label in JOIN:
        other, color, dashed = JOIN[label]
        join(it[2], off[("B", other)][2], color, dashed)
    elif board == "B" and label in {v[0] for v in JOIN.values()}:
        continue
    else:
        side = "left" if it[2][0] in ("W", "X", "A", "B", "C", "D", "E") else "right"
        margin_label(it[2], RENAME.get(label, label), it[4], it[5], side)
# The two halves share the rails; these bridge the middle in case your breadboard splits its rails there.
line([("Y", 30), ("Y", 34)], RED)
line([("Z", 30), ("Z", 34)], BLACK)
svg.text(X0 + 18.4 * P, xy(("Y", 31))[1], "← rail bridges", 9.5, "start", "#444", "600")
y_leg = Y0 + ROWS * P + 50
for i, (color, text, dashed) in enumerate([(RED, "3.3 V", False), (BLACK, "GND", False), (PURPLE, "signal", False),
                                           (ORANGE, "temporary test parts", True)]):
    x = 30 + i * 170
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    svg.add(f'<line x1="{x}" y1="{y_leg}" x2="{x + 26}" y2="{y_leg}" stroke="{color}" stroke-width="3"{dash}/>')
    svg.text(x + 32, y_leg, text, 11)
svg.parts.append("</svg>")
(HERE / "breadboard.svg").write_text("\n".join(svg.parts), encoding="utf-8")
print("wrote", HERE / "breadboard.svg")
