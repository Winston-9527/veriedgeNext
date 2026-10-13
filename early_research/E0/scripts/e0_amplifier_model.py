#!/usr/bin/env python3
"""公开放大器能省多少请求：解析模型 + 用 E0 实测误差分布做的半实证估计。

放大器（公开）：每个输出位置计算 s = ⟨k, h⟩，读出位 b = sign(sin(ω·s))，
再用 logit 偏置让输出 token 落在 b 指定的词表半区。验证方用全精度参考算出正确的 b₀。

误差模型：执行栈算出的是 s + e。
  - 解析部分：e ~ N(0, σ²)，诚实 σ_h，作弊 σ_q = ρ·σ_h。
  - 实证部分：e 取 E0 里同一 context 上"参考 top-1/top-2 logit 差"的偏差（实测分布，含重尾）。
    假设：读出 s 也是末层隐状态的一个线性泛函，误差形状与 logit 差的误差相同，尺度由 ω 吸收。
相位 φ = ω·s mod 2π 视为均匀分布。

翻转：sign(sin(φ + ω·e)) ≠ sign(sin(φ))。
输出信道：token 只以概率 1-η 落在 b 指定的半区（η 由偏置强度和文本熵决定），
  观测失配率 = η + (1-2η)·p。
升级攻击（只有尾分片能做）：攻击者知道自己算出的相位 φ' = φ + ω·e_q，
  把离 sin 零点最近的 c 比例位置改用规格精度栈重算。

用法（在 run_dir 下）：
    python scripts/e0_amplifier_model.py --out analysis/amplifier
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from e0_common import chernoff_n, exact_binomial_design, load_capture

ALPHA = BETA = 1e-3
ETAS = [0.0, 0.1, 0.2, 0.3]
ESC = [0.0, 0.05, 0.10, 0.20]
X_GRID = np.geomspace(0.02, 20, 120)   # x = ω·σ_h（以诚实误差尺度度量的放大倍数）


# ---------------------------------------------------------------- 通用

def wilson_upper(p: float, n: int, z: float = 1.645) -> float:
    c = p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, c / (1 + z * z / n))


def n_needed(p_h: float, p_q: float) -> float:
    d = exact_binomial_design(p_h, p_q, ALPHA, BETA)
    return float(d["N"]) if d else math.inf


def channel(p: float, eta: float) -> float:
    return eta + (1 - 2 * eta) * p


def flip_rate(phase: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """逐位置是否翻转：sign(sin(φ+δ)) ≠ sign(sin φ)。"""
    return np.sign(np.sin(phase + delta)) != np.sign(np.sin(phase))


# ---------------------------------------------------------------- 1. 解析：高斯误差

def analytic(rho_list, n_mc=400_000, seed=0) -> list[dict]:
    rng = np.random.default_rng(seed)
    phase = rng.uniform(0, 2 * np.pi, n_mc)
    z = rng.standard_normal(n_mc)
    ph_x = {x: flip_rate(phase, x * z).mean() for x in X_GRID}
    rows = []
    for rho in rho_list:
        pq_x = {x: flip_rate(phase, rho * x * z).mean() for x in X_GRID}
        for eta in ETAS:
            x = min(X_GRID, key=lambda x: chernoff_n(channel(ph_x[x], eta), channel(pq_x[x], eta), ALPHA))
            rows.append({"rho": rho, "eta": eta, "x_opt": float(x), "p_h": float(ph_x[x]),
                         "p_q": float(pq_x[x]),
                         "N_tokens": n_needed(channel(ph_x[x], eta), channel(pq_x[x], eta))})
    return rows


# ---------------------------------------------------------------- 2. 半实证：E0 实测误差

def gap_errors(ref, cap) -> np.ndarray:
    """逐 context 的 logit 差偏差；参考 top-1/top-2 不都在该栈 top-5 内的位置记为 NaN。"""
    rid, rv = ref["topk_ids"], ref["topk_val"]
    ids, v = cap["topk_ids"], cap["topk_val"]
    m1 = ids == rid[:, :1]
    m2 = ids == rid[:, 1:2]
    ok = m1.any(1) & m2.any(1)
    v1 = np.where(m1, v, 0).sum(1)
    v2 = np.where(m2, v, 0).sum(1)
    e = (v1 - v2) - (rv[:, 0] - rv[:, 1])
    e[~ok] = np.nan
    return e


def empirical(run: Path, honest: list[str], cheats: list[str], esc_to: str,
              passive_report: Path | None, seed=0) -> list[dict]:
    rng = np.random.default_rng(seed)
    ref = load_capture(run / "captures/torch_fp32.npz")
    E = {n: gap_errors(ref, load_capture(run / f"captures/{n}.npz"))
         for n in dict.fromkeys(honest + cheats + [esc_to])}
    valid = np.all([np.isfinite(E[n]) for n in E], axis=0)
    M = int(valid.sum())
    phase = rng.uniform(0, 2 * np.pi, M)
    Eh = {n: E[n][valid] for n in honest}
    e_esc = E[esc_to][valid]
    passive = json.loads(passive_report.read_text())["C_escalation"] if passive_report else {}

    # 用诚实栈误差的中位数绝对值作为 σ_h 的尺度（x = ω·σ_h）
    sig_h = max(np.median(np.abs(Eh[n])) for n in honest)
    ph_x = {x: wilson_upper(max(flip_rate(phase, (x / sig_h) * Eh[n]).mean() for n in honest), M)
            for x in X_GRID}
    rows = []
    for c in cheats:
        eq = E[c][valid]
        pc = passive.get(c, {}).get("curve", [])
        for esc in ESC:
            pq_x = {}
            for x in X_GRID:
                w = x / sig_h
                # 攻击者：按自己算出的相位，把离零点最近的 esc 比例位置改用升级目标栈的误差
                dist = np.abs(((phase + w * eq + np.pi / 2) % np.pi) - np.pi / 2)
                use_esc = np.zeros(M, bool)
                k = int(round(esc * M))
                if k:
                    use_esc[np.argsort(dist)[:k]] = True
                pq_x[x] = flip_rate(phase, w * np.where(use_esc, e_esc, eq)).mean()
            pas = next((pt["best_band"] for pt in pc if abs(pt["target_esc_rate"] - esc) < 1e-9), None)
            for eta in ETAS:
                x = min(X_GRID, key=lambda x: chernoff_n(channel(ph_x[x], eta), channel(pq_x[x], eta), ALPHA))
                rows.append({"cheat": c, "eta": eta, "esc": esc, "x_opt": float(x),
                             "p_h_ub": float(ph_x[x]), "p_q": float(pq_x[x]),
                             "N_tokens": n_needed(channel(ph_x[x], eta), channel(pq_x[x], eta)),
                             "passive_N_tokens": pas.get("N_exact") if pas else None,
                             "passive_band_frac": pas.get("frac") if pas else None})
    return rows


def fmt(n):
    return "∞" if n is None or (isinstance(n, float) and not math.isfinite(n)) else f"{int(n)}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    ana = analytic([1.3, 2.0, 3.0, 4.4, 10.0])
    scen = {
        "spec_bf16": dict(honest=["torch_bf16", "mlx_bf16", "apple_mps_bf16", "apple_mlx_bf16",
                                  "torch_fp16", "apple_mps_fp16"],
                          esc_to="torch_bf16", report="analysis/spec_bf16/e0_summary.json"),
        "spec_8bit_nobnb": dict(honest=["torch_bf16", "mlx_bf16", "apple_mps_bf16", "apple_mlx_bf16",
                                        "torch_fp16", "apple_mps_fp16", "torch_rtn_w8g128", "mlx_8bit",
                                        "apple_mlx_8bit"],
                                esc_to="mlx_8bit", report="analysis/spec_8bit_nobnb/e0_summary.json"),
    }
    cheats = ["torch_gptq_w4g128_L24-35", "torch_gptq_w4g128_L12-23", "torch_gptq_w4g128_L0-11",
              "mlx_q4_L24-35", "torch_gptq_w4g128", "mlx_q4"]
    emp = {k: empirical(args.run, v["honest"], cheats, v["esc_to"], args.run / v["report"])
           for k, v in scen.items()}
    (args.out / "amplifier_model.json").write_text(json.dumps({"analytic": ana, "empirical": emp}, indent=2))

    L = ["# 公开放大器 vs 被动 canary：所需 token 数（α=β=1e-3）", "",
         "## 1. 解析模型（高斯误差，ρ=σ_q/σ_h；ω 由验证方最优选取；无升级）", "",
         "| ρ | η=0 | η=0.1 | η=0.2 | η=0.3 | 最优 ω·σ_h（η=0） | p_h / p_q（η=0） |", "|---|---|---|---|---|---|---|"]
    for rho in sorted({r["rho"] for r in ana}):
        rr = {r["eta"]: r for r in ana if r["rho"] == rho}
        r0 = rr[0.0]
        L.append(f"| {rho} | " + " | ".join(fmt(rr[e]["N_tokens"]) for e in ETAS)
                 + f" | {r0['x_opt']:.2f} | {r0['p_h']:.3f} / {r0['p_q']:.3f} |")
    for k, rows in emp.items():
        L += ["", f"## 2. 半实证（{k}；E0-4B 实测误差；被动 = E0 实测最佳区间，单位为 token）", "",
              "| 作弊栈 | 升级 | 被动 N | 放大器 N（η=0 / 0.1 / 0.2 / 0.3） | η=0.2 时 p_h / p_q |",
              "|---|---|---|---|---|"]
        for c in cheats:
            for esc in ESC:
                rs = {r["eta"]: r for r in rows if r["cheat"] == c and r["esc"] == esc}
                r2 = rs[0.2]
                L.append(f"| `{c}` | {esc:.0%} | {fmt(rs[0.0]['passive_N_tokens'])} | "
                         + " / ".join(fmt(rs[e]["N_tokens"]) for e in ETAS)
                         + f" | {r2['p_h_ub']:.4f} / {r2['p_q']:.4f} |")
    (args.out / "AMPLIFIER_REPORT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
