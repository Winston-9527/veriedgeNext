"""P1a: Sign-balanced adaptive attack.

Construct e with sign(x)^T e = 0, i.e. the residual is orthogonal to sign(x).
For a reference x, choose per-coordinate sign-balanced perturbations:
  e_i = b_i * |x_i|  where b_i in {+1,-1} chosen so sum(sign(x_i) e_i) = 0.

Simple construction (exact nulling over pairs):
  pick pairs of coordinates with sign(x_i)=sign(x_j) and same |x| weight;
  add +c*|x_i| to one, -c*|x_j| to the other -> contribution cancels.

We build this greedily over the sampled coordinates so sign(x)^T e = 0 EXACTLY
on the sampled set, then measure:
  - SignRadial TPR (expect ~0: the blind spot)
  - ProjCos TPR     (expect high: angular redistribution, its home turf)
  - SRR TPR         (energy detector: sees |e|^2, should also detect)

Amplitude c controls how "material" the change is (c=0.5 => each perturbed
coord changes by 50% of |x|; total relative energy ~ c^2 * (n/2)/n ~ c^2/2).
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
from srr import compute_srr, SRRConfig, srr_stat

PAIR = "A/B"
Q = 256
PCTL = 99.0
SC = 3.0
SEED = 1


def sign_balanced_attack(bundle, c, seed, q=Q, checkpoint="C2"):
    """Perturb C2 so sign(x)^T (y-x) = 0 EXACTLY over q sampled coords, amplitude c.

    Construction: draw a raw perturbation e0, then remove its component along
    sign(x):  e = e0 - (sign(x).e0 / n_nonzero) * sign(x).
    This guarantees sum sign(x_i) e_i = 0 on the sampled set, while |e| stays
    ~ |e0| (the removed component is small since sign(x) is nearly isotropic).
    Amplitude c scales e0 to control materiality.
    """
    out = dict(bundle)
    t = out[f"prefill__{checkpoint}"].astype(np.float32).copy()
    r0 = t[0]
    T, D = r0.shape
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=q, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    x = r0[rows, cols].astype(np.float64)
    sgn = np.sign(x)
    # raw perturbation: random signs scaled by c * local |x| (material, dense)
    e0 = c * np.abs(x) * rng.choice([-1.0, 1.0], size=q)
    # project out the sign(x) direction: sum sign(x) e = 0
    denom = max(np.sum(sgn * sgn), 1e-12)  # number of nonzero-sign coords
    proj = np.sum(sgn * e0) / denom
    e = e0 - proj * sgn
    new_vals = x + e
    t[0, rows, cols] = new_vals.astype(np.float32)
    out[f"prefill__{checkpoint}"] = t
    null_check = float(np.sum(sgn * e))
    return out, null_check


def main():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re))

    # SignRadial gamma
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

    # SRR config
    scfg = SRRConfig(q=Q, n_groups=4, coords_per_group=Q // 4)
    srr_gm = {c: g[c] * SC for c in ["C1", "C2", "C3"]}  # reuse sign gamma as SRR gamma proxy
    # better: calibrate SRR gamma separately
    def calib_srr_gamma(Lc, Rc, ckts, seed):
        shared = sorted(set(Lc) & set(Rc))
        ratios = {c: [] for c in ckts}
        for pid in shared:
            for ck in ckts:
                E, B, _ = srr_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], scfg, seed)
                ratios[ck].append(float(np.max(E / (B + 1e-12))))
        return {c: float(np.percentile(np.array(ratios[c]), PCTL)) for c in ckts}

    srr_g = calib_srr_gamma(Lc, Rc, ["C1", "C2", "C3"], SEED)
    srr_gm = {c: srr_g[c] * SC for c in ["C1", "C2", "C3"]}

    def srr_det_energy(cand, ref):
        for ck in ["C1", "C2", "C3"]:
            a, _, _, _ = compute_srr(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], scfg, SEED, srr_gm[ck])
            if a:
                return True
        return False

    # ProjCos
    d4 = calibrate_proj_delta(Lc, Rc, 99.0, 16, 4, 911, SEED, "tstc_projcos")
    sd4 = {"prefill": {c: d4["prefill"][c] * 1.5 for c in ["C1", "C2", "C3"]}}

    def pc_det(cand, ref):
        ok, _ = baseline_detect("projcos4", cand, ref, SEED, sd4, 16, 0, 4, 911, "tstc_projcos")
        return ok

    d16 = calibrate_proj_delta(Lc, Rc, 99.0, 16, 16, 911, SEED, "tstc_projcos")
    sd16 = {"prefill": {c: d16["prefill"][c] * 1.5 for c in ["C1", "C2", "C3"]}}

    def pc16_det(cand, ref):
        ok, _ = baseline_detect("projcos16", cand, ref, SEED, sd16, 16, 0, 16, 911, "tstc_projcos")
        return ok

    n = len(eval_ids)
    print(f"=== P1a: sign-balanced attack on {PAIR} (sign(x)^T e = 0) ===")
    print(f"amplitude c | null_check | SignRadial | SRR | ProjCos4 | ProjCos16")
    for c in (0.1, 0.3, 0.5, 1.0):
        sr = en = p4 = p16 = 0
        null_max = 0.0
        for pid in eval_ids:
            atk, nullc = sign_balanced_attack(Re[pid], c, SEED)
            null_max = max(null_max, abs(nullc))
            if srr_det(atk, Re[pid]):
                sr += 1
            if srr_det_energy(atk, Re[pid]):
                en += 1
            if pc_det(atk, Re[pid]):
                p4 += 1
            if pc16_det(atk, Re[pid]):
                p16 += 1
        print(f"  c={c:<6.1f}  {null_max:<10.1e} {sr/n:<11.3f} {en/n:<6.3f} {p4/n:<9.3f} {p16/n:<9.3f}")


if __name__ == "__main__":
    main()
