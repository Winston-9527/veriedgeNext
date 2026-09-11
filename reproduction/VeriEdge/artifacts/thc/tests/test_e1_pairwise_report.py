from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "artifacts" / "thc" / "src" / "e1_pairwise_report.py"


def _write_capture_root(root: Path, *, prompt_offsets: dict[str, float]) -> None:
    capture_dir = root / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    meta_path = capture_dir / "checkpoint_metadata.jsonl"
    with meta_path.open("w", encoding="utf-8") as meta:
        for prompt_id, offset in prompt_offsets.items():
            base = np.array([[[1.10, 2.20, 3.30, 4.40]]], dtype=np.float32) + np.float32(offset)
            np.savez_compressed(
                capture_dir / f"{prompt_id}.npz",
                prefill__C1=base,
                prefill__C2=base + np.float32(0.5),
                prefill__C3=base + np.float32(1.0),
            )
            for checkpoint in ("C1", "C2", "C3"):
                meta.write(
                    json.dumps(
                        {
                            "prompt_id": prompt_id,
                            "split": "evaluation",
                            "stage": "prefill",
                            "stage_key": "prefill",
                            "decode_step": 0,
                            "checkpoint": checkpoint,
                            "shape": [1, 1, 4],
                            "provider_plan": ["provider_a", "provider_b", "provider_c"],
                            "provider": f"provider_{checkpoint.lower()}",
                            "runtime": "hetero_qwen_torch_chain",
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )


class E1PairwiseReportTests(unittest.TestCase):
    def test_pairwise_report_emits_summary_and_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            left_root = tmp / "left_eval"
            right_root = tmp / "right_eval"
            output_dir = tmp / "out"
            config_path = tmp / "config.json"
            delta_path = tmp / "delta_map.json"

            _write_capture_root(left_root, prompt_offsets={"prompt_a": 0.0, "prompt_b": 0.0})
            _write_capture_root(right_root, prompt_offsets={"prompt_a": 0.0002, "prompt_b": 0.0003})

            config_path.write_text(
                json.dumps(
                    {
                        "experiment": {
                            "shards": [
                                {"checkpoint": "C1"},
                                {"checkpoint": "C2"},
                                {"checkpoint": "C3"},
                            ]
                        },
                        "tstc": {
                            "seed_base": 2026,
                            "delta_map": {
                                "prefill": {"C1": 0.01, "C2": 0.01, "C3": 0.01},
                                "decode": {"C1": 0.01, "C2": 0.01, "C3": 0.01},
                            },
                            "prefill": {"default": {"token_samples": 1, "channel_samples": 4}},
                            "decode": {"default": {"channel_samples": 4}},
                        },
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            delta_path.write_text(
                json.dumps(
                    {
                        "delta_map": {
                            "prefill": {"C1": 0.01, "C2": 0.01, "C3": 0.01},
                            "decode": {"C1": 0.01, "C2": 0.01, "C3": 0.01},
                        }
                    },
                    indent=2,
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--config",
                    str(config_path),
                    "--delta-map-file",
                    str(delta_path),
                    "--pair",
                    f"pair_micro_noise::{left_root}::{right_root}",
                    "--output-dir",
                    str(output_dir),
                    "--owner",
                    "tester",
                ],
                check=True,
                cwd=str(ROOT),
            )

            detail_csv = output_dir / "exp_e1_{}_tester_pairwise_details.csv".format(
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%d")
            )
            summary_csv = output_dir / "exp_e1_{}_tester_summary.csv".format(
                __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%d")
            )
            self.assertTrue(detail_csv.exists())
            self.assertTrue(summary_csv.exists())

            with detail_csv.open("r", encoding="utf-8") as f:
                detail_rows = list(csv.DictReader(f))
            self.assertEqual(len(detail_rows), 2)
            self.assertTrue(all(row["stage"] == "prefill" for row in detail_rows))
            self.assertTrue(all(row["thc_detected"] == "True" for row in detail_rows))
            self.assertTrue(all(row["tstc_detected"] == "False" for row in detail_rows))
            self.assertTrue(all(row["localization_label"] == "N/A" for row in detail_rows))

            with summary_csv.open("r", encoding="utf-8") as f:
                summary_rows = list(csv.DictReader(f))
            self.assertEqual(len(summary_rows), 1)
            self.assertEqual(summary_rows[0]["pair_label"], "pair_micro_noise")
            self.assertEqual(summary_rows[0]["stage"], "prefill")
            self.assertEqual(summary_rows[0]["prompt_count"], "2")
            self.assertEqual(summary_rows[0]["thc_fpr"], "1.0")
            self.assertEqual(summary_rows[0]["tstc_fpr"], "0.0")


if __name__ == "__main__":
    unittest.main()
