from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from scripts.evaluate_forecast_performance import evaluate, outcome


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture(match_no: int, match_date: str, home_score: int, away_score: int) -> dict[str, object]:
    return {
        "match_no": match_no,
        "group": "A",
        "date": match_date,
        "home": f"Home {match_no}",
        "away": f"Away {match_no}",
        "home_score": home_score,
        "away_score": away_score,
        "fixture_winner": "",
        "venue_advantage": 0,
    }


def forecast(match_no: int, match_date: str, home: float, draw: float, away: float, score: str) -> dict[str, object]:
    return {
        "date": match_date,
        "match_no": match_no,
        "group": "A",
        "home_team": f"Home {match_no}",
        "away_team": f"Away {match_no}",
        "home": home,
        "draw": draw,
        "away": away,
        "home_expected_goals": 1,
        "away_expected_goals": 1,
        "score": score,
    }


def test_outcome_classification() -> None:
    assert [outcome(2, 0), outcome(1, 1), outcome(0, 1)] == ["home", "draw", "away"]


def test_evaluate_uses_latest_pre_match_forecast_and_as_of_cutoff(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures.csv"
    outputs = tmp_path / "outputs"
    write_csv(
        fixtures,
        [
            fixture(1, "2026-06-11", 2, 0),
            fixture(2, "2026-06-12", 1, 1),
            fixture(3, "2026-06-13", 0, 1),
        ],
    )
    write_csv(outputs / "2026-06-10" / "next_matchday_summary.csv", [forecast(2, "2026-06-12", 0.8, 0.1, 0.1, "2-0")])
    write_csv(outputs / "2026-06-11" / "next_matchday_summary.csv", [forecast(2, "2026-06-12", 0.1, 0.8, 0.1, "1-1")])
    write_csv(outputs / "2026-06-12" / "next_matchday_summary.csv", [forecast(3, "2026-06-13", 0.1, 0.1, 0.8, "1-2")])

    assert evaluate(fixtures, outputs, date.fromisoformat("2026-06-12")) == (1, 1, 1, 1)


def test_evaluate_counts_exact_score_separately_from_outcome(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures.csv"
    outputs = tmp_path / "outputs"
    write_csv(fixtures, [fixture(1, "2026-06-11", 2, 0)])
    write_csv(outputs / "2026-06-10" / "next_matchday_summary.csv", [forecast(1, "2026-06-11", 0.8, 0.1, 0.1, "1-0")])

    assert evaluate(fixtures, outputs, date.fromisoformat("2026-06-11")) == (1, 1, 0, 0)
