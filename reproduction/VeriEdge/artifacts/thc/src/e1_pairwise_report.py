from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from checkpoint_qwen import (
    checkpoint_order,
    load_capture_bundle_for_prompt,
    ordered_stage_keys,
    stage_decode_step,
    stage_family,
)
from hash_chain import HashConfig, compute_hash_chain, first_mismatch_index


DETAIL_COLUMNS = [
    "pair_label",
    "prompt_id",
    "stage",
    "stage_key",
    "decode_step",
    "left_capture_root",
    "right_capture_root",
    "left_runtime",
    "right_runtime",
    "thc_detected",
    "thc_first_mismatch_index",
    "thc_first_mismatch_checkpoint",
    "tstc_detected",
    "tstc_first_mismatch_index",
    "tstc_first_mismatch_checkpoint",
    "localization_label",
]

SUMMARY_COLUMNS = [
    "pair_label",
    "stage",
    "prompt_count",
    "thc_fpr",
    "tstc_fpr",
    "thc_detect_count",
    "tstc_detect_count",
    "thc_dominant_mismatch_checkpoint",
    "tstc_dominant_mismatch_checkpoint",
    "thc_mismatch_distribution",
    "tstc_mismatch_distribution",
    "left_capture_root",
    "right_capture_root",
    "notes",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build E1 pairwise honest-honest verifier tables from capture roots")
    parser.add_argument("--config", required=True, help="Path to qwen config JSON/YAML-compatible file")
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="Pair spec in the form pair_label::left_capture_root::right_capture_root",
    )
    parser.add_argument(
        "--pairs-file",
        default="",
        help="Optional JSON file containing [{'pair_label': ..., 'left_capture_root': ..., 'right_capture_root': ...}]",
    )
    parser.add_argument(
        "--delta-map-file",
        default="",
        help="Optional delta_map.json; overrides tstc.delta_map in config",
    )
    parser.add_argument(
        "--stage-family",
        default="prefill",
        choices=["prefill", "decode", "all"],
        help="Which stage family to include in the report",
    )
    parser.add_argument("--prompt-id", action="append", default=[], help="Optional prompt id filter")
    parser.add_argument("--owner", default="shared", help="Owner suffix in output filenames")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output dir; default is paper1_veriedge/E1/logs/<date>_<owner>",
    )
    return parser.parse_args()


def _load_structured(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml  # type: ignore

        return dict(yaml.safe_load(text))


def _apply_delta_map_file(config: Dict[str, Any], delta_map_file: str) -> Dict[str, Any]:
    if not str(delta_map_file).strip():
        return config
    payload = _load_structured(Path(delta_map_file).expanduser().resolve())
    updated = dict(config)
    tstc_cfg = dict(updated.get("tstc", {}))
    tstc_cfg["delta_map"] = dict(payload.get("delta_map", {}))
    updated["tstc"] = tstc_cfg
    return updated


def _tstc_cfg(config: Dict[str, Any]) -> HashConfig:
    tstc_cfg = dict(config.get("tstc", {}))
    prefill_cfg = dict(tstc_cfg.get("prefill", {}).get("default", {}))
    decode_cfg = dict(tstc_cfg.get("decode", {}).get("default", {}))
    return HashConfig(
        mode="tstc",
        seed_base=int(tstc_cfg.get("seed_base", 2026)),
        delta_map=dict(tstc_cfg.get("delta_map", {})),
        prefill_token_samples=int(prefill_cfg.get("token_samples", 4)),
        prefill_channel_samples=int(prefill_cfg.get("channel_samples", 16)),
        decode_channel_samples=int(decode_cfg.get("channel_samples", 32)),
    )


def _parse_pair_specs(raw_specs: Sequence[str], pairs_file: str) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []
    for raw in raw_specs:
        parts = raw.split("::")
        if len(parts) != 3:
            raise ValueError(f"invalid --pair spec: {raw}")
        pair_label, left_root, right_root = [part.strip() for part in parts]
        if not pair_label or not left_root or not right_root:
            raise ValueError(f"invalid --pair spec: {raw}")
        pairs.append(
            {
                "pair_label": pair_label,
                "left_capture_root": left_root,
                "right_capture_root": right_root,
            }
        )

    if pairs_file:
        payload = _load_structured(Path(pairs_file).expanduser().resolve())
        raw_pairs = payload.get("pairs", payload if isinstance(payload, list) else [])
        if not isinstance(raw_pairs, list):
            raise ValueError("pairs-file must be a JSON array or an object with key 'pairs'")
        for row in raw_pairs:
            if not isinstance(row, Mapping):
                raise ValueError(f"invalid pair row in pairs-file: {row!r}")
            pair_label = str(row.get("pair_label", "")).strip()
            left_root = str(row.get("left_capture_root", "")).strip()
            right_root = str(row.get("right_capture_root", "")).strip()
            if not pair_label or not left_root or not right_root:
                raise ValueError(f"invalid pair row in pairs-file: {row!r}")
            pairs.append(
                {
                    "pair_label": pair_label,
                    "left_capture_root": left_root,
                    "right_capture_root": right_root,
                }
            )

    if not pairs:
        raise ValueError("at least one pair must be provided via --pair or --pairs-file")
    return pairs


def _prompt_ids(capture_root: Path) -> List[str]:
    capture_dir = capture_root / "captures"
    if not capture_dir.exists():
        raise ValueError(f"capture directory not found: {capture_dir}")
    return sorted(path.stem for path in capture_dir.glob("*.npz"))


def _shared_prompt_ids(left_root: Path, right_root: Path, requested: Sequence[str]) -> List[str]:
    left_ids = set(_prompt_ids(left_root))
    right_ids = set(_prompt_ids(right_root))
    shared = sorted(left_ids & right_ids)
    if requested:
        wanted = {str(value) for value in requested}
        shared = [value for value in shared if value in wanted]
    if not shared:
        raise ValueError(
            f"no shared prompt ids between {left_root} and {right_root}"
        )
    return shared


def _selected_stage_keys(
    left_bundle: Mapping[str, Mapping[str, Any]],
    right_bundle: Mapping[str, Mapping[str, Any]],
    stage_filter: str,
) -> List[str]:
    left_keys = set(left_bundle.keys())
    right_keys = set(right_bundle.keys())
    if left_keys != right_keys:
        raise ValueError(f"stage key mismatch: left={sorted(left_keys)} right={sorted(right_keys)}")

    stage_keys = ordered_stage_keys(left_keys)
    if stage_filter == "all":
        return stage_keys
    return [key for key in stage_keys if stage_family(key) == stage_filter]


def _validate_checkpoint_layout(
    left_stage: Mapping[str, Any],
    right_stage: Mapping[str, Any],
    expected_order: Sequence[str],
) -> List[str]:
    left_keys = set(left_stage.keys())
    right_keys = set(right_stage.keys())
    if left_keys != right_keys:
        raise ValueError(f"checkpoint mismatch: left={sorted(left_keys)} right={sorted(right_keys)}")
    missing = [checkpoint for checkpoint in expected_order if checkpoint not in left_keys]
    if missing:
        raise ValueError(f"missing checkpoints for paired comparison: {missing}")
    return [checkpoint for checkpoint in expected_order if checkpoint in left_keys]


def _compare_chain(
    left_stage: Mapping[str, Any],
    right_stage: Mapping[str, Any],
    stage_name: str,
    checkpoint_names: Sequence[str],
    cfg: HashConfig,
) -> Dict[str, Any]:
    left_chain = compute_hash_chain(left_stage, checkpoint_names, stage_name, cfg)
    right_chain = compute_hash_chain(right_stage, checkpoint_names, stage_name, cfg)
    mismatch = first_mismatch_index(left_chain, right_chain)
    return {
        "detected": mismatch is not None,
        "first_mismatch_index": int(mismatch) if mismatch is not None else -1,
        "first_mismatch_checkpoint": checkpoint_names[mismatch] if mismatch is not None else "",
    }


def _write_csv(rows: Iterable[Dict[str, Any]], columns: Sequence[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _dominant_checkpoint(counter: Counter[str]) -> str:
    items = [(key, value) for key, value in counter.items() if key]
    if not items:
        return ""
    items.sort(key=lambda item: (-item[1], item[0]))
    return items[0][0]


def _json_counter(counter: Counter[str]) -> str:
    payload = {key: counter[key] for key in sorted(counter) if key}
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _build_summary_rows(detail_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        grouped[(str(row["pair_label"]), str(row["stage"]))].append(dict(row))

    summary_rows: List[Dict[str, Any]] = []
    for (pair_label, stage_name), bucket in sorted(grouped.items()):
        prompt_count = len(bucket)
        thc_counter = Counter(
            str(row["thc_first_mismatch_checkpoint"])
            for row in bucket
            if str(row["thc_first_mismatch_checkpoint"]).strip()
        )
        tstc_counter = Counter(
            str(row["tstc_first_mismatch_checkpoint"])
            for row in bucket
            if str(row["tstc_first_mismatch_checkpoint"]).strip()
        )
        thc_detect_count = sum(1 for row in bucket if str(row["thc_detected"]).lower() == "true")
        tstc_detect_count = sum(1 for row in bucket if str(row["tstc_detected"]).lower() == "true")
        sample_row = bucket[0]
        summary_rows.append(
            {
                "pair_label": pair_label,
                "stage": stage_name,
                "prompt_count": prompt_count,
                "thc_fpr": round(thc_detect_count / prompt_count, 6),
                "tstc_fpr": round(tstc_detect_count / prompt_count, 6),
                "thc_detect_count": thc_detect_count,
                "tstc_detect_count": tstc_detect_count,
                "thc_dominant_mismatch_checkpoint": _dominant_checkpoint(thc_counter),
                "tstc_dominant_mismatch_checkpoint": _dominant_checkpoint(tstc_counter),
                "thc_mismatch_distribution": _json_counter(thc_counter),
                "tstc_mismatch_distribution": _json_counter(tstc_counter),
                "left_capture_root": sample_row["left_capture_root"],
                "right_capture_root": sample_row["right_capture_root"],
                "notes": "honest-honest paired capture; localization is N/A",
            }
        )
    return summary_rows


def main() -> None:
    args = _parse_args()
    config = _apply_delta_map_file(_load_structured(Path(args.config).expanduser().resolve()), args.delta_map_file)
    expected_checkpoints = checkpoint_order(config)
    thc_cfg = HashConfig(mode="thc")
    tstc_cfg = _tstc_cfg(config)
    pair_specs = _parse_pair_specs(args.pair, args.pairs_file)

    detail_rows: List[Dict[str, Any]] = []
    for pair in pair_specs:
        pair_label = str(pair["pair_label"])
        left_root = Path(str(pair["left_capture_root"])).expanduser().resolve()
        right_root = Path(str(pair["right_capture_root"])).expanduser().resolve()
        prompt_ids = _shared_prompt_ids(left_root, right_root, args.prompt_id)

        for prompt_id in prompt_ids:
            left_bundle, _, left_runtime = load_capture_bundle_for_prompt(left_root, prompt_id)
            right_bundle, _, right_runtime = load_capture_bundle_for_prompt(right_root, prompt_id)
            stage_keys = _selected_stage_keys(left_bundle, right_bundle, args.stage_family)
            if not stage_keys:
                raise ValueError(f"no stage keys matched stage-family={args.stage_family} for prompt_id={prompt_id}")

            for stage_key in stage_keys:
                stage_name = stage_family(stage_key)
                checkpoint_names = _validate_checkpoint_layout(
                    left_bundle[stage_key],
                    right_bundle[stage_key],
                    expected_checkpoints,
                )
                thc = _compare_chain(left_bundle[stage_key], right_bundle[stage_key], stage_name, checkpoint_names, thc_cfg)
                tstc = _compare_chain(left_bundle[stage_key], right_bundle[stage_key], stage_name, checkpoint_names, tstc_cfg)
                detail_rows.append(
                    {
                        "pair_label": pair_label,
                        "prompt_id": prompt_id,
                        "stage": stage_name,
                        "stage_key": stage_key,
                        "decode_step": stage_decode_step(stage_key),
                        "left_capture_root": str(left_root),
                        "right_capture_root": str(right_root),
                        "left_runtime": left_runtime,
                        "right_runtime": right_runtime,
                        "thc_detected": bool(thc["detected"]),
                        "thc_first_mismatch_index": int(thc["first_mismatch_index"]),
                        "thc_first_mismatch_checkpoint": str(thc["first_mismatch_checkpoint"]),
                        "tstc_detected": bool(tstc["detected"]),
                        "tstc_first_mismatch_index": int(tstc["first_mismatch_index"]),
                        "tstc_first_mismatch_checkpoint": str(tstc["first_mismatch_checkpoint"]),
                        "localization_label": "N/A",
                    }
                )

    if not detail_rows:
        raise ValueError("no pairwise rows were generated")

    summary_rows = _build_summary_rows(detail_rows)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else (Path("paper1_veriedge/E1/logs") / f"{stamp}_{args.owner}").expanduser().resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / f"exp_e1_{stamp}_{args.owner}_pairwise_details.csv"
    summary_path = output_dir / f"exp_e1_{stamp}_{args.owner}_summary.csv"
    manifest_path = output_dir / f"exp_e1_{stamp}_{args.owner}_manifest.json"

    _write_csv(detail_rows, DETAIL_COLUMNS, detail_path)
    _write_csv(summary_rows, SUMMARY_COLUMNS, summary_path)
    manifest_path.write_text(
        json.dumps(
            {
                "owner": args.owner,
                "stage_family": args.stage_family,
                "pair_count": len(pair_specs),
                "prompt_filter": list(args.prompt_id),
                "pairs": pair_specs,
                "config": str(Path(args.config).expanduser().resolve()),
                "delta_map_file": str(Path(args.delta_map_file).expanduser().resolve()) if args.delta_map_file else "",
                "detail_csv": str(detail_path),
                "summary_csv": str(summary_path),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    print(f"Wrote E1 pairwise report to {output_dir}")


if __name__ == "__main__":
    main()
