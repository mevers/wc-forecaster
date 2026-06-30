from __future__ import annotations

import argparse
import csv
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

R32_MATCHES = range(73, 89)
RATING_START = "2026-06-10"
RATING_END = "2026-06-28"
METHODS = ("expected-table", "modal-group-table")
METHOD_LABELS = {
    "expected-table": "Expected table",
    "modal-group-table": "Modal group table",
}
COLOURS = {
    "Expected table": "#1f4e79",
    "Modal group table": "#d95f02",
    "R32 teams": "#218380",
    "R32 fixtures": "#1f4e79",
    "consistently up": "#218380",
    "consistently down": "#9b2226",
    "fluctuating": "#d95f02",
    "flat": "#697586",
}


@dataclass(frozen=True)
class Pair:
    team_a: str
    team_b: str

    @property
    def teams(self) -> frozenset[str]:
        return frozenset((self.team_a, self.team_b))

    def display(self) -> str:
        return f"{self.team_a} v {self.team_b}"


def read_actual(path: Path) -> dict[int, Pair]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            int(row["match_no"]): Pair(row["home"], row["away"])
            for row in csv.DictReader(handle)
            if row["group"] == "R32"
        }


def read_tournament_teams(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row["team"] for row in csv.DictReader(handle)]


def rating_baseline(path: Path, tournament_teams: list[str], actual: dict[int, Pair]) -> dict[str, Any]:
    actual_teams = {team for pair in actual.values() for team in pair.teams}
    tournament_set = set(tournament_teams)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            row
            for row in csv.DictReader(row for row in handle if not row.startswith("#"))
            if row["team"] in tournament_set
        ]
    top32 = {row["team"] for row in rows[:32]}
    return {
        "correct": len(top32 & actual_teams),
        "missed": sorted(actual_teams - top32),
        "extra": sorted(top32 - actual_teams),
    }


def read_ratings(path: Path) -> dict[str, float]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["team"]: float(row["rating"])
            for row in csv.DictReader(row for row in handle if not row.startswith("#"))
        }


def movement_pattern(deltas: list[float]) -> str:
    nonzero = [delta for delta in deltas if delta != 0]
    if not nonzero:
        return "flat"
    if all(delta > 0 for delta in nonzero):
        return "consistently up"
    if all(delta < 0 for delta in nonzero):
        return "consistently down"
    return "fluctuating"


def rating_change_summary(outputs_dir: Path, actual: dict[int, Pair]) -> list[dict[str, Any]]:
    actual_teams = sorted({team for pair in actual.values() for team in pair.teams})
    snapshots = [
        (path.parent.name, read_ratings(path))
        for path in sorted(outputs_dir.glob("*/derived_team_ratings.csv"))
        if RATING_START <= path.parent.name <= RATING_END
    ]
    rows = []
    for team in actual_teams:
        ratings = [snapshot[team] for _, snapshot in snapshots]
        deltas = [round(ratings[index + 1] - ratings[index], 1) for index in range(len(ratings) - 1)]
        positive_moves = sum(delta > 0 for delta in deltas)
        negative_moves = sum(delta < 0 for delta in deltas)
        gross_rating_movement = round(sum(abs(delta) for delta in deltas), 1)
        nonzero_moves = positive_moves + negative_moves
        rating_change = round(ratings[-1] - ratings[0], 1)
        rows.append(
            {
                "team": team,
                "start_rating": ratings[0],
                "end_rating": ratings[-1],
                "rating_change": rating_change,
                "gross_rating_movement": gross_rating_movement,
                "directional_efficiency": round(
                    rating_change / gross_rating_movement if gross_rating_movement else 0.0,
                    3,
                ),
                "directional_balance": round(
                    (positive_moves - negative_moves) / nonzero_moves if nonzero_moves else 0.0,
                    3,
                ),
                "positive_moves": positive_moves,
                "negative_moves": negative_moves,
                "flat_days": sum(delta == 0 for delta in deltas),
                "movement_pattern": movement_pattern(deltas),
                "largest_daily_gain": max(deltas),
                "largest_daily_loss": min(deltas),
            }
        )
    return [
        {**row, "rank_by_rating_change": rank}
        for rank, row in enumerate(
            sorted(rows, key=lambda row: row["rating_change"], reverse=True),
            start=1,
        )
    ]


def read_predictions(path: Path) -> dict[str, dict[int, Pair]]:
    out = {method: {} for method in METHODS}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            method = row["bracket_method"]
            match_no = int(row["match_no"])
            if method in out and match_no in R32_MATCHES:
                out[method][match_no] = Pair(row["team_a"], row["team_b"])
    for method, rows in out.items():
        missing = sorted(set(R32_MATCHES) - rows.keys())
        if missing:
            raise ValueError(f"{path} is missing {method} R32 slots: {missing}")
    return out


def compare_slots(actual: dict[int, Pair], predicted: dict[int, Pair]) -> list[dict[str, Any]]:
    actual_pair_slots = {pair.teams: match_no for match_no, pair in actual.items()}
    rows = []
    for match_no in sorted(actual):
        actual_pair = actual[match_no]
        predicted_pair = predicted[match_no]
        missing = sorted(actual_pair.teams - predicted_pair.teams)
        extra = sorted(predicted_pair.teams - actual_pair.teams)
        elsewhere = actual_pair_slots.get(predicted_pair.teams)
        rows.append(
            {
                "match_no": match_no,
                "actual_pair": actual_pair.display(),
                "predicted_pair": predicted_pair.display(),
                "right_spot": predicted_pair.teams == actual_pair.teams,
                "right_order": predicted_pair == actual_pair,
                "actual_teams_found": len(actual_pair.teams & predicted_pair.teams),
                "missing_actual_teams": ", ".join(missing) if missing else "-",
                "extra_predicted_teams": ", ".join(extra) if extra else "-",
                "predicted_pair_actual_elsewhere": elsewhere if elsewhere and elsewhere != match_no else "-",
            }
        )
    return rows


def summarise(as_of: str, method: str, actual: dict[int, Pair], predicted: dict[int, Pair]) -> dict[str, Any]:
    rows = compare_slots(actual, predicted)
    actual_teams = {team for pair in actual.values() for team in pair.teams}
    predicted_teams = {team for pair in predicted.values() for team in pair.teams}
    correct_slots = [row["match_no"] for row in rows if row["right_spot"]]
    missed_slots = [row["match_no"] for row in rows if not row["right_spot"]]
    ordered_slots = [row["match_no"] for row in rows if row["right_order"]]
    wrong_slot_pairs = [row["match_no"] for row in rows if row["predicted_pair_actual_elsewhere"] != "-"]
    return {
        "as_of": as_of,
        "method": method,
        "r32_team_accuracy": len(actual_teams & predicted_teams) / len(actual_teams),
        "slot_pair_accuracy": len(correct_slots) / len(actual),
        "correct_slots": correct_slots,
        "missed_slots": missed_slots,
        "ordered_pair_accuracy": len(ordered_slots) / len(actual),
        "ordered_correct_slots": ordered_slots,
        "team_place_accuracy": sum(row["actual_teams_found"] for row in rows) / (2 * len(actual)),
        "actual_r32_teams_predicted": len(actual_teams & predicted_teams),
        "wrong_slot_pairs": wrong_slot_pairs,
    }


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def count(value: float, total: int) -> str:
    return f"{value * total:.1f}/{total}"


def slots(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "-"


def load_plotnine() -> tuple[Any, Any]:
    try:
        return importlib.import_module("plotnine"), importlib.import_module("polars")
    except ModuleNotFoundError as exc:
        raise SystemExit("plotnine and polars are required to generate retro PNG charts. Install the project dependencies with `python3 -m pip install -e .`.") from exc


def retro_theme(p9: Any) -> Any:
    return (
        p9.theme_minimal(base_size=9)
        + p9.theme(
            figure_size=(8.8, 3.4),
            plot_background=p9.element_rect(fill="#fbfcfd", color="#fbfcfd"),
            panel_background=p9.element_rect(fill="#ffffff", color="#ffffff"),
            panel_grid_major_x=p9.element_blank(),
            panel_grid_minor=p9.element_blank(),
            panel_grid_major_y=p9.element_line(color="#e3e8ef", size=0.4),
            axis_title=p9.element_blank(),
            legend_title=p9.element_blank(),
            legend_position=(0.78, 0.82),
        )
    )


def save_plot(plot: Any, path: Path, width: float = 8.8, height: float = 3.4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plot.save(str(path), width=width, height=height, dpi=180, verbose=False)


def line_chart(
    path: Path,
    lower: int,
    upper: int,
    ticks: list[int],
    summary_rows: list[dict[str, Any]],
    value_key: str,
) -> None:
    p9, pl = load_plotnine()
    dates = sorted({row["as_of"] for row in summary_rows})

    def value(row: dict[str, Any]) -> float:
        return len(row["correct_slots"]) if value_key == "correct_slots" else float(row[value_key])

    rows = [
        {
            "day_index": dates.index(row["as_of"]),
            "as_of": row["as_of"],
            "method": METHOD_LABELS[row["method"]],
            "value": value(row),
        }
        for row in summary_rows
    ]
    tick_indexes = [0, 3, 6, 9, 12, 15, len(dates) - 1]
    right_labels = pl.DataFrame(
        {
            "day_index": [len(dates) - 0.35 for _ in ticks],
            "value": ticks,
            "label": [pct(tick / upper) for tick in ticks],
        }
    )
    plot = (
        p9.ggplot(pl.DataFrame(rows), p9.aes("day_index", "value", color="method"))
        + p9.geom_rect(
            data=pl.DataFrame(
                [{"xmin": len(dates) - 1.15, "xmax": len(dates) - 0.85, "ymin": lower, "ymax": upper}]
            ),
            mapping=p9.aes(xmin="xmin", xmax="xmax", ymin="ymin", ymax="ymax"),
            inherit_aes=False,
            fill="#f3f5f7",
            alpha=0.9,
        )
        + p9.geom_line(size=1.05)
        + p9.geom_point(size=1.9, fill="#ffffff")
        + p9.geom_text(
            data=right_labels,
            mapping=p9.aes("day_index", "value", label="label"),
            inherit_aes=False,
            ha="left",
            size=7,
            color="#697586",
        )
        + p9.scale_color_manual(values=COLOURS)
        + p9.scale_x_continuous(
            breaks=tick_indexes,
            labels=[dates[index][5:] for index in tick_indexes],
            limits=(-0.4, len(dates) + 0.55),
        )
        + p9.scale_y_continuous(breaks=ticks, limits=(lower, upper))
        + retro_theme(p9)
    )
    if value_key == "actual_r32_teams_predicted":
        plot = plot + p9.geom_hline(yintercept=25, linetype="dashed", color="#a7b1bc") + p9.annotate(
            "text",
            x=0.55,
            y=25.35,
            label="Ratings baseline: 25/32",
            ha="left",
            size=7,
            color="#364152",
        )
    if value_key == "correct_slots":
        plot = plot + p9.annotate(
            "text",
            x=7.45,
            y=9.1,
            label="Expected-table dip\nBrazil/Morocco slot swap",
            ha="left",
            size=7,
            color="#364152",
        )
    save_plot(plot, path)


def slope_chart(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    p9, pl = load_plotnine()
    dates = ("2026-06-25", "2026-06-26")
    rows = []
    for label, metric, total in (
        ("R32 teams", "r32_team_accuracy", 32),
        ("R32 fixtures", "slot_pair_accuracy", 16),
    ):
        for day_index, as_of in enumerate(dates):
            row = next(
                row
                for row in summary_rows
                if row["as_of"] == as_of and row["method"] == "expected-table"
            )
            rows.append(
                {
                    "day_index": day_index,
                    "metric": label,
                    "value": row[metric],
                    "label": f"{count(row[metric], total)} ({pct(row[metric])})",
                }
            )
    plot = (
        p9.ggplot(pl.DataFrame(rows), p9.aes("day_index", "value", color="metric", group="metric"))
        + p9.geom_line(size=1.05)
        + p9.geom_point(size=2.2)
        + p9.geom_text(p9.aes(label="label"), nudge_y=0.025, size=7)
        + p9.scale_color_manual(values=COLOURS)
        + p9.scale_x_continuous(breaks=[0, 1], labels=["25 Jun", "26 Jun"], limits=(-0.15, 1.15))
        + p9.scale_y_continuous(
            breaks=[0.625, 0.75, 0.875, 1.0],
            labels=["62.5%", "75.0%", "87.5%", "100.0%"],
            limits=(0.55, 1.02),
        )
        + retro_theme(p9)
    )
    save_plot(plot, path, width=7.6, height=3.2)


def method_chart(path: Path, summary_rows: list[dict[str, Any]]) -> None:
    p9, pl = load_plotnine()
    pre_final = [row for row in summary_rows if row["as_of"] < "2026-06-27"]
    windows = [
        ("10-17 Jun", "2026-06-10", "2026-06-17"),
        ("18-23 Jun", "2026-06-18", "2026-06-23"),
        ("24-26 Jun", "2026-06-24", "2026-06-26"),
    ]
    rows = []
    for label, start, end in windows:
        for method in METHODS:
            window_rows = [
                row
                for row in pre_final
                if row["method"] == method and start <= row["as_of"] <= end
            ]
            avg = sum(row["slot_pair_accuracy"] for row in window_rows) / len(window_rows)
            rows.append(
                {
                    "window": label,
                    "method": METHOD_LABELS[method],
                    "value": avg,
                    "label": pct(avg),
                }
            )
    plot = (
        p9.ggplot(pl.DataFrame(rows), p9.aes("window", "value", fill="method"))
        + p9.geom_col(position=p9.position_dodge(width=0.7), width=0.58)
        + p9.geom_text(
            p9.aes(label="label"),
            position=p9.position_dodge(width=0.7),
            va="bottom",
            size=7,
        )
        + p9.scale_fill_manual(values=COLOURS)
        + p9.scale_y_continuous(
            breaks=[0, 0.25, 0.5, 0.75, 1.0],
            labels=["0.0%", "25.0%", "50.0%", "75.0%", "100.0%"],
            limits=(0, 1.05),
        )
        + retro_theme(p9)
    )
    save_plot(plot, path, width=8.2, height=3.3)


def rating_change_chart(path: Path, rating_rows: list[dict[str, Any]]) -> None:
    p9, pl = load_plotnine()
    rows = [
        {
            "team": row["team"],
            "rating_change": row["rating_change"],
            "movement_pattern": row["movement_pattern"],
        }
        for row in rating_rows
    ]
    plot = (
        p9.ggplot(pl.DataFrame(rows), p9.aes("reorder(team, rating_change)", "rating_change"))
        + p9.geom_col(p9.aes(fill="movement_pattern"), width=0.72)
        + p9.geom_hline(yintercept=0, color="#697586", size=0.45)
        + p9.coord_flip()
        + p9.scale_fill_manual(values=COLOURS)
        + p9.scale_y_continuous(breaks=[-30, 0, 30, 60], labels=["-30", "0", "+30", "+60"])
        + retro_theme(p9)
        + p9.theme(legend_position=(0.76, 0.16))
    )
    save_plot(plot, path, width=8.8, height=6.4)


def write_charts(
    summary_rows: list[dict[str, Any]],
    rating_rows: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    line_chart(
        output_dir / "r32_field_convergence.png",
        20,
        32,
        [20, 24, 28, 32],
        summary_rows,
        "actual_r32_teams_predicted",
    )
    line_chart(
        output_dir / "r32_fixture_convergence.png",
        0,
        16,
        [0, 4, 8, 12, 16],
        summary_rows,
        "correct_slots",
    )
    slope_chart(output_dir / "r32_late_instability.png", summary_rows)
    method_chart(output_dir / "r32_method_comparison.png", summary_rows)
    rating_change_chart(output_dir / "r32_rating_change_rankings.png", rating_rows)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis(
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    rating_rows: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    write_csv(
        output_dir / "r32_convergence_summary.csv",
        [
            "as_of",
            "method",
            "correct_r32_teams",
            "correct_r32_team_placements",
            "correct_r32_fixtures",
            "correct_r32_fixtures_percent",
            "correct_r32_fixture_slots",
            "missed_r32_fixture_slots",
            "correct_display_order_slots",
            "confirmed_fixture_predicted_elsewhere",
        ],
        [
            {
                "as_of": row["as_of"],
                "method": row["method"],
                "correct_r32_teams": f"{row['actual_r32_teams_predicted']}/32",
                "correct_r32_team_placements": f"{int(row['team_place_accuracy'] * 32)}/32",
                "correct_r32_fixtures": f"{len(row['correct_slots'])}/16",
                "correct_r32_fixtures_percent": pct(row["slot_pair_accuracy"]),
                "correct_r32_fixture_slots": slots(row["correct_slots"]),
                "missed_r32_fixture_slots": slots(row["missed_slots"]),
                "correct_display_order_slots": slots(row["ordered_correct_slots"]),
                "confirmed_fixture_predicted_elsewhere": slots(row["wrong_slot_pairs"]),
            }
            for row in summary_rows
        ],
    )
    write_csv(
        output_dir / "r32_convergence_slot_audit.csv",
        [
            "as_of",
            "method",
            "match_no",
            "confirmed_fixture",
            "predicted_fixture",
            "correct_fixture",
            "correct_display_order",
            "confirmed_teams_in_this_slot",
            "missing_confirmed_teams",
            "extra_predicted_teams",
            "confirmed_fixture_predicted_in_slot",
        ],
        [
            {
                "as_of": row["as_of"],
                "method": row["method"],
                "match_no": row["match_no"],
                "confirmed_fixture": row["actual_pair"],
                "predicted_fixture": row["predicted_pair"],
                "correct_fixture": "yes" if row["right_spot"] else "no",
                "correct_display_order": "yes" if row["right_order"] else "no",
                "confirmed_teams_in_this_slot": row["actual_teams_found"],
                "missing_confirmed_teams": row["missing_actual_teams"],
                "extra_predicted_teams": row["extra_predicted_teams"],
                "confirmed_fixture_predicted_in_slot": row["predicted_pair_actual_elsewhere"],
            }
            for row in detail_rows
        ],
    )
    write_csv(
        output_dir / "r32_ratings_baseline.csv",
        ["correct", "missed", "extra"],
        [
            {
                "correct": baseline["correct"],
                "missed": ", ".join(baseline["missed"]),
                "extra": ", ".join(baseline["extra"]),
            }
        ],
    )
    write_csv(
        output_dir / "r32_rating_change_summary.csv",
        [
            "rank_by_rating_change",
            "team",
            "start_rating",
            "end_rating",
            "rating_change",
            "gross_rating_movement",
            "directional_efficiency",
            "directional_balance",
            "movement_pattern",
            "positive_moves",
            "negative_moves",
            "flat_days",
            "largest_daily_gain",
            "largest_daily_loss",
        ],
        rating_rows,
    )


def discover_runs(outputs_dir: Path) -> list[tuple[str, dict[str, dict[int, Pair]]]]:
    runs = []
    for path in sorted(outputs_dir.glob("*/most_likely_knockout_bracket.csv")):
        as_of = path.parent.name
        if len(as_of) == 10 and as_of[4] == "-" and as_of[7] == "-":
            runs.append((as_of, read_predictions(path)))
    return runs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("data/world_cup_2026/fixtures.csv"))
    parser.add_argument("--groups", type=Path, default=Path("data/world_cup_2026/groups.csv"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/r32_bracket_convergence_retro"))
    args = parser.parse_args()

    actual = read_actual(args.fixtures)
    runs = discover_runs(args.outputs_dir)
    summary_rows = [
        summarise(as_of, method, actual, methods[method])
        for as_of, methods in runs
        for method in METHODS
    ]
    detail_rows = [
        {"as_of": as_of, "method": method, **row}
        for as_of, methods in runs
        for method in METHODS
        for row in compare_slots(actual, methods[method])
    ]
    baseline = rating_baseline(
        args.outputs_dir / "2026-06-10" / "derived_team_ratings.csv",
        read_tournament_teams(args.groups),
        actual,
    )
    rating_rows = rating_change_summary(args.outputs_dir, actual)
    write_analysis(summary_rows, detail_rows, baseline, rating_rows, args.output_dir)
    write_charts(summary_rows, rating_rows, args.output_dir)


if __name__ == "__main__":
    main()
