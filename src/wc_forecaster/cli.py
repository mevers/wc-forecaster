from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import plotnine as p9
import yaml

os.environ.setdefault("XDG_CACHE_HOME", "/tmp/wc_forecaster_cache")

from wc_forecaster.adjustments import compute_adjustments
from wc_forecaster.bracket import expected_group_tables, knockout_bracket_options
from wc_forecaster.data import read_matches, rows, team, write_csv
from wc_forecaster.model import fit, lambdas, match_probs, outcome_constrained_median_scoreline, tune
from wc_forecaster.tournament import simulate


# Emits timestamped progress for long forecast runs.
def status(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


# Loads the model configuration that fixes inputs and tuning settings.
def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# Loads the 2026 team-to-group mapping with canonical team names.
def load_groups(path: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for row in rows(path):
        groups.setdefault(row["group"], []).append(team(row["team"]))
    return groups


# Loads eligible third-place groups for each round-of-32 slot.
def load_slots(path: str) -> dict[int, set[str]]:
    return {int(row["match_no"]): set(row["groups"].split("/")) for row in rows(path)}


# Renders a top-12 probability bar chart for report artefacts.
def chart(path: Path, rows_: list[dict[str, Any]], x: str, y: str, title: str) -> None:
    data = pl.DataFrame(rows_[:12])
    x_order = list(reversed(data[x].to_list()))
    plot = (
        p9.ggplot(data, p9.aes(x=x, y=y))
        + p9.geom_col(fill="#1f4e79", width=0.72)
        + p9.coord_flip()
        + p9.scale_x_discrete(limits=x_order)
        + p9.scale_y_continuous(labels=lambda values: [f"{100 * value:.1f}%" for value in values])
        + p9.labs(title=title)
        + p9.theme_minimal(base_size=9)
        + p9.theme(
            figure_size=(9, 5),
            plot_background=p9.element_rect(fill="#fbfcfd", color="#fbfcfd"),
            panel_background=p9.element_rect(fill="#ffffff", color="#ffffff"),
            panel_grid_major_y=p9.element_blank(),
            panel_grid_minor=p9.element_blank(),
            axis_title=p9.element_blank(),
        )
    )
    plot.save(str(path), width=9, height=5, dpi=180, verbose=False)


# Writes the derived rating snapshot before remaining-fixture simulation.
def write_ratings(path: Path, ratings: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write("# Snapshot of the model's derived team-strength ratings immediately before simulating the remaining tournament. These ratings are computed from observed matches only, not predicted fixtures or official FIFA ratings.\n")
        writer = csv.DictWriter(handle, fieldnames=["team", "rating"])
        writer.writeheader()
        writer.writerows({"team": k, "rating": round(v, 1)} for k, v in sorted(ratings.items(), key=lambda row: row[1], reverse=True))


# Shapes forecast-only adjustment outputs for team_adjustments.csv.
def adjustment_rows(
    teams: list[str],
    ratings: dict[str, float],
    cohesion_score: dict[str, float],
    cohesion_boost: dict[str, float],
    underdog_magic_residual: dict[str, float],
    underdog_magic_boost: dict[str, float],
    adjusted_ratings: dict[str, float],
) -> list[dict[str, Any]]:
    return [
        {
            "team": team_name,
            "base_rating": round(ratings[team_name], 1),
            "cohesion_score": round(cohesion_score[team_name], 3),
            "cohesion_boost": round(cohesion_boost[team_name], 3),
            "underdog_magic_residual": round(underdog_magic_residual.get(team_name, 0.0), 3),
            "underdog_magic_boost": round(underdog_magic_boost.get(team_name, 0.0), 3),
            "adjusted_rating": round(adjusted_ratings[team_name], 1),
        }
        for team_name in sorted(teams)
    ]


# Runs the full configured forecast and writes all output artefacts.
def predict(config_path: Path, update_readme: bool = False, as_of_override: str | None = None) -> None:
    status(f"Reading config: {config_path}")
    cfg = load_config(config_path)
    cfg["forecast"]["as_of"] = as_of_override or cfg["forecast"]["as_of"]
    as_of = date.fromisoformat(cfg["forecast"]["as_of"])
    out = Path(cfg["data"]["output_dir"]) / cfg["forecast"]["as_of"]
    status(f"Loading historical results: {cfg['data']['historical_results']}")
    historical = read_matches(cfg["data"]["historical_results"])
    # Fit excludes 2026 World Cup rows so live fixtures only update tournament state.
    training = [m for m in historical if not (m["date"].year == 2026 and m["tournament"] == "FIFA World Cup")]
    status(f"Loaded {len(historical):,} historical rows; using {len(training):,} for model fitting")
    tuning = tune(training, cfg, status) if cfg["fit"]["tune"] else {"selected_half_life": cfg["fit"]["half_life"], "selected_min_expected_goals": cfg["goals"]["min_expected_goals"], "scores": []}
    status(f"Fitting final model as of {as_of}")
    ratings, beta, s = fit(training, cfg, as_of)
    status("Loading 2026 tournament state")
    groups = load_groups(cfg["data"]["groups"])
    teams = [team_name for group in groups.values() for team_name in group]
    squads = rows(cfg["data"]["squads"])
    fixtures = read_matches(cfg["data"]["fixtures"])
    # Future-dated scored rows are treated as unplayed for this forecast date.
    fixtures = [{**m, "home_score": None, "away_score": None} if m["date"] > as_of else m for m in fixtures]
    played = sorted((m for m in fixtures if m["home_score"] is not None), key=lambda m: m["date"])
    status(f"Applying {len(played)} completed 2026 World Cup matches")
    (
        cohesion_score,
        cohesion_boost,
        underdog_magic_residual,
        underdog_magic_boost,
        adjusted_ratings,
    ) = compute_adjustments(teams, squads, played, ratings, beta, s, cfg)
    status(f"Simulating {cfg['forecast']['simulations']:,} tournaments")
    result = simulate(groups, fixtures, load_slots(cfg["data"]["third_place_slots"]), adjusted_ratings, beta, s, cfg, status)
    sims = cfg["forecast"]["simulations"]
    status("Writing forecast artefacts")
    # Convert empirical simulation counters into output probabilities.
    winner_rows = [{"team": k, "probability": v / sims} for k, v in result["title"].most_common()]
    round_rows = []
    for round_name, counter in result["reached"].items():
        for team_name, count in counter.items():
            round_rows.append({"team": team_name, "round": round_name, "probability": count / sims})
    fixture_rows = []
    for match in fixtures:
        probs = match_probs(match["home_team"], match["away_team"], match["venue_advantage"], adjusted_ratings, beta, s, cfg)
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
    # These marginal summaries are distinct from the coherent bracket artefact.
    matchup_marginal_rows = [
        {"match_no": match, "team_a": pair[0], "team_b": pair[1], "probability": count / sims}
        for match, counter in sorted(result["matchups"].items())
        for pair, count in [counter.most_common(1)[0]]
    ]
    winner_marginal_rows = [
        {"match_no": match, "team": counter.most_common(1)[0][0], "probability": counter.most_common(1)[0][1] / sims}
        for match, counter in sorted(result["match_winners"].items())
    ]
    # Build expected group tables and coherent knockout bracket rows.
    group_tables = expected_group_tables(groups, result, sims, adjusted_ratings)
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
    knockout_bracket_rows = knockout_bracket_options(groups, group_tables, result, load_slots(cfg["data"]["third_place_slots"]), fixtures, adjusted_ratings, beta, s, cfg)
    write_csv(out / "winner_odds.csv", winner_rows)
    write_csv(out / "round_reach_probabilities.csv", sorted(round_rows, key=lambda r: (r["team"], r["round"])))
    write_ratings(out / "derived_team_ratings.csv", ratings)
    write_csv(
        out / "team_adjustments.csv",
        adjustment_rows(
            teams,
            ratings,
            cohesion_score,
            cohesion_boost,
            underdog_magic_residual,
            underdog_magic_boost,
            adjusted_ratings,
        ),
    )
    write_csv(out / "group_fixture_1x2_probabilities.csv", fixture_rows)
    write_csv(out / "most_likely_group_tables.csv", group_table_rows)
    write_csv(out / "most_likely_knockout_bracket.csv", knockout_bracket_rows)
    write_csv(out / "match_slot_matchup_marginals.csv", matchup_marginal_rows)
    write_csv(out / "match_slot_winner_marginals.csv", winner_marginal_rows)
    next_dates = sorted({match["date"] for match in fixtures if match["date"] > as_of})
    next_rows = []
    if next_dates:
        # Summarise only the next fixture date after forecast.as_of.
        next_rows = [
            {
                "date": next_dates[0].isoformat(),
                "match_no": match["match_no"],
                "group": match["group"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "home": probs["home"],
                "draw": probs["draw"],
                "away": probs["away"],
                "home_expected_goals": home_xg,
                "away_expected_goals": away_xg,
                "score": "-".join(
                    str(goal)
                    for goal in outcome_constrained_median_scoreline(
                        home_xg,
                        away_xg,
                        cfg["goals"]["score_cap"],
                    )
                ),
            }
            for match, probs in zip(fixtures, fixture_rows)
            if match["date"] == next_dates[0]
            for home_xg, away_xg in [lambdas(match["home_team"], match["away_team"], match["venue_advantage"], adjusted_ratings, beta, s, cfg)]
        ]
        write_csv(out / "next_matchday_summary.csv", next_rows)
    (out / "tuning_summary.json").write_text(json.dumps(tuning, indent=2), encoding="utf-8")
    (out / "run_manifest.json").write_text(json.dumps({"as_of": cfg["forecast"]["as_of"], "simulations": sims, "coefficients": beta, "config": str(config_path)}, indent=2), encoding="utf-8")
    chart(out / "winner_odds.png", winner_rows, "team", "probability", "World Cup winner odds")
    status(f"Wrote forecast to {out}")
    if next_rows:
        table = [f"Next match day: {next_rows[0]['date']}", f"{'match':<5}  {'group':<5}  {'fixture':<28}  {'home':>6}  {'draw':>6}  {'away':>6}  {'score':>5}  {'xG':>9}"]
        for row in next_rows:
            fixture = f"{row['home_team']} vs {row['away_team']}"
            xg = f"{row['home_expected_goals']:.2f}-{row['away_expected_goals']:.2f}"
            table.append(f"{row['match_no']:<5}  {row['group']:<5}  {fixture:<28}  {100 * row['home']:>5.1f}%  {100 * row['draw']:>5.1f}%  {100 * row['away']:>5.1f}%  {row['score']:>5}  {xg:>9}")
        table_text = "\n".join(table)
        print(f"\n{table_text}")
        if update_readme:
            # Keep README next-matchday probabilities synced with CLI output.
            readme_table = "\n".join([table[0], *(line.rsplit("  ", 1)[0].rstrip() for line in table[1:])])
            readme = Path("README.md")
            text = readme.read_text(encoding="utf-8")
            start = text.index("```text\n", text.index("## Next match day forecasts")) + len("```text\n")
            end = text.index("\n```", start)
            readme.write_text(text[:start] + readme_table + text[end:], encoding="utf-8")


# Parses the CLI entry point and dispatches the predict command.
def main() -> None:
    parser = argparse.ArgumentParser(prog="wc-forecaster")
    sub = parser.add_subparsers(dest="command", required=True)
    predict_parser = sub.add_parser("predict")
    predict_parser.add_argument("--config", type=Path, default=Path("config/model.yaml"))
    predict_parser.add_argument("--as-of")
    args = parser.parse_args()
    predict(args.config, update_readme=True, as_of_override=args.as_of)
