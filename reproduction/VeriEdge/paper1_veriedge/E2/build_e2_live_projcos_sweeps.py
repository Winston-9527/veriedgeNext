from __future__ import annotations

import csv
import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from checkpoint_qwen import checkpoint_order  # type: ignore
from hash_chain import HashConfig, project_prefill_signature  # type: ignore
from pipeline_qwen import run_qwen_trial  # type: ignore

import build_e2_strict_tables as base  # type: ignore


OWNER = "live_ab_projcos_mainline"
STAMP = time.strftime("%Y%m%d")
TABLE_DIR = REPO_ROOT / "paper1_veriedge" / "E2" / "tables"
NOTE_DIR = REPO_ROOT / "paper1_veriedge" / "E2" / "notes"

TARGET_STAGE = "prefill"
PERCENTILES = [99.0, 99.5, 99.9, 99.95, 99.99]
PROJECTION_DIMS = [4, 8, 16, 32, 64]
TOKEN_SAMPLES = 16
TOLERANCE_SCALES = [0.5, 1.0, 1.5, 2.0]
BASELINE_PERCENTILE = 99.95
BASELINE_PROJECTION_DIM = 16
PROJECTION_SEED = 911

LIVE_A_CALIB = REPO_ROOT / "workspace" / "captures" / "E2_live" / "stack_a_calib_40"
LIVE_A_EVAL = REPO_ROOT / "workspace" / "captures" / "E2_live" / "stack_a_eval_200"
LIVE_B_CALIB = REPO_ROOT / "workspace" / "captures" / "E2_live" / "stack_b_calib_40"
LIVE_B_EVAL = REPO_ROOT / "workspace" / "captures" / "E2_live" / "stack_b_eval_200"
LIVE_B_RERUN = REPO_ROOT / "workspace" / "captures" / "E2_live" / "stack_b_rerun_eval_200"
CONFIG_PATH = REPO_ROOT / "artifacts" / "thc" / "config" / "e1_real_qwen_tstc_prefill_1x1_40_200.json"


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _live_context() -> Dict[str, Any]:
    return {
        "config_path": CONFIG_PATH,
        "left_calib": LIVE_A_CALIB,
        "right_calib": LIVE_B_CALIB,
        "left_eval": LIVE_A_EVAL,
        "right_eval": LIVE_B_EVAL,
        "homo_left_eval": LIVE_B_EVAL,
        "homo_right_eval": LIVE_B_RERUN,
        "tamper_root": LIVE_B_EVAL,
        "pair_label": "live_stack_a_vs_stack_b",
    }


def _projcos_cfg(delta_map: Dict[str, Dict[str, float]], projection_dim: int, token_samples: int = TOKEN_SAMPLES) -> HashConfig:
    return HashConfig(
        mode="tstc_projcos",
        seed_base=2026,
        delta_map=json.loads(json.dumps(delta_map, ensure_ascii=True)),
        prefill_token_samples=int(token_samples),
        prefill_projection_dim=int(projection_dim),
        decode_channel_samples=1,
        projection_seed=PROJECTION_SEED,
    )


def _projcos_hash_params(
    delta_map: Dict[str, Dict[str, float]],
    projection_dim: int,
    token_samples: int = TOKEN_SAMPLES,
) -> Dict[str, Any]:
    return {
        "mode": "tstc_projcos",
        "seed_base": 2026,
        "delta_map": json.loads(json.dumps(delta_map, ensure_ascii=True)),
        "prefill_token_samples": int(token_samples),
        "prefill_projection_dim": int(projection_dim),
        "decode_channel_samples": 1,
        "projection_seed": PROJECTION_SEED,
    }


def _calibrate_projcos_percentile(
    capture_roots: Sequence[Path],
    checkpoints: Sequence[str],
    percentile: float,
    projection_dim: int,
    token_samples: int = TOKEN_SAMPLES,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    machine_maps = {root.name: base._load_npz_map(root) for root in capture_roots}
    common_prompts = set.intersection(*(set(prompt_map.keys()) for prompt_map in machine_maps.values()))
    grouped: Dict[Tuple[str, str], List[float]] = {}
    proto_cfg = _projcos_cfg({"prefill": {}, "decode": {}}, projection_dim=projection_dim, token_samples=token_samples)
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
                _, left_sig = project_prefill_signature(left_payload[key], proto_cfg, checkpoint, seed)
                _, right_sig = project_prefill_signature(right_payload[key], proto_cfg, checkpoint, seed)
                denom = np.maximum(
                    np.linalg.norm(left_sig, axis=1) * np.linalg.norm(right_sig, axis=1),
                    1e-12,
                )
                cosine = np.sum(left_sig * right_sig, axis=1) / denom
                mean_gap = float(np.mean(1.0 - cosine)) if cosine.size else 0.0
                grouped.setdefault(("prefill", checkpoint), []).append(mean_gap)

    delta_map = {"prefill": {}, "decode": {}}
    summary_lookup: Dict[str, float] = {}
    for (_, checkpoint), gap_values in sorted(grouped.items()):
        values = np.asarray(gap_values, dtype=np.float32)
        delta = float(np.percentile(values, percentile)) if values.size else 0.0
        delta_map["prefill"][checkpoint] = delta
        summary_lookup[f"prefill_{checkpoint}"] = delta
    return delta_map, summary_lookup


def _tamper_metrics_projcos(
    config: Dict[str, Any],
    capture_root: Path,
    prompt_map: Mapping[str, Dict[str, str]],
    hash_params: Dict[str, Any],
) -> Dict[str, Any]:
    prompt_ids = sorted(prompt_map.keys())
    thc_rows: List[Dict[str, Any]] = []
    projcos_rows: List[Dict[str, Any]] = []

    thc_start = time.perf_counter()
    for prompt_id in prompt_ids:
        bundle, metadata, runtime = base._load_capture_bundle(capture_root, prompt_id)
        result = run_qwen_trial(
            config=config,
            scenario="tamper",
            verifier="thc",
            trial_index=0,
            prompt_record=prompt_map[prompt_id],
            captured_bundle=bundle,
            captured_metadata=metadata,
            captured_runtime=runtime,
        )
        thc_rows.extend([row for row in result["records"] if str(row["stage"]) == TARGET_STAGE])
    thc_runtime_sec = time.perf_counter() - thc_start

    proj_start = time.perf_counter()
    for prompt_id in prompt_ids:
        bundle, metadata, runtime = base._load_capture_bundle(capture_root, prompt_id)
        result = run_qwen_trial(
            config=config,
            scenario="tamper",
            verifier="tstc_projcos",
            trial_index=0,
            prompt_record=prompt_map[prompt_id],
            hash_params=hash_params,
            captured_bundle=bundle,
            captured_metadata=metadata,
            captured_runtime=runtime,
        )
        projcos_rows.extend([row for row in result["records"] if str(row["stage"]) == TARGET_STAGE])
    proj_runtime_sec = time.perf_counter() - proj_start

    def _agg(rows: Sequence[Mapping[str, Any]]) -> Tuple[float, float]:
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        tpr = sum(1 for row in rows if row.get("detected")) / n
        loc = sum(1 for row in rows if row.get("localization_correct")) / n
        return round(tpr, 6), round(loc, 6)

    thc_tpr, thc_loc = _agg(thc_rows)
    proj_tpr, proj_loc = _agg(projcos_rows)
    return {
        "prompt_count_tamper": len(prompt_ids),
        "thc_tpr": thc_tpr,
        "projcos_tpr": proj_tpr,
        "thc_localization_acc": thc_loc,
        "projcos_localization_acc": proj_loc,
        "thc_runtime_sec_tamper": round(thc_runtime_sec, 6),
        "projcos_runtime_sec_tamper": round(proj_runtime_sec, 6),
    }


def _row_with_runtime(
    base_row: Dict[str, Any],
    homo_metrics: Dict[str, Any],
    hetero_metrics: Dict[str, Any],
    tamper_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    row = dict(base_row)
    row.update(
        {
            "honest_homo_thc_fpr": homo_metrics["thc_fpr"],
            "honest_homo_projcos_fpr": homo_metrics["tstc_fpr"],
            "honest_homo_thc_runtime_ms_per_trace": round((float(homo_metrics["thc_runtime_sec"]) * 1000.0) / homo_metrics["prompt_count"], 6),
            "honest_homo_projcos_runtime_ms_per_trace": round((float(homo_metrics["tstc_runtime_sec"]) * 1000.0) / homo_metrics["prompt_count"], 6),
            "honest_hetero_thc_fpr": hetero_metrics["thc_fpr"],
            "honest_hetero_projcos_fpr": hetero_metrics["tstc_fpr"],
            "honest_hetero_thc_runtime_ms_per_trace": round((float(hetero_metrics["thc_runtime_sec"]) * 1000.0) / hetero_metrics["prompt_count"], 6),
            "honest_hetero_projcos_runtime_ms_per_trace": round((float(hetero_metrics["tstc_runtime_sec"]) * 1000.0) / hetero_metrics["prompt_count"], 6),
            "honest_hetero_dominant_projcos_mismatch_checkpoint": hetero_metrics["tstc_dominant_mismatch_checkpoint"],
            "tamper_thc_tpr": tamper_metrics["thc_tpr"],
            "tamper_projcos_tpr": tamper_metrics["projcos_tpr"],
            "tamper_thc_locacc": tamper_metrics["thc_localization_acc"],
            "tamper_projcos_locacc": tamper_metrics["projcos_localization_acc"],
            "tamper_thc_runtime_ms_per_trace": round((float(tamper_metrics["thc_runtime_sec_tamper"]) * 1000.0) / tamper_metrics["prompt_count_tamper"], 6),
            "tamper_projcos_runtime_ms_per_trace": round((float(tamper_metrics["projcos_runtime_sec_tamper"]) * 1000.0) / tamper_metrics["prompt_count_tamper"], 6),
        }
    )
    return row


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    context = _live_context()
    config = base._load_json(context["config_path"])
    prompt_map = base._prompt_map(config, split="evaluation")
    checkpoints = checkpoint_order(config)

    sample_rows: List[Dict[str, Any]] = []
    percentile_rows: List[Dict[str, Any]] = []
    tolerance_rows: List[Dict[str, Any]] = []
    global_rows: List[Dict[str, Any]] = []
    runtime_rows: List[Dict[str, Any]] = []

    baseline_delta_map, baseline_delta_lookup = _calibrate_projcos_percentile(
        [context["left_calib"], context["right_calib"]],
        checkpoints,
        BASELINE_PERCENTILE,
        projection_dim=BASELINE_PROJECTION_DIM,
    )
    baseline_global_delta_map = base._globalize_delta_map(baseline_delta_map)

    for percentile in PERCENTILES:
        checkpoint_delta_map, checkpoint_delta_lookup = _calibrate_projcos_percentile(
            [context["left_calib"], context["right_calib"]],
            checkpoints,
            percentile,
            projection_dim=BASELINE_PROJECTION_DIM,
        )
        variants = (
            ("checkpoint_specific", checkpoint_delta_map, checkpoint_delta_lookup),
            (
                "global_shared",
                base._globalize_delta_map(checkpoint_delta_map),
                {
                    "prefill_C1": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                    "prefill_C2": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                    "prefill_C3": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                },
            ),
        )
        for mode, delta_map, delta_lookup in variants:
            proj_cfg = _projcos_cfg(delta_map, projection_dim=BASELINE_PROJECTION_DIM)
            homo_metrics = base._pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
            hetero_metrics = base._pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
            tamper_metrics = _tamper_metrics_projcos(
                config,
                context["tamper_root"],
                prompt_map,
                _projcos_hash_params(delta_map, projection_dim=BASELINE_PROJECTION_DIM),
            )
            percentile_rows.append(
                _row_with_runtime(
                    {
                        "projection_dim": BASELINE_PROJECTION_DIM,
                        "token_samples": TOKEN_SAMPLES,
                        "signature_scalars_per_checkpoint": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM,
                        "signature_bytes_per_checkpoint_fp32": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM * 4,
                        "percentile": percentile,
                        "tolerance_mode": mode,
                        "tolerance_scale": 1.0,
                        "prefill_delta_c1": delta_lookup.get("prefill_C1", 0.0),
                        "prefill_delta_c2": delta_lookup.get("prefill_C2", 0.0),
                        "prefill_delta_c3": delta_lookup.get("prefill_C3", 0.0),
                    },
                    homo_metrics,
                    hetero_metrics,
                    tamper_metrics,
                )
            )

    for projection_dim in PROJECTION_DIMS:
        delta_map, delta_lookup = _calibrate_projcos_percentile(
            [context["left_calib"], context["right_calib"]],
            checkpoints,
            BASELINE_PERCENTILE,
            projection_dim=projection_dim,
        )
        proj_cfg = _projcos_cfg(delta_map, projection_dim=projection_dim)
        homo_metrics = base._pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        hetero_metrics = base._pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        tamper_metrics = _tamper_metrics_projcos(
            config,
            context["tamper_root"],
            prompt_map,
            _projcos_hash_params(delta_map, projection_dim=projection_dim),
        )
        row = _row_with_runtime(
            {
                "projection_dim": projection_dim,
                "token_samples": TOKEN_SAMPLES,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * projection_dim,
                "signature_bytes_per_checkpoint_fp32": TOKEN_SAMPLES * projection_dim * 4,
                "percentile": BASELINE_PERCENTILE,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": 1.0,
                "prefill_delta_c1": delta_lookup.get("prefill_C1", 0.0),
                "prefill_delta_c2": delta_lookup.get("prefill_C2", 0.0),
                "prefill_delta_c3": delta_lookup.get("prefill_C3", 0.0),
            },
            homo_metrics,
            hetero_metrics,
            tamper_metrics,
        )
        sample_rows.append(row)
        runtime_rows.append(
            {
                "study": "projection_dim_sweep",
                "projection_dim": projection_dim,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * projection_dim,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": 1.0,
                "honest_homo_projcos_runtime_ms_per_trace": row["honest_homo_projcos_runtime_ms_per_trace"],
                "honest_hetero_projcos_runtime_ms_per_trace": row["honest_hetero_projcos_runtime_ms_per_trace"],
                "tamper_projcos_runtime_ms_per_trace": row["tamper_projcos_runtime_ms_per_trace"],
            }
        )

    for scale in TOLERANCE_SCALES:
        scaled_delta = base._scale_delta_map(baseline_delta_map, scale)
        proj_cfg = _projcos_cfg(scaled_delta, projection_dim=BASELINE_PROJECTION_DIM)
        homo_metrics = base._pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        hetero_metrics = base._pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        tamper_metrics = _tamper_metrics_projcos(
            config,
            context["tamper_root"],
            prompt_map,
            _projcos_hash_params(scaled_delta, projection_dim=BASELINE_PROJECTION_DIM),
        )
        row = _row_with_runtime(
            {
                "projection_dim": BASELINE_PROJECTION_DIM,
                "token_samples": TOKEN_SAMPLES,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM,
                "signature_bytes_per_checkpoint_fp32": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM * 4,
                "percentile": BASELINE_PERCENTILE,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": scale,
                "prefill_delta_c1": scaled_delta.get("prefill", {}).get("C1", 0.0),
                "prefill_delta_c2": scaled_delta.get("prefill", {}).get("C2", 0.0),
                "prefill_delta_c3": scaled_delta.get("prefill", {}).get("C3", 0.0),
            },
            homo_metrics,
            hetero_metrics,
            tamper_metrics,
        )
        tolerance_rows.append(row)
        runtime_rows.append(
            {
                "study": "tolerance_scale_sweep",
                "projection_dim": BASELINE_PROJECTION_DIM,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": scale,
                "honest_homo_projcos_runtime_ms_per_trace": row["honest_homo_projcos_runtime_ms_per_trace"],
                "honest_hetero_projcos_runtime_ms_per_trace": row["honest_hetero_projcos_runtime_ms_per_trace"],
                "tamper_projcos_runtime_ms_per_trace": row["tamper_projcos_runtime_ms_per_trace"],
            }
        )

    for mode, active_delta in (
        ("checkpoint_specific", baseline_delta_map),
        ("global_shared", baseline_global_delta_map),
    ):
        proj_cfg = _projcos_cfg(active_delta, projection_dim=BASELINE_PROJECTION_DIM)
        homo_metrics = base._pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        hetero_metrics = base._pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, base._thc_cfg(), proj_cfg)
        tamper_metrics = _tamper_metrics_projcos(
            config,
            context["tamper_root"],
            prompt_map,
            _projcos_hash_params(active_delta, projection_dim=BASELINE_PROJECTION_DIM),
        )
        row = _row_with_runtime(
            {
                "projection_dim": BASELINE_PROJECTION_DIM,
                "token_samples": TOKEN_SAMPLES,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM,
                "signature_bytes_per_checkpoint_fp32": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM * 4,
                "percentile": BASELINE_PERCENTILE,
                "tolerance_mode": mode,
                "tolerance_scale": 1.0,
                "prefill_delta_c1": active_delta.get("prefill", {}).get("C1", 0.0),
                "prefill_delta_c2": active_delta.get("prefill", {}).get("C2", 0.0),
                "prefill_delta_c3": active_delta.get("prefill", {}).get("C3", 0.0),
            },
            homo_metrics,
            hetero_metrics,
            tamper_metrics,
        )
        global_rows.append(row)
        runtime_rows.append(
            {
                "study": "global_vs_checkpoint",
                "projection_dim": BASELINE_PROJECTION_DIM,
                "signature_scalars_per_checkpoint": TOKEN_SAMPLES * BASELINE_PROJECTION_DIM,
                "tolerance_mode": mode,
                "tolerance_scale": 1.0,
                "honest_homo_projcos_runtime_ms_per_trace": row["honest_homo_projcos_runtime_ms_per_trace"],
                "honest_hetero_projcos_runtime_ms_per_trace": row["honest_hetero_projcos_runtime_ms_per_trace"],
                "tamper_projcos_runtime_ms_per_trace": row["tamper_projcos_runtime_ms_per_trace"],
            }
        )

    common_fields = [
        "projection_dim",
        "token_samples",
        "signature_scalars_per_checkpoint",
        "signature_bytes_per_checkpoint_fp32",
        "percentile",
        "tolerance_mode",
        "tolerance_scale",
        "honest_homo_thc_fpr",
        "honest_homo_projcos_fpr",
        "honest_homo_thc_runtime_ms_per_trace",
        "honest_homo_projcos_runtime_ms_per_trace",
        "honest_hetero_thc_fpr",
        "honest_hetero_projcos_fpr",
        "honest_hetero_thc_runtime_ms_per_trace",
        "honest_hetero_projcos_runtime_ms_per_trace",
        "honest_hetero_dominant_projcos_mismatch_checkpoint",
        "tamper_thc_tpr",
        "tamper_projcos_tpr",
        "tamper_thc_locacc",
        "tamper_projcos_locacc",
        "tamper_thc_runtime_ms_per_trace",
        "tamper_projcos_runtime_ms_per_trace",
        "prefill_delta_c1",
        "prefill_delta_c2",
        "prefill_delta_c3",
    ]

    sample_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_samplesweep.csv"
    percentile_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_percentilesweep.csv"
    tol_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_tolerancesweep.csv"
    global_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_global_vs_checkpoint_delta.csv"
    runtime_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_runtime.csv"

    _write_csv(sample_csv, sample_rows, common_fields)
    _write_csv(percentile_csv, percentile_rows, common_fields)
    _write_csv(tol_csv, tolerance_rows, common_fields)
    _write_csv(global_csv, global_rows, common_fields)
    _write_csv(
        runtime_csv,
        runtime_rows,
        [
            "study",
            "projection_dim",
            "signature_scalars_per_checkpoint",
            "tolerance_mode",
            "tolerance_scale",
            "honest_homo_projcos_runtime_ms_per_trace",
            "honest_hetero_projcos_runtime_ms_per_trace",
            "tamper_projcos_runtime_ms_per_trace",
        ],
    )

    note_path = NOTE_DIR / "e2_live_projcos_run_notes.md"
    note_path.write_text(
        "\n".join(
            [
                "# E2 Live ProjCos Run Notes",
                "",
                f"- Pair label: `{context['pair_label']}`",
                f"- Left calibration root: `{context['left_calib']}`",
                f"- Right calibration root: `{context['right_calib']}`",
                f"- Left evaluation root: `{context['left_eval']}`",
                f"- Right evaluation root: `{context['right_eval']}`",
                f"- Homogeneous rerun root: `{context['homo_right_eval']}`",
                f"- Baseline percentile for sweeps: `{BASELINE_PERCENTILE}`",
                f"- Baseline projection dim: `{BASELINE_PROJECTION_DIM}`",
                f"- Projection-dim sweep: `{PROJECTION_DIMS}`",
                f"- Tolerance scales: `{TOLERANCE_SCALES}`",
                "- Sample size is interpreted as `projection_dim` growth with all 16 prefill tokens retained.",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Wrote live projcos E2 sweep tables to {TABLE_DIR}")


if __name__ == "__main__":
    main()
