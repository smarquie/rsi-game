# v0.5.1 follow-up validation (October 2)

After the completed v0.4 study: 27 v0.5 tests and 45 preserved legacy/v0.4 tests passed (72 total). The corrected 60-job readiness study completed with a single code identity; all recorded deployments were feasible and every wide-commitment process performed reviews in all 60 learning periods on the readiness worlds. The core paper grid (9,700 jobs) and stability grid (1,200 jobs) passed structural exploration preflight. State-dependent skips remain legitimate outcomes.

See [the completed-study review](audits/v04-completed/REVIEW.md) and [readiness provenance](audits/v04-completed/v051-readiness.json). The earlier validation record below refers to v0.5.0 and is retained as history, not evidence that the old launch grid was scientifically appropriate.

---

# v0.5 validation record

Validated locally with the versions pinned in `requirements-v05-tested.txt`.

- **65 automated tests passed**: 20 v0.5 tests, 27 preserved v0.4 tests and 18 legacy tests.
- The deployment test checks feasibility in **1,000 seeded worlds with infeasible commitment bounds**.
- **46/46 integration jobs completed and passed file-integrity checks**, with one model-code hash. The complete local report is `results/v05/validated/research/research_report.html`.
- **40/40 smoke tuning jobs completed**, remedy selection froze successfully, and the downstream 1,296-job smoke typology plan was prepared. This validates selection plumbing; the smoke-selected remedies are not a research recommendation.
- The editable installation and `rsi-game` entry point were verified. The `rsi-game-v04` entry point and original v0.4 source remain available.
- `bash -n scripts/run_v05.sh` passed.

## Numerical checks

| Quantity | Observed / verified |
|---|---|
| Saddle multiplier | 0.064 |
| Saddle curvature in spending units | 0.064 |
| Saddle two-function gain at radius 0.1 | Within 0.0001 of 0.0015 |
| Activation example | No positive two-function witness at radius 0.6; positive three-function gain above 0.008 at radius 0.1 |
| Interference barrier numerical estimate | 0.6340135 |
| Activation barrier numerical estimate | 0.0359001 |
| Full-frequency coefficient recovery | Absolute tolerance 1e-12 |
| Transfer-channel spending conservation | Tolerance 1e-12 |
| Ordered and Shapley decomposition sums | Tolerance 1e-12 |
| Symmetric price table targets | Tolerance 0.001 |
| Symmetric feedback at alpha=0 | 0.25 for n=5; 1 for n=2 |
| Corner clearing plateau | Selected price 0.15; set-valued flag true |
| Pinned invisible perturbation | Own-learning records agree within numerical tolerance |
| New-function paired design | Identical pre-learning state and deployment in both edited arms |

The barrier numbers are numerical search estimates, not global impossibility certificates. Tests of exact example structure are separate from held-out empirical hypotheses.

## Reproduce

```bash
.venv/bin/python -m unittest discover -s tests/v05 -v
.venv/bin/python -m unittest discover -s tests/v04 -v
.venv/bin/python -m unittest discover -s tests -p test_model.py -v
.venv/bin/python -m rsi_game.v05 suite --plan configs/v05/validation-plan.json --output results/v05/revalidation --workers 2
```

The machine-readable provenance is in `v05-validation-manifest.json`. Full publication-scale experiments have **not** been run. Integration tests do not establish the empirical hypotheses or every T1–T34 statement in the draft. See `V05_FIDELITY.md` before assigning a theoretical interpretation to the output.
