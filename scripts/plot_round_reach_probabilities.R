library(tidyverse)
library(ragg)
library(ggtext)


args <- commandArgs(trailingOnly = TRUE)
run_dir <- args[match("--run-dir", args) + 1]

df <- read_csv(file.path(run_dir, "round_reach_probabilities.csv")) |>
    bind_rows(
        read_csv(file.path(run_dir, "winner_odds.csv")) |> 
        mutate(round = "winner"))

rounds_of_interest <- c(
    `Quarter-Finals` = "quarter_final", 
    `Semi-Finals` = "semi_final", 
    `Final` = "final", 
    `Winner` = "winner")
flag_codes <- tribble(
    ~team, ~flag,
    "Argentina", "ar",
    "Algeria", "dz",
    "Australia", "au",
    "Austria", "at",
    "Belgium", "be",
    "Bosnia and Herzegovina", "ba",
    "Brazil", "br",
    "Canada", "ca",
    "Cape Verde", "cv",
    "Colombia", "co",
    "Croatia", "hr",
    "Curacao", "cw",
    "Czechia", "cz",
    "DR Congo", "cd",
    "Ecuador", "ec",
    "Egypt", "eg",
    "England", "gb-eng",
    "France", "fr",
    "Germany", "de",
    "Ghana", "gh",
    "Haiti", "ht",
    "Iran", "ir",
    "Iraq", "iq",
    "Ivory Coast", "ci",
    "Japan", "jp",
    "Jordan", "jo",
    "Mexico", "mx",
    "Morocco", "ma",
    "Netherlands", "nl",
    "New Zealand", "nz",
    "Norway", "no",
    "Panama", "pa",
    "Paraguay", "py",
    "Portugal", "pt",
    "Qatar", "qa",
    "Saudi Arabia", "sa",
    "Scotland", "gb-sct",
    "Senegal", "sn",
    "South Africa", "za",
    "South Korea", "kr",
    "Spain", "es",
    "Sweden", "se",
    "Switzerland", "ch",
    "Turkey", "tr",
    "Tunisia", "tn",
    "United States", "us",
    "Uruguay", "uy",
    "Uzbekistan", "uz"
)
top_teams <- df |>
    filter(round == "winner") |>
    arrange(desc(probability)) |>
    slice_head(n = 20) |>
    pull(team)
team_labels <- flag_codes |>
    filter(team %in% top_teams) |>
    mutate(label = paste0("<sup>", team, "                         ", "</sup> <img src='outputs/flags/", flag, ".png' width='14'/>")) |>
    select(team, label) |>
    deframe()

p <- df |> 
    filter(round %in% rounds_of_interest, team %in% top_teams) |>
    mutate(
        team = factor(team, levels = rev(top_teams)),
        round = factor(round, levels = rounds_of_interest, labels = names(rounds_of_interest))) |>
    ggplot(aes(
        y = team, 
        x = round, fill = probability)) +
    geom_tile() +
    geom_text(
        aes(label = scales::percent(probability, accuracy = 0.1)), 
        colour = "#333333", family = "Fira Sans", fontface = "bold", size = 3) +
    scale_fill_gradient(low = "white", high = "#f4a3a3") +
    scale_x_discrete(name = "") +
    scale_y_discrete(name = "", labels = team_labels) +
    theme_minimal(base_family = "Fira Sans") + 
    theme(
        axis.text.y.left = ggtext::element_markdown(family = "Fira Sans"),
        plot.caption = element_text(size = 6, colour = "grey50")) +
    guides(fill = "none") + 
    labs(
        title = "FIFA World Cup 2026 (1st - 20th)", 
        subtitle = sprintf("Round predictions as of %s", format(as.Date(basename(run_dir)), "%d %b %Y")),
        caption = "[https://github.com/mevers/wc-forecaster]")
ggsave(
    file.path(run_dir, "round_reach_probabilities.png"), 
    p, height = 5, width = 5, device = agg_png)
