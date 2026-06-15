---
author:
  name: Maurits Evers
  email: maurits.evers@gmail.com
revisions:
  - date: 2026-06-15
    notes: Clarified output artefacts, expected-table knockout bracket methodology, and 2026 World Cup cutoff handling.
  - date: 2026-06-14
    notes: Initial model specification document.
---

# Model specification

## Scope and data

The model estimates probabilities for the live 2026 FIFA World Cup using observed men’s international results, derived team ratings, a recency-weighted goals model, and Monte Carlo tournament simulation. It is inspired by the [Elo rating system](https://en.wikipedia.org/wiki/Elo_rating_system), [World Football Elo Ratings](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings), Elo-covariate World Cup simulation work such as Gilch and Müller’s [_On Elo based prediction models for the FIFA Worldcup 2018_](https://arxiv.org/abs/1806.01930), and the Maher/Dixon-Coles independent-Poisson football-score modelling lineage summarised in [Statistical association football predictions](https://en.wikipedia.org/wiki/Statistical_association_football_predictions).

Inputs are fixed by `config/model.yaml`:

| Input | Description |
| :--- | :--- |
| `data/historical_results/results.csv` | CSV file downloaded and curated from the public GitHub repo [`martj42/international_results`](https://github.com/martj42/international_results). Expected columns are `date`, `home_team`, `away_team`, `home_score`, `away_score`, `tournament`, `country`, `neutral`. |
| `data/world_cup_2026/groups.csv` | Team to group mapping. Expected columns are `group`, `position`, `team`. |
| `data/world_cup_2026/fixtures.csv` | Group-stage fixtures, completed scores, and `venue_advantage`, where `1` means team `home` has venue advantage, `0` means neutral site, and `-1` means team `away` has venue advantage. Expected columns are `match_no` ,`group` ,`date` ,`home` ,`away` ,`home_score` , `away_score` ,`venue_advantage`. |
| `data/world_cup_2026/third_place_slots.csv` | Eligible third-place groups for each round-of-32 slot. Expected columns are `match_no` , `winner_slot`, `groups`. |

Historical fitting excludes 2026 World Cup rows. Completed 2026 World Cup matches are applied only from the curated fixture file so they update the current tournament state exactly once. A 2026 fixture score is used only when the fixture date is on or before `forecast.as_of`; later scored rows are treated as unplayed for that forecast. Rows with missing/`NA` scores are treated as unplayed.

## Derived team ratings

The rating model is Elo-style, not the official [FIFA/Coca-Cola Men’s World Ranking](https://www.fifa.com/en/fifa-world-ranking/men). Elo is used because it gives an online estimate of latent team strength from sequential match outcomes, with update size proportional to surprise; the expected-score formula and update form come from the [Elo rating system](https://en.wikipedia.org/wiki/Elo_rating_system). The football adaptation follows [World Football Elo Ratings](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings), including tournament-specific \(K_i\), goal-difference multiplier \(G_i\), and a venue adjustment. In this model, \(R_0=1500\), \(d=400\), and the \(K_i\) values follow those conventions; [World Football Elo Ratings](https://en.wikipedia.org/wiki/World_Football_Elo_Ratings) use 100 rating points for home advantage, while this model sets the configurable venue-advantage prior to \(h=70\). The value \(h=70\) is not estimated; it is a deliberately smaller prior that should be treated as a sensitivity parameter.

Each match row has two ordered teams, \(a\) and \(b\). The source calls them `home_team` and `away_team`, but those labels can be nominal for neutral-site matches. Define the venue-advantage indicator from team \(a\)’s perspective as

$$
V_i =
\begin{cases}
1, & \text{team } a \text{ has venue advantage},\\
0, & \text{neutral site},\\
-1, & \text{team } b \text{ has venue advantage}.
\end{cases}
$$

<details>
<summary>How are venue-advantage indicators determined?</summary>

For the curated 2026 fixture CSV, \(V_i\) is read directly from `venue_advantage`. For the historical CSV, \(V_i\) is derived as:

$$
V_i =
\begin{cases}
0, & \texttt{neutral}=\texttt{TRUE},\\
-1, & \texttt{neutral}=\texttt{FALSE}\text{ and }\texttt{country}=\texttt{away\_team},\\
1, & \texttt{neutral}=\texttt{FALSE}\text{ otherwise}.
\end{cases}
$$

</details>

The Elo-point adjustment is then

$$
A_i=\frac{hV_i}{2}\,,
$$

where $h$ is the venue-advantage parameter.

Define venue-adjusted ratings as

$$
\begin{aligned}
R_{a,i}^{\star} &= R_{a,i}^{\mathrm{pre}} + A_i\\
R_{b,i}^{\star} &= R_{b,i}^{\mathrm{pre}} - A_i\,,
\end{aligned}
$$

where \(R_{a,i}^{\mathrm{pre}}\) and \(R_{b,i}^{\mathrm{pre}}\) are the two teams’ ratings immediately before match \(i\).

The starred ratings are used only for the expected-score calculation; they are not stored as new team ratings. For neutral-site matches, \(A_i=0\), so neither team receives a venue correction.

Elo treats the match result for team \(a\) as a numeric outcome: win \(=1\), draw \(=0.5\), loss \(=0\). The expected value of that outcome before match \(i\) is

$$
E_{a,i} = \frac{1}{1 + 10^{(R_{b,i}^{\star} - R_{a,i}^{\star}) / d}}.
$$

Here \(d\) is the Elo divisor.

<details>
<summary>Why this expression?</summary>

This is the standard [Elo expected score formula](https://en.wikipedia.org/wiki/Elo_rating_system#Mathematical_details). Elo maps a rating difference to an expected result using a logistic curve. If \(R_{a,i}^{\star}=R_{b,i}^{\star}\), then \(E_{a,i}=1/(1+10^0)=0.5\). If team \(a\) is rated higher, \(R_{b,i}^{\star}-R_{a,i}^{\star}<0\), so \(E_{a,i}>0.5\). With the standard \(d=400\), a 400-point advantage gives \(E_{a,i}=1/(1+10^{-1})\approx0.91\).

</details>

Let \(g_{a,i}\) be team \(a\)’s goals and \(g_{b,i}\) be team \(b\)’s goals in match \(i\). The realised score for team \(a\) is

$$
S_{a,i} =
\begin{cases}
1, & g_{a,i} > g_{b,i},\\
0.5, & g_{a,i} = g_{b,i},\\
0, & g_{a,i} < g_{b,i}.
\end{cases}
$$

Let \(G_i\) be the goal-difference multiplier for match \(i\). With absolute goal difference \(m_i=|g_{a,i}-g_{b,i}|\), it is

$$
G_i =
\begin{cases}
1, & m_i < 2,\\
1.5, & m_i = 2,\\
(11+m_i)/8, & m_i \ge 3.
\end{cases}
$$

In simple words, the goal-difference multiplier is

- \(G_i=1\) if the game is a draw or if it is won by 1 goal,
- \(G_i=1.5\) if the game is won by 2 goals,
- \(G_i=(11+m_i)/8\) if the game is won by 3 or more goals.

Ratings update after every observed match:

$$
\begin{aligned}
\Delta_i &= K_i G_i (S_{a,i} - E_{a,i})\\
R_{a,i}^{\mathrm{post}} &= R_{a,i}^{\mathrm{pre}} + \Delta_i\\
R_{b,i}^{\mathrm{post}} &= R_{b,i}^{\mathrm{pre}} - \Delta_i\,,
\end{aligned}
$$

where \(K_i\) is the match-importance weight for match \(i\).

The output `derived_team_ratings.csv` is the resulting rating snapshot after historical fitting and completed 2026 World Cup updates dated on or before `forecast.as_of`, immediately before simulating remaining fixtures. Predicted, simulated, and future-dated fixture scores do not update these ratings.

## Goal model

The score model is an independent Poisson model with log expected goals as a function of pre-match rating gap, venue advantage, and a fixed previous-win form offset. Independent Poisson goals are the standard baseline for football scores in the Maher/Dixon-Coles modelling lineage described in [Statistical association football predictions](https://en.wikipedia.org/wiki/Statistical_association_football_predictions). The rating-gap covariate is the compact team-strength signal, as in Elo-covariate World Cup prediction models such as [_On Elo based prediction models for the FIFA Worldcup 2018_](https://arxiv.org/abs/1806.01930) and Groll et al.’s [_Prediction of the FIFA World Cup 2018_](https://arxiv.org/abs/1806.03208).

During a chronological pass through observed matches before cut-off \(T\), each match contributes two in-memory regression observations: one observation for team \(a\)’s goals and one for team \(b\)’s goals. For observation \(j\), define:

- \(q_j\): venue-adjusted rating gap divided by 100,
- \(v_j\): venue-advantage indicator from that observation’s perspective,
- \(z_j\): previous-game indicator,
- \(y_j=\log(g_j+0.5)\): transformed goals response.

Only \(q_j\) and \(v_j\) are fitted covariates. \(z_j\) enters as a fixed offset via `form.gamma`; default \(\gamma=0.05\).

The model is then
$$
y_j - \gamma z_j = \beta_0 + \beta_1 q_j + \beta_2 v_j + \epsilon_j.
$$

The two observations generated by match \(i\) are:

| Observation | \(q_j\) | \(v_j\) | \(z_j\) | \(y_j\) |
|---|---|---|---|---|
| Team \(a\) | \(\displaystyle\frac{R_{a,i}^{\star}-R_{b,i}^{\star}}{100}\) | \(V_i\) | \(z_j=1\) if team \(a\) won previous fixture, else 0 | \(\log(g_{a,i}+0.5)\) |
| Team \(b\) | \(\displaystyle\frac{R_{b,i}^{\star}-R_{a,i}^{\star}}{100}\) | \(-V_i\) | \(z_j=1\) if team \(b\) won previous fixture, else 0 | \(\log(g_{b,i}+0.5)\) |

The \(+0.5\) offset keeps zero-goal observations finite. 

Match weights decay by age:

$$
w_i = 0.5^{\operatorname{age}_i/H}, \qquad
\operatorname{age}_i = \frac{T-\operatorname{date}_i}{365.25},
$$

where \(H\) is the half-life in years. Coefficients are weighted least squares:

$$
\hat{\boldsymbol\beta} = (\mathbf{X}^\top \mathbf{W}\mathbf{X})^{-1}\mathbf{X}^\top \mathbf{W}\mathbf{y}.
$$

Here \(\mathbf{X}\) is the design matrix with rows \((1,q_j,v_j)\), the WLS response vector has elements \(y_j-\gamma z_j\), and \(\mathbf{W}\) is the diagonal matrix of recency weights.

Expected goals for fixture \(a\) vs \(b\) are

$$
\begin{aligned}
\lambda_a &= \max(\lambda_{\min}, \exp(\hat\beta_0+\hat\beta_1 q_a+\hat\beta_2 v_a+\gamma z_a))\\
\lambda_b &= \max(\lambda_{\min}, \exp(\hat\beta_0+\hat\beta_1 q_b+\hat\beta_2 v_b+\gamma z_b))\,,
\end{aligned}
$$

where \(z_a\) and \(z_b\) indicate whether each team won its previous fixture, and \(\lambda_{\min}\) is the configured or tuned minimum expected-goals floor.


<details>
<summary>How are \(H\) and \(\lambda_{\min}\) chosen?</summary>

`config/model.yaml` has fallback values and tuning grids. If `fit.tune` is `false`, the model uses `fit.half_life` and `goals.min_expected_goals` directly. If `fit.tune` is `true`, the model fits once for each pair in `fit.half_life_years` × `goals.min_expected_goals_values`, evaluates the pairs on 2018 and 2022 World Cup match outcomes, and keeps the pair with the lowest 1X2 log loss. The fallback values are used if the backtest contains no evaluable World Cup matches.

For candidate pair \((H,\lambda_{\min})\), the tuning criterion is mean negative log likelihood of the observed 1X2 outcomes:

$$
\operatorname{NLL}(H,\lambda_{\min}) = -\frac{1}{n}\sum_{j=1}^{n}\log p_j(o_j \mid H,\lambda_{\min}).
$$

</details>

<details>
<summary>What does the gamma parameter mean for the expected goals?</summary>
In plain English, if \(\gamma=0.05\), a team that won its previous fixture receives a multiplicative expected-goals boost of \(\exp(0.05)\approx1.051\), about 5.1%, for its next fixture.
</details>

## Match and tournament simulation

The simulator uses the [2026 FIFA World Cup](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup) format: 12 groups of four, top two plus eight best third-place teams, round of 32, then single-elimination knockout to match 104. Group ranking is points, goal difference, goals for, then derived rating. FIFA fair-play points and official FIFA ranking tiebreakers are omitted because they are not present in the local data; the [2026 knockout-stage format](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage) includes the 32-team knockout structure, and the tournament regulations include third-place mappings from Annex C of the [Regulations for the FIFA World Cup 26 document](https://digitalhub.fifa.com/m/636f5c9c6f29771f/original/FWC2026_regulations_EN.pdf).

The previous-win state \(z\) is part of each Monte Carlo path. It records whether each team won its previous observed or simulated fixture. It is initialised from the chronological historical pass plus completed 2026 fixtures, then updated after every completed or simulated group match. In knockout matches, the advancing team is treated as having won the fixture for the next-round form offset, including advancement after a drawn scoreline.

### Group-stage matches

Completed group-stage fixtures use their recorded scores. For each unplayed group-stage fixture, simulated goal counts are sampled independently:

$$
C_a \sim \operatorname{Poisson}(\lambda_a), \qquad C_b \sim \operatorname{Poisson}(\lambda_b).
$$

Probabilities use a capped Poisson support \(0,\ldots,c\), with residual tail mass \(P(X>c)\) folded into the final bucket \(c\) (default \(c=8\); so the \(c\) bucket means "\(c\) or more" goals). This is not a truncated Poisson distribution, because probabilities are not conditioned on \(X\leq c\) and renormalised.

Let \(C_a\) and \(C_b\) denote the capped goal-count buckets for teams \(a\) and \(b\), and let \(r,u\in\{0,\ldots,c\}\) index possible capped scores. Fixture 1X2 probabilities sum scoreline probabilities:

$$\begin{aligned}
P(a\text{ win})&=\sum_{r>u}P(C_a=r)P(C_b=u)\\
P(\text{draw})&=\sum_{r=u}P(C_a=r)P(C_b=u)\,.
\end{aligned}
$$

In plain words, $P(a\text{ win})$ adds the probabilities of team $a$ scoring $r$ and team $b$ scoring $u$ goals, subject to team $a$ winning ($r > u$).

Drawn group-stage fixtures remain draws and contribute one point to each team. After all group fixtures in a Monte Carlo path are complete, group tables are ranked and the knockout slots are populated.

### Knockout matches

For each knockout match in a raw Monte Carlo simulation, the model first samples regulation-time goals \(C_a\) and \(C_b\) from the same capped Poisson score model. Regulation-time here means normal match time, excluding any extra time or penalty shootout. If \(C_a>C_b\), team \(a\) advances; if \(C_b>C_a\), team \(b\) advances. If \(C_a=C_b\), the drawn scoreline is resolved by a single rating-based advancement probability:

$$
P(a\text{ advances}\mid C_a=C_b)=\frac{1}{1+10^{(R_b-R_a)/\kappa}},
$$

where \(\kappa=\) `knockout.penalty_rating_scale` \(=500\). This approximates extra time plus penalties; it is not a separate extra-time model.

After \(M=\) `forecast.simulations` (default $M = 50,000$) simulated tournaments, output probabilities are empirical frequencies. Let \(N_{i,r}\) be the number of simulations in which team \(i\) reaches round \(r\), and let \(W_i\) be the number of simulations in which team \(i\) wins the tournament:

$$
\begin{aligned}
\hat p(i\text{ reaches round }r) &= \frac{N_{i,r}}{M}\\
\hat p(i\text{ wins tournament}) &= \frac{W_i}{M}\,.
\end{aligned}
$$

## Output artefacts

`wc-forecaster predict` writes forecast artefacts to `data.output_dir/forecast.as_of`, which is `outputs/<as_of>/` in the default config. These files are deterministic for a fixed config, code version, input data, and random seed.

The probability artefacts are:

- `winner_odds.csv`: one row per team with `team` and `probability`. This is the empirical title probability.
- `round_probabilities.csv`: one row per team and round with `team`, `round`, and `probability`. This is the empirical probability that the team reaches that round.
- `fixture_probabilities.csv`: one row per scheduled group fixture with `match_no`, `home_team`, `away_team`, `home`, `draw`, and `away`. The final three columns are 1X2 probabilities from the fitted score model at forecast time.
- `most_likely_group_tables.csv`: expected group tables with `group`, `position`, `team`, `expected_points`, `expected_goal_difference`, and `expected_goals_for`.

The rating and run metadata artefacts are:

- `derived_team_ratings.csv`: the model’s rating snapshot after historical fitting and completed 2026 World Cup updates dated on or before `forecast.as_of`, before simulating remaining fixtures.
- `tuning_summary.json`: selected tuning values and backtest scores when tuning is enabled.
- `run_manifest.json`: run metadata, including `as_of`, simulation count, fitted coefficients, and config path.

The knockout summary artefacts are deliberately different from each other:

- `most_likely_knockout_bracket.csv`: canonical most likely knockout bracket. Groups are ranked by expected table performance, and knockout winners are selected by head-to-head advancement probability. See `docs/most_likely_knockout_bracket_methodology.md`.
- `most_likely_bracket.csv`: deprecated legacy marginal winner summary. For each knockout match number in the raw Monte Carlo simulations, it gives the team that wins that match most often across all simulations. It is not generated from the fixed expected-table knockout bracket and should not be used as a bracket input.
- `most_likely_matchups.csv`: deprecated legacy marginal matchup summary. For each knockout match number in the raw Monte Carlo simulations, it gives the team pairing that appears most often across all simulations. It is not generated from the fixed expected-table knockout bracket and should not be used as a bracket input.
- `most_likely_tournament_bracket.csv`: deprecated copy of the expected-table knockout bracket, with winners chosen by head-to-head advancement probability.
- `most_likely_realised_bracket.csv`: deprecated copy of the same expected-table knockout bracket, seeded from expected group standings and resolved by head-to-head advancement probability.

The deprecated marginal knockout files are retained only for legacy analysis of raw simulation slot frequencies. Use `most_likely_knockout_bracket.csv` for any chart or report that needs one internally coherent knockout bracket.

The rendered chart artefacts are:

- `winner_odds.png`: bar chart of the leading title probabilities.
- `knockout_bracket.svg` and `knockout_bracket.png`: visual bracket rendered from `most_likely_knockout_bracket.csv` and `run_manifest.json`.

## Reproducibility and limitations

Default run state is `forecast.as_of=2026-06-14`, `forecast.simulations=50000`, `forecast.seed=20260614`. Outputs are deterministic for a fixed config, code version, curated tournament CSVs, and historical CSV.

Known exclusions: player availability, squad strength, rest/travel, style-specific team interactions, injuries, weather, market priors, fair-play tiebreakers, the full Annex C third-place combination lookup table, and the official FIFA ranking formula. The local data stores eligible third-place groups per round-of-32 slot; the model assigns qualifying third-place teams by deterministic matching within those eligible slots. The model estimates calibrated probabilities and derives a canonical most likely knockout bracket from expected group standings plus head-to-head advancement probabilities.
