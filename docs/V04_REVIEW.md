# Review of the v0.4 functions game

## Assessment

This is a substantial new model, not a parameter revision. The earlier game had finite role policies, evaluation snapshots and promotion. Version 0.4 instead studies continuous settings, private local beliefs, deliberate experiments, self-commitment and an endogenous budget price. It is a cleaner framework for separating local identification from coordination failures. Its most interesting research question is whether locally accurate learning can still produce globally poor, unstable or infeasible behavior.

The revision justifies a separate simulation engine. The old finite enumeration cannot answer the new continuous problem. No finite experiment design can cover every continuous state, parameter, initial condition and schedule. The implementation therefore combines analytical checks, numerical optimization bounds, controlled examples, broad parameter sweeps and explicitly limited trajectory diagnostics.

This review uses the supplied `rsi_functions_game_v04.pdf` as the model specification. It does not independently establish bibliographic accuracy or novelty.

## Issues to resolve in the manuscript

1. **Exact quadratic versus local approximation.** The simulator uses the globally exact quadratic Y = Y0 + b·q + qᵀCq. Exact demodulation and identification statements should be conditioned on that assumption. For a general smooth aggregate, Taylor remainder and changing backgrounds require approximation bounds.
2. **Local learning versus global control.** Recovering a slice correctly is not a convergence theorem for the coupled price/commitment process. Fixed-price coordinate ascent, unrestricted oracle clearing, finite-width commitments and lagged price adaptation are different dynamical systems. A proof for one does not transfer automatically to the others.
3. **Budget jumps and finite execution counts.** At a discontinuous best response, an ideal mixture can clear an average budget. With a finite T, arbitrary mixture fractions are not exactly realizable. The implementation rounds the high branch down, records both theoretical and realized spending, and reports the residual. More than one function may participate in a jump mixture. Such variation can violate the fixed-background identification assumptions.
4. **Exploration can shut down by construction.** A scheduled turn is skipped when amplitude < minimum width/2. With width 0.1 and maximum amplitude 0.03, every turn skips. Width 0.2 also disables the default amplitude 0.08. These draft combinations are retained and flagged, not silently repaired.
5. **All functions exploring removes the price response.** If no free function remains, increasing price cannot change their paths. The result may be slack budget and zero price, or unavoidable overload even at the price cap. This is a substantive architectural case, not an optimizer failure.
6. **Relative disruption depends on the aggregate's origin and sign.** Adding a constant to Y changes both amplitude and ex-post decisions without changing marginal incentives. For negative Y, the draft's relative loss rule can halve exploration even when Y is unchanged. R4 compares offsets and an explicitly labeled absolute-drop variant; the baseline remains faithful to the draft.
7. **Information impossibility requires precise scope.** The fixed-background non-identification construction supports a local observational-equivalence claim. It does not, by itself, rule out identification from every possible history, richer memory, known frequencies or coordinated experiments. The baseline algorithm does not store off-diagonal interactions; that design restriction should not be presented as a universal information theorem.
8. **Detecting a change is different from responding to it.** Other functions' changes can move the intercept or aggregate even when the relevant local slope is unchanged. Statements that a change is completely unnoticed need stronger conditions than unchanged marginal incentives.
9. **Invisible intervention is local to a specified point.** The construction preserves slices through the pinned target. Finite-width behavior, shifted centers near boundaries and changing backgrounds can reveal an effect. The informed-relocation control is labeled as an additional intervention.
10. **Optimization evidence needs qualified labels.** Multi-start SLSQP gives feasible candidates and a best-found objective. It does not enumerate every local maximum or certify the global optimum in an indefinite world. KKT residuals and tangent-space curvature are diagnostics; at boundaries they do not substitute for a full critical-cone proof. The optional bound solver reports its remaining numerical gap.
11. **Feasibility must accompany outcomes.** Raw Y above a feasible benchmark can reflect overload. Targets themselves may also be infeasible. Reports separate raw aggregate, overload penalty, spending, realized settings and targets.
12. **Replication is hierarchical.** Conditional on its world and deterministic schedule, a baseline run is deterministic. Four different seed labels do not create four independent observations. Independent worlds are the statistical unit; random schedules/interventions supply nested replicas. The plan removes duplicates by default.

## Implementation choices made explicit

- Settings are bounded by qbar = 1 − 10⁻⁶; cost is −γ log(1−q).
- Scalar best responses evaluate endpoints and every admissible stationary root. Concave cases have a vectorized implementation checked against the scalar reference.
- Fixed-background periods clear an average budget. Adaptive baseline uses lagged multiplicative price updates and partial setting adjustment; `adaptive_exact` is a separate exact-clearing control.
- A function's review receives only its own settings, aggregate observations, public price, own cost/weight and its own state. The true interaction matrix is confined to world generation and external diagnostics/benchmarks.
- Fits use centered/scaled least squares before conversion to the paper's coefficient basis. Logs record fit rank/conditioning and whether exact-identification assumptions held.
- The default nonresonant frequencies are [1,4,10,13,28]. Larger dimensions use a deterministic greedy extension, and execution count automatically satisfies T > 6 max(m).
- Rationing is implemented as an explicit alternative; physical scaling can violate commitment lower bounds, which are logged. Unspecified adaptive-rationing combinations are rejected.
- Ex-post disruption halves/doubles each function's amplitude scale. Belief memory and target damping are separate parameters.
- Outside interventions preserve a world-version history and invalidate stale diagnostic contexts.
- A settling diagnostic requires at least 20 observed periods inside the endpoint tolerance; otherwise it is null. It remains an outcome diagnostic, not proof of convergence of settings or price.

## Evidence already obtained

The 36-run smoke suite exercises every experiment family; it checks execution and diagnostics, not research hypotheses. Four E12 trajectories run for 300 periods each. In the linear baseline, the last-20-period target range is about 0.655 and accumulated mean-overload is about 97.2. Both interference starts likewise show large target motion and overload. These results do not establish a periodic orbit, but they do rule out interpreting these finite runs as convergence to the worked-example optima.

The worked-example mathematical benchmarks are checked independently of these learning trajectories. For Example 4.7 the optional numerical bound has lower value 0.656164490237 and an upper/lower gap about 10⁻⁹. This is a floating-point bound with numerical tolerances, not a formal interval-arithmetic proof.

The five-world, 32-start calibration pilot finds multiple validated stationary candidates in 1/5 worlds, below the draft's one-third target. All five best-found solutions bind the budget and have initial gaps above 5%. This sample is too small to establish population frequencies; defaults are preserved. Run the 50-world, 300-start calibration before tuning, record tuning separately, and evaluate tuned settings on held-out worlds.

The next high-value decision is which price/commitment mechanism should define the main model. Run E1, E4, E7 and R2–R6 first: they separate failure to learn, inability to explore, physical infeasibility, and price-driven instability. Once that mechanism is fixed, use E2/E6/E8/E9 to investigate traps, stale beliefs and the value of outside change.
