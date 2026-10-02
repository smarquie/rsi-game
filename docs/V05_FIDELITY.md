# v0.5 implementation, assumptions and publication boundaries

Source: Serge Marquie's `rsi_functions_game_v05.pdf`, working draft 0.5, October 2026. The original PDF is not copied into the public repository. The v0.4 source remains unchanged.

## Implemented research mechanisms

- Version-isolated world, best responses, price clearing, within-period execution and private local review.
- Standardized feasible deployment, cost-proportional fallback rationing, improvement, remaining opportunity, headroom, persistent threshold times and evaluation/resource accounting.
- R1 target-step cap, R2 price EMA, R3 integral price, R4 motive-aware commitment, R5 degeneracy-aware target updates, R6 spending-transfer channels, R7 full-frequency identification and joint optimization.
- Full-frequency design `[1,4,10,17,29]`, with dimension-dependent execution lengths; public-signal regression recovers the local quadratic in dither coordinates.
- Oracle support-enumerated accessibility searches, misallocation index, KKT residuals, pair transfer curvatures and numerical barrier-radius utility.
- Ordered five-component target-error decomposition and all-order Shapley allocation.
- Candidate failure taxonomy with an additional unresolved/transient class; a short run is not automatically called convergence.
- Four-arm copied-state interventions, frozen-learning controls, invisible perturbations, new functions and bounded process/environment edits.
- Rollback of rejected structural edits and state, implementation budget costs, charged validation effort, selection/test separation and fresh-world process-prefix evaluation.
- Nine structural archetypes, four positive value profiles, structural descriptors, broad ensembles, continuation paths, leave-archetype-out logistic/boosted prediction, behavioural clustering and occupancy audits.
- Frozen plans, atomic completed-run markers, input checksums, code identity, resumability, all-run reports and world-based statistical analysis.

## Additional assumptions that must be stated in the paper

**R7 feasibility is an oracle service.** The shared frequency design identifies performance in dither units. It does not identify other functions' costs or their settings. The implemented joint optimizer reconstructs the learned performance function but uses the simulator's cost/budget information to enforce feasibility. This is explicitly recorded in the run. It is an informed benchmark, not a demonstrated communication-free implementation of feasible joint optimization. A decentralized spending-coordinate version would require a separate approximate identification model and common feasibility protocol.

**R6 has shared feasibility clipping.** The slope and curvature fit use only the public reward and the hard-wired waveform. For heterogeneous costs the simulator selects a safe common amplitude and clips the common spending transfer to both members' feasible ranges. This requires a shared feasibility service. At a boundary with no two-sided feasible amplitude the channel is blocked; the implementation does not invent an untested one-sided estimator. Interpret R6 results conditional on this coordination capability.

**Private review versus oracle diagnostics.** Truth-based accessibility, reference prices and error decompositions are not fed into baseline private review. Oracle joint moves and R7's budget feasibility are separately labelled. Reference-price and benchmark calculations are diagnostic work, not environmental evaluations available to the learners.

**Shapley counterfactual convention.** The five corrections act additively on the local linear coefficient, curvature and price; counterfactual negative prices are floored at zero. Every order uses the same convention. The ordered decomposition is the paper's telescoping decomposition; the Shapley attribution depends on this explicit off-path counterfactual definition.

**Value profiles.** `aligned` and `anti_aligned` rank positive values by absolute loading on the leading eigenvector and preserve the sampled values and their norm. This is an explicit positive-value convention, not an unspecified signed rotation of b. `uniform` gives equal values before an activation-cluster adjustment. Top-eigenspace projection makes the alignment descriptor well-defined at repeated eigenvalues. Curvature ratios use mean absolute diagonal curvature. Complement modularity uses a greedy weighted community partition, not an exact modularity certificate.

**Structural catalogue.** The implemented default is a small fixed catalogue: U1 acts on edge (0,1) if negative, U2 on function 0, U3 enables pair (0,1), and U4–U6 use documented fixed rates/width/design choices. The proposer never searches true coefficients for the best edge. This is a bounded catalogue experiment. It is not an exhaustive search over every edge, cost role or parameter grid. Accepted process changes compose; full-design periods take precedence when they coincide with channel periods.

**Adaptive execution.** Baseline adaptive execution uses the price-adjusted private fit. The inter-period integral price is supported with fixed within-period execution; combining it with a second adaptive price loop is rejected rather than silently inventing a rule.

## What numerical outputs do and do not establish

A positive accessibility gain is a feasible witness. Multistart failure to find a gain does not prove Delta_m = 0 or a positive barrier radius. F/G classifications are therefore explicitly candidates. The numerical barrier utility returns a search bracket, not a certified impossibility interval. Exact examples support unit tests; they do not certify arbitrary indefinite worlds.

Concave KKT benchmarks can be globally certified. Nonconcave best-found ceilings are lower bounds on the true optimum. Consequently reported opportunity is a lower bound and captured headroom is an upper bound. Even an A classification in an uncertified world is success relative to the reported best-found benchmark. The inherited optional branch-and-bound routines are available to investigate small cases, but are not automatically run across the full grid.

A deployment is feasible even if its learned commitment bounds are infeasible: the fallback rationing rule is logged. Learning-period overload is retained and charged separately. Learning-period average reward and deployed reward are different quantities.

Current reports include marginal bootstrap intervals, explicit paired contrasts with Holm correction, effort-matched comparisons and censoring. Descriptor predictions and clusters are exploratory. Descriptor occupancy is audited; no automatic top-up claims to have filled every possible bin. Phase-plane data are exported, but partial-dependence/ALE plots and bootstrap refitting of prediction models are not yet automated. Those extensions are optional analysis work, not implemented results.

The X3 start sensitivity records trajectories and terminal allocations; a universal basin enumeration is not possible from a finite random-start sample. X4 records realized ceiling-effect bins, but arbitrary intervention magnitudes are not guaranteed to be matched; restrict comparisons to overlapping bins. Adding a function does not guarantee it is active or inactive: the final activity is logged rather than inferred from its label.

The structural test records selection costs separately and tests process prefixes on fresh worlds. A claim about increased edit-search productivity requires a further matched-effort study of repeated proposal search on those prefixes; higher held-out deployment performance alone does not establish that stronger claim.

## Verification scope

Automated checks cover deployment under infeasible bounds, the exploration premium, saddle multiplier and transfer curvature, unilateral versus coordinated opportunity, three-function activation, transfer budget preservation, full-frequency recovery, invisible-slice preservation, descriptor invariances, exact decomposition sums, all implemented remedies, frozen exploration, the symmetric scalar table/derivative, paired-control identity, resume integrity and report coverage. The interference and activation barrier estimates have also been checked numerically against the draft.

This is not a claim that every T1–T34 item has been independently replicated. In particular, reduced-model long-run oscillation thresholds, every numerical illustration, all corner selection cases and the paper's complete parameter grids require dedicated verification. The `stability` study runs the finite-dither engine; `reduced.py` separately implements the scalar formulas so those two models are not conflated.

Before a strong paper claim, retain a frozen plan, report complete coverage, review numerical failures, distinguish candidate from certified optima, and evaluate sensitivity to horizons and intervention magnitude. A blog can present the validated mechanisms and explicitly labelled exploratory simulations sooner. Neither format should describe this bounded quadratic game as an empirical test of actual LLM self-improvement without a separate empirical bridge.
