from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import yaml  # pyright: ignore[reportMissingModuleSource]

from wc_forecaster.data import read_matches, write_csv
from wc_forecaster.model import fit, lambdas, poisson_probs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/model.yaml"
TOP_N = 10


def outcome(match: dict[str, Any]) -> str:
    return (
        "home"
        if match["home_score"] > match["away_score"]
        else "draw"
        if match["home_score"] == match["away_score"]
        else "away"
    )


def snapshot_dates(output_dir: Path) -> list[date]:
    return sorted(
        date.fromisoformat(path.name)
        for path in output_dir.iterdir()
        if path.is_dir() and (path / "group_fixture_1x2_probabilities.csv").exists()
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def snapshot(
    snapshot_date: date,
    cfg: dict[str, Any],
    training: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    run_dir = Path(cfg["data"]["output_dir"]) / snapshot_date.isoformat()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    tuning = json.loads((run_dir / "tuning_summary.json").read_text(encoding="utf-8"))
    snapshot_cfg = deepcopy(cfg)
    snapshot_cfg["fit"]["half_life"] = tuning["selected_half_life"]
    snapshot_cfg["goals"]["min_expected_goals"] = tuning["selected_min_expected_goals"]
    _, _, previous_win = fit(training, snapshot_cfg, snapshot_date)
    for match in fixtures:
        if match["date"] <= snapshot_date and match["home_score"] is not None:
            previous_win[match["home_team"]] = match["home_score"] > match["away_score"]
            previous_win[match["away_team"]] = match["away_score"] > match["home_score"]
    return {
        "probabilities": {
            row["match_no"]: {
                "home": float(row["home"]),
                "draw": float(row["draw"]),
                "away": float(row["away"]),
            }
            for row in read_csv(run_dir / "group_fixture_1x2_probabilities.csv")
        },
        "ratings": {
            row["team"]: float(row["adjusted_rating"])
            for row in read_csv(run_dir / "team_adjustments.csv")
        },
        "beta": manifest["coefficients"],
        "previous_win": previous_win,
        "cfg": snapshot_cfg,
    }


def score_probability(
    home_score: int,
    away_score: int,
    home_probabilities: list[float],
    away_probabilities: list[float],
) -> float:
    return home_probabilities[home_score] * away_probabilities[away_score]


def winning_margin_probability(
    home_score: int,
    away_score: int,
    home_probabilities: list[float],
    away_probabilities: list[float],
) -> float:
    margin = abs(home_score - away_score)
    home_won = home_score > away_score
    return sum(
        home_probability * away_probability
        for predicted_home, home_probability in enumerate(home_probabilities)
        for predicted_away, away_probability in enumerate(away_probabilities)
        if (
            predicted_home - predicted_away >= margin
            if home_won
            else predicted_away - predicted_home >= margin
        )
    )


def ranked(rows: list[dict[str, Any]], probability: str) -> list[dict[str, Any]]:
    return [
        {"rank": rank, **row}
        for rank, row in enumerate(sorted(rows, key=lambda row: row[probability])[:TOP_N], 1)
    ]


def print_table(title: str, rows: list[dict[str, Any]], probability: str) -> None:
    print(f"\n{title}")
    print(f"{'rank':>4}  {'date':<10}  {'result':<43}  {'xG':>11}  {'probability':>11}")
    for row in rows:
        result = (
            f"{row['home_team']} {row['home_score']}-{row['away_score']} "
            f"{row['away_team']}"
        )
        expected_goals = (
            f"{row['home_expected_goals']:.2f}-{row['away_expected_goals']:.2f}"
        )
        print(
            f"{row['rank']:>4}  {row['date']:<10}  {result:<43}  "
            f"{expected_goals:>11}  {row[probability]:>10.2%}"
        )


def main() -> None:
    with CONFIG.open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    cfg["data"] = {
        key: str(ROOT / value) for key, value in cfg["data"].items() if key != "output_dir"
    } | {"output_dir": str(ROOT / cfg["data"]["output_dir"])}
    historical = read_matches(cfg["data"]["historical_results"])
    training = [
        match
        for match in historical
        if not (
            match["date"].year == 2026 and match["tournament"] == "FIFA World Cup"
        )
    ]
    fixtures = read_matches(cfg["data"]["fixtures"])
    completed = [match for match in fixtures if match["home_score"] is not None]
    dates = snapshot_dates(Path(cfg["data"]["output_dir"]))
    snapshots: dict[date, dict[str, Any]] = {}
    outcome_rows = []
    exact_score_rows = []
    winning_margin_rows = []

    for match in completed:
        forecast_date = max(
            snapshot_date for snapshot_date in dates if snapshot_date < match["date"]
        )
        if forecast_date not in snapshots:
            snapshots[forecast_date] = snapshot(forecast_date, cfg, training, fixtures)
        forecast = snapshots[forecast_date]
        probabilities = forecast["probabilities"][match["match_no"]]
        actual_outcome = outcome(match)
        expected_outcome = max(probabilities, key=probabilities.__getitem__)
        home_expected_goals, away_expected_goals = lambdas(
            match["home_team"],
            match["away_team"],
            match["venue_advantage"],
            forecast["ratings"],
            forecast["beta"],
            forecast["previous_win"],
            forecast["cfg"],
        )
        home_probabilities = poisson_probs(
            home_expected_goals, forecast["cfg"]["goals"]["score_cap"]
        )
        away_probabilities = poisson_probs(
            away_expected_goals, forecast["cfg"]["goals"]["score_cap"]
        )
        row = {
            "match_no": match["match_no"],
            "date": match["date"].isoformat(),
            "home_team": match["home_team"],
            "away_team": match["away_team"],
            "home_score": match["home_score"],
            "away_score": match["away_score"],
            "forecast_as_of": forecast_date.isoformat(),
            "home_expected_goals": home_expected_goals,
            "away_expected_goals": away_expected_goals,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
        }
        if actual_outcome != expected_outcome:
            outcome_rows.append(
                {**row, "outcome_probability": probabilities[actual_outcome]}
            )
        exact_score_rows.append(
            {
                **row,
                "exact_score_probability": score_probability(
                    match["home_score"],
                    match["away_score"],
                    home_probabilities,
                    away_probabilities,
                ),
            }
        )
        if actual_outcome != "draw":
            winning_margin_rows.append(
                {
                    **row,
                    "winning_margin_probability": winning_margin_probability(
                        match["home_score"],
                        match["away_score"],
                        home_probabilities,
                        away_probabilities,
                    ),
                }
            )

    outcome_upsets = ranked(outcome_rows, "outcome_probability")
    exact_score_upsets = ranked(exact_score_rows, "exact_score_probability")
    winning_margin_upsets = ranked(
        winning_margin_rows, "winning_margin_probability"
    )
    output_dir = Path(cfg["data"]["output_dir"])
    write_csv(output_dir / "outcome_upsets.csv", outcome_upsets)
    write_csv(output_dir / "exact_score_upsets.csv", exact_score_upsets)
    write_csv(output_dir / "winning_margin_upsets.csv", winning_margin_upsets)
    print_table("Outcome upsets", outcome_upsets, "outcome_probability")
    print_table(
        "Exact-score upsets", exact_score_upsets, "exact_score_probability"
    )
    print_table(
        "Winning-margin upsets",
        winning_margin_upsets,
        "winning_margin_probability",
    )


if __name__ == "__main__":
    main()
