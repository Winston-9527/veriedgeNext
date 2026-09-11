from __future__ import annotations

import csv
import hashlib
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"
E5_DIR = REPO_ROOT / "paper1_veriedge" / "E5"
TABLE_DIR = E5_DIR / "tables"
NOTE_DIR = E5_DIR / "notes"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))
if str(E2_DIR) not in sys.path:
    sys.path.insert(0, str(E2_DIR))

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import compute_hash_chain, first_mismatch_index  # type: ignore

import build_e2_material_tamper_full_matrix as full  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "verification_profile_matrix"
RUN_ID = f"exp_e5_{STAMP}_{OWNER}"

TARGET_STAGE = "prefill"
ALPHA = 0.10
BETA = 0.90


def _latest_table(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern), key=lambda p: (p.stat().st_mtime, p.name))
    if not matches:
        raise FileNotFoundError(f"no files match {pattern} under {root}")
    return matches[-1]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def _variant_budget_class(bytes_per_ckpt: int) -> str:
    if bytes_per_ckpt <= 64:
        return "tiny"
    if bytes_per_ckpt <= 256:
        return "small"
    if bytes_per_ckpt <= 512:
        return "medium"
    return "large"


def _risk_class(eval_fpr: float, material_tpr_min: float) -> str:
    if eval_fpr <= 0.10 and material_tpr_min >= 0.90:
        return "low-risk"
    if eval_fpr <= 0.20 and material_tpr_min >= 0.80:
        return "medium-risk"
    if eval_fpr <= 0.30 and material_tpr_min >= 0.50:
        return "high-risk"
    return "unverifiable"


def _pair_contexts() -> Dict[str, Dict[str, Any]]:
    return {
        ctx["pair_id"]: ctx
        for ctx in (full._context_from_manifest(path) for path in full.PAIR_MANIFESTS)
    }


def _attack_index(rows: Sequence[Mapping[str, str]]) -> Dict[Tuple[str, str], Dict[str, Mapping[str, str]]]:
    index: Dict[Tuple[str, str], Dict[str, Mapping[str, str]]] = {}
    for row in rows:
        key = (str(row["pair_id"]), str(row["variant"]))
        index.setdefault(key, {})[str(row["attack_family"])] = row
    return index


def _overhead_exact_index(rows: Sequence[Mapping[str, str]]) -> Dict[str, Mapping[str, str]]:
    return {str(row["variant"]): row for row in rows}


def _projcos8_overhead_proxy(exact_rows: Mapping[str, Mapping[str, str]]) -> Dict[str, float]:
    low = exact_rows["projcos4"]
    high = exact_rows["projcos16"]
    return {
        "challenge_latency_ms": (
            float(low["honest_hetero_challenge_latency_ms"]) + float(high["honest_hetero_challenge_latency_ms"])
        )
        / 2.0,
        "commitment_head_bytes": float(low["mean_commitment_head_bytes"]),
        "commitment_chain_bytes": float(low["mean_commitment_chain_bytes"]),
    }


def _evaluate_honest_hetero(
    left_eval: Path,
    right_eval: Path,
    checkpoints: Sequence[str],
    hash_cfg: Any,
) -> Tuple[int, int, str]:
    prompt_ids = scalar._shared_prompt_ids(left_eval, right_eval)
    detect_count = 0
    mismatch_counter: Dict[str, int] = {}
    for prompt_id in prompt_ids:
        left_bundle, _ = _load_bundle(left_eval, prompt_id)
        right_bundle, _ = _load_bundle(right_eval, prompt_id)
        detected, first_checkpoint = _compute_detect(left_bundle, right_bundle, checkpoints, hash_cfg)
        if detected:
            detect_count += 1
            if first_checkpoint:
                mismatch_counter[first_checkpoint] = mismatch_counter.get(first_checkpoint, 0) + 1
    dominant = ""
    if mismatch_counter:
        dominant = max(mismatch_counter.items(), key=lambda item: item[1])[0]
    return len(prompt_ids), detect_count, dominant


def _evaluate_honest_homo_if_available(
    right_eval: Path,
    checkpoints: Sequence[str],
    hash_cfg: Any,
) -> Tuple[str, float, str]:
    rerun_root, rerun_source = full._rerun_root_for(right_eval)
    if rerun_source == "same_run_prev_prompt":
        return rerun_source, float("nan"), ""
    prompt_ids = scalar._shared_prompt_ids(right_eval, rerun_root)
    detect_count = 0
    mismatch_counter: Dict[str, int] = {}
    for prompt_id in prompt_ids:
        validator_bundle, _ = _load_bundle(right_eval, prompt_id)
        candidate_bundle, _ = _load_bundle(rerun_root, prompt_id)
        detected, first_checkpoint = _compute_detect(validator_bundle, candidate_bundle, checkpoints, hash_cfg)
        if detected:
            detect_count += 1
            if first_checkpoint:
                mismatch_counter[first_checkpoint] = mismatch_counter.get(first_checkpoint, 0) + 1
    dominant = ""
    if mismatch_counter:
        dominant = max(mismatch_counter.items(), key=lambda item: item[1])[0]
    fpr = detect_count / len(prompt_ids) if prompt_ids else float("nan")
    return rerun_source, fpr, dominant


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    import argparse

    parser = argparse.ArgumentParser(description="Build measured-profile verification profile matrix")
    parser.add_argument("--selected-operating-points")
    parser.add_argument("--attack-summary")
    parser.add_argument("--e4-main-table")
    args = parser.parse_args()

    selected_operating_points = Path(args.selected_operating_points).resolve() if args.selected_operating_points else _latest_table(E2_DIR / "tables", "exp_e2_*_material_tamper_full_matrix_selected_operating_points.csv")
    attack_summary = Path(args.attack_summary).resolve() if args.attack_summary else _latest_table(E2_DIR / "tables", "exp_e2_*_material_tamper_full_matrix_attack_summary.csv")
    e4_main_table = Path(args.e4_main_table).resolve() if args.e4_main_table else _latest_table(E4_DIR / "tables", "exp_e4_*_equal_budget_live_ab_main_table.csv")

    selected_rows = _read_csv(selected_operating_points)
    attack_rows = _read_csv(attack_summary)
    e4_rows = _read_csv(e4_main_table)

    pair_contexts = _pair_contexts()
    attack_index = _attack_index(attack_rows)
    exact_overhead = _overhead_exact_index(e4_rows)
    projcos8_proxy = _projcos8_overhead_proxy(exact_overhead)

    output_rows: List[Dict[str, Any]] = []

    for row in selected_rows:
        pair_id = str(row["pair_id"])
        variant = str(row["variant"])
        context = pair_contexts[pair_id]
        config = scalar._load_json(context["config_path"])
        checkpoints = checkpoint_order(config)
        _variant_spec, hash_cfg = full._selected_hash_cfg(row, checkpoints, context)

        prompt_count, detect_count, dominant_mismatch = _evaluate_honest_hetero(
            context["left_eval"],
            context["right_eval"],
            checkpoints,
            hash_cfg,
        )
        eval_honest_fpr = detect_count / prompt_count if prompt_count else float("nan")

        homo_source, eval_homo_fpr, homo_dominant_mismatch = _evaluate_honest_homo_if_available(
            context["right_eval"],
            checkpoints,
            hash_cfg,
        )

        attacks = attack_index[(pair_id, variant)]
        gaussian = attacks["gaussian"]
        stale = attacks["stale_replay"]
        wrong = attacks["wrong_prompt"]

        material_tprs = [float(gaussian["detection_rate"]), float(stale["detection_rate"]), float(wrong["detection_rate"])]
        material_locs = [
            float(gaussian["localization_acc"]),
            float(stale["localization_acc"]),
            float(wrong["localization_acc"]),
        ]
        replay_runtime_ms = statistics.mean(float(attacks[name]["runtime_ms_per_trace"]) for name in attacks)

        if variant in exact_overhead:
            overhead = exact_overhead[variant]
            reveal_payload_bytes = int(float(overhead["reveal_payload_bytes_per_trace"]))
            commitment_head_bytes = float(overhead["mean_commitment_head_bytes"])
            commitment_chain_bytes = float(overhead["mean_commitment_chain_bytes"])
            challenge_latency_ms = float(overhead["honest_hetero_challenge_latency_ms"])
            overhead_source = "measured_e4_ab"
        elif variant == "projcos8":
            reveal_payload_bytes = int(float(row["signature_bytes_per_checkpoint_fp32"])) * 3
            commitment_head_bytes = projcos8_proxy["commitment_head_bytes"]
            commitment_chain_bytes = projcos8_proxy["commitment_chain_bytes"]
            challenge_latency_ms = projcos8_proxy["challenge_latency_ms"]
            overhead_source = "estimated_interp_from_projcos4_projcos16"
        else:
            reveal_payload_bytes = int(float(row["signature_bytes_per_checkpoint_fp32"])) * 3
            commitment_head_bytes = 32.0
            commitment_chain_bytes = 96.0
            challenge_latency_ms = replay_runtime_ms
            overhead_source = "fallback_runtime_proxy"

        bytes_per_ckpt = int(float(row["signature_bytes_per_checkpoint_fp32"]))
        material_tpr_min = min(material_tprs)
        material_tpr_mean = statistics.mean(material_tprs)
        material_loc_min = min(material_locs)
        material_loc_mean = statistics.mean(material_locs)
        risk_class = _risk_class(eval_honest_fpr, material_tpr_min)
        feasible = int(eval_honest_fpr <= ALPHA and material_tpr_min >= BETA)

        output_rows.append(
            {
                "pair_id": pair_id,
                "pair_label": row["pair_label"],
                "variant": variant,
                "family": row["family"],
                "budget_class": _variant_budget_class(bytes_per_ckpt),
                "tolerance_mode": row["tolerance_mode"],
                "percentile": row["percentile"],
                "tolerance_scale": row["tolerance_scale"],
                "token_samples": row["token_samples"],
                "channel_samples": row["channel_samples"],
                "projection_dim": row["projection_dim"],
                "signature_scalars_per_checkpoint": row["signature_scalars_per_checkpoint"],
                "signature_bytes_per_checkpoint_fp32": bytes_per_ckpt,
                "reveal_payload_bytes_per_trace": reveal_payload_bytes,
                "commitment_head_bytes": round(commitment_head_bytes, 6),
                "commitment_chain_bytes": round(commitment_chain_bytes, 6),
                "eval_prompt_count": prompt_count,
                "calib_honest_hetero_fpr": row["calib_honest_hetero_fpr"],
                "eval_honest_hetero_fpr": round(eval_honest_fpr, 6),
                "eval_honest_homo_fpr": "" if eval_homo_fpr != eval_homo_fpr else round(eval_homo_fpr, 6),
                "eval_honest_hetero_detect_count": detect_count,
                "eval_honest_hetero_dominant_mismatch": dominant_mismatch,
                "honest_homo_source": homo_source,
                "eval_honest_homo_dominant_mismatch": homo_dominant_mismatch,
                "gaussian_tpr": round(float(gaussian["detection_rate"]), 6),
                "stale_replay_tpr": round(float(stale["detection_rate"]), 6),
                "wrong_prompt_tpr": round(float(wrong["detection_rate"]), 6),
                "gaussian_locacc": round(float(gaussian["localization_acc"]), 6),
                "stale_replay_locacc": round(float(stale["localization_acc"]), 6),
                "wrong_prompt_locacc": round(float(wrong["localization_acc"]), 6),
                "material_tpr_min": round(material_tpr_min, 6),
                "material_tpr_mean": round(material_tpr_mean, 6),
                "material_locacc_min": round(material_loc_min, 6),
                "material_locacc_mean": round(material_loc_mean, 6),
                "reference_replay_runtime_ms": round(replay_runtime_ms, 6),
                "challenge_latency_ms": round(challenge_latency_ms, 6),
                "risk_class": risk_class,
                "feasible_under_alpha_beta": feasible,
                "alpha_threshold": ALPHA,
                "beta_threshold": BETA,
                "overhead_source": overhead_source,
                "selection_rule": row["selection_rule"],
            }
        )

    output_rows.sort(key=lambda r: (str(r["pair_id"]), str(r["variant"])))
    out_csv = TABLE_DIR / f"{RUN_ID}.csv"
    notes_path = NOTE_DIR / f"{RUN_ID}.md"
    manifest_path = NOTE_DIR / f"{RUN_ID}_manifest.json"
    _write_csv(
        out_csv,
        output_rows,
        [
            "pair_id",
            "pair_label",
            "variant",
            "family",
            "budget_class",
            "tolerance_mode",
            "percentile",
            "tolerance_scale",
            "token_samples",
            "channel_samples",
            "projection_dim",
            "signature_scalars_per_checkpoint",
            "signature_bytes_per_checkpoint_fp32",
            "reveal_payload_bytes_per_trace",
            "commitment_head_bytes",
            "commitment_chain_bytes",
            "eval_prompt_count",
            "calib_honest_hetero_fpr",
            "eval_honest_hetero_fpr",
            "eval_honest_homo_fpr",
            "eval_honest_hetero_detect_count",
            "eval_honest_hetero_dominant_mismatch",
            "honest_homo_source",
            "eval_honest_homo_dominant_mismatch",
            "gaussian_tpr",
            "stale_replay_tpr",
            "wrong_prompt_tpr",
            "gaussian_locacc",
            "stale_replay_locacc",
            "wrong_prompt_locacc",
            "material_tpr_min",
            "material_tpr_mean",
            "material_locacc_min",
            "material_locacc_mean",
            "reference_replay_runtime_ms",
            "challenge_latency_ms",
            "risk_class",
            "feasible_under_alpha_beta",
            "alpha_threshold",
            "beta_threshold",
            "overhead_source",
            "selection_rule",
        ],
    )

    feasible_count = sum(int(row["feasible_under_alpha_beta"]) for row in output_rows)
    manifest = {
        "run_id": RUN_ID,
        "inputs": {
            "selected_operating_points": {"path": str(selected_operating_points), "sha256": _sha256(selected_operating_points)},
            "attack_summary": {"path": str(attack_summary), "sha256": _sha256(attack_summary)},
            "e4_main_table": {"path": str(e4_main_table), "sha256": _sha256(e4_main_table)},
        },
        "thresholds": {"alpha": ALPHA, "beta": BETA},
        "output_csv": str(out_csv),
    }
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(__import__("json").dumps(manifest, indent=2), encoding="utf-8")
    lines = [
        f"# {RUN_ID}",
        "",
        "- Built from current strict measured results.",
        f"- Selected operating points source: {selected_operating_points}",
        f"- Material tamper summary source: {attack_summary}",
        f"- Overhead source: {e4_main_table}",
        f"- Manifest: {manifest_path}",
        "",
        "## Coverage",
        "",
        f"- rows: {len(output_rows)}",
        f"- feasible rows under alpha={ALPHA:.2f}, beta={BETA:.2f}: {feasible_count}",
        "",
        "## Notes",
        "",
        "- `eval_honest_hetero_fpr` is recomputed on held-out eval captures using the selected operating point for each pair x variant.",
        "- `material_*` metrics come from the full material-tamper matrix (gaussian, stale_replay, wrong_prompt).",
        "- `challenge_latency_ms` is exact for variants with E4 equal-budget measurements and estimated by interpolation for `projcos8`.",
        "- `eval_honest_homo_fpr` is only filled when a compatible rerun/absrepro donor exists.",
    ]
    notes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(out_csv)
    print(notes_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
