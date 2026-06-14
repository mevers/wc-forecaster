from __future__ import annotations

from wc_forecaster.elo import apply_match
from wc_forecaster.model import poisson_probs
from wc_forecaster.tournament import add_result, rank, third_assignment, winner


CFG = {
    "elo": {"initial": 1500.0, "divisor": 400.0, "venue_advantage": 70.0, "k": {"default": 30.0}},
    "goals": {"score_cap": 4, "min_expected_goals": 0.15},
    "form": {"gamma": 0.05},
    "knockout": {"penalty_rating_scale": 500.0},
}


def test_elo_updates_winner_up() -> None:
    ratings = {"A": 1500.0, "B": 1500.0}
    apply_match(ratings, {"home_team": "A", "away_team": "B", "home_score": 2, "away_score": 0, "venue_advantage": 0}, CFG)
    assert ratings["A"] > 1500
    assert ratings["B"] < 1500


def test_elo_supports_second_team_venue_advantage() -> None:
    ratings = {"A": 1500.0, "B": 1500.0}
    apply_match(ratings, {"home_team": "A", "away_team": "B", "home_score": 0, "away_score": 0, "venue_advantage": -1}, CFG)
    assert ratings["A"] > 1500
    assert ratings["B"] < 1500


def test_poisson_probs_sum_to_one() -> None:
    assert round(sum(poisson_probs(1.4, 6)), 10) == 1


def test_group_rank_uses_points_goal_difference_goals_for_rating() -> None:
    tab = {"A": {"points": 0, "gf": 0, "ga": 0}, "B": {"points": 0, "gf": 0, "ga": 0}, "C": {"points": 0, "gf": 0, "ga": 0}}
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
