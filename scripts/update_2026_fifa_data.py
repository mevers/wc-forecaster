from __future__ import annotations

import csv
import re
from io import TextIOWrapper
from pathlib import Path
from urllib.request import urlopen


SOURCE = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/world_cup_2026/fixtures.csv"
CONFIG = ROOT / "config/model.yaml"
ALIASES = {
    "Curaçao": "Curacao",
    "Côte d'Ivoire": "Ivory Coast",
    "Czech Republic": "Czechia",
    "USA": "United States",
    "Türkiye": "Turkey",
}


def team(name: str) -> str:
    return ALIASES.get(name, name)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def source_scores(source: str) -> dict[tuple[str, str, str], tuple[str, str]]:
    with urlopen(source) as response:
        rows = list(csv.DictReader(TextIOWrapper(response, encoding="utf-8")))
    return {
        (row["date"], team(row["home_team"]), team(row["away_team"])): (
            row["home_score"],
            row["away_score"],
        )
        for row in rows
        if row["date"].startswith("2026-")
        and row["tournament"] == "FIFA World Cup"
        and row["home_score"] != "NA"
    }


def main(source: str = SOURCE) -> None:
    scores = source_scores(source)
    fixtures = read_csv(FIXTURES)
    changed = 0
    matched_dates = []
    for row in fixtures:
        key = (row["date"], team(row["home"]), team(row["away"]))
        if key in scores:
            matched_dates.append(row["date"])
            if (row["home_score"], row["away_score"]) != scores[key]:
                row["home_score"], row["away_score"] = scores[key]
                changed += 1

    write_csv(FIXTURES, fixtures)

    latest_date = max(matched_dates)
    config = CONFIG.read_text(encoding="utf-8")
    CONFIG.write_text(
        re.sub(r'  as_of: "\d{4}-\d{2}-\d{2}"', f'  as_of: "{latest_date}"', config, count=1),
        encoding="utf-8",
    )

    print(f"Updated {changed} fixture rows; forecast.as_of is {latest_date}.")


if __name__ == "__main__":
    main()
