#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
preset="${1:-paper}"
workers="${2:-2}"
case "$preset" in smoke|pilot|paper|full) ;; *) echo 'Preset must be smoke, pilot, paper or full'; exit 2;; esac
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python_bin="$PWD/.venv/bin/python"
base="results/v05/$preset"
mkdir -p "$base/plans" "$base/_matplotlib"
export MPLCONFIGDIR="$PWD/$base/_matplotlib"
run_study() {
  local study="$1"
  shift
  "$python_bin" -m rsi_game.v05 plan --study "$study" --preset "$preset" --output "$base/plans/$study.json" "$@"
  "$python_bin" -m rsi_game.v05 suite --plan "$base/plans/$study.json" --output "$base/$study" --workers "$workers"
}
run_study examples
run_study tuning
"$python_bin" -m rsi_game.v05 select --input "$base/tuning" --output "$base/selection.json"
run_study core
run_study typology --selection "$base/selection.json"
"$python_bin" -m rsi_game.v05 typology-analysis --input "$base/typology"
run_study broad --selection "$base/selection.json"
"$python_bin" -m rsi_game.v05 typology-analysis --input "$base/broad"
run_study long --selection "$base/selection.json"
run_study structural
"$python_bin" -m rsi_game.v05 select-structural --input "$base/structural" --output "$base/structural-selection.json"
run_study structural-test --selection "$base/structural-selection.json"
# More expensive robustness stages are explicit, rather than hidden in a launch.
if [[ "${3:-}" == "--extended" ]]; then
  run_study stability
  run_study continuation
  "$python_bin" -m rsi_game.v05 typology-analysis --input "$base/continuation"
fi
printf 'Reports saved beneath %s/%s/<study>/research/research_report.html\n' "$PWD" "$base"
