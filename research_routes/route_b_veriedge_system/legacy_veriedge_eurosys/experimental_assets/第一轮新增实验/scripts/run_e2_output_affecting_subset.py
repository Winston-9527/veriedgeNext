from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
THC_SRC = REPO_ROOT / "artifacts" / "thc" / "src"
if str(THC_SRC) not in sys.path:
    sys.path.insert(0, str(THC_SRC))

from attack import inject_tamper  # type: ignore
from attack_material import inject_layer_skip, inject_scale_perturbation, inject_stale_replay, inject_wrong_prompt_checkpoint  # type: ignore
from checkpoint_qwen import load_capture_bundle_for_prompt  # type: ignore
from hetero_qwen_common import QwenShardRunner  # type: ignore

import build_e2_material_tamper_full_matrix as mat  # type: ignore
import build_e2_strict_tables as scalar  # type: ignore


RUN_ID = "exp_e2_20260512_output_affecting_subset"
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
REPORT_DIR = E2_DIR / "reports"

FOCUS_PAIR_IDS = ["t4strict_pair_a_vs_b_40_200", "t4strict_pair_b_vs_d_40_200"]
FOCUS_ATTACKS = [
    "gaussian",
    "cross_prompt_stale_substitution",
    "wrong_shard_output",
    "layer_skip",
    "scale_perturbation",
]
FOCUS_VARIANTS = ["scalar16", "projcos4"]
ATTACK_CHECKPOINT = "C2"
LAYER_SKIP_SOURCE_CHECKPOINT = "C1"
TOPK = 20
OUTPUT_TOPK_FOR_LABEL = 5


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _pair_context(pair_id: str) -> Dict[str, Any]:
    manifest_path = (
        REPO_ROOT
        / "paper1_veriedge"
        / "E1"
        / "logs"
        / pair_id
        / f"exp_e1_20260504_{pair_id}_manifest.json"
    )
    context = mat._context_from_manifest(manifest_path)
    old_root = Path("/Users/siyuan/Developer/Veriedge/VeriEdge")
    for key in ("left_calib", "right_calib", "left_eval", "right_eval", "tamper_root", "config_path"):
        value = Path(context[key])
        try:
            context[key] = REPO_ROOT / value.relative_to(old_root)
        except ValueError:
            context[key] = value
    return context


def _load_bundle(root: Path, prompt_id: str) -> Dict[str, Dict[str, np.ndarray]]:
    bundle, _metadata, _runtime = load_capture_bundle_for_prompt(root, prompt_id)
    return bundle


def _topk(logits: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(logits, dtype=np.float64).reshape(-1)
    k = min(int(k), values.size)
    idx = np.argpartition(values, -k)[-k:]
    idx = idx[np.argsort(values[idx])[::-1]]
    shifted = values[idx] - np.max(values[idx])
    probs = np.exp(shifted)
    probs = probs / max(float(np.sum(probs)), 1e-12)
    return idx.astype(np.int64), probs.astype(np.float64)


def _jaccard(left: Iterable[int], right: Iterable[int]) -> float:
    a = set(int(x) for x in left)
    b = set(int(x) for x in right)
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


class C2ToLogitsRunner:
    def __init__(self, model_path: Path, device: str, dtype_name: str) -> None:
        import torch

        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        dtype = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
            "auto": torch.float16 if device in {"cuda", "mps"} else torch.float32,
        }[dtype_name]
        self.device = torch.device(device)
        self.dtype = dtype
        self.runner = QwenShardRunner(
            model_id=str(model_path),
            start_layer=16,
            end_layer=23,
            checkpoint="C3",
            is_first=False,
            is_last=True,
            device=self.device,
            dtype=self.dtype,
            local_files_only=True,
            trust_remote_code=False,
            quantization="none",
        )
        self.torch = torch

    def logits_from_c2(self, c2: np.ndarray) -> np.ndarray:
        seq_len = int(np.asarray(c2).shape[1])
        session_id = uuid.uuid4().hex
        try:
            result = self.runner.run(
                session_id=session_id,
                input_ids=None,
                hidden_states_np=np.asarray(c2, dtype=np.float32),
                position_ids=list(range(seq_len)),
                cache_position=list(range(seq_len)),
            )
            hidden = self.torch.from_numpy(np.asarray(result["tensor"], dtype=np.float32)).to(
                device=self.device,
                dtype=self.dtype,
            )
            with self.torch.inference_mode():
                logits = self.runner.model.lm_head(hidden)
            return logits[:, -1, :].detach().to(dtype=self.torch.float32).cpu().numpy().reshape(-1)
        finally:
            self.runner.reset_session(session_id)


def _candidate_bundle(
    attack_name: str,
    base_bundle: Dict[str, Dict[str, np.ndarray]],
    stale_donor_bundle: Dict[str, Dict[str, np.ndarray]],
    wrong_donor_bundle: Dict[str, Dict[str, np.ndarray]],
    prompt_id: str,
) -> Dict[str, Dict[str, np.ndarray]]:
    if attack_name == "gaussian":
        return inject_tamper(
            base_bundle,
            checkpoint=ATTACK_CHECKPOINT,
            strength=0.15,
            seed=3000 + scalar._trial_index_for_prompt(prompt_id),
            relative_to_tensor_std=True,
            min_std=1e-6,
        )
    if attack_name == "cross_prompt_stale_substitution":
        return inject_stale_replay(base_bundle, stale_donor_bundle, checkpoint=ATTACK_CHECKPOINT)
    if attack_name == "wrong_shard_output":
        return inject_wrong_prompt_checkpoint(base_bundle, wrong_donor_bundle, checkpoint=ATTACK_CHECKPOINT)
    if attack_name == "layer_skip":
        return inject_layer_skip(base_bundle, checkpoint=ATTACK_CHECKPOINT, source_checkpoint=LAYER_SKIP_SOURCE_CHECKPOINT)
    if attack_name == "scale_perturbation":
        return inject_scale_perturbation(base_bundle, checkpoint=ATTACK_CHECKPOINT, scale_delta=0.15)
    raise ValueError(f"unsupported attack: {attack_name}")


def _label_from_logits(clean_logits: np.ndarray, attacked_logits: np.ndarray) -> Dict[str, Any]:
    clean_ids, clean_probs = _topk(clean_logits, TOPK)
    attacked_ids, attacked_probs = _topk(attacked_logits, TOPK)
    top1_changed = int(clean_ids[0] != attacked_ids[0])
    top5_jaccard = _jaccard(clean_ids[:OUTPUT_TOPK_FOR_LABEL], attacked_ids[:OUTPUT_TOPK_FOR_LABEL])
    top20_jaccard = _jaccard(clean_ids, attacked_ids)
    logit_l2 = float(np.linalg.norm(clean_logits.astype(np.float64) - attacked_logits.astype(np.float64)))
    logit_linf = float(np.max(np.abs(clean_logits.astype(np.float64) - attacked_logits.astype(np.float64))))
    # Label is intentionally discrete and easy to defend: the predicted next-token
    # winner changes, or the model's top-5 candidate set changes.
    output_affecting = int(bool(top1_changed) or top5_jaccard < 1.0)
    return {
        "output_affecting": output_affecting,
        "top1_changed": top1_changed,
        "top5_jaccard": round(top5_jaccard, 6),
        "top20_jaccard": round(top20_jaccard, 6),
        "logit_l2_delta": round(logit_l2, 6),
        "logit_linf_delta": round(logit_linf, 6),
        "clean_top1_id": int(clean_ids[0]),
        "attacked_top1_id": int(attacked_ids[0]),
        "clean_top5_ids": " ".join(str(int(x)) for x in clean_ids[:5]),
        "attacked_top5_ids": " ".join(str(int(x)) for x in attacked_ids[:5]),
        "clean_top5_probs": " ".join(f"{float(x):.8f}" for x in clean_probs[:5]),
        "attacked_top5_probs": " ".join(f"{float(x):.8f}" for x in attacked_probs[:5]),
    }


def _run_labels(pair_ids: Sequence[str], prompt_limit: int, runner: C2ToLogitsRunner) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for pair_id in pair_ids:
        context = _pair_context(pair_id)
        prompt_ids = scalar._shared_prompt_ids(context["right_eval"], context["right_eval"])
        if prompt_limit > 0:
            prompt_ids = prompt_ids[:prompt_limit]
        stale_root, stale_source_kind = mat._rerun_root_for(context["right_eval"])
        started = time.perf_counter()
        for idx, prompt_id in enumerate(prompt_ids):
            base_bundle = _load_bundle(context["right_eval"], prompt_id)
            stale_prompt_id = prompt_ids[(idx - 1) % len(prompt_ids)]
            wrong_prompt_id = prompt_ids[(idx + 1) % len(prompt_ids)]
            stale_donor_bundle = _load_bundle(stale_root, stale_prompt_id)
            wrong_donor_bundle = _load_bundle(context["right_eval"], wrong_prompt_id)
            clean_logits = runner.logits_from_c2(base_bundle["prefill"][ATTACK_CHECKPOINT])
            for attack_name in FOCUS_ATTACKS:
                candidate = _candidate_bundle(attack_name, base_bundle, stale_donor_bundle, wrong_donor_bundle, prompt_id)
                attacked_logits = runner.logits_from_c2(candidate["prefill"][ATTACK_CHECKPOINT])
                label = _label_from_logits(clean_logits, attacked_logits)
                rows.append(
                    {
                        "pair_id": pair_id,
                        "pair_label": context["pair_label"],
                        "prompt_id": prompt_id,
                        "attack_family": attack_name,
                        "attack_checkpoint": ATTACK_CHECKPOINT,
                        "attack_strength": 0.15 if attack_name in {"gaussian", "scale_perturbation"} else "",
                        "donor_source": (
                            stale_source_kind
                            if attack_name == "cross_prompt_stale_substitution"
                            else "same_run_next_prompt"
                            if attack_name == "wrong_shard_output"
                            else f"{LAYER_SKIP_SOURCE_CHECKPOINT}_to_{ATTACK_CHECKPOINT}"
                            if attack_name == "layer_skip"
                            else "scale_delta"
                            if attack_name == "scale_perturbation"
                            else "gaussian_noise"
                        ),
                        "output_affecting_available": 1,
                        "output_affecting_reason": "replay_to_logits_topk_label",
                        **label,
                    }
                )
        elapsed = time.perf_counter() - started
        print(f"labeled {pair_id}: prompts={len(prompt_ids)} rows={len(rows)} elapsed_sec={elapsed:.2f}", flush=True)
    return rows


def _summarize(labels: pd.DataFrame, detail: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    focus_detail = detail[
        detail["pair_id"].isin(labels["pair_id"].unique())
        & detail["variant"].isin(FOCUS_VARIANTS)
        & detail["attack_family"].isin(FOCUS_ATTACKS)
    ].copy()
    merged = focus_detail.merge(
        labels,
        on=["pair_id", "pair_label", "prompt_id", "attack_family"],
        how="inner",
        suffixes=("", "_label"),
    )
    # Normalize overlapping columns so the joined detail has a single canonical
    # output-affecting view sourced from the replay-to-logits labels.
    for field in (
        "attack_checkpoint",
        "attack_strength",
        "donor_source",
        "output_affecting_available",
        "output_affecting",
        "output_affecting_reason",
    ):
        label_field = f"{field}_label"
        if label_field in merged.columns:
            merged[field] = merged[label_field]
    if "output_affecting_available" in merged.columns:
        output_available = pd.to_numeric(merged["output_affecting_available"], errors="coerce").fillna(0).astype(int)
        merged["output_affecting_reason"] = output_available.map(
            lambda flag: "replay_to_logits_topk_label" if int(flag) == 1 else "no_logits_or_output_in_capture"
        )
    merged = merged.drop(columns=[col for col in merged.columns if col.endswith("_label")], errors="ignore")
    rows: List[Dict[str, Any]] = []
    output_col = "output_affecting"
    for keys, group in merged.groupby(["pair_id", "variant", "attack_family"], dropna=False):
        pair_id, variant, attack = keys
        output_values = pd.to_numeric(group[output_col], errors="coerce").fillna(0)
        affecting = group[output_values == 1]
        rows.append(
            {
                "pair_id": pair_id,
                "variant": variant,
                "attack_family": attack,
                "prompt_count": int(len(group)),
                "output_affecting_prompt_count": int(len(affecting)),
                "output_affecting_rate": round(float(output_values.mean()), 6) if len(group) else 0.0,
                "all_sample_detection_rate": round(float(group["detected"].mean()), 6) if len(group) else 0.0,
                "all_sample_localization_acc": round(float(group["localization_correct"].mean()), 6) if len(group) else 0.0,
                "output_affecting_detection_rate": round(float(affecting["detected"].mean()), 6) if len(affecting) else "",
                "output_affecting_localization_acc": round(float(affecting["localization_correct"].mean()), 6) if len(affecting) else "",
                "mean_logit_l2_delta": round(float(group["logit_l2_delta"].mean()), 6) if len(group) else 0.0,
                "mean_top5_jaccard": round(float(group["top5_jaccard"].mean()), 6) if len(group) else 0.0,
            }
        )
    return merged, pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, report_path: Path, labels_path: Path, joined_path: Path, summary_path: Path) -> None:
    markdown_rows = ["| " + " | ".join(summary.columns) + " |", "| " + " | ".join(["-"] * len(summary.columns)) + " |"]
    for _, row in summary.iterrows():
        markdown_rows.append("| " + " | ".join(str(row[col]) for col in summary.columns) + " |")
    pair_ids = sorted(str(x) for x in summary["pair_id"].dropna().unique())
    pair_scope = ", ".join(pair_ids)
    lines = [
        "# E2 Output-Affecting Subset Report",
        "",
        f"- Scope: output-affecting replay over {len(pair_ids)} pair(s): {pair_scope}.",
        f"- Variant coverage: focus matrix only (`{', '.join(FOCUS_VARIANTS)}`), not the full variant family.",
        "- Method: replace/perturb C2, replay layers 16-23 to logits using QwenShardRunner, then label next-token top-k changes.",
        "- Output-affecting label: `top1_changed == 1` or clean/attacked top-5 token set differs.",
        f"- Labels: {labels_path}",
        f"- Joined verifier detail: {joined_path}",
        f"- Summary: {summary_path}",
        "",
        "## Summary",
        "",
        "\n".join(markdown_rows),
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", default=str(REPO_ROOT / "workspace" / "models" / "Qwen3-0.6B"))
    parser.add_argument("--pairs", nargs="+", default=FOCUS_PAIR_IDS)
    parser.add_argument("--prompt-limit", type=int, default=0, help="0 means all shared prompts")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--dtype", default="auto", choices=["auto", "float16", "bfloat16", "float32"])
    args = parser.parse_args()

    runner = C2ToLogitsRunner(Path(args.model_path).expanduser().resolve(), args.device, args.dtype)
    labels = _run_labels(args.pairs, int(args.prompt_limit), runner)

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    labels_path = TABLE_DIR / f"{RUN_ID}_labels.csv"
    joined_path = TABLE_DIR / f"{RUN_ID}_joined_detail.csv"
    summary_path = TABLE_DIR / f"{RUN_ID}_summary.csv"
    report_path = REPORT_DIR / f"{RUN_ID}_report.md"

    label_fields = [
        "pair_id", "pair_label", "prompt_id", "attack_family", "attack_checkpoint", "attack_strength",
        "donor_source", "output_affecting_available", "output_affecting_reason", "output_affecting", "top1_changed", "top5_jaccard",
        "top20_jaccard", "logit_l2_delta", "logit_linf_delta", "clean_top1_id", "attacked_top1_id",
        "clean_top5_ids", "attacked_top5_ids", "clean_top5_probs", "attacked_top5_probs",
    ]
    _write_csv(labels_path, labels, label_fields)

    labels_df = pd.DataFrame(labels)
    detail = pd.read_csv(TABLE_DIR / "exp_e2_20260512_material_tamper_full_matrix_detail.csv")
    joined, summary = _summarize(labels_df, detail)
    joined.to_csv(joined_path, index=False)
    summary.to_csv(summary_path, index=False)
    _write_report(summary, report_path, labels_path, joined_path, summary_path)

    print(f"labels : {labels_path}")
    print(f"joined : {joined_path}")
    print(f"summary: {summary_path}")
    print(f"report : {report_path}")


if __name__ == "__main__":
    main()
