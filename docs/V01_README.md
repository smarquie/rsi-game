# RSI Game

A runnable research implementation of Serge Marquie's **A Two-Level Game of a Self-Improving Agent**, working draft v0.1, 1 October 2026.

Five functional roles play a finite policy game under a shared token budget. A second process diagnoses failures, proposes edits, and evaluates changes using a frozen snapshot that may be promoted every K cycles. This is a simulation of a game-theoretic model; it does not call, train, or modify an actual language model.

## Start in PyCharm

Open this folder as a project. Select **RSI Game - Interactive Lab** and click Run, or run `main.py`. Your browser opens a local laboratory where you can choose stickiness, editable components, promotion, evaluation timing, weak roles, measurement, cycles, and random seed.

The Mac project already has `.venv/bin/python`, using Python 3.11 and the Mac's installed NumPy. The shared PyCharm run configurations specify that interpreter explicitly. If PyCharm asks for a project interpreter for code inspection, select the existing `.venv/bin/python` interpreter.

For a fresh clone:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python main.py
```

Only NumPy is needed. The interface, reports, test runner, and server use the Python standard library. No API keys, remote services, paid dependencies, or frontend build tools are required. If port 8765 is busy, use `main.py --port 8766`.

## Results delivered

Open **results/report.html** for the interactive report, or use the laboratory's report link. Machine-readable results include:

- `results/default_object/object_analysis.json`: all 950,400 default action profiles analyzed, all pure equilibria, certified global team optimum, and deterministic sweep attraction basins.
- `results/study/`: every E1–E8 arm. The exploratory study uses 3 seeds × 100 cycles for each meta arm, and exhaustive enumeration for each of the 12 E5 object regimes. Per-run manifests record parameters, versions, seed, and runtime; `cycles.jsonl` records decisions and outcomes.
- `results/summary.csv` and `results/summary.json`: means and empirical 5th–95th percentile ranges across seeds. These are **not confidence intervals for the mean**.
- `results/analytical_audit.json`: numerical qualifications of analytical claims, a calibration check, and decoded default equilibria.
- `results/tests.txt`: the core validation run.

Default results: **55 pure equilibria**. The ordinary selected equilibrium has success probability **0.4233479187**, welfare **0.2733479187**, and expected token use **0.3**. Global team welfare is **0.3082899971**. Worst pure-equilibrium welfare is **−0.0073315935**, yielding a pure price of anarchy of **0.3156215906**. All default pure equilibria execute zero revision rounds. The prescribed deterministic sweep has no nontrivial cycles at defaults; this does not establish convergence for other update schedules or configurations.

## Commands

Run commands from the project root:

```bash
# Interactive local lab
.venv/bin/python main.py

# One reproducible meta run
.venv/bin/python -m rsi_game simulate --seed 0 --cycles 200 --K 5 --output results/my_run

# Editable evaluation, exact measurements
.venv/bin/python -m rsi_game simulate --edit-class 4 --exact --cycles 100

# Frozen improver (infinity)
.venv/bin/python -m rsi_game simulate --K inf

# Exhaustive equilibria, optimum, and deterministic sweep dynamics
.venv/bin/python -m rsi_game analyze --attractors --output results/default_object

# Export a complete editable configuration
.venv/bin/python -m rsi_game defaults --output config.json
.venv/bin/python -m rsi_game simulate --config config.json

# Individual experiment family; full paper defaults are 50 seeds × 200 cycles
.venv/bin/python -m rsi_game suite --experiment E2 --seeds 50 --cycles 200 --output results/full_suite

# Reproduce delivered exploratory E1–E8 study
.venv/bin/python research.py --seeds 3 --cycles 100 --workers 4

# Full paper-scale study (substantially more computation)
.venv/bin/python research.py --seeds 50 --cycles 200 --workers 4 --output results/full_scale

# Audit analytical qualifications; regenerate report
.venv/bin/python audit.py
.venv/bin/python -m rsi_game report

# Core tests
.venv/bin/python -m unittest discover -s tests -v
```

The report expects `<input>/study/E*/...`, `<input>/default_object/...`, and `<input>/analytical_audit.json`. To report a separate study, put its experiment output in a `study` subdirectory beneath a results root and pass `--input` and `--output`.

## What “exhaustive” means

`analyze --attractors` evaluates every profile of the finite object-level action grid. It certifies all pure feasible equilibria and the global team optimum, and computes every attractor and basin of the deterministic Gauss–Seidel update map in I,M,R,G,C order. Ties retain the incumbent action; improvements must exceed 1e-9. Basin sizes refer to a uniform grid of starting profiles, not an empirical distribution of deployed policies.

It does **not** enumerate mixed equilibria, every asynchronous update rule, all continuous configurations, or all possible stochastic meta trajectories. The meta-game is the draft's diagnosis/proposal/greedy-test behavioral benchmark. It is not a solved Markov-perfect equilibrium. The experiment suite is numerical evidence, not a proof of its hypotheses.

## Model fidelity and explicit completions

1. **Defaults are unchanged.** Initial quality meets the stated 0.35–0.65 criterion, coordinated welfare is higher, and a 10% generator-capability gain with its induced overhead improves welfare by more than 0.005. No automatic retuning is performed.
2. **Mandatory first-pass feasibility.** The paper specifies revision feasibility but leaves first-pass overflow undefined after overhead growth. This implementation requires the full initial pass to fit. Infeasible deviations are excluded; configurations with overhead alone greater than B are rejected. Once some profiles become infeasible, this is a shared-constraint/generalized policy game. At defaults every profile is feasible.
3. **Exact forward evaluation.** The Markov recursion integrates the stated difficulty distribution. Expected rejections include the final flag even when no revision can run. Rounds count only executed revisions. Critic review consumes its fixed cost even at f = 0.
4. **Sampler origins.** A failure is attributed to the last role producing a transition from correct to incorrect, reset on repair. The critic does not directly generate such a transition. Its welfare bottleneck value is therefore distinct from origin-based blame.
5. **Equilibrium evidence.** Every converged solver result is checked for unilateral regret. The seeded logit fallback is explicitly marked nonconverged even if its modal profile happens to have low regret. Low/high/canonical/warm starts only find equilibria; they cannot establish uniqueness.
6. **Team welfare.** Coordinate ascent gives a local team candidate and a lower bound on the selected policy's welfare gap. Only exhaustive enumeration reports a certified optimum and worst-pure price of anarchy.
7. **Queued evaluation changes.** Proposals are compared under the active protocol. The latest accepted value of each coordinate is applied at handover. K = infinity has no handover, so deferred edits remain queued forever.
8. **Promotion gate.** Run one independent Hign-cycle trial under each frozen improver; suppress recursive handovers during trials. Compare endpoint scores under the incumbent evaluator and divide their difference by Hign. The common starting-score term cancels. Discard trial configurations. Report the extra cycle count. Repeated trial averaging is an extension; the draft leaves its count unspecified.
9. **Protocol boundaries.** At clipped rho boundaries, overhead charges scale with the actual change. Raising rho cannot reduce critic overhead below the stated base overhead.
10. **Frontier.** cmax is a soft drift frontier, not a hard capability ceiling; Gaussian edits can exceed it.
11. **Randomness.** Separate NumPy streams for diagnosis, proposals, measurements, and promotion trials. The equilibrium fallback has a deterministic configuration-specific seed. Exact immutable cache keys avoid rounding collisions. Reproduce with the recorded Python/NumPy versions for strongest comparability.
12. **Configuration.** JSON rather than YAML keeps the installation small. `K: null` means infinity. Experiments use Python infinity for the decorrelation-length control; manifest serialization records it as `"Infinity"`.

## Reading the logs

A row describes the agent **after its accept/reject decision but before handover**. `W_before` and `candidate_W` make accept/reject errors auditable. `snapshot_hash` and `snapshot_c` identify the evaluator used that cycle. `score` is exact under the current yardstick; `reference_score` uses the initial snapshot and protocol; `oracle_score` uses true quality and the evaluator's token price.

When a handover occurs, `handover_protocol` and `next_snapshot_hash` describe the next cycle's state. `promotion_trial_cycles` includes discarded gate computation. `converged=false` means the logged policy is a fallback, not a certified equilibrium. `equilibrium_diagnostics` and local welfare-gap bounds are logged every ten cycles by default. Exact counterfactual capability gains and bottleneck hits are logged each cycle.

`false_accept` means an accepted proposal decreases mission welfare. `false_reject` means a rejected proposal would increase welfare by more than the acceptance margin. `reversal_coordinates` counts realized coordinate movements opposite a movement in the preceding epoch; it is not the fraction of all historical edits eventually undone. `candidates` are drawn even when boundary clipping makes them no-ops; noisy evaluation can accept those no-ops.

## Analytical cautions

- Proposition 7's proof holds evaluator detection fixed, but changing generator capability changes its denominator. Fixed cG/tE, or a condition controlling that effect, is needed for the claimed comparison. `audit.py` gives an algebraic conditional counterexample without asserting the configurations induce identical equilibria.
- Proposition 8's derivatives do not imply inevitable arrival at zero with a positive acceptance margin. Clipped final steps can be too small, and changing the agent can change the coefficient. The audit exhibits a 0.01 anchor whose final removal gains only 0.00420 under margin 0.005.
- Proposition 5's attribution formula requires failure shares among perceived true failures. Those differ from unconditional failure shares when detection is origin-dependent.
- Proposition 6 needs exact measurements, a fixed yardstick, and configuration-only selection. Arbitrary evaluator-family cycles do not prove cycles for this specific evaluator.
- Γ = 0 does not make one-step greed optimal over the remaining cycles of an epoch.
- At rhoE = 1 the inversion formula is correct, but default rhoE,0 = 0.9 cannot reach that limit merely by removing separation. Acceptance still needs a score gain above delta.

These qualifications are discussed in the report. The cited literature's bibliographic accuracy and novelty claims have not been independently reviewed.

## Module map

| Module | Responsibility |
|---|---|
| `params.py` | Validated immutable parameters, JSON, configuration fingerprint |
| `grids.py` | Exact finite action grids |
| `episode.py` | Batched exact recursion and independent stochastic sampler |
| `equilibrium.py` | Best responses, regret, logit fallback, team search, exhaustive attractor graph |
| `evaluator.py` | Snapshot correlation, judgment, exact/noisy scoring |
| `meta.py` | Diagnosis, proposals, decisions, handover and gate trials |
| `experiments.py` | All E1–E8 arms |
| `run.py` | CLI and per-run files |
| `analysis.py` | Aggregation and standalone interactive report |
| `app.py`, `lab.html` | Local browser laboratory |
| `research.py` | Parallel experiment runner |
| `audit.py` | Reproducible analytical checks |

No license is assigned automatically. The author can choose distribution terms separately.
