from __future__ import annotations

import argparse
import json
from pathlib import Path


CALIBRATION_COUNT = 40
EVALUATION_COUNT = 200


TASK_PREFIXES = [
    "Explain",
    "Summarize",
    "Compare",
    "Outline",
    "Describe",
    "List",
    "Give a concise checklist for",
    "Provide a short example of",
    "Write a brief note about",
    "Discuss",
]

TOPICS = [
    "dynamic programming",
    "floating-point arithmetic across hardware",
    "unit test debugging",
    "tokenization in language models",
    "Merkle trees in distributed systems",
    "gradient descent",
    "TCP versus UDP",
    "off-chain verification workflows",
    "checkpoint hashing",
    "heterogeneous model execution",
    "vector clocks",
    "quorum systems",
    "RPC retries and backoff",
    "content-addressed storage",
    "sharded model inference",
    "GPU memory fragmentation",
    "bfloat16 versus float32",
    "quantization-aware inference",
    "cache invalidation",
    "idempotent API design",
    "database indexing",
    "load balancing",
    "eventual consistency",
    "failure localization",
]

TASK_SUFFIXES = [
    "for a junior systems student in four sentences.",
    "in two short paragraphs with one concrete example.",
    "as a debugging checklist with five bullets.",
    "with one pitfall and one mitigation.",
    "for an engineer who is new to large-model serving.",
    "with a focus on practical trade-offs.",
    "in plain language without equations.",
    "for a code review discussion.",
    "as advice for production deployment.",
    "with emphasis on reproducibility.",
]


def _build_prompt(index: int) -> str:
    prefix = TASK_PREFIXES[index % len(TASK_PREFIXES)]
    topic = TOPICS[(index // len(TASK_PREFIXES)) % len(TOPICS)]
    suffix = TASK_SUFFIXES[(index // (len(TASK_PREFIXES) * 2)) % len(TASK_SUFFIXES)]
    return f"{prefix} {topic} {suffix}"


def _record(prompt_id: str, split: str, text: str) -> dict[str, str]:
    return {"prompt_id": prompt_id, "split": split, "text": text}


def build_records() -> list[dict[str, str]]:
    total = CALIBRATION_COUNT + EVALUATION_COUNT
    prompts = [_build_prompt(i) for i in range(total)]
    records: list[dict[str, str]] = []

    for idx in range(CALIBRATION_COUNT):
        records.append(_record(f"calib_{idx + 1:03d}", "calibration", prompts[idx]))
    for idx in range(EVALUATION_COUNT):
        records.append(_record(f"eval_{idx + 1:03d}", "evaluation", prompts[CALIBRATION_COUNT + idx]))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a deterministic 40/200 prompt split for E1 paired-capture runs")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[2] / "artifacts" / "thc" / "data" / "qwen_prompt_splits_40_200.jsonl"),
        help="Output JSONL path",
    )
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for record in build_records():
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    print(f"Wrote {CALIBRATION_COUNT} calibration + {EVALUATION_COUNT} evaluation prompts to {output_path}")


if __name__ == "__main__":
    main()
