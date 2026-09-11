"""projscalar1_abs + SignRadial64 combination across all synthetic attacks.

Measures TPR for each detector (and OR combinations) across the full attack
families on the A/B captures:
  scale 1.10x/1.20x, sign-balanced, balanced-channel, per-token, stale,
  partial-replay 10/50%, layer_skip, gaussian.
And honest FPR on the heterogeneous honest pairs.

projscalar1_abs = 1D projection (no normalize), compare mean |projected gap|.
SignRadial64 = q=64 signed radial.
Both calibrated on the 40 calib prompts, evaluated on 200 held-out.
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


def projscalar1_score(cand, ref, seed=SEED):
    """1D projection (no normalize), mean |projected gap| over sampled tokens."""
    import sys as _s
    _s.path.insert(0, "/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace/sanity_20260727/frozen_snapshot/artifacts/thc/src")
    import hash_chain as hc
    from baselines import _ckpts
    cfg = hc.HashConfig(mode="tstc_projabs", seed_base=seed, delta_map={"prefill": {}},
                        prefill_token_samples=16, prefill_projection_dim=1,
                        decode_channel_samples=1, projection_seed=911)
    lc = hc.compute_hash_chain(_ckpts(cand), list(CKPTS), "prefill", cfg)
    rc = hc.compute_hash_chain(_ckpts(ref), list(CKPTS), "prefill", cfg)
    mx = 0.0
    for i in range(len(CKPTS)):
        li = lc[i]["token_idx"]; ri = rc[i]["token_idx"]
        ls = lc[i]["summary"]; rs = rc[i]["summary"]
        if li.shape == ri.shape and np.array_equal(li, ri) and ls.shape == rs.shape:
            g = float(np.mean(np.abs(ls - rs)))
        else:
            g = 1.0
        mx = max(mx, g)
    return mx


def projscalar1_detect_threshold(Lc, Rc):
    """Calibrate projscalar1_abs threshold on calib (p99 x margin)."""
    scores = []
    for pid in sorted(set(Lc) & set(Rc)):
        scores.append(projscalar1_score(Rc[pid], Lc[pid]))
    return float(np.percentile(scores, PCTL)) * 2.0


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)

    # ---- SignRadial64 calibration ----
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

    # ---- projscalar1_abs threshold ----
    ps_thr = projscalar1_detect_threshold(Lc, Rc)
    print(f"SignRadial64 gamma(C1/C2/C3)={srr_gm['C1']:.4f}/{srr_gm['C2']:.4f}/{srr_gm['C3']:.4f}, projscalar1 thr={ps_thr:.4g}")

    def ps_det(cand, ref):
        return projscalar1_score(cand, ref) > ps_thr

    # ---- attacks ----
    attacks = {
        "honest(FPR)": lambda b: (b, Le[next(i for i, p in enumerate(eval_ids) if p == next(iter(Le)))]) if False else None,
    }
    # build honest pairs: ref = left, cand = right (same prompt) -> FPR
    honest_pairs = [(Re[pid], Le[pid]) for pid in eval_ids]  # cand=right, ref=left

    def run_on(cand_fn, ref_fn):
        # cand_fn(pid) -> cand bundle; ref_fn(pid) -> ref bundle
        srr_t = 0
        ps_t = 0
        both_or = 0
        for pid in eval_ids:
            cand = cand_fn(pid)
            ref = ref_fn(pid)
            s = srr_det(cand, ref)
            p = ps_det(cand, ref)
            if s:
                srr_t += 1
            if p:
                ps_t += 1
            if s or p:
                both_or += 1
        return srr_t / n, ps_t / n, both_or / n

    print()
    print(f"{'attack':22s} {'SRR64':>6s} {'ps1abs':>6s} {'OR':>6s}")
    # honest FPR
    s, p, o = run_on(lambda pid: Re[pid], lambda pid: Le[pid])
    print(f"  {'honest FPR':22s} {s:>6.3f} {p:>6.3f} {o:>6.3f}")

    atk_defs = {
        "scale_1.10": lambda pid: inject_scale(Re[pid], 0.10),
        "scale_1.20": lambda pid: inject_scale(Re[pid], 0.20),
        "sign_balanced": lambda pid: sign_balanced_attack(Re[pid], 0.5, SEED)[0],
        "balanced_channel": lambda pid: inject_per_channel_scale(Re[pid], 1.2, 0.8, SEED),
        "per_token": lambda pid: inject_per_token_scale(Re[pid], [1.2 if i % 2 == 0 else 0.8 for i in range(32)], "C2"),
        "stale": lambda pid: inject_stale(Re[pid], Re["eval_002"]),
        "partial_10": lambda pid: inject_partial_replay(Re[pid], Re["eval_002"], 0.10, SEED),
        "partial_50": lambda pid: inject_partial_replay(Re[pid], Re["eval_002"], 0.50, SEED),
        "layer_skip": lambda pid: inject_layer_skip(Re[pid]),
        "gaussian": lambda pid: inject_gaussian(Re[pid], 0.15, SEED),
    }
    for name, fn in atk_defs.items():
        s, p, o = run_on(fn, lambda pid: Re[pid])
        print(f"  {name:22s} {s:>6.3f} {p:>6.3f} {o:>6.3f}")


if __name__ == "__main__":
    main()
