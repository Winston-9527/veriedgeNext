#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="${PYTHON:-python3}"

echo "[1/6] Compute verifier-profile confidence intervals"
"${PYTHON_BIN}" scripts/compute_wilson_ci.py \
  --infile data/verifier_profiles.csv \
  --out data/verifier_profiles_with_ci.csv

echo "[2/6] Materialize placement replay"
"${PYTHON_BIN}" scripts/run_placement_replay.py \
  --profiles data/verifier_profiles.csv \
  --candidates data/placement_candidates.csv \
  --workload data/placement_workload.csv \
  --replay-log data/placement_replay_log.csv \
  --out data/placement_results.csv

echo "[3/6] Summarize placement replay"
"${PYTHON_BIN}" scripts/summarize_placement.py \
  --results data/placement_results.csv \
  --out data/placement_summary.csv

echo "[4/6] Plot placement replay"
"${PYTHON_BIN}" scripts/plot_placement_replay.py \
  --summary data/placement_summary.csv \
  --out figs/fig_placement_replay.pdf

echo "[5/6] Summarize delivery sweep"
"${PYTHON_BIN}" scripts/summarize_delivery.py \
  --runs data/delivery_runs.csv \
  --out data/delivery_summary.csv

echo "[6/6] Plot delivery sweep"
"${PYTHON_BIN}" scripts/plot_delivery_sweep.py \
  --summary data/delivery_summary.csv \
  --out figs/fig_delivery_sweep.pdf

echo "Done. Refreshed outputs are in data/ and figs/."
