"""Test SignRadial vs projcos on direction-changing, norm-preserving attacks.

The question: does SignRadial (radial detector) ALSO catch direction-only
changes (norm preserved, direction changed)? If not, it only complements
projcos and the two must be OR-ed. This script measures both.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial, sign_radial_stat
from baselines import baseline_detect, calibrate_proj_delta

PAIR = "A/B"
Q = 256
PCTL = 99.0
SC = 3.0
SEED = 1


def setup():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re))

    def calib_gamma(Lc, Rc, ckts, seed):
        shared = sorted(set(Lc) & set(Rc))
        ratios = {c: [] for c in ckts}
        for pid in shared:
            for ck in ckts:
                P, B = sign_radial_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], seed, n=Q)
                ratios[ck].append(abs(P) / (B + 1e-12))
        return {c: float(np.percentile(np.array(ratios[c]), PCTL)) for c in ckts}

    g = calib_gamma(Lc, Rc, ["C1", "C2", "C3"], SEED)
    gm = {c: g[c] * SC for c in ["C1", "C2", "C3"]}

    def srr_det(cand, ref):
        for ck in ["C1", "C2", "C3"]:
            a, _, _, _ = sign_radial(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], SEED, n=Q, gamma=gm[ck])
            if a:
                return True
        return False

    def proj_det(proj_dim):
        d = calibrate_proj_delta(Lc, Rc, 99.0, 16, proj_dim, 911, SEED, "tstc_projcos")
        sd = {"prefill": {c: d["prefill"][c] * 1.5 for c in ["C1", "C2", "C3"]}}

        def f(cand, ref):
            ok, _ = baseline_detect(f"projcos{proj_dim}", cand, ref, SEED, sd, 16, 0, proj_dim, 911, "tstc_projcos")
            return ok

        return f

    return Re, eval_ids, srr_det, proj_det(4), proj_det(16)


def sign_flip(bundle):
    return {c: -bundle[c].copy() for c in ["prefill__C1", "prefill__C2", "prefill__C3"]}


def permute_tokens(bundle, seed):
    out = dict(bundle)
    rng = np.random.default_rng(seed)
    t = out["prefill__C2"].copy()
    out["prefill__C2"] = t[:, rng.permutation(t.shape[1])]
    return out


def scale_attack(bundle, eps, seed=0):
    out = dict(bundle)
    out["prefill__C2"] = out["prefill__C2"].astype(np.float32) * (1.0 + eps)
    return out


def main():
    Re, eval_ids, srr, pc4, pc16 = setup()
    n = len(eval_ids)
    print(f"=== Direction-changing / norm-preserving attacks on A/B (n={n}) ===")
    print(f"{'attack':22s} {'SignRadial':>10s} {'projcos4':>8s} {'projcos16':>9s}")

    attacks = {
        "sign_flip (y=-x)": (sign_flip, None),
        "token_permute": (permute_tokens, SEED),
    }
    for name, (fn, arg) in attacks.items():
        sr = pc4d = pc16d = 0
        for pid in eval_ids:
            atk = fn(Re[pid], arg) if arg is not None else fn(Re[pid])
            if srr(atk, Re[pid]):
                sr += 1
            if pc4(atk, Re[pid]):
                pc4d += 1
            if pc16(atk, Re[pid]):
                pc16d += 1
        print(f"{name:22s} {sr/n:10.3f} {pc4d/n:8.3f} {pc16d/n:9.3f}")

    print()
    print("=== Cross-check: radial (scale) attack — should be SignRadial's home turf ===")
    for eps in (0.05, 0.10, 0.20):
        sr = pc4d = pc16d = 0
        for pid in eval_ids:
            atk = scale_attack(Re[pid], eps)
            if srr(atk, Re[pid]):
                sr += 1
            if pc4(atk, Re[pid]):
                pc4d += 1
            if pc16(atk, Re[pid]):
                pc16d += 1
        print(f"scale {(1+eps):.2f}x:     {sr/n:10.3f} {pc4d/n:8.3f} {pc16d/n:9.3f}")


if __name__ == "__main__":
    main()
