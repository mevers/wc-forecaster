from __future__ import annotations

import argparse
import base64
import csv
import importlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


WIDTH = 2400
HEIGHT = 1695
INK = "#18232d"
MUTED = "#6f7b86"
NAVY = "#113a59"
NAVY_2 = "#46546f"
GOLD = "#c49a55"
BRONZE = "#aa6a33"
PAPER = "#fbfcfd"
LINE = "#8b969f"

COUNTRY_CODES = {
    "Argentina": "ar",
    "Algeria": "dz",
    "Australia": "au",
    "Austria": "at",
    "Belgium": "be",
    "Bosnia and Herzegovina": "ba",
    "Brazil": "br",
    "Canada": "ca",
    "Cape Verde": "cv",
    "Colombia": "co",
    "Croatia": "hr",
    "Curacao": "cw",
    "Czechia": "cz",
    "DR Congo": "cd",
    "Ecuador": "ec",
    "Egypt": "eg",
    "England": "gb-eng",
    "France": "fr",
    "Germany": "de",
    "Ghana": "gh",
    "Haiti": "ht",
    "Iran": "ir",
    "Iraq": "iq",
    "Ivory Coast": "ci",
    "Japan": "jp",
    "Jordan": "jo",
    "Mexico": "mx",
    "Morocco": "ma",
    "Netherlands": "nl",
    "New Zealand": "nz",
    "Norway": "no",
    "Panama": "pa",
    "Paraguay": "py",
    "Portugal": "pt",
    "Qatar": "qa",
    "Saudi Arabia": "sa",
    "Scotland": "gb-sct",
    "Senegal": "sn",
    "South Africa": "za",
    "South Korea": "kr",
    "Spain": "es",
    "Sweden": "se",
    "Switzerland": "ch",
    "Turkey": "tr",
    "Tunisia": "tn",
    "United States": "us",
    "Uruguay": "uy",
    "Uzbekistan": "uz",
}

DISPLAY_NAMES = {
    "Bosnia and Herzegovina": "BiH",
    "United States": "USA",
}


@dataclass(frozen=True)
class RealisedMatch:
    team_a: str
    team_b: str
    winner: str


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def left(self) -> tuple[float, float]:
        return (self.x, self.cy)

    @property
    def right(self) -> tuple[float, float]:
        return (self.x + self.w, self.cy)

    @property
    def top(self) -> tuple[float, float]:
        return (self.cx, self.y)

    @property
    def bottom(self) -> tuple[float, float]:
        return (self.cx, self.y + self.h)


def read_realised_bracket(path: Path) -> dict[int, RealisedMatch]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            int(row["match_no"]): RealisedMatch(
                row["team_a"],
                row["team_b"],
                row["winner"],
            )
            for row in csv.DictReader(handle)
        }


def read_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def display_name(team: str) -> str:
    return DISPLAY_NAMES.get(team, team)


def flag_data_uri(flags_dir: Path, team: str, cache: dict[str, str]) -> str:
    code = COUNTRY_CODES[team]
    if code not in cache:
        data = base64.b64encode((flags_dir / f"{code}.png").read_bytes()).decode("ascii")
        cache[code] = f"data:image/png;base64,{data}"
    return cache[code]


def text(
    x: float,
    y: float,
    value: str,
    size: float,
    fill: str = INK,
    weight: int = 600,
    anchor: str = "start",
    opacity: float = 1,
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{size:.1f}" font-weight="{weight}" fill="{fill}" '
        f'opacity="{opacity:.3f}" dominant-baseline="middle">{escape(value)}</text>'
    )


def star_path(cx: float, cy: float, outer: float, inner: float) -> str:
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append(f"{cx + math.cos(angle) * radius:.1f},{cy + math.sin(angle) * radius:.1f}")
    return " ".join(points)


def background() -> list[str]:
    stars = [
        (270, 210, 120, "#ef3340", 0.18),
        (610, 115, 150, "#ef3340", 0.15),
        (1010, 310, 130, "#ef3340", 0.09),
        (370, 640, 95, "#ef3340", 0.08),
        (560, 1420, 115, "#3aa9e8", 0.13),
        (1100, 1455, 140, "#3aa9e8", 0.11),
        (1730, 1180, 155, "#2c96db", 0.15),
        (2030, 1390, 185, "#1d7fe5", 0.20),
        (2030, 240, 130, "#ef3340", 0.08),
    ]
    out = [
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>',
        '<path d="M0 0 H1050 L780 1695 H0 Z" fill="#ef3340" opacity="0.070"/>',
        '<path d="M1160 0 H2400 V1695 H1640 Z" fill="#ef3340" opacity="0.035"/>',
        '<path d="M610 1695 H2400 V820 Z" fill="#20a7f2" opacity="0.160"/>',
        '<path d="M1260 1695 H2400 V1050 Z" fill="#006fd6" opacity="0.120"/>',
    ]
    for cx, cy, radius, fill, opacity in stars:
        out.append(
            f'<polygon points="{star_path(cx, cy, radius, radius * 0.42)}" '
            f'fill="{fill}" opacity="{opacity:.3f}"/>'
        )
    return out


def defs() -> str:
    return """
<defs>
  <filter id="softShadow" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="0" dy="8" stdDeviation="9" flood-color="#0d2238" flood-opacity="0.08"/>
  </filter>
</defs>
""".strip()


def connector(start: tuple[float, float], end: tuple[float, float]) -> str:
    sx, sy = start
    ex, ey = end
    mx = (sx + ex) / 2
    points = f"{sx:.1f},{sy:.1f} {mx:.1f},{sy:.1f} {mx:.1f},{ey:.1f} {ex:.1f},{ey:.1f}"
    return f'<polyline points="{points}" fill="none" stroke="{LINE}" stroke-width="2.6" stroke-linejoin="round"/>'


def line(points: list[tuple[float, float]], width: float = 2.6, dashed: bool = False) -> str:
    point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash = ' stroke-dasharray="7 8"' if dashed else ""
    return f'<polyline points="{point_text}" fill="none" stroke="{LINE}" stroke-width="{width:.1f}" stroke-linejoin="round"{dash}/>'


def flag(
    flags_dir: Path,
    team: str,
    x: float,
    y: float,
    w: float,
    h: float,
    cache: dict[str, str],
) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="2.5" fill="#fff" stroke="#d8dee5" stroke-width="1"/>'
        f'<image x="{x + 1:.1f}" y="{y + 1:.1f}" width="{w - 2:.1f}" height="{h - 2:.1f}" '
        f'preserveAspectRatio="xMidYMid meet" href="{flag_data_uri(flags_dir, team, cache)}"/>'
    )


def row(
    flags_dir: Path,
    team: str,
    box: Box,
    y: float,
    h: float,
    winner: bool,
    cache: dict[str, str],
    large: bool = False,
) -> str:
    fill = "#fff7e8" if winner else "#ffffff"
    stroke = "#ecd7ad" if winner else "#e7edf2"
    flag_w = 54 if large else 32
    flag_h = 34 if large else 21
    font_size = 26 if large else 15
    name = display_name(team)
    if len(name) > 13 and not large:
        font_size = 13
    out = [
        f'<rect x="{box.x + 11:.1f}" y="{y:.1f}" width="{box.w - 22:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>',
    ]
    if winner:
        out.append(f'<rect x="{box.x + 11:.1f}" y="{y:.1f}" width="5.0" height="{h:.1f}" fill="{GOLD}"/>')
    out.append(flag(flags_dir, team, box.x + 22, y + (h - flag_h) / 2, flag_w, flag_h, cache))
    out.append(text(box.x + 22 + flag_w + 10, y + h / 2 + 1, name, font_size, INK, 700 if winner else 500))
    return "".join(out)


def match_card(
    flags_dir: Path,
    box: Box,
    match_no: int,
    round_name: str,
    teams: tuple[str, str],
    winner: str | None,
    cache: dict[str, str],
    header_fill: str = NAVY,
) -> str:
    header_h = 29
    row_h = (box.h - header_h - 14) / 2
    row_1_y = box.y + header_h + 7
    row_2_y = row_1_y + row_h
    vs_x = box.x + box.w - 33
    vs_y = row_1_y + row_h
    out = [
        '<g filter="url(#softShadow)">',
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="10" fill="#f8fbfd" stroke="#c8d1da" stroke-width="1.4"/>',
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{header_h:.1f}" rx="10" fill="{header_fill}"/>',
        f'<rect x="{box.x:.1f}" y="{box.y + header_h - 10:.1f}" width="{box.w:.1f}" height="10" fill="{header_fill}"/>',
        text(box.x + 14, box.y + 15, f"M{match_no}", 13, "#ffffff", 800),
        text(box.x + box.w - 14, box.y + 15, round_name, 10, "#dce8f1", 700, "end"),
        row(flags_dir, teams[0], box, row_1_y, row_h, teams[0] == winner, cache),
        row(flags_dir, teams[1], box, row_2_y, row_h, teams[1] == winner, cache),
        f'<circle cx="{vs_x:.1f}" cy="{vs_y:.1f}" r="12" fill="{header_fill}" stroke="#ffffff" stroke-width="3"/>',
        text(vs_x, vs_y + 0.5, "vs", 8, "#ffffff", 800, "middle"),
        "</g>",
    ]
    return "".join(out)


def final_card(flags_dir: Path, box: Box, teams: tuple[str, str], winner: str, cache: dict[str, str]) -> str:
    header_h = 56
    row_h = (box.h - header_h - 26) / 2
    row_1_y = box.y + header_h + 13
    row_2_y = row_1_y + row_h
    vs_y = row_1_y + row_h
    out = [
        '<g filter="url(#softShadow)">',
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="20" fill="#c79d5a" stroke="#a98145" stroke-width="2"/>',
        text(box.x + 28, box.y + 29, "M104", 25, "#ffffff", 900),
        text(box.x + box.w - 28, box.y + 29, "FINAL", 25, "#ffffff", 900, "end"),
        row(flags_dir, teams[0], box, row_1_y, row_h, teams[0] == winner, cache, True),
        row(flags_dir, teams[1], box, row_2_y, row_h, teams[1] == winner, cache, True),
        f'<circle cx="{box.cx:.1f}" cy="{vs_y:.1f}" r="22" fill="#ffffff" stroke="#c79d5a" stroke-width="5"/>',
        text(box.cx, vs_y + 1, "vs", 13, GOLD, 900, "middle"),
        "</g>",
    ]
    return "".join(out)


def trophy(cx: float, cy: float) -> str:
    return f"""
<g>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="72" fill="#ffffff" stroke="#8d989f" stroke-width="2"/>
  <ellipse cx="{cx:.1f}" cy="{cy + 43:.1f}" rx="35" ry="8" fill="#d0a45d"/>
  <rect x="{cx - 16:.1f}" y="{cy + 12:.1f}" width="32" height="35" rx="4" fill="#d0a45d"/>
  <path d="M{cx - 39:.1f} {cy - 34:.1f} H{cx + 39:.1f} L{cx + 27:.1f} {cy + 9:.1f} Q{cx:.1f} {cy + 27:.1f} {cx - 27:.1f} {cy + 9:.1f} Z" fill="#f0c46f" stroke="#b98536" stroke-width="2"/>
  <path d="M{cx - 39:.1f} {cy - 24:.1f} C{cx - 70:.1f} {cy - 24:.1f} {cx - 70:.1f} {cy + 10:.1f} {cx - 34:.1f} {cy + 8:.1f}" fill="none" stroke="#b98536" stroke-width="7"/>
  <path d="M{cx + 39:.1f} {cy - 24:.1f} C{cx + 70:.1f} {cy - 24:.1f} {cx + 70:.1f} {cy + 10:.1f} {cx + 34:.1f} {cy + 8:.1f}" fill="none" stroke="#b98536" stroke-width="7"/>
</g>
""".strip()


def loser(teams: tuple[str, str], winner: str) -> str:
    return teams[1] if teams[0] == winner else teams[0]


def round_name(match_no: int) -> str:
    if match_no <= 88:
        return "Round of 32"
    if match_no <= 96:
        return "Round of 16"
    if match_no <= 100:
        return "Quarter-final"
    return "Semi-final"


def draw_svg(
    output: Path,
    bracket: dict[int, RealisedMatch],
    manifest: dict[str, Any],
    flags_dir: Path,
) -> None:
    left_leaves = [73, 75, 74, 77, 83, 84, 81, 82]
    right_leaves = [76, 78, 79, 80, 86, 88, 85, 87]
    children = {
        89: (73, 75),
        90: (74, 77),
        91: (76, 78),
        92: (79, 80),
        93: (83, 84),
        94: (81, 82),
        95: (86, 88),
        96: (85, 87),
        97: (89, 90),
        98: (93, 94),
        99: (91, 92),
        100: (95, 96),
        101: (97, 98),
        102: (99, 100),
    }
    card_w = 238
    card_h = 96
    centres: dict[int, float] = {}
    for index, match_no in enumerate(left_leaves):
        centres[match_no] = 344 + index * 130
    for index, match_no in enumerate(right_leaves):
        centres[match_no] = 344 + index * 130
    for match_no in [89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102]:
        first, second = children[match_no]
        centres[match_no] = (centres[first] + centres[second]) / 2

    x_positions = {
        "left_leaf": 290,
        "left_r16": 540,
        "left_qf": 790,
        "left_sf": 960,
        "right_sf": 1202,
        "right_qf": 1372,
        "right_r16": 1622,
        "right_leaf": 1872,
    }
    boxes: dict[int, Box] = {}
    for match_no in left_leaves:
        boxes[match_no] = Box(x_positions["left_leaf"], centres[match_no] - card_h / 2, card_w, card_h)
    for match_no in right_leaves:
        boxes[match_no] = Box(x_positions["right_leaf"], centres[match_no] - card_h / 2, card_w, card_h)
    for match_no, key in [
        (89, "left_r16"),
        (90, "left_r16"),
        (93, "left_r16"),
        (94, "left_r16"),
        (97, "left_qf"),
        (98, "left_qf"),
        (101, "left_sf"),
        (91, "right_r16"),
        (92, "right_r16"),
        (95, "right_r16"),
        (96, "right_r16"),
        (99, "right_qf"),
        (100, "right_qf"),
        (102, "right_sf"),
    ]:
        boxes[match_no] = Box(x_positions[key], centres[match_no] - card_h / 2, card_w, card_h)

    teams_by_match = {
        match_no: (match.team_a, match.team_b)
        for match_no, match in bracket.items()
        if match_no != 104
    }
    final_teams = (bracket[104].team_a, bracket[104].team_b)
    third_place_teams = (
        loser(teams_by_match[101], bracket[101].winner),
        loser(teams_by_match[102], bracket[102].winner),
    )

    flag_cache: dict[str, str] = {}
    connectors = []
    for parent, (first, second) in children.items():
        for child in (first, second):
            if boxes[child].x < boxes[parent].x:
                connectors.append(connector(boxes[child].right, boxes[parent].left))
            else:
                connectors.append(connector(boxes[child].left, boxes[parent].right))

    final_box = Box(860, 1265, 680, 246)
    third_centre_y = (boxes[97].cy + boxes[101].cy) / 2 - 50
    third_box = Box((WIDTH - card_w) / 2, third_centre_y - card_h / 2, card_w, card_h)
    third_fork_y = (third_box.bottom[1] + boxes[101].top[1]) / 2
    connectors.extend(
        [
            line([boxes[101].bottom, (boxes[101].cx, 1150), (1200, 1150), final_box.top]),
            line([boxes[102].bottom, (boxes[102].cx, 1150), (1200, 1150), final_box.top]),
            line([third_box.bottom, (third_box.cx, third_fork_y)], 2.0, True),
            line([(boxes[101].cx, third_fork_y), (boxes[102].cx, third_fork_y)], 2.0, True),
            line([(boxes[101].cx, third_fork_y), boxes[101].top], 2.0, True),
            line([(boxes[102].cx, third_fork_y), boxes[102].top], 2.0, True),
        ]
    )

    simulations = int(manifest["simulations"])
    as_of = str(manifest["as_of"])
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        defs(),
        '<style>text{font-family:"Fira Sans","Avenir Next","Helvetica Neue",Arial,sans-serif;letter-spacing:0}</style>',
        *background(),
        text(1200, 88, "WORLD CUP", 118, INK, 900, "middle"),
        text(1200, 208, "2026", 182, "#ed1b2f", 900, "middle"),
        text(1200, 292, f"Most likely knockout bracket from {simulations:,} simulations · as at {as_of}", 23, MUTED, 500, "middle"),
        *connectors,
        trophy(1200, 1120),
    ]
    for match_no in [*left_leaves, 89, 90, 97, 93, 94, 98, 101, 102, 99, 91, 92, 100, 95, 96, *right_leaves]:
        svg.append(
            match_card(
                flags_dir,
                boxes[match_no],
                match_no,
                round_name(match_no),
                teams_by_match[match_no],
                bracket[match_no].winner,
                flag_cache,
                NAVY if match_no <= 88 else NAVY_2,
            )
        )
    svg.append(match_card(flags_dir, third_box, 103, "Third-place play-off", third_place_teams, None, flag_cache, BRONZE))
    svg.append(final_card(flags_dir, final_box, final_teams, bracket[104].winner, flag_cache))
    svg.append(text(1200, 1572, "Bold rows advance. Groups use expected table performance; knockouts use head-to-head advancement probability.", 18, MUTED, 500, "middle", 0.86))
    svg.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg), encoding="utf-8")


def render_png(svg_path: Path, png_path: Path) -> None:
    cairosvg = importlib.import_module("cairosvg")

    png_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=WIDTH * 2,
        output_height=HEIGHT * 2,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--flags-dir", type=Path, default=Path("outputs/flags"))
    args = parser.parse_args()
    draw_svg(
        args.run_dir / "knockout_bracket.svg",
        read_realised_bracket(args.run_dir / "most_likely_knockout_bracket.csv"),
        read_manifest(args.run_dir / "run_manifest.json"),
        args.flags_dir,
    )
    render_png(args.run_dir / "knockout_bracket.svg", args.run_dir / "knockout_bracket.png")


if __name__ == "__main__":
    main()
