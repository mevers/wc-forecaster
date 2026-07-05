from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.deep_dive_knockout_bracket_methods import (
    KnockoutMatch,
    PredictedMatch,
    checkpoint_cutoff,
    deterministic_forecast,
    prediction_rows_for,
    validate_metadata,
)


def match(
    round_name: str,
    slot: str,
    home: str,
    away: str,
    advancer: str,
    parent_left: str = "",
    parent_right: str = "",
) -> KnockoutMatch:
    return KnockoutMatch(
        "Cup",
        "2099",
        2099,
        round_name,
        slot,
        date(2099, 7, 1),
        home,
        away,
        1,
        1,
        advancer,
        parent_left,
        parent_right,
    )


def test_validate_metadata_catches_missing_historical_row() -> None:
    try:
        validate_metadata([match("R16", "R16_1", "A", "B", "A")], [])
    except ValueError as exc:
        assert "Metadata row not found" in str(exc)
    else:
        raise AssertionError("Expected missing metadata row to raise ValueError")


def test_prediction_rows_treat_reversed_pairing_as_correct() -> None:
    actual = match("QF", "QF_1", "A", "B", "B")
    predicted = {
        "QF_1": PredictedMatch("QF", "QF_1", "B", "A", "B", 0.55, 0.45),
    }

    rows = prediction_rows_for("Cup", "2099", "after-r16", "QF", "expected-table", predicted, {"QF_1": actual})

    assert rows[0]["pairing_correct"] is True
    assert rows[0]["advancer_correct"] is True
    assert rows[0]["pairing_and_advancer_correct"] is True


def test_prediction_rows_use_curated_advancer_not_draw_score() -> None:
    actual = match("QF", "QF_1", "A", "B", "B")
    predicted = {
        "QF_1": PredictedMatch("QF", "QF_1", "A", "B", "A", 0.55, 0.45),
    }

    rows = prediction_rows_for("Cup", "2099", "after-r16", "QF", "expected-table", predicted, {"QF_1": actual})

    assert rows[0]["actual_advancer"] == "B"
    assert rows[0]["advancer_correct"] is False


def test_checkpoint_cutoff_excludes_later_target_rounds() -> None:
    tournament_matches = [
        {"date": date(2099, 6, 20)},
        {"date": date(2099, 6, 21)},
        {"date": date(2099, 6, 25)},
        {"date": date(2099, 7, 1)},
    ]
    knockout_matches = [
        match("R16", "R16_1", "A", "B", "A"),
        match("QF", "QF_1", "A", "C", "A", "R16_1", "R16_2"),
    ]

    assert checkpoint_cutoff(tournament_matches, knockout_matches, "R16") == date(2099, 6, 25)
    assert checkpoint_cutoff(tournament_matches, knockout_matches, "QF") == date(2099, 7, 1)


def test_deterministic_forecast_propagates_parent_winners() -> None:
    knockout_matches = [
        match("QF", "QF_1", "A", "B", "A"),
        match("QF", "QF_2", "C", "D", "C"),
        match("QF", "QF_3", "E", "F", "E"),
        match("QF", "QF_4", "G", "H", "G"),
        match("SF", "SF_1", "A", "C", "A", "QF_1", "QF_2"),
        match("SF", "SF_2", "E", "G", "E", "QF_3", "QF_4"),
        match("F", "F_1", "A", "E", "A", "SF_1", "SF_2"),
    ]

    def fake_advancement(team_a: str, team_b: str, *_args: object) -> tuple[float, float]:
        winners = {"A", "C", "E", "G"}
        return (0.9, 0.1) if team_a in winners else (0.1, 0.9)

    with patch(
        "scripts.deep_dive_knockout_bracket_methods.advancement_probabilities",
        fake_advancement,
    ):
        predicted = deterministic_forecast(knockout_matches, "QF", {}, [], {}, {})

    assert predicted["SF_1"].teams == frozenset(("A", "C"))
    assert predicted["SF_2"].teams == frozenset(("E", "G"))
    assert predicted["F_1"].teams == frozenset(("A", "E"))
    assert predicted["F_1"].winner == "A"
