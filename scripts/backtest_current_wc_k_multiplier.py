from __future__ import annotations

import copy
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wc_forecaster.cli import load_config
from wc_forecaster.data import read_matches
from wc_forecaster.elo import apply_match
from wc_forecaster.model import fit, lambdas, match_probs, outcome_constrained_median_scoreline, tune


MULTIPLIERS = [1.0, 1.25, 1.5, 2.0]
STARTS = {2018: date(2018, 6, 14), 2022: date(2022, 11, 20)}


def outcome(match: dict[str, Any]) -> str:
    return "home" if match["home_score"] > match["away_score"] else "draw" if match["home_score"] == match["away_score"] else "away"


def world_cup_matches(matches: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    return [
        match
        for match in sorted(matches, key=lambda row: row["date"])
        if match["date"].year == year
        and match["tournament"] == "FIFA World Cup"
        and match["home_score"] is not None
    ]


def main() -> None:
    cfg = load_config(Path("config/model.yaml"))
    matches = read_matches(cfg["data"]["historical_results"])
    tune(matches, cfg)
    initial = {year: fit(matches, cfg, start) for year, start in STARTS.items()}
    rows = []
    for multiplier in MULTIPLIERS:
        losses = []
        hits = exact_scores = total = 0
        per_year: dict[int, list[float]] = defaultdict(list)
        for year, start in STARTS.items():
            ratings0, beta, s0 = initial[year]
            ratings = copy.deepcopy(ratings0)
            s = copy.deepcopy(s0)
            for match in world_cup_matches(matches, year):
                probs = match_probs(match["home_team"], match["away_team"], match["venue_advantage"], ratings, beta, s, cfg)
                loss = -math.log(max(1e-9, probs[outcome(match)]))
                losses.append(loss)
                per_year[year].append(loss)
                hits += max(("home", "draw", "away"), key=lambda key: probs[key]) == outcome(match)
                home_xg, away_xg = lambdas(match["home_team"], match["away_team"], match["venue_advantage"], ratings, beta, s, cfg)
                exact_scores += outcome_constrained_median_scoreline(home_xg, away_xg, cfg["goals"]["score_cap"]) == (match["home_score"], match["away_score"])
                total += 1
                apply_match(ratings, {**match, "elo_k_multiplier": multiplier}, cfg)
                s[match["home_team"]] = match["home_score"] > match["away_score"]
                s[match["away_team"]] = match["away_score"] > match["home_score"]
        rows.append(
            {
                "multiplier": multiplier,
                "log_loss": sum(losses) / len(losses),
                "log_loss_2018": sum(per_year[2018]) / len(per_year[2018]),
                "log_loss_2022": sum(per_year[2022]) / len(per_year[2022]),
                "outcome_accuracy": hits / total,
                "exact_score_accuracy": exact_scores / total,
            }
        )
    for row in sorted(rows, key=lambda item: item["log_loss"]):
        print(row)


if __name__ == "__main__":
    main()
