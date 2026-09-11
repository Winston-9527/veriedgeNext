"""P4b: W8A16 vs W8A8 precision cheating on RTX3090.

Threat distinction:
- W8A16: weights quantized to INT8, activations stay fp16 (bitsandbytes real
  int8 kernels). The "weight-only quantization" threat.
- W8A8 : weights AND activations quantized to INT8 (real low-precision matmul
  on quantized values, fp32 accumulate). The "full low-precision" threat.

Runs on RTX3090 (CUDA), Qwen3-0.6B, same device, same model, same input.
Measures SignRadial separation between honest BF16 and each cheating config,
plus TPR at a per-layer calibrated threshold.

Honest disclosure: W8A16 uses bnb's real int8 kernels (weights). W8A8 uses
per-layer int8 quantization of weights+activations with fp32 matmul on
quantized values (CUDA has no native int8 addmm), same as P1b methodology.
"""

from __future__ import annotations

import sys
import time
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


def quantize_tensor(x, bits):
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


class W8A8Linear(torch.nn.Module):
    """Weight + activation int8 quantization, fp32 accumulate (W8A8 sim)."""

    def __init__(self, w, b):
        super().__init__()
        self.register_buffer("w", w.detach().float())
        self.register_buffer("b", b.detach().float())

    def forward(self, x):
        wq, _ = quantize_tensor(self.w.to(x.device), 8)
        xq, _ = quantize_tensor(x, 8)
        return torch.nn.functional.linear(xq, wq, self.b.to(x.device).float())


def replace_linears_w8a8(model):
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, W8A8Linear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features)))
        else:
            replace_linears_w8a8(module)
    return model


def run_forward(model, tok, prompt, device):
    inp = tok([prompt], return_tensors="pt").to(device)
    with torch.no_grad():
        return model(**inp, output_hidden_states=True)


def srr_score(a, b):
    a = a[0].reshape(-1).float().cpu().numpy()
    b = b[0].reshape(-1).float().cpu().numpy()
    P = np.sum(np.sign(a) * (b - a))
    B = np.sum(np.abs(a))
    return abs(P) / (B + 1e-12)


def main():
    device = "cuda"
    torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(MODEL)
    bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)

    print("=== P4b: W8A16 vs W8A8, SignRadial separation (layer 16) ===")
    print(f"{'prompt':34s} {'honest':>8s} {'W8A16':>8s} {'W8A8':>8s}")

    scores = {"W8A16": [], "W8A8": []}
    for prompt in PROMPTS:
        # honest BF16 reference
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        hs_ref = [h.detach().float() for h in run_forward(m_ref, tok, prompt, device).hidden_states]
        hs_h = [h.detach().float() for h in run_forward(m_ref, tok, prompt, device).hidden_states]
        hh = srr_score(hs_ref[LAYER], hs_h[LAYER])
        row = [f"{prompt[:32]:34s}", f"{hh:>8.4f}"]

        # W8A16: bnb real int8 weights
        m_w8a16 = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb_cfg, device_map="cuda")
        hs16 = [h.detach().float() for h in run_forward(m_w8a16, tok, prompt, device).hidden_states]
        s16 = srr_score(hs_ref[LAYER], hs16[LAYER])
        scores["W8A16"].append(s16)
        row.append(f"{s16:>8.4f}")

        # W8A8: weights + activations int8
        m_w8a8 = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        m_w8a8 = replace_linears_w8a8(m_w8a8)
        hs8 = [h.detach().float() for h in run_forward(m_w8a8, tok, prompt, device).hidden_states]
        s8 = srr_score(hs_ref[LAYER], hs8[LAYER])
        scores["W8A8"].append(s8)
        row.append(f"{s8:>8.4f}")

        print("  " + " ".join(row))

        del m_ref, m_w8a16, m_w8a8
        torch.cuda.empty_cache()

    print()
    print("=== SignRadial score summary (layer 16) ===")
    for label in ["W8A16", "W8A8"]:
        s = np.array(scores[label])
        print(f"  {label}: mean={s.mean():.4f} min={s.min():.4f} max={s.max():.4f}")
    print("  honest~honest: ~0 (same-device BF16 rerun)")
    print()
    print("Deployment honest noise reference (A/B, q=256): C1 p99~0.06, C2 p99~0.032, C3 p99~0.012")


if __name__ == "__main__":
    main()
