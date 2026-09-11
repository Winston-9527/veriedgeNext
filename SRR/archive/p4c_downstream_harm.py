"""P4c: Downstream-harm coupling on RTX3090.

Links precision-cheating activation drift (SignRadial at a boundary) to OUTPUT
degradation. For each prompt, generate with honest BF16 and each cheating
config (INT8/FP8/INT4/W8A8/W8A16), measuring:
  - boundary SignRadial (prefill, layer 16)
  - token disagreement rate (top-1 differs from honest at each position)
  - KL divergence of token distributions vs honest
  - (compute saving is the quantization level, a proxy for the attacker's gain)

Answer: can SignRadial detect precision cheating that ACTUALLY degrades output?
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


def quantize_fp8(x, e4m3=True):
    x = x.float()
    try:
        dtype = torch.float8_e4m3fn if e4m3 else torch.float8_e5m2
        return x.to(dtype).to(torch.float32)
    except Exception:
        return (torch.round(x * 8.0) / 8.0) if e4m3 else (torch.round(x * 4.0) / 4.0)


def fp8_forward(model, tok, prompt, device):
    orig = torch.nn.Linear.forward

    def fp8_linear(self, x):
        wq = quantize_fp8(self.weight.detach(), e4m3=True)
        xq = quantize_fp8(x, e4m3=True)
        bias = self.bias.float() if self.bias is not None else None
        return torch.nn.functional.linear(xq, wq, bias)

    torch.nn.Linear.forward = fp8_linear
    try:
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            return model(**inp, output_hidden_states=True, use_cache=True)
    finally:
        torch.nn.Linear.forward = orig


def srr_score(a, b):
    a = a[0].reshape(-1).float().cpu().numpy()
    b = b[0].reshape(-1).float().cpu().numpy()
    P = np.sum(np.sign(a) * (b - a))
    B = np.sum(np.abs(a))
    return abs(P) / (B + 1e-12)


def generate(model, tok, prompt, device, max_new=MAX_NEW):
    """Greedy generate, return (tokens, logits_seq)."""
    inputs = tok([prompt], return_tensors="pt").to(device)
    gen_tokens = inputs["input_ids"]
    logits_seq = []
    past = None
    with torch.no_grad():
        for _ in range(max_new):
            out = model(input_ids=gen_tokens if past is None else gen_tokens[:, -1:], past_key_values=past, use_cache=True)
            past = out.past_key_values
            logits = out.logits[:, -1]  # [1, vocab]
            logits_seq.append(logits.cpu())
            next_tok = logits.argmax(dim=-1).unsqueeze(0)
            gen_tokens = torch.cat([gen_tokens, next_tok], dim=1)
    return gen_tokens[:, inputs["input_ids"].shape[1]:], torch.stack(logits_seq, dim=1)[0]  # [new_tokens, vocab]


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

    # config builders: (label, build_fn) where build_fn(model) applies cheating
    print("=== P4c: downstream-harm coupling ===")
    print("configs: BF16(honest) / INT8 / FP8 / INT4 / W8A8 / W8A16")

    results = {c: {"srr": [], "disagree": [], "kl": []} for c in ["INT8", "FP8", "INT4", "W8A8", "W8A16"]}

    for prompt in PROMPTS:
        # honest reference
        m_ref = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
        # boundary activation (prefill) for SignRadial
        inp = tok([prompt], return_tensors="pt").to(device)
        with torch.no_grad():
            hs_ref = m_ref(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
        ref_tokens, ref_logits = generate(m_ref, tok, prompt, device)

        for label in ["INT8", "FP8", "INT4", "W8A8", "W8A16"]:
            if label == "FP8":
                m_c = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
                with torch.no_grad():
                    out_c = fp8_forward(m_c, tok, prompt, device)
                    hs_c = out_c.hidden_states[LAYER].detach().float()
                cand_tokens, cand_logits = generate(m_c, tok, prompt, device)
            elif label == "W8A16":
                m_c = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb_cfg, device_map="cuda")
                with torch.no_grad():
                    hs_c = m_c(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
                cand_tokens, cand_logits = generate(m_c, tok, prompt, device)
            elif label == "W8A8":
                m_c = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
                m_c = replace_linears(m_c, 8)
                with torch.no_grad():
                    hs_c = m_c(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
                cand_tokens, cand_logits = generate(m_c, tok, prompt, device)
            else:  # INT4
                m_c = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float16, device_map="cuda")
                m_c = replace_linears(m_c, 4)
                with torch.no_grad():
                    hs_c = m_c(**inp, output_hidden_states=True).hidden_states[LAYER].detach().float()
                cand_tokens, cand_logits = generate(m_c, tok, prompt, device)

            results[label]["srr"].append(srr_score(hs_ref, hs_c))
            results[label]["disagree"].append(token_disagreement(ref_tokens, cand_tokens))
            results[label]["kl"].append(kl_div(ref_logits, cand_logits))
            del m_c
            torch.cuda.empty_cache()

        del m_ref
        torch.cuda.empty_cache()
        print(f"  done {prompt[:24]}")

    print()
    print(f"{'config':8s} {'SignRadial':>10s} {'tok disagree':>13s} {'KL':>8s}")
    for label in ["INT8", "FP8", "INT4", "W8A8", "W8A16"]:
        r = results[label]
        print(f"  {label:8s} {np.mean(r['srr']):>10.4f} {np.mean(r['disagree']):>13.3f} {np.mean(r['kl']):>8.4f}")
    print("honest~honest: SignRadial~0, disagree~0, KL~0")


if __name__ == "__main__":
    main()
