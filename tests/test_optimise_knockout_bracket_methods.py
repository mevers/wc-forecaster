from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.deep_dive_knockout_bracket_methods import CHECKPOINTS
from scripts.optimise_knockout_bracket_methods import OPTIMISED_METHODS, aggregate_summary


def summary_row(
    checkpoint: str,
    method: str,
    qf_found: int = 0,
    champion_correct: bool = False,
) -> dict[str, object]:
    return {
        "checkpoint": checkpoint,
        "method": method,
        "qf_teams_found": qf_found,
        "qf_teams_possible": 8,
        "sf_teams_found": 0,
        "sf_teams_possible": 4,
        "f_teams_found": 0,
        "f_teams_possible": 2,
        "champion_correct": champion_correct,
        "progression_score": qf_found + int(champion_correct),
        "progression_possible": 15,
        "exact_remaining_bracket": False,
    }


def test_weighted_summary_values_later_rounds_more_than_qf_volume() -> None:
    fixture_rows = [
        summary_row(checkpoint, method)
        for checkpoint, _start_round in CHECKPOINTS
        for method in OPTIMISED_METHODS
    ]
    fixture_rows[0] = summary_row("after-groups", "pairwise-favourites", 7, False)
    fixture_rows[1] = summary_row("after-groups", "modal-simulated-bracket", 0, True)

    rows = aggregate_summary(
        fixture_rows
    )

    scores = {
        row["method"]: row["weighted_progression_score"]
        for row in rows
        if row["checkpoint"] == "after-groups"
    }

    assert scores["modal-simulated-bracket"] > scores["pairwise-favourites"]
