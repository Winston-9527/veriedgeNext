from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
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

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt  # type: ignore
from hash_chain import HashConfig, project_prefill_linear_signature  # type: ignore

import build_e2_equal_budget_baseline as eq  # type: ignore
import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_material_tamper_full_matrix as mat  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "projscalar1_abs_multiseed_stability"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
REPORT_DIR = E2_DIR / "reports"

TARGET_STAGE = "prefill"
PAIR_IDS = [
    "t4strict_pair_a_vs_b_40_200",
    "t4strict_pair_a_vs_b_rtxint8_40_200",
    "t4strict_pair_a_vs_c_40_200",
    "t4strict_pair_a_vs_d_40_200",
    "t4strict_pair_b_vs_d_40_200",
    "t4strict_pair_e_vs_f_40_200",
]
PROJECTION_SEEDS = [777, 1001, 2027, 3407, 9001]
VARIANT = eq.VariantSpec("projscalar1_abs", "projabs", 16, 0, 1, 16, 64)
FOCUS_ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
    "scale_perturbation",
]
PRIMARY_ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
]


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


def _projabs_cfg(delta_map: Dict[str, Dict[str, float]], projection_seed: int) -> HashConfig:
    cfg = eq._projabs_hash_cfg(delta_map, VARIANT)
    cfg.projection_seed = int(projection_seed)
    return cfg


def _projabs_params(delta_map: Dict[str, Dict[str, float]], projection_seed: int) -> Dict[str, Any]:
    params = eq._projabs_hash_params(delta_map, VARIANT)
    params["projection_seed"] = int(projection_seed)
    return params


def _calibrate_projabs_percentile_seeded(
    capture_roots: Sequence[Path],
    checkpoints: Sequence[str],
    percentile: float,
    projection_seed: int,
) -> Dict[str, Dict[str, float]]:
    machine_maps = {root.name: scalar._load_npz_map(root) for root in capture_roots}
    common_prompts = set.intersection(*(set(prompt_map.keys()) for prompt_map in machine_maps.values()))
    grouped: Dict[Tuple[str, str], List[float]] = {}
    proto_cfg = _projabs_cfg({"prefill": {}, "decode": {}}, projection_seed)
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
    for (_, checkpoint), gap_values in sorted(grouped.items()):
        values = np.asarray(gap_values, dtype=np.float32)
        delta_map["prefill"][checkpoint] = float(np.percentile(values, percentile)) if values.size else 0.0
    return delta_map


def _evaluate_calib(
    *,
    delta_map: Dict[str, Dict[str, float]],
    projection_seed: int,
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    calib_prompt_map: Mapping[str, Dict[str, str]],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    hash_cfg = _projabs_cfg(delta_map, projection_seed)
    hash_params = _projabs_params(delta_map, projection_seed)
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


def _select_operating_point(
    context: Mapping[str, Any],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    projection_seed: int,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, float]]]:
    calib_prompt_map = scalar._prompt_map(config, split="calibration")
    select_context = dict(context)
    select_context["tamper_root"] = context["right_calib"]
    candidates: List[Dict[str, Any]] = []
    for percentile in eq.PERCENTILES:
        checkpoint_delta = _calibrate_projabs_percentile_seeded(
            [context["left_calib"], context["right_calib"]],
            checkpoints,
            percentile,
            projection_seed,
        )
        for mode, active_delta in (
            ("checkpoint_specific", checkpoint_delta),
            ("global_shared", scalar._globalize_delta_map(checkpoint_delta)),
        ):
            for scale in eq.TOLERANCE_SCALES:
                scaled = scalar._scale_delta_map(active_delta, scale)
                metrics = _evaluate_calib(
                    delta_map=scaled,
                    projection_seed=projection_seed,
                    config=config,
                    checkpoints=checkpoints,
                    calib_prompt_map=calib_prompt_map,
                    context=select_context,
                )
                candidates.append({**eq._row_common(VARIANT, mode, percentile, scale), **metrics})

    feasible_count = sum(1 for row in candidates if float(row["calib_honest_hetero_fpr"]) <= eq.TARGET_MAX_FPR)
    best = dict(eq._pick_best(candidates))
    base_delta = _calibrate_projabs_percentile_seeded(
        [context["left_calib"], context["right_calib"]],
        checkpoints,
        float(best["percentile"]),
        projection_seed,
    )
    if str(best["tolerance_mode"]) == "global_shared":
        base_delta = scalar._globalize_delta_map(base_delta)
    selected_delta = scalar._scale_delta_map(base_delta, float(best["tolerance_scale"]))
    best.update(
        {
            "pair_id": context["pair_id"],
            "pair_label": context["pair_label"],
            "projection_seed": projection_seed,
            "calib_feasible_count": feasible_count,
            "selected_from_feasible": int(feasible_count > 0),
            "selection_fallback_reason": "" if feasible_count > 0 else f"no calibration candidate with FPR <= {eq.TARGET_MAX_FPR:.2f}",
            "selection_rule": f"prefer calib FPR<={eq.TARGET_MAX_FPR:.2f}, then maximize (TPR-FPR)",
        }
    )
    return best, selected_delta


def _eval_hard_pair(
    context: Mapping[str, Any],
    config: Dict[str, Any],
    checkpoints: Sequence[str],
    delta_map: Dict[str, Dict[str, float]],
    projection_seed: int,
) -> Dict[str, Any]:
    prompt_map = scalar._prompt_map(config, split="evaluation")
    hash_cfg = _projabs_cfg(delta_map, projection_seed)
    hash_params = _projabs_params(delta_map, projection_seed)
    hetero = scalar._pair_fpr(
        context["left_eval"],
        context["right_eval"],
        checkpoints,
        TARGET_STAGE,
        scalar._thc_cfg(),
        hash_cfg,
    )
    tamper = proj._tamper_metrics_projcos(config, context["tamper_root"], prompt_map, hash_params)
    return {
        "pair_id": context["pair_id"],
        "pair_label": context["pair_label"],
        "variant": VARIANT.name,
        "family": VARIANT.family,
        "projection_seed": projection_seed,
        "signature_scalars_per_checkpoint": VARIANT.signature_scalars_per_checkpoint,
        "signature_bytes_per_checkpoint_fp32": VARIANT.signature_bytes_per_checkpoint_fp32,
        "eval_honest_hetero_fpr": hetero["tstc_fpr"],
        "eval_tamper_tpr": tamper["projcos_tpr"],
        "eval_tamper_locacc": tamper["projcos_localization_acc"],
        "eval_prompt_count": hetero["prompt_count"],
        "eval_runtime_ms_per_trace_hetero": round((float(hetero["tstc_runtime_sec"]) * 1000.0) / hetero["prompt_count"], 6),
        "eval_runtime_ms_per_trace_tamper": round((float(tamper["projcos_runtime_sec_tamper"]) * 1000.0) / tamper["prompt_count_tamper"], 6),
    }


def _load_bundle(root: Path, prompt_id: str) -> Dict[str, Dict[str, Any]]:
    bundle, _metadata, _runtime = load_capture_bundle_for_prompt(root, prompt_id)
    return bundle


def _eval_material_focus(
    context: Mapping[str, Any],
    checkpoints: Sequence[str],
    delta_map: Dict[str, Dict[str, float]],
    projection_seed: int,
) -> List[Dict[str, Any]]:
    prompt_ids = scalar._shared_prompt_ids(context["right_eval"], context["right_eval"])
    stale_root, _stale_source_kind = mat._rerun_root_for(context["right_eval"])
    tamper_cfg = mat._tamper_cfg()
    hash_cfg = _projabs_cfg(delta_map, projection_seed)
    attack_records: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
    mismatch_counter: Dict[str, Counter[str]] = defaultdict(Counter)

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

    rows: List[Dict[str, Any]] = []
    for attack_name in FOCUS_ATTACKS:
        records = attack_records[attack_name]
        n = len(records)
        rows.append(
            {
                "pair_id": context["pair_id"],
                "pair_label": context["pair_label"],
                "variant": VARIANT.name,
                "family": VARIANT.family,
                "projection_seed": projection_seed,
                "attack_family": attack_name,
                "attack_strength": float(tamper_cfg.get("strength", 0.15)) if attack_name in {"gaussian", "scale_perturbation"} else "",
                "prompt_count": n,
                "signature_scalars_per_checkpoint": VARIANT.signature_scalars_per_checkpoint,
                "signature_bytes_per_checkpoint_fp32": VARIANT.signature_bytes_per_checkpoint_fp32,
                "detection_rate": round(sum(1 for detected, _ in records if detected) / n, 6) if n else 0.0,
                "localization_acc": round(sum(1 for _, loc_ok in records if loc_ok) / n, 6) if n else 0.0,
                "dominant_mismatch_checkpoint": mismatch_counter[attack_name].most_common(1)[0][0] if mismatch_counter[attack_name] else "",
            }
        )
    return rows


def _summarize(
    selected_rows: Sequence[Mapping[str, Any]],
    hard_rows: Sequence[Mapping[str, Any]],
    material_rows: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pair_rows: List[Dict[str, Any]] = []
    for pair_id in PAIR_IDS:
        h = [row for row in hard_rows if row["pair_id"] == pair_id]
        m = [row for row in material_rows if row["pair_id"] == pair_id]
        primary = [row for row in m if row["attack_family"] in PRIMARY_ATTACKS]
        scale = [row for row in m if row["attack_family"] == "scale_perturbation"]
        s = [row for row in selected_rows if row["pair_id"] == pair_id]
        pair_rows.append(
            {
                "pair_id": pair_id,
                "seed_count": len(PROJECTION_SEEDS),
                "selected_feasible_rate": round(sum(int(row["selected_from_feasible"]) for row in s) / len(s), 6),
                "mean_eval_fpr": round(float(np.mean([float(row["eval_honest_hetero_fpr"]) for row in h])), 6),
                "max_eval_fpr": round(float(np.max([float(row["eval_honest_hetero_fpr"]) for row in h])), 6),
                "min_eval_tpr": round(float(np.min([float(row["eval_tamper_tpr"]) for row in h])), 6),
                "min_eval_locacc": round(float(np.min([float(row["eval_tamper_locacc"]) for row in h])), 6),
                "min_primary_material_tpr": round(float(np.min([float(row["detection_rate"]) for row in primary])), 6),
                "mean_primary_material_tpr": round(float(np.mean([float(row["detection_rate"]) for row in primary])), 6),
                "min_scale_tpr": round(float(np.min([float(row["detection_rate"]) for row in scale])), 6),
                "mean_scale_tpr": round(float(np.mean([float(row["detection_rate"]) for row in scale])), 6),
            }
        )

    overall = [
        {
            "pair_count": len(PAIR_IDS),
            "seed_count": len(PROJECTION_SEEDS),
            "run_count": len(hard_rows),
            "selected_feasible_rate": round(sum(int(row["selected_from_feasible"]) for row in selected_rows) / len(selected_rows), 6),
            "mean_eval_fpr": round(float(np.mean([float(row["eval_honest_hetero_fpr"]) for row in hard_rows])), 6),
            "max_eval_fpr": round(float(np.max([float(row["eval_honest_hetero_fpr"]) for row in hard_rows])), 6),
            "min_eval_tpr": round(float(np.min([float(row["eval_tamper_tpr"]) for row in hard_rows])), 6),
            "min_eval_locacc": round(float(np.min([float(row["eval_tamper_locacc"]) for row in hard_rows])), 6),
            "min_primary_material_tpr": round(float(np.min([float(row["detection_rate"]) for row in material_rows if row["attack_family"] in PRIMARY_ATTACKS])), 6),
            "mean_primary_material_tpr": round(float(np.mean([float(row["detection_rate"]) for row in material_rows if row["attack_family"] in PRIMARY_ATTACKS])), 6),
            "min_scale_tpr": round(float(np.min([float(row["detection_rate"]) for row in material_rows if row["attack_family"] == "scale_perturbation"])), 6),
            "mean_scale_tpr": round(float(np.mean([float(row["detection_rate"]) for row in material_rows if row["attack_family"] == "scale_perturbation"])), 6),
        }
    ]
    return pair_rows, overall


def _plot(pair_summary: Sequence[Mapping[str, Any]], hard_rows: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [row["pair_id"].replace("t4strict_pair_", "").replace("_40_200", "").replace("_", "\n") for row in pair_summary]
    x = np.arange(len(labels))
    mean_fpr = [float(row["mean_eval_fpr"]) for row in pair_summary]
    max_fpr = [float(row["max_eval_fpr"]) for row in pair_summary]
    min_primary = [float(row["min_primary_material_tpr"]) for row in pair_summary]
    mean_scale = [float(row["mean_scale_tpr"]) for row in pair_summary]

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), constrained_layout=True)
    axes[0].bar(x - 0.18, mean_fpr, width=0.36, color="#2563eb", label="mean FPR")
    axes[0].bar(x + 0.18, max_fpr, width=0.36, color="#93c5fd", label="max FPR")
    axes[0].axhline(eq.TARGET_MAX_FPR, color="#7f1d1d", linestyle="--", linewidth=1.1, label="FPR target 0.10")
    axes[0].set_title("ProjScalar1_abs held-out FPR across 5 projection seeds")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].set_ylim(0, max(0.12, max(max_fpr) * 1.25 if max_fpr else 0.12))
    axes[0].set_ylabel("FPR")
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
    axes[0].legend(frameon=False)

    axes[1].bar(x - 0.18, min_primary, width=0.36, color="#16a34a", label="min primary material TPR")
    axes[1].bar(x + 0.18, mean_scale, width=0.36, color="#f97316", label="mean scale TPR")
    axes[1].set_title("Material tamper stability")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=8)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("TPR")
    axes[1].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)
    axes[1].legend(frameon=False)

    fig.suptitle("ProjScalar1_abs multi-seed / all-pair stability", fontsize=14)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def _table(rows: Sequence[Mapping[str, Any]], cols: Sequence[str]) -> str:
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["-"] * len(cols)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
    return "\n".join(lines)


def _write_report(
    pair_summary: Sequence[Mapping[str, Any]],
    overall_summary: Sequence[Mapping[str, Any]],
    paths: Mapping[str, Path],
) -> None:
    lines = [
        f"# {RUN_ID}",
        "",
        "## 目的",
        "",
        "验证 `projscalar1_abs` 是否只是 A/B 或单一 projection seed 的偶然好点。实验覆盖 6 个 strict pair 与 5 个 projection seed，每个 pair/seed 都只用 calibration split 选 operating point，再在 held-out eval 上报告 FPR/TPR/LocAcc，并在 material tamper focus 上报告检测率。",
        "",
        "## 协议",
        "",
        f"- Pair 数：{len(PAIR_IDS)}。",
        f"- Projection seeds：{', '.join(str(x) for x in PROJECTION_SEEDS)}。",
        "- Variant：`projscalar1_abs`，即 16 个 token，每个 token 保留 1 维随机投影值，比较 mean absolute projected gap。",
        "- Payload：16 fp32 scalars = 64B/checkpoint；3 个 checkpoint 的 reveal payload 是 192B/trace。",
        "- 选点规则：calibration-only；优先 `calib FPR <= 0.10`，再最大化 `TPR - FPR`。",
        "- Material attacks：gaussian、cross_prompt_stale_substitution、wrong_shard_output、layer_skip、scale_perturbation。",
        "",
        "## Overall Summary",
        "",
        _table(
            overall_summary,
            [
                "pair_count",
                "seed_count",
                "run_count",
                "selected_feasible_rate",
                "mean_eval_fpr",
                "max_eval_fpr",
                "min_eval_tpr",
                "min_primary_material_tpr",
                "min_scale_tpr",
            ],
        ),
        "",
        "## Pair Summary",
        "",
        _table(
            pair_summary,
            [
                "pair_id",
                "seed_count",
                "selected_feasible_rate",
                "mean_eval_fpr",
                "max_eval_fpr",
                "min_eval_tpr",
                "min_primary_material_tpr",
                "min_scale_tpr",
            ],
        ),
        "",
        "## 为什么 projscalar1_abs 会好",
        "",
        "从数学上看，`projscalar1_abs` 不是旧 TSTC 那种只抽少量坐标的 sparse coordinate check。它先用随机投影把一个 token 的完整 hidden vector 压成 1 个标量，因此每个标量都混合了 1024 维 hidden state 的全局信息。对独立或分散在多维上的漂移，随机投影的期望平方差与原向量 L2 差成比例；也就是说，即使只保留 d=1，它仍然比“只看 16 个原始坐标”更不容易漏掉分布在很多维度上的变化。",
        "",
        "同时它比较的是 absolute projected gap，而不是 cosine。这个选择保留了幅值/norm 信息，所以它能检测 `scale_perturbation`；而 `projcos4` 会归一化方向，对纯 scale-only 攻击天然不敏感。换句话说，`projscalar1_abs` 在这里更像一个低维 Johnson-Lindenstrauss 风格的 norm-sensitive sketch：它牺牲了一部分方向几何解释性，但保留了幅值敏感性，并且比 sparse scalar coordinate 更充分地覆盖 hidden vector。",
        "",
        "不过它还不能直接替代 `projcos4` 主线。原因是 d=1 的随机投影可能存在方向抵消，理论上 adversary 如果知道投影方向，可以构造近似落在投影核空间的扰动。因此更稳妥的论文定位是：`projscalar1_abs` 是一个非常强的低预算 norm-sensitive bridge / hybrid candidate，可与 `projcos4` 组成 cosine + norm/projection-gap 的混合 verifier。",
        "",
        "## 产物",
        "",
        f"- Selected operating points: {paths['selected']}",
        f"- Hard-pair detail: {paths['hard']}",
        f"- Material focus detail: {paths['material']}",
        f"- Pair summary: {paths['pair_summary']}",
        f"- Overall summary: {paths['overall_summary']}",
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
    material_rows: List[Dict[str, Any]] = []

    for pair_id in PAIR_IDS:
        context = _context(pair_id)
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        for projection_seed in PROJECTION_SEEDS:
            selected, selected_delta = _select_operating_point(context, config, checkpoints, projection_seed)
            selected_rows.append(selected)
            hard_rows.append(_eval_hard_pair(context, config, checkpoints, selected_delta, projection_seed))
            material_rows.extend(_eval_material_focus(context, checkpoints, selected_delta, projection_seed))
            print(f"completed {pair_id} seed={projection_seed}", flush=True)

    pair_summary, overall_summary = _summarize(selected_rows, hard_rows, material_rows)

    selected_path = TABLE_DIR / f"{RUN_ID}_selected_operating_points.csv"
    hard_path = TABLE_DIR / f"{RUN_ID}_hard_pair_detail.csv"
    material_path = TABLE_DIR / f"{RUN_ID}_material_focus_detail.csv"
    pair_summary_path = TABLE_DIR / f"{RUN_ID}_pair_summary.csv"
    overall_summary_path = TABLE_DIR / f"{RUN_ID}_overall_summary.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_stability.png"
    report_path = REPORT_DIR / f"{RUN_ID}_report.md"

    _write_csv(
        selected_path,
        selected_rows,
        [
            "pair_id",
            "pair_label",
            "projection_seed",
            "variant",
            "family",
            "tolerance_mode",
            "percentile",
            "tolerance_scale",
            "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32",
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
            "projection_seed",
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
        ],
    )
    _write_csv(
        material_path,
        material_rows,
        [
            "pair_id",
            "pair_label",
            "projection_seed",
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
        ],
    )
    _write_csv(
        pair_summary_path,
        pair_summary,
        [
            "pair_id",
            "seed_count",
            "selected_feasible_rate",
            "mean_eval_fpr",
            "max_eval_fpr",
            "min_eval_tpr",
            "min_eval_locacc",
            "min_primary_material_tpr",
            "mean_primary_material_tpr",
            "min_scale_tpr",
            "mean_scale_tpr",
        ],
    )
    _write_csv(
        overall_summary_path,
        overall_summary,
        [
            "pair_count",
            "seed_count",
            "run_count",
            "selected_feasible_rate",
            "mean_eval_fpr",
            "max_eval_fpr",
            "min_eval_tpr",
            "min_eval_locacc",
            "min_primary_material_tpr",
            "mean_primary_material_tpr",
            "min_scale_tpr",
            "mean_scale_tpr",
        ],
    )
    _plot(pair_summary, hard_rows, figure_path)
    _write_report(
        pair_summary,
        overall_summary,
        {
            "selected": selected_path,
            "hard": hard_path,
            "material": material_path,
            "pair_summary": pair_summary_path,
            "overall_summary": overall_summary_path,
            "figure": figure_path,
            "report": report_path,
        },
    )

    print(f"selected : {selected_path}")
    print(f"hard     : {hard_path}")
    print(f"material : {material_path}")
    print(f"pair sum : {pair_summary_path}")
    print(f"overall  : {overall_summary_path}")
    print(f"figure   : {figure_path}")
    print(f"report   : {report_path}")


if __name__ == "__main__":
    main()
