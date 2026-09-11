from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from attack import inject_tamper  # type: ignore
from attack_material import inject_stale_replay, inject_wrong_prompt_checkpoint  # type: ignore
from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import compute_hash_chain, first_mismatch_index  # type: ignore

import build_e2_equal_budget_baseline as eq  # type: ignore
import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "material_tamper_full_matrix"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
NOTE_DIR = E2_DIR / "notes"

TARGET_STAGE = "prefill"
ATTACK_CHECKPOINT = "C2"
TAMPER_CFG_PATH = REPO_ROOT / "artifacts" / "thc" / "config" / "e1_real_qwen_tstc_prefill_1x1_40_200.json"

PAIR_MANIFESTS = [
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_b_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_b_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_b_rtxint8_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_b_rtxint8_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_c_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_c_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_a_vs_d_40_200" / "exp_e1_20260504_t4strict_pair_a_vs_d_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_b_vs_d_40_200" / "exp_e1_20260504_t4strict_pair_b_vs_d_40_200_manifest.json",
    REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4strict_pair_e_vs_f_40_200" / "exp_e1_20260504_t4strict_pair_e_vs_f_40_200_manifest.json",
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


def _load_bundle(root: Path, prompt_id: str) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    bundle, metadata_rows, _runtime = load_capture_bundle_for_prompt(root, prompt_id)
    return bundle, metadata_rows


def _context_from_manifest(path: Path) -> Dict[str, Any]:
    manifest = scalar._load_json(path)
    left_eval = Path(manifest["pairs"][0]["left_capture_root"]).resolve()
    right_eval = Path(manifest["pairs"][0]["right_capture_root"]).resolve()
    left_calib = left_eval.parent / f"{left_eval.name.replace('_eval', '_calib')}"
    right_calib = right_eval.parent / f"{right_eval.name.replace('_eval', '_calib')}"
    pair_id = path.parent.name
    return {
        "pair_id": pair_id,
        "pair_label": str(manifest["pairs"][0]["pair_label"]),
        "config_path": Path(manifest["config"]).resolve(),
        "left_calib": left_calib,
        "right_calib": right_calib,
        "left_eval": left_eval,
        "right_eval": right_eval,
        "tamper_root": right_eval,
    }


def _stack_key_from_root(root: Path) -> str:
    name = root.name
    if "_40_200_eval" in name:
        return name.replace("_40_200_eval", "")
    return name


def _rerun_root_for(right_eval: Path) -> Tuple[Path, str]:
    stack_key = _stack_key_from_root(right_eval)
    direct_rerun = right_eval.parent / f"{right_eval.name}_rerun"
    if direct_rerun.exists():
        return direct_rerun, "same_stack_rerun"

    # Manual mapping for A-D stacks present in absrepro captures.
    mappings = {
        "t4strict_stack_a_apple_metal8_applebf16_rtxfp32": "absrepro_r2_stack_a_apple_metal8_applebf16_rtxfp32_40_200_eval",
        "t4strict_stack_b_applebf16_applebf16_rtxfp32": "absrepro_r2_stack_b_applebf16_applebf16_rtxfp32_40_200_eval",
        "t4strict_stack_c_rtxbf16_applebf16_rtxfp32": "absrepro_r2_stack_c_rtxbf16_applebf16_rtxfp32_40_200_eval",
        "t4strict_stack_d_rtxfp32_applebf16_rtxfp32": "absrepro_r2_stack_d_rtxfp32_applebf16_rtxfp32_40_200_eval",
    }
    if stack_key in mappings:
        mapped = right_eval.parent / mappings[stack_key]
        if mapped.exists():
            return mapped, "absrepro_same_stack"

    # Fall back to a stale checkpoint from the same run when no rerun-compatible
    # donor stack exists for this pair. This still yields a shape-compatible but
    # semantically stale checkpoint substitution.
    return right_eval, "same_run_prev_prompt"


def _selected_hash_cfg(row: Mapping[str, Any], checkpoints: Sequence[str], context: Mapping[str, Any]):
    percentile = float(row["percentile"])
    tolerance_scale = float(row["tolerance_scale"])
    variant = next(spec for spec in VARIANTS if spec.name == row["variant"])
    if variant.family == "scalar":
        base_delta, _ = scalar._calibrate_percentile([context["left_calib"], context["right_calib"]], percentile)
        active_delta = base_delta if row["tolerance_mode"] == "checkpoint_specific" else scalar._globalize_delta_map(base_delta)
        scaled = scalar._scale_delta_map(active_delta, tolerance_scale)
        return variant, eq._scalar_hash_cfg(scaled, variant)

    base_delta, _ = proj._calibrate_projcos_percentile(
        [context["left_calib"], context["right_calib"]],
        checkpoints,
        percentile,
        projection_dim=variant.projection_dim,
        token_samples=variant.token_samples,
    )
    active_delta = base_delta if row["tolerance_mode"] == "checkpoint_specific" else scalar._globalize_delta_map(base_delta)
    scaled = scalar._scale_delta_map(active_delta, tolerance_scale)
    return variant, eq._projected_hash_cfg(scaled, variant)


def _trial_index_for_prompt(prompt_id: str) -> int:
    return scalar._trial_index_for_prompt(prompt_id)


def _tamper_cfg() -> Dict[str, Any]:
    cfg = scalar._load_json(TAMPER_CFG_PATH)
    tamper = dict(cfg.get("tamper", {}))
    tamper.setdefault("checkpoint", ATTACK_CHECKPOINT)
    tamper.setdefault("strength", 0.15)
    tamper.setdefault("relative_to_tensor_std", True)
    tamper.setdefault("min_std", 1e-6)
    return tamper


def _compute_detect(
    validator_bundle: Dict[str, Dict[str, Any]],
    candidate_bundle: Dict[str, Dict[str, Any]],
    checkpoints: Sequence[str],
    hash_cfg: Any,
) -> Tuple[bool, str]:
    for stage_key in ordered_stage_keys(validator_bundle.keys()):
        if stage_family(stage_key) != TARGET_STAGE:
            continue
        ref_chain = compute_hash_chain(validator_bundle[stage_key], checkpoints, TARGET_STAGE, hash_cfg)
        cand_chain = compute_hash_chain(candidate_bundle[stage_key], checkpoints, TARGET_STAGE, hash_cfg)
        mismatch = first_mismatch_index(ref_chain, cand_chain)
        if mismatch is not None:
            return True, checkpoints[mismatch] if mismatch < len(checkpoints) else ""
    return False, ""


def _plot(attack_summary: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return

    focus_variants = ["scalar16", "projcos4"]
    focus_pairs = [str(row["pair_id"]) for row in attack_summary]
    focus_pairs = sorted(set(focus_pairs))
    attacks = ["gaussian", "stale_replay", "wrong_prompt"]

    fig, axes = plt.subplots(len(focus_pairs), 1, figsize=(10, 3.6 * len(focus_pairs)), constrained_layout=True)
    if len(focus_pairs) == 1:
        axes = [axes]

    colors = {"scalar16": "#0f766e", "projcos4": "#c2410c"}
    for ax, pair_id in zip(axes, focus_pairs):
        x = range(len(attacks))
        width = 0.35
        for idx, variant in enumerate(focus_variants):
            subset = {
                str(row["attack_family"]): row
                for row in attack_summary
                if str(row["pair_id"]) == pair_id and str(row["variant"]) == variant
            }
            vals = [float(subset.get(attack, {}).get("detection_rate", 0.0)) for attack in attacks]
            shift = -width / 2 if idx == 0 else width / 2
            ax.bar([i + shift for i in x], vals, width=width, label=variant, color=colors[variant])
        ax.set_xticks(list(x))
        ax.set_xticklabels(attacks)
        ax.set_ylim(0.0, 1.05)
        ax.set_ylabel("TPR")
        ax.set_title(pair_id)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
        ax.legend(frameon=False)

    fig.suptitle("Full Material-Tamper Matrix: TPR for Scalar16 vs ProjCos4", fontsize=14)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def _select_operating_points(context: Mapping[str, Any], config: Dict[str, Any], checkpoints: Sequence[str]) -> List[Dict[str, Any]]:
    calib_prompt_map = scalar._prompt_map(config, split="calibration")
    select_context = dict(context)
    select_context["tamper_root"] = context["right_calib"]
    selected_rows: List[Dict[str, Any]] = []

    for variant in VARIANTS:
        candidates: List[Dict[str, Any]] = []
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
                        context=select_context,
                    )
                    candidates.append(
                        {
                            **eq._row_common(variant, mode, percentile, scale),
                            **metrics,
                        }
                    )
        best = dict(eq._pick_best(candidates))
        best["selection_rule"] = f"prefer calib FPR<={eq.TARGET_MAX_FPR:.2f}, then maximize (TPR-FPR)"
        selected_rows.append(best)
    return selected_rows


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    selected_rows_all: List[Dict[str, Any]] = []
    detail_rows: List[Dict[str, Any]] = []
    attack_summary_rows: List[Dict[str, Any]] = []
    tamper_cfg = _tamper_cfg()

    for manifest_path in PAIR_MANIFESTS:
        context = _context_from_manifest(manifest_path)
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        selected_rows = _select_operating_points(context, config, checkpoints)
        selected_rows_all.extend([{**row, "pair_id": context["pair_id"], "pair_label": context["pair_label"]} for row in selected_rows])

        prompt_ids = scalar._shared_prompt_ids(context["right_eval"], context["right_eval"])
        stale_root, stale_source_kind = _rerun_root_for(context["right_eval"])

        for row in selected_rows:
            variant, hash_cfg = _selected_hash_cfg(row, checkpoints, context)
            mismatch_counter: Dict[str, Counter[str]] = defaultdict(Counter)
            attack_records: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
            start = time.perf_counter()

            for idx, prompt_id in enumerate(prompt_ids):
                validator_bundle, _ = _load_bundle(context["right_eval"], prompt_id)
                base_bundle, _ = _load_bundle(context["right_eval"], prompt_id)
                stale_prompt_id = prompt_ids[(idx - 1) % len(prompt_ids)]
                stale_donor_bundle, _ = _load_bundle(stale_root, stale_prompt_id)
                wrong_prompt_id = prompt_ids[(idx + 1) % len(prompt_ids)]
                wrong_donor_bundle, _ = _load_bundle(context["right_eval"], wrong_prompt_id)

                attacks = {
                    "gaussian": inject_tamper(
                        base_bundle,
                        checkpoint=str(tamper_cfg.get("checkpoint", ATTACK_CHECKPOINT)),
                        strength=float(tamper_cfg.get("strength", 0.15)),
                        seed=3000 + _trial_index_for_prompt(prompt_id),
                        relative_to_tensor_std=bool(tamper_cfg.get("relative_to_tensor_std", True)),
                        min_std=float(tamper_cfg.get("min_std", 1e-6)),
                    ),
                    "stale_replay": inject_stale_replay(base_bundle, stale_donor_bundle, checkpoint=ATTACK_CHECKPOINT),
                    "wrong_prompt": inject_wrong_prompt_checkpoint(base_bundle, wrong_donor_bundle, checkpoint=ATTACK_CHECKPOINT),
                }

                for attack_name, candidate_bundle in attacks.items():
                    detected, first_checkpoint = _compute_detect(validator_bundle, candidate_bundle, checkpoints, hash_cfg)
                    loc_ok = detected and first_checkpoint == ATTACK_CHECKPOINT
                    attack_records[attack_name].append((detected, loc_ok))
                    if first_checkpoint:
                        mismatch_counter[attack_name][first_checkpoint] += 1
                    detail_rows.append(
                        {
                            "pair_id": context["pair_id"],
                            "pair_label": context["pair_label"],
                            "variant": variant.name,
                            "family": variant.family,
                            "attack_family": attack_name,
                            "prompt_id": prompt_id,
                            "donor_prompt_id": (
                                wrong_prompt_id
                                if attack_name == "wrong_prompt"
                                else stale_prompt_id if attack_name == "stale_replay" else prompt_id
                            ),
                            "donor_source": (
                                "same_run_next_prompt"
                                if attack_name == "wrong_prompt"
                                else stale_source_kind
                                if attack_name == "stale_replay"
                                else "gaussian_noise"
                            ),
                            "attack_checkpoint": ATTACK_CHECKPOINT,
                            "detected": int(detected),
                            "localization_correct": int(loc_ok),
                            "first_mismatch_checkpoint": first_checkpoint,
                        }
                    )

            runtime_ms_per_trace = ((time.perf_counter() - start) * 1000.0) / (len(prompt_ids) * 3)
            for attack_name in ("gaussian", "stale_replay", "wrong_prompt"):
                records = attack_records[attack_name]
                n = len(records)
                detect_rate = sum(1 for detected, _ in records if detected) / n if n else 0.0
                loc_acc = sum(1 for _, loc in records if loc) / n if n else 0.0
                attack_summary_rows.append(
                    {
                        "pair_id": context["pair_id"],
                        "pair_label": context["pair_label"],
                        "variant": variant.name,
                        "family": variant.family,
                        "attack_family": attack_name,
                        "prompt_count": n,
                        "signature_scalars_per_checkpoint": variant.signature_scalars_per_checkpoint,
                        "signature_bytes_per_checkpoint_fp32": variant.signature_bytes_per_checkpoint_fp32,
                        "detection_rate": round(detect_rate, 6),
                        "localization_acc": round(loc_acc, 6),
                        "dominant_mismatch_checkpoint": mismatch_counter[attack_name].most_common(1)[0][0] if mismatch_counter[attack_name] else "",
                        "runtime_ms_per_trace": round(runtime_ms_per_trace, 6),
                    }
                )

    selected_csv = TABLE_DIR / f"{RUN_ID}_selected_operating_points.csv"
    detail_csv = TABLE_DIR / f"{RUN_ID}_detail.csv"
    summary_csv = TABLE_DIR / f"{RUN_ID}_attack_summary.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_focus_tpr.png"
    notes_path = NOTE_DIR / f"{RUN_ID}_notes.md"

    _write_csv(
        selected_csv,
        selected_rows_all,
        [
            "pair_id", "pair_label", "variant", "family", "tolerance_mode", "percentile", "tolerance_scale",
            "token_samples", "channel_samples", "projection_dim", "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32", "calib_honest_hetero_fpr", "calib_tamper_tpr",
            "calib_tamper_locacc", "calib_prompt_count", "selection_rule",
        ],
    )
    _write_csv(
        detail_csv,
        detail_rows,
        [
            "pair_id", "pair_label", "variant", "family", "attack_family", "prompt_id", "donor_prompt_id",
            "donor_source", "attack_checkpoint", "detected", "localization_correct", "first_mismatch_checkpoint",
        ],
    )
    _write_csv(
        summary_csv,
        attack_summary_rows,
        [
            "pair_id", "pair_label", "variant", "family", "attack_family", "prompt_count",
            "signature_scalars_per_checkpoint", "signature_bytes_per_checkpoint_fp32", "detection_rate",
            "localization_acc", "dominant_mismatch_checkpoint", "runtime_ms_per_trace",
        ],
    )
    _plot(attack_summary_rows, figure_path)

    lines = [
        f"# {RUN_ID}",
        "",
        "- Full material-tamper matrix over all current strict 40/200 pair manifests.",
        "- Methods: scalar16, scalar64, projcos4, projcos8, projcos16.",
        "- Attacks: gaussian, stale_replay, wrong_prompt.",
        "- Attack target: right-side stack of each pair, matching pair-specific calibration/tamper root.",
        f"- Attack checkpoint: {ATTACK_CHECKPOINT}",
        f"- Gaussian tamper config: checkpoint={tamper_cfg.get('checkpoint')}, strength={tamper_cfg.get('strength')}, "
        f"relative_to_tensor_std={tamper_cfg.get('relative_to_tensor_std')}, min_std={tamper_cfg.get('min_std')}",
        f"- Selected operating points: {selected_csv}",
        f"- Detail CSV: {detail_csv}",
        f"- Attack summary CSV: {summary_csv}",
        f"- Focus figure: {figure_path}",
        "",
        "## Pair count",
        "",
        f"- manifests covered: {len(PAIR_MANIFESTS)}",
        f"- detail rows: {len(detail_rows)}",
        f"- summary rows: {len(attack_summary_rows)}",
    ]
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"selected ops : {selected_csv}")
    print(f"detail table : {detail_csv}")
    print(f"summary table: {summary_csv}")
    print(f"figure       : {figure_path}")
    print(f"notes        : {notes_path}")


if __name__ == "__main__":
    main()
