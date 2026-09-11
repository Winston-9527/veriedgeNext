"""P1b: Real BF16 -> low-precision precision cheating.

The malicious node runs a REAL layer-wise low-precision forward:
  - each Linear layer: quantize W to target precision (per-channel scale),
    quantize input activation, do the matmul with quantized operands
    (accumulated in fp32), dequantize output, feed next layer.
  - boundary activations are cast back to BF16 before the verifier sees them.
This is NOT "quantize output then dequantize" — every layer's arithmetic
happens on low-precision values, so quantization error propagates layer by
layer (the real "cheating compute" effect).

Runs on the mini (M4/MPS) where the model lives. Same device, same model,
same input, only numerical precision differs between honest and cheated.
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


def quantize_tensor(x, bits, dtype="int", per_channel=True):
    """Quantize tensor to {bits}-bit then dequantize (symmetric).

    Operates in fp32 (MPS limitation: no native low-precision matmul); the
    VALUES are rounded to the int{bits} grid so per-layer quantization error
    propagates like a real low-precision forward. Returns (dequantized_fp32,
    scale).
    """
    x = x.float()  # fp16 input -> fp32 first (MPS needs consistent dtypes)
    if dtype == "int":
        qmin = -(2 ** (bits - 1))
        qmax = 2 ** (bits - 1) - 1
        if per_channel and x.dim() >= 2:
            scale = x.abs().amax(dim=tuple(range(1, x.dim()))) / qmax
            scale = torch.clamp(scale, min=1e-8)
            shape = [1] * x.dim()
            shape[0] = -1
            scale_view = scale.view(shape)
        else:
            scale = x.abs().max() / qmax
            scale_view = scale
        q = torch.round(x / scale_view).clamp(qmin, qmax)
        return q * scale_view, scale
    # fp8
    raise NotImplementedError


def quantize_fp8(x, e4m3=True):
    """Round to FP8 (E4M3 or E5M2) grid, return dequantized float.

    Values are rounded to the fp8 mantissa/exponent grid (real quantization),
    returned as fp32 so the matmul runs on MPS. This captures the fp8 rounding
    error per layer; accumulation is fp32 (MPS limitation, disclosed).
    """
    x = x.float()
    has_fp8 = hasattr(torch, "float8_e4m3fn") and hasattr(torch, "float8_e5m2")
    if has_fp8:
        dtype = torch.float8_e4m3fn if e4m3 else torch.float8_e5m2
        try:
            return x.to(dtype).to(torch.float32)
        except Exception:
            pass
    # manual fp8 grid rounding fallback
    if e4m3:
        # E4M3: 1 sign, 4 exp, 3 mantissa -> round to 2^-3
        return torch.round(x * 8.0) / 8.0
    else:
        # E5M2: 1 sign, 5 exp, 2 mantissa -> round to 2^-2
        return torch.round(x * 4.0) / 4.0


class LowPrecLinear(torch.nn.Module):
    """A Linear whose VALUES are quantized to {bits}-bit (weights + activation).

    NOTE on honesty: the operands are the QUANTIZED values (rounded to the
    int8/int4 grid), so per-layer quantization error propagates exactly like a
    real low-precision forward. The matmul itself runs in fp32 (MPS has no
    int8 matmul kernel); accumulation precision is a hardware limitation we
    disclose, not a change to the quantization model.
    """

    def __init__(self, w: torch.Tensor, b: torch.Tensor, bits: int, quant_act: bool):
        super().__init__()
        self.register_buffer("w", w.detach().float())
        self.register_buffer("b", b.detach().float())
        self.bits = bits
        self.quant_act = quant_act

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        wq, _ = quantize_tensor(self.w.to(x.device), self.bits)  # fp32, per-output-channel
        if self.quant_act:
            xq, _ = quantize_tensor(x, self.bits, per_channel=False)  # fp32, per-tensor
        else:
            xq = x.float()
        # fp32 matmul on quantized values (MPS limitation: no low-precision mm)
        y = torch.nn.functional.linear(xq, wq, self.b.to(x.device).float())
        return y


def replace_linears(model, bits, quant_act=True):
    """Replace every nn.Linear with a LowPrecLinear at {bits}-bit precision."""
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, LowPrecLinear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features), bits, quant_act))
        else:
            replace_linears(module, bits, quant_act)
    return model


def run_forward(model, tok, prompt, device):
    inp = tok([prompt], return_tensors="pt").to(device)
    with torch.no_grad():
        out = model(**inp, output_hidden_states=True)
    return out


def main():
    device = "mps"
    torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL)
    prompts = [
        "The capital of France is",
        "Explain the theory of relativity in one paragraph.",
        "Write a Python function to compute fibonacci numbers.",
        "What is the difference between TCP and UDP?",
        "Summarize the plot of Hamlet.",
    ]

    print("=== P1b: real low-precision forward, boundary activation drift ===")
    print(f"{'prompt':34s} {'layer':>5s} {'honest~honest':>14s} {'BF16->INT8':>12s} {'BF16->FP8':>10s} {'BF16->INT4':>11s}")

    for prompt in prompts:
        # honest BF16 reference
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float16, device_map=device)
        out_ref = run_forward(m_ref, tok, prompt, device)
        hs_ref = [h.detach().float() for h in out_ref.hidden_states]

        # honest rerun (BF16 same) — control
        out_h = run_forward(m_ref, tok, prompt, device)
        hs_h = [h.detach().float() for h in out_h.hidden_states]

        # cheated: INT8, FP8, INT4 — fresh model each, replace linears
        results = {}
        for label, bits, qa in [("INT8", 8, True), ("FP8", None, True), ("INT4", 4, True)]:
            m_cheat = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float16, device_map=device)
            if label == "FP8":
                # fp8: use manual fp8 rounding on weights + activations
                # implement via quantize_fp8 hook
                out_c = run_fp8_forward(m_cheat, tok, prompt, device)
            else:
                m_cheat = replace_linears(m_cheat, bits, qa)
                out_c = run_forward(m_cheat, tok, prompt, device)
            hs_c = [h.detach().float() for h in out_c.hidden_states]
            results[label] = hs_c
            del m_cheat
            torch.mps.empty_cache() if hasattr(torch, "mps") else None

        # measure at middle layer (index 16)
        layer = 16
        # SignRadial-like relative radial diff
        def srr_score(a, b):
            a = a[0].reshape(-1).cpu().numpy()
            b = b[0].reshape(-1).cpu().numpy()
            P = np.sum(np.sign(a) * (b - a))
            B = np.sum(np.abs(a))
            return abs(P) / (B + 1e-12)

        hh = srr_score(hs_ref[layer], hs_h[layer])
        row = [f"{prompt[:32]:34s}", f"{layer:>5d}", f"{hh:>14.4f}"]
        for label in ["INT8", "FP8", "INT4"]:
            row.append(f"{srr_score(hs_ref[layer], results[label][layer]):>10.4f}")
        print("  " + " ".join(row))
        del m_ref
        torch.mps.empty_cache() if hasattr(torch, "mps") else None


def run_fp8_forward(model, tok, prompt, device):
    """FP8 forward: round every Linear weight+activation to fp8 manually."""
    # monkeypatch nn.Linear forward to round to fp8
    orig_linear = torch.nn.Linear.forward

    def fp8_linear(self, x):
        wq = quantize_fp8(self.weight.detach(), e4m3=True).float()
        xq = quantize_fp8(x, e4m3=True).float()
        bias = self.bias.float() if self.bias is not None else None
        return torch.nn.functional.linear(xq, wq, bias)

    torch.nn.Linear.forward = fp8_linear
    try:
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            return model(**inp, output_hidden_states=True)
    finally:
        torch.nn.Linear.forward = orig_linear


if __name__ == "__main__":
    main()
