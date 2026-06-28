# 2026 tournament data sources

Groups, schedule pattern, knockout slots, and third-place slot eligibility are curated from the FIFA 2026 pages mirrored in public match-schedule summaries and the knockout-stage reference page.

Completed score updates are taken from the public `martj42/international_results` CSV, not directly from FIFA:

```text
https://raw.githubusercontent.com/martj42/international_results/master/results.csv
```

`fixtures.csv` is the sole local source for 2026 FIFA World Cup tournament state. Matching 2026 World Cup rows are excluded from the packaged `data/historical_results/results.csv` file.

The `match_no` values in `fixtures.csv` are internal match identifiers used by the model and bracket wiring. They are not official FIFA match numbers.

The third-place CSV stores official eligible groups per round-of-32 slot. The model resolves qualified third-place teams by deterministic matching because fair-play data and the full Annex C mapping are not part of the local data.

`fixtures.csv` uses `venue_advantage = 1` when team `home` has host advantage, `-1` when team `away` has host advantage, and `0` for neutral-site matches.

`squads.csv` is bootstrapped from the Wikipedia 2026 FIFA World Cup squads page:

```text
https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads
```

The squad metadata columns are taken from the Wikipedia squad table. The `league` column uses the club's national association / league-system country from the squad table's club flag, not the exact domestic division.
