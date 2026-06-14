from __future__ import annotations

from pathlib import Path

import yaml

from wc_forecaster.cli import load_config, predict


def test_load_config(tmp_path: Path) -> None:
    path = tmp_path / "model.yaml"
    path.write_text("forecast:\n  simulations: 2\n", encoding="utf-8")
    assert load_config(path)["forecast"]["simulations"] == 2


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
