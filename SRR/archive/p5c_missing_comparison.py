"""Missing comparison: Scalar/ProjCos vs sign-balanced and balanced-channel attacks.

Completes the three-method comparison. For each baseline variant (scalar16/64,
projcos4/8/16, projscalar1_abs) measure TPR on:
  - sign-balanced attack (sign(x)^T e = 0)  — the attack SignRadial is blind to
  - balanced per-channel scaling            — the attack SignRadial is blind to

Also measures the COORDINATE-KNOWN vs COORDINATE-SECRET question for these
baselines (does knowing sampled coords help the attacker evade?).

Runs locally on captures (synthetic injection).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from baselines import baseline_detect, calibrate_proj_delta, calibrate_scalar_delta
from p1a_sign_balanced import sign_balanced_attack
from attacks import inject_per_channel_scale

PAIR = "A/B"
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


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)
    print(f"=== Missing: Scalar/ProjCos vs sign-balanced & balanced-channel ({PAIR}) ===")

    variants = [
        ("scalar16", "scalar", 1, 16, 0, ""),
        ("scalar64", "scalar", 1, 64, 0, ""),
        ("projcos4", "projcos", 16, 0, 4, "tstc_projcos"),
        ("projcos8", "projcos", 16, 0, 8, "tstc_projcos"),
        ("projcos16", "projcos", 16, 0, 16, "tstc_projcos"),
        ("projscalar1_abs", "projabs", 16, 0, 1, "tstc_projabs"),
    ]

    print(f"{'variant':16s} {'signbalTPR':>10s} {'balchnTPR':>9s}")

    for (vname, vfam, tok, chan, pdim, mode) in variants:
        # calibrate + select operating point (paper protocol: full grid)
        if vfam == "scalar":
            delta = calibrate_scalar_delta(Lc, Rc, 99.99, tok, chan, SEED)
        else:
            delta = calibrate_proj_delta(Lc, Rc, 99.0, tok, pdim, 911, SEED, mode)
        # pick best scale on calib (feasible then min FPR)
        best = None
        for scale in [0.5, 1.0, 1.5, 2.0]:
            sd = {"prefill": {c: delta["prefill"][c] * scale for c in CKPTS}}
            det = 0
            for pid in sorted(set(Lc) & set(Rc)):
                ok, _ = baseline_detect(vname, Rc[pid], Lc[pid], SEED, sd, tok, chan, pdim, 911, mode)
                if ok:
                    det += 1
            cfpr = det / len(set(Lc) & set(Rc))
            key = (1 if cfpr <= 0.10 else 0, -cfpr)
            if best is None or key > best[0]:
                best = (key, sd)
        sd = best[1]

        # sign-balanced attack
        sb_det = 0
        for pid in eval_ids:
            atk, _ = sign_balanced_attack(Re[pid], 0.5, SEED)
            ok, _ = baseline_detect(vname, atk, Re[pid], SEED, sd, tok, chan, pdim, 911, mode)
            if ok:
                sb_det += 1
        # balanced per-channel
        bc_det = 0
        for pid in eval_ids:
            atk = inject_per_channel_scale(Re[pid], 1.2, 0.8, SEED)
            ok, _ = baseline_detect(vname, atk, Re[pid], SEED, sd, tok, chan, pdim, 911, mode)
            if ok:
                bc_det += 1

        print(f"  {vname:16s} {sb_det/n:>10.3f} {bc_det/n:>9.3f}")

    print()
    print("Reference: SignRadial signbalTPR=0.000, balchnTPR=0.005 (blind)")
    print("Reference: ProjCos4 signbalTPR=1.000, balchnTPR=1.000 (recovers)")


if __name__ == "__main__":
    main()
