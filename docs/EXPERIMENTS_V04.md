# v0.4 experimental protocol

## Design and scope

`rsi_game/v04/experiments.py` is the executable design. `configs/v04/full-catalog.json` contains every arm, effective configuration, replication count and design flag without the large expanded job list. `plan --preset full` materializes that list without starting work. Draft defaults are unchanged. Robustness families are explicit extensions, not corrections silently substituted for the draft.

| Family | Arms | Factors / purpose |
|---|---:|---|
| E1 | 54 | Concave worlds: k = 1,2,5; damping = .3,.7,1; width = .02,.1,.2; budget factor = 1,3 |
| E2 | 18 | Frustrated/interference worlds; prior slope .5,1,2; maximum private motive 0,.3,.6 |
| E3 | 6 | k = 1,2,5 × nonresonant/resonant exploration |
| E4 | 9 | Disruption tolerance .005,.02,.05 × maximum amplitude .03,.08,.15 |
| E5 | 18 | Private motives 0,.3,.6 × width .02,.1,.3 × reviewed/unreviewed |
| E6 | 12 | Interaction scale .1,.4,.8 × k = 1,5 × belief memory .5,1 |
| E7 | 5 | Fixed background; lagged adaptation .1,.3,1; exact-clearing adaptive control |
| E8 | 4 | Concave, complements, interference, frustrated world structures |
| E9 | 9 | Random, invisible, local, cost interventions × k = 1,5; informed relocation control |
| E10 | 4 | n = 3,5,8,12; automatically compatible frequencies and execution counts |
| E11 | 4 | Budget factor .5,1,2,3 |
| E12 | 4 | Linear example, private-motive version, interference example from two controlled starts |
| R1 | 7 | Rotating/random schedule × k = 1,2,5; all-functions schedule |
| R2 | 4 | Price/rationing × fixed/adaptive commitment width |
| R3 | 9 | Price gain .1,.5,1 × adjustment .1,.3,1 |
| R4 | 6 | Aggregate offsets −5,0,5 × draft/absolute-drop disruption rule |
| R5 | 12 | Width 0,.02,.1,.3 × maximum amplitude .03,.08,.15 |
| R6 | 9 | All-explorer periods × budget .5,1,3 × damping .1,.7,1 |

Total: 194 arms. Smoke selects the first and last arm of each family (36 runs). Pilot uses all arms, five worlds and 100 periods (954 runs). Full uses 50 worlds and 300 periods, with up to four replicas only where the schedule or intervention is stochastic (10,704 runs). Worked examples use one fixed world. E5 unreviewed arms have period zero only. Outside interventions occur halfway through the chosen horizon.

## Questions, measures and controls

**Identification:** compare fitted curvature/local slope errors under verified premises; resonant controls; fixed versus adaptive background; rank, conditioning and skipped turns. A large error where assumptions fail is not evidence against the conditional identification result. Curvature can be recovered while the effective slope differs because price response changes the path.

**Coordination and stability:** report target path length, last-20-period target range, endpoint-relative aggregate settling, price/complementarity residuals, mean spending, overload, commitment violations, and skipped-turn counts. Inspect trajectories, not just final outcomes. A repeated pattern in a finite trace is a candidate cycle requiring longer horizons and return-map analysis, not a proven attractor.

**Efficiency and traps:** compare actual and target aggregates to feasible team best-found, ignoring-interactions and informed-free benchmarks. Report numerical KKT/slice residuals and distance to discovered candidates. Use optional bounds on small worlds. Different basins or local candidates do not establish that every trap has been found.

**Exploration:** compare actual mean-Y shift with the quadratic prediction only where its frequency/background assumptions hold. Separate harm due to exploration, stale models, price changes and overload. Flag width/amplitude combinations that necessarily suppress every turn.

**Outside changes:** inspect the pre/post world versions, local-fit response, target movement and recovery, distinguishing changed payoffs from changed costs. Compare invisible changes with explicit relocation; do not treat the latter as a spontaneous capability of the baseline function.

**Scale and budget:** dimension comparisons automatically increase T as required by frequency separation; this changes computational effort. Report effort as well as outcomes. Examine budget factors alongside overload and price responsiveness.

## Statistical plan

World seeds share underlying draws across compatible arms for paired comparisons. Changing dimension or structural family need not create comparable physical worlds; seed matching alone is not a causal guarantee. Within a world, average stochastic replicas first. Use worlds as the independent units and report means with 90% percentile-bootstrap intervals. One world has no inferential interval. The reports use 2,000 bootstrap resamples with a fixed seed.

The automatic paired contrasts are descriptive differences versus the first completed arm in lexical order. For confirmatory work, preselect scientifically meaningful baseline/treatment pairs and primary outcomes, define exclusions in advance, and account for the many comparisons. Do not infer significance from a large collection of unadjusted intervals. Treat null settling values as censored/not observed; a mean over observed settling times alone is selection-sensitive.

Calibration is separate from the primary comparison. Inspect 50 worlds and 300 starts before deciding whether the stated one-third multimodality criterion is met. If tuning is needed, archive the original calibration, record the new settings, and evaluate them on a separate set of world seeds using individual `simulate --world-seed` jobs or an explicitly modified design. Do not retroactively relabel a tuned study as the original default study.

## Validation and further extensions

The test suite covers scalar best responses, budget clearing, jump mixtures, exact frequency identification, demodulation, exploration effects, boundary centers, staleness identities, worked-example benchmarks, coordinate updates, adaptive total-derivative behavior, invisible interventions, numerical bounds, rationing violations, shutdown conditions, persistence and replication bookkeeping. Full validation expands the random best-response grid check.

The delivered design covers the specified quadratic model and declared extensions. It does not enumerate every continuous dynamic or test arbitrary nonlinear aggregates, observation noise, strategic schedule selection, alternative long-memory learning algorithms, endogenous utility weights, arbitrary n, or all parameter combinations. These would require new hypotheses and explicitly versioned extensions. Formal convergence or impossibility claims require proofs in addition to experiments.
