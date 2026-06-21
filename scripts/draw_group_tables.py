from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from draw_knockout_bracket import (
    GOLD,
    INK,
    MUTED,
    NAVY,
    WIDTH,
    background,
    defs,
    display_name,
    flag,
    read_manifest,
    render_png,
    text,
    watermark,
)
from wc_forecaster.cli import load_config, load_groups
from wc_forecaster.data import read_matches
from wc_forecaster.model import sample_score

HEIGHT = 1695
CARD_WIDTH = 950
CARD_HEIGHT = 170
CARD_GAP = 25
LEFT_GROUPS = "ABCDEF"
RIGHT_GROUPS = "GHIJKL"


def read_adjusted_ratings(path: Path) -> dict[str, float]:
    import csv

    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["team"]: float(row["adjusted_rating"])
            for row in csv.DictReader(handle)
        }


def initial_form(
    historical: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    as_of: date,
) -> dict[str, bool]:
    form: dict[str, bool] = {}
    training = [
        match
        for match in historical
        if not (
            match["date"].year == 2026
            and match["tournament"] == "FIFA World Cup"
        )
    ]
    played = [
        match
        for match in fixtures
        if match["date"] <= as_of and match["home_score"] is not None
    ]
    for match in sorted([*training, *played], key=lambda row: row["date"]):
        form[match["home_team"]] = match["home_score"] > match["away_score"]
        form[match["away_team"]] = match["away_score"] > match["home_score"]
    return form


def add_result(
    table: dict[str, dict[str, int]],
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> None:
    table[home]["gf"] += home_score
    table[home]["ga"] += away_score
    table[away]["gf"] += away_score
    table[away]["ga"] += home_score
    table[home]["points"] += 3 if home_score > away_score else 1 if home_score == away_score else 0
    table[away]["points"] += 3 if away_score > home_score else 1 if home_score == away_score else 0
    table[home]["wins" if home_score > away_score else "draws" if home_score == away_score else "losses"] += 1
    table[away]["wins" if away_score > home_score else "draws" if home_score == away_score else "losses"] += 1


def completed_group_metrics(
    groups: dict[str, list[str]],
    fixtures: list[dict[str, Any]],
    as_of: date,
) -> dict[str, dict[str, dict[str, int]]]:
    completed = {
        group: {
            team: {"points": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0}
            for team in teams
        }
        for group, teams in groups.items()
    }
    for match in fixtures:
        if match["date"] <= as_of and match["home_score"] is not None:
            add_result(
                completed[match["group"]],
                match["home_team"],
                match["away_team"],
                match["home_score"],
                match["away_score"],
            )
    return completed


def simulate_group_tables(
    run_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    config_path = Path(manifest["config"])
    cfg = load_config(config_path)
    tuning = json.loads((run_dir / "tuning_summary.json").read_text(encoding="utf-8"))
    cfg["goals"]["min_expected_goals"] = tuning["selected_min_expected_goals"]
    cfg["forecast"]["simulations"] = int(manifest["simulations"])
    as_of = date.fromisoformat(str(manifest["as_of"]))
    groups = load_groups(cfg["data"]["groups"])
    fixtures = read_matches(cfg["data"]["fixtures"])
    historical = read_matches(cfg["data"]["historical_results"])
    ratings = read_adjusted_ratings(run_dir / "team_adjustments.csv")
    beta = [float(value) for value in manifest["coefficients"]]
    form = initial_form(historical, fixtures, as_of)
    completed = completed_group_metrics(groups, fixtures, as_of)
    rng = random.Random(cfg["forecast"]["seed"])
    metrics = defaultdict(lambda: defaultdict(Counter))

    for _ in range(cfg["forecast"]["simulations"]):
        simulated_form = form.copy()
        for group, teams in groups.items():
            table = {
                team: {
                    "points": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "gf": 0,
                    "ga": 0,
                }
                for team in teams
            }
            for match in sorted(
                (fixture for fixture in fixtures if fixture["group"] == group),
                key=lambda fixture: fixture["date"],
            ):
                if match["date"] <= as_of and match["home_score"] is not None:
                    home_score, away_score = match["home_score"], match["away_score"]
                else:
                    home_score, away_score = sample_score(
                        rng,
                        match["home_team"],
                        match["away_team"],
                        match["venue_advantage"],
                        ratings,
                        beta,
                        simulated_form,
                        cfg,
                    )
                add_result(
                    table,
                    match["home_team"],
                    match["away_team"],
                    home_score,
                    away_score,
                )
                simulated_form[match["home_team"]] = home_score > away_score
                simulated_form[match["away_team"]] = away_score > home_score
            for team in teams:
                metrics[group][team]["points"] += table[team]["points"]
                metrics[group][team]["wins"] += table[team]["wins"]
                metrics[group][team]["draws"] += table[team]["draws"]
                metrics[group][team]["losses"] += table[team]["losses"]
                metrics[group][team]["goal_difference"] += table[team]["gf"] - table[team]["ga"]
                metrics[group][team]["goals_for"] += table[team]["gf"]
                metrics[group][team]["goals_against"] += table[team]["ga"]

    simulations = cfg["forecast"]["simulations"]
    tables = {}
    for group, teams in groups.items():
        rows = []
        for team in teams:
            rows.append(
                {
                    "team": team,
                    "wins": completed[group][team]["wins"],
                    "draws": completed[group][team]["draws"],
                    "losses": completed[group][team]["losses"],
                    "goals_for": completed[group][team]["gf"],
                    "goals_against": completed[group][team]["ga"],
                    "expected_wins": metrics[group][team]["wins"] / simulations,
                    "expected_draws": metrics[group][team]["draws"] / simulations,
                    "expected_losses": metrics[group][team]["losses"] / simulations,
                    "expected_goals_for": metrics[group][team]["goals_for"] / simulations,
                    "expected_goals_against": metrics[group][team]["goals_against"] / simulations,
                    "expected_points": metrics[group][team]["points"] / simulations,
                    "expected_goal_difference": metrics[group][team]["goal_difference"] / simulations,
                }
            )
        ranked = sorted(
            rows,
            key=lambda row: (
                row["expected_points"],
                row["expected_goal_difference"],
                row["expected_goals_for"],
                ratings[row["team"]],
            ),
            reverse=True,
        )
        tables[group] = [
            {**row, "position": position}
            for position, row in enumerate(ranked, 1)
        ]
    return tables


def group_card(
    x: float,
    y: float,
    group: str,
    rows: list[dict[str, Any]],
    flags_dir: Path,
    flag_cache: dict[str, str],
) -> str:
    header_height = 38
    columns_height = 26
    bottom_margin = 7
    row_height = (CARD_HEIGHT - header_height - columns_height - bottom_margin) / 4
    metric_x = {
        "W": x + 480,
        "D": x + 515,
        "L": x + 550,
        "GF:GA": x + 600,
        "xW": x + 655,
        "xD": x + 690,
        "xL": x + 725,
        "xGF:xGA": x + 785,
        "xGD": x + 855,
        "xPTS": x + 920,
    }
    out = [
        '<g filter="url(#softShadow)">',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" '
        'rx="10" fill="#f8fbfd" stroke="#c8d1da" stroke-width="1.4"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{CARD_WIDTH}" height="{header_height}" '
        f'rx="10" fill="{NAVY}"/>',
        f'<rect x="{x:.1f}" y="{y + header_height - 10:.1f}" width="{CARD_WIDTH}" '
        f'height="10" fill="{NAVY}"/>',
        text(x + 18, y + 20, f"GROUP {group}", 18, "#ffffff", 800),
        text(x + 35, y + header_height + columns_height / 2, "POS", 11, MUTED, 800, "middle"),
        text(x + 72, y + header_height + columns_height / 2, "TEAM", 11, MUTED, 800),
    ]
    for label, label_x in metric_x.items():
        out.append(
            text(label_x, y + header_height + columns_height / 2, label, 11, MUTED, 800, "middle")
        )
    for index, row in enumerate(rows):
        row_y = y + header_height + columns_height + index * row_height
        row_centre = row_y + row_height / 2
        qualified = row["position"] <= 2
        fill = "#fff7e8" if qualified else "#ffffff"
        out.append(
            f'<rect x="{x + 11:.1f}" y="{row_y:.1f}" width="{CARD_WIDTH - 22:.1f}" '
            f'height="{row_height:.1f}" fill="{fill}" stroke="#e7edf2" stroke-width="1"/>'
        )
        if qualified:
            out.append(
                f'<rect x="{x + 11:.1f}" y="{row_y:.1f}" width="5" '
                f'height="{row_height:.1f}" fill="{GOLD}"/>'
            )
        out.extend(
            [
                text(
                    x + 35,
                    row_centre + 0.5,
                    str(row["position"]),
                    13,
                    INK,
                    800 if qualified else 600,
                    "middle",
                ),
                flag(flags_dir, row["team"], x + 72, row_y + 2.5, 32, 16, flag_cache),
                text(
                    x + 114,
                    row_centre + 0.5,
                    display_name(row["team"]),
                    13 if len(display_name(row["team"])) <= 18 else 11,
                    INK,
                    700 if qualified else 500,
                ),
                text(metric_x["W"], row_centre, str(row["wins"]), 13, INK, 600, "middle"),
                text(metric_x["D"], row_centre, str(row["draws"]), 13, INK, 600, "middle"),
                text(metric_x["L"], row_centre, str(row["losses"]), 13, INK, 600, "middle"),
                text(
                    metric_x["GF:GA"],
                    row_centre,
                    f'{row["goals_for"]}:{row["goals_against"]}',
                    13,
                    INK,
                    600,
                    "middle",
                ),
                text(metric_x["xW"], row_centre, f'{row["expected_wins"]:.1f}', 13, INK, 600, "middle"),
                text(metric_x["xD"], row_centre, f'{row["expected_draws"]:.1f}', 13, INK, 600, "middle"),
                text(metric_x["xL"], row_centre, f'{row["expected_losses"]:.1f}', 13, INK, 600, "middle"),
                text(
                    metric_x["xGF:xGA"],
                    row_centre,
                    f'{row["expected_goals_for"]:.1f}:{row["expected_goals_against"]:.1f}',
                    13,
                    INK,
                    600,
                    "middle",
                ),
                text(
                    metric_x["xGD"],
                    row_centre,
                    f'{row["expected_goal_difference"]:+.1f}',
                    13,
                    INK,
                    600,
                    "middle",
                ),
                text(
                    metric_x["xPTS"],
                    row_centre,
                    f'{row["expected_points"]:.1f}',
                    13,
                    INK,
                    700,
                    "middle",
                ),
            ]
        )
    out.append(
        f'<line x1="{x + 628:.1f}" y1="{y + header_height:.1f}" '
        f'x2="{x + 628:.1f}" y2="{y + CARD_HEIGHT - bottom_margin:.1f}" '
        'stroke="#d8e0e7" stroke-width="1"/>'
    )
    out.append("</g>")
    return "".join(out)


def draw_svg(
    output: Path,
    tables: dict[str, list[dict[str, Any]]],
    manifest: dict[str, Any],
    flags_dir: Path,
) -> None:
    simulations = int(manifest["simulations"])
    as_of = str(manifest["as_of"])
    flag_cache: dict[str, str] = {}
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        defs(),
        '<style>text{font-family:"Fira Sans","Avenir Next","Helvetica Neue",Arial,sans-serif;'
        "letter-spacing:0}</style>",
        *background(),
        text(1200, 88, "WORLD CUP", 118, INK, 900, "middle"),
        text(1200, 208, "2026", 182, "#ed1b2f", 900, "middle"),
        text(
            1200,
            292,
            f"Expected group tables from {simulations:,} simulations · as at {as_of}",
            23,
            MUTED,
            500,
            "middle",
        ),
    ]
    for column_x, groups in [(140, LEFT_GROUPS), (1310, RIGHT_GROUPS)]:
        for index, group in enumerate(groups):
            svg.append(
                group_card(
                    column_x,
                    340 + index * (CARD_HEIGHT + CARD_GAP),
                    group,
                    tables[group],
                    flags_dir,
                    flag_cache,
                )
            )
    svg.extend(
        [
            text(
                1200,
                1578,
                "Bold rows qualify automatically. W/D/L and GF:GA are to date; x metrics are "
                "expected final values. Tables rank by xPTS, then xGD, then xGF.",
                18,
                MUTED,
                500,
                "middle",
                0.86,
            ),
            watermark(),
            "</svg>",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--flags-dir", type=Path, default=Path("outputs/flags"))
    args = parser.parse_args()
    svg_path = args.run_dir / "most_likely_group_tables.svg"
    draw_svg(
        svg_path,
        simulate_group_tables(args.run_dir, read_manifest(args.run_dir / "run_manifest.json")),
        read_manifest(args.run_dir / "run_manifest.json"),
        args.flags_dir,
    )
    render_png(svg_path, args.run_dir / "most_likely_group_tables.png")


if __name__ == "__main__":
    main()
