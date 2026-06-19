---
author:
  name: Maurits Evers
  email: maurits.evers@gmail.com
revisions:
  - date: 2026-06-19
    notes: Initial upset ranking methods document
---

# Upset ranking methods

## Overview

The analysis uses three complementary definitions of an upset. A match can rank
highly under one definition and not another because each measures a different
aspect of surprise.

### Outcome upset: Was the winner or draw unexpected?

This method considers only whether the match ended in a home win, draw, or away
win. If the forecast assigns 80% to the favourite, 15% to a draw, and 5% to the
underdog, an underdog win is the larger outcome upset. Only results that differ
from the most likely 1X2 outcome are included. Lower realised-outcome
probability means a larger upset.

### Exact-score upset: How surprising was that precise score?

This method measures the pre-match probability of the precise scoreline. A 7-1
result is therefore distinct from a routine 2-0 win, even when the same team was
favoured. Germany 7-1 Curacao can rank as a major exact-score upset although
Germany winning was expected. Every completed match is eligible; lower
probability means a more surprising scoreline.

### Winning-margin upset: How surprising was the scale of the win?

This method considers the winner and the size of the victory. For a 5-1 result,
it calculates the probability that the winner would win by four or more goals,
including scores such as 4-0, 6-1, and 7-2. It is well suited to exceptional
routs because it does not depend on the precise score. Draws are excluded.

In short:

| Method | Question | Ignores |
|---|---|---|
| Outcome | Was the home win, draw, or away win unexpected? | Exact score and margin |
| Exact score | Was this precise scoreline unexpected? | Similar scorelines |
| Winning margin | Was a win at least this large unexpected? | Precise score |

## Statistical definitions

Let \(H\) and \(A\) be the home and away goal counts. The model assumes
independent capped Poisson distributions derived from the latest forecast
snapshot strictly before the match:

\[
H\sim\operatorname{Poisson}(\lambda_H),\qquad
A\sim\operatorname{Poisson}(\lambda_A).
\]

The configured support is \(0,\ldots,c\), with probability above \(c\) folded
into the \(c\) bucket.

### Outcome-upset probability

Define the three 1X2 events:

\[
O_H=\{H>A\},\qquad O_D=\{H=A\},\qquad O_A=\{H<A\}.
\]

The pre-match forecast supplies \(P(O_H)\), \(P(O_D)\), and \(P(O_A)\). Let
\(O^\ast\) be the realised event and
\(\hat O=\arg\max_O P(O)\) the modal 1X2 outcome.

A match enters the outcome-upset ranking only when \(O^\ast\ne\hat O\). Its
ranking statistic is

\[
U_{\text{outcome}}=P(O^\ast).
\]

Matches are sorted in ascending order. This is a categorical surprise measure,
not a scoreline measure.

> [!EXAMPLE]
> **Spain vs. Cape Verde**
>
> Pre-match probabilities:
>   - Spain wins: 85.6%
>   - Draw: 9.8%
>   - Cape Verde wins: 4.6%
>
> Actual result (the realised outcome): 0-0
>
> Then: Outcome upset probability $U=P(O^\ast) = 0.098$
>
> Modal outcome was a Spain win = $\arg\max P(0.856,0.098, 0.046)$
>
> 1. Since realised and modal outcome differ, the match qualifies as an upset.
> 2. A _lower_ realised outcome probability ranks as a _larger_ upset.

### Exact-score probability

For observed score \((h,a)\), independence gives

\[
U_{\text{exact}}
=P(H=h,A=a)
=P(H=h)P(A=a).
\]

All matches are ranked in ascending order of \(U_{\text{exact}}\). Probability
assigned to nearby scores does not contribute, so unusual high scores often
rank prominently.

> [!EXAMPLE]
> **Germany vs. Curaçao**
>
> Pre-match model estimates (xG): $\lambda_\text{Germany} = 2.62$, $\lambda_\text{Curaçao} = 0.57$
>
> Actual result: 7-1
>
> Under independent Poisson goal models:
>   - $P(H = 7) = \displaystyle e^{-2.62}\frac{2.62^7}{7!} \simeq 0.021$
>   - $P(A = 1) = \displaystyle e^{-0.57}\frac{0.57^1}{1!} \simeq 0.323$
>
> Then: $U_{\text{exact}} = P(H = 7, A = 1) = P(H = 7) P(A = 1) = 0.021 \times 0.232 = 0.0068$
>
> In words: The model assigned roughly a 0.68% probability to the precise 7-1 outcome.

### Winning-margin probability

For a home win with observed margin \(m=h-a>0\),

\[
U_{\text{margin}}
=P(H-A\ge m)
=\sum_{i-j\ge m}P(H=i)P(A=j).
\]

For an away win with margin \(m=a-h>0\),

\[
U_{\text{margin}}
=P(A-H\ge m)
=\sum_{j-i\ge m}P(H=i)P(A=j).
\]

Only decisive matches are eligible. The statistic is a one-sided tail
probability that recognises both unexpected winners and extraordinary routs by
pre-match favourites.

> [!EXAMPLE]
> **Sweden vs. Tunesia**
>
> Actual result: 5-1. Actual observed winning margin 5-1 = 4.
>
> The winning margin probability is P(Sweden wins by at least 4 goals).
>
> Pre-match model estimates (xG): $\lambda_\text{Sweden} = 1.21$, $\lambda_\text{1.13} = 1.13$
>
> Sum the probabilities of every score where Sweden wins by four or more goals. This includes 4-0, 5-0, 5-1, 6-0, 6-1, 6-2 and all other qualifying sores within the model's capped support (max of 8 goals per team).
> 
> The resulting probability is $U_{\text{margin}} = 0.0143 = 1.43%$

---

> [!NOTE]
> These three upset measures should not be combined into one number without choosing an
> explicit weighting. They describe distinct notions of surprise, so the script
> reports three separate rankings.
