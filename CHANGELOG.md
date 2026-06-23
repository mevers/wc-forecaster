# Changelog

## v0.6.0

- Added an expected group-table visualisation with to-date and forecast metrics.
- Tweaked the expected group-table and bracket visualisations
- Changed next match-day scoreline reporting from marginal Poisson modes to medians, minimising expected absolute goal error.

## v0.5.1

- Corrected the Group F and Group J fixtures in the 2026 World Cup schedule.

## v0.5.0

- Replaced the log-transformed WLS model with a weighted Poisson GLM.
- Added the most likely scoreline to next match-day forecasts.
- Added a script for analysing outcome and scoreline upsets.
- Added a CLI option `--as-of` to override the forecast date.

## v0.4.0

- Added squad cohesion and underdog-magic adjustments to forecast ratings.
- Added squad data and `team_adjustments.csv`.
- Added next match-day CLI, CSV, and README summary with expected goals.
- Renamed output artefacts to have more meaningful names.

## v0.3.0

- Store forecast artefacts under `outputs/<as_of>/`.
- Render knockout brackets from an explicit dated run directory with `--run-dir`.
- Simulate the match 103 third-place play-off in Monte Carlo tournament paths.
- Added selectable bracket methods via `scripts/draw_knockout_bracket.py --bracket-method`, including `expected-table` and `modal-group-table` options with method-specific rendered filenames and subtitles.
- Added a script to update 2026 World Cup fixture scores from `martj42/international_results` and bump `forecast.as_of`.

## v0.2.0

- Added expected-table group standings in `most_likely_group_tables.csv`.
- Added the canonical expected-table knockout bracket in `most_likely_knockout_bracket.csv`.
- Added deprecated compatibility copies for older bracket artefact names.
- Added knockout bracket rendering to SVG and PNG.
- Documented the knockout bracket methodology and output artefact semantics.

## v0.1.0

- Initial version.
