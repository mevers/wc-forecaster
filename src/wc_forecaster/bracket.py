from __future__ import annotations

from typing import Any

from wc_forecaster.model import match_probs
from wc_forecaster.tournament import BRACKET, RO32, third_assignment

BRACKET_METHOD_EXPECTED_TABLE = "expected-table"
BRACKET_METHOD_MODAL_PATH = "modal-path"
BRACKET_METHODS = [BRACKET_METHOD_EXPECTED_TABLE, BRACKET_METHOD_MODAL_PATH]


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


def advancement_probabilities(team_a: str, team_b: str, ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> tuple[float, float]:
    probs = match_probs(team_a, team_b, 0, ratings, beta, s, cfg)
    penalty_a = 1 / (1 + 10 ** ((ratings[team_b] - ratings[team_a]) / cfg["knockout"]["penalty_rating_scale"]))
    team_a_advance = probs["home"] + probs["draw"] * penalty_a
    return team_a_advance, 1 - team_a_advance


def most_likely_knockout_bracket(group_tables: dict[str, list[dict[str, Any]]], slots: dict[int, set[str]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    qualifiers = {}
    thirds = []
    for group, rows_ in group_tables.items():
        qualifiers[f"1{group}"] = rows_[0]["team"]
        qualifiers[f"2{group}"] = rows_[1]["team"]
        thirds.append(rows_[2])
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
    s_bracket = s.copy()
    for match_no, pair in RO32.items():
        team_a = qualifiers[pair[0]]
        team_b = thirds_by_match[match_no].split(":")[0] if pair[1] == "3" else qualifiers[pair[1]]
        team_a_prob, team_b_prob = advancement_probabilities(team_a, team_b, ratings, beta, s_bracket, cfg)
        winner = team_a if team_a_prob >= team_b_prob else team_b
        rows_.append(
            {
                "match_no": match_no,
                "team_a": team_a,
                "team_b": team_b,
                "winner": winner,
                "team_a_advance_probability": team_a_prob,
                "team_b_advance_probability": team_b_prob,
            }
        )
        winners[match_no] = winner
        s_bracket[team_a] = winner == team_a
        s_bracket[team_b] = winner == team_b
    for match_no, left, right in BRACKET:
        team_a = winners[left]
        team_b = winners[right]
        team_a_prob, team_b_prob = advancement_probabilities(team_a, team_b, ratings, beta, s_bracket, cfg)
        winner = team_a if team_a_prob >= team_b_prob else team_b
        rows_.append(
            {
                "match_no": match_no,
                "team_a": team_a,
                "team_b": team_b,
                "winner": winner,
                "team_a_advance_probability": team_a_prob,
                "team_b_advance_probability": team_b_prob,
            }
        )
        winners[match_no] = winner
        s_bracket[team_a] = winner == team_a
        s_bracket[team_b] = winner == team_b
    return sorted(rows_, key=lambda row: row["match_no"])


def modal_knockout_bracket(result: dict[str, Any], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = result["bracket_paths"].most_common(1)[0][0]
    rows_ = []
    s_bracket = s.copy()
    for match_no, team_a, team_b, winner in path:
        team_a_prob, team_b_prob = advancement_probabilities(team_a, team_b, ratings, beta, s_bracket, cfg)
        rows_.append(
            {
                "match_no": match_no,
                "team_a": team_a,
                "team_b": team_b,
                "winner": winner,
                "team_a_advance_probability": team_a_prob,
                "team_b_advance_probability": team_b_prob,
            }
        )
        s_bracket[team_a] = winner == team_a
        s_bracket[team_b] = winner == team_b
    return sorted(rows_, key=lambda row: row["match_no"])


def knockout_bracket(method: str, group_tables: dict[str, list[dict[str, Any]]], result: dict[str, Any], slots: dict[int, set[str]], ratings: dict[str, float], beta: list[float], s: dict[str, bool], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    if method == BRACKET_METHOD_MODAL_PATH:
        return modal_knockout_bracket(result, ratings, beta, s, cfg)
    return most_likely_knockout_bracket(group_tables, slots, ratings, beta, s, cfg)
