# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

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
- `round_probabilities.csv`: Probabilities of reaching each tournament round.
- `fixture_probabilities.csv`: Group-stage fixtures with 1X2 probabilities.
- `derived_team_ratings.csv`: Pre-simulation model rating snapshot. It is based on historical and completed 2026 WC games.
- `team_adjustments.csv`: Squad cohesion, underdog magic, and adjusted forecast rating by team.
- `most_likely_group_tables.csv`: Expected group standings after group stage. This is used to seed the knockout bracket.
- `most_likely_knockout_bracket.csv`: Canonical most likely knockout bracket.
- `tuning_summary.json` and `run_manifest.json`: Tuning and run metadata. `run_manifest.json` is used in `scripts/draw_knockout_bracket.py`.
- `winner_odds.png`: WC winner probability chart.

Deprecated outputs:

- `most_likely_bracket.csv`: Deprecated legacy marginal winner summary for each knockout match slot; not a bracket input.
- `most_likely_matchups.csv`: Deprecated legacy marginal pairing summary for each knockout match slot; not a bracket input.
- `most_likely_tournament_bracket.csv`: Deprecated copy of the expected-table knockout bracket, with winners chosen by head-to-head advancement probability.
- `most_likely_realised_bracket.csv`: Deprecated copy of the same expected-table knockout bracket, seeded from expected group standings and resolved by head-to-head advancement probability.

Use `most_likely_knockout_bracket.csv` when you need an internally consistent knockout bracket. Do not use the deprecated marginal knockout files to draw or describe the bracket. See `docs/model_spec.md` for the full artefact definitions and `docs/most_likely_knockout_bracket_methodology.md` for the bracket methodology.

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
