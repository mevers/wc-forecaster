# R32 bracket convergence report rewrite plan

## Objective

Rewrite the R32 convergence retro as a findings report that explains why the prediction patterns changed over time, not just what the metrics did.

## Working thesis

R32 team prediction was strong early because the model started with a strong ratings prior. Exact fixture prediction converged later because the R32 bracket is a routing problem: small changes in group rank, runner-up paths, and third-place allocation can move multiple teams across slots. The two bracket methods expose different parts of that instability.

## Success criteria

- The executive summary states the main causes and implications, not just the headline numbers.
- Context and methodology is readable in one pass and defines only the terms needed for the findings.
- Each finding follows the same shape: observation, hypothesis, evidence, implication.
- The report separates team accuracy from fixture accuracy throughout.
- The report explains method differences: why `expected-table` and `modal-group-table` diverged, and what that tells us.
- Charts support specific findings and do not repeat section headings.
- Technical audit tables remain in the appendix, not in the main narrative.

## Report structure

1. Executive summary
   - State the three core findings: ratings prior, bracket routing sensitivity, and method disagreement as an instability signal.
   - Keep bullets short, but include interpretation.

2. Context and methodology
   - Explain the purpose of the retro.
   - Define the two methods in plain language.
   - Define the three metrics in plain language.
   - State why the team/fixture distinction matters.

3. Deep dive analysis
   - Finding 1: early team accuracy was mostly prior-driven.
   - Finding 2: fixture accuracy lagged because bracket slots are sensitive to rank and route changes.
   - Finding 3: the 26 June regression shows why more correct teams can still mean fewer correct fixtures.
   - Finding 4: neither method dominates; disagreement is the useful signal.

4. Strategic recommendations
   - Report team and fixture accuracy separately.
   - Keep both methods and use disagreement as a warning flag.
   - Add probability outputs for teams and fixtures.

5. Technical appendices
   - Keep daily scores and slot-level audit for reproducibility.

## Execution steps

1. Rewrite the generated report text around the working thesis.
2. Keep chart layout fixes already made.
3. Collapse long appendix tables if the report renderer supports it cleanly; otherwise keep them under technical appendices.
4. Regenerate the report and charts from `scripts/retro_r32_convergence.py`.
5. Run syntax/type checks and report any unavailable tooling.
