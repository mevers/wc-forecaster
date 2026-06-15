# Historical results source

`results.csv` was downloaded from the public `martj42/international_results` repository:

```text
https://raw.githubusercontent.com/martj42/international_results/master/results.csv
```

At download time the upstream file contained 49,477 rows from 1872-11-30 through 2026-06-27, including 2026 World Cup fixtures with `NA` scores.

This local copy excludes all 2026 FIFA World Cup rows. The current tournament state is stored in `data/world_cup_2026/fixtures.csv` so completed 2026 World Cup matches are represented in one place only.
