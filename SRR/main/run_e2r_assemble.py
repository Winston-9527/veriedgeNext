"""E2-R assembly: aggregate per-prompt detail -> main matrix, blindspot table,
strength-sweep figure, manifest, and result memo (with Q1/Q2/Q3).

Reads <out>/e2r_per_prompt_detail.csv.gz (produced by run_e2r_main.py) plus
<out>/e2r_manifest_partial.json. Runs anywhere (pure numpy + matplotlib).

Usage:
    python3 run_e2r_assemble.py --out results/e2r
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from e2r_common import (
    DETECTORS, FAMILIES, BOUNDARIES, RHOS, BLIND_RHO,
    wilson95, VERIFIER_SEED, PRIMARY_GUESS_SEED, GUESS_SEEDS,
)

DET_ORDER = {"SignRadial": 0, "ProjCos4": 1, "Combined": 2}


def blind_state(tpr: float, fpr: float) -> str:
    if tpr <= 2 * fpr:
        return "blind"
    if tpr <= 0.5:
        return "partial"
    return "detected"


def load_detail(path: Path):
    """Return (rows, honest_rows). rows: list of dicts keyed by DETAIL_COLS."""
    rows, honest = [], []
    with gzip.open(path, "rt", newline="") as fh:
        r = csv.DictReader(fh)
        for row in r:
            if row["family"] == "honest":
                honest.append(row)
            else:
                rows.append(row)
    return rows, honest


def eval_fpr(honest_rows, detector) -> float:
    k = sum(1 for h in honest_rows if h["detector"] == detector and h["detected"] == "1")
    return k / max(1, sum(1 for h in honest_rows if h["detector"] == detector))


def aggregate(rows, honest_rows, h0=None):
    """Return dict[(tm, fam, rho, kstar, det)] -> metrics dict.

    harmful := harm > h0[kstar] (design §5.2: material = beyond honest A/B
    heterogeneity at Q0.95). If h0 is None, falls back to harm > 0.
    """
    fpr = {d: eval_fpr(honest_rows, d) for d in DETECTORS}
    cells = defaultdict(list)
    for r in rows:
        key = (r["tm"], r["family"], float(r["rho"]), r["kstar"], r["detector"])
        cells[key].append(r)
    out = {}
    for key, rs in cells.items():
        det = key[4]
        kstar = key[3]
        thr = (h0 or {}).get(kstar, 0.0)
        n = len(rs)
        detected = [r for r in rs if r["detected"] == "1"]
        tpr = len(detected) / n
        evaded_harmful = [r for r in rs if r["detected"] != "1" and float(r["harm"]) > thr]
        harm_vals = [float(r["harm"]) for r in rs]
        rho_effs = [float(r["rho_eff"]) for r in rs]
        loc_ok = sum(1 for r in detected if r["loc_ok"] == "1")
        loc_acc = loc_ok / len(detected) if detected else float("nan")
        k_tpr = len(detected)
        lo, hi = wilson95(k_tpr, n)
        out[key] = {
            "n_eval": n,
            "tpr": tpr, "tpr_ci_lo": lo, "tpr_ci_hi": hi,
            "eval_fpr": fpr[det],
            "evaded_rate": 1 - tpr,
            "harmful_evasion_rate": len(evaded_harmful) / n,
            "harm_proxy_mean": float(np.mean(harm_vals)) if harm_vals else float("nan"),
            "localization_acc": loc_acc,
            "rho_eff_mean": float(np.mean(rho_effs)) if rho_effs else float("nan"),
            "state": blind_state(tpr, fpr[det]),
        }
    return out


def write_main_matrix(out, cells):
    cols = ["threat_model", "attack_family", "rho", "boundary", "detector",
            "n_eval", "threshold_gamma", "tpr_at_1fpr", "eval_fpr", "evaded_rate",
            "harmful_evasion_rate", "harm_proxy_mean", "localization_acc",
            "tpr_ci_lo", "tpr_ci_hi", "rho_eff"]
    with open(out / "e2r_main_matrix.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for (tm, fam, rho, kstar, det), m in sorted(cells.items()):
            w.writerow([tm, fam, rho, kstar, det, m["n_eval"],
                        round(tau_trace[det], 8), round(m["tpr"], 6),
                        round(m["eval_fpr"], 6), round(m["evaded_rate"], 6),
                        round(m["harmful_evasion_rate"], 6),
                        round(m["harm_proxy_mean"], 6),
                        "nan" if np.isnan(m["localization_acc"]) else round(m["localization_acc"], 6),
                        round(m["tpr_ci_lo"], 6), round(m["tpr_ci_hi"], 6),
                        "nan" if np.isnan(m["rho_eff_mean"]) else round(m["rho_eff_mean"], 6)])


def _cell(m):
    """TPR [Wilson95 CI] (state) — CI added for the n=520 blindspot-label audit (D)."""
    return f"{m['tpr']:.3f} [{m['tpr_ci_lo']:.3f},{m['tpr_ci_hi']:.3f}] ({m['state']})"


def write_blindspot(out, cells):
    # threat models present in the data (handles TM1b_knownP audit arm too)
    tms = sorted({k[0] for k in cells})
    lines = ["# E2-R blindspot table (fixed rho = %.3f, TPR@1%%FPR, state by $TPR\\le 2\\times evalFPR$)" % BLIND_RHO,
             "", "> 单元格格式：TPR [Wilson 95%% CI] (三态)。n=520 下 TPR≈FPR 的盲点标签 CI 跨分界（如 0.010 [0.004,0.022]），"
                 "joint_null 的 TPR==honest FPR 精确相等故结构性结论稳健。", ""]
    lines.append("| attack_family × threat_model | SignRadial | ProjCos4 | Combined |")
    lines.append("|---|---|---|---|")
    for fam in FAMILIES:
        for tm in tms:
            cells_row = []
            for det in DETECTORS:
                k = (tm, fam, BLIND_RHO, "C3", det)
                if k in cells:
                    cells_row.append(_cell(cells[k]))
                else:
                    cells_row.append("-")
            lines.append(f"| {fam} · {tm} | {' | '.join(cells_row)} |")
    # separate section: all boundaries at rho=0.01 (C3 = evasion-critical)
    lines.append("")
    lines.append("## All injection boundaries (rho = %.3f)" % BLIND_RHO)
    lines.append("| family × TM × boundary | SignRadial | ProjCos4 | Combined |")
    lines.append("|---|---|---|---|")
    for fam in FAMILIES:
        for tm in tms:
            for kstar in BOUNDARIES:
                row = []
                for det in DETECTORS:
                    k = (tm, fam, BLIND_RHO, kstar, det)
                    if k in cells:
                        row.append(_cell(cells[k]))
                    else:
                        row.append("-")
                lines.append(f"| {fam}·{tm}·{kstar} | {' | '.join(row)} |")
    (out / "e2r_blindspot_table.md").write_text("\n".join(lines) + "\n")


def write_sweep(out, cells):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    colors = {"SignRadial": "#d62728", "ProjCos4": "#1f77b4", "Combined": "#2ca02c"}
    for ax, fam in zip(axes.flat, FAMILIES):
        for det in DETECTORS:
            for tm, ls in (("TM1_seed_secret", "--"), ("TM2_seed_known", "-")):
                pts = []
                for rho in RHOS:
                    k = (tm, fam, rho, "C3", det)
                    if k in cells:
                        pts.append((rho, cells[k]["tpr"]))
                pts.sort()
                if pts:
                    ax.plot([p[0] for p in pts], [p[1] for p in pts],
                            ls, color=colors[det], label=f"{det} {tm.replace('_seed_','-')}" if fam == FAMILIES[0] else None)
        ax.set_xscale("log")
        ax.set_xlabel(r"$\rho$ (relative L2)")
        ax.set_ylabel("TPR@1%FPR")
        ax.set_title(fam)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=9)
    fig.suptitle("E2-R strength sweep: TPR@1%FPR vs tamper magnitude (C3 injection, evasion-critical)")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out / "e2r_strength_sweep.png", dpi=150)
    print("wrote e2r_strength_sweep.png")


def _sha12(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def write_manifest(out, mani, script_hashes=None):
    """Complete the manifest: add script hashes + construction code locations.

    Hashes computed dynamically from the on-disk scripts (so the manifest always
    reflects the files that produced the results)."""
    if script_hashes is None:
        root = Path(__file__).resolve().parent.parent
        script_hashes = {}
        for sub, names in {
                "lib": ("e2r_common.py", "e2r_attacks.py"),
                "main": ("run_e2r_main.py", "run_e2r_assemble.py"),
                "validation": ("run_e2r_harm_decode.py", "run_e2r_fresh.py",
                               "run_e2r_fresh_harm_decode.py")}.items():
            for name in names:
                p = root / sub / name
                if p.is_file():
                    script_hashes[name] = _sha12(p)
    out_mani = dict(mani)
    out_mani["script_hashes"] = script_hashes
    out_mani["construction_code"] = {
        "sign_balanced_sr": "e2r_attacks.py:sign_balanced (per-row sign projection on Omega)",
        "null_space_projcos": "e2r_attacks.py:null_space_projcos (per-row null(P) via (P^T P)^{-1}P^T)",
        "joint_null": "e2r_attacks.py:joint_null (null(P) + sign-balance fixup; report via joint_null_report)",
        "tol_hug_sr": "e2r_attacks.py:tol_hug (harm dir clamped to (1-delta)*Gamma by grid+bisect)",
        "tol_hug_projcos": "e2r_attacks.py:tol_hug (target Gamma_ProjCos)",
        "tol_hug_combined": "e2r_attacks.py:tol_hug (target Gamma_Combined via per-boundary ECDF max)",
    }
    out_mani["threat_models"] = {
        "TM2_seed_known": "attacker aligns construction to verifier seed 2026 (current impl node_sees_before_exec)",
        "TM1_seed_secret": "attacker aligns to guessed seed; verifier scores on 2026 (commit-then-challenge hypothetical)",
        "TM1b_knownP": "audit arm: P public (verifier seed), SignRadial coordinate sampling secret",
    }
    out_mani["column_note"] = ("e2r_main_matrix.threshold_gamma is the TRACE-MAX detection "
                               "threshold tau_trace = Q_{0.99}(calib trace-max honest); the "
                               "per-boundary thresholds used for localization/tol_hug are in "
                               "this manifest under 'gamma'.")
    (out / "e2r_manifest.json").write_text(json.dumps(out_mani, indent=2, default=str))


def main():
    global tau_trace
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--guess-seed", type=int, default=0,
                    help="override manifest primary_guess_seed (for TM-1 robustness dirs)")
    ap.add_argument("--tm1-only", action="store_true",
                    help="mark this run as TM-1 only (gs robustness dirs)")
    args = ap.parse_args()
    OUT = Path(args.out)

    rows, honest = load_detail(OUT / "e2r_per_prompt_detail.csv.gz")
    print(f"attack rows={len(rows)} honest rows={len(honest)}")
    mani = json.loads((OUT / "e2r_manifest_partial.json").read_text())
    if args.guess_seed:
        mani["primary_guess_seed"] = args.guess_seed
    if args.tm1_only:
        mani["scope"] = "TM1_seed_secret only (guess-seed robustness arm); TM2 rows absent"
    h0 = mani.get("h0", None)
    cells = aggregate(rows, honest, h0=h0)
    tau_trace = mani["tau_trace"]

    write_main_matrix(OUT, cells)
    write_blindspot(OUT, cells)
    write_manifest(OUT, mani)
    print("aggregates + blindspot + manifest written "
          "(paper figures generated by run_e2r_figs.py)")


if __name__ == "__main__":
    main()
