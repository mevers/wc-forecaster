from __future__ import annotations

from collections import defaultdict
from typing import Any


# Maps venue-adjusted ratings to team a's expected Elo score.
def expected(a: float, b: float, divisor: float) -> float:
    return 1 / (1 + 10 ** ((b - a) / divisor))


# Implements the World Football Elo goal-difference multiplier.
def goal_difference_multiplier(goals_a: int, goals_b: int) -> float:
    goal_difference = abs(goals_a - goals_b)
    return 1 if goal_difference < 2 else 1.5 if goal_difference == 2 else (11 + goal_difference) / 8


# Converts the scoreline into team a's realised Elo score.
def realised_score(goals_a: int, goals_b: int) -> float:
    return 1.0 if goals_a > goals_b else 0.5 if goals_a == goals_b else 0.0


# Chooses the match-importance K value for the tournament.
def k_value(tournament: str, cfg: dict[str, Any]) -> float:
    return float(cfg["elo"]["k"].get(tournament, cfg["elo"]["k"]["default"]))


# Applies half of the venue-advantage prior to each pre-match rating.
def venue_adjusted(a: float, b: float, venue: int, cfg: dict[str, Any]) -> tuple[float, float]:
    adjustment = venue * cfg["elo"]["venue_advantage"] / 2
    return a + adjustment, b - adjustment


# Applies the zero-sum Elo update for one observed match.
def apply_match(ratings: dict[str, float], match: dict[str, Any], cfg: dict[str, Any]) -> None:
    team_a = match["home_team"]
    team_b = match["away_team"]
    # Use venue-adjusted ratings only for expected-score calculation.
    rating_a, rating_b = venue_adjusted(ratings[team_a], ratings[team_b], match["venue_advantage"], cfg)
    exp = expected(rating_a, rating_b, cfg["elo"]["divisor"])
    # Combine importance, margin, and surprise into the Elo delta, scaled by current_world_cup_k_multiplier
    delta = (
        match.get("elo_k_multiplier", 1.0)
        * k_value(match.get("tournament", "FIFA World Cup"), cfg)
        * goal_difference_multiplier(match["home_score"], match["away_score"])
        * (realised_score(match["home_score"], match["away_score"]) - exp)
    )
    ratings[team_a] += delta
    ratings[team_b] -= delta


# Derives the rating snapshot by replaying completed matches to cutoff.
def train(matches: list[dict[str, Any]], cfg: dict[str, Any], cutoff: Any) -> dict[str, float]:
    ratings = defaultdict(lambda: float(cfg["elo"]["initial"]))
    # Chronological replay keeps each match dependent on prior updates.
    for match in sorted((m for m in matches if m["date"] <= cutoff and m["home_score"] is not None), key=lambda m: m["date"]):
        apply_match(ratings, match, cfg)
    return dict(ratings)
