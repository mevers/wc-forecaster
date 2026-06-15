from __future__ import annotations

import csv
from pathlib import Path

import yaml

from wc_forecaster.bracket import advancement_probabilities, expected_group_tables
from wc_forecaster.cli import load_config, predict
from wc_forecaster.tournament import BRACKET, RO32


CFG = {
    "elo": {"venue_advantage": 70.0},
    "goals": {"score_cap": 4, "min_expected_goals": 0.15},
    "form": {"gamma": 0.05},
    "knockout": {"penalty_rating_scale": 500.0},
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
    rows = expected_group_tables({"A": ["Alpha", "Beta", "Gamma", "Delta"]}, result, 2, {"Alpha": 1500, "Beta": 1400, "Gamma": 1300, "Delta": 1600})["A"]
    assert [row["team"] for row in rows] == ["Beta", "Alpha", "Gamma", "Delta"]


def test_advancement_probabilities_favour_stronger_team() -> None:
    team_a, team_b = advancement_probabilities("A", "B", {"A": 1600, "B": 1400}, [0.2, 0.1, 0.0], {}, CFG)
    assert team_a > team_b
    assert round(team_a + team_b, 10) == 1


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
    cfg = {
        "data": {"historical_results": str(hist), "groups": "data/world_cup_2026/groups.csv", "fixtures": "data/world_cup_2026/fixtures.csv", "third_place_slots": "data/world_cup_2026/third_place_slots.csv", "output_dir": str(tmp_path / "out")},
        "forecast": {"as_of": "2026-06-14", "simulations": 2, "seed": 1},
        "fit": {"tune": False, "half_life": 2.5, "half_life_years": [2.5]},
        "elo": {"initial": 1500.0, "divisor": 400.0, "venue_advantage": 70.0, "k": {"FIFA World Cup": 60.0, "Friendly": 20.0, "default": 30.0}},
        "goals": {"score_cap": 4, "min_expected_goals": 0.15, "min_expected_goals_values": [0.15]},
        "form": {"gamma": 0.05},
        "knockout": {"penalty_rating_scale": 500.0},
    }
    config = tmp_path / "model.yaml"
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    predict(config)
    assert (tmp_path / "out" / "winner_odds.csv").exists()
    assert (tmp_path / "out" / "most_likely_group_tables.csv").exists()
    assert (tmp_path / "out" / "most_likely_tournament_bracket.csv").exists()
    with (tmp_path / "out" / "fixture_probabilities.csv").open(encoding="utf-8") as handle:
        fixture = next(csv.DictReader(handle))
    assert fixture["home_team"] == "Mexico"
    assert fixture["away_team"] == "South Africa"
    with (tmp_path / "out" / "most_likely_tournament_bracket.csv").open(encoding="utf-8") as handle:
        realised = {int(row["match_no"]): row for row in csv.DictReader(handle)}
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
    fixtures = tmp_path / "fixtures.csv"
    fixtures.write_text(
        "match_no,group,date,home,away,home_score,away_score,venue_advantage\n"
        "1,A,2026-06-15,Mexico,South Africa,0,10,0\n",
        encoding="utf-8",
    )
    cfg = {
        "data": {"historical_results": str(hist), "groups": "data/world_cup_2026/groups.csv", "fixtures": str(fixtures), "third_place_slots": "data/world_cup_2026/third_place_slots.csv", "output_dir": str(tmp_path / "out")},
        "forecast": {"as_of": "2026-06-14", "simulations": 1, "seed": 1},
        "fit": {"tune": False, "half_life": 2.5, "half_life_years": [2.5]},
        "elo": {"initial": 1500.0, "divisor": 400.0, "venue_advantage": 70.0, "k": {"FIFA World Cup": 60.0, "Friendly": 20.0, "default": 30.0}},
        "goals": {"score_cap": 4, "min_expected_goals": 0.15, "min_expected_goals_values": [0.15]},
        "form": {"gamma": 0.05},
        "knockout": {"penalty_rating_scale": 500.0},
    }
    config = tmp_path / "model.yaml"
    config.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    predict(config)
    with (tmp_path / "out" / "derived_team_ratings.csv").open(encoding="utf-8") as handle:
        next(handle)
        ratings = {row["team"]: float(row["rating"]) for row in csv.DictReader(handle)}
    assert ratings["Mexico"] > ratings["South Africa"]
