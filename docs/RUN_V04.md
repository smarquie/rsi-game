# Running v0.4 on your Mac

## 1. Open the existing PyCharm project

Project folder:

```text
/Users/sergemarquie/Documents/Codex/2026-10-01/wha/outputs/rsi-game
```

In PyCharm use File → Open and select that folder. Select **RSI v0.4 - Interactive Lab** and click the green Run button, or open `main.py` and run it. Shared run configurations point to this project's `.venv/bin/python`. If prompted for an interpreter, select that existing file.

The app opens at **http://127.0.0.1:8766**. Choose world structure, explorers, damping, width and price regime; click **Run v0.4 simulation**. Switch the chart between aggregate, settings and price/overload. Download JSON to keep a browser run. The app uses 16 benchmark starts for responsiveness; use the command-line experiments for research output. Runs are local and require no API key.

The prepared smoke report is linked from the app. You can also open `results/v04/smoke/report.html` and `results/v04/examples/report.html` directly in a browser, without a server.

## 2. Open PyCharm's Terminal

Use this working directory for every command below:

```bash
cd /Users/sergemarquie/Documents/Codex/2026-10-01/wha/outputs/rsi-game
```

The commands specify the interpreter, so activating the virtual environment is optional. Keep the Mac awake and plugged in during long studies. Two workers are the conservative default; increasing workers can increase memory use and does not guarantee proportional speedup.

## 3. Reproduce a small end-to-end study

```bash
.venv/bin/python -m rsi_game.v04 suite --preset smoke --workers 2 --output results/v04/my-smoke
.venv/bin/python -m rsi_game.v04 report --input results/v04/my-smoke
open results/v04/my-smoke/report.html
```

This runs 36 jobs, spanning all 18 families, with 12 review periods and 8 benchmark starts. It validates the research pipeline; it is too short and has too few worlds for inference. The **RSI v0.4 - Smoke suite** PyCharm run configuration starts the same suite.

## 4. Run focused pilots before the full study

Start by inspecting the design; `plan` does not run simulations:

```bash
.venv/bin/python -m rsi_game.v04 plan --preset pilot --families E1 E4 E7 R2 R3 R4 R5 R6 --output results/v04/mechanism-plan.json
.venv/bin/python -m rsi_game.v04 suite --preset pilot --families E1 E4 E7 R2 R3 R4 R5 R6 --workers 2 --output results/v04/mechanism-pilot
.venv/bin/python -m rsi_game.v04 report --input results/v04/mechanism-pilot
```

Pilot defaults are five worlds, one replica, 100 periods and 32 optimization starts. The entire pilot would be 954 jobs and about 17.85 million model executions, excluding optimizer work. Use `--families E7` to begin more narrowly or `--max-jobs 4` to estimate runtime; removing that cap later resumes the same study. A capped run is marked partial.

For one configurable trajectory:

```bash
.venv/bin/python -m rsi_game.v04 simulate --config configs/v04/default.json --periods 100 --multistarts 32 --output results/v04/my-run --log-executions
.venv/bin/python -m rsi_game.v04 report --input results/v04/my-run
```

Copy `configs/v04/default.json` before editing. The `world` block controls the physical environment; `config` controls the learning process. Use separate output folders for changed configurations. `--log-executions` saves all within-period samples and can substantially increase disk usage; period-level records are saved automatically.

## 5. Run calibration and controlled checks

```bash
.venv/bin/python -m rsi_game.v04 calibrate --worlds 50 --multistarts 300 --output results/v04/calibration-full.json
.venv/bin/python -m rsi_game.v04 benchmark --scenario example2 --multistarts 300 --certify --max-boxes 5000 --output results/v04/my-certificate.json
.venv/bin/python -m rsi_game.v04 basins --mode fixed_low --resolution 21 --periods 150 --output results/v04/my-basin-low.json
.venv/bin/python -m rsi_game.v04 basins --mode fixed_high --resolution 21 --periods 150 --output results/v04/my-basin-high.json
.venv/bin/python -m rsi_game.v04 basins --mode learning --resolution 21 --periods 300 --output results/v04/my-basin-learning.json
```

Basin commands also save SVG/PNG figures when matplotlib is installed. They cover feasible grid starts only. Colors show the nearest candidate, not a proof of attraction; inspect final distances, settings and spending. Fixed-multiplier paths can leave the physical budget set. The learning basin computation is substantially more expensive.

## 6. Launch the full design when the mechanism is settled

```bash
.venv/bin/python -m rsi_game.v04 plan --preset full --output results/v04/full-plan.json
.venv/bin/python -m rsi_game.v04 suite --preset full --workers 2 --output results/v04/full
.venv/bin/python -m rsi_game.v04 report --input results/v04/full
```

Full defaults: 50 worlds, up to four nested replicas, 300 review periods and 300 benchmark starts. This is **194 arms, 10,704 distinct jobs and 599,066,768 model executions**, plus optimization and oracle comparisons. It is a substantial computation. Measure a representative pilot for each regime before estimating elapsed time; adaptive periods and harder optimizations have different costs. The full study has not been launched automatically.

Repeating an identical suite command resumes completed runs. Changed model code or parameters are rejected in the same run directory; prefer a new output directory. `--overwrite` explicitly replaces existing run outputs. Ctrl-C cancels queued work; already active workers can take time to finish. Completed runs are durable, and incomplete runs with the same identity restart when resumed. Reports include completed runs only.

## 7. Read the outputs correctly

The suite now automatically builds the dashboard and an extensive research bundle under `research/`. Open `research/research_report.html` for complete coverage of all runs, detailed analysis, and reusable manuscript text/tables/figures. See [Research reporting](RESEARCH_REPORTING.md). Use `--contrasts configs/v04/research-contrasts.json` to request the suggested explicit comparisons; use `--no-report` to defer reporting.

- `plan.json`: exact jobs, counts and design warnings.
- `suite_summary.json`: completed/failing jobs, runtime and partial-run flag.
- Per run: `manifest.json` (world, seeds, model hash and versions), `periods.jsonl`, scalar `periods.csv`, `summary.json`, `benchmarks.json`, `complete.json`; optional detailed `executions.jsonl`.
- Parquet files are also written if pyarrow is installed. Nested fields are JSON strings.
- `report.html`: portable interactive report, all-arm aggregate statistics, up to 96 representative trajectories.
- `aggregate.csv`, `run_summary.csv`, `paired_contrasts.json`: machine-readable comparisons; up to twelve representative SVG/PNG figures in `figures/`.

Compare reward, overload and feasibility before treating a high aggregate as success. A null settling period means the required 20-period stable suffix was not observed. A stable aggregate alone does not imply stable settings. Bootstrap intervals use independent worlds, after averaging nested replicas. One-world smoke results have no uncertainty interval. The automatically generated contrasts use the first arm in lexical order as a descriptive reference; choose scientific controls explicitly for publication.

## Tests and installation

```bash
.venv/bin/python -m unittest discover -s tests -v
RSI_FULL_VALIDATION=1 .venv/bin/python -m unittest discover -s tests/v04 -v
```

For another computer, clone the repository, create a Python 3.11+ virtual environment and install `pip install -e '.[reports]'`. `requirements-v04-tested.txt` records the direct numerical/reporting package versions tested on this Mac. Per-run manifests record actual versions. The old app runs through `legacy_main.py` on port 8765; old commands use `python -m rsi_game`. New commands always include `.v04`.
