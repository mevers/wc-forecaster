from __future__ import annotations

import pytest

from wc_forecaster.adjustments import (
    add_underdog_magic_residual,
    cohesion,
    underdog_magic_boosts,
)
from wc_forecaster.elo import apply_match
from wc_forecaster.model import outcome_constrained_median_scoreline, poisson_probs
from wc_forecaster.tournament import add_result, rank, third_assignment, winner


CFG = {
    "elo": {
        "initial": 1500.0,
        "divisor": 400.0,
        "venue_advantage": 70.0,
        "k": {"default": 30.0},
    },
    "goals": {"score_cap": 4, "min_expected_goals": 0.15},
    "form": {"gamma": 0.05},
    "knockout": {"penalty_rating_scale": 500.0},
    "underdog_magic": {
        "enabled": True,
        "max_rating_boost": 40.0,
        "points_residual_for_max_boost": 5.0,
        "min_rating_gap": 200.0,
        "rating_gap_for_full_weight": 300.0,
    },
    "cohesion": {
        "enabled": True,
        "max_rating_boost": 25.0,
        "same_club_weight": 1.0,
        "same_league_weight": 0.25,
        "score_for_max_boost": 20.0,
    },
}


def test_elo_updates_winner_up() -> None:
    ratings = {"A": 1500.0, "B": 1500.0}
    apply_match(
        ratings,
        {
            "home_team": "A",
            "away_team": "B",
            "home_score": 2,
            "away_score": 0,
            "venue_advantage": 0,
        },
        CFG,
    )
    assert ratings["A"] > 1500
    assert ratings["B"] < 1500


def test_elo_supports_second_team_venue_advantage() -> None:
    ratings = {"A": 1500.0, "B": 1500.0}
    apply_match(
        ratings,
        {
            "home_team": "A",
            "away_team": "B",
            "home_score": 0,
            "away_score": 0,
            "venue_advantage": -1,
        },
        CFG,
    )
    assert ratings["A"] > 1500
    assert ratings["B"] < 1500


def test_poisson_probs_sum_to_one() -> None:
    assert round(sum(poisson_probs(1.4, 6)), 10) == 1


def test_outcome_constrained_median_scoreline_respects_most_likely_outcome() -> None:
    assert outcome_constrained_median_scoreline(0.9500605015258919, 1.5093479508355436, 8) == (1, 2)


def test_group_rank_uses_points_goal_difference_goals_for_rating() -> None:
    tab = {
        "A": {"points": 0, "gf": 0, "ga": 0},
        "B": {"points": 0, "gf": 0, "ga": 0},
        "C": {"points": 0, "gf": 0, "ga": 0},
    }
    add_result(tab, "A", "B", 1, 0)
    add_result(tab, "C", "A", 2, 0)
    assert rank(tab, {"A": 1600, "B": 1500, "C": 1400})[0] == "C"


def test_third_assignment_respects_slot_groups() -> None:
    out = third_assignment(["Brazil:C", "Japan:F"], {74: {"A", "C"}, 77: {"F"}})
    assert out == {74: "Brazil:C", 77: "Japan:F"}


def test_knockout_winner_returns_one_team() -> None:
    import random

    s = {"A": False, "B": False}
    won = winner(random.Random(1), "A", "B", {"A": 1600, "B": 1500}, [0.2, 0.1, 0.0], s, CFG)
    assert won in {"A", "B"}
    assert s[won] is True


def test_cohesion_scores_same_club_pairs() -> None:
    squads = [{"team": "A", "player": str(i), "club": "One", "league": "X"} for i in range(6)]
    scores, boosts = cohesion(squads, ["A"], CFG)
    assert scores["A"] == 15
    assert boosts["A"] == 18.75


def test_cohesion_scores_same_league_pairs() -> None:
    squads = [
        {"team": "A", "player": "1", "club": "One", "league": "X"},
        {"team": "A", "player": "2", "club": "Two", "league": "X"},
        {"team": "A", "player": "3", "club": "Three", "league": "X"},
    ]
    scores, boosts = cohesion(squads, ["A"], CFG)
    assert scores["A"] == 0.75
    assert boosts["A"] == 0.9375


def test_cohesion_fails_for_missing_team() -> None:
    with pytest.raises(ValueError, match="Missing squad rows for: B"):
        cohesion([{"team": "A", "player": "1", "club": "One", "league": "X"}], ["A", "B"], CFG)


def test_underdog_magic_boosts_positive_underdog_surprise_only() -> None:
    residuals = {"A": 0.0, "B": 0.0}
    match = {
        "home_team": "A",
        "away_team": "B",
        "home_score": 1,
        "away_score": 0,
        "venue_advantage": 0,
    }
    add_underdog_magic_residual(
        residuals,
        match,
        {"A": 1200.0, "B": 1800.0},
        {},
        [0.2, 0.1, 0.0],
        {},
        CFG,
    )
    boosts = underdog_magic_boosts(residuals, CFG)
    assert residuals["A"] > 0
    assert residuals["B"] == 0
    assert boosts["A"] > 0
    assert boosts["B"] == 0


def test_underdog_magic_ignores_near_equal_surprise() -> None:
    residuals = {"A": 0.0, "B": 0.0}
    match = {
        "home_team": "A",
        "away_team": "B",
        "home_score": 1,
        "away_score": 0,
        "venue_advantage": 0,
    }
    add_underdog_magic_residual(
        residuals,
        match,
        {"A": 1700.0, "B": 1750.0},
        {},
        [0.2, 0.1, 0.0],
        {},
        CFG,
    )
    assert residuals == {"A": 0.0, "B": 0.0}
