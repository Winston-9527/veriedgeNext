"""Coordinate-known vs coordinate-secret attack alignment.

The paper's verifier commits the seed context at placement, and the manual
says the adversary "must fix/send activation without knowing sampled
positions" (secret per-request PRF). My earlier attacks (sign-balanced,
balanced-channel) used a FIXED seed = the attacker KNOWS the coordinates.

This tests: does coordinate secrecy actually protect SignRadial from
sign-balanced / balanced-channel? Simulate:
  - KNOWN coords: attacker injects attack adapted to the SAME sampled coords
    the verifier checks (my earlier P1a/P2b setup).
  - SECRET coords: attacker injects attack adapted to a DIFFERENT coordinate
    set (attacker guesses coords; verifier checks its own secret coords).

Measures SignRadial TPR in both cases. If secret coords kill the attack
(TPR drops), the sign-balanced/blind-spot concern is weaker in the real
protocol; if it survives, the blind spot is real even under secrecy.
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
from attacks import inject_per_channel_scale

PAIR = "A/B"
Q = 256
PCTL = 99.0
SC = 3.0
VERIFIER_SEED = 1      # coords the verifier checks
ATTACKER_SEED = 1      # coords the attacker adapts to (KNOWN when == verifier)
CKPTS = ["C1", "C2", "C3"]


def load():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    return Lc, Rc, Le, Re, sorted(set(Le) & set(Re))


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)

    # SignRadial gamma calibrated on verifier's coords
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

    print(f"=== Coordinate KNOWN vs SECRET alignment ({PAIR}, q={Q}) ===")
    print(f"verifier checks coords from seed={VERIFIER_SEED}")

    for atk_name, atk_fn in [
        ("sign-balanced", lambda b, aseed: sign_balanced_attack(b, 0.5, aseed)[0]),
        ("balanced-channel 1.2/0.8", lambda b, aseed: inject_per_channel_scale(b, 1.2, 0.8, aseed)),
    ]:
        print(f"\n  attack: {atk_name}")
        for label, aseed in [("KNOWN (attacker seed == verifier)", VERIFIER_SEED),
                             ("SECRET (attacker seed != verifier)", VERIFIER_SEED + 12345)]:
            det = 0
            for pid in eval_ids:
                atk = atk_fn(Re[pid], aseed)
                if srr_det(atk, Re[pid]):
                    det += 1
            print(f"    {label:38s}: SignRadial TPR={det/n:.3f}")

    # honest FPR reference
    det = 0
    for pid in eval_ids:
        if srr_det(Re[pid], Le[pid]):
            det += 1
    print(f"\n  honest FPR (verifier coords): {det/n:.3f}")


if __name__ == "__main__":
    main()
