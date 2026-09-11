"""E2-R figures: blindspot heatmap + harm-evidence figure (paper drafts).

Reads results/e2r/e2r_main_matrix.csv, results/e2r/e2r_manifest.json and
results/e2r/e2r_harm_decode/harm_decode_summary.csv. Generates:
  e2r_blindspot_heatmap.png  — coverage matrix (fam×TM rows, 3 detector cols,
                               TPR color + blind/partial/detected state)
  e2r_harm_evidence.png      — 2 panels: logit-shift harm vs honest h0; and the
                               32-token decode evidence (token agreement / ROUGE-L
                               / output-change)

Usage: python3 run_e2r_figs.py --out results/e2r
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# CJK fonts (macOS PingFang/STHeiti; Linux fallback to Noto). DejaVu last as
# the ASCII-only backstop. axes.unicode_minus=False so '-' renders correctly.
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "PingFang SC", "STHeiti", "Hiragino Sans", "Heiti TC",
    "Noto Sans CJK SC", "Noto Sans CJK TC", "Arial Unicode MS", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import DETECTORS, FAMILIES, BLIND_RHO, wilson95


def blind_state(tpr, fpr):
    if tpr <= 2 * fpr:
        return "blind"
    if tpr <= 0.5:
        return "partial"
    return "detected"


def load_matrix(path):
    rows = {}
    for r in csv.DictReader(open(path)):
        key = (r["threat_model"], r["attack_family"], r["rho"], r["boundary"], r["detector"])
        rows[key] = r
    return rows


def fig_sweep_publicP(out, main_rows, knownP_rows):
    """Strength sweep under the AUDITED threat model: P is public.

    TM-2 curves (solid): from the main matrix (TM2_seed_known).
    TM-1 curves (dashed): from the TM1b_knownP arm (P public, Omega secret) —
    the audited semantics. Under P public, ProjCos behaves identically for
    TM-1 and TM-2 (both know P); only SignRadial's sampled coords differ.
    """
    from e2r_common import RHOS, FAMILIES, DETECTORS
    colors = {"SignRadial": "#d62728", "ProjCos4": "#1f77b4", "Combined": "#2ca02c"}
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for ax, fam in zip(axes.flat, FAMILIES):
        for det in DETECTORS:
            for label, tm, ls, src in [
                ("TM-1 (P 公开, Ω 保密)", "TM1b_knownP", "--", knownP_rows),
                ("TM-2 (P 公开, Ω 已知)", "TM2_seed_known", "-", main_rows),
            ]:
                pts = []
                for rho in RHOS:
                    r = src.get((tm, fam, str(rho), "C3", det))
                    if r is not None:
                        pts.append((rho, float(r["tpr_at_1fpr"])))
                pts.sort()
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], ls,
                            color=colors[det],
                            label=f"{det} {label}" if fam == FAMILIES[0] else None)
        ax.set_xscale("log")
        ax.set_xlabel(r"$\rho$ (relative L2)")
        ax.set_ylabel("TPR@1%FPR")
        ax.set_title(fam, fontsize=11)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=8.5)
    fig.suptitle("E2-R 强度谱（审计后威胁模型：P 公开）— TPR@1%FPR vs 篡改幅度 ρ，C3 注入\n"
                 "PC 通道 TM-1 ≡ TM-2（P 公开等价）；仅 SR 抽查坐标 Ω 区分两模型",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(out / "e2r_strength_sweep.png", dpi=150)
    plt.close(fig)
    print("wrote e2r_strength_sweep.png (P-public threat model)")


def fig_heatmap(out, rows):
    tms = ["TM1_seed_secret", "TM2_seed_known"]
    tm_lbl = {"TM1_seed_secret": "TM-1 (seed 保密)", "TM2_seed_known": "TM-2 (seed 已知)"}
    eval_fpr = {"SignRadial": 0.0096, "ProjCos4": 0.0154, "Combined": 0.0096}

    fig, ax = plt.subplots(figsize=(9.5, 8.5))
    # rows: fam × TM; cols: detectors
    n_row = len(FAMILIES) * len(tms)
    grid = np.full((n_row, 3), np.nan)
    texts = []
    for i, fam in enumerate(FAMILIES):
        for j, tm in enumerate(tms):
            row = i * len(tms) + j
            for d, det in enumerate(DETECTORS):
                r = rows.get((tm, fam, str(BLIND_RHO), "C3", det))
                if r is None:
                    continue
                tpr = float(r["tpr_at_1fpr"])
                grid[row, d] = tpr
                st = blind_state(tpr, eval_fpr[det])
                texts.append((row, d, f"{tpr:.3f}\n{st}"))

    im = ax.imshow(grid, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    for (row, d, txt) in texts:
        ax.text(d, row, txt, ha="center", va="center", fontsize=8.5,
                color="black" if 0.25 < grid[row, d] < 0.75 else "white")
    ax.set_xticks(range(3))
    ax.set_xticklabels(DETECTORS, fontsize=11)
    ax.set_yticks(range(n_row))
    ax.set_yticklabels([f"{fam}·{tm_lbl[tm]}" for fam in FAMILIES for tm in tms],
                       fontsize=9)
    # separator between TM groups within each family
    for i in range(len(FAMILIES)):
        ax.axhline(i * 2 - 0.5, color="black", lw=0.5, alpha=0.3)
    ax.set_xlabel("detector", fontsize=11)
    ax.set_title(f"E2-R 盲点覆盖矩阵 — C3（末层）注入，ρ={BLIND_RHO}，TPR@1%FPR\n"
                 "红=blind（TPR≤2×FPR）、黄=partial、绿=detected；盲点判据 §2.4",
                 fontsize=11)
    fig.colorbar(im, ax=ax, label="TPR@1%FPR", shrink=0.85)
    fig.tight_layout()
    fig.savefig(out / "e2r_blindspot_heatmap.png", dpi=150)
    plt.close(fig)
    print("wrote e2r_blindspot_heatmap.png")


def fig_harm_evidence(out, rows, mani, decode_summary_path):
    h0 = mani.get("h0", {}).get("C3", 0.0233)
    fams = list(FAMILIES)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))

    # ---- panel A: logit-shift harm (C3 TM-2 rho=0.01) vs honest h0 ----
    ax = axes[0]
    harm, tpr = [], []
    for fam in fams:
        r = rows.get(("TM2_seed_known", fam, str(BLIND_RHO), "C3", "Combined"))
        harm.append(float(r["harm_proxy_mean"]))
        tpr.append(float(r["tpr_at_1fpr"]))
    x = np.arange(len(fams))
    ax.bar(x, harm, color="#d62728", alpha=0.85, label="harm_proxy_mean (逃避攻击)")
    ax.axhline(h0, color="#1f77b4", ls="--", lw=1.5, label=f"honest h0 (C3) = {h0:.3f}")
    for xi, (h, t) in enumerate(zip(harm, tpr)):
        ax.text(xi, h + 0.01, f"TPR={t:.2f}", ha="center", fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(fams, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("relative last-token logit shift")
    ax.set_ylim(0, max(harm) * 1.2)
    ax.set_title("(a) 逃避的篡改 logit 偏移 vs 诚实异构地板（C3, TM-2, ρ=0.01）",
                 fontsize=10)
    ax.legend(fontsize=8)

    # ---- panel B: 32-token decode evidence (output rewrite) ----
    ax = axes[1]
    decode = {}
    if decode_summary_path.is_file():
        for r in csv.DictReader(open(decode_summary_path)):
            decode[r["family"]] = r
    ag = [float(decode[f]["mean_token_agreement"]) for f in fams if f in decode]
    rl = [float(decode[f]["mean_rouge_l_f1"]) for f in fams if f in decode]
    ch = [float(decode[f]["p_output_changed"]) for f in fams if f in decode]
    w = 0.26
    xi = np.arange(len(fams))
    ax.bar(xi - w, ag, w, label="token 一致率 (低=全文重写)", color="#1f77b4")
    ax.bar(xi, rl, w, label="ROUGE-L F1", color="#2ca02c")
    ax.bar(xi + w, ch, w, label="输出改变率", color="#ff7f0e")
    ax.axhline(1.0, color="gray", ls=":", lw=1)
    ax.set_xticks(xi); ax.set_xticklabels(fams, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("ratio")
    ax.set_ylim(0, 1.1)
    ax.set_title("(b) 32-token 贪婪解码：逃避攻击重写最终输出（TM-2, C3, ρ=0.01）",
                 fontsize=10)
    ax.legend(fontsize=7.5, loc="lower center")

    fig.suptitle("E2-R 危害证据：盲点攻击改变模型最终输出", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out / "e2r_harm_evidence.png", dpi=150)
    plt.close(fig)
    print("wrote e2r_harm_evidence.png")


def fig_fresh_vs_fixed(out, fresh_csv):
    """fresh-P vs fixed-P: does per-request fresh P/Omega eliminate the
    construction-based blind spots? 4 key families: joint_null/null_space/
    sign_balanced (should rise = blind spot gone) and tol_hug_combined
    (magnitude-clamping -> survives)."""
    from e2r_common import RHOS
    fresh = {}
    for r in csv.DictReader(open(fresh_csv)):
        key = (r["family"], float(r["rho"]))
        fresh[key] = {d: float(r[d]) for d in DETECTORS}
        fresh[key][f"{DETECTORS[0]}_fixed"] = float(r[f"{DETECTORS[0]}_fixed"])
        fresh[key][f"{DETECTORS[1]}_fixed"] = float(r[f"{DETECTORS[1]}_fixed"])
        fresh[key][f"{DETECTORS[2]}_fixed"] = float(r[f"{DETECTORS[2]}_fixed"])

    panels = [("joint_null", "Combined", "joint-null（同时躲两检测器）"),
              ("null_space_projcos", "ProjCos4", "null-space（躲 ProjCos）"),
              ("sign_balanced_sr", "SignRadial", "sign-balanced（躲 SignRadial）"),
              ("tol_hug_combined", "Combined", "tol_hug_combined（幅度钳制）")]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, (fam, det, title) in zip(axes, panels):
        rhos, fr, fx = [], [], []
        for rho in RHOS:
            k = (fam, rho)
            if k in fresh:
                rhos.append(rho)
                fr.append(fresh[k][det])
                fx.append(fresh[k][f"{det}_fixed"])
        ax.plot(rhos, fx, "o-", color="#d62728", lw=2, label="fixed-P（攻击前已知 P）")
        ax.plot(rhos, fr, "s--", color="#1f77b4", lw=2, label="fresh-P（challenge 后随机 P）")
        ax.set_xscale("log")
        ax.set_xlabel(r"$\rho$")
        ax.set_ylabel(f"{det} TPR@1%FPR")
        ax.set_ylim(-0.05, 1.05)
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.suptitle("fresh-P（commit-then-challenge）vs fixed-P：构造性盲点消除，tol_hug 幅度钳制仍在（C3 注入）",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(out / "e2r_fresh_vs_fixed.png", dpi=150)
    plt.close(fig)
    print("wrote e2r_fresh_vs_fixed.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--knownp-matrix", default="",
                    help="TM1b_knownP matrix CSV (P-public TM-1) for the sweep figure")
    ap.add_argument("--fresh-csv", default="",
                    help="fresh-vs-fixed comparison CSV (run_e2r_fresh.py output)")
    args = ap.parse_args()
    OUT = Path(args.out)
    rows = load_matrix(OUT / "e2r_main_matrix.csv")
    mani = json.loads((OUT / "e2r_manifest.json").read_text())
    fig_heatmap(OUT, rows)
    # harm-decode results live in the sibling dir results/e2r_harm_decode/
    decode_summary = OUT.parent / "e2r_harm_decode" / "harm_decode_summary.csv"
    fig_harm_evidence(OUT, rows, mani, decode_summary)
    # strength sweep under the audited (P-public) threat model
    kp = args.knownp_matrix or str(OUT.parent / "e2r_knownP" / "e2r_main_matrix.csv")
    if Path(kp).is_file():
        kp_rows = load_matrix(kp)
        fig_sweep_publicP(OUT, rows, kp_rows)
    else:
        print(f"skip sweep: knownP matrix not found at {kp}")
    # fresh-P validation figure
    fc = args.fresh_csv or str(OUT.parent / "e2r_fresh" / "e2r_fresh_vs_fixed.csv")
    if Path(fc).is_file():
        fig_fresh_vs_fixed(OUT, fc)
    else:
        print(f"skip fresh figure: {fc} not found")


if __name__ == "__main__":
    raise SystemExit(main())
