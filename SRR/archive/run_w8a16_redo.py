"""W8A16 redo: unified-protocol precision downgrade detection (720-pool).

Fixes old p4b_w8a16_vs_w8a8.py problems:
  1. honest baseline was SAME-device rerun (~0), masking the threshold.
     Now: honest = D(H_A, H_B) from independent A/B captures (MPS vs CUDA),
     threshold = Q_{0.99} of calibration honest scores.
  2. score was full-tensor; now q=64 sampled SignRadial + ProjCos4 (trace max).
  3. protocol: ref = H_A (stack_a, MPS), cand = honest H_B (stack_b, CUDA fp32)
     OR W8A16(H_B) (bnb int8 weights, same device/input). Detector compares
     D(H_A, cand) uniformly.
  4. W8A16 uses REAL bitsandbytes int8 weight kernels (load_in_8bit).

Run on RTX6000 (CUDA). Requires Qwen3-0.6B cache, bitsandbytes, 720-pool
jsonl, captures_720/{stack_a,stack_b}_720.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path("/home/siyuan/Developer/ndss2027/workspace/inversion/captures_720")
PROMPTS = Path("/home/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl")
MODEL = "Qwen/Qwen3-0.6B"
BOUNDARY_LAYERS = {"C1": 7, "C2": 15, "C3": 27}
SEED = 2026


def sr_score(cand: torch.Tensor, ref: torch.Tensor, q: int, seed: int) -> float:
    a = ref.reshape(-1).float().numpy()
    b = cand.reshape(-1).float().numpy()
    T = a.shape[0]
    flat = np.random.default_rng(seed).choice(T, size=min(q, T), replace=False)
    x, y = a[flat], b[flat]
    P = float(np.sum(np.sign(x) * (y - x)))
    B = float(np.sum(np.abs(x)))
    return abs(P) / (B + 1e-12)


def projcos_score(cand: torch.Tensor, ref: torch.Tensor, k: int, seed: int) -> float:
    """ProjCos on [T, D] hidden states: sample token rows, project to k dims."""
    a = ref[0].float().numpy().astype(np.float64)  # [T, D]
    b = cand[0].float().numpy().astype(np.float64)  # [T, D]
    T = a.shape[0]
    rng = np.random.default_rng(seed)
    rows = rng.choice(T, size=T, replace=False)
    rng2 = np.random.default_rng(seed + 911)
    P = rng2.normal(0.0, 1.0, (a.shape[1], k)) / np.sqrt(a.shape[1])
    rp, cp = a[rows] @ P, b[rows] @ P
    rn = rp / (np.linalg.norm(rp, axis=1, keepdims=True) + 1e-12)
    cn = cp / (np.linalg.norm(cp, axis=1, keepdims=True) + 1e-12)
    return float(np.mean(1.0 - np.clip(np.sum(rn * cn, axis=1), -1, 1)))


def trace_scores(cand_bundle, ref_bundle, seed):
    """Return (sr_trace, proj_trace) over C1/C2/C3 using captured bundles."""
    sr = max(sr_score(torch.from_numpy(cand_bundle[b]), torch.from_numpy(ref_bundle[b]), 64, seed)
             for b in ("C1", "C2", "C3"))
    proj = max(projcos_score(torch.from_numpy(cand_bundle[b]), torch.from_numpy(ref_bundle[b]), 4, seed)
               for b in ("C1", "C2", "C3"))
    return sr, proj


def run_hidden(model, tok, input_ids, device):
    ids = torch.tensor([input_ids], dtype=torch.long, device=device)
    with torch.no_grad():
        out = model(ids, output_hidden_states=True)
    return [h.detach().float().cpu() for h in out.hidden_states]


def model_trace(model, tok, input_ids, device, ref_bundle, seed):
    """D(H_A, model_activation) trace scores, model = fp16 or bnb-int8."""
    hs = run_hidden(model, tok, input_ids, device)
    sr = proj = 0.0
    for b, li in BOUNDARY_LAYERS.items():
        h = hs[li]  # [1, T, D]
        sr = max(sr, sr_score(h, torch.from_numpy(ref_bundle[b]), 64, seed))
        proj = max(proj, projcos_score(h, torch.from_numpy(ref_bundle[b]), 4, seed))
    return sr, proj


def main() -> int:
    device = "cuda"
    torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    pid2split = {}
    for line in open(PROMPTS):
        p = json.loads(line)
        pid2split[p["prompt_id"]] = p["split"]
    calib_ids = [pid for pid, s in pid2split.items() if s == "calibration"]
    eval_ids = [pid for pid, s in pid2split.items() if s == "evaluation"]
    print(f"calib={len(calib_ids)} eval={len(eval_ids)}")

    def load_stack(name):
        d = {}
        for npz in sorted((ROOT / name / "captures").glob("*.npz")):
            with np.load(npz) as f:
                d[npz.stem] = {b: f[f"prefill__{b}"] for b in ("C1", "C2", "C3")}
        return d
    stack_a = load_stack("stack_a_720")  # H_A (MPS)
    stack_b = load_stack("stack_b_720")  # H_B (CUDA fp32 honest)

    # honest calibration scores: D(H_A, H_B) from captures
    cal_sr, cal_proj = [], []
    for pid in calib_ids:
        s, p = trace_scores(stack_b[pid], stack_a[pid], SEED)
        cal_sr.append(s); cal_proj.append(p)
    cal_sr = np.array(cal_sr); cal_proj = np.array(cal_proj)
    tau_sr = float(np.quantile(cal_sr, 0.99))
    tau_proj = float(np.quantile(cal_proj, 0.99))
    print(f"honest A/B thresholds: SR p99={tau_sr:.5f} ProjCos p99={tau_proj:.5f}")

    # combined threshold via ECDF-normalized max
    def ecdf_fn(xs):
        return lambda v: float(np.searchsorted(xs, v, side="right")) / (len(xs) + 1)
    u_sr, u_proj = ecdf_fn(np.sort(cal_sr)), ecdf_fn(np.sort(cal_proj))
    cal_combo = np.array([max(u_sr(s), u_proj(p)) for s, p in zip(cal_sr, cal_proj)])
    tau_combo = float(np.quantile(cal_combo, 0.99))

    tok = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    prompt_ids = {pid: None for pid in eval_ids}
    for line in open(PROMPTS):
        p = json.loads(line)
        if p["prompt_id"] in prompt_ids:
            prompt_ids[p["prompt_id"]] = p["input_ids"]

    # evaluate on eval set
    res = {"honest": {"sr": [], "proj": []}, "W8A16": {"sr": [], "proj": []}}
    # honest from captures
    for pid in eval_ids:
        s, p = trace_scores(stack_b[pid], stack_a[pid], SEED)
        res["honest"]["sr"].append(s); res["honest"]["proj"].append(p)
    print("honest eval scores computed (from captures)")

    # W8A16: bnb int8 weights, same device, same inputs
    print("loading W8A16 (bitsandbytes int8 weights)...")
    bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)
    m_w8a16 = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb_cfg,
                                                   device_map="cuda", local_files_only=True)
    for i, pid in enumerate(eval_ids):
        s, p = model_trace(m_w8a16, tok, prompt_ids[pid], device, stack_a[pid], SEED)
        res["W8A16"]["sr"].append(s); res["W8A16"]["proj"].append(p)
        if (i + 1) % 100 == 0:
            print(f"  W8A16 eval {i+1}/{len(eval_ids)}")
    del m_w8a16
    torch.cuda.empty_cache()

    def tpr(vals, tau):
        return float(np.mean(np.array(vals) > tau))

    print("\n=== W8A16 redo: TPR@1%FPR (720-pool, A=MPS/B=CUDA) ===")
    print(f"{'case':12s} {'SignRadial':>11s} {'ProjCos4':>11s} {'Combined':>11s}")
    for case in ("honest", "W8A16"):
        sr = tpr(res[case]["sr"], tau_sr)
        proj = tpr(res[case]["proj"], tau_proj)
        combo = tpr([max(u_sr(s), u_proj(p)) for s, p in zip(res[case]["sr"], res[case]["proj"])], tau_combo)
        print(f"{case:12s} {sr:11.4f} {proj:11.4f} {combo:11.4f}")
    print(f"\nmean SR:  honest={np.mean(res['honest']['sr']):.5f}  W8A16={np.mean(res['W8A16']['sr']):.5f}")
    print(f"mean ProjCos: honest={np.mean(res['honest']['proj']):.5f}  W8A16={np.mean(res['W8A16']['proj']):.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
