# RSI Functions Game — v0.4

A research implementation of Serge Marquie's revised continuous functions game. Functions learn local quadratic response models from their own settings and the shared aggregate, explore on separate frequencies, and interact through a common resource price. This is a mathematical simulation, not a system that trains or modifies an LLM.

The v0.4 redesign replaces the finite snapshot game as the default app. Its engine lives in `rsi_game/v04/`; the v0.1 engine, results and commands remain available. Read [the review](docs/V04_REVIEW.md), [running instructions](docs/RUN_V04.md), and [experiment protocol](docs/EXPERIMENTS_V04.md).

## Run on this Mac

Open this folder in PyCharm, select **RSI v0.4 - Interactive Lab**, and click Run. Alternatively, run `main.py`. The project interpreter is `.venv/bin/python`. The local browser app opens at http://127.0.0.1:8766.

```bash
.venv/bin/python main.py
```

For a fresh clone, use Python 3.11 or later:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[reports]'
.venv/bin/python main.py
```

## Prepared research

There are **194 arms across E1–E12 and R1–R6**. The full design contains **10,704 distinct runs** after removing deterministic duplicate seeds. It has been prepared, not run in full. Start with the 36-run smoke suite, then selected pilot families; see the protocol before the full study.

```bash
.venv/bin/python -m rsi_game.v04 suite --preset smoke --workers 2 --output results/v04/my-smoke
.venv/bin/python -m rsi_game.v04 report --input results/v04/my-smoke
```

Delivered results are under `results/v04`: 36 smoke runs; four 300-period worked-example runs; a five-world calibration audit; an Example 4.7 numerical global bound; and a finite initial-state basin map. Open `results/v04/smoke/report.html` or `results/v04/examples/report.html` in a browser. JSONL, CSV and Parquet records retain parameters, diagnostics and provenance.

Continuous dynamics cannot be exhaustively enumerated. Nonconcave multi-start solutions are labeled **best found**. Optional branch-and-bound gives an explicit numerical optimality gap. Correct local learning does not guarantee convergence, feasibility, or a team optimum.

## Validation and legacy

```bash
.venv/bin/python -m unittest discover -s tests -v
RSI_FULL_VALIDATION=1 .venv/bin/python -m unittest discover -s tests/v04 -v
.venv/bin/python legacy_main.py
```

The full validation flag expands the best-response check to 1,000 random cases against 100,000-point grids. [Original v0.1 documentation](docs/V01_README.md) describes the preserved finite game; its conclusions do not transfer to v0.4. `python -m rsi_game` remains the legacy CLI; use `python -m rsi_game.v04` for this model.

No license is assigned automatically. The source PDFs are not redistributed in this repository.
