#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="${PYTHON:-python3}"

echo "[1/2] Reproduce all figures"
bash scripts/reproduce_all_figures.sh

echo "[2/2] Export supplementary tables"
"${PYTHON_BIN}" scripts/export_supplementary_tables.py \
  --data-dir data \
  --extended-dir data/extended \
  --out-dir tables

echo "Done. Regenerated figures are in figs/ and tables are in tables/."

