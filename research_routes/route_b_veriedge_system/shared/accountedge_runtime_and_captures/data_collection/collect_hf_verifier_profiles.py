#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
import pandas as pd


DEFAULT_PROMPTS = [
    "Summarize why checkpoint verification is useful for edge inference.",
    "Explain selective payload delivery in one short paragraph.",
    "List three risks in distributed model serving.",
    "Give a concise definition of false positive rate.",
    "Write one sentence about verifier workload.",
    "Describe why replay attacks are hard to detect.",
    "What does a placement policy decide before task disclosure?",
    "Explain the difference between latency and goodput.",
]


@dataclass(frozen=True)
class CaptureSet:
    checkpoint_names: tuple[str, ...]
    honest_a: np.ndarray
    honest_b: np.ndarray
    tampered: np.ndarray


def load_prompts(path: str | None, max_prompts: int) -> list[str]:
    if path is None:
        return DEFAULT_PROMPTS[:max_prompts]
    prompts: list[str] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            prompts.append(json.loads(line)["prompt"])
        else:
            prompts.append(line)
        if len(prompts) >= max_prompts:
            break
    return prompts


def checkpoint_indices(num_hidden_states: int) -> list[int]:
    # hidden_states includes the embedding output at index 0; use internal layers.
    last = num_hidden_states - 1
    return sorted(set([max(1, last // 3), max(1, (2 * last) // 3), last]))


def collect_hf_captures(
    model_id: str,
    prompts: list[str],
    max_length: int,
    honest_noise: float,
    tamper_strength: float,
    seed: int,
) -> CaptureSet:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Missing optional Hugging Face dependencies. Run: "
            "pip install -r data_collection/requirements-hf.txt"
        ) from exc

    rng = np.random.default_rng(seed)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        torch_dtype="auto",
        device_map="auto",
    )
    model.eval()
    device = next(model.parameters()).device

    prompt_tensors: list[np.ndarray] = []
    names: tuple[str, ...] | None = None
    with torch.no_grad():
        for prompt in prompts:
            encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length)
            encoded = {key: value.to(device) for key, value in encoded.items()}
            outputs = model(**encoded, output_hidden_states=True, use_cache=False)
            indices = checkpoint_indices(len(outputs.hidden_states))
            names = tuple(f"C{i + 1}" for i in range(len(indices)))
            checkpoints = []
            for index in indices:
                tensor = outputs.hidden_states[index][0].detach().float().cpu().numpy()
                checkpoints.append(tensor)
            prompt_tensors.append(np.stack(checkpoints, axis=0))

    honest_a = np.stack(prompt_tensors, axis=0)
    honest_b = honest_a + rng.normal(0.0, honest_noise, size=honest_a.shape)
    tampered = honest_a.copy()
    tampered[:, 1, :, :] += rng.normal(0.0, tamper_strength, size=tampered[:, 1, :, :].shape)
    return CaptureSet(checkpoint_names=names or ("C1", "C2", "C3"), honest_a=honest_a, honest_b=honest_b, tampered=tampered)


def collect_synthetic_captures(
    prompts: list[str],
    honest_noise: float,
    tamper_strength: float,
    seed: int,
) -> CaptureSet:
    rng = np.random.default_rng(seed)
    shape = (len(prompts), 3, 12, 32)
    honest_a = rng.normal(0.0, 1.0, size=shape)
    honest_b = honest_a + rng.normal(0.0, honest_noise, size=shape)
    tampered = honest_a.copy()
    tampered[:, 1, :, :] += rng.normal(0.0, tamper_strength, size=tampered[:, 1, :, :].shape)
    return CaptureSet(checkpoint_names=("C1", "C2", "C3"), honest_a=honest_a, honest_b=honest_b, tampered=tampered)


def random_projection(hidden_dim: int, sketch_dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(hidden_dim, sketch_dim))
    return matrix / np.linalg.norm(matrix, axis=0, keepdims=True)


def sampled_abs_distance(a: np.ndarray, b: np.ndarray, sample_size: int, seed: int) -> np.ndarray:
    flat_a = a.reshape(a.shape[0], -1)
    flat_b = b.reshape(b.shape[0], -1)
    rng = np.random.default_rng(seed)
    sample_size = min(sample_size, flat_a.shape[1])
    cols = rng.choice(flat_a.shape[1], size=sample_size, replace=False)
    return np.mean(np.abs(flat_a[:, cols] - flat_b[:, cols]), axis=1)


def projected_cosine_distance(a: np.ndarray, b: np.ndarray, sketch_dim: int, seed: int) -> np.ndarray:
    # input shape: prompt x checkpoint x token x hidden
    projection = random_projection(a.shape[-1], sketch_dim, seed)
    sketch_a = np.einsum("pcth,hd->pctd", a, projection)
    sketch_b = np.einsum("pcth,hd->pctd", b, projection)
    sketch_a = sketch_a / np.maximum(np.linalg.norm(sketch_a, axis=-1, keepdims=True), 1e-12)
    sketch_b = sketch_b / np.maximum(np.linalg.norm(sketch_b, axis=-1, keepdims=True), 1e-12)
    cosine = np.sum(sketch_a * sketch_b, axis=-1)
    return np.max(1.0 - cosine, axis=(1, 2))


def profile_rows(captures: CaptureSet, alpha: float, seed: int) -> list[dict]:
    variants = [
        ("scalar16", "sampled_abs", 16, 64),
        ("projcos4", "projected_token", 4, 256),
        ("projcos16", "projected_token", 16, 1024),
    ]
    rows = []
    for profile_idx, (sketch, family, size, sketch_bytes) in enumerate(variants, start=1):
        if family == "sampled_abs":
            honest_scores = sampled_abs_distance(captures.honest_a, captures.honest_b, size, seed + profile_idx)
            tamper_scores = sampled_abs_distance(captures.honest_a, captures.tampered, size, seed + profile_idx)
        else:
            honest_scores = projected_cosine_distance(captures.honest_a, captures.honest_b, size, seed + profile_idx)
            tamper_scores = projected_cosine_distance(captures.honest_a, captures.tampered, size, seed + profile_idx)

        threshold = float(np.quantile(honest_scores, 1.0 - alpha))
        fpr = float(np.mean(honest_scores > threshold))
        tpr = float(np.mean(tamper_scores > threshold))
        rows.append(
            {
                "profile_id": f"collected_{profile_idx:03d}",
                "model": "hf_or_synthetic_smoke",
                "boundary": "-".join(captures.checkpoint_names),
                "pair": "single_machine_smoke",
                "device_a": "local_backend_a",
                "backend_a": "local",
                "device_b": "local_backend_b",
                "backend_b": "local",
                "sketch": sketch,
                "alpha": alpha,
                "beta": 0.9,
                "fpr": fpr,
                "tpr": tpr,
                "sketch_bytes": sketch_bytes,
                "verify_ms": 0.0,
                "n_eval": len(honest_scores),
                "n_calib": len(honest_scores),
                "feasible": int(fpr <= alpha and tpr >= 0.9),
                "fpr_false_positives": int(np.sum(honest_scores > threshold)),
                "fpr_trials": len(honest_scores),
                "tpr_true_positives": int(np.sum(tamper_scores > threshold)),
                "tpr_trials": len(tamper_scores),
                "risk_class": "low-risk" if fpr <= alpha and tpr >= 0.9 else "smoke-only",
                "selection_rule": "calibrate threshold on honest scores; evaluate held-out tamper scores",
                "threshold": threshold,
            }
        )
    return rows


def save_captures(path: Path, captures: CaptureSet) -> None:
    np.savez_compressed(
        path,
        checkpoint_names=np.array(captures.checkpoint_names),
        honest_a=captures.honest_a,
        honest_b=captures.honest_b,
        tampered=captures.tampered,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect small verifier-profile CSVs from checkpoint captures.")
    parser.add_argument("--backend", choices=["hf", "synthetic"], default="hf")
    parser.add_argument("--model-id", default="Qwen/Qwen3-0.6B")
    parser.add_argument("--prompts", default=None, help="Optional text or JSONL file with a prompt field.")
    parser.add_argument("--max-prompts", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=64)
    parser.add_argument("--alpha", type=float, default=0.10)
    parser.add_argument("--honest-noise", type=float, default=0.002)
    parser.add_argument("--tamper-strength", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=20260515)
    parser.add_argument("--out-dir", default="data_collection/out_smoke")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    prompts = load_prompts(args.prompts, args.max_prompts)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.backend == "hf":
        captures = collect_hf_captures(
            model_id=args.model_id,
            prompts=prompts,
            max_length=args.max_length,
            honest_noise=args.honest_noise,
            tamper_strength=args.tamper_strength,
            seed=args.seed,
        )
    else:
        captures = collect_synthetic_captures(
            prompts=prompts,
            honest_noise=args.honest_noise,
            tamper_strength=args.tamper_strength,
            seed=args.seed,
        )

    captures_path = out_dir / "captures.npz"
    profiles_path = out_dir / "verifier_profiles_collected.csv"
    summary_path = out_dir / "collection_summary.json"
    save_captures(captures_path, captures)
    rows = profile_rows(captures, alpha=args.alpha, seed=args.seed)
    pd.DataFrame(rows).to_csv(profiles_path, index=False)

    summary = {
        "backend": args.backend,
        "model_id": args.model_id if args.backend == "hf" else None,
        "prompt_count": len(prompts),
        "checkpoint_names": captures.checkpoint_names,
        "outputs": {
            "captures": str(captures_path),
            "profiles": str(profiles_path),
            "summary": str(summary_path),
        },
        "scope": "single-machine smoke collector; measured paper figures use included CSVs under data/",
        "profiles": rows,
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps({"wrote": summary["outputs"], "profile_count": len(rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
