"""E2-R main orchestrator: unified-protocol adaptive adversary x 3 detectors.

Runs on RTX6000 (CUDA fp32, matching stack_b). Two-phase by design:
  - Phase A (numpy): thresholds, honest baselines, constructions, scoring.
  - Phase B (CUDA):  _replay injection forward (downstream propagation + logits),
                     _output_gradient_torch harm directions, honest logits.

Streams per-prompt detail rows to <out>/e2r_per_prompt_detail.csv.gz so a
partial/failed run can be resumed by assembly (run_e2r_assemble.py).

Usage:
    python3 run_e2r_main.py \
        --root /path/to/captures_720 --prompts /path/to/qwen_prompt_splits...jsonl \
        --out results/e2r --harm-dir gradient [--max-eval N] [--sanity-only]
"""

from __future__ import annotations

import argparse
import gzip
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import (
    VERIFIER_SEED, PRIMARY_GUESS_SEED, GUESS_SEEDS, BOUNDARIES, DETECTORS,
    FAMILIES, RHOS, ALPHA, DELTA, SR_Q, PROJ_K, BLIND_RHO,
    load_stack, load_splits, load_ids, data_fingerprint,
    boundary_scores, trace_scores, calibrate, detect_trace, wilson95,
    sr_score, projcos_score, _ck,
)
from e2r_attacks import construct, joint_null_report

DETAIL_COLS = ["tm", "family", "rho", "kstar", "pid", "detector",
               "s_C1", "s_C2", "s_C3", "detected", "loc_first", "loc_ok",
               "harm", "argmax_change", "rho_eff"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------- replay helpers

def replay_logits(adapter, kstar: str, activation: np.ndarray):
    """_replay(kstar, activation[1,T,D]) -> (activations dict, last-token logits)."""
    res = adapter._replay(kstar, activation)
    last = res.logits[..., -1, :][0]          # [V] float32
    return res.activations, last.astype(np.float64)


def honest_logits_full(adapter, ids: np.ndarray):
    """run_from_input_ids -> last-token logits [V]."""
    res = adapter.run_from_input_ids(ids, sketcher=lambda x: x)
    last = res.suffix_output.logits[..., -1, :][0]
    return last.astype(np.float64)


def gradient_dir(adapter, kstar: str, source: np.ndarray):
    """_output_gradient_torch(kstar, source[1,T,D]) -> harm direction g [T,D]."""
    gres = adapter._output_gradient_torch(kstar, source)
    return gres.gradient[0].astype(np.float64)


# ------------------------------------------------------------------- phases

def stage_sanity(adapter, stack_a, stack_b, eval_ids, device):
    """§3.5 mandatory sanity checks. Aborts on failure."""
    log("STAGE 0: sanity (replay reproduces capture)")
    # (1) replay(C1, b_C1) reproduces b_C2/b_C3
    for pid in eval_ids[:3]:
        b1 = stack_b[pid]
        act = b1[_ck("C1")]
        acts, _ = replay_logits(adapter, "C1", act)
        ok2 = np.array_equal(np.asarray(acts["C2"], dtype=np.float32),
                             np.asarray(b1[_ck("C2")], dtype=np.float32))
        ok3 = np.array_equal(np.asarray(acts["C3"], dtype=np.float32),
                             np.asarray(b1[_ck("C3")], dtype=np.float32))
        if not (ok2 and ok3):
            raise RuntimeError(
                f"SANITY FAIL: replay(C1, b_C1) does not reproduce b_C2/b_C3 "
                f"for {pid} (ok2={ok2} ok3={ok3})")
    log(f"  replay reproduces capture: {len(eval_ids[:3])} prompts OK")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--harm-dir", choices=["gradient", "random"], default="gradient")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-eval", type=int, default=0, help="debug: cap eval prompts")
    ap.add_argument("--sanity-only", action="store_true")
    ap.add_argument("--skip-honest-logits", action="store_true")
    ap.add_argument("--cond", default="", help="debug: only these conditions (tm|fam|rho|k), comma-sep")
    ap.add_argument("--guess-seed", type=int, default=PRIMARY_GUESS_SEED,
                    help="TM-1 attacker's guessed seed (default 2027)")
    ap.add_argument("--p-seed", type=int, default=0,
                    help="audit arm TM1b_knownP: P public (verifier seed). 0 = P secret (default)")
    args = ap.parse_args()

    ROOT = Path(args.root)
    PP = Path(args.prompts)
    OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------- numpy phase
    log(f"loading 720 pool from {ROOT}")
    stack_a = load_stack(ROOT, "stack_a_720")
    stack_b = load_stack(ROOT, "stack_b_720")
    p2s = load_splits(PP)
    ids_map = load_ids(PP)
    calib = sorted(p for p in stack_a if p2s.get(p) == "calibration" and p in stack_b)
    eval_ids = sorted(p for p in stack_a if p2s.get(p) == "evaluation" and p in stack_b)
    if args.max_eval:
        eval_ids = eval_ids[: args.max_eval]
    log(f"calib={len(calib)} eval={len(eval_ids)}")

    C = calibrate(calib, stack_a, stack_b, VERIFIER_SEED)
    tau = C["tau_trace"]
    gamma = C["gamma"]
    combo_trace = C["combo_trace"]
    u_sr, u_pc, combo = C["combo"]
    log(f"tau_trace={ {k: round(v, 6) for k, v in tau.items()} }")
    log(f"gamma.SR={ {k: round(v, 5) for k, v in gamma['SignRadial'].items()} }")

    if args.sanity_only:
        return 0

    # ------------------------------------------------------------ torch phase
    import torch
    from transformers import AutoTokenizer
    ae2_src = Path(__import__("os").environ.get(
        "E2R_AE2_SRC",
        "/home/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/src"))
    sys.path.insert(0, str(ae2_src))
    from accountedge_e2.qwen import QwenFull28Adapter

    log(f"loading Qwen3-0.6B on {args.device} fp32")
    adapter = QwenFull28Adapter.from_pretrained(
        "Qwen/Qwen3-0.6B", device=args.device, local_files_only=True,
        dtype=torch.float32)
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    adapter._tok = tok  # keep for reference
    model_id_sha = None

    # ---- STAGE 0 sanity
    stage_sanity(adapter, stack_a, stack_b, eval_ids, args.device)

    # ---- STAGE 1: honest logits (eval) + h0 (calib)
    log("STAGE 1: honest last-token logits (eval) + h0 (calib)")
    honest_last = {}
    for i, pid in enumerate(eval_ids):
        ids = np.array([ids_map[pid]], dtype=np.int64)
        honest_last[pid] = honest_logits_full(adapter, ids)
        if (i + 1) % 100 == 0:
            log(f"  honest logits {i+1}/{len(eval_ids)}")

    # h0: honest A/B logit shift per boundary on calib
    shift = {b: [] for b in BOUNDARIES}
    for pid in calib:
        for b in BOUNDARIES:
            _, lb = replay_logits(adapter, b, stack_b[pid][_ck(b)])  # honest B suffix
            _, la = replay_logits(adapter, b, stack_a[pid][_ck(b)])  # A injected
            denom = np.linalg.norm(lb) + 1e-12
            shift[b].append(float(np.linalg.norm(la - lb) / denom))
    h0 = {b: float(np.quantile(np.array(shift[b]), 0.95)) for b in BOUNDARIES}
    log(f"h0 (honest A/B logit shift Q0.95): { {k: round(v, 5) for k, v in h0.items()} }")

    # ---- STAGE 2: harm directions g (gradient) for eval x boundary
    if args.harm_dir == "gradient":
        log("STAGE 2: output-gradient harm directions (eval x boundary)")
        gdirs = {}
        for i, pid in enumerate(eval_ids):
            gdirs[pid] = {}
            for b in BOUNDARIES:
                gdirs[pid][b] = gradient_dir(adapter, b, stack_b[pid][_ck(b)])
            if (i + 1) % 100 == 0:
                log(f"  gradients {i+1}/{len(eval_ids)}")
    else:
        log("STAGE 2: random harm directions")
        gdirs = {pid: {b: np.random.default_rng(hash(pid) % 2**32)
                       .normal(0, 1, stack_b[pid][_ck(b)][0].shape).astype(np.float64)
                       for b in BOUNDARIES} for pid in eval_ids}

    # ---- STAGE 3: main matrix loop
    log("STAGE 3: main matrix loop")
    detail_path = OUT / "e2r_per_prompt_detail.csv.gz"
    fh = gzip.open(detail_path, "wt", newline="")
    w = csv.writer(fh)
    w.writerow(DETAIL_COLS)

    cond_filter = set()
    if args.cond:
        for c in args.cond.split(","):
            cond_filter.add(tuple(c.split("|")))

    def combo_boundary(cand1, x1, seed_att, b):
        return max(u_sr[b](sr_score(cand1, x1, SR_Q, seed_att)),
                   u_pc[b](projcos_score(cand1, x1, PROJ_K, seed_att)))

    def combo_boundary_p(cand1, x1, seed_att, p_seed, b):
        """Combined score with SR from Omega seed, ProjCos from P seed
        (TM1b_knownP: attacker nails P, Omega stays guessed)."""
        return max(u_sr[b](sr_score(cand1, x1, SR_Q, seed_att)),
                   u_pc[b](projcos_score(cand1, x1, PROJ_K, p_seed)))

    n_conds = 0
    t_cond = time.time()
    for tm, att_seed in [("TM1_seed_secret", args.guess_seed),
                         ("TM2_seed_known", VERIFIER_SEED)]:
        # audit arm TM1b_knownP: P is public (verifier seed), Omega stays secret
        p_seed = att_seed
        tm_label = tm
        if tm.startswith("TM1") and args.p_seed:
            p_seed = args.p_seed
            tm_label = "TM1b_knownP"
        for fam in FAMILIES:
            for rho in RHOS:
                for kstar in BOUNDARIES:
                    if cond_filter and (tm_label, fam, str(rho), kstar) not in cond_filter:
                        continue
                    n_conds += 1
                    t0 = time.time()
                    for i, pid in enumerate(eval_ids):
                        x1 = stack_a[pid][_ck(kstar)]
                        b1 = stack_b[pid][_ck(kstar)]
                        x = x1[0].astype(np.float64)
                        b = b1[0].astype(np.float64)
                        bnorm = np.linalg.norm(b)
                        g = gdirs[pid][kstar]
                        # attacker-side score fn: SR uses Omega seed (att_seed),
                        # ProjCos uses P seed (p_seed). TM-2 aligned; TM-1
                        # misaligned on Omega; TM1b_knownP aligned on P only.
                        if fam == "tol_hug_sr":
                            score_fn = lambda c1, _seed=att_seed: sr_score(c1, x1, SR_Q, _seed)
                            target = gamma["SignRadial"][kstar]
                        elif fam == "tol_hug_projcos":
                            score_fn = lambda c1, _ps=p_seed: projcos_score(c1, x1, PROJ_K, _ps)
                            target = gamma["ProjCos4"][kstar]
                        elif fam == "tol_hug_combined":
                            score_fn = lambda c1: combo_boundary_p(c1, x1, att_seed, p_seed, kstar)
                            target = gamma["Combined"][kstar]
                        else:
                            score_fn, target = None, None

                        e, rho_eff = construct(fam, g, x, b, att_seed, rho, bnorm,
                                               score_fn=score_fn, target=target,
                                               p_seed=p_seed)
                        injected = (b + e)[None].astype(np.float32)
                        acts, logits_att = replay_logits(adapter, kstar, injected)

                        cand = {}
                        for kk in BOUNDARIES:
                            if kk == kstar:
                                cand[_ck(kk)] = injected
                            elif kk in acts:
                                cand[_ck(kk)] = np.asarray(acts[kk], dtype=np.float32)
                            else:
                                cand[_ck(kk)] = stack_b[pid][_ck(kk)]

                        bs = boundary_scores(cand, stack_a[pid], VERIFIER_SEED)
                        det = detect_trace(bs, combo_trace, cand, stack_a[pid],
                                           VERIFIER_SEED, tau)

                        # per-boundary Combined score (ECDF fusion) for localization
                        combo_b = {}
                        for b in BOUNDARIES:
                            combo_b[b] = max(
                                u_sr[b](sr_score(cand[_ck(b)], stack_a[pid][_ck(b)], SR_Q, VERIFIER_SEED)),
                                u_pc[b](projcos_score(cand[_ck(b)], stack_a[pid][_ck(b)], PROJ_K, VERIFIER_SEED)))

                        def sb(d, b):
                            return bs[b][d] if d != "Combined" else combo_b[b]

                        # localization per detector (first boundary over Gamma)
                        loc = {}
                        for d in DETECTORS:
                            first = None
                            for b in BOUNDARIES:
                                if sb(d, b) > gamma[d][b]:
                                    first = b
                                    break
                            loc[d] = (first, first == kstar)

                        # harm
                        lh = honest_last[pid]
                        denom = np.linalg.norm(lh) + 1e-12
                        harm = float(np.linalg.norm(logits_att - lh) / denom)
                        ac = int(np.argmax(logits_att) != np.argmax(lh))

                        for d in DETECTORS:
                            w.writerow([tm_label, fam, rho, kstar, pid, d,
                                        round(sb(d, "C1"), 8), round(sb(d, "C2"), 8),
                                        round(sb(d, "C3"), 8),
                                        int(det[d]), loc[d][0] or "none", int(loc[d][1]),
                                        round(harm, 8), ac, round(rho_eff, 6)])
                    log(f"  {tm_label} {fam:20s} rho={rho:<5} {kstar}: {time.time()-t0:.1f}s "
                        f"({n_conds}/{216})")

    fh.close()

    # honest rows (eval FPR + honest harm=0)
    log("writing honest rows")
    with gzip.open(detail_path, "at", newline="") as fh:
        w = csv.writer(fh)
        for pid in eval_ids:
            ref = stack_a[pid]
            cand = stack_b[pid]
            bs = boundary_scores(cand, ref, VERIFIER_SEED)
            det = detect_trace(bs, combo_trace, cand, ref, VERIFIER_SEED, tau)
            combo_b = {}
            for b in BOUNDARIES:
                combo_b[b] = max(u_sr[b](sr_score(cand[_ck(b)], ref[_ck(b)], SR_Q, VERIFIER_SEED)),
                                 u_pc[b](projcos_score(cand[_ck(b)], ref[_ck(b)], PROJ_K, VERIFIER_SEED)))
            for d in DETECTORS:
                def _sb(d_, b_):
                    return bs[b_][d_] if d_ != "Combined" else combo_b[b_]
                w.writerow(["NA", "honest", -1.0, "NA", pid, d,
                            round(_sb(d, "C1"), 8), round(_sb(d, "C2"), 8),
                            round(_sb(d, "C3"), 8), int(det[d]), "none", 0,
                            0.0, 0, -1.0])

    # manifest (partial; assembly completes it)
    mani = {
        "verifier_seed": VERIFIER_SEED,
        "guess_seeds": GUESS_SEEDS,
        "primary_guess_seed": PRIMARY_GUESS_SEED,
        "p_seed_public": args.p_seed or None,
        "rho_grid": list(RHOS), "delta": DELTA, "alpha": ALPHA,
        "sr_q": SR_Q, "proj_k": PROJ_K,
        "harm_dir": args.harm_dir,
        "data_fingerprint": data_fingerprint(ROOT, PP),
        "n_calib": len(calib), "n_eval": len(eval_ids),
        "tau_trace": tau,
        "gamma": gamma,
        "h0": h0,
        "harm_proxy": "relative L2 shift of last-token logits vs honest; harmful iff > h0[boundary]",
    }
    with open(OUT / "e2r_manifest_partial.json", "w") as fh:
        json.dump(mani, fh, indent=2, default=str)
    log(f"done. detail -> {detail_path}  ({n_conds} conditions, {len(eval_ids)} eval)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
