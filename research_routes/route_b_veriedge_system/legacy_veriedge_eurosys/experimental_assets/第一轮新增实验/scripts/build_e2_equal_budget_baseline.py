from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - plotting is best effort
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from checkpoint_qwen import checkpoint_order  # type: ignore
from hash_chain import HashConfig, project_prefill_linear_signature  # type: ignore

import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "equal_budget_live_ab"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
NOTE_DIR = E2_DIR / "notes"

TARGET_STAGE = "prefill"
PERCENTILES = [99.0, 99.5, 99.9, 99.95, 99.99]
TOLERANCE_SCALES = [0.5, 1.0, 1.5, 2.0]
TARGET_MAX_FPR = 0.10


@dataclass(frozen=True)
class VariantSpec:
    name: str
    family: str
    token_samples: int
    channel_samples: int
    projection_dim: int
    signature_scalars_per_checkpoint: int
    signature_bytes_per_checkpoint_fp32: int


VARIANTS: Sequence[VariantSpec] = (
    VariantSpec(
        name="scalar16",
        family="scalar",
        token_samples=1,
        channel_samples=16,
        projection_dim=0,
        signature_scalars_per_checkpoint=16,
        signature_bytes_per_checkpoint_fp32=64,
    ),
    VariantSpec(
        name="scalar64",
        family="scalar",
        token_samples=1,
        channel_samples=64,
        projection_dim=0,
        signature_scalars_per_checkpoint=64,
        signature_bytes_per_checkpoint_fp32=256,
    ),
    VariantSpec(
        name="projscalar1_abs",
        family="projabs",
        token_samples=16,
        channel_samples=0,
        projection_dim=1,
        signature_scalars_per_checkpoint=16,
        signature_bytes_per_checkpoint_fp32=64,
    ),
    VariantSpec(
        name="projcos4",
        family="projcos",
        token_samples=16,
        channel_samples=0,
        projection_dim=4,
        signature_scalars_per_checkpoint=64,
        signature_bytes_per_checkpoint_fp32=256,
    ),
    VariantSpec(
        name="projcos16",
        family="projcos",
        token_samples=16,
        channel_samples=0,
        projection_dim=16,
        signature_scalars_per_checkpoint=256,
        signature_bytes_per_checkpoint_fp32=1024,
    ),
)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _scale_delta_map(delta_map: Dict[str, Dict[str, float]], scale: float) -> Dict[str, Dict[str, float]]:
    return scalar._scale_delta_map(delta_map, scale)


def _projected_hash_params(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> Dict[str, Any]:
    return proj._projcos_hash_params(
        delta_map=delta_map,
        projection_dim=variant.projection_dim,
        token_samples=variant.token_samples,
    )


def _projected_hash_cfg(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> HashConfig:
    return proj._projcos_cfg(
        delta_map=delta_map,
        projection_dim=variant.projection_dim,
        token_samples=variant.token_samples,
    )


def _projabs_hash_params(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> Dict[str, Any]:
    params = _projected_hash_params(delta_map, variant)
    params["mode"] = "tstc_projabs"
    return params


def _projabs_hash_cfg(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> HashConfig:
    cfg = _projected_hash_cfg(delta_map, variant)
    cfg.mode = "tstc_projabs"
    return cfg


def _scalar_hash_cfg(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> HashConfig:
    return scalar._build_hash_cfg_grid(
        delta_map=delta_map,
        token_samples=variant.token_samples,
        channel_samples=variant.channel_samples,
    )


def _scalar_hash_params(delta_map: Dict[str, Dict[str, float]], variant: VariantSpec) -> Dict[str, Any]:
    return {
        "seed_base": 2026,
        "delta_map": json.loads(json.dumps(delta_map, ensure_ascii=True)),
        "prefill_token_samples": int(variant.token_samples),
        "prefill_channel_samples": int(variant.channel_samples),
        "decode_channel_samples": 1,
    }


def _calibrate_projabs_percentile(
    capture_roots: Sequence[Path],
    checkpoints: Sequence[str],
    percentile: float,
    projection_dim: int,
    token_samples: int,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    machine_maps = {root.name: scalar._load_npz_map(root) for root in capture_roots}
    common_prompts = set.intersection(*(set(prompt_map.keys()) for prompt_map in machine_maps.values()))
    grouped: Dict[Tuple[str, str], List[float]] = {}
    proto_cfg = _projabs_hash_cfg({"prefill": {}, "decode": {}}, VariantSpec("proto", "projabs", token_samples, 0, projection_dim, 0, 0))
    checkpoint_index = {name: idx for idx, name in enumerate(checkpoints)}

    machine_names = list(machine_maps.keys())
    for left_name, right_name in combinations(machine_names, 2):
        left_prompts = machine_maps[left_name]
        right_prompts = machine_maps[right_name]
        for prompt_id in sorted(common_prompts):
            left_payload = left_prompts[prompt_id]
            right_payload = right_prompts[prompt_id]
            for checkpoint in checkpoints:
                key = f"prefill__{checkpoint}"
                if key not in left_payload or key not in right_payload:
                    continue
                seed = proto_cfg.seed_base + checkpoint_index[checkpoint]
                _, left_sig = project_prefill_linear_signature(left_payload[key], proto_cfg, checkpoint, seed)
                _, right_sig = project_prefill_linear_signature(right_payload[key], proto_cfg, checkpoint, seed)
                mean_gap = float(np.mean(np.abs(left_sig - right_sig))) if left_sig.size else 0.0
                grouped.setdefault(("prefill", checkpoint), []).append(mean_gap)

    delta_map = {"prefill": {}, "decode": {}}
    summary_lookup: Dict[str, float] = {}
    for (_, checkpoint), gap_values in sorted(grouped.items()):
        values = np.asarray(gap_values, dtype=np.float32)
        delta = float(np.percentile(values, percentile)) if values.size else 0.0
        delta_map["prefill"][checkpoint] = delta
        summary_lookup[f"prefill_{checkpoint}"] = delta
    return delta_map, summary_lookup


def _selection_tuple(row: Mapping[str, Any]) -> Tuple[int, float, float, float, float]:
    feasible = 1 if float(row["calib_honest_hetero_fpr"]) <= TARGET_MAX_FPR else 0
    score = float(row["calib_tamper_tpr"]) - float(row["calib_honest_hetero_fpr"])
    return (
        feasible,
        score,
        float(row["calib_tamper_tpr"]),
        float(row["calib_tamper_locacc"]),
        -float(row["calib_honest_hetero_fpr"]),
    )


def _pick_best(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not rows:
        raise ValueError("no candidate rows to select from")
    feasible = [row for row in rows if float(row["calib_honest_hetero_fpr"]) <= TARGET_MAX_FPR]
    bucket = feasible or list(rows)
    return max(bucket, key=_selection_tuple)


def _row_common(variant: VariantSpec, mode: str, percentile: float, scale: float) -> Dict[str, Any]:
    return {
        "variant": variant.name,
        "family": variant.family,
        "tolerance_mode": mode,
        "percentile": percentile,
        "tolerance_scale": scale,
        "token_samples": variant.token_samples,
        "channel_samples": variant.channel_samples,
        "projection_dim": variant.projection_dim,
        "signature_scalars_per_checkpoint": variant.signature_scalars_per_checkpoint,
        "signature_bytes_per_checkpoint_fp32": variant.signature_bytes_per_checkpoint_fp32,
    }


def _evaluate_variant(
    *,
    variant: VariantSpec,
    delta_map: Dict[str, Dict[str, float]],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    calib_prompt_map: Mapping[str, Dict[str, str]],
    context: Mapping[str, Path],
) -> Dict[str, Any]:
    if variant.family == "scalar":
        hash_cfg = _scalar_hash_cfg(delta_map, variant)
        hash_params = _scalar_hash_params(delta_map, variant)
        calib_hetero = scalar._pair_fpr(
            context["left_calib"],
            context["right_calib"],
            checkpoints,
            TARGET_STAGE,
            scalar._thc_cfg(),
            hash_cfg,
        )
        calib_tamper = scalar._tamper_metrics(config, context["right_calib"], calib_prompt_map, hash_params)
        return {
            "calib_honest_hetero_fpr": calib_hetero["tstc_fpr"],
            "calib_tamper_tpr": calib_tamper["tstc_tpr"],
            "calib_tamper_locacc": calib_tamper["tstc_localization_acc"],
            "calib_prompt_count": calib_hetero["prompt_count"],
        }

    if variant.family == "projabs":
        hash_cfg = _projabs_hash_cfg(delta_map, variant)
        hash_params = _projabs_hash_params(delta_map, variant)
    else:
        hash_cfg = _projected_hash_cfg(delta_map, variant)
        hash_params = _projected_hash_params(delta_map, variant)
    calib_hetero = scalar._pair_fpr(
        context["left_calib"],
        context["right_calib"],
        checkpoints,
        TARGET_STAGE,
        scalar._thc_cfg(),
        hash_cfg,
    )
    calib_tamper = proj._tamper_metrics_projcos(config, context["right_calib"], calib_prompt_map, hash_params)
    return {
        "calib_honest_hetero_fpr": calib_hetero["tstc_fpr"],
        "calib_tamper_tpr": calib_tamper["projcos_tpr"],
        "calib_tamper_locacc": calib_tamper["projcos_localization_acc"],
        "calib_prompt_count": calib_hetero["prompt_count"],
    }


def _evaluate_selected_on_eval(
    *,
    variant: VariantSpec,
    delta_map: Dict[str, Dict[str, float]],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    eval_prompt_map: Mapping[str, Dict[str, str]],
    context: Mapping[str, Path],
) -> Dict[str, Any]:
    if variant.family == "scalar":
        hash_cfg = _scalar_hash_cfg(delta_map, variant)
        hash_params = _scalar_hash_params(delta_map, variant)
        eval_homo = scalar._pair_fpr(
            context["homo_left_eval"],
            context["homo_right_eval"],
            checkpoints,
            TARGET_STAGE,
            scalar._thc_cfg(),
            hash_cfg,
        )
        eval_hetero = scalar._pair_fpr(
            context["left_eval"],
            context["right_eval"],
            checkpoints,
            TARGET_STAGE,
            scalar._thc_cfg(),
            hash_cfg,
        )
        eval_tamper = scalar._tamper_metrics(config, context["tamper_root"], eval_prompt_map, hash_params)
        return {
            "eval_honest_homo_fpr": eval_homo["tstc_fpr"],
            "eval_honest_hetero_fpr": eval_hetero["tstc_fpr"],
            "eval_tamper_tpr": eval_tamper["tstc_tpr"],
            "eval_tamper_locacc": eval_tamper["tstc_localization_acc"],
            "eval_runtime_ms_per_trace_homo": round((float(eval_homo["tstc_runtime_sec"]) * 1000.0) / eval_homo["prompt_count"], 6),
            "eval_runtime_ms_per_trace_hetero": round((float(eval_hetero["tstc_runtime_sec"]) * 1000.0) / eval_hetero["prompt_count"], 6),
            "eval_runtime_ms_per_trace_tamper": round((float(eval_tamper["tstc_runtime_sec_tamper"]) * 1000.0) / eval_tamper["prompt_count_tamper"], 6),
            "eval_dominant_mismatch_checkpoint": eval_hetero["tstc_dominant_mismatch_checkpoint"],
            "eval_prompt_count": eval_hetero["prompt_count"],
        }

    if variant.family == "projabs":
        hash_cfg = _projabs_hash_cfg(delta_map, variant)
        hash_params = _projabs_hash_params(delta_map, variant)
    else:
        hash_cfg = _projected_hash_cfg(delta_map, variant)
        hash_params = _projected_hash_params(delta_map, variant)
    eval_homo = scalar._pair_fpr(
        context["homo_left_eval"],
        context["homo_right_eval"],
        checkpoints,
        TARGET_STAGE,
        scalar._thc_cfg(),
        hash_cfg,
    )
    eval_hetero = scalar._pair_fpr(
        context["left_eval"],
        context["right_eval"],
        checkpoints,
        TARGET_STAGE,
        scalar._thc_cfg(),
        hash_cfg,
    )
    eval_tamper = proj._tamper_metrics_projcos(config, context["tamper_root"], eval_prompt_map, hash_params)
    return {
        "eval_honest_homo_fpr": eval_homo["tstc_fpr"],
        "eval_honest_hetero_fpr": eval_hetero["tstc_fpr"],
        "eval_tamper_tpr": eval_tamper["projcos_tpr"],
        "eval_tamper_locacc": eval_tamper["projcos_localization_acc"],
        "eval_runtime_ms_per_trace_homo": round((float(eval_homo["tstc_runtime_sec"]) * 1000.0) / eval_homo["prompt_count"], 6),
        "eval_runtime_ms_per_trace_hetero": round((float(eval_hetero["tstc_runtime_sec"]) * 1000.0) / eval_hetero["prompt_count"], 6),
        "eval_runtime_ms_per_trace_tamper": round((float(eval_tamper["projcos_runtime_sec_tamper"]) * 1000.0) / eval_tamper["prompt_count_tamper"], 6),
        "eval_dominant_mismatch_checkpoint": eval_hetero["tstc_dominant_mismatch_checkpoint"],
        "eval_prompt_count": eval_hetero["prompt_count"],
    }


def _plot(summary_rows: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return

    figure_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(summary_rows, key=lambda row: (int(row["signature_bytes_per_checkpoint_fp32"]), str(row["variant"])))
    xs = [int(row["signature_bytes_per_checkpoint_fp32"]) for row in ordered]
    fprs = [float(row["eval_honest_hetero_fpr"]) for row in ordered]
    tprs = [float(row["eval_tamper_tpr"]) for row in ordered]
    labels = [str(row["variant"]) for row in ordered]
    colors = {
        "scalar": "#0f766e",
        "projabs": "#2563eb",
        "projcos": "#c2410c",
    }
    feasible = [row for row in ordered if int(row.get("selected_from_feasible", 0)) == 1]
    frontier: List[Mapping[str, Any]] = []
    best_tpr = -1.0
    for row in sorted(feasible, key=lambda item: (float(item["eval_honest_hetero_fpr"]), -float(item["eval_tamper_tpr"]))):
        tpr = float(row["eval_tamper_tpr"])
        if tpr > best_tpr:
            frontier.append(row)
            best_tpr = tpr

    label_offsets = {
        ("scalar16", "Held-out FPR"): (8, 8),
        ("projscalar1_abs", "Held-out FPR"): (8, -14),
        ("scalar64", "Held-out FPR"): (8, 8),
        ("projcos4", "Held-out FPR"): (8, 10),
        ("projcos16", "Held-out FPR"): (8, -14),
        ("scalar16", "Held-out TPR"): (-38, 12),
        ("projscalar1_abs", "Held-out TPR"): (-46, -18),
        ("scalar64", "Held-out TPR"): (-34, 12),
        ("projcos4", "Held-out TPR"): (8, -18),
        ("projcos16", "Held-out TPR"): (8, 12),
    }

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 4.8), constrained_layout=True)
    for ax, ys, title, ylabel in (
        (axes[0], fprs, "Equal-Budget Honest-Hetero FPR", "Held-out FPR"),
        (axes[1], tprs, "Equal-Budget Tamper TPR", "Held-out TPR"),
    ):
        ax.set_xscale("log", base=2)
        for row, x, y, label in zip(ordered, xs, ys, labels):
            family = str(row["family"])
            marker = "o" if int(row.get("selected_from_feasible", 0)) == 1 else "x"
            ax.scatter([x], [y], s=90, color=colors[family], marker=marker, edgecolor="black", linewidth=0.8, zorder=3)
            offset = label_offsets.get((label, ylabel), (6, 6))
            ax.annotate(
                label,
                (x, y),
                textcoords="offset points",
                xytext=offset,
                fontsize=8,
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.72},
            )
        if ylabel == "Held-out TPR" and frontier:
            fx = [int(row["signature_bytes_per_checkpoint_fp32"]) for row in frontier]
            fy = [float(row["eval_tamper_tpr"]) for row in frontier]
            ax.plot(fx, fy, color="#111827", linestyle="--", linewidth=1.2, alpha=0.8, label="Pareto frontier")
            ax.legend(frameon=False, loc="lower right")
        ax.set_xlabel("Signature bytes per checkpoint (fp32)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.4)
        ax.set_xticks(sorted(set(xs)))
        ax.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda val, _: f"{int(val)}"))

    axes[0].set_ylim(-0.02, 1.02)
    axes[1].set_ylim(0.90, 1.045)
    fig.suptitle("E2 Equal-Budget Baseline: Scalar vs Projected-Token TSTC", fontsize=14)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    context = proj._live_context()
    config = scalar._load_json(context["config_path"])
    checkpoints = checkpoint_order(config)
    calib_prompt_map = scalar._prompt_map(config, split="calibration")
    eval_prompt_map = scalar._prompt_map(config, split="evaluation")

    candidate_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for variant in VARIANTS:
        variant_candidates: List[Dict[str, Any]] = []
        for percentile in PERCENTILES:
            if variant.family == "scalar":
                checkpoint_delta_map, _ = scalar._calibrate_percentile(
                    [context["left_calib"], context["right_calib"]],
                    percentile,
                )
            elif variant.family == "projabs":
                checkpoint_delta_map, _ = _calibrate_projabs_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    percentile,
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
            else:
                checkpoint_delta_map, _ = proj._calibrate_projcos_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    percentile,
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
            for mode, active_delta in (
                ("checkpoint_specific", checkpoint_delta_map),
                ("global_shared", scalar._globalize_delta_map(checkpoint_delta_map)),
            ):
                for scale in TOLERANCE_SCALES:
                    scaled_delta = _scale_delta_map(active_delta, scale)
                    metrics = _evaluate_variant(
                        variant=variant,
                        delta_map=scaled_delta,
                        config=config,
                        checkpoints=checkpoints,
                        calib_prompt_map=calib_prompt_map,
                        context=context,
                    )
                    row = {
                        **_row_common(variant, mode, percentile, scale),
                        **metrics,
                    }
                    variant_candidates.append(row)
                    candidate_rows.append(row)

        best = dict(_pick_best(variant_candidates))
        feasible_count = sum(1 for row in variant_candidates if float(row["calib_honest_hetero_fpr"]) <= TARGET_MAX_FPR)
        if variant.family == "scalar":
            if str(best["tolerance_mode"]) == "checkpoint_specific":
                selected_delta, _ = scalar._calibrate_percentile(
                    [context["left_calib"], context["right_calib"]],
                    float(best["percentile"]),
                )
            else:
                base_delta, _ = scalar._calibrate_percentile(
                    [context["left_calib"], context["right_calib"]],
                    float(best["percentile"]),
                )
                selected_delta = scalar._globalize_delta_map(base_delta)
        elif variant.family == "projabs":
            if str(best["tolerance_mode"]) == "checkpoint_specific":
                selected_delta, _ = _calibrate_projabs_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    float(best["percentile"]),
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
            else:
                base_delta, _ = _calibrate_projabs_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    float(best["percentile"]),
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
                selected_delta = scalar._globalize_delta_map(base_delta)
        else:
            if str(best["tolerance_mode"]) == "checkpoint_specific":
                selected_delta, _ = proj._calibrate_projcos_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    float(best["percentile"]),
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
            else:
                base_delta, _ = proj._calibrate_projcos_percentile(
                    [context["left_calib"], context["right_calib"]],
                    checkpoints,
                    float(best["percentile"]),
                    projection_dim=variant.projection_dim,
                    token_samples=variant.token_samples,
                )
                selected_delta = scalar._globalize_delta_map(base_delta)
        selected_delta = _scale_delta_map(selected_delta, float(best["tolerance_scale"]))
        best.update(
            _evaluate_selected_on_eval(
                variant=variant,
                delta_map=selected_delta,
                config=config,
                checkpoints=checkpoints,
                eval_prompt_map=eval_prompt_map,
                context=context,
            )
        )
        best["calib_feasible_count"] = feasible_count
        best["selected_from_feasible"] = int(feasible_count > 0)
        best["selection_fallback_reason"] = "" if feasible_count > 0 else f"no calibration candidate with FPR <= {TARGET_MAX_FPR:.2f}"
        best["selection_rule"] = f"prefer calib FPR<={TARGET_MAX_FPR:.2f}, then maximize (TPR-FPR)"
        summary_rows.append(best)

    candidate_csv = TABLE_DIR / f"{RUN_ID}_candidate_grid.csv"
    summary_csv = TABLE_DIR / f"{RUN_ID}_selected_summary.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_fpr_tpr_vs_budget.png"
    notes_path = NOTE_DIR / f"{RUN_ID}_notes.md"

    fieldnames = [
        "variant",
        "family",
        "tolerance_mode",
        "percentile",
        "tolerance_scale",
        "token_samples",
        "channel_samples",
        "projection_dim",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "calib_honest_hetero_fpr",
        "calib_tamper_tpr",
        "calib_tamper_locacc",
        "eval_honest_homo_fpr",
        "eval_honest_hetero_fpr",
        "eval_tamper_tpr",
        "eval_tamper_locacc",
        "eval_runtime_ms_per_trace_homo",
        "eval_runtime_ms_per_trace_hetero",
        "eval_runtime_ms_per_trace_tamper",
        "eval_dominant_mismatch_checkpoint",
        "calib_prompt_count",
        "eval_prompt_count",
        "calib_feasible_count",
        "selected_from_feasible",
        "selection_fallback_reason",
    ]
    _write_csv(candidate_csv, candidate_rows, fieldnames)
    _write_csv(summary_csv, summary_rows, fieldnames + ["selection_rule"])
    _plot(summary_rows, figure_path)

    notes_lines = [
        f"# {RUN_ID}",
        "",
        "- Protocol: select each variant's operating point on calibration-only A/B live captures, then report held-out evaluation metrics on 200 eval prompts.",
        f"- Selection rule: prefer calibration honest-hetero FPR <= {TARGET_MAX_FPR:.2f}; within feasible points maximize (TPR - FPR), then TPR, then LocAcc.",
        "- Variants: scalar16, scalar64, projscalar1_abs, projcos4, projcos16.",
        "- Bridge variant: projscalar1_abs uses 16 prefill tokens x d=1 random projection and compares mean absolute projected gap. The real signature payload is 16 fp32 scalars / 64B per checkpoint on these captures; the handbook table's 256B row appears to contain an arithmetic typo for 16 x 1.",
        f"- Candidate grid CSV: {candidate_csv}",
        f"- Selected summary CSV: {summary_csv}",
        f"- Figure: {figure_path}",
        "",
        "## Selected held-out results",
        "",
    ]
    for row in summary_rows:
        notes_lines.append(
            f"- {row['variant']}: bytes/ckpt={row['signature_bytes_per_checkpoint_fp32']}, "
            f"mode={row['tolerance_mode']}, p={row['percentile']}, scale={row['tolerance_scale']}, "
            f"eval FPR={row['eval_honest_hetero_fpr']}, eval TPR={row['eval_tamper_tpr']}, "
            f"eval LocAcc={row['eval_tamper_locacc']}, "
            f"selected_from_feasible={row['selected_from_feasible']}."
        )
    notes_path.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")

    print(f"candidate grid : {candidate_csv}")
    print(f"selected table : {summary_csv}")
    print(f"figure         : {figure_path}")
    print(f"notes          : {notes_path}")


if __name__ == "__main__":
    main()
