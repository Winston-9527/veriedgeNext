"""Verify whether ProjCos8 + SignRadial64 is the best combination.

ProjCos8 already showed W8A16 TPR=1.0 (precision cheating). Now test whether
ProjCos8 ALSO covers SignRadial's synthetic blind spots (sign-balanced,
balanced-channel, gaussian) like ProjCos4 does, across all attack families.
Also report FPR. Compare ProjCos4 vs ProjCos8 vs projscalar1_abs combined
with SignRadial64.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial, sign_radial_stat
from p1a_sign_balanced import sign_balanced_attack
from attacks import (
    inject_scale, inject_per_channel_scale, inject_per_token_scale,
    inject_stale, inject_partial_replay, inject_layer_skip, inject_gaussian,
)

PAIR = "A/B"
Q_SRR = 64
PCTL = 99.0
SC_SRR = 3.0
SEED = 1
CKPTS = ["C1", "C2", "C3"]


def load():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    return Lc, Rc, Le, Re, sorted(set(Le) & set(Re))


def projcos_gap_score(cand, ref, seed=SEED, d=4):
    """Max checkpoint projcos mean-gap (raw score)."""
    import sys as _s
    _s.path.insert(0, "/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace/sanity_20260727/frozen_snapshot/artifacts/thc/src")
    import hash_chain as hc
    from baselines import _ckpts
    cfg = hc.HashConfig(mode="tstc_projcos", seed_base=seed, delta_map={"prefill": {}},
                        prefill_token_samples=16, prefill_projection_dim=d,
                        decode_channel_samples=1, projection_seed=911)
    lc = hc.compute_hash_chain(_ckpts(cand), list(CKPTS), "prefill", cfg)
    rc = hc.compute_hash_chain(_ckpts(ref), list(CKPTS), "prefill", cfg)
    mx = 0.0
    for i in range(len(CKPTS)):
        li = lc[i]["token_idx"]; ri = rc[i]["token_idx"]
        ls = lc[i]["summary"]; rs = rc[i]["summary"]
        if li.shape == ri.shape and np.array_equal(li, ri) and ls.shape == rs.shape:
            denom = np.maximum(np.linalg.norm(ls, axis=1) * np.linalg.norm(rs, axis=1), 1e-12)
            g = float(np.mean(1.0 - np.sum(ls * rs, axis=1) / denom))
        else:
            g = 1.0
        mx = max(mx, g)
    return mx


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)

    # SignRadial64 threshold
    def calib_srr(ck):
        r = []
        for pid in sorted(set(Lc) & set(Rc)):
            P, B = sign_radial_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], SEED, n=Q_SRR)
            r.append(abs(P) / (B + 1e-12))
        return float(np.percentile(r, PCTL)) * SC_SRR
    srr_gm = {c: calib_srr(c) for c in CKPTS}

    def srr_det(cand, ref):
        for ck in CKPTS:
            a, _, _, _ = sign_radial(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], SEED, n=Q_SRR, gamma=srr_gm[ck])
            if a:
                return True
        return False

    # ProjCos thresholds per d (calibrate p99 on calib)
    proj_thr = {}
    for d in [4, 8]:
        scores = [projcos_gap_score(Rc[pid], Lc[pid], d=d) for pid in sorted(set(Lc) & set(Rc))]
        proj_thr[d] = float(np.percentile(scores, PCTL)) * 2.0
    print(f"ProjCos4 thr={proj_thr[4]:.4g}, ProjCos8 thr={proj_thr[8]:.4g}, SignRadial64 gamma(C2)={srr_gm['C2']:.4f}")

    def pc_det(cand, ref, d):
        return projcos_gap_score(cand, ref, d=d) > proj_thr[d]

    # attacks
    atk_defs = {
        "honest(FPR)": lambda pid, ref: (Re[pid], Le[pid]),
        "scale_1.10": lambda pid, ref: (inject_scale(Re[pid], 0.10), ref),
        "scale_1.20": lambda pid, ref: (inject_scale(Re[pid], 0.20), ref),
        "sign_balanced": lambda pid, ref: (sign_balanced_attack(Re[pid], 0.5, SEED)[0], ref),
        "balanced_channel": lambda pid, ref: (inject_per_channel_scale(Re[pid], 1.2, 0.8, SEED), ref),
        "per_token": lambda pid, ref: (inject_per_token_scale(Re[pid], [1.2 if i % 2 == 0 else 0.8 for i in range(32)], "C2"), ref),
        "stale": lambda pid, ref: (inject_stale(Re[pid], Re["eval_002"]), ref),
        "partial_10": lambda pid, ref: (inject_partial_replay(Re[pid], Re["eval_002"], 0.10, SEED), ref),
        "partial_50": lambda pid, ref: (inject_partial_replay(Re[pid], Re["eval_002"], 0.50, SEED), ref),
        "layer_skip": lambda pid, ref: (inject_layer_skip(Re[pid]), ref),
        "gaussian": lambda pid, ref: (inject_gaussian(Re[pid], 0.15, SEED), ref),
    }

    print()
    print(f"{'attack':20s} {'SRR64':>6s} {'PC4':>5s} {'PC8':>5s} {'SRR+PC4':>8s} {'SRR+PC8':>8s} {'SRR+ps1':>8s}")
    for name, fn in atk_defs.items():
        res = {"s": 0, "p4": 0, "p8": 0, "or4": 0, "or8": 0, "orps": 0}
        # projscalar1 score per prompt
        ps_thr = None
        for pid in eval_ids:
            cand, ref = fn(pid, Re[pid])
            s = srr_det(cand, ref)
            p4 = pc_det(cand, ref, 4)
            p8 = pc_det(cand, ref, 8)
            res["s"] += s
            res["p4"] += p4
            res["p8"] += p8
            res["or4"] += (s or p4)
            res["or8"] += (s or p8)
        print(f"  {name:20s} "
              f"{res['s']/n:>6.3f} {res['p4']/n:>5.3f} {res['p8']/n:>5.3f} "
              f"{res['or4']/n:>8.3f} {res['or8']/n:>8.3f}")


if __name__ == "__main__":
    main()
