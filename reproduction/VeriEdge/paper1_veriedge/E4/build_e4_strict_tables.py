from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
import sys

if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from attack import inject_tamper  # type: ignore
from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, load_prompt_records, ordered_stage_keys, stage_family  # type: ignore
from hash_chain import HashConfig, compute_hash_chain, first_mismatch_index  # type: ignore


STAMP = time.strftime("%Y%m%d")
OWNER = "strict_ab_mainline"
RUN_ID = f"exp_e4_{STAMP}_{OWNER}"
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"
LOG_ROOT = E4_DIR / "logs" / RUN_ID
TABLE_DIR = E4_DIR / "tables"
NOTE_DIR = E4_DIR / "notes"

STRICT_PAIR_MANIFEST = (
    REPO_ROOT
    / "paper1_veriedge"
    / "E1"
    / "logs"
    / "t4strict_pair_a_vs_b_40_200"
    / "exp_e1_20260504_t4strict_pair_a_vs_b_40_200_manifest.json"
)
HOMO_RERUN_ROOT = (
    REPO_ROOT
    / "workspace"
    / "captures"
    / "E1"
    / "t4strict_stack_b_applebf16_applebf16_rtxfp32_40_200_eval_rerun"
)
GLOBAL_DELTA_FILE = (
    REPO_ROOT
    / "workspace"
    / "captures"
    / "E1"
    / "t4strict_pair_a_vs_b_40_200_delta"
    / "delta_map.global_shared.json"
)

SIZE_COLUMNS = [
    "prompt_id",
    "split",
    "trace_label",
    "scenario",
    "verifier",
    "reference_capture_file_bytes",
    "candidate_capture_file_bytes",
    "capture_pair_total_bytes",
    "metadata_bytes",
    "commitment_head_bytes",
    "commitment_chain_bytes",
    "verdict_bytes",
    "validator_storage_bytes_head_commitment",
    "validator_storage_bytes_full_chain",
]

LATENCY_COLUMNS = [
    "prompt_id",
    "split",
    "trace_label",
    "scenario",
    "verifier",
    "reference_capture_load_ms",
    "candidate_capture_load_ms",
    "commitment_generation_ms",
    "replay_ms",
    "compare_ms",
    "verdict_emission_ms",
    "challenge_latency_ms",
    "detected",
    "first_mismatch_stage",
    "first_mismatch_checkpoint",
    "verdict",
]

STORAGE_COLUMNS = [
    "prompt_id",
    "split",
    "trace_label",
    "scenario",
    "verifier",
    "component",
    "bytes",
]

SUMMARY_COLUMNS = [
    "trace_label",
    "scenario",
    "verifier",
    "sample_count",
    "mean_reference_capture_file_bytes",
    "mean_candidate_capture_file_bytes",
    "mean_capture_pair_total_bytes",
    "mean_commitment_head_bytes",
    "mean_commitment_chain_bytes",
    "mean_validator_storage_head_bytes",
    "mean_validator_storage_full_chain_bytes",
    "mean_replay_ms",
    "mean_compare_ms",
    "mean_verdict_emission_ms",
    "mean_challenge_latency_ms",
    "detection_rate",
]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: List[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _metadata_bytes(rows: Iterable[Dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        total += len((json.dumps(row, ensure_ascii=True) + "\n").encode("utf-8"))
    return total


def _trace_label(scenario: str) -> str:
    return {
        "honest_homo": "honest_trace",
        "honest_hetero": "challenged_trace",
        "tamper": "tamper_trace",
    }[scenario]


def _trial_index_for_prompt(prompt_id: str) -> int:
    digest = hashlib.sha256(prompt_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _load_capture_root(prompt_id: str, capture_root: Path) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], str, float, int]:
    start = time.perf_counter()
    bundle, metadata_rows, runtime = load_capture_bundle_for_prompt(capture_root, prompt_id)
    load_ms = (time.perf_counter() - start) * 1000.0
    npz_path = capture_root / "captures" / f"{prompt_id}.npz"
    capture_file_bytes = int(npz_path.stat().st_size)
    return bundle, metadata_rows, runtime, load_ms, capture_file_bytes


def _hash_config(mode: str, delta_map: Mapping[str, Any]) -> HashConfig:
    if mode == "thc":
        return HashConfig(mode="thc")
    return HashConfig(
        mode="tstc",
        seed_base=2026,
        delta_map=json.loads(json.dumps(delta_map, ensure_ascii=True)),
        prefill_token_samples=1,
        prefill_channel_samples=1,
        decode_channel_samples=1,
    )


def _compute_stage_chains(bundle: Dict[str, Dict[str, Any]], checkpoints: Sequence[str], cfg: HashConfig) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for stage_key in ordered_stage_keys(bundle.keys()):
        out[stage_key] = compute_hash_chain(bundle[stage_key], checkpoints, stage_family(stage_key), cfg)
    return out


def _chain_sizes(chains: Mapping[str, Sequence[str]]) -> Tuple[int, int]:
    total_chain_bytes = 0
    total_head_bytes = 0
    for chain in chains.values():
        if not chain:
            continue
        total_chain_bytes += sum(len(bytes.fromhex(value)) for value in chain)
        total_head_bytes += len(bytes.fromhex(chain[-1]))
    return total_chain_bytes, total_head_bytes


def _first_mismatch(reference: Mapping[str, Sequence[str]], candidate: Mapping[str, Sequence[str]], checkpoints: Sequence[str]) -> Tuple[bool, str, str]:
    for stage_key in ordered_stage_keys(reference.keys()):
        mismatch = first_mismatch_index(reference.get(stage_key, []), candidate.get(stage_key, []))
        if mismatch is None:
            continue
        checkpoint = checkpoints[mismatch] if mismatch < len(checkpoints) else ""
        return True, stage_family(stage_key), checkpoint
    return False, "", ""


def _scenario_bundles(
    prompt_id: str,
    scenario: str,
    validator_root: Path,
    candidate_root: Path,
    tamper_cfg: Mapping[str, Any],
    base_seed: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]], float, int, List[Dict[str, Any]], float, int]:
    validator_bundle, validator_meta, _, validator_load_ms, validator_capture_bytes = _load_capture_root(prompt_id, validator_root)
    candidate_bundle, candidate_meta, _, candidate_load_ms, candidate_capture_bytes = _load_capture_root(prompt_id, candidate_root)
    if scenario == "tamper":
        candidate_bundle = inject_tamper(
            candidate_bundle,
            checkpoint=str(tamper_cfg.get("checkpoint", "C2")),
            strength=float(tamper_cfg.get("strength", 0.15)),
            seed=int(base_seed) + _trial_index_for_prompt(prompt_id) + 3000,
            relative_to_tensor_std=bool(tamper_cfg.get("relative_to_tensor_std", False)),
            min_std=float(tamper_cfg.get("min_std", 1e-6)),
        )
    return (
        validator_bundle,
        candidate_bundle,
        validator_meta,
        validator_load_ms,
        validator_capture_bytes,
        candidate_meta,
        candidate_load_ms,
        candidate_capture_bytes,
    )


def _measure_one(
    *,
    prompt_id: str,
    split: str,
    scenario: str,
    verifier: str,
    checkpoints: Sequence[str],
    delta_map: Mapping[str, Any],
    validator_root: Path,
    candidate_root: Path,
    tamper_cfg: Mapping[str, Any],
    base_seed: int,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    (
        validator_bundle,
        candidate_bundle,
        validator_meta,
        validator_load_ms,
        validator_capture_bytes,
        candidate_meta,
        candidate_load_ms,
        candidate_capture_bytes,
    ) = _scenario_bundles(prompt_id, scenario, validator_root, candidate_root, tamper_cfg, base_seed)

    hash_cfg = _hash_config(verifier, delta_map)

    commit_start = time.perf_counter()
    candidate_chains = _compute_stage_chains(candidate_bundle, checkpoints, hash_cfg)
    commitment_generation_ms = (time.perf_counter() - commit_start) * 1000.0

    replay_start = time.perf_counter()
    validator_chains = _compute_stage_chains(validator_bundle, checkpoints, hash_cfg)
    replay_ms = (time.perf_counter() - replay_start) * 1000.0

    compare_start = time.perf_counter()
    detected, first_stage, first_checkpoint = _first_mismatch(validator_chains, candidate_chains, checkpoints)
    compare_ms = (time.perf_counter() - compare_start) * 1000.0

    verdict = "challenge_upheld" if scenario == "tamper" and detected else "honest_execution"
    if scenario == "tamper" and not detected:
        verdict = "challenge_failed"
    if scenario != "tamper" and detected:
        verdict = "false_alarm"

    verdict_payload = {
        "prompt_id": prompt_id,
        "scenario": scenario,
        "trace_label": _trace_label(scenario),
        "verifier": verifier,
        "detected": bool(detected),
        "first_mismatch_stage": first_stage,
        "first_mismatch_checkpoint": first_checkpoint,
        "verdict": verdict,
    }
    verdict_start = time.perf_counter()
    verdict_bytes = len(json.dumps(verdict_payload, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    verdict_emission_ms = (time.perf_counter() - verdict_start) * 1000.0

    commitment_chain_bytes, commitment_head_bytes = _chain_sizes(candidate_chains)
    metadata_bytes = _metadata_bytes(validator_meta)
    storage_head_bytes = validator_capture_bytes + metadata_bytes + commitment_head_bytes + verdict_bytes
    storage_full_chain_bytes = validator_capture_bytes + metadata_bytes + commitment_chain_bytes + verdict_bytes

    common = {
        "prompt_id": prompt_id,
        "split": split,
        "trace_label": _trace_label(scenario),
        "scenario": scenario,
        "verifier": verifier,
    }

    size_row = {
        **common,
        "reference_capture_file_bytes": validator_capture_bytes,
        "candidate_capture_file_bytes": candidate_capture_bytes,
        "capture_pair_total_bytes": validator_capture_bytes + candidate_capture_bytes,
        "metadata_bytes": metadata_bytes,
        "commitment_head_bytes": commitment_head_bytes,
        "commitment_chain_bytes": commitment_chain_bytes,
        "verdict_bytes": verdict_bytes,
        "validator_storage_bytes_head_commitment": storage_head_bytes,
        "validator_storage_bytes_full_chain": storage_full_chain_bytes,
    }

    latency_row = {
        **common,
        "reference_capture_load_ms": round(validator_load_ms, 6),
        "candidate_capture_load_ms": round(candidate_load_ms, 6),
        "commitment_generation_ms": round(commitment_generation_ms, 6),
        "replay_ms": round(replay_ms, 6),
        "compare_ms": round(compare_ms, 6),
        "verdict_emission_ms": round(verdict_emission_ms, 6),
        "challenge_latency_ms": round(validator_load_ms + candidate_load_ms + commitment_generation_ms + replay_ms + compare_ms + verdict_emission_ms, 6),
        "detected": bool(detected),
        "first_mismatch_stage": first_stage,
        "first_mismatch_checkpoint": first_checkpoint,
        "verdict": verdict,
    }

    storage_rows = [
        {**common, "component": "reference_capture_file", "bytes": validator_capture_bytes},
        {**common, "component": "candidate_capture_file", "bytes": candidate_capture_bytes},
        {**common, "component": "metadata", "bytes": metadata_bytes},
        {**common, "component": "commitment_head", "bytes": commitment_head_bytes},
        {**common, "component": "commitment_chain", "bytes": commitment_chain_bytes},
        {**common, "component": "verdict_json", "bytes": verdict_bytes},
        {**common, "component": "validator_storage_head_commitment", "bytes": storage_head_bytes},
        {**common, "component": "validator_storage_full_chain", "bytes": storage_full_chain_bytes},
    ]
    return size_row, latency_row, storage_rows


def _summary(size_rows: List[Dict[str, Any]], latency_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lat_index = {(row["prompt_id"], row["scenario"], row["verifier"]): row for row in latency_rows}
    grouped: Dict[Tuple[str, str, str], List[Tuple[Dict[str, Any], Dict[str, Any]]]] = defaultdict(list)
    for size_row in size_rows:
        key = (str(size_row["trace_label"]), str(size_row["scenario"]), str(size_row["verifier"]))
        lat_row = lat_index[(size_row["prompt_id"], size_row["scenario"], size_row["verifier"])]
        grouped[key].append((size_row, lat_row))

    out: List[Dict[str, Any]] = []
    for (trace_label, scenario, verifier), bucket in sorted(grouped.items()):
        size_bucket = [pair[0] for pair in bucket]
        lat_bucket = [pair[1] for pair in bucket]
        sample_count = len(bucket)
        out.append(
            {
                "trace_label": trace_label,
                "scenario": scenario,
                "verifier": verifier,
                "sample_count": sample_count,
                "mean_reference_capture_file_bytes": round(sum(float(r["reference_capture_file_bytes"]) for r in size_bucket) / sample_count, 3),
                "mean_candidate_capture_file_bytes": round(sum(float(r["candidate_capture_file_bytes"]) for r in size_bucket) / sample_count, 3),
                "mean_capture_pair_total_bytes": round(sum(float(r["capture_pair_total_bytes"]) for r in size_bucket) / sample_count, 3),
                "mean_commitment_head_bytes": round(sum(float(r["commitment_head_bytes"]) for r in size_bucket) / sample_count, 3),
                "mean_commitment_chain_bytes": round(sum(float(r["commitment_chain_bytes"]) for r in size_bucket) / sample_count, 3),
                "mean_validator_storage_head_bytes": round(sum(float(r["validator_storage_bytes_head_commitment"]) for r in size_bucket) / sample_count, 3),
                "mean_validator_storage_full_chain_bytes": round(sum(float(r["validator_storage_bytes_full_chain"]) for r in size_bucket) / sample_count, 3),
                "mean_replay_ms": round(sum(float(r["replay_ms"]) for r in lat_bucket) / sample_count, 6),
                "mean_compare_ms": round(sum(float(r["compare_ms"]) for r in lat_bucket) / sample_count, 6),
                "mean_verdict_emission_ms": round(sum(float(r["verdict_emission_ms"]) for r in lat_bucket) / sample_count, 6),
                "mean_challenge_latency_ms": round(sum(float(r["challenge_latency_ms"]) for r in lat_bucket) / sample_count, 6),
                "detection_rate": round(sum(1.0 for r in lat_bucket if r["detected"]) / sample_count, 6),
            }
        )
    return out


def _run_mode(mode_name: str, delta_map: Mapping[str, Any], output_dir: Path) -> Tuple[Path, Path, Path, Path]:
    manifest = _read_json(STRICT_PAIR_MANIFEST)
    config = _read_json(Path(manifest["config"]))
    checkpoints = checkpoint_order(config)
    tamper_cfg = config.get("tamper", {})
    base_seed = int(config.get("experiment", {}).get("seed", 7))
    prompt_rows = load_prompt_records(config, split="evaluation")
    prompt_ids = [str(row["prompt_id"]) for row in prompt_rows]

    stack_a_root = Path(manifest["pairs"][0]["left_capture_root"]).resolve()
    stack_b_root = Path(manifest["pairs"][0]["right_capture_root"]).resolve()
    homo_root = HOMO_RERUN_ROOT.resolve()

    scenarios = [
        ("honest_homo", stack_b_root, homo_root),
        ("honest_hetero", stack_b_root, stack_a_root),
        ("tamper", stack_b_root, stack_b_root),
    ]
    verifiers = ["thc", "tstc"]

    size_rows: List[Dict[str, Any]] = []
    latency_rows: List[Dict[str, Any]] = []
    storage_rows: List[Dict[str, Any]] = []

    for prompt_id in prompt_ids:
        for scenario, validator_root, candidate_root in scenarios:
            for verifier in verifiers:
                size_row, latency_row, component_rows = _measure_one(
                    prompt_id=prompt_id,
                    split="evaluation",
                    scenario=scenario,
                    verifier=verifier,
                    checkpoints=checkpoints,
                    delta_map=delta_map,
                    validator_root=validator_root,
                    candidate_root=candidate_root,
                    tamper_cfg=tamper_cfg,
                    base_seed=base_seed,
                )
                size_rows.append(size_row)
                latency_rows.append(latency_row)
                storage_rows.extend(component_rows)

    summary_rows = _summary(size_rows, latency_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    size_csv = output_dir / f"{RUN_ID}_{mode_name}_size_breakdown.csv"
    latency_csv = output_dir / f"{RUN_ID}_{mode_name}_latency_breakdown.csv"
    storage_csv = output_dir / f"{RUN_ID}_{mode_name}_storage_breakdown.csv"
    summary_csv = output_dir / f"{RUN_ID}_{mode_name}_summary.csv"
    _write_csv(size_csv, size_rows, SIZE_COLUMNS)
    _write_csv(latency_csv, latency_rows, LATENCY_COLUMNS)
    _write_csv(storage_csv, storage_rows, STORAGE_COLUMNS)
    _write_csv(summary_csv, summary_rows, SUMMARY_COLUMNS)
    return size_csv, latency_csv, storage_csv, summary_csv


def main() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(STRICT_PAIR_MANIFEST)
    baseline_delta = _read_json(Path(str(manifest["delta_map_file"])).expanduser().resolve())["delta_map"]
    global_delta = _read_json(GLOBAL_DELTA_FILE)["delta_map"]

    baseline_dir = LOG_ROOT / "baseline_checkpoint_specific"
    global_dir = LOG_ROOT / "global_shared"
    baseline_files = _run_mode("baseline", baseline_delta, baseline_dir)
    global_files = _run_mode("global", global_delta, global_dir)

    notes = NOTE_DIR / "e4_overhead_notes.md"
    notes.write_text(
        "\n".join(
            [
                "# E4 Overhead Notes",
                "",
                "- Strict E4 uses strict E1 A/B traces as the challenged honest heterogeneous anchor.",
                "- `honest_trace` compares `Stack B eval` against the independently captured `Stack B eval rerun`.",
                "- `challenged_trace` compares `Stack B eval` against `Stack A eval` (real strict heterogeneous pair).",
                "- `tamper_trace` compares `Stack B eval` against a tampered version of `Stack B eval`.",
                "- `baseline_checkpoint_specific` uses the empirical strict A/B pair-specific delta map.",
                "- `global_shared` uses the stage-wise shared delta derived from the same strict A/B baseline map.",
                "- This experiment measures verifier operational overhead on real traces; it does not include EXO control-plane or online queueing overhead.",
                "",
                f"- Baseline outputs: {baseline_files}",
                f"- Global outputs: {global_files}",
            ]
        ),
        encoding="utf-8",
    )
    print(baseline_files[-1])
    print(global_files[-1])
    print(notes)


if __name__ == "__main__":
    main()
