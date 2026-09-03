from __future__ import annotations

import csv
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

from attack import inject_tamper  # type: ignore
from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt  # type: ignore
from hash_chain import _projection_matrix  # type: ignore

import build_e2_material_tamper_full_matrix as mat  # type: ignore
import build_e2_projscalar1_abs_multiseed_stability as ms  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "projscalar1_abs_experiment_c"
RUN_ID = f"exp_e2_{STAMP}_{OWNER}"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIGURE_DIR = E2_DIR / "figures"
REPORT_DIR = E2_DIR / "reports"

PROJECTION_SEED = 777
STRENGTHS = [0.01, 0.02, 0.05, 0.10, 0.15, 0.20]
ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
    "scale_perturbation",
    "projection_aware_nullspace",
]
SWEEP_ATTACKS = ["gaussian", "scale_perturbation", "projection_aware_nullspace"]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _load_bundle(root: Path, prompt_id: str) -> Dict[str, Dict[str, np.ndarray]]:
    bundle, _metadata, _runtime = load_capture_bundle_for_prompt(root, prompt_id)
    return bundle


def _clone(bundle: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, Dict[str, np.ndarray]]:
    return {stage: {name: np.array(tensor, copy=True) for name, tensor in stage_map.items()} for stage, stage_map in bundle.items()}


def _inject_projection_aware_nullspace(
    bundle: Dict[str, Dict[str, np.ndarray]],
    *,
    checkpoint: str,
    checkpoints: Sequence[str],
    projection_seed: int,
    strength: float,
    prompt_id: str,
) -> Dict[str, Dict[str, np.ndarray]]:
    tampered = _clone(bundle)
    checkpoint_index = {name: idx for idx, name in enumerate(checkpoints)}
    if checkpoint not in checkpoint_index:
        raise KeyError(checkpoint)
    verifier_seed = 2026 + checkpoint_index[checkpoint]
    rng = np.random.default_rng(88000 + scalar._trial_index_for_prompt(prompt_id))

    for stage, stage_map in tampered.items():
        if checkpoint not in stage_map:
            raise KeyError(f"checkpoint {checkpoint} missing from stage {stage}")
        tensor = stage_map[checkpoint].astype(np.float32)
        if tensor.ndim != 3:
            raise ValueError(f"expected rank-3 tensor, got {tensor.shape}")
        hidden = tensor.shape[-1]
        proj = _projection_matrix(hidden, 1, int(projection_seed) + verifier_seed).reshape(-1)
        denom = max(float(np.dot(proj, proj)), 1e-12)
        sigma = float(strength) * max(float(np.std(tensor, dtype=np.float32)), 1e-6)
        noise = rng.normal(0.0, sigma, size=tensor.shape).astype(np.float64)
        flat = noise.reshape(-1, hidden)
        coeff = (flat @ proj) / denom
        flat = flat - coeff[:, None] * proj[None, :]
        stage_map[checkpoint] = tensor + flat.reshape(tensor.shape).astype(np.float32)
    return tampered


def _attack_bundle(
    attack_name: str,
    *,
    base_bundle: Dict[str, Dict[str, np.ndarray]],
    stale_donor_bundle: Dict[str, Dict[str, np.ndarray]],
    wrong_donor_bundle: Dict[str, Dict[str, np.ndarray]],
    checkpoints: Sequence[str],
    prompt_id: str,
    strength: float,
) -> Dict[str, Dict[str, np.ndarray]]:
    if attack_name == "gaussian":
        return inject_tamper(
            base_bundle,
            checkpoint=mat.ATTACK_CHECKPOINT,
            strength=float(strength),
            seed=3000 + scalar._trial_index_for_prompt(prompt_id),
            relative_to_tensor_std=True,
            min_std=1e-6,
        )
    if attack_name in {"cross_prompt_stale_substitution", "wrong_shard_output", "layer_skip", "scale_perturbation"}:
        return mat._attack_bundle(
            attack_name=attack_name,
            base_bundle=base_bundle,
            stale_donor_bundle=stale_donor_bundle,
            wrong_donor_bundle=wrong_donor_bundle,
            tamper_cfg=mat._tamper_cfg(),
            prompt_id=prompt_id,
            strength=float(strength),
        )
    if attack_name == "projection_aware_nullspace":
        return _inject_projection_aware_nullspace(
            base_bundle,
            checkpoint=mat.ATTACK_CHECKPOINT,
            checkpoints=checkpoints,
            projection_seed=PROJECTION_SEED,
            strength=float(strength),
            prompt_id=prompt_id,
        )
    raise ValueError(attack_name)


def _eval_attack_set(
    context: Mapping[str, Any],
    checkpoints: Sequence[str],
    selected_delta: Dict[str, Dict[str, float]],
    attack_strengths: Mapping[str, float],
) -> List[Dict[str, Any]]:
    hash_cfg = ms._projabs_cfg(selected_delta, PROJECTION_SEED)
    prompt_ids = scalar._shared_prompt_ids(context["right_eval"], context["right_eval"])
    stale_root, stale_source = mat._rerun_root_for(context["right_eval"])
    records: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
    mismatch_counter: Dict[str, Counter[str]] = defaultdict(Counter)

    for idx, prompt_id in enumerate(prompt_ids):
        validator_bundle = _load_bundle(context["right_eval"], prompt_id)
        base_bundle = _load_bundle(context["right_eval"], prompt_id)
        stale_prompt_id = prompt_ids[(idx - 1) % len(prompt_ids)]
        wrong_prompt_id = prompt_ids[(idx + 1) % len(prompt_ids)]
        stale_donor_bundle = _load_bundle(stale_root, stale_prompt_id)
        wrong_donor_bundle = _load_bundle(context["right_eval"], wrong_prompt_id)
        for attack_name, strength in attack_strengths.items():
            candidate = _attack_bundle(
                attack_name,
                base_bundle=base_bundle,
                stale_donor_bundle=stale_donor_bundle,
                wrong_donor_bundle=wrong_donor_bundle,
                checkpoints=checkpoints,
                prompt_id=prompt_id,
                strength=float(strength),
            )
            detected, first_checkpoint = mat._compute_detect(validator_bundle, candidate, checkpoints, hash_cfg)
            loc_ok = detected and first_checkpoint == mat.ATTACK_CHECKPOINT
            records[attack_name].append((detected, loc_ok))
            if first_checkpoint:
                mismatch_counter[attack_name][first_checkpoint] += 1

    rows: List[Dict[str, Any]] = []
    for attack_name, attack_records in records.items():
        n = len(attack_records)
        rows.append(
            {
                "pair_id": context["pair_id"],
                "pair_label": context["pair_label"],
                "variant": ms.VARIANT.name,
                "family": ms.VARIANT.family,
                "projection_seed": PROJECTION_SEED,
                "attack_family": attack_name,
                "attack_strength": attack_strengths[attack_name],
                "prompt_count": n,
                "detection_rate": round(sum(1 for detected, _ in attack_records if detected) / n, 6) if n else 0.0,
                "localization_acc": round(sum(1 for _, loc_ok in attack_records if loc_ok) / n, 6) if n else 0.0,
                "dominant_mismatch_checkpoint": mismatch_counter[attack_name].most_common(1)[0][0] if mismatch_counter[attack_name] else "",
            }
        )
    return rows


def _summaries(focus_rows: Sequence[Mapping[str, Any]], sweep_rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    attack_summary: List[Dict[str, Any]] = []
    for attack in ATTACKS:
        vals = [float(row["detection_rate"]) for row in focus_rows if row["attack_family"] == attack]
        locs = [float(row["localization_acc"]) for row in focus_rows if row["attack_family"] == attack]
        attack_summary.append(
            {
                "attack_family": attack,
                "pair_count": len({row["pair_id"] for row in focus_rows if row["attack_family"] == attack}),
                "mean_detection_rate": round(float(np.mean(vals)), 6) if vals else "",
                "min_detection_rate": round(float(np.min(vals)), 6) if vals else "",
                "mean_localization_acc": round(float(np.mean(locs)), 6) if locs else "",
                "min_localization_acc": round(float(np.min(locs)), 6) if locs else "",
            }
        )
    sweep_summary: List[Dict[str, Any]] = []
    for attack in SWEEP_ATTACKS:
        for strength in STRENGTHS:
            vals = [
                float(row["detection_rate"])
                for row in sweep_rows
                if row["attack_family"] == attack and abs(float(row["attack_strength"]) - float(strength)) < 1e-12
            ]
            sweep_summary.append(
                {
                    "attack_family": attack,
                    "attack_strength": strength,
                    "mean_detection_rate": round(float(np.mean(vals)), 6) if vals else "",
                    "min_detection_rate": round(float(np.min(vals)), 6) if vals else "",
                }
            )
    return attack_summary, sweep_summary


def _plot(attack_summary: Sequence[Mapping[str, Any]], sweep_summary: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), constrained_layout=True)

    attacks = [row["attack_family"] for row in attack_summary]
    x = np.arange(len(attacks))
    axes[0].bar(x, [float(row["mean_detection_rate"]) for row in attack_summary], color="#2563eb")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([a.replace("_", "\n") for a in attacks], fontsize=8)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_title("Experiment C attack-family mean TPR")
    axes[0].set_ylabel("Mean TPR over 6 pairs")
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)

    colors = {"gaussian": "#16a34a", "scale_perturbation": "#f97316", "projection_aware_nullspace": "#7c3aed"}
    for attack in SWEEP_ATTACKS:
        rows = [row for row in sweep_summary if row["attack_family"] == attack]
        axes[1].plot(
            [float(row["attack_strength"]) for row in rows],
            [float(row["mean_detection_rate"]) for row in rows],
            marker="o",
            linewidth=1.8,
            color=colors[attack],
            label=attack.replace("_", " "),
        )
    axes[1].set_ylim(-0.02, 1.05)
    axes[1].set_xlabel("Attack strength")
    axes[1].set_ylabel("Mean TPR over 6 pairs")
    axes[1].set_title("Weak-to-strong sweep")
    axes[1].grid(True, linestyle="--", linewidth=0.6, alpha=0.4)
    axes[1].legend(frameon=False)
    fig.suptitle("ProjScalar1_abs Experiment C extension", fontsize=14)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def _table(rows: Sequence[Mapping[str, Any]], cols: Sequence[str]) -> str:
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["-"] * len(cols)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
    return "\n".join(lines)


def _write_report(attack_summary: Sequence[Mapping[str, Any]], sweep_summary: Sequence[Mapping[str, Any]], paths: Mapping[str, Path]) -> None:
    null_rows = [row for row in sweep_summary if row["attack_family"] == "projection_aware_nullspace"]
    lines = [
        f"# {RUN_ID}",
        "",
        "## 目的",
        "",
        "`projscalar1_abs` 已经在多 seed / 全 pair 上表现稳定。本实验补齐它在实验 C 语境下的必要证据：不同攻击家族、弱到强 strength sweep，以及 projection-aware null-space attack 边界。",
        "",
        "## 协议",
        "",
        f"- Pair: 6 strict pairs。",
        f"- Projection seed: {PROJECTION_SEED}。",
        "- Variant: `projscalar1_abs`，64B/checkpoint。",
        "- Focus attacks: gaussian, cross_prompt_stale_substitution, wrong_shard_output, layer_skip, scale_perturbation, projection_aware_nullspace。",
        f"- Sweep attacks: {', '.join(SWEEP_ATTACKS)} over strengths {STRENGTHS}。",
        "",
        "## Attack-family Summary",
        "",
        _table(attack_summary, ["attack_family", "pair_count", "mean_detection_rate", "min_detection_rate", "mean_localization_acc", "min_localization_acc"]),
        "",
        "## Projection-aware Null-space Boundary",
        "",
        _table(null_rows, ["attack_family", "attack_strength", "mean_detection_rate", "min_detection_rate"]),
        "",
        "## Weak-to-strong Sweep",
        "",
        _table(sweep_summary, ["attack_family", "attack_strength", "mean_detection_rate", "min_detection_rate"]),
        "",
        "## 解读",
        "",
        "`projscalar1_abs` 对普通实验 C 攻击家族依然很强，包含语义替换、layer skip、scale perturbation。它能检测 scale 的原因是 absolute projected gap 保留了幅值信息。弱攻击 sweep 显示：Gaussian 在 `0.01` 已经稳定检出；scale 在 `0.01` 时平均 TPR 只有约 `0.239`，到 `0.02` 上升到约 `0.942`，`0.05` 及以上为 `1.0`。因此它不是只在强 scale attack 上有效，但极弱 scale 仍存在灰区。",
        "",
        "但 projection-aware null-space attack 展示了它的理论边界：如果攻击者知道 projection vector，可以构造几乎落在投影核空间的扰动，使被保留的 d=1 投影值变化很小。这个结果不削弱它作为低预算 hybrid candidate 的价值，反而说明论文中不应把它写成单独通用 verifier；更合理的系统设计是 `projcos` 方向统计 + `projscalar/norm` 幅值统计的混合 verifier。",
        "",
        "## 产物",
        "",
        f"- Selected operating points: {paths['selected']}",
        f"- Focus detail: {paths['focus']}",
        f"- Strength sweep detail: {paths['sweep']}",
        f"- Attack summary: {paths['attack_summary']}",
        f"- Sweep summary: {paths['sweep_summary']}",
        f"- Figure: {paths['figure']}",
    ]
    paths["report"].parent.mkdir(parents=True, exist_ok=True)
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    selected_rows: List[Dict[str, Any]] = []
    focus_rows: List[Dict[str, Any]] = []
    sweep_rows: List[Dict[str, Any]] = []

    for pair_id in ms.PAIR_IDS:
        context = ms._context(pair_id)
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        selected, selected_delta = ms._select_operating_point(context, config, checkpoints, PROJECTION_SEED)
        selected_rows.append(selected)
        focus_rows.extend(_eval_attack_set(context, checkpoints, selected_delta, {attack: 0.15 for attack in ATTACKS}))
        for attack in SWEEP_ATTACKS:
            for strength in STRENGTHS:
                sweep_rows.extend(_eval_attack_set(context, checkpoints, selected_delta, {attack: strength}))
        print(f"completed {pair_id}", flush=True)

    attack_summary, sweep_summary = _summaries(focus_rows, sweep_rows)
    selected_path = TABLE_DIR / f"{RUN_ID}_selected_operating_points.csv"
    focus_path = TABLE_DIR / f"{RUN_ID}_focus_detail.csv"
    sweep_path = TABLE_DIR / f"{RUN_ID}_strength_sweep_detail.csv"
    attack_summary_path = TABLE_DIR / f"{RUN_ID}_attack_summary.csv"
    sweep_summary_path = TABLE_DIR / f"{RUN_ID}_strength_sweep_summary.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_attack_and_sweep.png"
    report_path = REPORT_DIR / f"{RUN_ID}_report.md"

    _write_csv(selected_path, selected_rows, [
        "pair_id", "pair_label", "projection_seed", "variant", "family", "tolerance_mode", "percentile",
        "tolerance_scale", "signature_scalars_per_checkpoint", "signature_bytes_per_checkpoint_fp32",
        "calib_honest_hetero_fpr", "calib_tamper_tpr", "calib_tamper_locacc", "calib_prompt_count",
        "calib_feasible_count", "selected_from_feasible", "selection_fallback_reason", "selection_rule",
    ])
    fields = [
        "pair_id", "pair_label", "variant", "family", "projection_seed", "attack_family", "attack_strength",
        "prompt_count", "detection_rate", "localization_acc", "dominant_mismatch_checkpoint",
    ]
    _write_csv(focus_path, focus_rows, fields)
    _write_csv(sweep_path, sweep_rows, fields)
    _write_csv(attack_summary_path, attack_summary, ["attack_family", "pair_count", "mean_detection_rate", "min_detection_rate", "mean_localization_acc", "min_localization_acc"])
    _write_csv(sweep_summary_path, sweep_summary, ["attack_family", "attack_strength", "mean_detection_rate", "min_detection_rate"])
    _plot(attack_summary, sweep_summary, figure_path)
    _write_report(attack_summary, sweep_summary, {
        "selected": selected_path,
        "focus": focus_path,
        "sweep": sweep_path,
        "attack_summary": attack_summary_path,
        "sweep_summary": sweep_summary_path,
        "figure": figure_path,
        "report": report_path,
    })
    print(f"selected: {selected_path}")
    print(f"focus   : {focus_path}")
    print(f"sweep   : {sweep_path}")
    print(f"summary : {attack_summary_path}")
    print(f"figure  : {figure_path}")
    print(f"report  : {report_path}")


if __name__ == "__main__":
    main()
