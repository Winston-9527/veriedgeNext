"""E2-R fresh-P harm validation: under commit-then-challenge (fresh per-request
seed_s), does an EVADED tamper actually change the final generated output?

Answers the audit question: the last family that still evades detection under
fresh P/Omega (tol_hug_combined, and small-rho joint_null) — is it real harm or
just a weak perturbation that passes?

Protocol = run_e2r_fresh.py (commit-to-seed + reveal, eval-anchored thresholds),
attacker = OUTPUT-GRADIENT harm direction g (realistic attacker with model
access, unlike run_e2r_fresh.py's random g), C3 injection.

Metrics per (family, evaded/detected):
  - harm: replay(C3, b+e) last-token logits vs honest full-forward, rel-L2
  - argmax_change: first-token flip
  - 32-token greedy decode: token agreement / ROUGE-L F1 / p_output_changed

Run on RTX6000 (CUDA fp32). Compare directly to fixed-protocol §3.2/3.3.

Usage:
    python3 run_e2r_fresh_harm_decode.py --root ... --prompts ... --out results/e2r_fresh_harm
        [--rho 0.01] [--max-eval N]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import (load_stack, load_splits, load_ids, sr_score,
                        projcos_score, smoothed_ecdf, BOUNDARIES, FAMILIES,
                        SR_Q, PROJ_K, ALPHA, VERIFIER_SEED, _ck)
from e2r_attacks import construct

MASTER = 20260810   # must match run_e2r_fresh.py
AG = VERIFIER_SEED  # attacker's guessed seed (2026), same as run_e2r_fresh.py default
MAX_NEW = 32


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def lcs_len(a, b):
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        row, prow = dp[i], dp[i - 1]
        for j in range(1, n + 1):
            row[j] = prow[j - 1] + 1 if a[i - 1] == b[j - 1] else max(prow[j], row[j - 1])
    return dp[m][n]


def rouge_l_f1(a, b):
    if not a or not b:
        return 0.0
    lcs = lcs_len(a, b)
    if lcs == 0:
        return 0.0
    p, r = lcs / len(b), lcs / len(a)
    return 2 * p * r / (p + r)


def _decode_groups(model, tok, ids_map, groups, device, inject=None):
    out_tokens = {}
    for T, pids in groups.items():
        ids = np.stack([np.array(ids_map[p]) for p in pids])
        ids_t = torch.tensor(ids, dtype=torch.long, device=device)
        hook = None
        if inject is not None:
            B = len(pids)
            inj = np.stack([np.asarray(inject[p], dtype=np.float32) for p in pids])
            inv = torch.as_tensor(inj, device=device)
            state = {"done": False}

            def _make_hook(inv_t, T_len):
                def hook(module, args, output):
                    h = output[0] if isinstance(output, tuple) else output
                    if not state["done"] and h.shape[1] == T_len:
                        state["done"] = True
                        return inv_t
                    return output
                return hook
            hook = _make_hook(inv, T)
            handle = model.model.layers[27].register_forward_hook(hook)
        try:
            with torch.no_grad():
                out = model.generate(ids_t, max_new_tokens=MAX_NEW, do_sample=False,
                                     use_cache=True, temperature=1.0, top_p=None)
        finally:
            if hook is not None:
                handle.remove()
        gen = out[:, T:].tolist()
        for pid, toks in zip(pids, gen):
            out_tokens[pid] = toks
    return out_tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rho", type=float, default=0.01)
    ap.add_argument("--max-eval", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    ROOT = Path(args.root); PP = Path(args.prompts); OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)
    RHO = args.rho

    # ---------------- data ----------------
    stack_a = load_stack(ROOT, "stack_a_720")
    stack_b = load_stack(ROOT, "stack_b_720")
    p2s = load_splits(PP); ids_map = load_ids(PP)
    calib = sorted(p for p in stack_a if p2s.get(p) == "calibration" and p in stack_b)
    eval_ids = sorted(p for p in stack_a if p2s.get(p) == "evaluation" and p in stack_b)
    if args.max_eval:
        eval_ids = eval_ids[: args.max_eval]
    log(f"calib={len(calib)} eval={len(eval_ids)} rho={RHO} AG={AG}")

    # ---------------- fresh protocol (identical to run_e2r_fresh.py) ----------------
    rng = np.random.default_rng(MASTER)
    seed_map = {pid: int(rng.integers(0, 2**32)) for pid in calib + eval_ids}

    def trace_scores(ids, seed_fn):
        sr, pc = [], []
        for pid in ids:
            s = seed_fn(pid)
            a, b = stack_a[pid], stack_b[pid]
            sr.append(max(sr_score(b[_ck(k)], a[_ck(k)], SR_Q, s) for k in BOUNDARIES))
            pc.append(max(projcos_score(b[_ck(k)], a[_ck(k)], PROJ_K, s) for k in BOUNDARIES))
        return np.array(sr), np.array(pc)

    cal_tr_sr, cal_tr_pc = trace_scores(calib, lambda p: seed_map[p])
    u_tr_sr = smoothed_ecdf(cal_tr_sr)
    u_tr_pc = smoothed_ecdf(cal_tr_pc)
    cal_tr_combo = np.array([max(u_tr_sr(s), u_tr_pc(p)) for s, p in zip(cal_tr_sr, cal_tr_pc)])

    f_sr, f_pc = trace_scores(eval_ids, lambda p: seed_map[p])
    tau_fresh = {"SignRadial": float(np.quantile(f_sr, 1 - ALPHA)),
                 "ProjCos4": float(np.quantile(f_pc, 1 - ALPHA)),
                 "Combined": float(np.quantile(cal_tr_combo, 1 - ALPHA))}
    log(f"fresh thresholds (eval-anchored SR/PC, calib Combo): { {k: round(v,6) for k,v in tau_fresh.items()} }")

    # per-boundary calib (tol_hug construction targets)
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

    # honest fresh FPR (for the record)
    n_eval = len(eval_ids)
    def detect_fresh(cand, ref, s):
        sr = max(sr_score(cand[_ck(k)], ref[_ck(k)], SR_Q, s) for k in BOUNDARIES)
        pc = max(projcos_score(cand[_ck(k)], ref[_ck(k)], PROJ_K, s) for k in BOUNDARIES)
        combo = max(u_tr_sr(sr), u_tr_pc(pc))
        return {"SignRadial": sr > tau_fresh["SignRadial"],
                "ProjCos4": pc > tau_fresh["ProjCos4"],
                "Combined": combo > tau_fresh["Combined"]}
    fresh_fpr = {d: 0 for d in ("SignRadial", "ProjCos4", "Combined")}
    for pid in eval_ids:
        det = detect_fresh(stack_b[pid], stack_a[pid], seed_map[pid])
        for d in fresh_fpr:
            fresh_fpr[d] += int(det[d])
    fresh_fpr = {d: k / n_eval for d, k in fresh_fpr.items()}
    log(f"fresh honest eval FPR: { {d: round(v,4) for d,v in fresh_fpr.items()} }")

    # ---------------- model (CUDA fp32) ----------------
    ae2_src = Path(os.environ.get("E2R_AE2_SRC",
        "/home/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/src"))
    sys.path.insert(0, str(ae2_src))
    from accountedge_e2.qwen import QwenFull28Adapter
    from transformers import AutoTokenizer

    log(f"loading Qwen3-0.6B on {args.device} fp32")
    adapter = QwenFull28Adapter.from_pretrained(
        "Qwen/Qwen3-0.6B", device=args.device, local_files_only=True,
        dtype=torch.float32)
    model = adapter._model
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    model.eval()

    # ---------------- honest full-forward logits (eval) ----------------
    log("honest full-forward logits (eval)")
    honest_last = {}
    for i, pid in enumerate(eval_ids):
        ids = np.array([ids_map[pid]], dtype=np.int64)
        res = adapter.run_from_input_ids(ids, sketcher=lambda x: x)
        honest_last[pid] = res.suffix_output.logits[..., -1, :][0].astype(np.float64)
        if (i + 1) % 100 == 0:
            log(f"  honest logits {i+1}/{n_eval}")

    # ---------------- honest greedy decode (batched by T) ----------------
    log("honest greedy decode (batched by T)")
    groups = defaultdict(list)
    for p in eval_ids:
        groups[len(ids_map[p])].append(p)
    honest_tokens = _decode_groups(model, tok, ids_map, groups, args.device, inject=None)

    # ---------------- per-family: construct (gradient g), fresh-detect, harm, decode ----------------
    def replay_logits(kstar, activation):
        res = adapter._replay(kstar, activation)
        return res.activations, res.logits[..., -1, :][0].astype(np.float64)

    detail_path = OUT / "e2r_fresh_harm_per_prompt.csv.gz"
    with gzip.open(detail_path, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "rho", "pid",
                    "det_SR", "det_PC", "det_Combo",
                    "harm", "argmax_change", "token_agreement", "rouge_l_f1"])
        for fam in FAMILIES:
            log(f"--- {fam} rho={RHO} (gradient g, fresh detect) ---")
            # construct attacks + gradient + harm per prompt
            inject = {}
            rows = []
            for i, pid in enumerate(eval_ids):
                x1 = stack_a[pid][_ck("C3")]
                x = x1[0].astype(np.float64)
                b = stack_b[pid][_ck("C3")][0].astype(np.float64)
                bnorm = np.linalg.norm(b)
                # gradient harm direction (realistic attacker)
                gres = adapter._output_gradient_torch("C3", stack_b[pid][_ck("C3")])
                g = gres.gradient[0].astype(np.float64)
                # tol_hug targets under AG (attacker's guess)
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
                e, _ = construct(fam, g, x, b, AG, RHO, bnorm, score_fn=sf, target=tgt)
                e_2d = (b + e).astype(np.float32)      # [T,D] for decode inject
                inject[pid] = e_2d
                # fresh detection
                cand = dict(stack_b[pid]); cand[_ck("C3")] = e_2d[None]
                det = detect_fresh(cand, stack_a[pid], seed_map[pid])
                # harm (replay vs honest full-forward)
                _, logits_att = replay_logits("C3", e_2d[None])
                lh = honest_last[pid]
                harm = float(np.linalg.norm(logits_att - lh) / (np.linalg.norm(lh) + 1e-12))
                ac = int(np.argmax(logits_att) != np.argmax(lh))
                rows.append((pid, det, harm, ac))
                if (i + 1) % 200 == 0:
                    log(f"  constructed {i+1}/{n_eval}")
            # decode tampered (batched by T, full 520)
            log(f"  decoding {fam} rho={RHO}")
            tampered = _decode_groups(model, tok, ids_map, groups, args.device, inject=inject)
            for pid, det, harm, ac in rows:
                ht, tt = honest_tokens[pid], tampered[pid]
                agree = float(np.mean([1.0 if tt[j] == ht[j] else 0.0
                                       for j in range(min(len(ht), len(tt)))]))
                w.writerow([fam, RHO, pid, int(det["SignRadial"]), int(det["ProjCos4"]),
                            int(det["Combined"]), round(harm, 6), ac,
                            round(agree, 4), round(rouge_l_f1(ht, tt), 4)])
            log(f"  {fam} done")

    # ---------------- aggregate ----------------
    agg = defaultdict(lambda: defaultdict(list))
    with gzip.open(detail_path, "rt") as fh:
        for r in csv.DictReader(fh):
            fam = r["family"]
            ev = int(r["det_Combo"]) == 0
            agg[fam]["evaded" if ev else "detected"].append(
                (float(r["harm"]), int(r["argmax_change"]), float(r["token_agreement"]),
                 float(r["rouge_l_f1"])))

    summary = {"rho": RHO, "AG": AG, "fpr_fresh": fresh_fpr, "tau_fresh": tau_fresh,
               "master": MASTER, "n_eval": n_eval, "max_new": MAX_NEW}
    fam_sum = {}
    for fam in FAMILIES:
        d = {}
        for grp in ("evaded", "detected"):
            v = agg[fam][grp]
            if not v:
                continue
            harms = np.array([x[0] for x in v]); args_ = [x[1] for x in v]
            agree = np.array([x[2] for x in v])
            d[grp] = {
                "n": len(v),
                "harm_mean": float(np.mean(harms)),
                "argmax_flip": float(np.mean(args_)),
                "token_agreement_mean": float(np.mean(agree)),
                "p_output_changed": float(np.mean(agree < 1.0)),
                "harm_gt_h0": float(np.mean(harms > 0.0233)),  # h0_C3 (honest A/B Q0.95)
            }
        fam_sum[fam] = d
    summary["by_family"] = fam_sum
    json.dump(summary, open(OUT / "e2r_fresh_harm_summary.json", "w"), indent=2)
    log(f"done -> {OUT}")

    print("\n=== fresh-P (gradient g) harm of EVADED attacks (C3, rho=%s, Combo-evaded) ===" % RHO)
    print(f"{'family':20s} {'n_ev':>5s} {'harm_mean':>9s} {'argmax_flip':>11s} {'tok_agree':>9s} {'out_chg':>8s} {'harm>h0':>8s}")
    for fam in FAMILIES:
        d = fam_sum[fam].get("evaded")
        if not d:
            print(f"{fam:20s}  (no evaded)")
            continue
        print(f"{fam:20s} {d['n']:5d} {d['harm_mean']:9.3f} {d['argmax_flip']:11.3f} "
              f"{d['token_agreement_mean']:9.3f} {d['p_output_changed']:8.3f} {d['harm_gt_h0']:8.3f}")


if __name__ == "__main__":
    raise SystemExit(main())
