"""E2-R second-level harm validation: does a blindspot tamper change the FINAL
generated output? (BATCHED — groups prompts by sequence length T, decodes each
group in one generate() call with a hook injecting the stacked C3 activations.)

For C3 (last-boundary) injection under TM-2, decode 32 greedy tokens from the
tampered activation and compare to the honest greedy decode:
  - per-position token agreement
  - ROUGE-L F1 (LCS-based)

Method (faithful to "tamper at the last prefill boundary"):
  HF generate() with a forward hook on layers[27]. During PREFILL (seq len == T)
  the layer-27 output is replaced by the injected activation (honest b_C3 + e).
  The layer-27 KV cache stays honest (the tamper replaces the boundary OUTPUT,
  which only feeds norm+head -> first-token logits). Subsequent decode tokens
  attend to the honest KV + the tampered first token.

Usage (RTX6000):
    python3 run_e2r_harm_decode.py --root ... --prompts ... --out ... \
        --rho 0.01 [--max-eval N]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import (VERIFIER_SEED, FAMILIES, PROJ_K, SR_Q, BOUNDARIES,
                        _ck, load_stack, load_splits, load_ids, calibrate,
                        sr_score, projcos_score)
from e2r_attacks import construct

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


def _decode_groups(model, tok, groups, device, inject=None):
    """Decode MAX_NEW greedy tokens for prompts grouped by T.

    inject: dict {pid: [T,D] np} -> the C3 activation replacing layer-27 output
    during prefill for that prompt. None -> honest decode.
    Returns dict {pid: [tokens]}.
    """
    out_tokens = {}
    for T, pids in groups.items():
        ids = np.stack([np.array(ids_map[p]) for p in pids])  # [B, T]
        ids_t = torch.tensor(ids, dtype=torch.long, device=device)
        hook = None
        if inject is not None:
            B = len(pids)
            inj = np.stack([np.asarray(inject[p], dtype=np.float32) for p in pids])  # [B,T,D]
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
    global ids_map
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rho", type=float, default=0.01)
    ap.add_argument("--max-eval", type=int, default=0)
    ap.add_argument("--harm-dir", choices=["gradient", "random"], default="gradient")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    ROOT = Path(args.root); PP = Path(args.prompts); OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=True)

    stack_a = load_stack(ROOT, "stack_a_720")
    stack_b = load_stack(ROOT, "stack_b_720")
    p2s = load_splits(PP); ids_map = load_ids(PP)
    eval_ids = sorted(p for p in stack_a if p2s.get(p) == "evaluation" and p in stack_b)
    if args.max_eval:
        eval_ids = eval_ids[: args.max_eval]
    log(f"eval={len(eval_ids)} rho={args.rho}")

    # group by prefill length T (no padding needed)
    groups = defaultdict(list)
    for p in eval_ids:
        groups[len(ids_map[p])].append(p)
    log(f"T groups: { {k: len(v) for k, v in sorted(groups.items())} }")

    ae2_src = Path(__import__("os").environ.get(
        "E2R_AE2_SRC", "/home/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/src"))
    sys.path.insert(0, str(ae2_src))
    from accountedge_e2.qwen import QwenFull28Adapter
    from transformers import AutoTokenizer

    log("loading model (fp32 CUDA)")
    adapter = QwenFull28Adapter.from_pretrained(
        "Qwen/Qwen3-0.6B", device=args.device, local_files_only=True,
        dtype=torch.float32)
    model = adapter._model
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B", local_files_only=True)
    model.eval()

    log("honest greedy decode (batched by T)")
    honest_tokens = _decode_groups(model, tok, groups, args.device, inject=None)

    log("C3 harm directions (output-gradient)")
    gdirs = {}
    for i, pid in enumerate(eval_ids):
        b1 = stack_b[pid][_ck("C3")]
        if args.harm_dir == "gradient":
            gdirs[pid] = adapter._output_gradient_torch("C3", b1).gradient[0].astype(np.float64)
        else:
            gdirs[pid] = np.random.default_rng(i).normal(0, 1, b1[0].shape).astype(np.float64)

    # tol_hug targets: per-boundary gamma at C3 from calib honest (same as main run)
    calib_ids = sorted(p for p in stack_a if p2s.get(p) == "calibration" and p in stack_b)
    C = calibrate(calib_ids, stack_a, stack_b, VERIFIER_SEED)
    gamma = C["gamma"]
    u_sr, u_pc, combo = C["combo"]

    def tol_hug_score_fn(fam, x1, kstar):
        if fam == "tol_hug_sr":
            return (lambda c1: sr_score(c1, x1, SR_Q, VERIFIER_SEED),
                    gamma["SignRadial"][kstar])
        if fam == "tol_hug_projcos":
            return (lambda c1: projcos_score(c1, x1, PROJ_K, VERIFIER_SEED),
                    gamma["ProjCos4"][kstar])
        return (lambda c1: max(u_sr[kstar](sr_score(c1, x1, SR_Q, VERIFIER_SEED)),
                               u_pc[kstar](projcos_score(c1, x1, PROJ_K, VERIFIER_SEED))),
                gamma["Combined"][kstar])

    with gzip.open(OUT / "harm_decode_per_prompt.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "rho", "pid", "honest_tokens", "tampered_tokens",
                    "token_agreement", "rouge_l_f1"])
        for fam in FAMILIES:
            log(f"decoding {fam} rho={args.rho} (batched)")
            inject = {}
            for pid in eval_ids:
                x1 = stack_a[pid][_ck("C3")]                      # [1,T,D] for scores
                x = x1[0].astype(np.float64)                      # [T,D] for construction
                b = stack_b[pid][_ck("C3")][0].astype(np.float64)
                sf, tgt = tol_hug_score_fn(fam, x1, "C3") if fam.startswith("tol_hug") else (None, None)
                e, _ = construct(fam, gdirs[pid], x, b, VERIFIER_SEED, args.rho,
                                 np.linalg.norm(b), score_fn=sf, target=tgt)
                inject[pid] = (b + e).astype(np.float32)
            tampered = _decode_groups(model, tok, groups, args.device, inject=inject)
            for pid in eval_ids:
                ht, tt = honest_tokens[pid], tampered[pid]
                agree = float(np.mean([1.0 if tt[j] == ht[j] else 0.0
                                       for j in range(min(len(ht), len(tt)))]))
                w.writerow([fam, args.rho, pid, ht, tt, round(agree, 4),
                            round(rouge_l_f1(ht, tt), 4)])

    summary = {}
    with gzip.open(OUT / "harm_decode_per_prompt.csv.gz", "rt") as fh:
        agg = defaultdict(list)
        for row in csv.DictReader(fh):
            agg[row["family"]].append((float(row["token_agreement"]), float(row["rouge_l_f1"])))
    with open(OUT / "harm_decode_summary.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "n", "mean_token_agreement", "mean_rouge_l_f1", "p_output_changed"])
        for fam in FAMILIES:
            vals = agg.get(fam, [])
            n = len(vals)
            ag = np.mean([v[0] for v in vals]); rl = np.mean([v[1] for v in vals])
            changed = np.mean([1.0 if v[0] < 1.0 else 0.0 for v in vals])
            w.writerow([fam, n, round(ag, 4), round(rl, 4), round(changed, 4)])
            summary[fam] = {"n": n, "mean_token_agreement": round(ag, 4),
                            "mean_rouge_l_f1": round(rl, 4), "p_output_changed": round(changed, 4)}
    json.dump({"rho": args.rho, "max_new": MAX_NEW, "summary": summary},
              open(OUT / "harm_decode_summary.json", "w"), indent=2)
    log("done -> %s" % OUT)


if __name__ == "__main__":
    raise SystemExit(main())
