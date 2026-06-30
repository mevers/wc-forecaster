library(tidyverse)
library(tidyverse)

fn <- list.files(
    "outputs/", pattern = "derived_team", full.names = TRUE, recursive = TRUE)
dates <- str_remove_all(fn, "outputs|derived_team_ratings.csv|/")


r32_teams <- read_csv("data/world_cup_2026/fixtures.csv") |>
    filter(group == "R32") |>
    select(home, away) |>
    stack() |>
    pull(values) |>
    sort()
r32_teams

df <- fn |>
    set_names(dates) |>
    map_dfr(~ read_csv(.x, comment = "#"), .id = "as_of", )


data <- df |>
    mutate(
        as_of = as.Date(as_of),
        dow = wday(as_of, label = TRUE),
        week = isoweek(as_of)) |>
    arrange(as_of) |>
    group_by(team) |>
    mutate(
        r0 = rating[as_of == min(as_of)],
        dr = rating - r0,
        cdr = cumsum(dr),
        tmp = c(0, cumsum(diff(rating)))) |>
    ungroup()
data



data |>
    filter(team %in% r32_teams) |>
    ggplot(aes(as_of, cdr)) +
    geom_step() +
    theme_minimal() + 
    theme(legend.position = "bottom") +
    facet_wrap(~ team, ncol = 8)
