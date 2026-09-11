"""P4b-v3: REAL precision cheating, DEPLOYMENT honest threshold.

Fixes the honest-threshold=0 bug: same-device BF16 rerun is bit-identical so
honest score=0 and every precision variant looks detectable. In deployment the
verifier uses a DIFFERENT device, so honest heterogeneous drift is nonzero.

Here we use the REAL heterogeneous honest threshold (A/B capture, same model,
C2 boundary ≈ layer16): SignRadial64 p99=0.066, ProjCos4 p99 (measured below),
Scalar16 p99 (measured below). Each precision variant's score on 3090 is
compared against this deployment honest p99 — TPR = fraction of prompts whose
score exceeds the honest threshold.

Same device (3090), same model, same prompts, fixed coordinates.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

MODEL = "workspace/models/Qwen3-0.6B"
PROMPTS = [
    "The capital of France is",
    "Explain the theory of relativity in one paragraph.",
    "Write a Python function to compute fibonacci numbers.",
    "What is the difference between TCP and UDP?",
    "Summarize the plot of Hamlet.",
    "List three reasons why the sky is blue.",
    "Translate 'good morning' into French, Spanish and German.",
    "What is the square root of 144?",
    "Describe the water cycle briefly.",
    "Give a recipe for chocolate chip cookies.",
]
LAYER = 16
Q_SRR = 64
PROJ_DIM = 4
Q_SCALAR = 16

# deployment honest p99 thresholds (measured from real A/B heterogeneous
# captures, C2 boundary ~ layer16, same Qwen3-0.6B model)
HONEST_P99 = {
    "srr64": 0.0664,
    "projcos4": 0.001592,
    "scalar16": 1.1387,
}


def quantize_int(x, bits):
    x = x.float()
    qmin = -(2 ** (bits - 1))
    qmax = 2 ** (bits - 1) - 1
    if x.dim() >= 2:
        scale = x.abs().amax(dim=tuple(range(1, x.dim()))) / qmax
        scale = torch.clamp(scale, min=1e-8)
        shape = [1] * x.dim()
        shape[0] = -1
        sv = scale.view(shape)
    else:
        scale = x.abs().max() / qmax
        sv = scale
    q = torch.round(x / sv).clamp(qmin, qmax)
    return q * sv, scale


def quantize_int_raw(x, bits):
    x = x.float()
    qmax = 127.0
    if x.dim() >= 2:
        scale = x.abs().amax(dim=tuple(range(1, x.dim()))) / qmax
        scale = torch.clamp(scale, min=1e-8)
        shape = [1] * x.dim()
        shape[0] = -1
        sv = scale.view(shape)
    else:
        scale = x.abs().max() / qmax
        sv = scale
    q = torch.round(x / sv).clamp(-128, 127).to(torch.int8)
    return q, scale


def quantize_fp8(x):
    return torch.round(x.float() * 8.0) / 8.0


class LowPrecLinear(torch.nn.Module):
    def __init__(self, w, b, bits):
        super().__init__()
        self.register_buffer("w", w.detach().float())
        self.register_buffer("b", b.detach().float())
        self.bits = bits

    def forward(self, x):
        wq, _ = quantize_int(self.w.to(x.device), self.bits)
        xq, _ = quantize_int(x, self.bits)
        return torch.nn.functional.linear(xq, wq, self.b.to(x.device).float())


class NativeW8A8Linear(torch.nn.Module):
    def __init__(self, w, b):
        super().__init__()
        self.register_buffer("w_fp32", w.detach().float())
        self.register_buffer("b", b.detach().float())
        q, scale = quantize_int_raw(w.detach().float(), 8)
        self.register_buffer("w_int8", q.contiguous())
        self.register_buffer("w_scale", scale.clone())

    def forward(self, x):
        xq_int, x_scale = quantize_int_raw(x, 8)
        w_int8 = self.w_int8.to(x.device)
        w_scale = self.w_scale.to(x.device)
        orig = xq_int.shape
        x2 = xq_int.reshape(-1, xq_int.shape[-1])
        M = x2.shape[0]
        w_t = w_int8.t().contiguous()
        if M <= 16:
            x2 = torch.nn.functional.pad(x2, (0, 0, 0, 32 - M))
        out = torch._int_mm(x2, w_t)
        if M <= 16:
            out = out[:M]
        out_fp = out.float() * x_scale.float() * w_scale.float().unsqueeze(0)
        return out_fp.reshape(*orig[:-1], -1) + self.b.to(x.device)


def replace_linears(model, bits):
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, LowPrecLinear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features), bits))
        else:
            replace_linears(module, bits)
    return model


def replace_w8a8(model):
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, NativeW8A8Linear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features)))
        else:
            replace_w8a8(module)
    return model


def fp8_forward(model, tok, prompt, device):
    orig = torch.nn.Linear.forward

    def fp8_linear(self, x):
        wq = quantize_fp8(self.weight.detach())
        xq = quantize_fp8(x)
        bias = self.bias.float() if self.bias is not None else None
        return torch.nn.functional.linear(xq, wq, bias)

    torch.nn.Linear.forward = fp8_linear
    try:
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            return model(**inp, output_hidden_states=True)
    finally:
        torch.nn.Linear.forward = orig


def run_forward(model, tok, prompt, device):
    inp = tok([prompt], return_tensors="pt").to(device)
    with torch.no_grad():
        return model(**inp, output_hidden_states=True)


def srr64_score(a, b, seed=1):
    a = a[0].float().cpu().numpy()
    b = b[0].float().cpu().numpy()
    T = min(a.shape[0], b.shape[0])
    D = a.shape[1]
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=Q_SRR, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    x = a[rows, cols]
    y = b[rows, cols]
    return abs(np.sum(np.sign(x) * (y - x))) / (np.sum(np.abs(x)) + 1e-12)


def projcos4_gap(a, b, seed=1):
    a = a[0].float().cpu().numpy()
    b = b[0].float().cpu().numpy()
    T, D = a.shape
    rng = np.random.default_rng(seed + 911)
    tok_idx = rng.choice(T, size=min(16, T), replace=False)
    R = np.random.default_rng(777 + seed).normal(0, 1 / np.sqrt(4), (D, 4))
    A = a[tok_idx] @ R
    B = b[tok_idx] @ R
    A = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-12)
    B = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-12)
    return float(np.mean(1 - np.sum(A * B, axis=1)))


def scalar16_score(a, b, seed=1):
    a = a[0].float().cpu().numpy().reshape(-1)
    b = b[0].float().cpu().numpy().reshape(-1)
    rng = np.random.default_rng(seed)
    flat = rng.choice(len(a), size=16, replace=False)
    return float(np.abs(a[flat] - b[flat]).max())


def main():
    device = "cuda"
    torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(MODEL)
    bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)

    print(f"deployment honest p99 (C2): srr64={HONEST_P99['srr64']:.4f}, projcos4={HONEST_P99['projcos4']:.6f}, scalar16={HONEST_P99['scalar16']:.4f}")

    scores = {p: {"W8A16": [], "W8A8": [], "FP8": [], "INT4": []}
              for p in ["srr64", "projcos4", "scalar16"]}

    for prompt in PROMPTS:
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            hs_ref = m_ref(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        variants = {}
        m_w = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb_cfg, device_map="cuda")
        with torch.no_grad():
            variants["W8A16"] = m_w(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        del m_w; torch.cuda.empty_cache()
        m_n = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        m_n = replace_w8a8(m_n)
        with torch.no_grad():
            variants["W8A8"] = m_n(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        del m_n; torch.cuda.empty_cache()
        m_f = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        variants["FP8"] = fp8_forward(m_f, tok, prompt, device).hidden_states[LAYER].detach().float()
        del m_f; torch.cuda.empty_cache()
        m_i = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        m_i = replace_linears(m_i, 4)
        with torch.no_grad():
            variants["INT4"] = m_i(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        del m_i; torch.cuda.empty_cache()
        del m_ref; torch.cuda.empty_cache()

        for v in ["W8A16", "W8A8", "FP8", "INT4"]:
            scores["srr64"][v].append(srr64_score(hs_ref, variants[v]))
            scores["projcos4"][v].append(projcos4_gap(hs_ref, variants[v]))
            scores["scalar16"][v].append(scalar16_score(hs_ref, variants[v]))
        print(f"  done {prompt[:24]}")

    print()
    print("=== P4b-v3: real precision cheating vs DEPLOYMENT honest threshold ===")
    print(f"SignRadial64(q=64) thr={HONEST_P99['srr64']:.4f} | ProjCos4 thr={HONEST_P99['projcos4']:.6f} | Scalar16 thr={HONEST_P99['scalar16']:.4f}")
    print()
    print(f"{'method':12s} | {'W8A16':>7s} {'W8A8':>6s} {'FP8':>5s} {'INT4':>6s}")
    for meth in ["srr64", "projcos4", "scalar16"]:
        thr = HONEST_P99[meth]
        row = [f"{meth:12s} |"]
        for v in ["W8A16", "W8A8", "FP8", "INT4"]:
            vals = np.array(scores[meth][v])
            tpr = float(np.mean(vals > thr))
            row.append(f"{tpr:>7.2f}")
        print(" ".join(row))
    print()
    print("=== Combination: SignRadial64 OR ProjCos4 ===")
    thr_s = HONEST_P99["srr64"]
    thr_p = HONEST_P99["projcos4"]
    row = ["OR-gate  |"]
    for v in ["W8A16", "W8A8", "FP8", "INT4"]:
        s = np.array(scores["srr64"][v])
        p = np.array(scores["projcos4"][v])
        tpr = float(np.mean((s > thr_s) | (p > thr_p)))
        row.append(f"{tpr:>7.2f}")
    print(" ".join(row))


if __name__ == "__main__":
    main()
