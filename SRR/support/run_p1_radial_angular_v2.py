"""P1 v2: Radial-Angular controlled perturbation — TPR@1%FPR vs theta.

Fixes the q=64 sampling-noise issue found in v1: at theta=90 the random
orthogonal perturbation does not cancel in only 64 sampled coords (random-walk
std too large), so SignRadial's angular blindness was masked. Here SignRadial
uses q=1024 sampled coords so the angular endpoint reliably cancels.

Expectation (mechanism proof):
  theta ~ 0 (radial):   SignRadial high, ProjCos low (=FPR)
  theta ~ 90 (angular): ProjCos high, SignRadial drops
  Combined high across the whole range

Delta(theta) = rho*||H_B||_F*(cos*r + sin*a), r = H_B/||H_B||, a perp r.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

from run_p0_main_table_720 import (
    load_split, projcos_score, scalar_score, combo_score_factory,
    DETECTORS, wilson95, _ck,
)

THETAS = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]
RHOS = [0.05, 0.10]
SR_Q = 1024
ALPHA_FPR = 0.01


def radial_angular_attack(bundle, rho, theta_deg, seed, checkpoint="C2"):
    t3 = bundle[_ck(checkpoint)].astype(np.float64)
    t = t3[0].reshape(-1)
    norm = float(np.linalg.norm(t))
    r = t / norm
    rng = np.random.default_rng(seed + 12345)
    g = rng.standard_normal(t.shape)
    a = g - float(np.dot(g, r)) * r
    an = float(np.linalg.norm(a))
    a = a / an
    th = math.radians(theta_deg)
    delta_flat = rho * norm * (math.cos(th) * r + math.sin(th) * a)
    out = dict(bundle)
    out[_ck(checkpoint)] = (t3 + delta_flat.reshape(t3.shape)).astype(np.float32)
    return out


def sr_q_score(cand, ref, q, seed, checkpoint="C2"):
    c0 = np.asarray(cand[_ck(checkpoint)], dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref[_ck(checkpoint)], dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    flat = np.random.default_rng(seed).choice(seq * c0.shape[1], size=q, replace=False)
    x = r0.reshape(-1)[flat]
    y = c0.reshape(-1)[flat]
    P = float(np.sum(np.sign(x) * (y - x)))
    B = float(np.sum(np.abs(x)))
    return abs(P) / (B + 1e-12)


def score_of_p1(det, cand, ref, seed):
    """score for P1 (signradial uses q=SR_Q, others same as P0)."""
    if det == "scalar16":
        return max(scalar_score(cand[_ck(c)], ref[_ck(c)], 16, seed) for c in ("C1", "C2", "C3"))
    if det == "projcos4":
        return max(projcos_score(cand[_ck(c)], ref[_ck(c)], 4, seed) for c in ("C1", "C2", "C3"))
    if det == "signradial":
        return max(sr_q_score(cand, ref, SR_Q, seed, checkpoint=c) for c in ("C1", "C2", "C3"))
    raise ValueError(det)


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
    print(f"calib={len(calib_ids)} eval={len(eval_ids)}  SR q={SR_Q}")
    seed = 2026

    left_calib = {p: stack_a[p] for p in calib_ids}
    right_calib = {p: stack_b[p] for p in calib_ids}
    left_eval = {p: stack_a[p] for p in eval_ids}
    right_eval = {p: stack_b[p] for p in eval_ids}

    # ---- thresholds: build per-detector calibration honest using P1 score fns ----
    calib_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        calib_honest[det] = np.array([score_of_p1(det, right_calib[p], left_calib[p], seed) for p in calib_ids])
    # combined: joint-calibrated max-fusion on the SAME P1 scores
    _, _, combo_score = combo_score_factory(calib_honest, seed)
    calib_honest["combined"] = np.array([combo_score(right_calib[p], left_calib[p]) for p in calib_ids])
    tau = {det: float(np.quantile(calib_honest[det], 1.0 - ALPHA_FPR)) for det in DETECTORS}

    # ---- run ----
    rows = []
    for rho in RHOS:
        print(f"\n=== rho = {rho} (SR q={SR_Q}) ===")
        print(f"{'theta':>6s} {'scalar16':>10s} {'projcos4':>10s} {'signradial':>10s} {'combined':>10s}")
        for theta in THETAS:
            row = {"rho": rho, "theta_deg": theta, "sr_q": SR_Q}
            vals = []
            for det in DETECTORS:
                sc = []
                for p in eval_ids:
                    cand = radial_angular_attack(right_eval[p], rho, theta, seed)
                    s = combo_score(cand, left_eval[p]) if det == "combined" else score_of_p1(det, cand, left_eval[p], seed)
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
    with (out / "p1_radial_angular_v2.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nwrote results/p1_radial_angular_v2.csv ({len(rows)} rows)")

    # ---- plot ----
    try:
        import warnings
        warnings.filterwarnings("ignore")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        colors = {"scalar16": "#C44E52", "projcos4": "#55A868", "signradial": "#4C72B0", "combined": "#111111"}
        nrho = len(RHOS)
        fig, axes = plt.subplots(1, nrho, figsize=(6.4 * nrho, 5.4), sharey=True)
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
            ax.set_title(f"rho={rho}, SR q={SR_Q}")
            ax.set_xlabel("theta (deg): radial -> angular")
            ax.set_ylim(-0.02, 1.05)
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
        axes[0].set_ylabel("TPR @ 1% FPR")
        fig.suptitle("Radial-Angular perturbation (720-pool, A=MPS/B=CUDA)")
        fig.tight_layout()
        fig.savefig(out / "p1_radial_angular_v2.png", dpi=140)
        print("wrote results/p1_radial_angular_v2.png")
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    raise SystemExit(main())
