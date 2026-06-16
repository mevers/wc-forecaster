from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

os.environ.setdefault("MPLCONFIGDIR", "/tmp/wc_forecaster_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/wc_forecaster_cache")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from wc_forecaster.data import read_matches, rows, team, write_csv
from wc_forecaster.elo import apply_match
from wc_forecaster.bracket import BRACKET_METHOD_EXPECTED_TABLE, BRACKET_METHODS, expected_group_tables, knockout_bracket
from wc_forecaster.model import fit, match_probs, tune
from wc_forecaster.tournament import simulate


def status(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_groups(path: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for row in rows(path):
        groups.setdefault(row["group"], []).append(team(row["team"]))
    return groups


def load_slots(path: str) -> dict[int, set[str]]:
    return {int(row["match_no"]): set(row["groups"].split("/")) for row in rows(path)}


def chart(path: Path, rows_: list[dict[str, Any]], x: str, y: str, title: str) -> None:
    plt.figure(figsize=(9, 5))
    plt.bar([r[x] for r in rows_[:12]], [r[y] for r in rows_[:12]])
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def write_ratings(path: Path, ratings: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write("# Snapshot of the model's derived team-strength ratings immediately before simulating the remaining tournament. These ratings are computed from observed matches only, not predicted fixtures or official FIFA ratings.\n")
        writer = csv.DictWriter(handle, fieldnames=["team", "rating"])
        writer.writeheader()
        writer.writerows({"team": k, "rating": round(v, 1)} for k, v in sorted(ratings.items(), key=lambda row: row[1], reverse=True))


def predict(config_path: Path, bracket_method: str = BRACKET_METHOD_EXPECTED_TABLE) -> None:
    status(f"Reading config: {config_path}")
    cfg = load_config(config_path)
    as_of = date.fromisoformat(cfg["forecast"]["as_of"])
    out = Path(cfg["data"]["output_dir"]) / cfg["forecast"]["as_of"]
    status(f"Loading historical results: {cfg['data']['historical_results']}")
    historical = read_matches(cfg["data"]["historical_results"])
    training = [m for m in historical if not (m["date"].year == 2026 and m["tournament"] == "FIFA World Cup")]
    status(f"Loaded {len(historical):,} historical rows; using {len(training):,} for model fitting")
    tuning = tune(training, cfg, status) if cfg["fit"]["tune"] else {"selected_half_life": cfg["fit"]["half_life"], "selected_min_expected_goals": cfg["goals"]["min_expected_goals"], "scores": []}
    status(f"Fitting final model as of {as_of}")
    ratings, beta, s = fit(training, cfg, as_of)
    status("Loading 2026 tournament state")
    groups = load_groups(cfg["data"]["groups"])
    fixtures = read_matches(cfg["data"]["fixtures"])
    fixtures = [{**m, "home_score": None, "away_score": None} if m["date"] > as_of else m for m in fixtures]
    played = sorted((m for m in fixtures if m["home_score"] is not None), key=lambda m: m["date"])
    status(f"Applying {len(played)} completed 2026 World Cup matches")
    for match in played:
        match["tournament"] = "FIFA World Cup"
        apply_match(ratings, match, cfg)
        s[match["home_team"]] = match["home_score"] > match["away_score"]
        s[match["away_team"]] = match["away_score"] > match["home_score"]
    status(f"Simulating {cfg['forecast']['simulations']:,} tournaments")
    result = simulate(groups, fixtures, load_slots(cfg["data"]["third_place_slots"]), ratings, beta, s, cfg, status)
    sims = cfg["forecast"]["simulations"]
    status("Writing forecast artefacts")
    winner_rows = [{"team": k, "probability": v / sims} for k, v in result["title"].most_common()]
    round_rows = []
    for round_name, counter in result["reached"].items():
        for team_name, count in counter.items():
            round_rows.append({"team": team_name, "round": round_name, "probability": count / sims})
    fixture_rows = []
    for match in fixtures:
        probs = match_probs(match["home_team"], match["away_team"], match["venue_advantage"], ratings, beta, s, cfg)
        fixture_rows.append(
            {
                "match_no": match["match_no"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "home": probs["home"],
                "draw": probs["draw"],
                "away": probs["away"],
            }
        )
    matchup_rows = [
        {"match_no": match, "team_a": pair[0], "team_b": pair[1], "probability": count / sims}
        for match, counter in sorted(result["matchups"].items())
        for pair, count in [counter.most_common(1)[0]]
    ]
    group_tables = expected_group_tables(groups, result, sims, ratings)
    group_table_rows = [
        {
            "group": row["group"],
            "position": row["position"],
            "team": row["team"],
            "expected_points": row["expected_points"],
            "expected_goal_difference": row["expected_goal_difference"],
            "expected_goals_for": row["expected_goals_for"],
        }
        for group in groups
        for row in group_tables[group]
    ]
    knockout_bracket_rows = knockout_bracket(bracket_method, group_tables, result, load_slots(cfg["data"]["third_place_slots"]), ratings, beta, s, cfg)
    write_csv(out / "winner_odds.csv", winner_rows)
    write_csv(out / "round_probabilities.csv", sorted(round_rows, key=lambda r: (r["team"], r["round"])))
    write_ratings(out / "derived_team_ratings.csv", ratings)
    write_csv(out / "fixture_probabilities.csv", fixture_rows)
    write_csv(out / "most_likely_group_tables.csv", group_table_rows)
    write_csv(out / "most_likely_matchups.csv", matchup_rows)
    write_csv(out / "most_likely_knockout_bracket.csv", knockout_bracket_rows)
    write_csv(out / "most_likely_tournament_bracket.csv", knockout_bracket_rows)
    write_csv(out / "most_likely_realised_bracket.csv", knockout_bracket_rows)
    write_csv(out / "most_likely_bracket.csv", [{"match_no": match, "team": counter.most_common(1)[0][0], "probability": counter.most_common(1)[0][1] / sims} for match, counter in sorted(result["match_winners"].items())])
    (out / "tuning_summary.json").write_text(json.dumps(tuning, indent=2), encoding="utf-8")
    (out / "run_manifest.json").write_text(json.dumps({"as_of": cfg["forecast"]["as_of"], "simulations": sims, "coefficients": beta, "config": str(config_path), "bracket_method": bracket_method}, indent=2), encoding="utf-8")
    chart(out / "winner_odds.png", winner_rows, "team", "probability", "World Cup winner odds")
    status(f"Wrote forecast to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="wc-forecaster")
    sub = parser.add_subparsers(dest="command", required=True)
    predict_parser = sub.add_parser("predict")
    predict_parser.add_argument("--config", type=Path, default=Path("config/model.yaml"))
    predict_parser.add_argument("--bracket-method", choices=BRACKET_METHODS, default=BRACKET_METHOD_EXPECTED_TABLE)
    args = parser.parse_args()
    predict(args.config, args.bracket_method)
