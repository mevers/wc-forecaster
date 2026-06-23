# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

## Next match day forecasts

```text
Next match day: 2026-06-23
match  group  fixture                         home    draw    away  score
45     L      England vs Ghana               83.4%   11.6%    5.0%    3-0
46     L      Panama vs Croatia              20.4%   25.2%   54.4%    1-1
47     K      Portugal vs Uzbekistan         58.6%   23.8%   17.5%    2-1
48     K      Colombia vs DR Congo           70.3%   18.8%   10.9%    2-0
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
- `next_matchday_summary.csv`: Next match-day fixtures with 1X2 probabilities, expected goals, and a median scoreline.
- `derived_team_ratings.csv`: Pre-simulation model rating snapshot. It is based on historical and completed 2026 WC games.
- `team_adjustments.csv`: Squad cohesion, underdog magic, and adjusted forecast rating by team.
- `most_likely_group_tables.csv`: Expected group standings after group stage. Used to seed the knockout bracket and for the group table visualisation.
- `most_likely_knockout_bracket.csv`: Canonical most likely knockout bracket. Used as input for the bracket visualisation.
- `match_slot_matchup_marginals.csv`: Most common pairing for each knockout match slot across raw simulations. **Not a bracket input.**
- `match_slot_winner_marginals.csv`: Most common winner for each knockout match slot across raw simulations. **Not a bracket input.**
- `tuning_summary.json`: Tuning metadata
- `run_manifest.json`: Run metadata. Used in `scripts/draw_knockout_bracket.py`.
- `winner_odds.png`: WC winner probability chart.

Use `most_likely_knockout_bracket.csv` when you need an internally consistent knockout bracket. See `docs/model_spec.md` for the full artefact definitions and `docs/most_likely_knockout_bracket_methodology.md` for the bracket methodology.

## Render visualisations

```sh
python3 scripts/draw_knockout_bracket.py --run-dir outputs/2026-06-14
python3 scripts/draw_group_tables.py --run-dir outputs/2026-06-14
```

Use `--bracket-method modal-group-table` to render the bracket seeded from the
most common complete table in each group. The default is `expected-table`,
which ranks groups by average simulated table performance before building the
bracket.

Both scripts read forecast artefacts from the run directory and write SVG and PNG visualisations there.

## Data

Historical results live in `data/historical_results/`. Curated 2026 tournament data lives in `data/world_cup_2026/`, including fixtures, groups, third-place slot eligibility, and final squad composition in `squads.csv`. Source notes are in each directory's `SOURCES.md`.
