"""P2: Scale strength sweep — TPR@1%FPR vs |alpha-1| (720-pool, dual-device).

From real candidate H_B:  H_attack = alpha * H_B.
alpha in {0.90,0.95,0.98,0.99,1.01,1.02,1.05,1.10}.
For each detector (scalar16, projcos4, signradial, combined), thresholds are
the same joint-calibrated ones from the P0 main-table script (calibration 200
benign, alpha_FPR = 1%). Report TPR@1%FPR per |alpha-1| and save a plot.

Theory:
  - ProjCos: cos(H_A R, alpha H_B R) = cos(H_A R, H_B R) -> TPR ~ FPR (flat ~1%)
  - SignRadial: coherent radial signal |alpha-1| -> TPR rises monotonically
  - Combined: max of the two -> flat-to-high, covers both
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

from run_p0_main_table_720 import (
    load_split, score_of, combo_score_factory, DETECTORS,
    apply_attack, wilson95, ROOT, STACKS, CHECKPOINTS, _ck,
)
from attacks import inject_scale

ALPHAS = [0.90, 0.95, 0.98, 0.99, 1.01, 1.02, 1.05, 1.10]
ALPHA_FPR = 0.01


def main() -> None:
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)

    stack_a = load_split("A", "all")
    stack_b = load_split("B", "all")
    prompts_path = Path("/Users/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl")
    pid2split = {}
    for line in open(prompts_path):
        p = json.loads(line)
        pid2split[p["prompt_id"]] = p["split"]
    calib_ids = sorted(pid for pid in stack_a if pid2split.get(pid) == "calibration" and pid in stack_b)
    eval_ids = sorted(pid for pid in stack_a if pid2split.get(pid) == "evaluation" and pid in stack_b)
    print(f"calib={len(calib_ids)} eval={len(eval_ids)}")
    seed = 2026

    left_calib = {p: stack_a[p] for p in calib_ids}
    right_calib = {p: stack_b[p] for p in calib_ids}
    left_eval = {p: stack_a[p] for p in eval_ids}
    right_eval = {p: stack_b[p] for p in eval_ids}

    # ---- thresholds (same protocol as P0) ----
    calib_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        calib_honest[det] = np.array([score_of(det, right_calib[p], left_calib[p], seed) for p in calib_ids])
    fP, fR, combo_score = combo_score_factory(calib_honest)
    calib_honest["combined"] = np.array([combo_score(right_calib[p], left_calib[p]) for p in calib_ids])
    tau = {det: float(np.quantile(calib_honest[det], 1.0 - ALPHA_FPR)) for det in DETECTORS}

    # eval honest for FPR check
    eval_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        eval_honest[det] = np.array([score_of(det, right_eval[p], left_eval[p], seed) for p in eval_ids])
    eval_honest["combined"] = np.array([combo_score(right_eval[p], left_eval[p]) for p in eval_ids])

    print("\n=== scale sweep: TPR@1%FPR vs |alpha-1| ===")
    print(f"{'alpha':>6s} {'|a-1|':>6s} " + " ".join(f"{d:>12s}" for d in DETECTORS))
    rows = []
    for alpha in ALPHAS:
        eps = alpha - 1.0
        row = {"alpha": alpha, "abs_delta": abs(alpha - 1.0)}
        vals = []
        for det in DETECTORS:
            sc = []
            for p in eval_ids:
                cand = inject_scale(right_eval[p], eps, seed)
                s = combo_score(cand, left_eval[p]) if det == "combined" else score_of(det, cand, left_eval[p], seed)
                sc.append(s)
            sc = np.array(sc, dtype=np.float64)
            k = int(np.sum(sc > tau[det]))
            n = len(sc)
            tpr = k / n
            lo, hi = wilson95(k, n)
            row[f"tpr_{det}"] = tpr
            row[f"tpr_{det}_lo"] = lo
            row[f"tpr_{det}_hi"] = hi
            vals.append(tpr)
        rows.append(row)
        print(f"{alpha:6.2f} {abs(alpha-1.0):6.3f} " + " ".join(f"{v:12.4f}" for v in vals))

    # honest FPR per detector (once)
    print("\nhonest eval FPR (should be ~1%):")
    for det in DETECTORS:
        fpr = float(np.mean(eval_honest[det] > tau[det]))
        print(f"  {det:12s} FPR={fpr:.4f}")

    cols = list(rows[0].keys()) if rows else []
    with (out / "p2_scale_sweep.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote results/p2_scale_sweep.csv ({len(rows)} rows)")

    # ---- plot ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        x = [r["abs_delta"] for r in rows]
        fig, ax = plt.subplots(figsize=(8, 5.5))
        colors = {"scalar16": "#C44E52", "projcos4": "#55A868", "signradial": "#4C72B0", "combined": "#111111"}
        for det in DETECTORS:
            y = [r[f"tpr_{det}"] for r in rows]
            lo = [r[f"tpr_{det}_lo"] for r in rows]
            hi = [r[f"tpr_{det}_hi"] for r in rows]
            ax.plot(x, y, "o-", label=det, color=colors[det])
            ax.fill_between(x, lo, hi, color=colors[det], alpha=0.15)
        ax.set_xlabel("|alpha - 1| (scale magnitude)")
        ax.set_ylabel("TPR @ 1% FPR")
        ax.set_title("Scale strength sweep (720-pool, A=MPS/B=CUDA)")
        ax.axhline(0.01, color="gray", ls="--", lw=0.8, label="FPR=1%")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / "p2_scale_sweep.png", dpi=140)
        print(f"wrote results/p2_scale_sweep.png")
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    raise SystemExit(main())
