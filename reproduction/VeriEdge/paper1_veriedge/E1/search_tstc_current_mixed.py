from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from checkpoint_qwen import checkpoint_order, load_capture_bundle_for_prompt, ordered_stage_keys, stage_family
from e1_pairwise_report import _compare_chain, _shared_prompt_ids, _validate_checkpoint_layout
from hash_chain import HashConfig


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_delta_map(calib_left: Path, calib_right: Path, percentile: float) -> dict[str, dict[str, float]]:
    import numpy as np

    left_ids = sorted(set(p.stem for p in (calib_left / "captures").glob("*.npz")))
    right_ids = sorted(set(p.stem for p in (calib_right / "captures").glob("*.npz")))
    shared = sorted(set(left_ids) & set(right_ids))
    if not shared:
        raise ValueError("no shared calibration prompt ids")

    grouped: dict[tuple[str, str], list[Any]] = {}
    for prompt_id in shared:
        left_bundle, _, _ = load_capture_bundle_for_prompt(calib_left, prompt_id)
        right_bundle, _, _ = load_capture_bundle_for_prompt(calib_right, prompt_id)
        for stage_key in ordered_stage_keys(set(left_bundle.keys()) & set(right_bundle.keys())):
            stage = stage_family(stage_key)
            for checkpoint in sorted(set(left_bundle[stage_key].keys()) & set(right_bundle[stage_key].keys())):
                left = left_bundle[stage_key][checkpoint].reshape(-1)
                right = right_bundle[stage_key][checkpoint].reshape(-1)
                diff = np.abs(left.astype("float32") - right.astype("float32"))
                grouped.setdefault((stage, checkpoint), []).append(diff)

    delta_map: dict[str, dict[str, float]] = {"prefill": {}, "decode": {}}
    for (stage, checkpoint), chunks in grouped.items():
        import numpy as np

        values = np.concatenate(chunks, axis=0).astype("float32")
        delta_map[stage][checkpoint] = float(np.percentile(values, percentile)) if values.size else 0.0
    return delta_map


def _score(
    eval_left: Path,
    eval_right: Path,
    checkpoints: list[str],
    token_samples: int,
    channel_samples: int,
    percentile: float,
    delta_map: dict[str, dict[str, float]],
) -> dict[str, Any]:
    prompt_ids = _shared_prompt_ids(eval_left, eval_right, [])
    cfg = HashConfig(
        mode="tstc",
        seed_base=2026,
        delta_map=delta_map,
        prefill_token_samples=token_samples,
        prefill_channel_samples=channel_samples,
        decode_channel_samples=32,
    )
    detect_count = 0
    mismatch_counter: Counter[str] = Counter()
    for prompt_id in prompt_ids:
        left_bundle, _, _ = load_capture_bundle_for_prompt(eval_left, prompt_id)
        right_bundle, _, _ = load_capture_bundle_for_prompt(eval_right, prompt_id)
        stage_keys = ordered_stage_keys(set(left_bundle.keys()) & set(right_bundle.keys()))
        stage_key = stage_keys[0]
        checkpoint_names = _validate_checkpoint_layout(left_bundle[stage_key], right_bundle[stage_key], checkpoints)
        tstc = _compare_chain(left_bundle[stage_key], right_bundle[stage_key], "prefill", checkpoint_names, cfg)
        if bool(tstc["detected"]):
            detect_count += 1
            checkpoint = str(tstc["first_mismatch_checkpoint"])
            if checkpoint:
                mismatch_counter[checkpoint] += 1
    prompt_count = len(prompt_ids)
    return {
        "percentile": percentile,
        "token_samples": token_samples,
        "channel_samples": channel_samples,
        "prompt_count": prompt_count,
        "detect_count": detect_count,
        "tstc_fpr": round(detect_count / prompt_count, 6),
        "dominant_mismatch_checkpoint": mismatch_counter.most_common(1)[0][0] if mismatch_counter else "",
        "mismatch_distribution": json.dumps(dict(sorted(mismatch_counter.items())), ensure_ascii=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Search TSTC parameters on the current mixed-stack 200-prompt captures")
    parser.add_argument("--output-csv", default=str(REPO_ROOT / "paper1_veriedge" / "E1" / "tables" / "current_mixed_tstc_search.csv"))
    args = parser.parse_args()

    config = _load_json(REPO_ROOT / "artifacts" / "thc" / "config" / "e1_real_qwen_tstc_prefill_1x1_40_200.json")
    checkpoints = checkpoint_order(config)

    calib_left = REPO_ROOT / "workspace" / "captures" / "E1" / "t4_final_current_mixed_40_200_left_calib"
    calib_right = REPO_ROOT / "workspace" / "captures" / "E1" / "t4_final_current_mixed_40_200_right_calib"
    eval_left = REPO_ROOT / "workspace" / "captures" / "E1" / "t4_final_current_mixed_40_200_left_eval"
    eval_right = REPO_ROOT / "workspace" / "captures" / "E1" / "t4_final_current_mixed_40_200_right_eval"

    percentiles = [99.0, 99.5, 99.9, 99.95, 99.99]
    token_grid = [1, 2, 4, 8]
    channel_grid = [1, 2, 4, 8, 16, 32]

    rows: list[dict[str, Any]] = []
    delta_cache: dict[float, dict[str, dict[str, float]]] = {}
    for percentile in percentiles:
        delta_cache[percentile] = _build_delta_map(calib_left, calib_right, percentile)
        for token_samples in token_grid:
            for channel_samples in channel_grid:
                rows.append(
                    _score(
                        eval_left,
                        eval_right,
                        checkpoints,
                        token_samples,
                        channel_samples,
                        percentile,
                        delta_cache[percentile],
                    )
                )

    rows.sort(key=lambda row: (float(row["tstc_fpr"]), int(row["token_samples"]) * int(row["channel_samples"]), -float(row["percentile"])))

    output_path = Path(args.output_csv).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "percentile",
                "token_samples",
                "channel_samples",
                "prompt_count",
                "detect_count",
                "tstc_fpr",
                "dominant_mismatch_checkpoint",
                "mismatch_distribution",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote search results to {output_path}")
    print("Top 10:")
    for row in rows[:10]:
        print(row)


if __name__ == "__main__":
    main()
