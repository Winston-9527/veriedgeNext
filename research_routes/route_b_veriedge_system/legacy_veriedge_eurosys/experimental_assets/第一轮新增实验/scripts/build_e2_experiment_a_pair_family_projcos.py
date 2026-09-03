from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import _sample_indices, compute_hash_chain, first_mismatch_index, project_prefill_signature  # type: ignore
from pipeline_qwen import run_qwen_trial  # type: ignore

import build_e2_equal_budget_baseline as eq  # type: ignore
import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = "20260512"
OWNER = "experiment_a_pair_family_projcos"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
NOTE_DIR = E2_DIR / "notes"

TARGET_STAGE = "prefill"

PAIR_MANIFESTS = [
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_b_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_b_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_c_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_c_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_d_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_d_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_b_vs_d_40_200" / "exp_e1_20260504_t4strict_pair_b_vs_d_40_200_manifest.json",
]

VARIANTS: Sequence[eq.VariantSpec] = (
    eq.VariantSpec("scalar16", "scalar", 1, 16, 0, 16, 64),
    eq.VariantSpec("scalar64", "scalar", 1, 64, 0, 64, 256),
    eq.VariantSpec("projcos4", "projcos", 16, 0, 4, 64, 256),
    eq.VariantSpec("projcos8", "projcos", 16, 0, 8, 128, 512),
    eq.VariantSpec("projcos16", "projcos", 16, 0, 16, 256, 1024),
)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _load_context(manifest_path: Path) -> Dict[str, Any]:
    manifest = scalar._load_json(manifest_path)
    left_eval = Path(manifest["pairs"][0]["left_capture_root"]).resolve()
    right_eval = Path(manifest["pairs"][0]["right_capture_root"]).resolve()
    left_calib = left_eval.parent / f"{left_eval.name.replace('_eval', '_calib')}"
    right_calib = right_eval.parent / f"{right_eval.name.replace('_eval', '_calib')}"
    return {
        "pair_id": manifest_path.parent.name,
        "pair_label": str(manifest["pairs"][0]["pair_label"]),
        "config_path": Path(manifest["config"]).resolve(),
        "left_calib": left_calib,
        "right_calib": right_calib,
        "left_eval": left_eval,
        "right_eval": right_eval,
        "tamper_root": right_eval,
    }


def _selected_delta(
    row: Mapping[str, Any],
    variant: eq.VariantSpec,
    checkpoints: Sequence[str],
    context: Mapping[str, Any],
) -> Dict[str, Dict[str, float]]:
    percentile = float(row["percentile"])
    scale = float(row["tolerance_scale"])
    if variant.family == "scalar":
        base_delta, _ = scalar._calibrate_percentile([context["left_calib"], context["right_calib"]], percentile)
    else:
        base_delta, _ = proj._calibrate_projcos_percentile(
            [context["left_calib"], context["right_calib"]],
            checkpoints,
            percentile,
            projection_dim=variant.projection_dim,
            token_samples=variant.token_samples,
        )
    active_delta = base_delta if row["tolerance_mode"] == "checkpoint_specific" else scalar._globalize_delta_map(base_delta)
    return scalar._scale_delta_map(active_delta, scale)


def _hash_cfg(delta_map: Dict[str, Dict[str, float]], variant: eq.VariantSpec):
    if variant.family == "scalar":
        return eq._scalar_hash_cfg(delta_map, variant)
    return eq._projected_hash_cfg(delta_map, variant)


def _hash_params(delta_map: Dict[str, Dict[str, float]], variant: eq.VariantSpec) -> Dict[str, Any]:
    if variant.family == "scalar":
        return eq._scalar_hash_params(delta_map, variant)
    return eq._projected_hash_params(delta_map, variant)


def _load_bundle(root: Path, prompt_id: str) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], str]:
    return load_capture_bundle_for_prompt(root, prompt_id)


def _projcos_gap(left_tensor: np.ndarray, right_tensor: np.ndarray, cfg: Any, checkpoint: str, seed: int) -> float:
    _, left_sig = project_prefill_signature(left_tensor, cfg, checkpoint, seed)
    _, right_sig = project_prefill_signature(right_tensor, cfg, checkpoint, seed)
    denom = np.maximum(np.linalg.norm(left_sig, axis=1) * np.linalg.norm(right_sig, axis=1), 1e-12)
    cosine = np.sum(left_sig * right_sig, axis=1) / denom
    return float(np.mean(1.0 - cosine)) if cosine.size else 0.0


def _scalar_gap(left_tensor: np.ndarray, right_tensor: np.ndarray, cfg: Any, checkpoint: str, seed: int) -> float:
    left = np.nan_to_num(np.asarray(left_tensor, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    right = np.nan_to_num(np.asarray(right_tensor, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if left.ndim != 3 or right.ndim != 3:
        return 0.0
    left_rows = left.reshape(-1, left.shape[-1])
    right_rows = right.reshape(-1, right.shape[-1])
    token_idx = _sample_indices(left_rows.shape[0], int(cfg.prefill_token_samples), seed)
    gaps: List[float] = []
    for offset, row_idx in enumerate(token_idx):
        channel_idx = _sample_indices(left_rows.shape[1], int(cfg.prefill_channel_samples), seed + 1000 + offset + int(row_idx))
        gaps.extend(np.abs(left_rows[int(row_idx), channel_idx] - right_rows[int(row_idx), channel_idx]).astype(np.float32).tolist())
    return float(np.mean(gaps)) if gaps else 0.0


def _eval_hetero_detail(
    *,
    pair_id: str,
    pair_label: str,
    variant: eq.VariantSpec,
    hash_cfg: Any,
    checkpoints: Sequence[str],
    left_eval: Path,
    right_eval: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    prompt_ids = scalar._shared_prompt_ids(left_eval, right_eval)
    mismatch_counter: Counter[str] = Counter()
    detail_rows: List[Dict[str, Any]] = []
    gap_rows: List[Dict[str, Any]] = []
    start = time.perf_counter()

    for prompt_id in prompt_ids:
        left_bundle, _, _ = _load_bundle(left_eval, prompt_id)
        right_bundle, _, _ = _load_bundle(right_eval, prompt_id)
        detected = False
        first_checkpoint = ""
        for stage_key in ordered_stage_keys(left_bundle.keys()):
            if stage_family(stage_key) != TARGET_STAGE:
                continue
            left_stage = left_bundle[stage_key]
            right_stage = right_bundle[stage_key]
            left_chain = compute_hash_chain(left_stage, checkpoints, TARGET_STAGE, hash_cfg)
            right_chain = compute_hash_chain(right_stage, checkpoints, TARGET_STAGE, hash_cfg)
            mismatch = first_mismatch_index(left_chain, right_chain)
            if mismatch is not None:
                detected = True
                first_checkpoint = checkpoints[mismatch]
                mismatch_counter[first_checkpoint] += 1
            for idx, checkpoint in enumerate(checkpoints):
                key = checkpoint
                if key not in left_stage or key not in right_stage:
                    continue
                seed = int(hash_cfg.seed_base) + idx
                gap = (
                    _projcos_gap(left_stage[key], right_stage[key], hash_cfg, checkpoint, seed)
                    if variant.family == "projcos"
                    else _scalar_gap(left_stage[key], right_stage[key], hash_cfg, checkpoint, seed)
                )
                threshold = float(hash_cfg.delta_map.get("prefill", {}).get(checkpoint, 0.0))
                gap_rows.append(
                    {
                        "pair_id": pair_id,
                        "pair_label": pair_label,
                        "variant": variant.name,
                        "family": variant.family,
                        "prompt_id": prompt_id,
                        "checkpoint": checkpoint,
                        "gap_metric": "mean_projected_cosine_gap" if variant.family == "projcos" else "mean_sampled_abs_gap",
                        "gap_value": round(gap, 9),
                        "threshold": round(threshold, 9),
                        "over_threshold": int(gap > threshold),
                    }
                )
            break
        detail_rows.append(
            {
                "pair_id": pair_id,
                "pair_label": pair_label,
                "variant": variant.name,
                "family": variant.family,
                "prompt_id": prompt_id,
                "detected": int(detected),
                "first_mismatch_checkpoint": first_checkpoint,
            }
        )

    runtime_sec = time.perf_counter() - start
    count = len(prompt_ids)
    summary = {
        "eval_prompt_count": count,
        "eval_honest_hetero_fpr": round(sum(int(row["detected"]) for row in detail_rows) / count, 6) if count else 0.0,
        "eval_runtime_ms_per_trace_hetero": round((runtime_sec * 1000.0) / count, 6) if count else 0.0,
        "eval_dominant_mismatch_checkpoint": mismatch_counter.most_common(1)[0][0] if mismatch_counter else "",
        "eval_mismatch_c1_count": mismatch_counter["C1"],
        "eval_mismatch_c2_count": mismatch_counter["C2"],
        "eval_mismatch_c3_count": mismatch_counter["C3"],
    }
    return summary, detail_rows, gap_rows


def _tamper_detail(
    *,
    pair_id: str,
    pair_label: str,
    variant: eq.VariantSpec,
    config: Dict[str, Any],
    capture_root: Path,
    prompt_map: Mapping[str, Dict[str, str]],
    hash_params: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    prompt_ids = sorted(prompt_map.keys())
    rows: List[Dict[str, Any]] = []
    start = time.perf_counter()
    verifier = "tstc" if variant.family == "scalar" else "tstc_projcos"
    for prompt_id in prompt_ids:
        bundle, metadata, runtime = _load_bundle(capture_root, prompt_id)
        result = run_qwen_trial(
            config=config,
            scenario="tamper",
            verifier=verifier,
            trial_index=scalar._trial_index_for_prompt(prompt_id),
            prompt_record=prompt_map[prompt_id],
            hash_params=hash_params,
            captured_bundle=bundle,
            captured_metadata=metadata,
            captured_runtime=runtime,
        )
        for record in result["records"]:
            if str(record["stage"]) != TARGET_STAGE:
                continue
            rows.append(
                {
                    "pair_id": pair_id,
                    "pair_label": pair_label,
                    "variant": variant.name,
                    "family": variant.family,
                    "prompt_id": prompt_id,
                    "detected": int(bool(record["detected"])),
                    "localization_correct": int(bool(record["localization_correct"])),
                    "first_mismatch_checkpoint": str(record["first_mismatch_checkpoint"]),
                }
            )
    runtime_sec = time.perf_counter() - start
    count = len(rows)
    mismatch_counter = Counter(row["first_mismatch_checkpoint"] for row in rows if row["first_mismatch_checkpoint"])
    summary = {
        "eval_tamper_tpr": round(sum(int(row["detected"]) for row in rows) / count, 6) if count else 0.0,
        "eval_tamper_locacc": round(sum(int(row["localization_correct"]) for row in rows) / count, 6) if count else 0.0,
        "eval_runtime_ms_per_trace_tamper": round((runtime_sec * 1000.0) / count, 6) if count else 0.0,
        "eval_tamper_dominant_mismatch_checkpoint": mismatch_counter.most_common(1)[0][0] if mismatch_counter else "",
        "eval_tamper_mismatch_c1_count": mismatch_counter["C1"],
        "eval_tamper_mismatch_c2_count": mismatch_counter["C2"],
        "eval_tamper_mismatch_c3_count": mismatch_counter["C3"],
    }
    return summary, rows


def _plot(summary_rows: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return
    pairs = ["t4strict_pair_a_vs_b_40_200", "t4strict_pair_a_vs_c_40_200", "t4strict_pair_a_vs_d_40_200", "t4strict_pair_b_vs_d_40_200"]
    variants = ["scalar16", "scalar64", "projcos4", "projcos8", "projcos16"]
    pair_labels = {
        "t4strict_pair_a_vs_b_40_200": "A/B",
        "t4strict_pair_a_vs_c_40_200": "A/C",
        "t4strict_pair_a_vs_d_40_200": "A/D",
        "t4strict_pair_b_vs_d_40_200": "B/D",
    }
    colors = {"scalar16": "#0f766e", "scalar64": "#14b8a6", "projcos4": "#c2410c", "projcos8": "#ea580c", "projcos16": "#f59e0b"}
    lookup = {(str(row["pair_id"]), str(row["variant"])): row for row in summary_rows}

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), constrained_layout=True)
    width = 0.15
    base_x = np.arange(len(pairs))
    for i, variant in enumerate(variants):
        offset = (i - 2) * width
        fprs = [float(lookup[(pair, variant)]["eval_honest_hetero_fpr"]) for pair in pairs]
        tprs = [float(lookup[(pair, variant)]["eval_tamper_tpr"]) for pair in pairs]
        axes[0].bar(base_x + offset, fprs, width=width, label=variant, color=colors[variant])
        axes[1].bar(base_x + offset, tprs, width=width, label=variant, color=colors[variant])
    for ax, title, ylabel in (
        (axes[0], "Experiment A pair family: held-out honest-hetero FPR", "FPR"),
        (axes[1], "Experiment A pair family: held-out tamper TPR", "TPR"),
    ):
        ax.set_xticks(base_x, [pair_labels[pair] for pair in pairs])
        ax.set_ylim(0.0, 1.05)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
    axes[1].legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.3))
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, dpi=220, bbox_inches="tight")
    fig.savefig(figure_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _paper_table_rows(summary_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in summary_rows:
        is_feasible = int(row["selected_from_feasible"]) == 1
        status = "calibration_feasible" if is_feasible else "fallback_no_feasible_calib_fpr"
        rows.append(
            {
                "pair_id": row["pair_id"],
                "pair_label": row["pair_label"],
                "variant": row["variant"],
                "family": row["family"],
                "paper_status": status,
                "paper_include_as_main": int(is_feasible),
                "calib_feasible_count": row["calib_feasible_count"],
                "selected_from_feasible": row["selected_from_feasible"],
                "selection_fallback_reason": row["selection_fallback_reason"],
                "tolerance_mode": row["tolerance_mode"],
                "percentile": row["percentile"],
                "tolerance_scale": row["tolerance_scale"],
                "signature_scalars_per_checkpoint": row["signature_scalars_per_checkpoint"],
                "signature_bytes_per_checkpoint_fp32": row["signature_bytes_per_checkpoint_fp32"],
                "calib_honest_hetero_fpr": row["calib_honest_hetero_fpr"],
                "calib_tamper_tpr": row["calib_tamper_tpr"],
                "eval_honest_hetero_fpr": row["eval_honest_hetero_fpr"],
                "eval_tamper_tpr": row["eval_tamper_tpr"],
                "eval_tamper_locacc": row["eval_tamper_locacc"],
            }
        )
    return rows


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    candidate_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    hetero_detail_rows: List[Dict[str, Any]] = []
    tamper_detail_rows: List[Dict[str, Any]] = []
    gap_rows: List[Dict[str, Any]] = []

    for manifest_path in PAIR_MANIFESTS:
        context = _load_context(manifest_path)
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        calib_prompt_map = scalar._prompt_map(config, split="calibration")
        eval_prompt_map = scalar._prompt_map(config, split="evaluation")

        for variant in VARIANTS:
            variant_candidates: List[Dict[str, Any]] = []
            for percentile in eq.PERCENTILES:
                if variant.family == "scalar":
                    checkpoint_delta_map, _ = scalar._calibrate_percentile([context["left_calib"], context["right_calib"]], percentile)
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
                    for scale in eq.TOLERANCE_SCALES:
                        scaled_delta = scalar._scale_delta_map(active_delta, scale)
                        metrics = eq._evaluate_variant(
                            variant=variant,
                            delta_map=scaled_delta,
                            config=config,
                            checkpoints=checkpoints,
                            calib_prompt_map=calib_prompt_map,
                            context=context,
                        )
                        row = {
                            "pair_id": context["pair_id"],
                            "pair_label": context["pair_label"],
                            **eq._row_common(variant, mode, percentile, scale),
                            **metrics,
                        }
                        variant_candidates.append(row)
                        candidate_rows.append(row)

            feasible_count = sum(1 for row in variant_candidates if float(row["calib_honest_hetero_fpr"]) <= eq.TARGET_MAX_FPR)
            best = dict(eq._pick_best(variant_candidates))
            selected_delta = _selected_delta(best, variant, checkpoints, context)
            cfg = _hash_cfg(selected_delta, variant)
            params = _hash_params(selected_delta, variant)
            hetero_metrics, hetero_rows, variant_gap_rows = _eval_hetero_detail(
                pair_id=context["pair_id"],
                pair_label=context["pair_label"],
                variant=variant,
                hash_cfg=cfg,
                checkpoints=checkpoints,
                left_eval=context["left_eval"],
                right_eval=context["right_eval"],
            )
            tamper_metrics, variant_tamper_rows = _tamper_detail(
                pair_id=context["pair_id"],
                pair_label=context["pair_label"],
                variant=variant,
                config=config,
                capture_root=context["tamper_root"],
                prompt_map=eval_prompt_map,
                hash_params=params,
            )
            best.update(hetero_metrics)
            best.update(tamper_metrics)
            best["pair_id"] = context["pair_id"]
            best["pair_label"] = context["pair_label"]
            best["calib_feasible_count"] = feasible_count
            best["selected_from_feasible"] = int(feasible_count > 0)
            best["selection_fallback_reason"] = "" if feasible_count > 0 else f"no calibration candidate with FPR <= {eq.TARGET_MAX_FPR:.2f}"
            best["selection_rule"] = f"prefer calib FPR<={eq.TARGET_MAX_FPR:.2f}, then maximize (TPR-FPR)"
            summary_rows.append(best)
            hetero_detail_rows.extend(hetero_rows)
            tamper_detail_rows.extend(variant_tamper_rows)
            gap_rows.extend(variant_gap_rows)

    candidate_csv = TABLE_DIR / f"{RUN_ID}_candidate_grid.csv"
    summary_csv = TABLE_DIR / f"{RUN_ID}_selected_summary.csv"
    hetero_detail_csv = TABLE_DIR / f"{RUN_ID}_hetero_mismatch_detail.csv"
    tamper_detail_csv = TABLE_DIR / f"{RUN_ID}_tamper_mismatch_detail.csv"
    gap_csv = TABLE_DIR / f"{RUN_ID}_gap_distribution.csv"
    paper_table_csv = TABLE_DIR / f"{RUN_ID}_paper_main_table.csv"
    fallback_table_csv = TABLE_DIR / f"{RUN_ID}_fallback_baselines.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_pair_family_fpr_tpr.png"
    notes_path = NOTE_DIR / f"{RUN_ID}_notes.md"

    common_fields = [
        "pair_id",
        "pair_label",
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
        "calib_prompt_count",
    ]
    summary_fields = common_fields + [
        "calib_feasible_count",
        "selected_from_feasible",
        "selection_fallback_reason",
        "eval_honest_hetero_fpr",
        "eval_tamper_tpr",
        "eval_tamper_locacc",
        "eval_runtime_ms_per_trace_hetero",
        "eval_runtime_ms_per_trace_tamper",
        "eval_dominant_mismatch_checkpoint",
        "eval_mismatch_c1_count",
        "eval_mismatch_c2_count",
        "eval_mismatch_c3_count",
        "eval_tamper_dominant_mismatch_checkpoint",
        "eval_tamper_mismatch_c1_count",
        "eval_tamper_mismatch_c2_count",
        "eval_tamper_mismatch_c3_count",
        "eval_prompt_count",
        "selection_rule",
    ]
    _write_csv(candidate_csv, candidate_rows, common_fields)
    _write_csv(summary_csv, summary_rows, summary_fields)
    _write_csv(
        hetero_detail_csv,
        hetero_detail_rows,
        ["pair_id", "pair_label", "variant", "family", "prompt_id", "detected", "first_mismatch_checkpoint"],
    )
    _write_csv(
        tamper_detail_csv,
        tamper_detail_rows,
        ["pair_id", "pair_label", "variant", "family", "prompt_id", "detected", "localization_correct", "first_mismatch_checkpoint"],
    )
    _write_csv(
        gap_csv,
        gap_rows,
        ["pair_id", "pair_label", "variant", "family", "prompt_id", "checkpoint", "gap_metric", "gap_value", "threshold", "over_threshold"],
    )
    paper_rows = _paper_table_rows(summary_rows)
    paper_fields = [
        "pair_id",
        "pair_label",
        "variant",
        "family",
        "paper_status",
        "paper_include_as_main",
        "calib_feasible_count",
        "selected_from_feasible",
        "selection_fallback_reason",
        "tolerance_mode",
        "percentile",
        "tolerance_scale",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "calib_honest_hetero_fpr",
        "calib_tamper_tpr",
        "eval_honest_hetero_fpr",
        "eval_tamper_tpr",
        "eval_tamper_locacc",
    ]
    _write_csv(paper_table_csv, paper_rows, paper_fields)
    _write_csv(
        fallback_table_csv,
        [row for row in paper_rows if int(row["paper_include_as_main"]) == 0],
        paper_fields,
    )
    _plot(summary_rows, figure_path)

    fallback_rows = [row for row in summary_rows if int(row["selected_from_feasible"]) == 0]
    lines = [
        f"# {RUN_ID}",
        "",
        "- Covers strict A/B, A/C, A/D, and B/D with the same held-out protocol.",
        "- Operating points are selected on 40 calibration prompts and evaluated on 200 held-out prompts.",
        "- Summary includes calibration feasibility flags, first-mismatch counts, and links to gap distributions.",
        f"- Candidate grid: {candidate_csv}",
        f"- Selected summary: {summary_csv}",
        f"- Honest-hetero mismatch detail: {hetero_detail_csv}",
        f"- Tamper mismatch detail: {tamper_detail_csv}",
        f"- Gap distribution: {gap_csv}",
        f"- Paper-ready table with explicit feasibility status: {paper_table_csv}",
        f"- Fallback-only baseline table: {fallback_table_csv}",
        f"- Figure: {figure_path}",
        "",
        "## Calibration fallback rows",
        "",
    ]
    if fallback_rows:
        for row in fallback_rows:
            lines.append(
                f"- {row['pair_id']} / {row['variant']}: {row['selection_fallback_reason']}; "
                f"selected calib FPR={row['calib_honest_hetero_fpr']}."
            )
    else:
        lines.append("- None.")
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"candidate grid : {candidate_csv}")
    print(f"selected table : {summary_csv}")
    print(f"hetero detail  : {hetero_detail_csv}")
    print(f"tamper detail  : {tamper_detail_csv}")
    print(f"gap table      : {gap_csv}")
    print(f"paper table    : {paper_table_csv}")
    print(f"fallback table : {fallback_table_csv}")
    print(f"figure         : {figure_path}")
    print(f"notes          : {notes_path}")


if __name__ == "__main__":
    main()
