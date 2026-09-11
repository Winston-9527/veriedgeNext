"""Native precision cheating on RTX3090.

NATIVE = real low-precision kernels, not fp32 simulation:
- W8A16: bitsandbytes load_in_8bit (real int8 weight kernels, fp16 activations).
- W8A8 : real int8xint8->int32 matmul via torch._int_mm. Weights and
  activations are quantized to int8 (per-channel weight scale, per-token act
  scale), matmul in native int8 kernels, dequantized to fp32. This is how
  real W8A8 (e.g. vLLM, TensorRT-LLM) works.

Compare native vs simulated W8A8 drift to confirm they agree, then measure
SignRadial detection.
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


def quantize_int8_sym(x, per_channel=True):
    """Symmetric int8 quantization. Returns (q_int8, scale, zero)."""
    x = x.float()
    qmax = 127.0
    if per_channel and x.dim() >= 2:
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


class NativeW8A8Linear(torch.nn.Module):
    """Weight + activation int8, NATIVE int8xint8->int32 matmul via torch._int_mm."""

    def __init__(self, w, b):
        super().__init__()
        # pre-quantize weight to int8 per-output-channel, keep fp32 scale
        self.register_buffer("w_fp32", w.detach().float())
        self.register_buffer("b", b.detach().float())
        self.register_buffer("w_int8", torch.zeros(w.shape, dtype=torch.int8))
        self.register_buffer("w_scale", torch.zeros(w.shape[0]))
        self._requantize()

    def _requantize(self):
        q, scale = quantize_int8_sym(self.w_fp32, per_channel=True)
        self.w_int8.copy_(q)
        self.w_scale.copy_(scale)

    def forward(self, x):
        xq, x_scale = quantize_int8_sym(x, per_channel=False)  # per-tensor act scale
        w_int8 = self.w_int8.to(x.device)
        w_scale = self.w_scale.to(x.device)
        # native int8 x int8 -> int32 matmul
        # weight [out, in], x [..., in] -> need x as [M, K], w as [K, N]
        orig_shape = xq.shape
        xq_2d = xq.reshape(-1, xq.shape[-1])
        M = xq_2d.shape[0]
        w_t = w_int8.t().contiguous()  # [in, out]
        # torch._int_mm needs M > 16; pad to a safe multiple (32)
        if M <= 16:
            pad = 32 - M
            xq_2d = torch.nn.functional.pad(xq_2d, (0, 0, 0, pad))
        out = torch._int_mm(xq_2d, w_t)  # [M, out] int32
        if M <= 16:
            out = out[:M]
        # dequantize: out_fp32 = (xq * x_scale) @ (w_int8 * w_scale) = x_scale * out * w_scale
        x_scale_v = x_scale.float()
        w_scale_v = w_scale.float()
        out_fp = out.float() * x_scale_v * w_scale_v.unsqueeze(0)
        out_fp = out_fp.reshape(*orig_shape[:-1], -1)
        return out_fp + self.b.to(x.device)


def replace_linears_w8a8_native(model):
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, NativeW8A8Linear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features)))
        else:
            replace_linears_w8a8_native(module)
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
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL)
    print("=== Native precision cheating: W8A8 via torch._int_mm (real int8 matmul) ===")
    print(f"{'prompt':34s} {'honest':>8s} {'W8A8-native':>12s}")

    scores = []
    for prompt in PROMPTS:
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        hs_ref = [h.detach().float() for h in run_forward(m_ref, tok, prompt, device).hidden_states]
        hs_h = [h.detach().float() for h in run_forward(m_ref, tok, prompt, device).hidden_states]
        hh = srr_score(hs_ref[LAYER], hs_h[LAYER])

        m_native = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        m_native = replace_linears_w8a8_native(m_native)
        hs_n = [h.detach().float() for h in run_forward(m_native, tok, prompt, device).hidden_states]
        sn = srr_score(hs_ref[LAYER], hs_n[LAYER])
        scores.append(sn)
        print(f"  {prompt[:32]:34s} {hh:>8.4f} {sn:>12.4f}")

        del m_ref, m_native
        torch.cuda.empty_cache()

    print()
    print(f"W8A8-native SignRadial: mean={np.mean(scores):.4f} min={np.min(scores):.4f} max={np.max(scores):.4f}")
    print("Compare with P4b simulated W8A8: mean=0.083 min=0.044 max=0.131")
    print("Deployment honest p99: C1=0.060, C2=0.032, C3=0.012")


if __name__ == "__main__":
    main()
