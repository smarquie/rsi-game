# Complete experimental research reports

Every `suite` command now generates a research bundle automatically after the requested jobs finish, including when individual jobs fail. Failed or missing jobs remain visible in the coverage audit. Use `--no-report` only to defer the report, and run `report` later. A manually interrupted suite can be reported from its completed results.

For an existing study, no model rerun is needed:

```bash
.venv/bin/python -m rsi_game.v04 report --input results/v04/smoke --contrasts configs/v04/research-contrasts.json
.venv/bin/python -m rsi_game.v04 report --input results/v04/examples
```

Open `results/v04/smoke/research/research_report.html`. The ordinary dashboard also links to it. Generate a separate report for each study directory; do not combine directories containing different configurations under identical family/arm/world/seed identities.

## What is included

- **Every valid completed run**, with no representative-run cap. The report links to an individual appendix for each run: interactive trajectories for all periods and functions, complete scalar period records, every derived metric, final function states, benchmark history and reproduction manifest.
- **Every completed arm**, including adverse, null, nonconverged and overloaded results. Each arm has a methods/configuration record, numerical narrative, design flags, and descriptive statistics for all metrics.
- **All-family figures** in SVG and PNG, showing every completed arm's late reward, overload and target movement. These complement the earlier representative trajectory figures. Captions and paths are in `figure_index.csv`.
- **Editable report text** in `research_report.md`, containing study methods, per-arm results, statistics, configurations, limitations and links to supplementary run records. HTML provides a readable and printable report. Browser Print → Save as PDF produces a review copy.
- **Reusable tables:** `all_runs.csv`, `world_means.csv`, `all_arm_statistics.csv`, `planned_contrasts.csv`, `interventions.csv`, and `benchmark_audit.csv`. Benchmark tables preserve full optimization details as a JSON field; intervention tables preserve raw events and window denominators.
- **Provenance:** input checksums, numerical-library versions, model hashes, report-code hash, report version, timestamp, contrast definitions, bootstrap settings and the exact input directory in `report_manifest.json`.
- **Coverage:** expected/completed/missing/unexpected jobs, invalid records, incomplete directories and the suite failure log in `coverage_audit.json`. Completion markers must match their manifests, period sequences must be complete, and mixed model hashes are rejected. Checksums make the input snapshot auditable; they are not a formal proof of model correctness.

Run appendices contain all scalar period records. Original JSONL/Parquet files remain the authoritative source for the full nested, per-function diagnostics. Within-period execution samples exist only for simulations originally run with `--log-executions`; reporting cannot reconstruct samples that were not saved.

## Statistical conventions

Research-report intervals are **95% percentile bootstrap intervals over independent world means**, using 4,000 resamples and seed 4104. Nested replicas are averaged within world before computing the study mean, so worlds with extra replicas do not receive extra weight. The older overview dashboard retains its explicitly labeled 90% intervals; use the research bundle consistently for manuscript tables.

Every statistic reports the number of worlds with usable values, total worlds, number of runs, missing-run count, mean, median, standard deviation, range and interval. A single world has no interval. Fewer than ten worlds are explicitly treated as exploratory; even larger samples require assessing the world-generating design.

Null settling times are not replaced by the horizon or zero. Their mean is conditional on observed settling; report `settling_observed` alongside it. Missing fit-error metrics mean no eligible observations, not zero error. Intervals are exploratory and are not adjusted for testing many outcomes. No automatic p-values or significance claims are generated.

Partial results can be biased by outcome-dependent failures or missing nested replicas. Inspect coverage before interpreting aggregates. Unequal horizons and world changes make some comparisons inappropriate even when an arithmetic difference can be calculated. Raw Y can exceed a feasible benchmark through overload; present penalized reward and feasibility alongside efficiency claims.

## Specify scientific comparisons explicitly

Supply a JSON list with `family`, `reference`, `treatment` and `metric`:

```json
[
  {
    "family": "E7",
    "reference": "fixed",
    "treatment": "adaptive_exact",
    "metric": "tail_mean_reward"
  }
]
```

The bundled `configs/v04/research-contrasts.json` provides five suggested mechanism comparisons. These are proposed comparisons, not a claim of preregistration. Select and freeze primary contrasts before a confirmatory study. A smoke suite may omit an arm; such a contrast is reported as not estimable instead of being substituted with another control.

```bash
.venv/bin/python -m rsi_game.v04 suite --preset pilot --families E7 --workers 2 --output results/v04/e7-pilot --contrasts configs/v04/research-contrasts.json
```

Contrasts are treatment-minus-reference differences within shared world seeds after nested-replica averaging. The table includes matched counts, usable pairs, changed configuration fields and a 95% interval. Seed matching alone does not guarantee a causal design. Multiple changed fields imply a combined intervention; the report lists them rather than attributing the difference to one factor. No arbitrary lexical reference is used in the research bundle. The older dashboard's lexical contrasts remain descriptive only.

## Integrating the bundle into a paper

1. Freeze the model, study plan, primary outcomes, comparison definitions, stopping rules and world population. Record any calibration separately from held-out evaluation.
2. Complete the intended study and inspect the coverage audit, failed jobs, benchmark residuals, identification assumptions and feasibility diagnostics.
3. Use the generated methods and results text as an editable draft. Import CSV tables and SVG figures into the manuscript, preserving denominators, units, horizons and uncertainty definitions.
4. Link empirical claims to run IDs and the report manifest. Archive the bundle with source data and code revision. Include all arms and unsuccessful runs in supplementary material.
5. Add the theoretical argument, substantive interpretation, related literature and any confirmatory statistical analysis. The generated report intentionally does not invent causal explanations, prove cycles from finite trajectories, or claim a manuscript is publication-ready without scientific review.

The delivered smoke report and four worked-example appendices demonstrate the complete reporting pipeline. They are preliminary results. The prepared full study has not been run; its report will be generated from actual results after execution.
