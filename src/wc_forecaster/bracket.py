from __future__ import annotations

from typing import Any

from wc_forecaster.model import match_probs
from wc_forecaster.tournament import BRACKET, RO32, third_assignment

BRACKET_METHOD_EXPECTED_TABLE = "expected-table"
BRACKET_METHOD_MODAL_GROUP_TABLE = "modal-group-table"
BRACKET_METHODS = [BRACKET_METHOD_EXPECTED_TABLE, BRACKET_METHOD_MODAL_GROUP_TABLE]


# Averages simulated points, goal difference, and goals for into expected tables.
def expected_group_tables(groups: dict[str, list[str]], result: dict[str, Any], sims: int, ratings: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    out = {}
    for group, teams in groups.items():
        rows_ = []
        for team_name in teams:
            metrics = result["group_metrics"][group][team_name]
            rows_.append(
                {
                    "group": group,
                    "team": team_name,
                    "expected_points": metrics["points"] / sims,
                    "expected_goal_difference": metrics["goal_difference"] / sims,
                    "expected_goals_for": metrics["goals_for"] / sims,
                }
            )
        ranked = sorted(
            rows_,
            # Apply model-spec table ordering, with rating as final tiebreaker.
            key=lambda row: (
                row["expected_points"],
                row["expected_goal_difference"],
                row["expected_goals_for"],
                ratings[row["team"]],
            ),
            reverse=True,
        )
        out[group] = [{**row, "position": position} for position, row in enumerate(ranked, 1)]
    return out


# Combines neutral 1X2 probabilities with rating-based draw advancement.
def advancement_probabilities(team_a: str, team_b: str, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> tuple[float, float]:
    probs = match_probs(team_a, team_b, 0, ratings, beta, s, cfg)
    penalty_a = 1 / (1 + 10 ** ((ratings[team_b] - ratings[team_a]) / cfg["knockout"]["penalty_rating_scale"]))
    team_a_advance = probs["home"] + probs["draw"] * penalty_a
    return team_a_advance, 1 - team_a_advance


# Selects each group's modal complete ordered simulated table.
def modal_group_tables(groups: dict[str, list[str]], result: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        group: [
            {
                "group": group,
                "position": position,
                "team": row[0],
                "expected_points": row[1],
                "expected_goal_difference": row[2],
                "expected_goals_for": row[3],
            }
            for position, row in enumerate(result["group_tables"][group].most_common(1)[0][0], 1)
        ]
        for group in groups
    }


# Records one deterministic knockout row and updates previous-win state.
def append_match(rows_: list[dict[str, Any]], match_no: int, team_a: str, team_b: str, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> str:
    team_a_prob, team_b_prob = advancement_probabilities(team_a, team_b, ratings, beta, s, cfg)
    winner = team_a if team_a_prob >= team_b_prob else team_b
    rows_.append({"match_no": match_no, "team_a": team_a, "team_b": team_b, "winner": winner, "team_a_advance_probability": team_a_prob, "team_b_advance_probability": team_b_prob})
    s[team_a] = winner == team_a
    s[team_b] = winner == team_b
    return winner


# Seeds a coherent bracket, then propagates head-to-head winners.
def most_likely_knockout_bracket(group_tables: dict[str, list[dict[str, Any]]], slots: dict[int, set[str]], fixtures: list[dict[str, Any]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    qualifiers = {}
    thirds = []
    for group, rows_ in group_tables.items():
        qualifiers[f"1{group}"] = rows_[0]["team"]
        qualifiers[f"2{group}"] = rows_[1]["team"]
        thirds.append(rows_[2])
    # Select the eight best third-place teams from the chosen group tables.
    best_thirds = [
        f"{row['team']}:{row['group']}"
        for row in sorted(
            thirds,
            key=lambda row: (
                row["expected_points"],
                row["expected_goal_difference"],
                row["expected_goals_for"],
                ratings[row["team"]],
            ),
            reverse=True,
        )[:8]
    ]
    thirds_by_match = third_assignment(best_thirds, slots)
    rows_ = []
    winners = {}
    semi_losers = {}
    knockout_fixtures = {int(match["match_no"]): match for match in fixtures if match["group"] == "R32"}
    s_bracket = s.copy()
    # Seed the round of 32 from direct qualifiers and eligible third-place slots.
    for match_no, pair in RO32.items():
        match = knockout_fixtures.get(match_no)
        team_a = match["home_team"] if match else qualifiers[pair[0]]
        team_b = match["away_team"] if match else thirds_by_match[match_no].split(":")[0] if pair[1] == "3" else qualifiers[pair[1]]
        winners[match_no] = append_match(rows_, match_no, team_a, team_b, ratings, beta, s_bracket, cfg)
        # Use recorded knockout winners when completed fixtures exist.
        if match and match["home_score"] is not None and match["fixture_winner"]:
            rows_[-1]["winner"] = winners[match_no] = match["fixture_winner"]
            s_bracket[team_a], s_bracket[team_b] = winners[match_no] == team_a, winners[match_no] == team_b
    for match_no, left, right in BRACKET:
        if match_no == 104:
            # Resolve match 103 from the two semi-final losers before the final.
            append_match(rows_, 103, semi_losers[101], semi_losers[102], ratings, beta, s_bracket, cfg)
        team_a = winners[left]
        team_b = winners[right]
        winner = append_match(rows_, match_no, team_a, team_b, ratings, beta, s_bracket, cfg)
        winners[match_no] = winner
        # Keep semi-final losers for the third-place play-off.
        if match_no in {101, 102}:
            semi_losers[match_no] = team_b if winner == team_a else team_a
    return sorted(rows_, key=lambda row: row["match_no"])


# Builds one bracket; only the group-table construction method changes.
def knockout_bracket(method: str, groups: dict[str, list[str]], group_tables: dict[str, list[dict[str, Any]]], result: dict[str, Any], slots: dict[int, set[str]], fixtures: list[dict[str, Any]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    if method == BRACKET_METHOD_MODAL_GROUP_TABLE:
        group_tables = modal_group_tables(groups, result)
    return most_likely_knockout_bracket(group_tables, slots, fixtures, ratings, beta, s, cfg)


# Emits labelled coherent bracket rows for every supported method.
def knockout_bracket_options(groups: dict[str, list[str]], group_tables: dict[str, list[dict[str, Any]]], result: dict[str, Any], slots: dict[int, set[str]], fixtures: list[dict[str, Any]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"bracket_method": method, **row}
        for method in BRACKET_METHODS
        for row in knockout_bracket(method, groups, group_tables, result, slots, fixtures, ratings, beta, s, cfg)
    ]
