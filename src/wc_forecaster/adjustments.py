from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

from wc_forecaster.model import match_probs


def boosted_ratings(ratings: dict[str, float], *boosts: dict[str, float]) -> dict[str, float]:
    teams = set(ratings)
    for boost in boosts:
        teams.update(boost)
    return {team: ratings[team] + sum(boost.get(team, 0.0) for boost in boosts) for team in teams}


def cohesion(
    squads: list[dict[str, str]],
    teams: list[str],
    cfg: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float]]:
    scores = dict.fromkeys(teams, 0.0)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in squads:
        if row["team"] in scores:
            if not row["player"] or not row["club"] or not row["league"]:
                raise ValueError(f"Incomplete squad row for {row['team']}")
            grouped[row["team"]].append(row)
    missing = [team for team in teams if team not in grouped]
    if missing:
        raise ValueError(f"Missing squad rows for: {', '.join(missing)}")
    params = cfg["cohesion"]
    for team, players in grouped.items():
        for player_a, player_b in combinations(players, 2):
            if player_a["club"] == player_b["club"]:
                scores[team] += params["same_club_weight"]
            elif player_a["league"] == player_b["league"]:
                scores[team] += params["same_league_weight"]
    boosts = {
        team: min(
            params["max_rating_boost"],
            params["max_rating_boost"] * score / params["score_for_max_boost"],
        )
        for team, score in scores.items()
    }
    return scores, boosts


def zero_adjustments(teams: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    return dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)


def actual_points(goals_for: int, goals_against: int) -> float:
    return 3.0 if goals_for > goals_against else 1.0 if goals_for == goals_against else 0.0


def underdog_weight(team_rating: float, opponent_rating: float, cfg: dict[str, Any]) -> float:
    params = cfg["underdog_magic"]
    gap = opponent_rating - team_rating
    if gap < params["min_rating_gap"]:
        return 0.0
    return min(
        1.0,
        (gap - params["min_rating_gap"])
        / (params["rating_gap_for_full_weight"] - params["min_rating_gap"]),
    )


def add_underdog_magic_residual(
    residuals: dict[str, float],
    match: dict[str, Any],
    ratings: dict[str, float],
    cohesion_boost: dict[str, float],
    beta: list[float],
    s: dict[str, bool],
    cfg: dict[str, Any],
) -> None:
    forecast_ratings = boosted_ratings(ratings, cohesion_boost)
    probs = match_probs(
        match["home_team"],
        match["away_team"],
        match["venue_advantage"],
        forecast_ratings,
        beta,
        s,
        cfg,
    )
    home = match["home_team"]
    away = match["away_team"]
    residuals[home] += max(
        0.0,
        actual_points(match["home_score"], match["away_score"]) - (3 * probs["home"] + probs["draw"]),
    ) * underdog_weight(forecast_ratings[home], forecast_ratings[away], cfg)
    residuals[away] += max(
        0.0,
        actual_points(match["away_score"], match["home_score"]) - (3 * probs["away"] + probs["draw"]),
    ) * underdog_weight(forecast_ratings[away], forecast_ratings[home], cfg)


def underdog_magic_boosts(residuals: dict[str, float], cfg: dict[str, Any]) -> dict[str, float]:
    params = cfg["underdog_magic"]
    return {
        team: min(
            params["max_rating_boost"],
            params["max_rating_boost"]
            * max(0.0, residual)
            / params["points_residual_for_max_boost"],
        )
        for team, residual in residuals.items()
    }
