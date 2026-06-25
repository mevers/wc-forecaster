# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

## Next match day forecasts

```text
Next match day: 2026-06-25
match  group  fixture                         home    draw    away  score
55     D      Turkey vs United States        20.0%   24.6%   55.5%    1-1
56     D      Paraguay vs Australia          36.5%   27.7%   35.8%    1-1
57     E      Ecuador vs Germany             23.9%   26.0%   50.1%    1-1
58     E      Curacao vs Ivory Coast         17.3%   23.7%   59.0%    1-2
59     F      Japan vs Sweden                62.2%   22.3%   15.6%    2-1
60     F      Tunisia vs Netherlands          7.1%   14.9%   78.0%    0-2
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
