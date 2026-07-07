# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

## Next match day forecasts

```text
Next match day: 2026-07-07
match  group  fixture                         home    draw    away  score
95     R16    Argentina vs Egypt             77.1%   15.4%    7.5%    2-0
96     R16    Switzerland vs Colombia        32.8%   27.2%   40.1%    1-2
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
- `next_matchday_summary.csv`: Next match-day fixtures with 1X2 probabilities, expected goals, and an outcome-constrained median scoreline.
- `derived_team_ratings.csv`: Pre-simulation model rating snapshot. It is based on historical and completed 2026 WC games.
- `team_adjustments.csv`: Squad cohesion, underdog magic, and adjusted forecast rating by team.
- `most_likely_group_tables.csv`: Expected group standings after group stage. Used to seed the knockout bracket and for the group table visualisation.
- `most_likely_knockout_bracket.csv`: Labelled knockout bracket options. Used as input for the bracket visualisation. It includes `expected-table`, `modal-group-table`, `title-favourite-bracket`, and `title-field-consensus-bracket` rows.
- `match_slot_matchup_marginals.csv`: Most common pairing for each knockout match slot across raw simulations. **Not a bracket input.**
- `match_slot_winner_marginals.csv`: Most common winner for each knockout match slot across raw simulations. **Not a bracket input.**
- `tuning_summary.json`: Tuning metadata
- `run_manifest.json`: Run metadata. Used in `scripts/draw_knockout_bracket.py`.
- `winner_odds.png`: WC winner probability chart.

Use `most_likely_knockout_bracket.csv` when you need an internally consistent knockout bracket. See `docs/model_spec.md` for the full artefact definitions and `docs/bracket_prediction_methods.md` for the bracket methodology.

## Render visualisations

```sh
python3 scripts/draw_knockout_bracket.py --run-dir outputs/2026-06-14
python3 scripts/draw_group_tables.py --run-dir outputs/2026-06-14
```

Choose the rendered bracket with `--bracket-method`:

- `all`: Render every implemented bracket method.
- `expected-table`: Default. Ranks groups by average simulated table performance, then advances the head-to-head favourite in each displayed knockout pairing.
- `modal-group-table`: Seeds the bracket from the most common complete ordered table in each group, then advances the head-to-head favourite in each displayed knockout pairing.
- `title-favourite-bracket`: Finds the empirical title favourite from `winner_odds.csv`, filters to simulations where that team wins the tournament, then renders the actual simulated route with the highest conditional bracket score.
- `title-field-consensus-bracket`: Recommended for bracket prediction. Filters to simulations where the empirical title favourite wins, then renders the route with the highest weighted QF/SF/final/champion field-consensus score.

Both scripts read forecast artefacts from the run directory and write SVG and PNG visualisations there.

## Data

Historical results live in `data/historical_results/`. Curated 2026 tournament data lives in `data/world_cup_2026/`, including fixtures, groups, third-place slot eligibility, and final squad composition in `squads.csv`. Source notes are in each directory's `SOURCES.md`.
