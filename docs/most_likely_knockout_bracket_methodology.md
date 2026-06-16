# Most likely bracket methodology

## TL;DR summary

`most_likely_knockout_bracket.csv` contains two bracket options, distinguished
by the `bracket_method` column:

1. **`expected-table`: Average first, then build the bracket.** This is the default render option. The model averages each team's simulated group performance, ranks groups by expected points, expected goal difference, and expected goals for, then seeds the knockout bracket from those expected tables.
2. **`modal-group-table`: Count group tables first, then build the bracket.** This option finds the most common complete ordered table in each group, then seeds the knockout bracket from those modal group tables.

Both methods apply to the group-stage table construction, not only to knockout
matches. Once a method has seeded the knockout bracket, both methods resolve
knockout matches in the same deterministic way: choose the team with the higher
head-to-head advancement probability and propagate winners forward. Match 103,
the third-place play-off, is resolved from the two semi-final losers.

The exact full-tournament `modal-path` method is not used. Complete tournament
paths are too sparse to be stable at normal simulation counts.

## Shared knockout resolution

Both implemented methods produce a deterministic set of group tables. Those
tables seed the round of 32: group winners, group runners-up, and the eight
best third-place teams.

For knockout match \(k\), with teams \(a\) and \(b\), let \(p_a\), \(p_d\), and
\(p_b\) be the model's regulation probabilities for team \(a\) win, draw, and
team \(b\) win at a neutral venue. Let

\[
q_a=\frac{1}{1+10^{(R_b-R_a)/s}}
\]

be team \(a\)'s advancement probability after a drawn knockout scoreline, using
the configured penalty rating scale \(s\). The advancement probability is

\[
\pi_{a,k}=P(a\text{ advances}\mid a,b)=p_a+p_dq_a.
\]

The knockout point forecast is

\[
\hat{W}_k=
\begin{cases}
a & \text{if } \pi_{a,k}\geq 1-\pi_{a,k},\\
b & \text{otherwise.}
\end{cases}
\]

Winners are propagated forward through the bracket. The same rule is used for
the third-place play-off between the two semi-final losers.

## Method: `expected-table`

For group \(g\), team \(i\), and simulation draw \(m\), let

\[
S_{ig}^{(m)} = \left(P_{ig}^{(m)}, GD_{ig}^{(m)}, GF_{ig}^{(m)}\right)
\]

be the realised group table statistics: points, goal difference, and goals for.
The project estimates the expected table vector

\[
\mu_{ig}=E[S_{ig}]
\]

by Monte Carlo averaging:

\[
\hat{\mu}_{ig}=\frac{1}{M}\sum_{m=1}^{M}S_{ig}^{(m)}.
\]

The group table point forecast is the lexicographic ordering

\[
\hat{R}_g^{\,E}
=\operatorname{lexrank}_{i\in g}
\left(
\hat{E}[P_{ig}],
\hat{E}[GD_{ig}],
\hat{E}[GF_{ig}],
R_i
\right),
\]

where \(R_i\) is the model's derived team rating and is used only as the final
deterministic tiebreaker.

This is a plug-in decision rule: first estimate each team's expected table
performance, then apply the tournament's ranking operator to those expected
statistics. The object being ranked is the vector of expected team-level table
statistics, not the probability mass of a complete ordered table.

## Method: `modal-group-table`

For a group \(g\), let \(T_g\) denote the complete ordered group table,
including the ranking of all four teams after applying the model's group
tiebreakers. Each row in \(T_g\) includes the team's points, goal difference,
and goals for.

The modal group-table forecast is

\[
\hat{T}_g^{\,\text{mode}}=\arg\max_t P(T_g=t).
\]

The project estimates this by counting complete ordered tables in the Monte
Carlo simulations and selecting the most common table separately for each group.
The selected modal tables are then used to seed the knockout bracket. The top
two teams qualify directly, and the eight best third-place teams are selected
from the third-place rows of the selected modal tables.

This preserves coherence within each group table: the ordering and table
statistics come from an actual simulated table state for that group. It does not
claim that the selected tables for all groups occurred together in one complete
simulated tournament path.

## Statistical distinction

The two implemented methods answer different questions:

- `expected-table`: Which bracket follows from average simulated group performance?
- `modal-group-table`: Which bracket follows from each group's most common complete table?

In general,

\[
\operatorname{lexrank}_{i\in g}(E[S_{ig}])
\neq
\arg\max_t P(T_g=t).
\]

The inequality is not a computational bug. It is the difference between a
functional of expected team-level summaries and the mode of a joint discrete
distribution over ordered group tables.

The small script `docs/modal_group_table_counterexample.R` gives a reproducible
four-team example. It simulates a group where the expected table is
\(A,B,C,D\), but the modal complete ordered table is \(A,C,B,D\).

## Methods not used

### Full `modal-path`

For the whole tournament, let \(Y\) denote the complete realised tournament
path: all group results, all group tables, all knockout pairings, and all
knockout winners. The full modal-path forecast would be

\[
\hat{Y}^{\,\text{mode}}=\arg\max_y P(Y=y).
\]

This selects the single complete tournament path with the highest probability
mass. It is coherent by construction, but it is not used by this project because
the complete path space is too large and sparse. In trial runs, the selected
full path occurred only once even with 100,000 simulations, making the result
effectively an arbitrary sampled path rather than a stable point forecast.

### Marginal summaries

Both implemented methods also differ from marginal summaries. For example,

\[
\arg\max_i P(\text{team }i\text{ finishes first in group }g)
\]

is a first-place marginal. It does not define the full group ordering. Likewise,
the most common winner of match \(k\) and the most common pairing in match \(k\)
are separate marginal summaries. They need not come from the same bracket.

Those marginal summaries should not be stitched together as a bracket.

## Relationship to other artefacts

`most_likely_knockout_bracket.csv` is the bracket visualisation input. It
contains one row per bracket method and match, with `bracket_method` identifying
which method produced the row.

`scripts/draw_knockout_bracket.py --bracket-method` selects which method to
render. The default is `expected-table`.

Two deprecated files contain the same method-indexed bracket rows:

- `most_likely_tournament_bracket.csv`: deprecated compatibility copy of `most_likely_knockout_bracket.csv`.
- `most_likely_realised_bracket.csv`: deprecated compatibility copy of `most_likely_knockout_bracket.csv`.

The deprecated legacy marginal knockout files answer different questions and
are not bracket inputs:

- `most_likely_bracket.csv`: in the raw Monte Carlo simulations, for each match slot, which team wins most often?
- `most_likely_matchups.csv`: in the raw Monte Carlo simulations, for each match slot, which pairing appears most often?

## References

- Gneiting, T. (2011). [Making and Evaluating Point Forecasts](https://arxiv.org/abs/0912.0902). *Journal of the American Statistical Association*, 106(494), 746-762. This frames point forecasts as statistical functionals of a predictive distribution and motivates stating the target functional explicitly.
- Gneiting, T. and Raftery, A. E. (2007). [Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437). *Journal of the American Statistical Association*, 102(477), 359-378. This distinguishes probabilistic forecasts from point summaries and discusses proper scoring of predictive distributions.
- Gilch, L. A. (2022). [Nested Zero Inflated Generalized Poisson Regression for FIFA World Cup 2022](https://arxiv.org/abs/2205.04173). This gives a football tournament simulation context in which match simulations are used to estimate stage probabilities.
- Barrientos, A. F., Sen, D., Page, G. L., and Dunson, D. B. (2019). [Bayesian inferences on uncertain ranks and orderings: Application to ranking players and lineups](https://arxiv.org/abs/1907.04842). This is used only to frame uncertainty in rankings and orderings; it is not the ranking rule used by this project.
