# Completed v0.4 study and v0.5.1 launch decision

All **10,704/10,704 runs completed**, with zero failed, missing, unexpected, invalid or incomplete jobs in the research coverage audit. All runs use model hash `d5f31a480d4078bf4ad2`. Runtime was 26,696 seconds, approximately 7.42 hours. Original outputs are preserved. This review builds on the earlier trajectory audit, rather than treating the entire study as a new independent sample.

## What the newly completed families change

| Result | Evidence | Consequence for the next study |
|---|---|---|
| Randomized single-function schedule is useful | Final-20-period reward: 2.992 versus 2.843 for rotation; paired world-mean difference +0.150, exploratory 95% bootstrap interval [0.060, 0.253] | Add randomized scheduling as a candidate; average its four replicas within each world before inference or method selection |
| Adaptive commitment widths are useful | Reward 3.064 versus 2.843 for fixed commitment; difference +0.222 [0.131, 0.328] | Add adaptive commitment as a candidate and verify that subsequent commitment updates preserve the adaptive width |
| Rationing can create misleading apparent stability | Roughly 227,000–229,000 execution-coordinate bound violations per run; 63% of planned turns skipped | Do not describe this as constraint-respecting convergence; continue using feasible deployment plus violation/overload diagnostics |
| Negative rewards expose the old disruption rule | With Y0=-5, the draft rule skips 91.5% of turns versus 3.1% with the absolute-drop rule | Default v0.5.1 to the sign-robust rule and retain reward-offset sensitivity controls |
| Exploration shutdown is deterministic in incompatible configurations | R5 width 0.10/cap 0.03 and width 0.30/caps 0.03 or 0.08 skip 100% of turns | Separate actual commitment half-width from minimum freedom; preflight the generated grid |
| Low damping remains important with many explorers | At budget factor 1, all-explorer reward 2.635 for beta=0.1 versus 1.191 for beta=0.7 | Retain damping controls; do not infer an inherently harmful effect of simultaneous exploration from one damping choice |
| Tighter budgets change dynamics | E11 mean overload per period: 0.081 at budget factor 0.5 versus essentially zero at 2 or 3 | Continue budget stratification and effort accounting |

The intervals above are exploratory, unadjusted paired bootstrap intervals on 50 world-level observations. Random-schedule replicas were averaged within worlds. They motivate controls, not claims that one method universally wins. “Adaptive commitment” here changes the commitment bands; it is distinct from the defective v0.4 adaptive-within-period review discussed below.

## Findings from the earlier audit remain relevant

- Local non-resonant identification can be accurate to about 1e-12 while collective performance is poor. Keep the identification/accessibility/discovery distinction.
- The v0.4 adaptive-within-period review omitted its intended private cost subtraction; its high raw output also involved severe overspending. Do not use E7/R3 to validate the corrected adaptive learner. v0.5 subtracts the private price term and uses feasible deployment; a regression test now checks the subtraction explicitly.
- Large-n arms use more evaluations per period, and different archetypes have different initial headroom. Use matched effort and both absolute and relative outcomes.
- Numerical best-found nonconcave benchmarks are not global certificates. Preserve KKT and feasibility diagnostics.

## Corrections in v0.5.1

1. Added `commitment_half_width`, separate from `w_min`. Core X1 varies half-width 0.05/0.20 with minimum width 0.10 and amplitude cap 0.08. Stability varies half-width 0.01–0.30 with fixed minimum width 0.02. These respect the minimum-freedom constraint without accidentally disabling exploration.
2. Plan generation and execution reject an unlabelled positive-exploration configuration with amplitude cap below minimum width/2. State-dependent skipping is still possible and remains a measured failure mode.
3. Fixed the v0.5 simulator's post-review commitment update: it now preserves the adaptive width rather than overwriting it with a fixed width.
4. Added `random_schedule`, `adaptive_commit`, and `damping03` process controls. Publication/full random-schedule arms receive four nested replicas.
5. Changed the v0.5.1 default disruption rule to `absolute_drop`. This corrects the sign problem, but **does not make the full exploration rule invariant to adding a constant to Y**, because amplitude still depends on its magnitude. The readiness study measures both rules at offsets -5, 0 and +5.
6. Method selection now ranks mean absolute deployment improvement, averaging replicas within world first. This avoids selecting solely on unstable ratios when initial headroom is tiny. Headroom fractions remain secondary reported outcomes. Oracle and R7 are benchmark arms, excluded from selecting the three ordinary process candidates.
7. Added a 60-run readiness study on seeds 900000–900002, disjoint from tuning and held-out publication seeds. It covers both commitment widths, new process controls, signed reward offsets and corrected adaptive execution.
8. The launch script uses fresh `results/v05/v051/` directories. Existing v0.4/v0.5 data must not be resumed under changed code identities.

This is a versioned operational clarification to the theory, not a claim that the previous literal single-width configuration was equivalent. Describe commitment half-width, minimum freedom and exploration amplitude separately in the paper's methods.

## Launch recommendation

Run the corrected publication-oriented package after the readiness checks pass. Start with `paper`, not the maximal `full` grid. The script runs readiness first, then examples, tuning, frozen selection, the core study, typology, long horizons and structural selection/held-out transfer; `--extended` adds stability and continuation studies. Reuse the same command to resume unchanged code and plans. Reports remain explicit about incomplete studies and numerical limitations.

The complete source results are in `results/v04/full/research/research_report.html`. `all-arm-summary.csv` records world-weighted summaries for every arm, and `source-checksums.json` records the input versions used here. The old source and result files were not changed.
