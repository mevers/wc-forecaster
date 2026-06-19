# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

## Next match day forecasts

```text
Next match day: 2026-06-19
match  group  fixture                         home    draw    away  score
29     C      Brazil vs Haiti                78.3%   14.8%    6.9%    2-0
30     C      Scotland vs Morocco            24.9%   26.3%   48.9%    0-1
31     D      Turkey vs Paraguay             41.9%   27.8%   30.3%    1-1
32     D      United States vs Australia     41.4%   27.1%   31.6%    1-1
```

## Setup

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

## Predict

```sh
wc-forecaster predict
```

The command reads `config/model.yaml` and writes forecast artefacts to `outputs/<as_of>/`.

Key outputs are:

- `winner_odds.csv`: Title probabilities by team.
- `round_reach_probabilities.csv`: Probabilities of reaching each tournament round.
- `group_fixture_1x2_probabilities.csv`: Group-stage fixtures with 1X2 probabilities.
- `next_matchday_summary.csv`: Next match-day fixtures with 1X2 probabilities and expected goals.
- `derived_team_ratings.csv`: Pre-simulation model rating snapshot. It is based on historical and completed 2026 WC games.
- `team_adjustments.csv`: Squad cohesion, underdog magic, and adjusted forecast rating by team.
- `most_likely_group_tables.csv`: Expected group standings after group stage. This is used to seed the knockout bracket.
- `most_likely_knockout_bracket.csv`: Canonical most likely knockout bracket. Used as bracket input.
- `match_slot_matchup_marginals.csv`: Most common pairing for each knockout match slot across raw simulations. **Not a bracket input.**
- `match_slot_winner_marginals.csv`: Most common winner for each knockout match slot across raw simulations. **Not a bracket input.**
- `tuning_summary.json`: Tuning metadata
- `run_manifest.json`: Run metadata. Used in `scripts/draw_knockout_bracket.py`.
- `winner_odds.png`: WC winner probability chart.

Use `most_likely_knockout_bracket.csv` when you need an internally consistent knockout bracket. See `docs/model_spec.md` for the full artefact definitions and `docs/most_likely_knockout_bracket_methodology.md` for the bracket methodology.

## Render bracket

```sh
python3 scripts/draw_knockout_bracket.py --run-dir outputs/2026-06-14
```

Use `--bracket-method modal-group-table` to render the bracket seeded from the
most common complete table in each group. The default is `expected-table`,
which ranks groups by average simulated table performance before building the
bracket.

This reads `most_likely_knockout_bracket.csv` and `run_manifest.json` from that run directory, then writes `knockout_bracket_<bracket-method>.png` there.

## Data

Historical results live in `data/historical_results/`. Curated 2026 tournament data lives in `data/world_cup_2026/`, including fixtures, groups, third-place slot eligibility, and final squad composition in `squads.csv`. Source notes are in each directory's `SOURCES.md`.
