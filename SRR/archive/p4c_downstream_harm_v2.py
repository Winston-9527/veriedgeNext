"""P4c (v2): Downstream-harm coupling — W8A16 vs W8A8 vs honest.

Focused version on the two STABLE precision-cheating configs on CUDA
(INT8/FP8/INT4 decode is numerically unstable: INT8 explodes at layer 16,
FP8 produces NaN — see diagnosis). W8A16 and W8A8 are the meaningful
downstream-harm comparison:

  - W8A16 (weight-only int8): SignRadial invisible (0.005). Question: does it
    still harm output? If yes, it is a REAL blind spot needing output-level
    detection. If no (output fine), invisible is "correct rejection".
  - W8A8 (weight+act int8): SignRadial detectable (0.08). Question: does its
    drift correspond to real output harm?

For each prompt, greedy-generate 32 tokens with honest / W8A16 / W8A8 and
measure boundary SignRadial (layer 16), token disagreement vs honest, KL of
token distributions, and (surrogate for compute saving) the quantization level.
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
    "List three reasons why the sky is blue.",
    "What is the square root of 144?",
    "Describe the water cycle briefly.",
    "Give a recipe for chocolate chip cookies.",
]
MAX_NEW = 32
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


class LowPrecLinear(torch.nn.Module):
    def __init__(self, w, b, bits):
        super().__init__()
        self.register_buffer("w", w.detach().float())
        self.register_buffer("b", b.detach().float())
        self.bits = bits

    def forward(self, x):
        wq, _ = quantize_tensor(self.w.to(x.device), self.bits)
        xq, _ = quantize_tensor(x, self.bits)
        return torch.nn.functional.linear(xq, wq, self.b.to(x.device).float())


def replace_linears(model, bits):
    for name, module in list(model.named_children()):
        if isinstance(module, torch.nn.Linear):
            setattr(model, name, LowPrecLinear(module.weight.data, module.bias.data if module.bias is not None else torch.zeros(module.out_features), bits))
        else:
            replace_linears(module, bits)
    return model


def srr_score(a, b):
    a = a[0].reshape(-1).float().cpu().numpy()
    b = b[0].reshape(-1).float().cpu().numpy()
    P = np.sum(np.sign(a) * (b - a))
    B = np.sum(np.abs(a))
    return abs(P) / (B + 1e-12)


def generate(model, tok, prompt, device, max_new=MAX_NEW):
    inputs = tok([prompt], return_tensors="pt").to(device)
    gen_tokens = inputs["input_ids"]
    logits_seq = []
    past = None
    with torch.no_grad():
        for _ in range(max_new):
            out = model(input_ids=gen_tokens if past is None else gen_tokens[:, -1:], past_key_values=past, use_cache=True)
            past = out.past_key_values
            logits = out.logits[:, -1]
            logits_seq.append(logits.cpu())
            next_tok = logits.argmax(dim=-1).unsqueeze(0)
            gen_tokens = torch.cat([gen_tokens, next_tok], dim=1)
    return gen_tokens[:, inputs["input_ids"].shape[1]:], torch.stack(logits_seq, dim=1)[0]


def token_disagreement(ref_tokens, cand_tokens):
    n = min(ref_tokens.shape[-1], cand_tokens.shape[-1])
    return float((ref_tokens[0, :n] != cand_tokens[0, :n]).float().mean())


def kl_div(ref_logits, cand_logits):
    n = min(ref_logits.shape[0], cand_logits.shape[0])
    r = ref_logits[:n].float().softmax(-1) + 1e-9
    c = cand_logits[:n].float().log_softmax(-1)
    return float((r * (r.log() - c)).sum(-1).mean())


def main():
    device = "cuda"
    torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    tok = AutoTokenizer.from_pretrained(MODEL)
    bnb_cfg = BitsAndBytesConfig(load_in_8bit=True)

    results = {"W8A16": {"srr": [], "disagree": [], "kl": []},
               "W8A8": {"srr": [], "disagree": [], "kl": []}}

    print("=== P4c: downstream-harm coupling (W8A16 vs W8A8) ===")
    print(f"{'prompt':26s} | {'W8A16 srr/dis/KL':>22s} | {'W8A8 srr/dis/KL':>22s}")
    for prompt in PROMPTS:
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            hs_ref = m_ref(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        ref_tokens, ref_logits = generate(m_ref, tok, prompt, device)
        del m_ref; torch.cuda.empty_cache()

        row = [f"{prompt[:24]:26s}"]
        for label, build in [
            ("W8A16", lambda: AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb_cfg, device_map="cuda")),
            ("W8A8", lambda: replace_linears(AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda"), 8)),
        ]:
            m_c = build()
            with torch.no_grad():
                hs_c = m_c(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
            cand_tokens, cand_logits = generate(m_c, tok, prompt, device)
            srr = srr_score(hs_ref, hs_c)
            dis = token_disagreement(ref_tokens, cand_tokens)
            kl = kl_div(ref_logits, cand_logits)
            results[label]["srr"].append(srr)
            results[label]["disagree"].append(dis)
            results[label]["kl"].append(kl)
            row.append(f"{srr:.3f}/{dis:.2f}/{kl:.1f}")
            del m_c; torch.cuda.empty_cache()
        print("  " + " | ".join(row))

    print()
    print("=== Aggregate (8 prompts, 32 generated tokens each) ===")
    print(f"{'config':8s} {'SignRadial':>10s} {'tok disagree':>13s} {'KL':>8s}")
    for label in ["W8A16", "W8A8"]:
        r = results[label]
        print(f"  {label:8s} {np.mean(r['srr']):>10.4f} {np.mean(r['disagree']):>13.3f} {np.mean(r['kl']):>8.4f}")
    print()
    print("Interpretation:")
    print("  - W8A16 invisible to SignRadial (~0.005) but DOES it harm output?")
    print("  - W8A8 detectable (0.08) — does its drift correspond to harm?")


if __name__ == "__main__":
    main()
