# 2026 tournament data sources

Groups, schedule pattern, knockout slots, and third-place slot eligibility are curated from the FIFA 2026 pages mirrored in public match-schedule summaries and the knockout-stage reference page.

Completed score updates are taken from the public `martj42/international_results` CSV, not directly from FIFA:

```text
https://raw.githubusercontent.com/martj42/international_results/master/results.csv
```

`fixtures.csv` is the sole local source for 2026 FIFA World Cup tournament state. Matching 2026 World Cup rows are excluded from the packaged `data/historical_results/results.csv` file.

The third-place CSV stores official eligible groups per round-of-32 slot. The model resolves qualified third-place teams by deterministic matching because fair-play data and the full Annex C mapping are not part of the local data.

`fixtures.csv` uses `venue_advantage = 1` when team `home` has host advantage, `-1` when team `away` has host advantage, and `0` for neutral-site matches.
