from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.lines import Line2D

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
REPORT_DIR = E2_DIR / "reports"

RUN_ID = "exp_e2_20260512_material_tamper_full_matrix"


def _short_pair(pair_id: str) -> str:
    return pair_id.replace("t4strict_pair_", "").replace("_40_200", "").replace("_vs_", "/").upper()


def _plot_strength_sweep(df: pd.DataFrame, out: Path) -> None:
    if plt is None:
        return
    focus_pairs = ["t4strict_pair_a_vs_b_40_200", "t4strict_pair_b_vs_d_40_200"]
    focus_variants = ["scalar16", "projcos4"]
    attacks = ["gaussian", "scale_perturbation"]
    colors = {"scalar16": "#0f766e", "projcos4": "#c2410c"}
    linestyles = {"gaussian": "-", "scale_perturbation": "--"}

    fig, axes = plt.subplots(1, len(focus_pairs), figsize=(13.2, 4.6), constrained_layout=True)
    for ax, pair_id in zip(axes, focus_pairs):
        subset_pair = df[df["pair_id"] == pair_id]
        for variant in focus_variants:
            for attack in attacks:
                subset = subset_pair[(subset_pair["variant"] == variant) & (subset_pair["attack_family"] == attack)]
                subset = subset.sort_values("attack_strength")
                if subset.empty:
                    continue
                ax.plot(
                    subset["attack_strength"],
                    subset["detection_rate"],
                    marker="o",
                    linewidth=1.8,
                    color=colors[variant],
                    linestyle=linestyles[attack],
                )
        ax.set_title(_short_pair(pair_id))
        ax.set_xlabel("Attack strength")
        ax.set_ylabel("Detection rate / TPR")
        ax.set_ylim(-0.02, 1.05)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.4)

    method_handles = [
        Line2D([0], [0], color=colors["scalar16"], marker="o", linewidth=2.0, label="scalar16"),
        Line2D([0], [0], color=colors["projcos4"], marker="o", linewidth=2.0, label="projcos4"),
    ]
    attack_handles = [
        Line2D([0], [0], color="#374151", linestyle="-", linewidth=2.0, label="Gaussian noise"),
        Line2D([0], [0], color="#374151", linestyle="--", linewidth=2.0, label="Scale perturbation"),
    ]
    method_legend = axes[-1].legend(
        handles=method_handles,
        title="Method (color)",
        frameon=False,
        fontsize=8,
        title_fontsize=9,
        loc="center left",
        bbox_to_anchor=(1.02, 0.72),
    )
    axes[-1].add_artist(method_legend)
    axes[-1].legend(
        handles=attack_handles,
        title="Attack (line style)",
        frameon=False,
        fontsize=8,
        title_fontsize=9,
        loc="center left",
        bbox_to_anchor=(1.02, 0.38),
    )
    fig.suptitle("Experiment C strength sweep: color encodes verifier; line style encodes attack", fontsize=13)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _plot_material_focus(summary: pd.DataFrame, out: Path) -> None:
    if plt is None:
        return
    focus_pairs = ["t4strict_pair_a_vs_b_40_200", "t4strict_pair_b_vs_d_40_200"]
    focus_variants = ["scalar16", "projcos4"]
    attacks = ["cross_prompt_stale_substitution", "wrong_shard_output", "layer_skip", "scale_perturbation"]
    labels = {
        "cross_prompt_stale_substitution": "Cross-prompt\nstale",
        "wrong_shard_output": "Wrong-shard\nsubstitution",
        "layer_skip": "Layer skip",
        "scale_perturbation": "Scale-only",
    }
    colors = {"scalar16": "#0f766e", "projcos4": "#c2410c"}

    fig, axes = plt.subplots(1, len(focus_pairs), figsize=(12.4, 4.4), constrained_layout=True)
    width = 0.34
    for ax, pair_id in zip(axes, focus_pairs):
        pair_df = summary[(summary["pair_id"] == pair_id) & (summary["variant"].isin(focus_variants))]
        x = list(range(len(attacks)))
        for offset, variant in ((-width / 2, "scalar16"), (width / 2, "projcos4")):
            vals = []
            for attack in attacks:
                row = pair_df[(pair_df["variant"] == variant) & (pair_df["attack_family"] == attack)]
                vals.append(float(row["detection_rate"].iloc[0]) if not row.empty else 0.0)
            bars = ax.bar([pos + offset for pos in x], vals, width=width, color=colors[variant], label=variant)
            for bar, val, attack in zip(bars, vals, attacks):
                if val == 0.0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        0.035,
                        "0",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        fontweight="bold",
                        color="#7f1d1d" if attack == "scale_perturbation" else "#111827",
                    )
        ax.set_title(_short_pair(pair_id))
        ax.set_xticks(x)
        ax.set_xticklabels([labels[attack] for attack in attacks], fontsize=8)
        ax.set_ylim(0.0, 1.05)
        ax.set_ylabel("Detection rate / TPR")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
        ax.axvspan(2.5, 3.5, color="#fee2e2", alpha=0.35, zorder=0)
        ax.text(3, 0.98, "direction-preserving\nblind spot", ha="center", va="top", fontsize=8, color="#7f1d1d")
    axes[-1].legend(frameon=False, loc="lower right")
    fig.suptitle("Experiment C material tamper focus: projcos is strong on direction-changing attacks, weak on scale-only", fontsize=12)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    selected: pd.DataFrame,
    sweep: pd.DataFrame,
    report_path: Path,
    strength_fig: Path,
    focus_fig: Path,
) -> None:
    focus = summary[
        summary["pair_id"].isin(["t4strict_pair_a_vs_b_40_200", "t4strict_pair_b_vs_d_40_200"])
        & summary["variant"].isin(["scalar16", "projcos4"])
    ]
    lines = [
        "# Experiment C Material Tamper Report (2026-05-12)",
        "",
        "## Status",
        "",
        "- This report supersedes `E2_material_tamper_full_matrix_report_20260507.md`.",
        "- Completed: expanded attack family, statistical/material attack-layer split, localization fields, calibration-feasibility flags, and detection-vs-strength sweep.",
        "- Not completed: output-affecting subset. Current captures contain checkpoints only, not logits/top-k/final outputs, so this requirement is explicitly downgraded to future capture work.",
        "- Interpretation change: Experiment C should be written as a tamper-family differentiation study, not as a single scalar-vs-projcos win/loss table.",
        "",
        "## Scope",
        "",
        "- This rerun is an offline replay experiment on real checkpoint captures, not an online adversarial deployment.",
        "- Main attack families now include gaussian, same_prompt_old_run_replay, cross_prompt_stale_substitution, wrong_shard_output, scale_perturbation, and layer_skip.",
        "- Statistical tamper and material tamper are explicitly separated via `attack_layer`.",
        "- `same_prompt_old_run_replay` is treated as a negative control / rerun-consistency test, not as primary material-tamper evidence.",
        "- `scale_perturbation` is a direction-preserving attack; cosine-only projected-token verification is expected to be weak on it.",
        "",
        "## Artifacts",
        "",
        f"- Selected operating points: {TABLE_DIR / (RUN_ID + '_selected_operating_points.csv')}",
        f"- Attack summary: {TABLE_DIR / (RUN_ID + '_attack_summary.csv')}",
        f"- Detail table: {TABLE_DIR / (RUN_ID + '_detail.csv')}",
        f"- Strength sweep: {TABLE_DIR / (RUN_ID + '_strength_sweep.csv')}",
        f"- Strength figure: {strength_fig}",
        f"- Material focus figure: {focus_fig}",
        "",
        "## Calibration Feasibility",
        "",
    ]
    fallback = selected[selected["selected_from_feasible"] == 0]
    if fallback.empty:
        lines.append("- No fallback operating points.")
    else:
        for _, row in fallback.iterrows():
            lines.append(
                f"- {row['pair_id']} / {row['variant']}: no calibration-feasible point; "
                f"selected calibration FPR={row['calib_honest_hetero_fpr']}."
            )
    lines.extend(["", "## Focus Results", ""])
    for _, row in focus.iterrows():
        strength = row["attack_strength"]
        strength_part = "" if pd.isna(strength) else f", strength={strength}"
        lines.append(
            f"- {row['pair_id']} / {row['variant']} / {row['attack_family']}: "
            f"layer={row['attack_layer']}{strength_part}, "
            f"TPR={row['detection_rate']}, LocAcc={row['localization_acc']}."
        )
    lines.extend(
        [
            "",
            "## Main Interpretation",
            "",
            "- `projcos4` is strong on material attacks that change representation direction or semantic content: cross-prompt stale substitution, wrong-shard substitution, and layer skip.",
            "- `same_prompt_old_run_replay` is mostly undetected because it is close to an honest rerun. It should be reported as a negative control rather than a successful tamper benchmark.",
            "- `scale_perturbation` exposes a real blind spot: projected cosine removes norm information, so pure scaling can evade it even when scalar-coordinate checks detect increasing scale strength.",
            "- The correct claim is therefore not 'projcos universally dominates material tamper', but 'projcos is much stronger for direction-changing material tamper; scale-only attacks require a norm-sensitive or hybrid component.'",
            "",
            "## Strength Sweep Takeaways",
            "",
            "- Gaussian tamper is detected strongly by projcos4 across the tested strengths on A/B and B/D.",
            "- Scale perturbation is intentionally hard for cosine-based projcos, because pure scaling preserves direction; scalar variants detect it better as strength grows.",
            "- This is useful for the paper: projcos is strong for direction-changing material substitutions, but scale-only attacks require either norm information or a hybrid signature.",
            "",
            "## Output-Affecting Subset",
            "",
            "- The current CSVs set `output_affecting_available=0` for all rows.",
            "- This is a data limitation, not a silent omission: the existing `.npz` captures only include checkpoint tensors.",
            "- To complete this handbook item, a new capture pass must persist logits, top-k, or final generated output for each prompt and attack candidate.",
            "",
            "## Remaining Boundary",
            "",
            "- This is still an offline controlled replay benchmark. It supports verifier sensitivity analysis, but should not be described as a complete online adversarial deployment.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    summary = pd.read_csv(TABLE_DIR / f"{RUN_ID}_attack_summary.csv")
    selected = pd.read_csv(TABLE_DIR / f"{RUN_ID}_selected_operating_points.csv")
    sweep = pd.read_csv(TABLE_DIR / f"{RUN_ID}_strength_sweep.csv")
    strength_fig = FIGURE_DIR / f"{RUN_ID}_strength_sweep_focus.png"
    focus_fig = FIGURE_DIR / f"{RUN_ID}_material_focus_panel.png"
    report_path = REPORT_DIR / f"{RUN_ID}_completion_report.md"
    _plot_strength_sweep(sweep, strength_fig)
    _plot_material_focus(summary, focus_fig)
    _write_report(summary, selected, sweep, report_path, strength_fig, focus_fig)
    print(f"strength figure: {strength_fig}")
    print(f"focus figure   : {focus_fig}")
    print(f"report         : {report_path}")


if __name__ == "__main__":
    main()
