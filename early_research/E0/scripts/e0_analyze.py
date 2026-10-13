#!/usr/bin/env python3
"""E0 第 3 步：被动 canary 基线 + 不确定性升级攻击分析。

对每个 context，"失配" = 该栈 top-1 ≠ 参考栈 top-1。输出四组结果：
  A. 各栈总体失配率（按 prompt 做 cluster bootstrap CI）
  B. 按参考 margin 分位数分箱的失配率；验证方可选的最佳 canary 区间
  C. 升级攻击：作弊栈在自身 margin < τ 时改用 --escalate-to 栈的输出；
     扫 τ 得到 (升级成本, 残余失配率, 所需 canary 数 N*) 曲线
  D. 量化器感知的 canary 挑选：验证方用 selector 栈模拟作弊，挑"会翻转且
     selector margin 最大"的 context 组成 canary 池，再在升级攻击下评估

用法：
    python e0_analyze.py --captures-dir captures --ref torch_fp32 \
        --honest torch_bf16,torch_fp16,mlx_bf16 --cheat torch_rtn_w4g128,mlx_q4 \
        --escalate-to torch_bf16 --selectors torch_rtn_w4g128 --out-dir analysis/spec_bf16
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np

from e0_common import chernoff_n, exact_binomial_design, load_capture

ESC_RATES = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50]
N_BINS = 10
POOL_SIZES = [50, 200, 1000]


# ---------------------------------------------------------------- helpers

def cluster_bootstrap(x: np.ndarray, clusters: np.ndarray, n_boot: int, rng) -> tuple[float, float]:
    """按 prompt 重采样的均值 95% CI（同一 prompt 内各位置相关）。"""
    uniq, inv = np.unique(clusters, return_inverse=True)
    sums = np.bincount(inv, weights=x.astype(float))
    cnts = np.bincount(inv)
    idx = rng.integers(0, len(uniq), size=(n_boot, len(uniq)))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wilson_upper(x: np.ndarray, z: float = 1.645) -> float:
    """失配率的单侧 95% Wilson 上界：p_h=0 的小样本不至于给出过于乐观的 N。"""
    n = len(x)
    if n == 0:
        return 1.0
    p = float(x.mean())
    c = p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, c / (1 + z * z / n))


def escalation_mask(own_margin: np.ndarray, rate: float, rng) -> np.ndarray:
    """攻击者重算自身 margin 最小的 rate 比例 context（随机打破平局，保证成本恰为 rate）。"""
    esc = np.zeros(len(own_margin), bool)
    k = int(round(rate * len(own_margin)))
    if k:
        esc[np.lexsort((rng.random(len(own_margin)), own_margin))[:k]] = True
    return esc


def design(p_h: float, p_q: float, alpha: float, beta: float) -> dict:
    """p_h 应传入保守估计（Wilson 上界）。"""
    d = {"p_h": p_h, "p_q": p_q, "N_chernoff": chernoff_n(p_h, p_q, alpha)}
    ex = exact_binomial_design(p_h, p_q, alpha, beta)
    d["N_exact"], d["k_exact"] = (ex["N"], ex["k"]) if ex else (None, None)
    return d


def finite(x: float) -> float | None:
    return None if x is None or not math.isfinite(x) else round(x, 2)


# ---------------------------------------------------------------- main analysis

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures-dir", type=Path, required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--honest", required=True, help="逗号分隔；规格精度下的诚实栈（不含 ref）")
    ap.add_argument("--cheat", required=True, help="逗号分隔；作弊栈")
    ap.add_argument("--escalate-to", required=True, help="攻击者升级时用的全精度栈")
    ap.add_argument("--selectors", default="", help="逗号分隔；D 部分用来模拟作弊的栈")
    ap.add_argument("--alpha", type=float, default=1e-3, help="目标 FPR")
    ap.add_argument("--beta", type=float, default=1e-3, help="目标 FNR")
    ap.add_argument("--min-band-frac", type=float, default=0.05,
                    help="canary 区间至少覆盖的 context 比例（太窄的区间池子不够用）")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    honest = [s for s in args.honest.split(",") if s]
    cheat = [s for s in args.cheat.split(",") if s]
    selectors = [s for s in args.selectors.split(",") if s]
    names = list(dict.fromkeys([args.ref, *honest, *cheat, args.escalate_to, *selectors]))
    cap = {n: load_capture(args.captures_dir / f"{n}.npz") for n in names}

    # 对齐检查：同一份 contexts、同样的 (seq, pos) 顺序
    ref = cap[args.ref]
    for n, c in cap.items():
        assert c["meta"]["contexts_sha256"] == ref["meta"]["contexts_sha256"], f"{n}: contexts 不一致"
        assert np.array_equal(c["seq_idx"], ref["seq_idx"]) and np.array_equal(c["pos"], ref["pos"]), n

    seq = ref["seq_idx"]
    M = len(seq)
    ref_top1 = ref["topk_ids"][:, 0]
    ref_margin = ref["topk_val"][:, 0] - ref["topk_val"][:, 1]
    top1 = {n: c["topk_ids"][:, 0] for n, c in cap.items()}
    margin = {n: c["topk_val"][:, 0] - c["topk_val"][:, 1] for n, c in cap.items()}
    mism = {n: top1[n] != ref_top1 for n in names}
    rng = np.random.default_rng(0)
    out: dict = {"n_contexts": M, "n_prompts": int(len(np.unique(seq))), "ref": args.ref,
                 "honest": honest, "cheat": cheat, "escalate_to": args.escalate_to,
                 "alpha": args.alpha, "beta": args.beta,
                 "stacks": {n: c["meta"] for n, c in cap.items()}}

    # ---- A. 总体失配率
    rates = {}
    for n in names:
        if n == args.ref:
            continue
        lo, hi = cluster_bootstrap(mism[n], seq, args.n_boot, rng)
        flipped = mism[n]
        rates[n] = {"role": "honest" if n in honest else "cheat" if n in cheat else "aux",
                    "mismatch": float(flipped.mean()), "ci95": [lo, hi],
                    "median_own_margin_on_flips": float(np.median(margin[n][flipped])) if flipped.any() else None,
                    "median_own_margin_all": float(np.median(margin[n]))}
    out["A_rates"] = rates
    p_h_global = max(rates[h]["mismatch"] for h in honest)

    # ---- B. 参考 margin 分箱 + 最佳 canary 区间（不考虑升级）
    edges = np.quantile(ref_margin, np.linspace(0, 1, N_BINS + 1))
    edges[-1] += 1e-6
    bin_id = np.clip(np.searchsorted(edges, ref_margin, side="right") - 1, 0, N_BINS - 1)
    bands = [(a, b) for a, b in itertools.combinations(range(N_BINS + 1), 2)
             if (b - a) / N_BINS >= args.min_band_frac]
    band_masks = {(a, b): (bin_id >= a) & (bin_id < b) for a, b in bands}

    bins_rows = []
    for k in range(N_BINS):
        m = bin_id == k
        row = {"bin": k, "ref_margin_lo": float(edges[k]), "ref_margin_hi": float(edges[k + 1]),
               "n": int(m.sum())}
        for n in names:
            if n != args.ref:
                row[n] = float(mism[n][m].mean())
        bins_rows.append(row)
    out["B_bins"] = bins_rows

    # 区间在偶数 prompt 上挑，在奇数 prompt 上报告，避免"在同一份数据上挑最优"的乐观偏差
    sel_half = seq % 2 == 0
    eval_half = ~sel_half

    def best_band(served_mism: np.ndarray) -> dict:
        """验证方选所需 canary 数最少的参考 margin 区间。p_h 取诚实栈中最差者的 Wilson 上界。"""
        best = None
        for (a, b), m in band_masks.items():
            ms = m & sel_half
            p_h = max(wilson_upper(mism[h][ms]) for h in honest)
            n_c = chernoff_n(p_h, float(served_mism[ms].mean()), args.alpha)
            if best is None or n_c < best[1]:
                best = ((a, b), n_c)
        (a, b), _ = best
        me = band_masks[(a, b)] & eval_half
        p_h_raw = max(float(mism[h][me].mean()) for h in honest)
        p_h_ub = max(wilson_upper(mism[h][me]) for h in honest)
        res = {"band_bins": [a, b], "ref_margin_range": [float(edges[a]), float(edges[b])],
               "frac": float(band_masks[(a, b)].mean()), "n_eval": int(me.sum()), "p_h_raw": p_h_raw}
        res.update(design(p_h_ub, float(served_mism[me].mean()), args.alpha, args.beta))
        return res

    # ---- C. 升级攻击
    esc_rows = []
    out["C_escalation"] = {}
    e_top1 = top1[args.escalate_to]
    for c in cheat:
        curve = []
        for r in ESC_RATES:
            esc = escalation_mask(margin[c], r, rng)
            served = np.where(esc, e_top1, top1[c]) != ref_top1
            bb = best_band(served)
            pt = {"target_esc_rate": r,
                  "tau": float(margin[c][esc].max()) if esc.any() else None,
                  "esc_cost": float(esc.mean()), "residual_mismatch_all": float(served.mean()),
                  "best_band": bb}
            curve.append(pt)
            esc_rows.append({"cheat": c, "target_esc_rate": r, "tau": pt["tau"],
                             "esc_cost": pt["esc_cost"], "residual_mismatch_all": pt["residual_mismatch_all"],
                             "band_p_h": bb["p_h"], "band_p_q": bb["p_q"], "band": bb["band_bins"],
                             "N_chernoff": finite(bb["N_chernoff"]), "N_exact": bb.get("N_exact")})

        def n_of(pt):  # 优先用精确二项设计，找不到（区分不了）记为 ∞
            b = pt["best_band"]
            return b["N_exact"] if b.get("N_exact") else math.inf
        n0 = n_of(curve[0])
        n10 = max(n_of(pt) for pt in curve if pt["esc_cost"] <= 0.10 + 1e-9)
        out["C_escalation"][c] = {
            "curve": curve, "N_no_escalation": finite(n0), "N_at_esc_le_10pct": finite(n10),
            # 预注册判据：升级成本 ≤10% 时，所需 canary 数（精确设计）至少放大 10 倍或超过 1000
            "motivation_holds": bool(n10 >= max(10 * n0, 1000)) if math.isfinite(n0) else None,
        }

    # ---- D. 量化器感知的 canary 池
    out["D_selected_pools"] = []
    for s in selectors:
        score = np.where(mism[s], margin[s], -np.inf)  # 只要 selector 翻转的；越自信越好
        order = np.argsort(-score)
        n_avail = int(mism[s].sum())
        for K in POOL_SIZES:
            if K > n_avail:
                continue
            pool = np.zeros(M, bool)
            pool[order[:K]] = True
            p_h = max(wilson_upper(mism[h][pool]) for h in honest)
            for c in cheat:
                for r in ESC_RATES:
                    esc = escalation_mask(margin[c], r, rng)
                    served = np.where(esc, e_top1, top1[c]) != ref_top1
                    p_q = float(served[pool].mean())
                    row = {"selector": s, "oracle": s == c, "pool_K": K, "cheat": c,
                           "target_esc_rate": r, "esc_cost": float(esc.mean()),
                           "pool_min_selector_margin": float(margin[s][order[K - 1]]),
                           **design(p_h, p_q, args.alpha, args.beta)}
                    row["N_chernoff"] = finite(row["N_chernoff"])
                    out["D_selected_pools"].append(row)

    # ---- 落盘
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "e0_summary.json").write_text(json.dumps(out, indent=2, default=float))
    write_csv(args.out_dir / "e0_bins.csv", bins_rows)
    write_csv(args.out_dir / "e0_escalation.csv", esc_rows)
    write_csv(args.out_dir / "e0_selected_pools.csv", out["D_selected_pools"])
    write_report(args.out_dir / "E0_REPORT.md", out, p_h_global)
    try_plot(args.out_dir / "e0_escalation.png", out)
    print(f"done -> {args.out_dir}")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_report(path: Path, out: dict, p_h_global: float) -> None:
    L = [f"# E0 自动报告（ref = `{out['ref']}`）", "",
         f"- contexts：{out['n_contexts']}（{out['n_prompts']} 个 prompt）；α={out['alpha']}，β={out['beta']}",
         f"- 诚实栈：{', '.join(out['honest'])}；作弊栈：{', '.join(out['cheat'])}；升级目标：`{out['escalate_to']}`",
         "", "## A. 总体 top-1 失配率", "",
         "| 栈 | 角色 | 失配率 | 95% CI | 翻转处自身 margin 中位数 | 全体自身 margin 中位数 |",
         "|---|---|---|---|---|---|"]
    for n, r in out["A_rates"].items():
        mf = r["median_own_margin_on_flips"]
        L.append(f"| `{n}` | {r['role']} | {r['mismatch']:.4f} | [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}] | "
                 f"{'—' if mf is None else f'{mf:.3f}'} | {r['median_own_margin_all']:.3f} |")
    L += ["", f"诚实栈最大失配率（全局）：{p_h_global:.4f}", "",
          "## C. 升级攻击（区间在偶数 prompt 上选、奇数 prompt 上报告；p_h 用 Wilson 95% 上界）", "",
          "| 作弊栈 | 升级成本 | 残余失配(全体) | 区间 p_h(上界) | 区间 p_q | N*(Chernoff) | N(exact) |",
          "|---|---|---|---|---|---|---|"]
    for c, d in out["C_escalation"].items():
        for pt in d["curve"]:
            b = pt["best_band"]
            nc = finite(b["N_chernoff"])
            L.append(f"| `{c}` | {pt['esc_cost']:.3f} | {pt['residual_mismatch_all']:.4f} | {b['p_h']:.4f} | "
                     f"{b['p_q']:.4f} | {'∞' if nc is None else nc} | {b.get('N_exact') or '—'} |")
    L += ["", "**预注册判据**（N 取精确二项设计；升级成本 ≤10% 时 N ≥ max(10·N(无升级), 1000)）：", ""]
    for c, d in out["C_escalation"].items():
        L.append(f"- `{c}`：N(无升级)={d['N_no_escalation']}，N(成本≤10%)={d['N_at_esc_le_10pct']} "
                 f"→ motivation_holds = **{d['motivation_holds']}**")
    if out["D_selected_pools"]:
        L += ["", "## D. 量化器感知的 canary 池（选翻转且 selector 最自信的 K 个 context）", "",
              "| selector | oracle | K | 作弊栈 | 升级成本 | p_h(上界) | p_q | N(exact) |",
              "|---|---|---|---|---|---|---|---|"]
        for r in out["D_selected_pools"]:
            if r["target_esc_rate"] in (0.0, 0.05, 0.10, 0.20):
                L.append(f"| `{r['selector']}` | {r['oracle']} | {r['pool_K']} | `{r['cheat']}` | "
                         f"{r['esc_cost']:.3f} | {r['p_h']:.4f} | {r['p_q']:.4f} | "
                         f"{r['N_exact'] or '∞'} |")
    path.write_text("\n".join(L) + "\n")


def try_plot(path: Path, out: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for c, d in out["C_escalation"].items():
        xs = [pt["esc_cost"] for pt in d["curve"]]
        ys = [min(pt["best_band"]["N_chernoff"], 1e6) for pt in d["curve"]]
        ax.plot(xs, ys, marker="o", label=c)
    ax.set_yscale("log")
    ax.set_xlabel("escalation cost (fraction of contexts recomputed at full precision)")
    ax.set_ylabel(f"canaries needed N* (α={out['alpha']})")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


if __name__ == "__main__":
    main()
