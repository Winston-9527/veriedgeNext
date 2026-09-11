from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run measured-profile E5 policy replay")
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--owner", required=True)
    return parser.parse_args()


def _write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _placement_latency_ms(task: Dict[str, Any], placement: Dict[str, Any]) -> float:
    chars = float(task["prompt_chars"])
    base = float(placement["base_fixed_ms"]) + chars * float(placement["per_char_ms"])
    coordination = max(int(placement["group_width"]) - 1, 0) * (12.0 + 0.45 * float(placement["network_rtt_ms"]))
    network = 1.25 * float(placement["network_rtt_ms"]) if task["client_profile"] == "WAN" else 0.55 * float(placement["network_rtt_ms"])
    return base + coordination + network


def _success_probability(task: Dict[str, Any], placement: Dict[str, Any]) -> float:
    prob = float(placement["base_success"])
    required_width = int(task["required_width"])
    actual_width = int(placement["group_width"])
    if actual_width < required_width:
        prob -= 0.18 * (required_width - actual_width)
    elif actual_width > required_width:
        prob += 0.01 * min(actual_width - required_width, 2)
    if task["client_profile"] != placement["network"]:
        prob -= 0.025
    prob -= float(placement["network_loss_pct"]) * 0.012
    return max(0.40, min(0.995, prob))


def _candidates(task: Dict[str, Any], placements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if task["client_profile"] == "LAN":
        return [placement for placement in placements if placement["network"] == "LAN"]
    return [placement for placement in placements if placement["network"] == "WAN"]


def _score_cost_only(task: Dict[str, Any], placement: Dict[str, Any]) -> float:
    return _placement_latency_ms(task, placement)


def _score_reputation(task: Dict[str, Any], placement: Dict[str, Any], weights: Dict[str, float]) -> float:
    return _score_cost_only(task, placement) + (1.0 - _success_probability(task, placement)) * float(weights["failure_penalty"])


def _score_network(task: Dict[str, Any], placement: Dict[str, Any], weights: Dict[str, float]) -> float:
    width_penalty = max(int(placement["group_width"]) - int(task["required_width"]), 0) * float(weights["width_penalty"])
    return _score_reputation(task, placement, weights) + float(placement["network_rtt_ms"]) * float(weights["network_penalty_factor"]) + width_penalty


def _score_verification(task: Dict[str, Any], placement: Dict[str, Any], weights: Dict[str, float]) -> float:
    verification_risk = float(placement["verification_risk"])
    false_dispute_risk = float(placement["false_dispute_risk"])
    risk_penalty = verification_risk * float(weights["risk_penalty"])
    challenge_cost = verification_risk * float(placement["challenge_latency_ms"])
    replay_cost = verification_risk * float(placement["reference_replay_runtime_ms"])
    workload_penalty = replay_cost * float(weights["workload_penalty"])
    dispute_penalty = false_dispute_risk * float(weights["challenge_penalty"])
    efficacy_credit = float(placement["material_tpr_min"]) * float(weights.get("efficacy_weight", 0.0))
    infeasible_penalty = 1000000.0 if int(placement["feasible_under_alpha_beta"]) == 0 else 0.0
    return (
        _score_network(task, placement, weights)
        + risk_penalty
        + challenge_cost
        + workload_penalty
        + dispute_penalty
        + infeasible_penalty
        - efficacy_credit
    )


def _select_random(task: Dict[str, Any], placements: List[Dict[str, Any]], rng: random.Random) -> Tuple[Dict[str, Any], str]:
    return rng.choice(_candidates(task, placements)), "random"


def _select_simple(policy: str, task: Dict[str, Any], placements: List[Dict[str, Any]], weights: Dict[str, float], rng: random.Random) -> Tuple[Dict[str, Any], str]:
    candidates = _candidates(task, placements)
    if policy == "cost_only":
        return min(candidates, key=lambda p: _score_cost_only(task, p)), "direct"
    if policy == "reputation_aware":
        return min(candidates, key=lambda p: _score_reputation(task, p, weights)), "direct"
    if policy == "network_aware":
        return min(candidates, key=lambda p: _score_network(task, p, weights)), "direct"
    raise ValueError(policy)


def _select_risk_constrained(task: Dict[str, Any], placements: List[Dict[str, Any]], weights: Dict[str, float]) -> Tuple[Dict[str, Any], str]:
    candidates = _candidates(task, placements)
    feasible = [p for p in candidates if int(p["feasible_under_alpha_beta"]) == 1]
    pool = feasible if feasible else candidates
    mode = "feasible_only" if feasible else "fallback_any"
    return min(pool, key=lambda p: _score_verification(task, p, weights)), mode


def _select_adaptive(task: Dict[str, Any], placements: List[Dict[str, Any]], weights: Dict[str, float]) -> Tuple[Dict[str, Any], str]:
    candidates = _candidates(task, placements)
    by_pair: Dict[str, List[Dict[str, Any]]] = {}
    for placement in candidates:
        by_pair.setdefault(str(placement["pair_id"]), []).append(placement)

    best_choice: Dict[str, Any] | None = None
    best_score = float("inf")
    best_mode = "adaptive"

    for pair_id, pair_candidates in by_pair.items():
        baseline = min(pair_candidates, key=lambda p: _score_network(task, p, weights))
        if int(baseline["feasible_under_alpha_beta"]) == 1:
            score = _score_network(task, baseline, weights)
            mode = "keep_baseline"
            chosen = baseline
        else:
            feasible_variants = [p for p in pair_candidates if int(p["feasible_under_alpha_beta"]) == 1]
            if feasible_variants:
                chosen = min(feasible_variants, key=lambda p: _score_verification(task, p, weights))
                score = _score_verification(task, chosen, weights)
                mode = "upgrade_verifier"
            else:
                chosen = min(pair_candidates, key=lambda p: _score_verification(task, p, weights))
                score = _score_verification(task, chosen, weights)
                mode = "fallback_unverifiable"

        if score < best_score:
            best_score = score
            best_choice = chosen
            best_mode = f"{mode}:{pair_id}"

    assert best_choice is not None
    return best_choice, best_mode


def _select(
    policy: str,
    task: Dict[str, Any],
    placements: List[Dict[str, Any]],
    weights: Dict[str, float],
    rng: random.Random,
) -> Tuple[Dict[str, Any], str]:
    if policy == "random":
        return _select_random(task, placements, rng)
    if policy in {"cost_only", "reputation_aware", "network_aware"}:
        return _select_simple(policy, task, placements, weights, rng)
    if policy == "risk_constrained":
        return _select_risk_constrained(task, placements, weights)
    if policy == "adaptive_verifier":
        return _select_adaptive(task, placements, weights)
    raise ValueError(policy)


def _run_policy_for_workload(
    policy: str,
    workload: Dict[str, Any],
    placements: List[Dict[str, Any]],
    weights: Dict[str, float],
    rng_seed: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rng = random.Random(rng_seed)
    busy_until: Dict[str, float] = {placement["placement_id"]: 0.0 for placement in placements}
    per_task: List[Dict[str, Any]] = []

    completion_sum = 0.0
    success_count = 0
    challenge_count = 0
    verifier_workload_sum = 0.0
    utility_sum = 0.0
    width_sum = 0.0
    false_dispute_risk_sum = 0.0
    unverifiable_count = 0
    infeasible_count = 0
    high_risk_count = 0
    low_risk_count = 0
    medium_risk_count = 0
    last_completion = 0.0

    for task in workload["tasks"]:
        placement, decision_mode = _select(policy, task, placements, weights, rng)
        arrival_s = float(task["arrival_s"])
        base_latency_s = _placement_latency_ms(task, placement) / 1000.0
        queue_wait_s = max(0.0, busy_until[placement["placement_id"]] - arrival_s)
        challenge = rng.random() < float(placement["verification_risk"])
        success = rng.random() < _success_probability(task, placement)
        verifier_workload_ms = (
            float(placement["reference_replay_runtime_ms"])
            + (float(placement["challenge_latency_ms"]) if challenge else 0.0)
        )
        completion_s = arrival_s + queue_wait_s + base_latency_s
        busy_until[placement["placement_id"]] = completion_s

        completion_sum += completion_s - arrival_s
        success_count += int(success)
        challenge_count += int(challenge)
        verifier_workload_sum += verifier_workload_ms
        width_sum += float(placement["group_width"])
        false_dispute_risk_sum += float(placement["false_dispute_risk"])
        last_completion = max(last_completion, completion_s)

        risk_class = str(placement["risk_class"])
        feasible = int(placement["feasible_under_alpha_beta"])
        if feasible == 0:
            infeasible_count += 1
        if risk_class == "unverifiable":
            unverifiable_count += 1
        elif risk_class == "high-risk":
            high_risk_count += 1
        elif risk_class == "medium-risk":
            medium_risk_count += 1
        elif risk_class == "low-risk":
            low_risk_count += 1

        utility = (
            (1.0 if success else 0.0)
            - 0.15 * challenge
            - 0.02 * queue_wait_s
            - 0.10 * float(placement["false_dispute_risk"])
        )
        utility_sum += utility

        per_task.append(
            {
                "workload_id": workload["workload_id"],
                "policy": policy,
                "task_id": task["task_id"],
                "client_profile": task["client_profile"],
                "required_width": task["required_width"],
                "placement_id": placement["placement_id"],
                "placement_label": placement["label"],
                "pair_id": placement["pair_id"],
                "variant": placement["variant"],
                "decision_mode": decision_mode,
                "risk_class": placement["risk_class"],
                "group_width": placement["group_width"],
                "arrival_s": round(arrival_s, 6),
                "queue_wait_s": round(queue_wait_s, 6),
                "task_latency_s": round(base_latency_s + queue_wait_s, 6),
                "success": int(success),
                "challenge": int(challenge),
                "verification_risk": round(float(placement["verification_risk"]), 6),
                "false_dispute_risk": round(float(placement["false_dispute_risk"]), 6),
                "material_tpr_min": round(float(placement["material_tpr_min"]), 6),
                "feasible_under_alpha_beta": int(placement["feasible_under_alpha_beta"]),
                "verifier_workload_ms": round(verifier_workload_ms, 6),
                "completion_utility": round(utility, 6),
            }
        )

    task_count = len(per_task)
    goodput = success_count / max(last_completion, 1e-9)
    mean_false_dispute_risk = false_dispute_risk_sum / task_count if task_count else 0.0
    summary = {
        "workload_id": workload["workload_id"],
        "policy": policy,
        "task_count": task_count,
        "mean_task_latency_s": round(completion_sum / task_count, 6),
        "success_rate": round(success_count / task_count, 6),
        "challenge_rate": round(challenge_count / task_count, 6),
        "mean_verifier_workload_ms_per_task": round(verifier_workload_sum / task_count, 6),
        "goodput_success_per_s": round(goodput, 6),
        "false_dispute_risk": round(mean_false_dispute_risk, 6),
        "unverifiable_placement_rate": round(unverifiable_count / task_count, 6),
        "infeasible_under_alpha_beta_rate": round(infeasible_count / task_count, 6),
        "high_risk_placement_rate": round(high_risk_count / task_count, 6),
        "medium_risk_placement_rate": round(medium_risk_count / task_count, 6),
        "low_risk_placement_rate": round(low_risk_count / task_count, 6),
        "risk_adjusted_goodput": round(goodput * (1.0 - mean_false_dispute_risk), 6),
        "mean_completion_utility": round(utility_sum / task_count, 6),
        "average_group_width": round(width_sum / task_count, 6),
    }
    return per_task, summary


def main() -> None:
    args = _parse_args()
    payload = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    policies = [
        "random",
        "cost_only",
        "reputation_aware",
        "network_aware",
        "risk_constrained",
        "adaptive_verifier",
    ]
    placements = list(payload["placements"])
    weights = dict(payload["policy_weights"])

    all_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    base_seed = int(payload["seed"])
    for workload_idx, workload in enumerate(payload["workloads"]):
        for policy_idx, policy in enumerate(policies):
            rows, summary = _run_policy_for_workload(
                policy,
                workload,
                placements,
                weights,
                rng_seed=base_seed + workload_idx * 101 + policy_idx * 17,
            )
            all_rows.extend(rows)
            summary_rows.append(summary)

    stamp = time.strftime("%Y%m%d")
    per_task_path = output_dir / f"exp_e5_{stamp}_{args.owner}_per_task.csv"
    summary_path = output_dir / f"exp_e5_{stamp}_{args.owner}_policy_compare.csv"
    config_path = output_dir / f"exp_e5_{stamp}_{args.owner}_policy_config.json"

    _write_csv(
        per_task_path,
        all_rows,
        [
            "workload_id",
            "policy",
            "task_id",
            "client_profile",
            "required_width",
            "placement_id",
            "placement_label",
            "pair_id",
            "variant",
            "decision_mode",
            "risk_class",
            "group_width",
            "arrival_s",
            "queue_wait_s",
            "task_latency_s",
            "success",
            "challenge",
            "verification_risk",
            "false_dispute_risk",
            "material_tpr_min",
            "feasible_under_alpha_beta",
            "verifier_workload_ms",
            "completion_utility",
        ],
    )
    _write_csv(
        summary_path,
        summary_rows,
        [
            "workload_id",
            "policy",
            "task_count",
            "mean_task_latency_s",
            "success_rate",
            "challenge_rate",
            "mean_verifier_workload_ms_per_task",
            "goodput_success_per_s",
            "false_dispute_risk",
            "unverifiable_placement_rate",
            "infeasible_under_alpha_beta_rate",
            "high_risk_placement_rate",
            "medium_risk_placement_rate",
            "low_risk_placement_rate",
            "risk_adjusted_goodput",
            "mean_completion_utility",
            "average_group_width",
        ],
    )
    config_path.write_text(
        json.dumps(
            {
                "seed": payload["seed"],
                "source": payload["source"],
                "network_profiles": payload["network_profiles"],
                "constraints": payload["constraints"],
                "placements": payload["placements"],
                "workloads": [{"workload_id": w["workload_id"], "description": w["description"]} for w in payload["workloads"]],
                "policy_weights": payload["policy_weights"],
                "policy_order": policies,
                "notes": "Measured-profile E5 replay uses per-placement verification profiles and supports risk-constrained / adaptive-verifier policies.",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(per_task_path)
    print(summary_path)
    print(config_path)


if __name__ == "__main__":
    main()
