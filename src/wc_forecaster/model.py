from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any

from wc_forecaster.elo import apply_match, venue_adjusted


# Solves the 3-parameter IRLS normal equations for the Poisson GLM.
def solve3(a: list[list[float]], b: list[float]) -> list[float]:
    for i in range(3):
        pivot = a[i][i]
        for j in range(i, 3):
            a[i][j] /= pivot
        b[i] /= pivot
        for k in range(3):
            if k != i:
                factor = a[k][i]
                for j in range(i, 3):
                    a[k][j] -= factor * a[i][j]
                b[k] -= factor * b[i]
    return b


# Fits Elo-derived ratings, previous-win state, and Poisson goal coefficients.
def fit(matches: list[dict[str, Any]], cfg: dict[str, Any], cutoff: date) -> tuple[dict[str, float], list[float], dict[str, bool]]:
    ratings = defaultdict(lambda: float(cfg["elo"]["initial"]))
    s: dict[str, bool] = {}
    gamma = cfg["form"]["gamma"]
    goal_observations = []
    for match in sorted((m for m in matches if m["date"] <= cutoff and m["home_score"] is not None), key=lambda m: m["date"]):
        v_i = match["venue_advantage"]
        team_a = match["home_team"]
        team_b = match["away_team"]
        # Build the two team-perspective observations from pre-match ratings.
        rating_a, rating_b = venue_adjusted(ratings[team_a], ratings[team_b], v_i, cfg)
        match_observations = [
            ([1.0, (rating_a - rating_b) / 100, v_i], match["home_score"], s.get(team_a, False)),
            ([1.0, (rating_b - rating_a) / 100, -v_i], match["away_score"], s.get(team_b, False)),
        ]
        age = (cutoff - match["date"]).days / 365.25
        # Downweight older matches using the configured half-life.
        weight = 0.5 ** (age / cfg["fit"]["half_life"])
        for features, goals, s_j in match_observations:
            goal_observations.append((features, goals, gamma * s_j, weight))
        apply_match(ratings, match, cfg)
        s[team_a] = match["home_score"] > match["away_score"]
        s[team_b] = match["away_score"] > match["home_score"]
    beta = [0.0, 0.0, 0.0]
    for _ in range(25):
        information = [[0.0] * 3 for _ in range(3)]
        score = [0.0] * 3
        # Accumulate weighted Poisson score and information terms for IRLS.
        for features, goals, offset, weight in goal_observations:
            expected_goals = math.exp(sum(x * b for x, b in zip(features, beta)) + offset)
            for i in range(3):
                score[i] += weight * features[i] * (goals - expected_goals)
                for j in range(3):
                    information[i][j] += weight * expected_goals * features[i] * features[j]
        update = solve3(information, score)
        beta = [value + change for value, change in zip(beta, update)]
        if max(abs(change) for change in update) < 1e-10:
            break
    return ratings, beta, s


# Computes capped-floor expected goals for both teams in a fixture.
def lambdas(team_a: str, team_b: str, v: int, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> tuple[float, float]:
    rating_a, rating_b = venue_adjusted(ratings[team_a], ratings[team_b], v, cfg)
    q_a = (rating_a - rating_b) / 100
    q_b = (rating_b - rating_a) / 100
    s_a = s.get(team_a, False)
    s_b = s.get(team_b, False)
    floor = cfg["goals"]["min_expected_goals"]
    gamma = cfg["form"]["gamma"]
    return max(floor, math.exp(beta[0] + beta[1] * q_a + beta[2] * v + gamma * s_a)), max(floor, math.exp(beta[0] + beta[1] * q_b - beta[2] * v + gamma * s_b))


# Builds capped Poisson probabilities with tail mass folded into the cap.
def poisson_probs(lam: float, cap: int) -> list[float]:
    probs = [math.exp(-lam)]
    for goals in range(1, cap + 1):
        probs.append(probs[-1] * lam / goals)
    probs[-1] += 1 - sum(probs)
    return probs


# Reports a scoreline consistent with the most likely 1X2 outcome.
def outcome_constrained_median_scoreline(lambda_a: float, lambda_b: float, cap: int) -> tuple[int, int]:
    probs_a = poisson_probs(lambda_a, cap)
    probs_b = poisson_probs(lambda_b, cap)
    grid = [(i, j, pi * pj) for i, pi in enumerate(probs_a) for j, pj in enumerate(probs_b)]
    # Choose the most likely outcome bucket before selecting a scoreline.
    outcome = max(
        ("home", "draw", "away"),
        key=lambda o: sum(
            p
            for i, j, p in grid
            if (i > j if o == "home" else i == j if o == "draw" else i < j)
        ),
    )

    # Restricts candidate scorelines to the selected 1X2 outcome.
    def matches_outcome(h: int, a: int) -> bool:
        return h > a if outcome == "home" else h == a if outcome == "draw" else h < a

    # Minimise expected absolute goal error, breaking ties by exact-score probability.
    return min(
        (
            (
                sum(p * (abs(i - h) + abs(j - a)) for i, j, p in grid),
                -probs_a[h] * probs_b[a],
                h,
                a,
            )
            for h in range(cap + 1)
            for a in range(cap + 1)
            if matches_outcome(h, a)
        )
    )[2:]


# Sums capped scoreline probabilities into home-draw-away buckets.
def match_probs(team_a: str, team_b: str, v: int, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> dict[str, float]:
    lambda_a, lambda_b = lambdas(team_a, team_b, v, ratings, beta, s, cfg)
    probs_a = poisson_probs(lambda_a, cfg["goals"]["score_cap"])
    probs_b = poisson_probs(lambda_b, cfg["goals"]["score_cap"])
    probs = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for i, pi in enumerate(probs_a):
        for j, pj in enumerate(probs_b):
            probs["home" if i > j else "draw" if i == j else "away"] += pi * pj
    return probs


# Samples independent capped Poisson goals for one simulated fixture.
def sample_score(rng: Any, team_a: str, team_b: str, v: int, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> tuple[int, int]:
    lambda_a, lambda_b = lambdas(team_a, team_b, v, ratings, beta, s, cfg)
    cap = cfg["goals"]["score_cap"]
    probs_a = poisson_probs(lambda_a, cap)
    probs_b = poisson_probs(lambda_b, cap)
    return rng.choices(range(cap + 1), probs_a)[0], rng.choices(range(cap + 1), probs_b)[0]


# Tunes half-life and goal floor by World Cup 1X2 log loss.
def tune(matches: list[dict[str, Any]], cfg: dict[str, Any], status: Any = None) -> dict[str, Any]:
    original_half_life = cfg["fit"]["half_life"]
    original_floor = cfg["goals"]["min_expected_goals"]
    scores = []
    for half_life in cfg["fit"]["half_life_years"]:
        for floor in cfg["goals"]["min_expected_goals_values"]:
            if status:
                status(f"Tuning half-life={half_life}, min-goals={floor}")
            cfg["fit"]["half_life"] = half_life
            cfg["goals"]["min_expected_goals"] = floor
            loss = 0.0
            n = 0
            # Backtest each candidate against 2018 and 2022 World Cup outcomes.
            for year, start in [(2018, date(2018, 6, 14)), (2022, date(2022, 11, 20))]:
                ratings, beta, s = fit(matches, cfg, start)
                for match in sorted(matches, key=lambda row: row["date"]):
                    if match["date"].year == year and match.get("tournament") == "FIFA World Cup" and match["home_score"] is not None:
                        probs = match_probs(match["home_team"], match["away_team"], match["venue_advantage"], ratings, beta, s, cfg)
                        outcome = "home" if match["home_score"] > match["away_score"] else "draw" if match["home_score"] == match["away_score"] else "away"
                        loss -= math.log(max(1e-9, probs[outcome]))
                        n += 1
                        s[match["home_team"]] = match["home_score"] > match["away_score"]
                        s[match["away_team"]] = match["away_score"] > match["home_score"]
            scores.append({"half_life": half_life, "min_expected_goals": floor, "log_loss": loss / n if n else 0.0, "matches": n})
    best = min(scores, key=lambda row: row["log_loss"])
    cfg["fit"]["half_life"] = best["half_life"] if best["matches"] else original_half_life
    cfg["goals"]["min_expected_goals"] = best["min_expected_goals"] if best["matches"] else original_floor
    if status:
        status(f"Selected half-life={cfg['fit']['half_life']}, min-goals={cfg['goals']['min_expected_goals']}")
    return {"selected_half_life": cfg["fit"]["half_life"], "selected_min_expected_goals": cfg["goals"]["min_expected_goals"], "scores": scores}
