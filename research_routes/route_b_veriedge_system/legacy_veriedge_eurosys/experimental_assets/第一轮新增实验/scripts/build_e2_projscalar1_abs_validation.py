from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt  # type: ignore

import build_e2_equal_budget_baseline as eq  # type: ignore
import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_material_tamper_full_matrix as mat  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "projscalar1_abs_validation"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
REPORT_DIR = E2_DIR / "reports"
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"

TARGET_STAGE = "prefill"
PAIR_IDS = [
    "t4strict_pair_a_vs_b_40_200",
    "t4strict_pair_b_vs_d_40_200",
]
VARIANTS: Sequence[eq.VariantSpec] = (
    eq.VariantSpec("scalar16", "scalar", 1, 16, 0, 16, 64),
    eq.VariantSpec("projscalar1_abs", "projabs", 16, 0, 1, 16, 64),
    eq.VariantSpec("projcos4", "projcos", 16, 0, 4, 64, 256),
)
FOCUS_ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
    "scale_perturbation",
]
PRIMARY_E5_ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
]
E5_ALPHA = 0.10
E5_BETA = 0.90


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _manifest_path(pair_id: str) -> Path:
    return (
        REPO_ROOT
        / "paper1_veriedge"
        / "E1"
        / "logs"
        / pair_id
        / f"exp_e1_20260504_{pair_id}_manifest.json"
    )


def _context(pair_id: str) -> Dict[str, Any]:
    context = mat._context_from_manifest(_manifest_path(pair_id))
    context["pair_id"] = pair_id
    context["tamper_root"] = context["right_eval"]
    return context


def _calibrate_delta(
    variant: eq.VariantSpec,
    context: Mapping[str, Any],
    checkpoints: Sequence[str],
    percentile: float,
) -> Dict[str, Dict[str, float]]:
    roots = [context["left_calib"], context["right_calib"]]
    if variant.family == "scalar":
        delta_map, _ = scalar._calibrate_percentile(roots, percentile)
    elif variant.family == "projabs":
        delta_map, _ = eq._calibrate_projabs_percentile(
            roots,
            checkpoints,
            percentile,
            projection_dim=variant.projection_dim,
            token_samples=variant.token_samples,
        )
    else:
        delta_map, _ = proj._calibrate_projcos_percentile(
            roots,
            checkpoints,
            percentile,
            projection_dim=variant.projection_dim,
            token_samples=variant.token_samples,
        )
    return delta_map


def _hash_cfg(variant: eq.VariantSpec, delta_map: Dict[str, Dict[str, float]]):
    if variant.family == "scalar":
        return eq._scalar_hash_cfg(delta_map, variant)
    if variant.family == "projabs":
        return eq._projabs_hash_cfg(delta_map, variant)
    return eq._projected_hash_cfg(delta_map, variant)


def _hash_params(variant: eq.VariantSpec, delta_map: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    if variant.family == "scalar":
        return eq._scalar_hash_params(delta_map, variant)
    if variant.family == "projabs":
        return eq._projabs_hash_params(delta_map, variant)
    return eq._projected_hash_params(delta_map, variant)


def _select_operating_points(
    context: Mapping[str, Any],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Dict[str, float]]]]:
    calib_prompt_map = scalar._prompt_map(config, split="calibration")
    select_context = dict(context)
    select_context["tamper_root"] = context["right_calib"]
    selected_rows: List[Dict[str, Any]] = []
    selected_deltas: Dict[str, Dict[str, Dict[str, float]]] = {}

    for variant in VARIANTS:
        candidates: List[Dict[str, Any]] = []
        for percentile in eq.PERCENTILES:
            checkpoint_delta = _calibrate_delta(variant, context, checkpoints, percentile)
            for mode, active_delta in (
                ("checkpoint_specific", checkpoint_delta),
                ("global_shared", scalar._globalize_delta_map(checkpoint_delta)),
            ):
                for scale in eq.TOLERANCE_SCALES:
                    scaled = scalar._scale_delta_map(active_delta, scale)
                    metrics = eq._evaluate_variant(
                        variant=variant,
                        delta_map=scaled,
                        config=config,
                        checkpoints=checkpoints,
                        calib_prompt_map=calib_prompt_map,
                        context=select_context,
                    )
                    candidates.append({**eq._row_common(variant, mode, percentile, scale), **metrics})

        feasible_count = sum(1 for row in candidates if float(row["calib_honest_hetero_fpr"]) <= eq.TARGET_MAX_FPR)
        best = dict(eq._pick_best(candidates))
        base_delta = _calibrate_delta(variant, context, checkpoints, float(best["percentile"]))
        if str(best["tolerance_mode"]) == "global_shared":
            base_delta = scalar._globalize_delta_map(base_delta)
        selected_delta = scalar._scale_delta_map(base_delta, float(best["tolerance_scale"]))
        selected_deltas[variant.name] = selected_delta
        best.update(
            {
                "pair_id": context["pair_id"],
                "pair_label": context["pair_label"],
                "calib_feasible_count": feasible_count,
                "selected_from_feasible": int(feasible_count > 0),
                "selection_fallback_reason": "" if feasible_count > 0 else f"no calibration candidate with FPR <= {eq.TARGET_MAX_FPR:.2f}",
                "selection_rule": f"prefer calib FPR<={eq.TARGET_MAX_FPR:.2f}, then maximize (TPR-FPR)",
            }
        )
        selected_rows.append(best)

    return selected_rows, selected_deltas


def _eval_hard_pair(
    context: Mapping[str, Any],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    selected_deltas: Mapping[str, Dict[str, Dict[str, float]]],
) -> List[Dict[str, Any]]:
    prompt_map = scalar._prompt_map(config, split="evaluation")
    rows: List[Dict[str, Any]] = []
    for variant in VARIANTS:
        delta_map = selected_deltas[variant.name]
        hash_cfg = _hash_cfg(variant, delta_map)
        hash_params = _hash_params(variant, delta_map)
        started = time.perf_counter()
        hetero = scalar._pair_fpr(
            context["left_eval"],
            context["right_eval"],
            checkpoints,
            TARGET_STAGE,
            scalar._thc_cfg(),
            hash_cfg,
        )
        if variant.family == "scalar":
            tamper = scalar._tamper_metrics(config, context["tamper_root"], prompt_map, hash_params)
            tpr = tamper["tstc_tpr"]
            loc = tamper["tstc_localization_acc"]
            tamper_runtime = tamper["tstc_runtime_sec_tamper"]
        else:
            tamper = proj._tamper_metrics_projcos(config, context["tamper_root"], prompt_map, hash_params)
            tpr = tamper["projcos_tpr"]
            loc = tamper["projcos_localization_acc"]
            tamper_runtime = tamper["projcos_runtime_sec_tamper"]
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "pair_id": context["pair_id"],
                "pair_label": context["pair_label"],
                "variant": variant.name,
                "family": variant.family,
                "signature_scalars_per_checkpoint": variant.signature_scalars_per_checkpoint,
                "signature_bytes_per_checkpoint_fp32": variant.signature_bytes_per_checkpoint_fp32,
                "eval_honest_hetero_fpr": hetero["tstc_fpr"],
                "eval_tamper_tpr": tpr,
                "eval_tamper_locacc": loc,
                "eval_prompt_count": hetero["prompt_count"],
                "eval_runtime_ms_per_trace_hetero": round((float(hetero["tstc_runtime_sec"]) * 1000.0) / hetero["prompt_count"], 6),
                "eval_runtime_ms_per_trace_tamper": round((float(tamper_runtime) * 1000.0) / tamper["prompt_count_tamper"], 6),
                "wall_runtime_sec": round(elapsed, 6),
            }
        )
    return rows


def _load_bundle(root: Path, prompt_id: str) -> Dict[str, Dict[str, Any]]:
    bundle, _metadata, _runtime = load_capture_bundle_for_prompt(root, prompt_id)
    return bundle


def _eval_material_focus(
    context: Mapping[str, Any],
    checkpoints: Sequence[str],
    selected_deltas: Mapping[str, Dict[str, Dict[str, float]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    prompt_ids = scalar._shared_prompt_ids(context["right_eval"], context["right_eval"])
    stale_root, stale_source_kind = mat._rerun_root_for(context["right_eval"])
    tamper_cfg = mat._tamper_cfg()
    summary_rows: List[Dict[str, Any]] = []
    detail_rows: List[Dict[str, Any]] = []

    for variant in VARIANTS:
        hash_cfg = _hash_cfg(variant, selected_deltas[variant.name])
        attack_records: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
        mismatch_counter: Dict[str, Counter[str]] = defaultdict(Counter)
        started = time.perf_counter()
        for idx, prompt_id in enumerate(prompt_ids):
            validator_bundle = _load_bundle(context["right_eval"], prompt_id)
            base_bundle = _load_bundle(context["right_eval"], prompt_id)
            stale_prompt_id = prompt_ids[(idx - 1) % len(prompt_ids)]
            wrong_prompt_id = prompt_ids[(idx + 1) % len(prompt_ids)]
            stale_donor_bundle = _load_bundle(stale_root, stale_prompt_id)
            wrong_donor_bundle = _load_bundle(context["right_eval"], wrong_prompt_id)
            for attack_name in FOCUS_ATTACKS:
                candidate_bundle = mat._attack_bundle(
                    attack_name=attack_name,
                    base_bundle=base_bundle,
                    stale_donor_bundle=stale_donor_bundle,
                    wrong_donor_bundle=wrong_donor_bundle,
                    tamper_cfg=tamper_cfg,
                    prompt_id=prompt_id,
                    strength=float(tamper_cfg.get("strength", 0.15)),
                )
                detected, first_checkpoint = mat._compute_detect(validator_bundle, candidate_bundle, checkpoints, hash_cfg)
                loc_ok = detected and first_checkpoint == mat.ATTACK_CHECKPOINT
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
                        "attack_strength": float(tamper_cfg.get("strength", 0.15)) if attack_name in {"gaussian", "scale_perturbation"} else "",
                        "prompt_id": prompt_id,
                        "detected": int(detected),
                        "localization_correct": int(loc_ok),
                        "first_mismatch_checkpoint": first_checkpoint,
                    }
                )
        runtime_ms = ((time.perf_counter() - started) * 1000.0) / (len(prompt_ids) * len(FOCUS_ATTACKS))
        for attack_name in FOCUS_ATTACKS:
            records = attack_records[attack_name]
            n = len(records)
            summary_rows.append(
                {
                    "pair_id": context["pair_id"],
                    "pair_label": context["pair_label"],
                    "variant": variant.name,
                    "family": variant.family,
                    "attack_family": attack_name,
                    "attack_strength": float(tamper_cfg.get("strength", 0.15)) if attack_name in {"gaussian", "scale_perturbation"} else "",
                    "prompt_count": n,
                    "signature_scalars_per_checkpoint": variant.signature_scalars_per_checkpoint,
                    "signature_bytes_per_checkpoint_fp32": variant.signature_bytes_per_checkpoint_fp32,
                    "detection_rate": round(sum(1 for detected, _ in records if detected) / n, 6) if n else 0.0,
                    "localization_acc": round(sum(1 for _, loc_ok in records if loc_ok) / n, 6) if n else 0.0,
                    "dominant_mismatch_checkpoint": mismatch_counter[attack_name].most_common(1)[0][0] if mismatch_counter[attack_name] else "",
                    "runtime_ms_per_trace": round(runtime_ms, 6),
                }
            )
    return summary_rows, detail_rows


def _plot(hard_rows: Sequence[Mapping[str, Any]], material_rows: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    colors = {"scalar16": "#0f766e", "projscalar1_abs": "#2563eb", "projcos4": "#c2410c"}
    variants = [variant.name for variant in VARIANTS]
    pairs = PAIR_IDS
    attacks = FOCUS_ATTACKS

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
    width = 0.24
    x = list(range(len(pairs)))
    for idx, variant in enumerate(variants):
        shift = (idx - 1) * width
        lookup = {(str(row["pair_id"]), str(row["variant"])): row for row in hard_rows}
        fprs = [float(lookup[(pair, variant)]["eval_honest_hetero_fpr"]) for pair in pairs]
        tprs = [float(lookup[(pair, variant)]["eval_tamper_tpr"]) for pair in pairs]
        axes[0].bar([i + shift for i in x], fprs, width=width, label=variant, color=colors[variant])
        axes[1].bar([i + shift for i in x], tprs, width=width, label=variant, color=colors[variant])

    for ax, title, ylabel in (
        (axes[0], "Hard-pair honest-hetero FPR", "FPR"),
        (axes[1], "Hard-pair Gaussian tamper TPR", "TPR"),
    ):
        ax.set_xticks(x)
        ax.set_xticklabels(["A/B", "B/D"])
        ax.set_ylim(0, 1.05)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
        ax.legend(frameon=False)

    avg_lookup: Dict[Tuple[str, str], float] = {}
    for variant in variants:
        for attack in attacks:
            vals = [
                float(row["detection_rate"])
                for row in material_rows
                if str(row["variant"]) == variant and str(row["attack_family"]) == attack
            ]
            avg_lookup[(variant, attack)] = sum(vals) / len(vals) if vals else 0.0
    x2 = list(range(len(attacks)))
    for idx, variant in enumerate(variants):
        shift = (idx - 1) * width
        axes[2].bar([i + shift for i in x2], [avg_lookup[(variant, attack)] for attack in attacks], width=width, label=variant, color=colors[variant])
    axes[2].set_xticks(x2)
    axes[2].set_xticklabels(["Gaussian", "Cross-stale", "Wrong-shard", "Layer skip", "Scale"], rotation=20, ha="right")
    axes[2].set_ylim(0, 1.05)
    axes[2].set_title("Material tamper TPR averaged over A/B and B/D")
    axes[2].set_ylabel("TPR")
    axes[2].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
    axes[2].legend(frameon=False)
    fig.suptitle("ProjScalar1_abs Validation: hard pairs and material-tamper focus", fontsize=14)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def _latest_table(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern), key=lambda p: (p.stat().st_mtime, p.name))
    if not matches:
        raise FileNotFoundError(f"no files match {pattern} under {root}")
    return matches[-1]


def _risk_class(eval_fpr: float, material_tpr_min: float) -> str:
    if eval_fpr <= E5_ALPHA and material_tpr_min >= E5_BETA:
        return "low-risk"
    if eval_fpr <= 0.20 and material_tpr_min >= 0.80:
        return "medium-risk"
    if eval_fpr <= 0.30 and material_tpr_min >= 0.50:
        return "high-risk"
    return "unverifiable"


def _e5_profile_addendum(
    hard_rows: Sequence[Mapping[str, Any]],
    material_rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    e4_path = _latest_table(E4_DIR / "tables", "exp_e4_*_equal_budget_live_ab_main_table.csv")
    with e4_path.open("r", encoding="utf-8", newline="") as f:
        e4_rows = {str(row["variant"]): row for row in csv.DictReader(f)}

    material_lookup: Dict[Tuple[str, str], Dict[str, float]] = {}
    for pair_id in PAIR_IDS:
        for variant in [spec.name for spec in VARIANTS]:
            scoped = [
                row
                for row in material_rows
                if str(row["pair_id"]) == pair_id
                and str(row["variant"]) == variant
                and str(row["attack_family"]) in PRIMARY_E5_ATTACKS
            ]
            material_lookup[(pair_id, variant)] = {
                "material_tpr_min": min(float(row["detection_rate"]) for row in scoped),
                "material_tpr_mean": sum(float(row["detection_rate"]) for row in scoped) / len(scoped),
                "material_locacc_min": min(float(row["localization_acc"]) for row in scoped),
                "material_locacc_mean": sum(float(row["localization_acc"]) for row in scoped) / len(scoped),
                "reference_replay_runtime_ms": sum(float(row["runtime_ms_per_trace"]) for row in scoped) / len(scoped),
            }

    rows: List[Dict[str, Any]] = []
    for row in hard_rows:
        pair_id = str(row["pair_id"])
        variant = str(row["variant"])
        overhead = e4_rows.get(variant, {})
        material = material_lookup[(pair_id, variant)]
        eval_fpr = float(row["eval_honest_hetero_fpr"])
        material_min = material["material_tpr_min"]
        rows.append(
            {
                "pair_id": pair_id,
                "pair_label": row["pair_label"],
                "variant": variant,
                "family": row["family"],
                "signature_bytes_per_checkpoint_fp32": row["signature_bytes_per_checkpoint_fp32"],
                "reveal_payload_bytes_per_trace": overhead.get("reveal_payload_bytes_per_trace", int(float(row["signature_bytes_per_checkpoint_fp32"])) * 3),
                "challenge_latency_ms": overhead.get("honest_hetero_challenge_latency_ms", row["eval_runtime_ms_per_trace_hetero"]),
                "eval_honest_hetero_fpr": row["eval_honest_hetero_fpr"],
                "material_tpr_min": round(material_min, 6),
                "material_tpr_mean": round(material["material_tpr_mean"], 6),
                "material_locacc_min": round(material["material_locacc_min"], 6),
                "material_locacc_mean": round(material["material_locacc_mean"], 6),
                "risk_class": _risk_class(eval_fpr, material_min),
                "feasible_under_alpha_beta": int(eval_fpr <= E5_ALPHA and material_min >= E5_BETA),
                "alpha_threshold": E5_ALPHA,
                "beta_threshold": E5_BETA,
                "profile_scope": "projscalar1_abs_validation_addendum_not_full_e5_policy_replay",
                "overhead_source": "measured_e4_equal_budget_ab" if variant in e4_rows else "fallback_from_signature_bytes",
            }
        )
    return rows


def _write_report(
    selected_rows: Sequence[Mapping[str, Any]],
    hard_rows: Sequence[Mapping[str, Any]],
    material_rows: Sequence[Mapping[str, Any]],
    paths: Mapping[str, Path],
) -> None:
    def table(rows: Sequence[Mapping[str, Any]], cols: Sequence[str]) -> str:
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["-"] * len(cols)) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
        return "\n".join(lines)

    material_avg_rows: List[Dict[str, Any]] = []
    for variant in [variant.name for variant in VARIANTS]:
        for attack in FOCUS_ATTACKS:
            vals = [float(row["detection_rate"]) for row in material_rows if row["variant"] == variant and row["attack_family"] == attack]
            locs = [float(row["localization_acc"]) for row in material_rows if row["variant"] == variant and row["attack_family"] == attack]
            material_avg_rows.append(
                {
                    "variant": variant,
                    "attack_family": attack,
                    "mean_detection_rate": round(sum(vals) / len(vals), 6) if vals else "",
                    "mean_localization_acc": round(sum(locs) / len(locs), 6) if locs else "",
                }
            )

    lines = [
        f"# {RUN_ID}",
        "",
        "## 目的",
        "",
        "`projscalar1_abs` 在 A/B equal-budget 单点上表现很好，但这不足以证明它稳定优于 `projcos4`。本验证包把它作为低预算 bridge / hybrid 候选，补做 A/B 与 B/D hard pair，以及实验 C material-tamper focus 攻击。",
        "",
        "## 协议",
        "",
        f"- Pair: {', '.join(PAIR_IDS)}。",
        "- 方法: `scalar16`、`projscalar1_abs`、`projcos4`。",
        "- 选点: 只用 calibration split；优先满足 calib FPR <= 0.10，再最大化 TPR-FPR。",
        "- `projscalar1_abs`: 16 tokens x d=1 random projection，比较 mean absolute projected gap，payload 为 16 fp32 scalars = 64B/checkpoint。",
        "- Material focus attacks: gaussian, cross_prompt_stale_substitution, wrong_shard_output, layer_skip, scale_perturbation。",
        "",
        "## Hard Pair Held-out Summary",
        "",
        table(
            hard_rows,
            [
                "pair_id",
                "variant",
                "signature_bytes_per_checkpoint_fp32",
                "eval_honest_hetero_fpr",
                "eval_tamper_tpr",
                "eval_tamper_locacc",
            ],
        ),
        "",
        "## Material Tamper Focus Mean over A/B and B/D",
        "",
        table(material_avg_rows, ["variant", "attack_family", "mean_detection_rate", "mean_localization_acc"]),
        "",
        "## 解读",
        "",
        "- 如果 `projscalar1_abs` 在 A/B 和 B/D 上都保持低 FPR、高 TPR，说明它不是纯 A/B seed-specific 偶然点。",
        "- 如果它在 material attacks 上接近 `projcos4`，它可以作为低预算候选或 hybrid 组件进入论文补充实验。",
        "- 如果它只对 gaussian 或 scale 类攻击强、对 semantic substitution/layer skip 弱，则它更像 norm/projection-gap detector，不应替代 `projcos4` 主线。",
        "",
        "## E5-style Profile Addendum",
        "",
        "- 已补一个轻量 profile addendum，复用 E4 measured overhead 与本验证包的 A/B、B/D held-out FPR/material TPR。",
        "- 这不是完整 E5 policy replay，不覆盖所有 6 个 pair，也不应替代正式 E5 主表。",
        "- 它的作用是判断 `projscalar1_abs` 是否值得进入完整 placement profile：如果 `feasible_under_alpha_beta=1` 且 payload/latency 低，就值得补完整 E5。",
        "",
        "## 产物",
        "",
        f"- Selected operating points: {paths['selected']}",
        f"- Hard-pair summary: {paths['hard']}",
        f"- Material focus summary: {paths['material']}",
        f"- Material focus detail: {paths['detail']}",
        f"- E5-style profile addendum: {paths['e5_profile']}",
        f"- Figure: {paths['figure']}",
    ]
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    selected_rows: List[Dict[str, Any]] = []
    hard_rows: List[Dict[str, Any]] = []
    material_summary_rows: List[Dict[str, Any]] = []
    material_detail_rows: List[Dict[str, Any]] = []

    for pair_id in PAIR_IDS:
        context = _context(pair_id)
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        pair_selected, selected_deltas = _select_operating_points(context, config, checkpoints)
        selected_rows.extend(pair_selected)
        hard_rows.extend(_eval_hard_pair(context, config, checkpoints, selected_deltas))
        material_summary, material_detail = _eval_material_focus(context, checkpoints, selected_deltas)
        material_summary_rows.extend(material_summary)
        material_detail_rows.extend(material_detail)

    selected_path = TABLE_DIR / f"{RUN_ID}_selected_operating_points.csv"
    hard_path = TABLE_DIR / f"{RUN_ID}_hard_pair_summary.csv"
    material_path = TABLE_DIR / f"{RUN_ID}_material_focus_summary.csv"
    detail_path = TABLE_DIR / f"{RUN_ID}_material_focus_detail.csv"
    e5_profile_path = TABLE_DIR / f"{RUN_ID}_e5_profile_addendum.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_hard_and_material_focus.png"
    report_path = REPORT_DIR / f"{RUN_ID}_report.md"

    _write_csv(
        selected_path,
        selected_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "tolerance_mode",
            "percentile",
            "tolerance_scale",
            "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32",
            "token_samples",
            "channel_samples",
            "projection_dim",
            "calib_honest_hetero_fpr",
            "calib_tamper_tpr",
            "calib_tamper_locacc",
            "calib_prompt_count",
            "calib_feasible_count",
            "selected_from_feasible",
            "selection_fallback_reason",
            "selection_rule",
        ],
    )
    _write_csv(
        hard_path,
        hard_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32",
            "eval_honest_hetero_fpr",
            "eval_tamper_tpr",
            "eval_tamper_locacc",
            "eval_prompt_count",
            "eval_runtime_ms_per_trace_hetero",
            "eval_runtime_ms_per_trace_tamper",
            "wall_runtime_sec",
        ],
    )
    _write_csv(
        material_path,
        material_summary_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "attack_family",
            "attack_strength",
            "prompt_count",
            "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32",
            "detection_rate",
            "localization_acc",
            "dominant_mismatch_checkpoint",
            "runtime_ms_per_trace",
        ],
    )
    _write_csv(
        detail_path,
        material_detail_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "attack_family",
            "attack_strength",
            "prompt_id",
            "detected",
            "localization_correct",
            "first_mismatch_checkpoint",
        ],
    )
    e5_profile_rows = _e5_profile_addendum(hard_rows, material_summary_rows)
    _write_csv(
        e5_profile_path,
        e5_profile_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "signature_bytes_per_checkpoint_fp32",
            "reveal_payload_bytes_per_trace",
            "challenge_latency_ms",
            "eval_honest_hetero_fpr",
            "material_tpr_min",
            "material_tpr_mean",
            "material_locacc_min",
            "material_locacc_mean",
            "risk_class",
            "feasible_under_alpha_beta",
            "alpha_threshold",
            "beta_threshold",
            "profile_scope",
            "overhead_source",
        ],
    )
    _plot(hard_rows, material_summary_rows, figure_path)
    _write_report(
        selected_rows,
        hard_rows,
        material_summary_rows,
        {
            "selected": selected_path,
            "hard": hard_path,
            "material": material_path,
            "detail": detail_path,
            "e5_profile": e5_profile_path,
            "figure": figure_path,
            "report": report_path,
        },
    )

    print(f"selected : {selected_path}")
    print(f"hard     : {hard_path}")
    print(f"material : {material_path}")
    print(f"detail   : {detail_path}")
    print(f"e5 add   : {e5_profile_path}")
    print(f"figure   : {figure_path}")
    print(f"report   : {report_path}")


if __name__ == "__main__":
    main()
