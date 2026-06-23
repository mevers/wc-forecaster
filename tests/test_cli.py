from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from wc_forecaster.bracket import (
    advancement_probabilities,
    expected_group_tables,
    modal_group_tables,
)
from wc_forecaster.cli import load_config, predict
from wc_forecaster.model import poisson_median
from wc_forecaster.tournament import BRACKET, RO32


CFG = {
    "elo": {"venue_advantage": 70.0},
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


def write_squads(path: Path) -> None:
    with Path("data/world_cup_2026/groups.csv").open(encoding="utf-8") as handle:
        teams = [row["team"] for row in csv.DictReader(handle)]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("team,number,position,player,date_of_birth,age,caps,goals,club,league\n")
        for team in teams:
            handle.write(f"{team},1,GK,{team} Player,2000-01-01,26,0,0,{team} Club,{team}\n")


def predict_config(
    hist: Path,
    fixtures: str,
    squads: Path,
    out: Path,
    simulations: int,
) -> dict[str, Any]:
    return {
        "data": {
            "historical_results": str(hist),
            "groups": "data/world_cup_2026/groups.csv",
            "fixtures": fixtures,
            "squads": str(squads),
            "third_place_slots": "data/world_cup_2026/third_place_slots.csv",
            "output_dir": str(out),
        },
        "forecast": {"as_of": "2026-06-14", "simulations": simulations, "seed": 1},
        "fit": {"tune": False, "half_life": 2.5, "half_life_years": [2.5]},
        "elo": {
            "initial": 1500.0,
            "divisor": 400.0,
            "venue_advantage": 70.0,
            "k": {"FIFA World Cup": 60.0, "Friendly": 20.0, "default": 30.0},
        },
        "goals": {
            "score_cap": 4,
            "min_expected_goals": 0.15,
            "min_expected_goals_values": [0.15],
        },
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


def test_load_config(tmp_path: Path) -> None:
    path = tmp_path / "model.yaml"
    path.write_text("forecast:\n  simulations: 2\n", encoding="utf-8")
    assert load_config(path)["forecast"]["simulations"] == 2


def test_expected_group_tables_rank_by_expected_table_metrics() -> None:
    result = {
        "group_metrics": {
            "A": {
                "Alpha": {"points": 10, "goal_difference": 1, "goals_for": 2},
                "Beta": {"points": 10, "goal_difference": 3, "goals_for": 1},
                "Gamma": {"points": 8, "goal_difference": 4, "goals_for": 5},
                "Delta": {"points": 8, "goal_difference": 4, "goals_for": 2},
            }
        }
    }
    rows = expected_group_tables(
        {"A": ["Alpha", "Beta", "Gamma", "Delta"]},
        result,
        2,
        {"Alpha": 1500, "Beta": 1400, "Gamma": 1300, "Delta": 1600},
    )["A"]
    assert [row["team"] for row in rows] == ["Beta", "Alpha", "Gamma", "Delta"]


def test_advancement_probabilities_favour_stronger_team() -> None:
    team_a, team_b = advancement_probabilities(
        "A",
        "B",
        {"A": 1600, "B": 1400},
        [0.2, 0.1, 0.0],
        {},
        CFG,
    )
    assert team_a > team_b
    assert round(team_a + team_b, 10) == 1


def test_modal_group_tables_use_most_common_complete_group_table() -> None:
    result = {
        "group_tables": {
            "A": Counter(
                {
                    (
                        ("Alpha", 7, 3, 5),
                        ("Beta", 5, 1, 4),
                        ("Gamma", 3, -1, 2),
                        ("Delta", 1, -3, 1),
                    ): 1,
                    (
                        ("Beta", 6, 2, 4),
                        ("Alpha", 4, 0, 3),
                        ("Gamma", 4, 0, 2),
                        ("Delta", 2, -2, 1),
                    ): 2,
                }
            )
        }
    }
    rows = modal_group_tables({"A": ["Alpha", "Beta", "Gamma", "Delta"]}, result)["A"]
    assert [(row["position"], row["team"], row["expected_points"]) for row in rows] == [
        (1, "Beta", 6),
        (2, "Alpha", 4),
        (3, "Gamma", 4),
        (4, "Delta", 2),
    ]


def test_predict_smoke(tmp_path: Path) -> None:
    hist = tmp_path / "results.csv"
    hist.write_text(
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2017-01-01,Mexico,South Africa,2,0,Friendly,x,Mexico,FALSE\n"
        "2018-06-15,Brazil,Morocco,1,0,FIFA World Cup,x,x,TRUE\n"
        "2018-06-16,Canada,Switzerland,0,1,FIFA World Cup,x,x,TRUE\n"
        "2022-11-21,United States,Paraguay,0,0,FIFA World Cup,x,x,TRUE\n"
        "2024-01-01,Argentina,Spain,1,2,Friendly,x,Spain,FALSE\n"
        "2025-01-01,Spain,Argentina,3,1,Friendly,x,x,TRUE\n",
        encoding="utf-8",
    )
    squads = tmp_path / "squads.csv"
    write_squads(squads)
    cfg = predict_config(hist, "data/world_cup_2026/fixtures.csv", squads, tmp_path / "out", 2)
    config = tmp_path / "model.yaml"
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    predict(config)
    out = tmp_path / "out" / "2026-06-14"
    assert (out / "winner_odds.csv").exists()
    assert (out / "team_adjustments.csv").exists()
    assert (out / "most_likely_group_tables.csv").exists()
    assert (out / "most_likely_knockout_bracket.csv").exists()
    assert (out / "next_matchday_summary.csv").exists()
    assert (out / "match_slot_matchup_marginals.csv").exists()
    assert (out / "match_slot_winner_marginals.csv").exists()
    assert not (out / "most_likely_bracket.csv").exists()
    assert not (out / "most_likely_tournament_bracket.csv").exists()
    assert not (out / "most_likely_realised_bracket.csv").exists()
    with (out / "group_fixture_1x2_probabilities.csv").open(encoding="utf-8") as handle:
        fixture = next(csv.DictReader(handle))
    assert fixture["home_team"] == "Mexico"
    assert fixture["away_team"] == "South Africa"
    with (out / "next_matchday_summary.csv").open(encoding="utf-8") as handle:
        next_fixture = next(csv.DictReader(handle))
    assert next_fixture["score"] == (
        f"{poisson_median(float(next_fixture['home_expected_goals']), 4)}-"
        f"{poisson_median(float(next_fixture['away_expected_goals']), 4)}"
    )
    with (out / "most_likely_knockout_bracket.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    realised = {
        int(row["match_no"]): row for row in rows if row["bracket_method"] == "expected-table"
    }
    assert {row["bracket_method"] for row in rows} == {"expected-table", "modal-group-table"}
    assert 103 in realised
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert "bracket_method" not in manifest
    with (out / "team_adjustments.csv").open(encoding="utf-8") as handle:
        adjustment = next(csv.DictReader(handle))
    assert adjustment["base_rating"]
    assert adjustment["adjusted_rating"]
    round_of_32_teams = [
        team
        for match_no in RO32
        for team in (realised[match_no]["team_a"], realised[match_no]["team_b"])
    ]
    assert len(round_of_32_teams) == len(set(round_of_32_teams))
    assert all(row["winner"] in {row["team_a"], row["team_b"]} for row in realised.values())
    assert all(
        float(row["team_a_advance_probability"]) >= float(row["team_b_advance_probability"])
        if row["winner"] == row["team_a"]
        else float(row["team_b_advance_probability"]) > float(row["team_a_advance_probability"])
        for row in realised.values()
    )
    assert all(
        {realised[left]["winner"], realised[right]["winner"]}
        == {realised[parent]["team_a"], realised[parent]["team_b"]}
        for parent, left, right in BRACKET
    )


def test_predict_ignores_future_dated_scored_fixtures_for_ratings(tmp_path: Path) -> None:
    hist = tmp_path / "results.csv"
    hist.write_text(
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2017-01-01,Mexico,South Africa,2,0,Friendly,x,Mexico,FALSE\n"
        "2018-06-15,Brazil,Morocco,1,0,FIFA World Cup,x,x,TRUE\n"
        "2018-06-16,Canada,Switzerland,0,1,FIFA World Cup,x,x,TRUE\n"
        "2022-11-21,United States,Paraguay,0,0,FIFA World Cup,x,x,TRUE\n"
        "2024-01-01,Argentina,Spain,1,2,Friendly,x,Spain,FALSE\n"
        "2025-01-01,Spain,Argentina,3,1,Friendly,x,x,TRUE\n",
        encoding="utf-8",
    )
    squads = tmp_path / "squads.csv"
    write_squads(squads)
    fixtures = tmp_path / "fixtures.csv"
    fixtures.write_text(
        "match_no,group,date,home,away,home_score,away_score,venue_advantage\n"
        "1,A,2026-06-15,Mexico,South Africa,0,10,0\n",
        encoding="utf-8",
    )
    cfg = predict_config(hist, str(fixtures), squads, tmp_path / "out", 1)
    config = tmp_path / "model.yaml"
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    predict(config)
    ratings_path = tmp_path / "out" / "2026-06-14" / "derived_team_ratings.csv"
    with ratings_path.open(encoding="utf-8") as handle:
        next(handle)
        ratings = {row["team"]: float(row["rating"]) for row in csv.DictReader(handle)}
    assert ratings["Mexico"] > ratings["South Africa"]
