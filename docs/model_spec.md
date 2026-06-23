---
author:
  name: Maurits Evers
  email: maurits.evers@gmail.com
revisions:
  - date: 2026-06-16
    notes: Added squad cohesion and Iceland-effect forecast adjustments.
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
| `data/world_cup_2026/squads.csv` | 2026 WC squad compositions derived from [2026 FIFA World Cup squads](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads). Expected columns for the model are `team`, `player`, `club`, and `league`; the file also stores additional squad metadata such as number, position, date of birth, age, caps, and goals. The `league` value is the club's national association / league-system country, not the exact domestic division. |
| `data/world_cup_2026/third_place_slots.csv` | Eligible third-place groups for each round-of-32 slot. Expected columns are `match_no` , `winner_slot`, `groups`. |

Historical model fitting excludes any 2026 World Cup fixtures. Completed 2026 World Cup matches are sourced from the fixture file and applied once to the live tournament state, updating Elo ratings, previous-win form, underdog-magic residuals, and completed group results. They are _not_ used to update or re-estimate the fitted goal-model coefficients. A 2026 fixture score is used only when the fixture date is on or before `forecast.as_of`; later scored rows are treated as unplayed for that forecast. Rows with missing/`NA` scores are treated as unplayed.

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

For team \(k\), let \(\ell(k)\) be its last observed match on or before `forecast.as_of`. Define

$$
R_k^{\mathrm{derived}} = R_{k,\ell(k)}^{\mathrm{post}}.
$$

The output `derived_team_ratings.csv` stores this rating snapshot immediately before simulating remaining fixtures. Predicted, simulated, and future-dated fixture scores do not update these ratings.

## Forecast rating adjustments

Forecasts use derived ratings adjusted for two additional effects: squad cohesion and underdog magic ("Iceland effect").

> [!NOTE]
> These adjustments are forecast-only rating adjustments: they are added to derived ratings for prediction, but they are not included in `derived_team_ratings.csv` and they are not produced by the Elo match update process detailed in the previous section.

For team \(k\), the adjusted forecast rating is

$$
R_k^{\mathrm{forecast}} = R_k^{\mathrm{derived}} + B_k^{\mathrm{cohesion}} + B_k^{\mathrm{underdog}}.
$$

The adjusted forecast ratings are used for remaining fixture probabilities, simulated match score probabilities, group-table rating tiebreakers, best-third ranking tiebreakers, and rating-based knockout advancement after drawn regulation-time scorelines.

### Squad cohesion adjustment

The cohesion boost is a heuristic adjustment based on 2026 WC squad composition: For every unordered pair of players in a squad, a same-club pair contributes `cohesion.same_club_weight`; otherwise, a same-league-system pair contributes `cohesion.same_league_weight`. Let this pair score be \(C_k\). The boost is

$$
B_k^{\mathrm{cohesion}} = \min\left(b_{\max}, b_{\max}\frac{C_k}{C_{\max}}\right),
$$

where \(b_{\max}=\) `cohesion.max_rating_boost` and \(C_{\max}=\) `cohesion.score_for_max_boost`.

If `cohesion.enabled` is `false`, this boost is zero. When cohesion is enabled, the curated squad CSV must contain complete `team`, `player`, `club`, and `league` values for every forecast team.

> [!NOTE]
> The raw pair score rises quickly as more players share a club or league, but the final rating boost has diminishing returns through the cap at \(b_{\max}\).

### Underdog magic adjustment

The running team rating approach already captures part of an underdog run: if a lower-rated team draws or beats a stronger opponent, its derived rating increases through the match update process. The "Iceland effect" is a small additional post-hoc boost for genuine underdogs based on previous match results that significantly deviated from model-expected results.

The model expresses expected results as expected points, \(\operatorname{EP}_{k,i}\). For each completed game \(i\), _before_ the team rating update, compute \(\operatorname{EP}_{k,i}\) from the model's pre-match 1X2 probabilities (defined in [Group-stage matches](#group-stage-matches)), excluding underdog magic:

$$
\operatorname{EP}_{k,i}=3P(k\text{ win in }i)+P(\text{draw in }i).
$$

Let \(A_{k,i}\) be team \(k\)'s actual points from fixture \(i\): 3 for a win, 1 for a draw, 0 for a loss. The positive points residual is

$$
Q_{k,i}=\max(0,A_{k,i}-\operatorname{EP}_{k,i}).
$$

For completed game \(i\), let \(k'\) be team \(k\)'s opponent, and let \(R_{k,i}^{\mathrm{pre}}\) be team \(k\)'s rolling team rating immediately before game \(i\), after earlier completed games have been applied. Define

$$
R_{k,i}^{\mathrm{base}}=R_{k,i}^{\mathrm{pre}}+B_k^{\mathrm{cohesion}}.
$$

Underdog magic is excluded from \(R^{\mathrm{base}}\). The pre-match rating gap for team \(k\) is

$$
g_{k,i}=R_{k',i}^{\mathrm{base}}-R_{k,i}^{\mathrm{base}}.
$$

The underdog weight is then

$$
w_{k,i} =
\begin{cases}
0, & g_{k,i} < g_{\min},\\
\min\left(1,\displaystyle\frac{g_{k,i}-g_{\min}}{g_{\max}-g_{\min}}\right), & g_{k,i} \ge g_{\min}\,,
\end{cases}
$$

where \(g_{\min}=\) `underdog_magic.min_rating_gap`  and \(g_{\max}=\) `underdog_magic.rating_gap_for_full_weight`.

The accumulated underdog residual is

$$
D_k=\sum_i w_{k,i}Q_{k,i}.
$$


$$
B_k^{\mathrm{underdog}} = \min\left(u_{\max}, u_{\max}\frac{D_k}{D_{\max}}\right),
$$

where \(u_{\max}=\) `underdog_magic.max_rating_boost` and \(D_{\max}=\) `underdog_magic.points_residual_for_max_boost`. 

In plain words: If the pre-match rating gap is less than the threshold $g_{\min}$ then a team receives no underdog boost. If `underdog_magic.enabled` is `false`, this boost is zero. The Iceland effect is based only on observed completed fixtures; simulated future matches do not create further residuals inside Monte Carlo paths.

<details>
<summary>How is the threshold determined?</summary>

The default threshold is calibrated around Iceland before Euro 2016: Portugal and England count as genuine underdog matches, while Hungary and Austria do not.

</details>

## Goal model

The score model is an independent Poisson model with log expected goals as a function of pre-match rating gap, venue advantage, and a fixed previous-win form offset. Independent Poisson goals are the standard baseline for football scores in the Maher/Dixon-Coles modelling lineage described in [Statistical association football predictions](https://en.wikipedia.org/wiki/Statistical_association_football_predictions). The rating-gap covariate is the compact team-strength signal, as in Elo-covariate World Cup prediction models such as [_On Elo based prediction models for the FIFA Worldcup 2018_](https://arxiv.org/abs/1806.01930) and Groll et al.’s [_Prediction of the FIFA World Cup 2018_](https://arxiv.org/abs/1806.03208). Fitting uses derived Elo ratings available before each historical match; forecasting remaining World Cup fixtures uses the temporary forecast ratings defined above.

During a chronological pass through observed matches before cut-off \(T\), each match contributes two in-memory regression observations: one observation for team \(a\)’s goals and one for team \(b\)’s goals. For observation \(j\), define:

- \(q_j\): venue-adjusted rating gap divided by 100,
- \(v_j\): venue-advantage indicator from that observation’s perspective,
- \(z_j\): previous-game indicator,
- \(g_j\): observed goals.

Only \(q_j\) and \(v_j\) are fitted covariates. \(z_j\) enters as a fixed offset via `form.gamma`; default \(\gamma=0.05\).

The weighted Poisson GLM with log link is
$$
g_j\sim\operatorname{Poisson}(\lambda_j),\qquad
\log\lambda_j = \beta_0 + \beta_1 q_j + \beta_2 v_j + \gamma z_j.
$$

The two observations generated by match \(i\) are:

| Observation | \(q_j\) | \(v_j\) | \(z_j\) | Response |
|---|---|---|---|---|
| Team \(a\) | \(\displaystyle\frac{R_{a,i}^{\star}-R_{b,i}^{\star}}{100}\) | \(V_i\) | \(z_j=1\) if team \(a\) won previous fixture, else 0 | \(g_{a,i}\) |
| Team \(b\) | \(\displaystyle\frac{R_{b,i}^{\star}-R_{a,i}^{\star}}{100}\) | \(-V_i\) | \(z_j=1\) if team \(b\) won previous fixture, else 0 | \(g_{b,i}\) |

Match weights decay by age:

$$
w_i = 0.5^{\operatorname{age}_i/H}, \qquad
\operatorname{age}_i = \frac{T-\operatorname{date}_i}{365.25},
$$

where \(H\) is the half-life in years. Coefficients maximise the weighted Poisson log-likelihood:

$$
\hat{\boldsymbol\beta}
=\arg\max_{\boldsymbol\beta}\sum_j w_j\log P(g_j\mid\lambda_j).
$$

The fit uses iteratively reweighted least squares. Fractional recency weights scale each observation’s contribution to the likelihood.

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

Let \(C_a\) and \(C_b\) denote the capped goal-count buckets for teams \(a\) and \(b\), and let \(r,u\in\{0,\ldots,c\}\) index possible capped scores. Fixture 1X2 probabilities are then the sum of individual scoreline probabilities:

$$\begin{aligned}
P(a\text{ win})&=\sum_{r>u}P(C_a=r)P(C_b=u)\\
P(\text{draw})&=\sum_{r=u}P(C_a=r)P(C_b=u)\\
P(b\text{ win})&=\sum_{r<u}P(C_a=r)P(C_b=u)\,.
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
- `round_reach_probabilities.csv`: one row per team and round with `team`, `round`, and `probability`. This is the empirical probability that the team reaches that round.
- `group_fixture_1x2_probabilities.csv`: one row per scheduled group fixture with `match_no`, `home_team`, `away_team`, `home`, `draw`, and `away`. The final three columns are 1X2 probabilities from the fitted score model at forecast time.
- `next_matchday_summary.csv`: one row per fixture on the next fixture date after `forecast.as_of`, with 1X2 probabilities, expected goals, and a median scoreline. The scoreline uses each team's marginal Poisson median and therefore minimises expected absolute goal error.
- `most_likely_group_tables.csv`: expected group tables with `group`, `position`, `team`, `expected_points`, `expected_goal_difference`, and `expected_goals_for`.

The rating and run metadata artefacts are:

- `derived_team_ratings.csv`: the model’s rating snapshot after historical fitting and completed 2026 World Cup updates dated on or before `forecast.as_of`, before simulating remaining fixtures.
- `team_adjustments.csv`: one row per forecast team with base derived rating, squad cohesion score and boost, underdog-magic residual and boost, and final adjusted forecast rating.
- `tuning_summary.json`: selected tuning values and backtest scores when tuning is enabled.
- `run_manifest.json`: run metadata, including `as_of`, simulation count, fitted coefficients, and config path.

The knockout summary artefacts are deliberately different from each other:

- `most_likely_knockout_bracket.csv`: canonical most likely knockout bracket. Groups are ranked by expected table performance, and knockout winners are selected by head-to-head advancement probability. See `docs/most_likely_knockout_bracket_methodology.md`.
- `match_slot_matchup_marginals.csv`: for each knockout match slot in the raw Monte Carlo simulations, the team pairing that appears most often and its simulation frequency. It is not a bracket input.
- `match_slot_winner_marginals.csv`: for each knockout match slot in the raw Monte Carlo simulations, the team that wins that slot most often and its simulation frequency. It is not a bracket input.

Use `most_likely_knockout_bracket.csv` for any chart or report that needs one internally coherent knockout bracket.

The rendered chart artefacts are:

- `winner_odds.png`: bar chart of the leading title probabilities.
- `knockout_bracket.svg` and `knockout_bracket.png`: visual bracket rendered from `most_likely_knockout_bracket.csv` and `run_manifest.json`.

## Reproducibility and limitations

Default run state is `forecast.as_of=2026-06-15`, `forecast.simulations=50000`, `forecast.seed=20260614`. Outputs are deterministic for a fixed config, code version, curated tournament CSVs, squad CSV, and historical CSV.

Known exclusions: player availability, individual player quality beyond national-team results, rest/travel, style-specific team interactions, injuries, weather, market priors, fair-play tiebreakers, the full Annex C third-place combination lookup table, and the official FIFA ranking formula. The local data stores eligible third-place groups per round-of-32 slot; the model assigns qualifying third-place teams by deterministic matching within those eligible slots. The model estimates calibrated probabilities and derives a canonical most likely knockout bracket from expected group standings plus head-to-head advancement probabilities.
