from __future__ import annotations

from scripts.retro_r32_convergence import Pair, compare_slots, summarise


def test_compare_slots_counts_reversed_pair_in_right_spot_not_right_order() -> None:
    actual = {73: Pair("South Africa", "Canada"), 74: Pair("Germany", "Paraguay")}
    predicted = {73: Pair("Canada", "South Africa"), 74: Pair("Germany", "Paraguay")}

    rows = compare_slots(actual, predicted)

    assert rows[0]["right_spot"] is True
    assert rows[0]["right_order"] is False
    assert rows[0]["actual_teams_found"] == 2


def test_compare_slots_identifies_partial_and_wrong_slot_matches() -> None:
    actual = {73: Pair("South Africa", "Canada"), 74: Pair("Germany", "Paraguay")}
    predicted = {73: Pair("South Africa", "Germany"), 74: Pair("Canada", "South Africa")}

    rows = compare_slots(actual, predicted)

    assert rows[0]["actual_teams_found"] == 1
    assert rows[0]["missing_actual_teams"] == "Canada"
    assert rows[0]["extra_predicted_teams"] == "Germany"
    assert rows[1]["predicted_pair_actual_elsewhere"] == 73


def test_summarise_reports_pair_and_team_accuracy() -> None:
    actual = {73: Pair("South Africa", "Canada"), 74: Pair("Germany", "Paraguay")}
    predicted = {73: Pair("Canada", "South Africa"), 74: Pair("Canada", "Germany")}

    summary = summarise("2026-06-10", "expected-table", actual, predicted)

    assert summary["slot_pair_accuracy"] == 0.5
    assert summary["r32_team_accuracy"] == 0.75
    assert summary["team_place_accuracy"] == 0.75
    assert summary["actual_r32_teams_predicted"] == 3
    assert summary["correct_slots"] == [73]
