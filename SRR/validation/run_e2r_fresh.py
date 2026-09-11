"""E2-R fresh-P protocol validation: does commit-then-challenge with per-request
fresh P/Omega eliminate the constructible joint-null blind spot?

Protocol change under test (system-design feedback from E2-R):
  OLD: verifier checks coordinates/projection P fixed BEFORE execution; attacker
       who knows P constructs e in ker(P) ∩ ker(SR_Omega) exactly -> joint-null
       structural blind spot (TPR ≈ FPR at ALL rho).
  NEW (commit-to-seed + reveal, per audit): the attacker commits the FULL
       tampered activation FIRST; the verifier generates a random seed_s per
       request, commits C = Commit(seed_s), and only REVEALS seed_s after the
       activation is committed. Anyone can then re-derive P_s/Omega_s from the
       public seed_s and re-verify (public verifiability). For a fixed e != 0,
       Pr[e·P = 0] = 0 (continuous random matrix, a.e.) -> the exact joint-null
       construction is no longer possible because the attacker does not know
       seed_s at commit time (temporal secret). Residual evasion is only
       tolerance (e too small to exceed the threshold).

Isolation: SAME attack constructions (attacker uses a fixed guessed seed),
only the VERIFIER detection seed changes — fixed (2026) vs per-request random
seed_s (recorded in the manifest = reveal semantics; the attacker cannot know
it before committing e).

AUDIT FIX (P0): the per-request random seed policy makes the honest score
distribution unstable across pids — calib's Q_{0.99} over-truncates eval
(FPR 2.7% vs nominal 1%). This script therefore uses **eval-anchored**
thresholds: tau_D = Q_{0.99}(eval honest score for detector D) under EACH
policy, so BOTH fresh and fixed sides are compared at exactly 1% FPR.
(Test-set calibration is acceptable for protocol comparison; noted as a
limitation.)

Pure numpy, local: C3 injection needs no propagation and no CUDA model.

Usage:
    python3 run_e2r_fresh.py --root ... --prompts ... --out results/e2r_fresh
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import (VERIFIER_SEED, BOUNDARIES, DETECTORS, FAMILIES, RHOS,
                        ALPHA, DELTA, SR_Q, PROJ_K, _ck,
                        load_stack, load_splits, sr_score, projcos_score,
                        smoothed_ecdf)
from e2r_attacks import construct

MASTER = 20260810  # master secret for per-request seeds; secret to attacker pre-reveal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--guess-seed", type=int, default=VERIFIER_SEED,
                    help="attacker's fixed guessed seed (assumes the verifier uses this)")
    ap.add_argument("--max-eval", type=int, default=0)
    args = ap.parse_args()
    OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)

    stack_a = load_stack(Path(args.root), "stack_a_720")
    stack_b = load_stack(Path(args.root), "stack_b_720")
    p2s = load_splits(Path(args.prompts))
    calib = sorted(p for p in stack_a if p2s.get(p) == "calibration" and p in stack_b)
    eval_ids = sorted(p for p in stack_a if p2s.get(p) == "evaluation" and p in stack_b)
    if args.max_eval:
        eval_ids = eval_ids[: args.max_eval]
    print(f"calib={len(calib)} eval={len(eval_ids)} guess_seed={args.guess_seed}")

    rng = np.random.default_rng(MASTER)
    seed_map = {pid: int(rng.integers(0, 2**32)) for pid in calib + eval_ids}

    def trace_scores(ids, seed_fn):
        """Per-prompt trace-max SR/PC (+combined via ECDF below) under seed_fn."""
        sr, pc = [], []
        for pid in ids:
            s = seed_fn(pid)
            a, b = stack_a[pid], stack_b[pid]
            sr.append(max(sr_score(b[_ck(k)], a[_ck(k)], SR_Q, s) for k in BOUNDARIES))
            pc.append(max(projcos_score(b[_ck(k)], a[_ck(k)], PROJ_K, s) for k in BOUNDARIES))
        return np.array(sr), np.array(pc)

    # ---- fresh policy: ECDFs from calib TRACE-MAX scores (main-protocol fusion) ----
    cal_tr_sr, cal_tr_pc = trace_scores(calib, lambda p: seed_map[p])
    u_tr_sr = smoothed_ecdf(cal_tr_sr)
    u_tr_pc = smoothed_ecdf(cal_tr_pc)

    # Combined threshold: eval-anchoring saturates at the ECDF ceiling n/(n+1)~0.995
    # (honest combo Q_{0.99} lands at the ceiling). Use the calib-based threshold
    # (main-protocol style) for Combined and report its ACTUAL eval FPR.
    cal_tr_combo = np.array([max(u_tr_sr(s), u_tr_pc(p)) for s, p in zip(cal_tr_sr, cal_tr_pc)])

    # fresh eval honest (trace-max SR/PC) -> eval-anchored thresholds per detector
    f_sr, f_pc = trace_scores(eval_ids, lambda p: seed_map[p])
    f_combo = np.array([max(u_tr_sr(f_sr[i]), u_tr_pc(f_pc[i])) for i in range(len(eval_ids))])
    tau_fresh = {"SignRadial": float(np.quantile(f_sr, 1 - ALPHA)),
                 "ProjCos4": float(np.quantile(f_pc, 1 - ALPHA)),
                 "Combined": float(np.quantile(cal_tr_combo, 1 - ALPHA))}
    print(f"fresh thresholds: SR/PC eval-anchored={ {k: round(v, 5) for k, v in tau_fresh.items() if k!='Combined'} }, "
          f"Combined calib-based={tau_fresh['Combined']:.4f} (ECDF ceiling ~{200/201:.4f})")

    # per-boundary calib (for tol_hug construction calibration)
    cal_sr = {b: [] for b in BOUNDARIES}
    cal_pc = {b: [] for b in BOUNDARIES}
    for pid in calib:
        s = seed_map[pid]
        for b in BOUNDARIES:
            cal_sr[b].append(sr_score(stack_b[pid][_ck(b)], stack_a[pid][_ck(b)], SR_Q, s))
            cal_pc[b].append(projcos_score(stack_b[pid][_ck(b)], stack_a[pid][_ck(b)], PROJ_K, s))
    cal_sr = {b: np.array(v) for b, v in cal_sr.items()}
    cal_pc = {b: np.array(v) for b, v in cal_pc.items()}
    u_sr = {b: smoothed_ecdf(cal_sr[b]) for b in BOUNDARIES}
    u_pc = {b: smoothed_ecdf(cal_pc[b]) for b in BOUNDARIES}

    # ---- fixed policy: eval-anchored thresholds from main detail honest rows ----
    detail = OUT.parent / "e2r" / "e2r_per_prompt_detail.csv.gz"
    fixed_honest = {d: [] for d in DETECTORS}
    fixed_attack = {}  # (fam, rho, det) -> list of trace-max attack scores (C3, TM2)
    if detail.is_file():
        import gzip
        with gzip.open(detail, "rt") as fh:
            for r in csv.DictReader(fh):
                tr = max(float(r[f"s_{b}"]) for b in BOUNDARIES)
                if r["family"] == "honest":
                    fixed_honest[r["detector"]].append(tr)
                elif r["tm"] == "TM2_seed_known" and r["kstar"] == "C3":
                    key = (r["family"], r["rho"], r["detector"])
                    fixed_attack.setdefault(key, []).append(tr)
    tau_fixed = {d: float(np.quantile(np.array(fixed_honest[d]), 1 - ALPHA))
                 for d in DETECTORS}
    # Combined: use the main protocol's calib-based tau_Combo (eval-anchoring
    # saturates at the ECDF ceiling for the fused channel)
    main_mani = OUT.parent / "e2r" / "e2r_manifest.json"
    if main_mani.is_file():
        tau_fixed["Combined"] = float(json.load(open(main_mani))["tau_trace"]["Combined"])
    print(f"fixed thresholds: SR/PC eval-anchored={ {k: round(v, 5) for k, v in tau_fixed.items() if k!='Combined'} }, "
          f"Combined main-protocol={tau_fixed['Combined']:.4f}")

    # ---- attack construction (attacker's guessed seed) ----
    AG = args.guess_seed
    cand_C3 = {}
    for fam in FAMILIES:
        cand_C3[fam] = {}
        for rho in RHOS:
            cand_C3[fam][rho] = {}
            for i, pid in enumerate(eval_ids):
                x1 = stack_a[pid][_ck("C3")]
                x = x1[0].astype(np.float64); b = stack_b[pid][_ck("C3")][0].astype(np.float64)
                bnorm = np.linalg.norm(b)
                g = np.random.default_rng(i).normal(0, 1, x.shape).astype(np.float64)
                if fam == "tol_hug_sr":
                    sf = lambda c1: sr_score(c1, x1, SR_Q, AG)
                    tgt = float(np.quantile(cal_sr["C3"], 1 - ALPHA))
                elif fam == "tol_hug_projcos":
                    sf = lambda c1: projcos_score(c1, x1, PROJ_K, AG)
                    tgt = float(np.quantile(cal_pc["C3"], 1 - ALPHA))
                elif fam == "tol_hug_combined":
                    def sf(c1, _AG=AG, _x=x1):
                        s = sr_score(c1, _x, SR_Q, _AG)
                        p = projcos_score(c1, _x, PROJ_K, _AG)
                        return max(u_sr["C3"](s), u_pc["C3"](p))
                    cal_combo_c3 = np.array([max(u_sr["C3"](s), u_pc["C3"](p))
                                             for s, p in zip(cal_sr["C3"], cal_pc["C3"])])
                    tgt = float(np.quantile(cal_combo_c3, 1 - ALPHA))
                else:
                    sf = tgt = None
                e, _ = construct(fam, g, x, b, AG, rho, bnorm, score_fn=sf, target=tgt)
                cand_C3[fam][rho][pid] = (b + e)[None].astype(np.float32)

    # ---- fresh attack detection (trace-max under fresh seed) ----
    def attack_trace_fresh(pid, fam, rho):
        s = seed_map[pid]
        cand = dict(stack_b[pid]); cand[_ck("C3")] = cand_C3[fam][rho][pid]
        a = stack_a[pid]
        sr = max(sr_score(cand[_ck(k)], a[_ck(k)], SR_Q, s) for k in BOUNDARIES)
        pc = max(projcos_score(cand[_ck(k)], a[_ck(k)], PROJ_K, s) for k in BOUNDARIES)
        combo = max(u_tr_sr(sr), u_tr_pc(pc))
        return {"SignRadial": sr, "ProjCos4": pc, "Combined": combo}

    n = len(eval_ids)
    fresh_tpr = {}
    for fam in FAMILIES:
        for rho in RHOS:
            hits = {d: 0 for d in DETECTORS}
            for pid in eval_ids:
                sc = attack_trace_fresh(pid, fam, rho)
                for d in DETECTORS:
                    hits[d] += int(sc[d] > tau_fresh[d])
            fresh_tpr[(fam, rho)] = {d: hits[d] / n for d in DETECTORS}

    # ---- fixed TPR (eval-anchored, from detail) ----
    fixed_tpr = {}
    for (fam, rho, det), sc in fixed_attack.items():
        fixed_tpr.setdefault((fam, float(rho)), {})[det] = \
            float(np.mean(np.array(sc) > tau_fixed[det]))

    # ---- honest FPR under each policy (eval-anchored => ~1%) ----
    fresh_fpr = {d: float(np.mean(f_sr > tau_fresh["SignRadial"])) if d == "SignRadial" else
                 (float(np.mean(f_pc > tau_fresh["ProjCos4"])) if d == "ProjCos4" else
                  float(np.mean(f_combo > tau_fresh["Combined"]))) for d in DETECTORS}
    fixed_fpr = {d: float(np.mean(np.array(fixed_honest[d]) > tau_fixed[d]))
                 for d in DETECTORS}

    print("\n=== fresh-P (commit-reveal) vs fixed-P — TPR@统一 1% FPR (eval-anchored), C3 ===")
    print(f"eval FPR: fresh { {k: round(v, 4) for k, v in fresh_fpr.items()} } | "
          f"fixed { {k: round(v, 4) for k, v in fixed_fpr.items()} }")
    print(f"{'family':22s} {'rho':>5s} | {'SR fixed→fresh':>15s} | {'PC fixed→fresh':>15s} | {'Combo fixed→fresh':>18s}")
    out_rows = []
    for fam in FAMILIES:
        for rho in RHOS:
            fs = fresh_tpr[(fam, rho)]
            fx = fixed_tpr.get((fam, rho), {})
            row = {"family": fam, "rho": rho}
            cell = []
            for d in DETECTORS:
                ff = fx.get(d, float("nan")); fr = fs[d]
                row[d] = fr; row[f"{d}_fixed"] = ff
                cell.append(f"{ff:.3f}→{fr:.3f}")
            print(f"{fam:22s} {rho:>5} | {' | '.join(cell)}")
            out_rows.append(row)

    with open(OUT / "e2r_fresh_vs_fixed.csv", "w") as fh:
        w = csv.DictWriter(fh, fieldnames=["family", "rho"] +
                           [f"{d}" for d in DETECTORS] +
                           [f"{d}_fixed" for d in DETECTORS])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    json.dump({
        "guess_seed": AG,
        "mechanism": "commit-to-seed + reveal: verifier commits C=Commit(seed_s) per "
                     "request, attacker commits e first (cannot know seed_s), then "
                     "verifier reveals seed_s; anyone re-derives P_s/Omega_s and "
                     "re-verifies. seed_s = temporal secret (per-request random), "
                     "revealed below.",
        "master": MASTER,
        "seed_reveal": {str(k): v for k, v in seed_map.items()},
        "threshold_policy": "eval-anchored Q_{0.99} per policy (P0 audit fix): "
                            "per-request random seeds destabilize calib's Q0.99; "
                            "using eval honest Q0.99 fixes FPR to ~1% for both sides. "
                            "Test-set calibration acceptable for protocol comparison.",
        "fpr_fresh": fresh_fpr, "fpr_fixed": fixed_fpr,
        "tau_fresh": tau_fresh, "tau_fixed": tau_fixed,
        "n_eval": n,
        "tpr_fresh": {f"{k[0]}|{k[1]}": v for k, v in fresh_tpr.items()},
    }, open(OUT / "e2r_fresh_manifest.json", "w"), indent=2)
    print(f"wrote {OUT / 'e2r_fresh_vs_fixed.csv'}")


if __name__ == "__main__":
    raise SystemExit(main())
