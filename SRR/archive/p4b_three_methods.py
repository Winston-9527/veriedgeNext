"""Three-method comparison on real W8A8 cheating (RTX3090).

For each prompt: honest BF16 reference, then W8A8-cheated forward. Measure
whether Scalar16, ProjCos4, SignRadial detect the cheating (vs their own
honest-hetero calibrated threshold). Uses native W8A8 (torch._int_mm).
"""

import sys, numpy as np, torch
sys.path.insert(0, ".")
from p4b_native_w8a8 import (NativeW8A8Linear, replace_linears_w8a8_native,
                             quantize_int8_sym, MODEL, PROMPTS, LAYER, run_forward)

MODEL_PATH = "workspace/models/Qwen3-0.6B"

def srr(a, b):
    a=a[0].reshape(-1).float().cpu().numpy(); b=b[0].reshape(-1).float().cpu().numpy()
    return abs(np.sum(np.sign(a)*(b-a)))/(np.sum(np.abs(a))+1e-12)

def main():
    device="cuda"; torch.set_grad_enabled(False)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok=AutoTokenizer.from_pretrained(MODEL_PATH)
    srr_scores=[]; proj_scores=[]; scalar_scores=[]
    for prompt in PROMPTS:
        m_ref=AutoModelForCausalLM.from_pretrained(MODEL_PATH, torch_dtype=torch.float16, device_map="cuda")
        inp=tok([prompt],return_tensors="pt").to(device)
        with torch.no_grad():
            hs_ref=m_ref(**inp,output_hidden_states=True).hidden_states[LAYER].detach().float()
        m_c=AutoModelForCausalLM.from_pretrained(MODEL_PATH, torch_dtype=torch.float16, device_map="cuda")
        m_c=replace_linears_w8a8_native(m_c)
        with torch.no_grad():
            hs_c=m_c(**inp,output_hidden_states=True).hidden_states[LAYER].detach().float()
        # SignRadial
        srr_scores.append(srr(hs_ref, hs_c))
        # ProjCos: mean(1-cos) on sampled tokens
        r=hs_ref[0]; c=hs_c[0]
        rn=r/torch.norm(r,dim=-1,keepdim=True); cn=c/torch.norm(c,dim=-1,keepdim=True)
        proj_scores.append(float((1-(rn*cn).sum(-1)).mean()))
        # Scalar: max abs diff on sampled coords (use full tensor here as proxy)
        scalar_scores.append(float((hs_ref-hs_c).abs().max()))
        del m_ref,m_c; torch.cuda.empty_cache()
    print("=== Three methods on W8A8 cheating (layer 16) ===")
    print(f"  SignRadial: mean={np.mean(srr_scores):.4f}  (detect threshold ~0.02-0.06)")
    print(f"  ProjCos   : mean gap={np.mean(proj_scores):.6f}  (need honest gap baseline to threshold)")
    print(f"  Scalar16  : mean max-abs-diff={np.mean(scalar_scores):.4f} (absolute, needs honest baseline)")
    # honest reference for proj/scalar (rerun honest vs honest)
    hg=[]; hd=[]
    for prompt in PROMPTS[:4]:
        m=AutoModelForCausalLM.from_pretrained(MODEL_PATH, torch_dtype=torch.float16, device_map="cuda")
        inp=tok([prompt],return_tensors="pt").to(device)
        with torch.no_grad():
            h1=m(**inp,output_hidden_states=True).hidden_states[LAYER].detach().float()
            h2=m(**inp,output_hidden_states=True).hidden_states[LAYER].detach().float()
        r=h1[0]; c=h2[0]; rn=r/torch.norm(r,dim=-1,keepdim=True); cn=c/torch.norm(c,dim=-1,keepdim=True)
        hg.append(float((1-(rn*cn).sum(-1)).mean()))
        hd.append(float((h1-h2).abs().max()))
        del m; torch.cuda.empty_cache()
    print(f"  honest~honest: proj gap mean={np.mean(hg):.6f}, scalar max-abs={np.mean(hd):.4f}")
    print(f"  -> proj W8A8 gap / honest gap = {np.mean(proj_scores)/max(np.mean(hg),1e-9):.1f}x")
    print(f"  -> scalar W8A8 / honest = {np.mean(scalar_scores)/max(np.mean(hd),1e-9):.1f}x")

if __name__=="__main__":
    main()
