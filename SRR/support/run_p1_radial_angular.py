"""P1: Radial-Angular controlled perturbation — TPR@1%FPR vs theta.

For real benign pair (H_A, H_B), attack from H_B:
    r = H_B / ||H_B||_F
    a = (g - <g,r>r) / ||g - <g,r>r||_F      (g random, a ⟂ r)
    Delta(theta) = rho * ||H_B||_F * (cos(theta)*r + sin(theta)*a)
    H_attack = H_B + Delta(theta)
theta in {0,15,30,45,60,75,90} deg. All attacks have the SAME relative-L2
magnitude rho; only the radial-vs-angular mix changes.

Expectation:
  - theta ~ 0 (radial): SignRadial strong, ProjCos weak
  - theta ~ 90 (angular): ProjCos strong, SignRadial drops
  - Combined high across the whole range

rho is swept (0.05 / 0.10 / 0.20) to show the transition clearly.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

from run_p0_main_table_720 import (
    load_split, score_of, combo_score_factory, DETECTORS,
    wilson95, CHECKPOINTS, _ck,
)

THETAS = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]
RHOS = [0.05, 0.10, 0.20]
ALPHA_FPR = 0.01


def radial_angular_attack(bundle, rho, theta_deg, seed, checkpoint="C2"):
    """H_attack = H_B + rho*||H_B||_F*(cos*r + sin*a), r radial, a ⟂ r."""
    t3 = bundle[_ck(checkpoint)].astype(np.float64)          # [1, T, D]
    t = t3[0].reshape(-1)                                     # [T*D]
    norm = float(np.linalg.norm(t))
    if norm < 1e-12:
        raise ValueError("zero-norm reference")
    r = t / norm
    rng = np.random.default_rng(seed + 12345)
    g = rng.standard_normal(t.shape)
    a = g - float(np.dot(g, r)) * r
    an = float(np.linalg.norm(a))
    if an < 1e-12:
        a = rng.standard_normal(t.shape)
        a -= float(np.dot(a, r)) * r
        an = float(np.linalg.norm(a))
    a = a / an
    th = math.radians(theta_deg)
    delta_flat = rho * norm * (math.cos(th) * r + math.sin(th) * a)
    delta3 = delta_flat.reshape(t3.shape)                     # [1, T, D]
    out = dict(bundle)
    out[_ck(checkpoint)] = (t3 + delta3).astype(np.float32)
    return out


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

    # ---- thresholds ----
    calib_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        calib_honest[det] = np.array([score_of(det, right_calib[p], left_calib[p], seed) for p in calib_ids])
    _, _, combo_score = combo_score_factory(calib_honest, seed)
    calib_honest["combined"] = np.array([combo_score(right_calib[p], left_calib[p]) for p in calib_ids])
    tau = {det: float(np.quantile(calib_honest[det], 1.0 - ALPHA_FPR)) for det in DETECTORS}

    # ---- run ----
    rows = []
    for rho in RHOS:
        print(f"\n=== rho = {rho} ===")
        print(f"{'theta':>6s} {'scalar16':>10s} {'projcos4':>10s} {'signradial':>10s} {'combined':>10s}")
        for theta in THETAS:
            row = {"rho": rho, "theta_deg": theta}
            vals = []
            for det in DETECTORS:
                sc = []
                for idx, p in enumerate(eval_ids):
                    cand = radial_angular_attack(right_eval[p], rho, theta, seed)
                    s = combo_score(cand, left_eval[p]) if det == "combined" else score_of(det, cand, left_eval[p], seed)
                    sc.append(s)
                sc = np.array(sc, dtype=np.float64)
                k = int(np.sum(sc > tau[det]))
                tpr = k / len(sc)
                lo, hi = wilson95(k, len(sc))
                row[f"tpr_{det}"] = tpr
                row[f"tpr_{det}_lo"] = lo
                row[f"tpr_{det}_hi"] = hi
                vals.append(tpr)
            rows.append(row)
            print(f"{theta:6.1f} " + " ".join(f"{v:10.4f}" for v in vals))

    cols = list(rows[0].keys())
    with (out / "p1_radial_angular.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nwrote results/p1_radial_angular.csv ({len(rows)} rows)")

    # ---- plot ----
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        colors = {"scalar16": "#C44E52", "projcos4": "#55A868", "signradial": "#4C72B0", "combined": "#111111"}
        nrho = len(RHOS)
        fig, axes = plt.subplots(1, nrho, figsize=(6.2 * nrho, 5.2), sharey=True)
        if nrho == 1:
            axes = [axes]
        for ax, rho in zip(axes, RHOS):
            sub = [r for r in rows if r["rho"] == rho]
            x = [r["theta_deg"] for r in sub]
            for det in DETECTORS:
                y = [r[f"tpr_{det}"] for r in sub]
                lo = [r[f"tpr_{det}_lo"] for r in sub]
                hi = [r[f"tpr_{det}_hi"] for r in sub]
                ax.plot(x, y, "o-", label=det, color=colors[det])
                ax.fill_between(x, lo, hi, color=colors[det], alpha=0.15)
            ax.axhline(0.01, color="gray", ls="--", lw=0.8, label="FPR=1%")
            ax.set_title(f"rho = {rho}")
            ax.set_xlabel("theta (deg): radial -> angular")
            ax.set_ylim(-0.02, 1.05)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        axes[0].set_ylabel("TPR @ 1% FPR")
        fig.suptitle("Radial-Angular perturbation (720-pool, A=MPS/B=CUDA)")
        fig.tight_layout()
        fig.savefig(out / "p1_radial_angular.png", dpi=140)
        print("wrote results/p1_radial_angular.png")
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    raise SystemExit(main())
