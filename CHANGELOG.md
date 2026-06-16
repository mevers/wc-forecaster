# Changelog

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
