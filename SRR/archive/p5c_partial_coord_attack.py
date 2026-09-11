"""Coordinate secrecy: partial-coordinate adaptive attack.

Refines the alignment question. The paper's verifier commits seed context;
the manual says the adversary must fix/send activation WITHOUT knowing the
sampled positions (secret per-request PRF). My earlier sign-balanced attack
perturbed the ENTIRE C2 tensor to be orthogonal to sign(x) — so coordinate
secrecy did not help. But a REAL adaptive attacker who does NOT know the
checked coordinates can only perturb a FRACTION of coordinates blindly.

This measures SignRadial detection vs the fraction of coordinates the
attacker can corrupt (blindly, without knowing the verifier's seed):
  p_corrupt = 0.1, 0.25, 0.5, 0.75, 1.0
For each, the attacker picks a random p_fraction of coordinates and applies
a sign-balanced perturbation there; the verifier checks its own secret coords.
If SignRadial detects even small corruption fractions, coordinate secrecy
matters; if it needs ~100%, the blind spot is robust to the protocol.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial, sign_radial_stat

PAIR = "A/B"
Q = 256
PCTL = 99.0
SC = 3.0
VERIFIER_SEED = 1
CKPTS = ["C1", "C2", "C3"]


def load():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    return Lc, Rc, Le, Re, sorted(set(Le) & set(Re))


def partial_sign_balanced(bundle, c, p_corrupt, attacker_seed, checkpoint="C2"):
    """Corrupt a p_fraction of C2 coords (blind, attacker's own seed) with a
    sign-balanced perturbation. Attacker does NOT know verifier's coords."""
    out = dict(bundle)
    t = out[f"prefill__{checkpoint}"].astype(np.float32).copy()
    r0 = t[0]
    T, D = r0.shape
    rng = np.random.default_rng(attacker_seed)
    # pick p_fraction of all coords to corrupt
    n_total = T * D
    n_corrupt = max(1, int(round(p_corrupt * n_total)))
    flat = rng.choice(n_total, size=n_corrupt, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    x = r0[rows, cols].astype(np.float64)
    sgn = np.sign(x)
    e0 = c * np.abs(x) * rng.choice([-1.0, 1.0], size=n_corrupt)
    denom = max(np.sum(sgn * sgn), 1e-12)
    proj = np.sum(sgn * e0) / denom
    e = e0 - proj * sgn
    t[0, rows, cols] = (x + e).astype(np.float32)
    out[f"prefill__{checkpoint}"] = t
    return out


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)

    def calib_gamma(ck, seed):
        ratios = []
        for pid in sorted(set(Lc) & set(Rc)):
            P, B = sign_radial_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], seed, n=Q)
            ratios.append(abs(P) / (B + 1e-12))
        return float(np.percentile(ratios, PCTL))

    gm = {c: calib_gamma(c, VERIFIER_SEED) * SC for c in CKPTS}

    def srr_det(cand, ref):
        for ck in CKPTS:
            a, _, _, _ = sign_radial(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], VERIFIER_SEED, n=Q, gamma=gm[ck])
            if a:
                return True
        return False

    print(f"=== Partial-coordinate attack (attacker blind to verifier seed={VERIFIER_SEED}) ===")
    print(f"{'p_corrupt':10s} {'SignRadial TPR':>14s}")
    for pc in [0.05, 0.10, 0.25, 0.50, 0.75, 1.00]:
        det = 0
        for pid in eval_ids:
            atk = partial_sign_balanced(Re[pid], 0.5, pc, VERIFIER_SEED + 999)
            if srr_det(atk, Re[pid]):
                det += 1
        print(f"  {pc:<10.2f} {det/n:>14.3f}")
    print()
    print("Interpretation:")
    print("  - If TPR rises with p_corrupt, coordinate secrecy helps (blind spot needs ~100% corruption)")
    print("  - If TPR stays low even at 100%, the blind spot is robust to the protocol")


if __name__ == "__main__":
    main()
