from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
E2_DIR_PY = REPO_ROOT / "paper1_veriedge" / "E2"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))
if str(E2_DIR_PY) not in sys.path:
    sys.path.insert(0, str(E2_DIR_PY))

from attack import inject_tamper  # type: ignore
from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import HashConfig, compute_hash_chain, first_mismatch_index  # type: ignore

import build_e2_equal_budget_baseline as eq  # type: ignore
import build_e2_live_projcos_sweeps as proj  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "equal_budget_live_ab"
RUN_ID = f"exp_e4_{STAMP}_{OWNER}"
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"
TABLE_DIR = E4_DIR / "tables"
FIGURE_DIR = E4_DIR / "figures"
NOTE_DIR = E4_DIR / "notes"


def _latest_selected_summary() -> Path:
    matches = sorted((REPO_ROOT / "paper1_veriedge" / "E2" / "tables").glob("exp_e2_*_equal_budget_live_ab_selected_summary.csv"), key=lambda p: (p.stat().st_mtime, p.name))
    if not matches:
        raise FileNotFoundError("no equal-budget selected summary found under paper1_veriedge/E2/tables")
    return matches[-1]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _trial_index_for_prompt(prompt_id: str) -> int:
    digest = hashlib.sha256(prompt_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _load_capture_root(prompt_id: str, capture_root: Path) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], float, int]:
    start = time.perf_counter()
    bundle, metadata_rows, _runtime = load_capture_bundle_for_prompt(capture_root, prompt_id)
    load_ms = (time.perf_counter() - start) * 1000.0
    capture_file_bytes = int((capture_root / "captures" / f"{prompt_id}.npz").stat().st_size)
    return bundle, metadata_rows, load_ms, capture_file_bytes


def _metadata_bytes(rows: Sequence[Mapping[str, Any]]) -> int:
    total = 0
    for row in rows:
        total += len((json.dumps(dict(row), ensure_ascii=True) + "\n").encode("utf-8"))
    return total


def _chain_sizes_generic(chains: Mapping[str, Sequence[Any]]) -> Tuple[int, int]:
    total_chain_bytes = 0
    total_head_bytes = 0
    for chain in chains.values():
        if not chain:
            continue
        for item in chain:
            if isinstance(item, dict):
                total_chain_bytes += len(bytes.fromhex(str(item["chain_hash"])))
            else:
                total_chain_bytes += len(bytes.fromhex(str(item)))
        last = chain[-1]
        if isinstance(last, dict):
            total_head_bytes += len(bytes.fromhex(str(last["chain_hash"])))
        else:
            total_head_bytes += len(bytes.fromhex(str(last)))
    return total_chain_bytes, total_head_bytes


def _compute_stage_chains(bundle: Dict[str, Dict[str, Any]], checkpoints: Sequence[str], cfg: HashConfig) -> Dict[str, Sequence[Any]]:
    out: Dict[str, Sequence[Any]] = {}
    for stage_key in ordered_stage_keys(bundle.keys()):
        out[stage_key] = compute_hash_chain(bundle[stage_key], checkpoints, stage_family(stage_key), cfg)
    return out


def _first_mismatch(reference: Mapping[str, Sequence[Any]], candidate: Mapping[str, Sequence[Any]], checkpoints: Sequence[str]) -> Tuple[bool, str, str]:
    for stage_key in ordered_stage_keys(reference.keys()):
        mismatch = first_mismatch_index(reference.get(stage_key, []), candidate.get(stage_key, []))
        if mismatch is None:
            continue
        checkpoint = checkpoints[mismatch] if mismatch < len(checkpoints) else ""
        return True, stage_family(stage_key), checkpoint
    return False, "", ""


def _selected_hash_cfg(row: Mapping[str, str], checkpoints: Sequence[str], context: Mapping[str, Path]) -> Tuple[HashConfig, Dict[str, Dict[str, float]]]:
    percentile = float(row["percentile"])
    tolerance_scale = float(row["tolerance_scale"])
    variant = next(spec for spec in eq.VARIANTS if spec.name == row["variant"])
    if variant.family == "scalar":
        base_delta, _ = scalar._calibrate_percentile([context["left_calib"], context["right_calib"]], percentile)
        active_delta = base_delta if row["tolerance_mode"] == "checkpoint_specific" else scalar._globalize_delta_map(base_delta)
        scaled = scalar._scale_delta_map(active_delta, tolerance_scale)
        return eq._scalar_hash_cfg(scaled, variant), scaled

    base_delta, _ = proj._calibrate_projcos_percentile(
        [context["left_calib"], context["right_calib"]],
        checkpoints,
        percentile,
        projection_dim=variant.projection_dim,
        token_samples=variant.token_samples,
    )
    active_delta = base_delta if row["tolerance_mode"] == "checkpoint_specific" else scalar._globalize_delta_map(base_delta)
    scaled = scalar._scale_delta_map(active_delta, tolerance_scale)
    return eq._projected_hash_cfg(scaled, variant), scaled


def _reveal_payload_bytes_per_trace(row: Mapping[str, str], checkpoint_count: int) -> int:
    return int(row["signature_bytes_per_checkpoint_fp32"]) * int(checkpoint_count)


def _scenario_roots(context: Mapping[str, Path], scenario: str) -> Tuple[Path, Path]:
    if scenario == "honest_homo":
        return context["homo_left_eval"], context["homo_right_eval"]
    if scenario == "honest_hetero":
        return context["left_eval"], context["right_eval"]
    if scenario == "tamper":
        return context["tamper_root"], context["tamper_root"]
    raise ValueError(f"unsupported scenario: {scenario}")


def _verdict_for(scenario: str, detected: bool) -> str:
    if scenario == "tamper":
        return "challenge_upheld" if detected else "challenge_failed"
    return "false_alarm" if detected else "honest_execution"


def _measure_variant_scenario(
    *,
    row: Mapping[str, str],
    hash_cfg: HashConfig,
    checkpoints: Sequence[str],
    context: Mapping[str, Path],
    scenario: str,
    tamper_cfg: Mapping[str, Any],
    base_seed: int,
) -> List[Dict[str, Any]]:
    validator_root, candidate_root = _scenario_roots(context, scenario)
    prompt_ids = scalar._shared_prompt_ids(validator_root, candidate_root)
    reveal_payload_bytes = _reveal_payload_bytes_per_trace(row, len(checkpoints))
    out_rows: List[Dict[str, Any]] = []

    for prompt_id in prompt_ids:
        validator_bundle, validator_meta, validator_load_ms, validator_capture_bytes = _load_capture_root(prompt_id, validator_root)
        candidate_bundle, candidate_meta, candidate_load_ms, candidate_capture_bytes = _load_capture_root(prompt_id, candidate_root)
        if scenario == "tamper":
            candidate_bundle = inject_tamper(
                candidate_bundle,
                checkpoint=str(tamper_cfg.get("checkpoint", "C2")),
                strength=float(tamper_cfg.get("strength", 0.15)),
                seed=int(base_seed) + _trial_index_for_prompt(prompt_id) + 3000,
                relative_to_tensor_std=bool(tamper_cfg.get("relative_to_tensor_std", False)),
                min_std=float(tamper_cfg.get("min_std", 1e-6)),
            )

        commit_start = time.perf_counter()
        candidate_chains = _compute_stage_chains(candidate_bundle, checkpoints, hash_cfg)
        commitment_generation_ms = (time.perf_counter() - commit_start) * 1000.0

        replay_start = time.perf_counter()
        validator_chains = _compute_stage_chains(validator_bundle, checkpoints, hash_cfg)
        replay_ms = (time.perf_counter() - replay_start) * 1000.0

        compare_start = time.perf_counter()
        detected, first_stage, first_checkpoint = _first_mismatch(validator_chains, candidate_chains, checkpoints)
        compare_ms = (time.perf_counter() - compare_start) * 1000.0

        verdict_payload = {
            "prompt_id": prompt_id,
            "scenario": scenario,
            "variant": row["variant"],
            "detected": bool(detected),
            "first_mismatch_stage": first_stage,
            "first_mismatch_checkpoint": first_checkpoint,
            "verdict": _verdict_for(scenario, bool(detected)),
        }
        verdict_bytes = len(json.dumps(verdict_payload, ensure_ascii=True, sort_keys=True).encode("utf-8"))
        commitment_chain_bytes, commitment_head_bytes = _chain_sizes_generic(candidate_chains)
        reference_metadata_bytes = _metadata_bytes(validator_meta)
        candidate_metadata_bytes = _metadata_bytes(candidate_meta)
        metadata_bytes = reference_metadata_bytes + candidate_metadata_bytes
        reference_storage_head_bytes = validator_capture_bytes + reference_metadata_bytes
        candidate_working_set_head_bytes = candidate_capture_bytes + candidate_metadata_bytes
        challenge_working_set_head_bytes = (
            reference_storage_head_bytes
            + candidate_working_set_head_bytes
            + commitment_head_bytes
            + verdict_bytes
        )
        challenge_working_set_full_chain_bytes = (
            reference_storage_head_bytes
            + candidate_working_set_head_bytes
            + commitment_chain_bytes
            + verdict_bytes
        )
        challenge_latency_no_commit_ms = validator_load_ms + candidate_load_ms + replay_ms + compare_ms
        challenge_latency_with_commit_ms = challenge_latency_no_commit_ms + commitment_generation_ms

        out_rows.append(
            {
                "variant": row["variant"],
                "family": row["family"],
                "scenario": scenario,
                "prompt_id": prompt_id,
                "tolerance_mode": row["tolerance_mode"],
                "percentile": row["percentile"],
                "tolerance_scale": row["tolerance_scale"],
                "signature_scalars_per_checkpoint": row["signature_scalars_per_checkpoint"],
                "signature_bytes_per_checkpoint_fp32": row["signature_bytes_per_checkpoint_fp32"],
                "reveal_payload_bytes_per_trace": reveal_payload_bytes,
                "reference_capture_file_bytes": validator_capture_bytes,
                "candidate_capture_file_bytes": candidate_capture_bytes,
                "metadata_bytes": metadata_bytes,
                "commitment_head_bytes": commitment_head_bytes,
                "commitment_chain_bytes": commitment_chain_bytes,
                "reference_storage_head_bytes": reference_storage_head_bytes,
                "candidate_working_set_head_bytes": candidate_working_set_head_bytes,
                "challenge_working_set_head_bytes": challenge_working_set_head_bytes,
                "challenge_working_set_full_chain_bytes": challenge_working_set_full_chain_bytes,
                "reference_capture_load_ms": round(validator_load_ms, 6),
                "candidate_capture_load_ms": round(candidate_load_ms, 6),
                "commitment_generation_ms": round(commitment_generation_ms, 6),
                "replay_ms": round(replay_ms, 6),
                "compare_ms": round(compare_ms, 6),
                "challenge_latency_no_commit_ms": round(challenge_latency_no_commit_ms, 6),
                "challenge_latency_ms": round(challenge_latency_with_commit_ms, 6),
                "detected": int(bool(detected)),
                "first_mismatch_stage": first_stage,
                "first_mismatch_checkpoint": first_checkpoint,
                "verdict_bytes": verdict_bytes,
            }
        )
    return out_rows


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _build_summary(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["variant"]), str(row["scenario"]))].append(row)

    summary: List[Dict[str, Any]] = []
    for (variant, scenario), bucket in sorted(grouped.items()):
        first = bucket[0]
        summary.append(
            {
                "variant": variant,
                "family": first["family"],
                "scenario": scenario,
                "sample_count": len(bucket),
                "tolerance_mode": first["tolerance_mode"],
                "percentile": first["percentile"],
                "tolerance_scale": first["tolerance_scale"],
                "signature_scalars_per_checkpoint": first["signature_scalars_per_checkpoint"],
                "signature_bytes_per_checkpoint_fp32": first["signature_bytes_per_checkpoint_fp32"],
                "reveal_payload_bytes_per_trace": first["reveal_payload_bytes_per_trace"],
                "mean_commitment_head_bytes": round(_mean([float(row["commitment_head_bytes"]) for row in bucket]), 6),
                "mean_commitment_chain_bytes": round(_mean([float(row["commitment_chain_bytes"]) for row in bucket]), 6),
                "mean_reference_storage_head_bytes": round(_mean([float(row["reference_storage_head_bytes"]) for row in bucket]), 6),
                "mean_candidate_working_set_head_bytes": round(_mean([float(row["candidate_working_set_head_bytes"]) for row in bucket]), 6),
                "mean_challenge_working_set_head_bytes": round(_mean([float(row["challenge_working_set_head_bytes"]) for row in bucket]), 6),
                "mean_challenge_working_set_full_chain_bytes": round(_mean([float(row["challenge_working_set_full_chain_bytes"]) for row in bucket]), 6),
                "mean_commitment_generation_ms": round(_mean([float(row["commitment_generation_ms"]) for row in bucket]), 6),
                "mean_replay_ms": round(_mean([float(row["replay_ms"]) for row in bucket]), 6),
                "mean_compare_ms": round(_mean([float(row["compare_ms"]) for row in bucket]), 6),
                "mean_challenge_latency_no_commit_ms": round(_mean([float(row["challenge_latency_no_commit_ms"]) for row in bucket]), 6),
                "mean_challenge_latency_ms": round(_mean([float(row["challenge_latency_ms"]) for row in bucket]), 6),
                "detection_rate": round(_mean([float(row["detected"]) for row in bucket]), 6),
                "dominant_mismatch_checkpoint": max(
                    {str(row["first_mismatch_checkpoint"]) for row in bucket},
                    key=lambda checkpoint: sum(1 for row in bucket if str(row["first_mismatch_checkpoint"]) == checkpoint),
                )
                if any(str(row["first_mismatch_checkpoint"]) for row in bucket)
                else "",
            }
        )
    return summary


def _build_main_table(summary_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in summary_rows:
        grouped[str(row["variant"])][str(row["scenario"])] = row

    main_rows: List[Dict[str, Any]] = []
    for variant, by_scenario in sorted(grouped.items()):
        anchor = by_scenario.get("honest_hetero") or next(iter(by_scenario.values()))
        homo = by_scenario.get("honest_homo", {})
        hetero = by_scenario.get("honest_hetero", {})
        tamper = by_scenario.get("tamper", {})
        main_rows.append(
            {
                "variant": variant,
                "family": anchor.get("family", ""),
                "tolerance_mode": anchor.get("tolerance_mode", ""),
                "percentile": anchor.get("percentile", ""),
                "tolerance_scale": anchor.get("tolerance_scale", ""),
                "signature_scalars_per_checkpoint": anchor.get("signature_scalars_per_checkpoint", ""),
                "signature_bytes_per_checkpoint_fp32": anchor.get("signature_bytes_per_checkpoint_fp32", ""),
                "reveal_payload_bytes_per_trace": anchor.get("reveal_payload_bytes_per_trace", ""),
                "mean_commitment_head_bytes": anchor.get("mean_commitment_head_bytes", ""),
                "mean_commitment_chain_bytes": anchor.get("mean_commitment_chain_bytes", ""),
                "honest_homo_detection_rate": homo.get("detection_rate", ""),
                "honest_homo_challenge_latency_no_commit_ms": homo.get("mean_challenge_latency_no_commit_ms", ""),
                "honest_homo_challenge_latency_ms": homo.get("mean_challenge_latency_ms", ""),
                "honest_hetero_detection_rate": hetero.get("detection_rate", ""),
                "honest_hetero_challenge_latency_no_commit_ms": hetero.get("mean_challenge_latency_no_commit_ms", ""),
                "honest_hetero_challenge_latency_ms": hetero.get("mean_challenge_latency_ms", ""),
                "tamper_detection_rate": tamper.get("detection_rate", ""),
                "tamper_challenge_latency_no_commit_ms": tamper.get("mean_challenge_latency_no_commit_ms", ""),
                "tamper_challenge_latency_ms": tamper.get("mean_challenge_latency_ms", ""),
            }
        )
    return main_rows


def _plot(main_rows: Sequence[Mapping[str, Any]], figure_path: Path) -> None:
    if plt is None:
        return

    ordered = sorted(main_rows, key=lambda row: int(row["signature_bytes_per_checkpoint_fp32"]))
    methods = [str(row["variant"]) for row in ordered]
    bytes_per_trace = [int(row["reveal_payload_bytes_per_trace"]) for row in ordered]
    hetero_latency = [float(row["honest_hetero_challenge_latency_ms"]) for row in ordered]
    tamper_latency = [float(row["tamper_challenge_latency_ms"]) for row in ordered]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    axes[0].bar(methods, bytes_per_trace, color=["#0f766e", "#115e59", "#c2410c", "#9a3412"])
    axes[0].set_title("Reveal Payload per Trace")
    axes[0].set_ylabel("Bytes")
    axes[0].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)

    x = range(len(methods))
    width = 0.36
    axes[1].bar([i - width / 2 for i in x], hetero_latency, width=width, label="honest-hetero", color="#2563eb")
    axes[1].bar([i + width / 2 for i in x], tamper_latency, width=width, label="tamper", color="#dc2626")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(methods)
    axes[1].set_title("Challenge Latency")
    axes[1].set_ylabel("ms / trace")
    axes[1].legend(frameon=False)
    axes[1].grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.4)

    fig.suptitle("E4 Equal-Budget Overhead: Scalar vs Projected-Token TSTC", fontsize=14)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, dpi=220)
    fig.savefig(figure_path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    selected_summary = _latest_selected_summary()
    selected_rows = _read_csv(selected_summary)
    context = proj._live_context()
    config = scalar._load_json(context["config_path"])
    checkpoints = checkpoint_order(config)
    tamper_cfg = config.get("tamper", {})
    base_seed = int(config.get("experiment", {}).get("seed", 7))

    detail_rows: List[Dict[str, Any]] = []
    for row in selected_rows:
        hash_cfg, _delta_map = _selected_hash_cfg(row, checkpoints, context)
        for scenario in ("honest_homo", "honest_hetero", "tamper"):
            detail_rows.extend(
                _measure_variant_scenario(
                    row=row,
                    hash_cfg=hash_cfg,
                    checkpoints=checkpoints,
                    context=context,
                    scenario=scenario,
                    tamper_cfg=tamper_cfg,
                    base_seed=base_seed,
                )
            )

    summary_rows = _build_summary(detail_rows)
    main_rows = _build_main_table(summary_rows)

    detail_csv = TABLE_DIR / f"{RUN_ID}_detail.csv"
    summary_csv = TABLE_DIR / f"{RUN_ID}_summary.csv"
    main_csv = TABLE_DIR / f"{RUN_ID}_main_table.csv"
    figure_path = FIGURE_DIR / f"{RUN_ID}_payload_latency.png"
    notes_path = NOTE_DIR / f"{RUN_ID}_notes.md"

    detail_fields = [
        "variant",
        "family",
        "scenario",
        "prompt_id",
        "tolerance_mode",
        "percentile",
        "tolerance_scale",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "reveal_payload_bytes_per_trace",
        "reference_capture_file_bytes",
        "candidate_capture_file_bytes",
        "metadata_bytes",
        "commitment_head_bytes",
        "commitment_chain_bytes",
        "reference_storage_head_bytes",
        "candidate_working_set_head_bytes",
        "challenge_working_set_head_bytes",
        "challenge_working_set_full_chain_bytes",
        "reference_capture_load_ms",
        "candidate_capture_load_ms",
        "commitment_generation_ms",
        "replay_ms",
        "compare_ms",
        "challenge_latency_no_commit_ms",
        "challenge_latency_ms",
        "detected",
        "first_mismatch_stage",
        "first_mismatch_checkpoint",
        "verdict_bytes",
    ]
    summary_fields = [
        "variant",
        "family",
        "scenario",
        "sample_count",
        "tolerance_mode",
        "percentile",
        "tolerance_scale",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "reveal_payload_bytes_per_trace",
        "mean_commitment_head_bytes",
        "mean_commitment_chain_bytes",
        "mean_reference_storage_head_bytes",
        "mean_candidate_working_set_head_bytes",
        "mean_challenge_working_set_head_bytes",
        "mean_challenge_working_set_full_chain_bytes",
        "mean_commitment_generation_ms",
        "mean_replay_ms",
        "mean_compare_ms",
        "mean_challenge_latency_no_commit_ms",
        "mean_challenge_latency_ms",
        "detection_rate",
        "dominant_mismatch_checkpoint",
    ]
    main_fields = [
        "variant",
        "family",
        "tolerance_mode",
        "percentile",
        "tolerance_scale",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "reveal_payload_bytes_per_trace",
        "mean_commitment_head_bytes",
        "mean_commitment_chain_bytes",
        "honest_homo_detection_rate",
        "honest_homo_challenge_latency_no_commit_ms",
        "honest_homo_challenge_latency_ms",
        "honest_hetero_detection_rate",
        "honest_hetero_challenge_latency_no_commit_ms",
        "honest_hetero_challenge_latency_ms",
        "tamper_detection_rate",
        "tamper_challenge_latency_no_commit_ms",
        "tamper_challenge_latency_ms",
    ]

    _write_csv(detail_csv, detail_rows, detail_fields)
    _write_csv(summary_csv, summary_rows, summary_fields)
    _write_csv(main_csv, main_rows, main_fields)
    _plot(main_rows, figure_path)

    lines = [
        f"# {RUN_ID}",
        "",
        f"- Selected configs source: {selected_summary}",
        "- Context: same live A/B 40-calibration / 200-evaluation captures used by equal-budget E2.",
        "- Commitment bytes count only digest-chain storage; reveal payload bytes count sketch disclosure on challenge path.",
        "- `challenge_latency_ms` includes capture load + commitment generation + replay + compare.",
        "- `challenge_latency_no_commit_ms` excludes commitment generation for compatibility with earlier drafts.",
        "- `reference_storage_head_bytes` is validator-retained reference storage; `candidate_working_set_*` and `challenge_working_set_*` are challenge-path working-set sizes.",
        f"- Detail CSV: {detail_csv}",
        f"- Summary CSV: {summary_csv}",
        f"- Main table CSV: {main_csv}",
        f"- Figure: {figure_path}",
        "",
        "## Main comparison",
        "",
    ]
    for row in main_rows:
        lines.append(
            f"- {row['variant']}: reveal={row['reveal_payload_bytes_per_trace']} B/trace, "
            f"hetero latency={row['honest_hetero_challenge_latency_ms']} ms "
            f"(no-commit {row['honest_hetero_challenge_latency_no_commit_ms']} ms), "
            f"tamper latency={row['tamper_challenge_latency_ms']} ms "
            f"(no-commit {row['tamper_challenge_latency_no_commit_ms']} ms), "
            f"hetero detect rate={row['honest_hetero_detection_rate']}, "
            f"tamper detect rate={row['tamper_detection_rate']}."
        )
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"detail table : {detail_csv}")
    print(f"summary table: {summary_csv}")
    print(f"main table   : {main_csv}")
    print(f"figure       : {figure_path}")
    print(f"notes        : {notes_path}")


if __name__ == "__main__":
    main()
