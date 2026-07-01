from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

ALIASES = {"Curaçao": "Curacao", "Côte d'Ivoire": "Ivory Coast", "Czech Republic": "Czechia", "USA": "United States", "Türkiye": "Turkey"}


# Normalises source team names to the model's canonical labels.
def team(name: str) -> str:
    return ALIASES.get(name, name)


# Reads a CSV into raw string-keyed rows.
def rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# Derives the venue indicator from either curated fixtures or historical rows.
def venue_advantage(row: dict[str, str], home: str, away: str) -> int:
    if "venue_advantage" in row:
        return int(row["venue_advantage"])
    if row["neutral"].upper() == "TRUE":
        return 0
    return -1 if team(row["country"]) == away else 1


# Converts result CSV rows into the match records consumed by the model.
def read_matches(path: str | Path) -> list[dict[str, Any]]:
    out = []
    for row in rows(path):
        home_score = row["home_score"]
        away_score = row["away_score"]
        # Support both historical result and 2026 fixture team column names.
        home = team(row.get("home_team", row.get("home", "")))
        away = team(row.get("away_team", row.get("away", "")))
        fixture_winner = team(row.get("fixture_winner", ""))
        out.append(
            {
                **row,
                "date": date.fromisoformat(row["date"]),
                "home_team": home,
                "away_team": away,
                "home_score": int(home_score) if home_score not in {"", "NA"} else None,
                "away_score": int(away_score) if away_score not in {"", "NA"} else None,
                "fixture_winner": fixture_winner or None,
                "venue_advantage": venue_advantage(row, home, away),
            }
        )
    return out


# Writes model output rows using the first row's field order.
def write_csv(path: Path, rows_: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_[0]))
        writer.writeheader()
        writer.writerows(rows_)
