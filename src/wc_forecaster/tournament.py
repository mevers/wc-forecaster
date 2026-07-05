from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Any

from wc_forecaster.model import sample_score

RO32 = {
    73: ("2A", "2B"),
    74: ("1E", "3"),
    75: ("1F", "2C"),
    76: ("1C", "2F"),
    77: ("1I", "3"),
    78: ("2E", "2I"),
    79: ("1A", "3"),
    80: ("1L", "3"),
    81: ("1D", "3"),
    82: ("1G", "3"),
    83: ("2K", "2L"),
    84: ("1H", "2J"),
    85: ("1B", "3"),
    86: ("1J", "2H"),
    87: ("1K", "3"),
    88: ("2D", "2G"),
}
BRACKET = [(89, 73, 75), (90, 74, 77), (91, 76, 78), (92, 79, 80), (93, 83, 84), (94, 81, 82), (95, 86, 88), (96, 85, 87), (97, 89, 90), (98, 93, 94), (99, 91, 92), (100, 95, 96), (101, 97, 98), (102, 99, 100), (104, 101, 102)]
ROUNDS = {73: "round_of_32", 89: "round_of_16", 97: "quarter_final", 101: "semi_final", 104: "final"}


# Creates the mutable group table state for one simulation path.
def table(teams: list[str]) -> dict[str, dict[str, int]]:
    return {team: {"points": 0, "gf": 0, "ga": 0} for team in teams}


# Applies one regulation-time group result to points and goals.
def add_result(tab: dict[str, dict[str, int]], home: str, away: str, hs: int, aw: int) -> None:
    tab[home]["gf"] += hs
    tab[home]["ga"] += aw
    tab[away]["gf"] += aw
    tab[away]["ga"] += hs
    tab[home]["points"] += 3 if hs > aw else 1 if hs == aw else 0
    tab[away]["points"] += 3 if aw > hs else 1 if hs == aw else 0


# Ranks group teams by points, goal difference, goals for, then rating.
def rank(tab: dict[str, dict[str, int]], ratings: dict[str, float]) -> list[str]:
    return sorted(tab, key=lambda t: (tab[t]["points"], tab[t]["gf"] - tab[t]["ga"], tab[t]["gf"], ratings[t]), reverse=True)


# Assigns best third-place teams to eligible round-of-32 slots.
def third_assignment(thirds: list[str], slots: dict[int, set[str]]) -> dict[int, str]:
    groups = {team[-1]: team for team in thirds}
    out: dict[int, str] = {}

    # Backtracks over constrained slots so each third-place group is used once.
    def search(matches: list[int]) -> bool:
        if not matches:
            return True
        match = min(matches, key=lambda m: len(slots[m] & groups.keys()))
        for group in sorted(slots[match] & groups.keys()):
            out[match] = groups.pop(group)
            if search([m for m in matches if m != match]):
                return True
            groups[group] = out.pop(match)
        return False

    search(list(slots))
    return out


# Simulates or resolves one knockout match and updates previous-win state.
def winner(rng: random.Random, team_a: str, team_b: str, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any], venue_advantage: int = 0) -> str:
    goals_a, goals_b = sample_score(rng, team_a, team_b, venue_advantage, ratings, beta, s, cfg)
    if goals_a != goals_b:
        won = team_a if goals_a > goals_b else team_b
    else:
        p = 1 / (1 + 10 ** ((ratings[team_b] - ratings[team_a]) / cfg["knockout"]["penalty_rating_scale"]))
        won = team_a if rng.random() < p else team_b
    s[team_a] = won == team_a
    s[team_b] = won == team_b
    return won


# Runs Monte Carlo tournament paths and accumulates empirical output counters.
def simulate(groups: dict[str, list[str]], fixtures: list[dict[str, Any]], slots: dict[int, set[str]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any], status: Any = None) -> dict[str, Any]:
    rng = random.Random(cfg["forecast"]["seed"])
    title = Counter()
    reached = defaultdict(Counter)
    group_metrics = defaultdict(lambda: defaultdict(Counter))
    group_tables = defaultdict(Counter)
    matchups = defaultdict(Counter)
    match_winners = defaultdict(Counter)
    knockout_paths = []
    knockout_fixtures = {int(match["match_no"]): match for match in fixtures if match["group"] not in groups}
    sims = cfg["forecast"]["simulations"]
    step = max(1, sims // 10)
    for sim in range(1, sims + 1):
        # Keep previous-win form state path-local across simulated fixtures.
        s_sim = s.copy()
        qualifiers = {}
        thirds = []
        for group, teams in groups.items():
            tab = table(teams)
            for match in sorted((f for f in fixtures if f["group"] == group), key=lambda f: f["date"]):
                # Use recorded scores for completed fixtures and sample unplayed ones.
                hs, aw = (match["home_score"], match["away_score"]) if match["home_score"] is not None else sample_score(rng, match["home_team"], match["away_team"], match["venue_advantage"], ratings, beta, s_sim, cfg)
                add_result(tab, match["home_team"], match["away_team"], hs, aw)
                s_sim[match["home_team"]] = hs > aw
                s_sim[match["away_team"]] = aw > hs
            ordered = rank(tab, ratings)
            for team_name in teams:
                group_metrics[group][team_name]["points"] += tab[team_name]["points"]
                group_metrics[group][team_name]["goal_difference"] += tab[team_name]["gf"] - tab[team_name]["ga"]
                group_metrics[group][team_name]["goals_for"] += tab[team_name]["gf"]
            group_tables[group][tuple((team_name, tab[team_name]["points"], tab[team_name]["gf"] - tab[team_name]["ga"], tab[team_name]["gf"]) for team_name in ordered)] += 1
            qualifiers[f"1{group}"] = ordered[0]
            qualifiers[f"2{group}"] = ordered[1]
            thirds.append((ordered[2], group, tab[ordered[2]]["points"], tab[ordered[2]]["gf"] - tab[ordered[2]]["ga"], tab[ordered[2]]["gf"]))
        # Select eight best third-place teams and map them into eligible slots.
        thirds_by_match = third_assignment([f"{row[0]}:{row[1]}" for row in sorted(thirds, key=lambda r: (r[2], r[3], r[4], ratings[r[0]]), reverse=True)[:8]], slots)
        winners = {}
        knockout_teams: dict[int, tuple[str, str]] = {}
        knockout_path = []
        for match_no, pair in RO32.items():
            match = knockout_fixtures.get(match_no)
            home = match["home_team"] if match else qualifiers[pair[0]]
            away = match["away_team"] if match else thirds_by_match[match_no].split(":")[0] if pair[1] == "3" else qualifiers[pair[1]]
            matchups[match_no][(home, away)] += 1
            winners[match_no] = winner(rng, home, away, ratings, beta, s_sim, cfg, match["venue_advantage"] if match else 0)
            # Use recorded knockout winners when completed fixtures exist.
            if match and match["home_score"] is not None and match["fixture_winner"]:
                winners[match_no] = match["fixture_winner"]
                s_sim[home], s_sim[away] = winners[match_no] == home, winners[match_no] == away
            match_winners[match_no][winners[match_no]] += 1
            knockout_path.append((match_no, home, away, winners[match_no]))
            reached["round_of_32"][home] += 1
            reached["round_of_32"][away] += 1
        for match_no, left, right in BRACKET:
            if match_no == 104:
                # Resolve match 103 from the two semi-final losers before the final.
                team_a = next(team for team in knockout_teams[101] if team != winners[101])
                team_b = next(team for team in knockout_teams[102] if team != winners[102])
                matchups[103][(team_a, team_b)] += 1
                winners[103] = winner(rng, team_a, team_b, ratings, beta, s_sim, cfg)
                match_winners[103][winners[103]] += 1
                knockout_path.append((103, team_a, team_b, winners[103]))
            left_team = winners[left]
            right_team = winners[right]
            fixture = knockout_fixtures.get(match_no)
            if fixture and {fixture["home_team"], fixture["away_team"]} == {left_team, right_team}:
                left_team = fixture["home_team"]
                right_team = fixture["away_team"]
            else:
                fixture = None
            matchups[match_no][(left_team, right_team)] += 1
            reached[next(name for start, name in sorted(ROUNDS.items(), reverse=True) if match_no >= start)].update((left_team, right_team))
            winners[match_no] = winner(rng, left_team, right_team, ratings, beta, s_sim, cfg, fixture["venue_advantage"] if fixture else 0)
            if fixture and fixture["home_score"] is not None and fixture["fixture_winner"]:
                winners[match_no] = fixture["fixture_winner"]
                s_sim[left_team], s_sim[right_team] = winners[match_no] == left_team, winners[match_no] == right_team
            match_winners[match_no][winners[match_no]] += 1
            knockout_teams[match_no] = (left_team, right_team)
            knockout_path.append((match_no, left_team, right_team, winners[match_no]))
        title[winners[104]] += 1
        knockout_paths.append(tuple(knockout_path))
        if status and (sim % step == 0 or sim == sims):
            status(f"Simulated {sim:,}/{sims:,} tournaments")
    return {
        "title": title,
        "reached": reached,
        "group_metrics": group_metrics,
        "group_tables": group_tables,
        "matchups": matchups,
        "match_winners": match_winners,
        "knockout_paths": knockout_paths,
    }
