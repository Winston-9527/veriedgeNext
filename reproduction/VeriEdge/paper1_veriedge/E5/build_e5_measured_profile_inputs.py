from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_TABLE_DIR = REPO_ROOT / "paper1_veriedge" / "E5" / "tables"
PROMPT_FILE = REPO_ROOT / "artifacts" / "thc" / "data" / "qwen_prompt_splits_40_200.jsonl"
REQUESTER_CONFIG = REPO_ROOT / "artifacts" / "inference-E2E" / "requester" / "config.example.yaml"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build measured-profile E5 policy replay inputs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--profile-matrix")
    return parser.parse_args()


def _read_csv(path: Path) -> List[Dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _latest_profile_matrix() -> Path:
    matches = sorted(PROFILE_TABLE_DIR.glob("exp_e5_*_verification_profile_matrix.csv"), key=lambda p: (p.stat().st_mtime, p.name))
    if not matches:
        raise FileNotFoundError(f"no verification profile matrix found under {PROFILE_TABLE_DIR}")
    return matches[-1]


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_eval_prompts(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if str(payload.get("split", "")) != "evaluation":
                continue
            text = str(payload.get("text", ""))
            rows.append(
                {
                    "prompt_id": str(payload["prompt_id"]),
                    "text_chars": len(text),
                    "text_words": len(text.split()),
                }
            )
    return rows


def _network_profiles_from_yaml(path: Path) -> Dict[str, Dict[str, float]]:
    text = path.read_text(encoding="utf-8")
    wan_spec = ""
    capture = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("network_profiles:"):
            capture = True
            continue
        if capture and line.startswith("matrix:"):
            break
        if capture and "target_spec:" in line and "WAN" not in line:
            value = line.split("target_spec:", 1)[1].strip().strip('"')
            if value:
                wan_spec = value
    lan = {"rtt_ms": 5.0, "bandwidth_mbps": 300.0, "loss_pct": 0.1}
    if not wan_spec:
        return {"LAN": lan, "WAN": {"rtt_ms": 49.0, "bandwidth_mbps": 40.0, "loss_pct": 1.33}}
    rtts: List[float] = []
    bws: List[float] = []
    losses: List[float] = []
    for item in wan_spec.split(","):
        _, rtt, bw, loss = item.split(":")
        rtts.append(float(rtt))
        bws.append(float(bw))
        losses.append(float(loss))
    return {
        "LAN": lan,
        "WAN": {
            "rtt_ms": round(statistics.mean(rtts), 3),
            "bandwidth_mbps": round(min(bws), 3),
            "loss_pct": round(statistics.mean(losses), 3),
        },
    }


def _task_records(prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chars = [row["text_chars"] for row in prompts]
    p40 = statistics.quantiles(chars, n=10)[3]
    p75 = statistics.quantiles(chars, n=4)[2]
    median_chars = statistics.median(chars)
    tasks: List[Dict[str, Any]] = []
    for idx, row in enumerate(prompts):
        char_count = int(row["text_chars"])
        if char_count <= p40:
            required_width = 1
        elif char_count <= p75:
            required_width = 2
        else:
            required_width = 3
        client_profile = "LAN" if idx < int(len(prompts) * 0.7) else "WAN"
        difficulty = round(char_count / max(median_chars, 1), 6)
        tasks.append(
            {
                "task_id": str(row["prompt_id"]),
                "prompt_chars": char_count,
                "prompt_words": int(row["text_words"]),
                "difficulty": difficulty,
                "required_width": required_width,
                "client_profile": client_profile,
            }
        )
    return tasks


def _workloads(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    single_tasks = [{**task, "arrival_s": float(idx) * 5.0} for idx, task in enumerate(tasks)]
    queued_tasks = [{**task, "arrival_s": float(idx // 8) * 0.25} for idx, task in enumerate(tasks)]
    return [
        {
            "workload_id": "single_task",
            "description": "Independent tasks with no queue pressure.",
            "tasks": single_tasks,
        },
        {
            "workload_id": "queued_8",
            "description": "Burst arrivals with queue pressure every 8 tasks.",
            "tasks": queued_tasks,
        },
    ]


def _profile_lookup(rows: List[Dict[str, str]]) -> Dict[tuple[str, str], Dict[str, str]]:
    return {(row["pair_id"], row["variant"]): row for row in rows}


def _single_homo_template(profile_rows: List[Dict[str, str]], variant: str) -> Dict[str, float]:
    candidates = [row for row in profile_rows if row["variant"] == variant]
    replay = statistics.mean(float(row["reference_replay_runtime_ms"]) for row in candidates)
    challenge = statistics.mean(float(row["challenge_latency_ms"]) for row in candidates)
    bytes_ckpt = int(float(candidates[0]["signature_bytes_per_checkpoint_fp32"]))
    reveal = int(float(candidates[0]["reveal_payload_bytes_per_trace"]))
    return {
        "reference_replay_runtime_ms": round(replay, 6),
        "challenge_latency_ms": round(challenge, 6),
        "bytes_per_checkpoint": bytes_ckpt,
        "bytes_per_trace": reveal,
    }


def _placements(profile_rows: List[Dict[str, str]], network_profiles: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    profile = _profile_lookup(profile_rows)
    lan = network_profiles["LAN"]
    wan = network_profiles["WAN"]

    def build_from_profile(
        *,
        placement_id: str,
        label: str,
        network: str,
        pair_id: str,
        variant: str,
        group_width: int,
        base_success: float,
        base_fixed_ms: float,
        per_char_ms: float,
    ) -> Dict[str, Any]:
        row = profile[(pair_id, variant)]
        net = lan if network == "LAN" else wan
        fpr = float(row["eval_honest_hetero_fpr"])
        tpr = float(row["material_tpr_min"])
        return {
            "placement_id": placement_id,
            "label": label,
            "network": network,
            "group_width": group_width,
            "pair_id": pair_id,
            "variant": variant,
            "risk_class": row["risk_class"],
            "verification_risk": fpr,
            "false_dispute_risk": fpr,
            "material_tpr_min": tpr,
            "material_locacc_min": float(row["material_locacc_min"]),
            "feasible_under_alpha_beta": int(row["feasible_under_alpha_beta"]),
            "signature_bytes_per_checkpoint_fp32": int(float(row["signature_bytes_per_checkpoint_fp32"])),
            "reveal_payload_bytes_per_trace": int(float(row["reveal_payload_bytes_per_trace"])),
            "reference_replay_runtime_ms": float(row["reference_replay_runtime_ms"]),
            "challenge_latency_ms": float(row["challenge_latency_ms"]),
            "commitment_head_bytes": float(row["commitment_head_bytes"]),
            "commitment_chain_bytes": float(row["commitment_chain_bytes"]),
            "base_success": base_success,
            "base_fixed_ms": base_fixed_ms,
            "per_char_ms": per_char_ms,
            "network_rtt_ms": net["rtt_ms"],
            "network_loss_pct": net["loss_pct"],
        }

    homo_scalar = _single_homo_template(profile_rows, "scalar16")
    homo_projcos = _single_homo_template(profile_rows, "projcos4")

    placements: List[Dict[str, Any]] = [
        {
            "placement_id": "lan_single_homo_scalar16",
            "label": "LAN single-node homo scalar16",
            "network": "LAN",
            "group_width": 1,
            "pair_id": "single_homo",
            "variant": "scalar16",
            "risk_class": "low-risk",
            "verification_risk": 0.0,
            "false_dispute_risk": 0.0,
            "material_tpr_min": 1.0,
            "material_locacc_min": 1.0,
            "feasible_under_alpha_beta": 1,
            "signature_bytes_per_checkpoint_fp32": homo_scalar["bytes_per_checkpoint"],
            "reveal_payload_bytes_per_trace": homo_scalar["bytes_per_trace"],
            "reference_replay_runtime_ms": homo_scalar["reference_replay_runtime_ms"],
            "challenge_latency_ms": homo_scalar["challenge_latency_ms"],
            "commitment_head_bytes": 32.0,
            "commitment_chain_bytes": 96.0,
            "base_success": 0.992,
            "base_fixed_ms": 780.0,
            "per_char_ms": 0.84,
            "network_rtt_ms": lan["rtt_ms"],
            "network_loss_pct": lan["loss_pct"],
        },
        {
            "placement_id": "lan_single_homo_projcos4",
            "label": "LAN single-node homo projcos4",
            "network": "LAN",
            "group_width": 1,
            "pair_id": "single_homo",
            "variant": "projcos4",
            "risk_class": "low-risk",
            "verification_risk": 0.0,
            "false_dispute_risk": 0.0,
            "material_tpr_min": 1.0,
            "material_locacc_min": 1.0,
            "feasible_under_alpha_beta": 1,
            "signature_bytes_per_checkpoint_fp32": homo_projcos["bytes_per_checkpoint"],
            "reveal_payload_bytes_per_trace": homo_projcos["bytes_per_trace"],
            "reference_replay_runtime_ms": homo_projcos["reference_replay_runtime_ms"],
            "challenge_latency_ms": homo_projcos["challenge_latency_ms"],
            "commitment_head_bytes": 32.0,
            "commitment_chain_bytes": 96.0,
            "base_success": 0.992,
            "base_fixed_ms": 780.0,
            "per_char_ms": 0.84,
            "network_rtt_ms": lan["rtt_ms"],
            "network_loss_pct": lan["loss_pct"],
        },
        build_from_profile(
            placement_id="lan_ab_scalar16",
            label="LAN A/B scalar16",
            network="LAN",
            pair_id="t4strict_pair_a_vs_b_40_200",
            variant="scalar16",
            group_width=3,
            base_success=0.978,
            base_fixed_ms=940.0,
            per_char_ms=0.97,
        ),
        build_from_profile(
            placement_id="lan_ab_projcos4",
            label="LAN A/B projcos4",
            network="LAN",
            pair_id="t4strict_pair_a_vs_b_40_200",
            variant="projcos4",
            group_width=3,
            base_success=0.978,
            base_fixed_ms=940.0,
            per_char_ms=0.97,
        ),
        build_from_profile(
            placement_id="wan_ac_scalar16",
            label="WAN A/C scalar16",
            network="WAN",
            pair_id="t4strict_pair_a_vs_c_40_200",
            variant="scalar16",
            group_width=3,
            base_success=0.958,
            base_fixed_ms=1080.0,
            per_char_ms=1.01,
        ),
        build_from_profile(
            placement_id="wan_ac_projcos4",
            label="WAN A/C projcos4",
            network="WAN",
            pair_id="t4strict_pair_a_vs_c_40_200",
            variant="projcos4",
            group_width=3,
            base_success=0.958,
            base_fixed_ms=1080.0,
            per_char_ms=1.01,
        ),
        build_from_profile(
            placement_id="wan_ad_scalar16",
            label="WAN A/D scalar16",
            network="WAN",
            pair_id="t4strict_pair_a_vs_d_40_200",
            variant="scalar16",
            group_width=3,
            base_success=0.952,
            base_fixed_ms=1060.0,
            per_char_ms=0.99,
        ),
        build_from_profile(
            placement_id="wan_ad_projcos4",
            label="WAN A/D projcos4",
            network="WAN",
            pair_id="t4strict_pair_a_vs_d_40_200",
            variant="projcos4",
            group_width=3,
            base_success=0.952,
            base_fixed_ms=1060.0,
            per_char_ms=0.99,
        ),
        build_from_profile(
            placement_id="wan_bd_scalar16",
            label="WAN B/D scalar16",
            network="WAN",
            pair_id="t4strict_pair_b_vs_d_40_200",
            variant="scalar16",
            group_width=3,
            base_success=0.91,
            base_fixed_ms=1120.0,
            per_char_ms=1.03,
        ),
        build_from_profile(
            placement_id="wan_bd_projcos4",
            label="WAN B/D projcos4",
            network="WAN",
            pair_id="t4strict_pair_b_vs_d_40_200",
            variant="projcos4",
            group_width=3,
            base_success=0.91,
            base_fixed_ms=1120.0,
            per_char_ms=1.03,
        ),
    ]
    return placements


def main() -> None:
    args = _parse_args()
    profile_matrix = Path(args.profile_matrix).resolve() if args.profile_matrix else _latest_profile_matrix()
    profile_rows = _read_csv(profile_matrix)
    prompts = _load_eval_prompts(PROMPT_FILE)
    network_profiles = _network_profiles_from_yaml(REQUESTER_CONFIG)
    tasks = _task_records(prompts)
    workloads = _workloads(tasks)
    placements = _placements(profile_rows, network_profiles)

    payload = {
        "seed": int(args.seed),
        "source": {
            "profile_matrix": str(profile_matrix),
            "profile_matrix_sha256": _sha256(profile_matrix),
            "prompt_file": str(PROMPT_FILE),
            "requester_config": str(REQUESTER_CONFIG),
        },
        "network_profiles": network_profiles,
        "constraints": {
            "alpha_fpr_max": 0.10,
            "beta_tpr_min": 0.90,
        },
        "placements": placements,
        "workloads": workloads,
        "policy_weights": {
            "failure_penalty": 850.0,
            "network_penalty_factor": 0.35,
            "width_penalty": 30.0,
            "workload_penalty": 0.03,
            "risk_penalty": 750.0,
            "challenge_penalty": 320.0,
            "efficacy_weight": 75.0,
        },
        "notes": (
            "Measured-profile E5 inputs use the verification profile matrix. "
            "Placement options differ both by pair and verifier signature."
        ),
    }
    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
