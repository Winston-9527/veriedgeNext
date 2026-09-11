from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, load_prompt_records, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import HashConfig, compute_hash_chain, first_mismatch_index  # type: ignore
from pipeline_qwen import run_qwen_trial  # type: ignore


OWNER = "strict_ab_mainline"
STAMP = time.strftime("%Y%m%d")
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
LOG_DIR = E2_DIR / "logs" / f"exp_e2_{STAMP}_{OWNER}"
TABLE_DIR = E2_DIR / "tables"
NOTE_DIR = E2_DIR / "notes"

STRICT_PAIR_MANIFEST = Path(
    os.environ.get(
        "STRICT_PAIR_MANIFEST",
        str(
            REPO_ROOT
            / "paper1_veriedge"
            / "E1"
            / "logs"
            / "t4strict_pair_a_vs_b_40_200"
            / "exp_e1_20260504_t4strict_pair_a_vs_b_40_200_manifest.json"
        ),
    )
)
HOMO_RERUN_ROOT = Path(
    os.environ.get(
        "HOMO_RERUN_ROOT",
        str(
            REPO_ROOT
            / "workspace"
            / "captures"
            / "E1"
            / "t4strict_stack_b_applebf16_applebf16_rtxfp32_40_200_eval_rerun"
        ),
    )
)

SAMPLE_SIZES = [4, 8, 16, 32, 64]
TOLERANCE_SCALES = [0.5, 1.0, 1.5, 2.0]
FIXED_SAMPLE_SIZE = 4
TARGET_STAGE = "prefill"
PERCENTILES = [99.0, 99.5, 99.9, 99.95, 99.99]
SAMPLING_GRID = [
    (1, 4),
    (2, 2),
    (1, 8),
    (2, 4),
    (4, 4),
    (2, 8),
    (4, 8),
]


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _load_capture_bundle(capture_root: Path, prompt_id: str) -> Tuple[Mapping[str, Mapping[str, np.ndarray]], List[Dict[str, Any]], str]:
    return load_capture_bundle_for_prompt(capture_root, prompt_id)


def _load_npz_map(capture_root: Path) -> Dict[str, Dict[str, np.ndarray]]:
    capture_dir = capture_root / "captures"
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for npz_path in sorted(capture_dir.glob("*.npz")):
        with np.load(npz_path) as data:
            out[npz_path.stem] = {key: data[key].astype(np.float32) for key in data.files}
    return out


def _iter_values(payloads: Iterable[np.ndarray]) -> np.ndarray:
    arrays = [np.asarray(arr, dtype=np.float32).reshape(-1) for arr in payloads]
    if not arrays:
        return np.array([], dtype=np.float32)
    return np.concatenate(arrays, axis=0).astype(np.float32)


def _prompt_map(config: Dict[str, Any], split: str = "evaluation") -> Dict[str, Dict[str, str]]:
    return {row["prompt_id"]: row for row in load_prompt_records(config, split=split)}


def _trial_index_for_prompt(prompt_id: str) -> int:
    digest = hashlib.sha256(prompt_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _shared_prompt_ids(left_root: Path, right_root: Path) -> List[str]:
    left_ids = {path.stem for path in (left_root / "captures").glob("*.npz")}
    right_ids = {path.stem for path in (right_root / "captures").glob("*.npz")}
    return sorted(left_ids & right_ids)


def _stage_keys(bundle: Mapping[str, Mapping[str, Any]], family: str) -> List[str]:
    return [key for key in ordered_stage_keys(bundle.keys()) if stage_family(key) == family]


def _thc_cfg() -> HashConfig:
    return HashConfig(mode="thc")


def _build_hash_cfg(delta_map: Dict[str, Dict[str, float]], sample_size: int) -> HashConfig:
    return HashConfig(
        mode="tstc",
        seed_base=2026,
        delta_map=json.loads(json.dumps(delta_map, ensure_ascii=True)),
        prefill_token_samples=1,
        prefill_channel_samples=int(sample_size),
        decode_channel_samples=1,
    )


def _build_hash_cfg_grid(delta_map: Dict[str, Dict[str, float]], token_samples: int, channel_samples: int) -> HashConfig:
    return HashConfig(
        mode="tstc",
        seed_base=2026,
        delta_map=json.loads(json.dumps(delta_map, ensure_ascii=True)),
        prefill_token_samples=int(token_samples),
        prefill_channel_samples=int(channel_samples),
        decode_channel_samples=1,
    )


def _pair_fpr(
    left_root: Path,
    right_root: Path,
    checkpoints: Sequence[str],
    stage_family_name: str,
    thc_cfg: HashConfig,
    tstc_cfg: HashConfig,
) -> Dict[str, Any]:
    prompt_ids = _shared_prompt_ids(left_root, right_root)
    thc_detect = 0
    tstc_detect = 0
    thc_counter: Counter[str] = Counter()
    tstc_counter: Counter[str] = Counter()

    thc_start = time.perf_counter()
    for prompt_id in prompt_ids:
        left_bundle, _, _ = _load_capture_bundle(left_root, prompt_id)
        right_bundle, _, _ = _load_capture_bundle(right_root, prompt_id)
        for stage_key in _stage_keys(left_bundle, stage_family_name):
            left_stage = left_bundle[stage_key]
            right_stage = right_bundle[stage_key]
            thc_chain_left = compute_hash_chain(left_stage, checkpoints, stage_family_name, thc_cfg)
            thc_chain_right = compute_hash_chain(right_stage, checkpoints, stage_family_name, thc_cfg)
            thc_mismatch = first_mismatch_index(thc_chain_left, thc_chain_right)
            if thc_mismatch is not None:
                thc_detect += 1
                thc_counter[checkpoints[thc_mismatch]] += 1
    thc_runtime_sec = time.perf_counter() - thc_start

    tstc_start = time.perf_counter()
    for prompt_id in prompt_ids:
        left_bundle, _, _ = _load_capture_bundle(left_root, prompt_id)
        right_bundle, _, _ = _load_capture_bundle(right_root, prompt_id)
        for stage_key in _stage_keys(left_bundle, stage_family_name):
            left_stage = left_bundle[stage_key]
            right_stage = right_bundle[stage_key]
            tstc_chain_left = compute_hash_chain(left_stage, checkpoints, stage_family_name, tstc_cfg)
            tstc_chain_right = compute_hash_chain(right_stage, checkpoints, stage_family_name, tstc_cfg)
            tstc_mismatch = first_mismatch_index(tstc_chain_left, tstc_chain_right)
            if tstc_mismatch is not None:
                tstc_detect += 1
                tstc_counter[checkpoints[tstc_mismatch]] += 1
    tstc_runtime_sec = time.perf_counter() - tstc_start

    count = len(prompt_ids)
    return {
        "prompt_count": count,
        "thc_fpr": round(thc_detect / count, 6) if count else 0.0,
        "tstc_fpr": round(tstc_detect / count, 6) if count else 0.0,
        "thc_detect_count": thc_detect,
        "tstc_detect_count": tstc_detect,
        "thc_dominant_mismatch_checkpoint": thc_counter.most_common(1)[0][0] if thc_counter else "",
        "tstc_dominant_mismatch_checkpoint": tstc_counter.most_common(1)[0][0] if tstc_counter else "",
        "thc_runtime_sec": round(thc_runtime_sec, 6),
        "tstc_runtime_sec": round(tstc_runtime_sec, 6),
    }


def _tamper_metrics(
    config: Dict[str, Any],
    capture_root: Path,
    prompt_map: Mapping[str, Dict[str, str]],
    hash_params: Dict[str, Any],
) -> Dict[str, Any]:
    prompt_ids = sorted(prompt_map.keys())
    thc_rows: List[Dict[str, Any]] = []
    tstc_rows: List[Dict[str, Any]] = []

    thc_start = time.perf_counter()
    for prompt_id in prompt_ids:
        bundle, metadata, runtime = _load_capture_bundle(capture_root, prompt_id)
        result = run_qwen_trial(
            config=config,
            scenario="tamper",
            verifier="thc",
            trial_index=_trial_index_for_prompt(prompt_id),
            prompt_record=prompt_map[prompt_id],
            captured_bundle=bundle,
            captured_metadata=metadata,
            captured_runtime=runtime,
        )
        thc_rows.extend([row for row in result["records"] if str(row["stage"]) == TARGET_STAGE])
    thc_runtime_sec = time.perf_counter() - thc_start

    tstc_start = time.perf_counter()
    for prompt_id in prompt_ids:
        bundle, metadata, runtime = _load_capture_bundle(capture_root, prompt_id)
        result = run_qwen_trial(
            config=config,
            scenario="tamper",
            verifier="tstc",
            trial_index=_trial_index_for_prompt(prompt_id),
            prompt_record=prompt_map[prompt_id],
            hash_params=hash_params,
            captured_bundle=bundle,
            captured_metadata=metadata,
            captured_runtime=runtime,
        )
        tstc_rows.extend([row for row in result["records"] if str(row["stage"]) == TARGET_STAGE])
    tstc_runtime_sec = time.perf_counter() - tstc_start

    def _agg(rows: Sequence[Mapping[str, Any]]) -> Tuple[float, float]:
        if not rows:
            return 0.0, 0.0
        n = len(rows)
        tpr = sum(1 for row in rows if row.get("detected")) / n
        loc = sum(1 for row in rows if row.get("localization_correct")) / n
        return round(tpr, 6), round(loc, 6)

    thc_tpr, thc_loc = _agg(thc_rows)
    tstc_tpr, tstc_loc = _agg(tstc_rows)
    return {
        "prompt_count_tamper": len(prompt_ids),
        "thc_tpr": thc_tpr,
        "tstc_tpr": tstc_tpr,
        "thc_localization_acc": thc_loc,
        "tstc_localization_acc": tstc_loc,
        "thc_runtime_sec_tamper": round(thc_runtime_sec, 6),
        "tstc_runtime_sec_tamper": round(tstc_runtime_sec, 6),
    }


def _globalize_delta_map(delta_map: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    global_map: Dict[str, Dict[str, float]] = {}
    for stage_name, checkpoints in delta_map.items():
        values = [float(value) for value in checkpoints.values()]
        shared = max(values) if values else 0.0
        global_map[stage_name] = {checkpoint: shared for checkpoint in checkpoints}
    return global_map


def _scale_delta_map(delta_map: Dict[str, Dict[str, float]], scale: float) -> Dict[str, Dict[str, float]]:
    scaled: Dict[str, Dict[str, float]] = {}
    for stage_name, checkpoints in delta_map.items():
        scaled[stage_name] = {
            checkpoint: float(value) * float(scale) for checkpoint, value in checkpoints.items()
        }
    return scaled


def _calibrate_percentile(
    capture_roots: Sequence[Path],
    percentile: float,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    machine_maps = {root.name: _load_npz_map(root) for root in capture_roots}
    common_prompts = set.intersection(*(set(prompt_map.keys()) for prompt_map in machine_maps.values()))
    grouped: Dict[Tuple[str, str], List[np.ndarray]] = {}

    machine_names = list(machine_maps.keys())
    for left_name, right_name in combinations(machine_names, 2):
        left_prompts = machine_maps[left_name]
        right_prompts = machine_maps[right_name]
        for prompt_id in sorted(common_prompts):
            left_payload = left_prompts[prompt_id]
            right_payload = right_prompts[prompt_id]
            for key in sorted(set(left_payload.keys()) & set(right_payload.keys())):
                stage_key, checkpoint = key.split("__", 1)
                fam = stage_family(stage_key)
                diff = np.abs(left_payload[key].reshape(-1) - right_payload[key].reshape(-1)).astype(np.float32)
                grouped.setdefault((fam, checkpoint), []).append(diff)

    delta_map = {"prefill": {}, "decode": {}}
    summary_lookup: Dict[str, float] = {}
    for (fam, checkpoint), diffs in sorted(grouped.items()):
        values = _iter_values(diffs)
        delta = float(np.percentile(values, percentile)) if values.size else 0.0
        delta_map[fam][checkpoint] = delta
        summary_lookup[f"{fam}_{checkpoint}"] = delta
    return delta_map, summary_lookup


def _load_context() -> Dict[str, Any]:
    manifest = _load_json(STRICT_PAIR_MANIFEST)
    left_eval = Path(manifest["pairs"][0]["left_capture_root"]).resolve()
    right_eval = Path(manifest["pairs"][0]["right_capture_root"]).resolve()
    left_calib = left_eval.parent / f"{left_eval.name.replace('_eval', '_calib')}"
    right_calib = right_eval.parent / f"{right_eval.name.replace('_eval', '_calib')}"
    return {
        "config_path": Path(manifest["config"]).resolve(),
        "baseline_delta_map_path": Path(manifest["delta_map_file"]).resolve(),
        "left_eval": left_eval,
        "right_eval": right_eval,
        "left_calib": left_calib,
        "right_calib": right_calib,
        "pair_label": str(manifest["pairs"][0]["pair_label"]),
        "homo_left_eval": right_eval,
        "homo_right_eval": HOMO_RERUN_ROOT.resolve(),
        "tamper_root": right_eval,
    }


def _row_with_runtime(
    base: Dict[str, Any],
    homo_metrics: Dict[str, Any],
    hetero_metrics: Dict[str, Any],
    tamper_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    row = dict(base)
    row.update(
        {
            "honest_homo_thc_fpr": homo_metrics["thc_fpr"],
            "honest_homo_tstc_fpr": homo_metrics["tstc_fpr"],
            "honest_homo_thc_runtime_ms_per_trace": round((float(homo_metrics["thc_runtime_sec"]) * 1000.0) / homo_metrics["prompt_count"], 6),
            "honest_homo_tstc_runtime_ms_per_trace": round((float(homo_metrics["tstc_runtime_sec"]) * 1000.0) / homo_metrics["prompt_count"], 6),
            "honest_hetero_thc_fpr": hetero_metrics["thc_fpr"],
            "honest_hetero_tstc_fpr": hetero_metrics["tstc_fpr"],
            "honest_hetero_thc_runtime_ms_per_trace": round((float(hetero_metrics["thc_runtime_sec"]) * 1000.0) / hetero_metrics["prompt_count"], 6),
            "honest_hetero_tstc_runtime_ms_per_trace": round((float(hetero_metrics["tstc_runtime_sec"]) * 1000.0) / hetero_metrics["prompt_count"], 6),
            "tamper_thc_tpr": tamper_metrics["thc_tpr"],
            "tamper_tstc_tpr": tamper_metrics["tstc_tpr"],
            "tamper_thc_locacc": tamper_metrics["thc_localization_acc"],
            "tamper_tstc_locacc": tamper_metrics["tstc_localization_acc"],
            "tamper_thc_runtime_ms_per_trace": round((float(tamper_metrics["thc_runtime_sec_tamper"]) * 1000.0) / tamper_metrics["prompt_count_tamper"], 6),
            "tamper_tstc_runtime_ms_per_trace": round((float(tamper_metrics["tstc_runtime_sec_tamper"]) * 1000.0) / tamper_metrics["prompt_count_tamper"], 6),
            "honest_hetero_dominant_tstc_mismatch_checkpoint": hetero_metrics["tstc_dominant_mismatch_checkpoint"],
        }
    )
    return row


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    context = _load_context()
    config = _load_json(context["config_path"])
    prompt_map = _prompt_map(config, split="evaluation")
    checkpoints = checkpoint_order(config)
    baseline_delta_map = _load_json(context["baseline_delta_map_path"])["delta_map"]
    global_delta_map = _globalize_delta_map(baseline_delta_map)

    sample_rows: List[Dict[str, Any]] = []
    percentile_rows: List[Dict[str, Any]] = []
    grid_rows: List[Dict[str, Any]] = []
    tolerance_rows: List[Dict[str, Any]] = []
    global_rows: List[Dict[str, Any]] = []
    runtime_rows: List[Dict[str, Any]] = []

    for percentile in PERCENTILES:
        checkpoint_delta_map, checkpoint_delta_lookup = _calibrate_percentile([context["left_calib"], context["right_calib"]], percentile)
        delta_variants = (
            ("checkpoint_specific", checkpoint_delta_map, checkpoint_delta_lookup),
            (
                "global_shared",
                _globalize_delta_map(checkpoint_delta_map),
                {
                    "prefill_C1": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                    "prefill_C2": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                    "prefill_C3": max(checkpoint_delta_lookup.values()) if checkpoint_delta_lookup else 0.0,
                },
            ),
        )
        for mode, delta_map, delta_lookup in delta_variants:
            tstc_cfg = _build_hash_cfg(delta_map, FIXED_SAMPLE_SIZE)
            homo_metrics = _pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
            hetero_metrics = _pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
            tamper_metrics = _tamper_metrics(
                config,
                context["tamper_root"],
                prompt_map,
                {
                    "seed_base": 2026,
                    "delta_map": delta_map,
                    "prefill_token_samples": 1,
                    "prefill_channel_samples": FIXED_SAMPLE_SIZE,
                    "decode_channel_samples": 1,
                },
            )
            percentile_rows.append(
                _row_with_runtime(
                    {
                        "percentile": percentile,
                        "sample_size": FIXED_SAMPLE_SIZE,
                        "token_samples": 1,
                        "channel_samples": FIXED_SAMPLE_SIZE,
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

    for token_samples, channel_samples in SAMPLING_GRID:
        tstc_cfg = _build_hash_cfg_grid(baseline_delta_map, token_samples, channel_samples)
        homo_metrics = _pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        hetero_metrics = _pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        tamper_metrics = _tamper_metrics(
            config,
            context["tamper_root"],
            prompt_map,
            {
                "seed_base": 2026,
                "delta_map": baseline_delta_map,
                "prefill_token_samples": token_samples,
                "prefill_channel_samples": channel_samples,
                "decode_channel_samples": 1,
            },
        )
        grid_rows.append(
            _row_with_runtime(
                {
                    "sample_size": token_samples * channel_samples,
                    "token_samples": token_samples,
                    "channel_samples": channel_samples,
                    "tolerance_mode": "checkpoint_specific",
                    "tolerance_scale": 1.0,
                },
                homo_metrics,
                hetero_metrics,
                tamper_metrics,
            )
        )

    for sample_size in SAMPLE_SIZES:
        tstc_cfg = _build_hash_cfg(baseline_delta_map, sample_size)
        homo_metrics = _pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        hetero_metrics = _pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        tamper_metrics = _tamper_metrics(
            config,
            context["tamper_root"],
            prompt_map,
            {
                "seed_base": 2026,
                "delta_map": baseline_delta_map,
                "prefill_token_samples": 1,
                "prefill_channel_samples": sample_size,
                "decode_channel_samples": 1,
            },
        )
        row = _row_with_runtime(
            {
                "sample_size": sample_size,
                "token_samples": 1,
                "channel_samples": sample_size,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": 1.0,
            },
            homo_metrics,
            hetero_metrics,
            tamper_metrics,
        )
        sample_rows.append(row)
        runtime_rows.append(
            {
                "study": "sample_size_sweep",
                "sample_size": sample_size,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": 1.0,
                "honest_homo_thc_runtime_ms_per_trace": row["honest_homo_thc_runtime_ms_per_trace"],
                "honest_homo_tstc_runtime_ms_per_trace": row["honest_homo_tstc_runtime_ms_per_trace"],
                "honest_hetero_thc_runtime_ms_per_trace": row["honest_hetero_thc_runtime_ms_per_trace"],
                "honest_hetero_tstc_runtime_ms_per_trace": row["honest_hetero_tstc_runtime_ms_per_trace"],
                "tamper_thc_runtime_ms_per_trace": row["tamper_thc_runtime_ms_per_trace"],
                "tamper_tstc_runtime_ms_per_trace": row["tamper_tstc_runtime_ms_per_trace"],
            }
        )

    for scale in TOLERANCE_SCALES:
        scaled_delta = _scale_delta_map(baseline_delta_map, scale)
        tstc_cfg = _build_hash_cfg(scaled_delta, FIXED_SAMPLE_SIZE)
        homo_metrics = _pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        hetero_metrics = _pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        tamper_metrics = _tamper_metrics(
            config,
            context["tamper_root"],
            prompt_map,
            {
                "seed_base": 2026,
                "delta_map": scaled_delta,
                "prefill_token_samples": 1,
                "prefill_channel_samples": FIXED_SAMPLE_SIZE,
                "decode_channel_samples": 1,
            },
        )
        row = _row_with_runtime(
            {
                "sample_size": FIXED_SAMPLE_SIZE,
                "token_samples": 1,
                "channel_samples": FIXED_SAMPLE_SIZE,
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
                "sample_size": FIXED_SAMPLE_SIZE,
                "tolerance_mode": "checkpoint_specific",
                "tolerance_scale": scale,
                "honest_homo_thc_runtime_ms_per_trace": row["honest_homo_thc_runtime_ms_per_trace"],
                "honest_homo_tstc_runtime_ms_per_trace": row["honest_homo_tstc_runtime_ms_per_trace"],
                "honest_hetero_thc_runtime_ms_per_trace": row["honest_hetero_thc_runtime_ms_per_trace"],
                "honest_hetero_tstc_runtime_ms_per_trace": row["honest_hetero_tstc_runtime_ms_per_trace"],
                "tamper_thc_runtime_ms_per_trace": row["tamper_thc_runtime_ms_per_trace"],
                "tamper_tstc_runtime_ms_per_trace": row["tamper_tstc_runtime_ms_per_trace"],
            }
        )

    for mode, active_delta in (
        ("checkpoint_specific", baseline_delta_map),
        ("global_shared", global_delta_map),
    ):
        tstc_cfg = _build_hash_cfg(active_delta, FIXED_SAMPLE_SIZE)
        homo_metrics = _pair_fpr(context["homo_left_eval"], context["homo_right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        hetero_metrics = _pair_fpr(context["left_eval"], context["right_eval"], checkpoints, TARGET_STAGE, _thc_cfg(), tstc_cfg)
        tamper_metrics = _tamper_metrics(
            config,
            context["tamper_root"],
            prompt_map,
            {
                "seed_base": 2026,
                "delta_map": active_delta,
                "prefill_token_samples": 1,
                "prefill_channel_samples": FIXED_SAMPLE_SIZE,
                "decode_channel_samples": 1,
            },
        )
        row = _row_with_runtime(
            {
                "sample_size": FIXED_SAMPLE_SIZE,
                "token_samples": 1,
                "channel_samples": FIXED_SAMPLE_SIZE,
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
                "sample_size": FIXED_SAMPLE_SIZE,
                "tolerance_mode": mode,
                "tolerance_scale": 1.0,
                "honest_homo_thc_runtime_ms_per_trace": row["honest_homo_thc_runtime_ms_per_trace"],
                "honest_homo_tstc_runtime_ms_per_trace": row["honest_homo_tstc_runtime_ms_per_trace"],
                "honest_hetero_thc_runtime_ms_per_trace": row["honest_hetero_thc_runtime_ms_per_trace"],
                "honest_hetero_tstc_runtime_ms_per_trace": row["honest_hetero_tstc_runtime_ms_per_trace"],
                "tamper_thc_runtime_ms_per_trace": row["tamper_thc_runtime_ms_per_trace"],
                "tamper_tstc_runtime_ms_per_trace": row["tamper_tstc_runtime_ms_per_trace"],
            }
        )

    sample_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_samplesweep.csv"
    percentile_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_percentilesweep.csv"
    grid_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_sampling_grid.csv"
    tol_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_tolerancesweep.csv"
    global_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_global_vs_checkpoint_delta.csv"
    runtime_csv = TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_runtime.csv"

    common_fields = [
        "sample_size",
        "token_samples",
        "channel_samples",
        "tolerance_mode",
        "tolerance_scale",
        "honest_homo_thc_fpr",
        "honest_homo_tstc_fpr",
        "honest_homo_thc_runtime_ms_per_trace",
        "honest_homo_tstc_runtime_ms_per_trace",
        "honest_hetero_thc_fpr",
        "honest_hetero_tstc_fpr",
        "honest_hetero_thc_runtime_ms_per_trace",
        "honest_hetero_tstc_runtime_ms_per_trace",
        "honest_hetero_dominant_tstc_mismatch_checkpoint",
        "tamper_thc_tpr",
        "tamper_tstc_tpr",
        "tamper_thc_locacc",
        "tamper_tstc_locacc",
        "tamper_thc_runtime_ms_per_trace",
        "tamper_tstc_runtime_ms_per_trace",
        "prefill_delta_c1",
        "prefill_delta_c2",
        "prefill_delta_c3",
    ]

    _write_csv(sample_csv, sample_rows, common_fields)
    _write_csv(
        percentile_csv,
        percentile_rows,
        ["percentile"] + common_fields,
    )
    _write_csv(grid_csv, grid_rows, common_fields)
    _write_csv(tol_csv, tolerance_rows, common_fields)
    _write_csv(global_csv, global_rows, common_fields)
    _write_csv(
        runtime_csv,
        runtime_rows,
        [
            "study",
            "sample_size",
            "tolerance_mode",
            "tolerance_scale",
            "honest_homo_thc_runtime_ms_per_trace",
            "honest_homo_tstc_runtime_ms_per_trace",
            "honest_hetero_thc_runtime_ms_per_trace",
            "honest_hetero_tstc_runtime_ms_per_trace",
            "tamper_thc_runtime_ms_per_trace",
            "tamper_tstc_runtime_ms_per_trace",
        ],
    )

    run_notes = NOTE_DIR / "e2_strict_run_notes.md"
    interpretation_notes = NOTE_DIR / "e2_strict_interpretation_notes.md"
    run_notes.write_text(
        "\n".join(
            [
                "# E2 Strict Run Notes",
                "",
                f"- Heterogeneous anchor pair: `{context['pair_label']}`",
                f"- Heterogeneous left eval root: `{context['left_eval']}`",
                f"- Heterogeneous right eval root: `{context['right_eval']}`",
                f"- Homogeneous left eval root: `{context['homo_left_eval']}`",
                f"- Homogeneous right eval root: `{context['homo_right_eval']}`",
                f"- Baseline delta map: `{context['baseline_delta_map_path']}`",
                f"- Fixed sample size for tolerance/global sweeps: `{FIXED_SAMPLE_SIZE}`",
                "- Sample size is implemented as `token_samples=1` and `channel_samples=sample_size`.",
                f"- Percentile sweep: `{PERCENTILES}`",
                f"- 2D sampling grid: `{SAMPLING_GRID}`",
            ]
        ),
        encoding="utf-8",
    )
    interpretation_notes.write_text(
        "\n".join(
            [
                "# E2 Strict Interpretation Notes",
                "",
                "- `honest_homo_*_fpr` reports same-stack repeated execution mismatch rate.",
                "- `honest_hetero_*_fpr` reports strict E1 A-vs-B real heterogeneous mismatch rate.",
                "- `tamper_*` metrics are computed on held-out evaluation traces with injected tamper.",
                "- This strict E2 is designed to answer the manual's questions about sample size, tolerance scale, and global-vs-checkpoint tolerance on top of strict E1 traces.",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Wrote strict E2 tables to {TABLE_DIR}")


if __name__ == "__main__":
    main()
