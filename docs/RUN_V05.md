# Running the v0.5 research package

The v0.5 engine is separate from v0.4. Your existing v0.4 study and browser on port 8766 continue to use the old engine. v0.5 reports are standalone HTML files; a browser server is optional.

## 1. Open the project and check the installation

In PyCharm, open this project directory and select its `.venv/bin/python` interpreter:

```bash
cd /Users/sergemarquie/Documents/Codex/2026-10-01/wha/outputs/rsi-game
.venv/bin/python --version
.venv/bin/python -m unittest discover -s tests/v05 -v
```

The current environment already has the required libraries. On a fresh checkout:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-v05-tested.txt
.venv/bin/python -m pip install --no-deps -e .
```

The project files and run configurations are ready. Automatic GUI launch from this restricted session failed in the JetBrains Java runtime; open the project from your existing PyCharm window if needed. This does not affect the tested terminal commands.

New PyCharm run configurations prepare the publication core plan, execute the validation plan, or rebuild a report. `main_v05.py` prepares a pilot plan and prints the launch command. The existing `main.py` intentionally remains the v0.4 interactive laboratory.

## 2. Validate all execution paths first

```bash
.venv/bin/python -m rsi_game.v05 suite \
  --plan configs/v05/validation-plan.json \
  --output results/v05/my-validation \
  --workers 2

open results/v05/my-validation/research/research_report.html
```

This is a 46-job integration check covering the remedies, independent-learning controls, numerical saddle, all intervention types, pinned/unpinned invisible controls and structural selection. Short runs test the software; they do not establish scientific conclusions. The validation plan does not replace the paper's complete T1–T34 checklist; see `V05_FIDELITY.md`.

## 3. Pilot, then inspect the cost

The pilot below runs five held-out world seeds across the core experiments, 100 periods, 32 benchmark starts and five accessibility starts. It is more substantial than the validation check.

```bash
.venv/bin/python -m rsi_game.v05 plan \
  --study core --preset pilot \
  --output results/v05/pilot/plans/core.json

.venv/bin/python -m rsi_game.v05 suite \
  --plan results/v05/pilot/plans/core.json \
  --output results/v05/pilot/core \
  --workers 2

open results/v05/pilot/core/research/research_report.html
```

Prepare the larger plan without executing it, then extrapolate runtime and raw disk use from your own Mac:

```bash
.venv/bin/python -m rsi_game.v05 plan \
  --study core --preset paper \
  --output results/v05/paper/plans/core.json

.venv/bin/python -m rsi_game.v05 estimate \
  --plan results/v05/paper/plans/core.json \
  --pilot results/v05/pilot/core --workers 2
```

These estimates are approximate: dimension, optimizer difficulty, benchmark reuse, longer horizons, accessibility frequency and HTML reporting affect the cost. In particular, 12-function support enumeration can be much slower than five-function cases. A partial run can be produced with `--max-jobs 10`; its report is explicitly labelled PARTIAL.

## 4. Run the publication-oriented package

```bash
caffeinate -i bash scripts/run_v05.sh paper 2
```

The script performs the stages in this order:

1. Numerical examples.
2. Remedy tuning on seeds 0–99, then freezes three selected processes.
3. Core X1–X5 experiments on held-out seeds 100–149.
4. X6 factorial typology: 9 archetypes × 4 value profiles × 3 strengths × 3 budget factors × 20 worlds, each with baseline and three selected processes.
5. Broad-ensemble descriptor coverage and prediction checks.
6. Long-horizon replication to 3,000 periods, with outputs at 300, 1,000 and 3,000.
7. Bounded structural-edit selection on seeds 0–99.
8. Every prefix of the frozen transferable process-edit sequence on fresh held-out worlds.

It automatically creates reports after each study and runs the descriptor/behavioural analysis on the typology and broad ensembles. It stops on failed jobs rather than silently continuing to selection. It never launches the old v0.4 experiments.

For the symmetric stability grid and 21-point continuation paths as well:

```bash
caffeinate -i bash scripts/run_v05.sh paper 2 --extended
```

The `paper` preset is a tractable reduction of the maximal grid, not a promise of statistical power. It uses 50 held-out seeds for core studies, 300 periods for primary endpoints, 300 benchmark starts and 20 accessibility starts. Factorial typology uses the full 6,480-world construction. The separate long-horizon stage investigates persistence on selected processes. A claim that explicitly requires 500 held-out worlds must use `full`, not `paper`.

For the maximal prepared grid, including 500 held-out seeds and longer horizons:

```bash
caffeinate -i bash scripts/run_v05.sh full 2 --extended
```

This is an exceptionally large computational study, not an overnight Mac command. The core alone exceeds 180,000 jobs and 600 million learning periods; typology, continuations, accessibility optimization and HTML appendices add substantial work and storage. Prepare and estimate before launching:

```bash
.venv/bin/python -m rsi_game.v05 plan \
  --study core --preset full \
  --output results/v05/full/plans/core.json

.venv/bin/python -m rsi_game.v05 estimate \
  --plan results/v05/full/plans/core.json \
  --pilot results/v05/pilot/core --workers 2
```

## 5. Individual stages, if you prefer control over timing

These are the full publication-oriented commands that the script runs. Each can be resumed independently.

```bash
# Tune on selection worlds only.
.venv/bin/python -m rsi_game.v05 plan --study tuning --preset paper --output results/v05/paper/plans/tuning.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/tuning.json --output results/v05/paper/tuning --workers 2
.venv/bin/python -m rsi_game.v05 select --input results/v05/paper/tuning --output results/v05/paper/selection.json

# Core research questions.
.venv/bin/python -m rsi_game.v05 plan --study core --preset paper --output results/v05/paper/plans/core.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/core.json --output results/v05/paper/core --workers 2

# Structural typology, conditional on the frozen tuning selection.
.venv/bin/python -m rsi_game.v05 plan --study typology --preset paper --selection results/v05/paper/selection.json --output results/v05/paper/plans/typology.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/typology.json --output results/v05/paper/typology --workers 2
.venv/bin/python -m rsi_game.v05 typology-analysis --input results/v05/paper/typology

# Long-horizon replication, without selecting again on test results.
.venv/bin/python -m rsi_game.v05 plan --study long --preset paper --selection results/v05/paper/selection.json --output results/v05/paper/plans/long.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/long.json --output results/v05/paper/long --workers 2

# Select bounded edits, then evaluate transferable process edits on fresh worlds.
.venv/bin/python -m rsi_game.v05 plan --study structural --preset paper --output results/v05/paper/plans/structural.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/structural.json --output results/v05/paper/structural --workers 2
.venv/bin/python -m rsi_game.v05 select-structural --input results/v05/paper/structural --output results/v05/paper/structural-selection.json
.venv/bin/python -m rsi_game.v05 plan --study structural-test --preset paper --selection results/v05/paper/structural-selection.json --output results/v05/paper/plans/structural-test.json
.venv/bin/python -m rsi_game.v05 suite --plan results/v05/paper/plans/structural-test.json --output results/v05/paper/structural-test --workers 2
```

Selection is deterministic and recorded with source checksums. Remedy selection ranks average final captured headroom across balanced tuning cells. Structural transfer selects process edits accepted in at least half of selection runs, in acceptance-frequency order; every prefix is evaluated. An empty accepted sequence is a valid negative result. Structural selection effort is retained separately; held-out performance alone must not be described as cost-free recursive improvement.

## 6. Resume, report, and inspect failures

Run the identical command again to resume. Completed jobs are reused only if their configuration, source-code identity and file checksums match. Do not edit the v0.5 source while a study is running. After a code change, use a new output directory. Ctrl-C stops orchestration; incomplete jobs can be rerun. Do not delete a completion marker to disguise a mismatched run.

```bash
.venv/bin/python -m rsi_game.v05 report --input results/v05/paper/core
open results/v05/paper/core/research/research_report.html
```

`failures.json` lists failed jobs. Coverage tables distinguish missing jobs and integrity failures. Mixed-code reports are refused. SciPy's bounds-clipping warning alone does not establish failure; feasibility and KKT diagnostics remain in the outputs. If a run fails, inspect its logged error rather than suppressing all warnings.

## 7. What you receive for the paper or blog

Each study's `research/` directory contains:

- `research_report.html`: complete coverage, arm summaries, paired comparisons, effort-matched comparisons, intervention effects and links to every run.
- `all_runs.csv`, `all_periods.csv`, `all_arm_statistics.csv`: complete scalar data and world-level bootstrap intervals.
- `paired_contrasts.csv`: matched baseline differences, paired sign-randomization p-values and Holm correction within experimental families.
- `matched_effort_pairs.csv`, `matched_effort_statistics.csv`: comparisons at a common evaluation/resource budget, with actual consumed resources retained.
- `horizon_outcomes.csv`: available 300/1,000/3,000-period endpoints.
- `intervention_effects.csv`, `intervention_statistics.csv`: D, F, Gamma0, Gamma1 and A, plus realized ceiling-effect bins.
- `structural_selection.csv`: accepted edits and charged effort.
- `descriptor_generalization.csv`, `descriptor_predictions.csv`, `behavioural_clusters.csv`, `descriptor_occupancy.csv`, when the typology analysis has adequate data.
- `report_manifest.json`: provenance and coverage.

Each `runs/<id>/result.json` retains the full nested records, ordered/Shapley decomposition, accessibility witnesses, benchmark candidates, configurations and effects. Standard runs also have Parquet period data. Every run has an HTML appendix, not just representative examples.

Speed events that do not occur are right-censored. Restricted mean times include censored runs; reported event-specific resource averages condition on reaching the target. Marginal bootstrap intervals are not simultaneous confidence bands. The paired sign tests require an exchangeable/symmetric null for paired differences. Use corrected confirmatory contrasts, not whichever subplot looks strongest after browsing the held-out results.

The package is an experimental foundation. No finite collection of simulations establishes “all possible dynamics”; impossibility claims require analytical conditions or numerical certificates. The implementation conventions and remaining optional extensions are documented in `V05_FIDELITY.md`.
