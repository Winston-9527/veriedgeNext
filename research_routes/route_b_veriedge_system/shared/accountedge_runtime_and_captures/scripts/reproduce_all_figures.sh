#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="${PYTHON:-python3}"

echo "[1/2] Reproduce core summaries and figures"
bash scripts/reproduce_main_results.sh

echo "[2/2] Reproduce extended figures from included CSVs"
"${PYTHON_BIN}" scripts/plot_extended_figures.py \
  --data-dir data \
  --extended-dir data/extended \
  --out-dir figs

echo "Done. Regenerated figures are in figs/."
