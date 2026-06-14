# World Cup forecaster

Minimal Python model for forecasting the live 2026 FIFA World Cup and rendering forecast artefacts.

## Setup

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## Predict

```sh
wc-forecaster predict
```

The command reads `config/model.yaml` and writes forecast artefacts to `outputs/`.

Useful outputs include winner odds, round probabilities, derived team ratings, fixture probabilities, the most likely bracket, most likely matchups, a tuning summary, a run manifest, and a winner-odds chart.

This reads the CSV and JSON artefacts in `outputs/` and writes `outputs/knockout_bracket.png`.

## Data

Historical results live in `data/historical_results/`. Curated 2026 tournament data lives in `data/world_cup_2026/`. Source notes are in each directory's `SOURCES.md`.
