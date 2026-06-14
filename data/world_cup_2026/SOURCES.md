# 2026 tournament data sources

Groups, schedule pattern, knockout slots, and third-place slot eligibility are curated from the FIFA 2026 pages mirrored in public match-schedule summaries and the knockout-stage reference page.

Completed results included as of 14 June 2026:

- Mexico 2-0 South Africa, South Korea 2-1 Czechia, Canada 1-1 Bosnia and Herzegovina, United States 4-1 Paraguay, Brazil 1-1 Morocco, Scotland 1-0 Haiti, Qatar 1-1 Switzerland: SB Nation schedule/results summary and the historical results CSV.
- Brazil 1-1 Morocco and Haiti 0-1 Scotland cross-checks: Guardian match reports.
- Australia 2-0 Turkey: contemporary tournament summary.

The third-place CSV stores official eligible groups per round-of-32 slot. The model resolves qualified third-place teams by deterministic matching because fair-play data and the full Annex C mapping are not part of the local data.

`fixtures.csv` uses `venue_advantage = 1` when team `home` has host advantage, `-1` when team `away` has host advantage, and `0` for neutral-site matches.
