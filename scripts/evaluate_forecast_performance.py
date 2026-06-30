from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def predicted_outcome(row: dict[str, str]) -> str:
    return max(("home", "draw", "away"), key=lambda key: float(row[key]))


def forecasts_by_match(outputs_dir: Path) -> dict[int, list[tuple[date, dict[str, str]]]]:
    forecasts: dict[int, list[tuple[date, dict[str, str]]]] = {}
    for path in sorted(outputs_dir.glob("*/next_matchday_summary.csv")):
        snapshot_date = date.fromisoformat(path.parent.name)
        for row in read_csv(path):
            forecasts.setdefault(int(row["match_no"]), []).append((snapshot_date, row))
    return forecasts


def completed_fixtures(fixtures_path: Path, as_of: date) -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(fixtures_path)
        if row["home_score"] and row["away_score"] and date.fromisoformat(row["date"]) <= as_of
    ]


def evaluate(fixtures_path: Path, outputs_dir: Path, as_of: date) -> tuple[int, int, int, int]:
    forecasts = forecasts_by_match(outputs_dir)
    evaluated = outcome_hits = exact_score_hits = missing_forecasts = 0
    for fixture in completed_fixtures(fixtures_path, as_of):
        fixture_date = date.fromisoformat(fixture["date"])
        candidates = [
            forecast
            for forecast in forecasts.get(int(fixture["match_no"]), [])
            if forecast[0] < fixture_date
        ]
        if not candidates:
            missing_forecasts += 1
            continue
        _, forecast = max(candidates, key=lambda item: item[0])
        home_score, away_score = int(fixture["home_score"]), int(fixture["away_score"])
        evaluated += 1
        outcome_hits += predicted_outcome(forecast) == outcome(home_score, away_score)
        exact_score_hits += forecast["score"] == f"{home_score}-{away_score}"
    return evaluated, outcome_hits, exact_score_hits, missing_forecasts


def pct(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "data/world_cup_2026/fixtures.csv")
    parser.add_argument("--outputs-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()
    evaluated, outcome_hits, exact_score_hits, missing_forecasts = evaluate(
        args.fixtures,
        args.outputs_dir,
        args.as_of,
    )
    print(f"Forecast performance through {args.as_of}")
    print(f"Evaluated fixtures: {evaluated}")
    print(f"Outcome accuracy: {outcome_hits}/{evaluated} ({pct(outcome_hits, evaluated)})")
    print(f"Exact score accuracy: {exact_score_hits}/{evaluated} ({pct(exact_score_hits, evaluated)})")
    print(f"Missing pre-match forecasts: {missing_forecasts}")


if __name__ == "__main__":
    main()
