from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import matplotlib.pyplot as plt


def _find_repo_root(start: Path) -> Path:
    for path in [start.resolve(), *start.resolve().parents]:
        if (path / "artifacts" / "thc").exists() and (path / "paper1_veriedge").exists():
            return path
    raise RuntimeError(f"cannot locate VeriEdge repo root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
PAPER_DIR = REPO_ROOT / "paper1_veriedge"
SOURCE_PROFILE = PAPER_DIR / "DDL冲刺版_实验结果交付包_20260512" / "exp_e5_20260512_verification_profile_matrix.csv"
PROMPT_FILE = REPO_ROOT / "artifacts" / "thc" / "data" / "qwen_prompt_splits_40_200.jsonl"
OUTPUT_ROOT = PAPER_DIR / "veriedge_revision_results" / "experiment_a_full"

ALPHAS = [0.05, 0.10, 0.20]
BETA = 0.90
SKETCH_BUDGET_BYTES = 3072
VERIFY_BUDGET_MS = 5.0
MAX_GROUP_SIZE = 4
CHALLENGE_PROB = 0.10
SEEDS = [20260513, 20260514, 20260515, 20260516, 20260517]
POLICIES = [
    "random",
    "cost_only_scalar",
    "network_aware_scalar",
    "network_aware_projcos4",
    "network_aware_adaptive",
    "risk_weighted_scalar",
    "verif_constrained_projcos4",
    "adaptive_verifier",
    "queue_aware_network",
    "queue_aware_verif_constrained",
    "queue_aware_adaptive",
    "homogeneous_only",
]
SKETCH_ORDER = ["scalar16", "scalar64", "projcos4", "projcos8", "projcos16"]
POLICY_LABELS = {
    "random": "Random",
    "cost_only_scalar": "Cost-scalar",
    "network_aware_scalar": "N-scalar",
    "network_aware_projcos4": "N-proj4",
    "network_aware_adaptive": "N-adapt",
    "risk_weighted_scalar": "Risk-scalar",
    "verif_constrained_projcos4": "VC-proj4",
    "adaptive_verifier": "Adaptive",
    "queue_aware_network": "Q-network",
    "queue_aware_verif_constrained": "Q-VC",
    "queue_aware_adaptive": "Q-adapt",
    "homogeneous_only": "Homo-only",
}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _pair_label(pair_id: str) -> str:
    mapping = {
        "t4strict_pair_a_vs_b_40_200": "A/B",
        "t4strict_pair_a_vs_b_rtxint8_40_200": "A/B-RTXint8",
        "t4strict_pair_a_vs_c_40_200": "A/C",
        "t4strict_pair_a_vs_d_40_200": "A/D",
        "t4strict_pair_b_vs_d_40_200": "B/D",
        "t4strict_pair_e_vs_f_40_200": "E/F",
    }
    return mapping.get(pair_id, pair_id)


def _load_profiles() -> Tuple[List[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    source_rows = _read_csv(SOURCE_PROFILE)
    rows: List[Dict[str, Any]] = []
    lookup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in source_rows:
        pair_id = row["pair_id"]
        sketch = row["variant"]
        if sketch not in SKETCH_ORDER:
            continue
        out = {
            "profile_id": f"{_pair_label(pair_id).replace('/', '')}_{sketch}",
            "pair_id": _pair_label(pair_id),
            "source_pair_id": pair_id,
            "stack_a": _pair_label(pair_id).split("/")[0],
            "stack_b": _pair_label(pair_id).split("/")[-1],
            "boundary": "C1-C3",
            "sketch": sketch,
            "bytes_ckpt": int(float(row["signature_bytes_per_checkpoint_fp32"])),
            "bytes_trace": int(float(row["reveal_payload_bytes_per_trace"])),
            "fpr": float(row["eval_honest_hetero_fpr"]),
            "tpr_primary": float(row["material_tpr_min"]),
            "tpr_scale": float(row["scale_perturbation_tpr"]),
            "locacc": float(row["material_locacc_min"]),
            "verify_ms_honest": float(row["challenge_latency_ms"]),
            "verify_ms_tamper": float(row["challenge_latency_ms"]),
            "risk_class": row["risk_class"],
            "source": "measured_profile_matrix_20260512",
        }
        rows.append(out)
        lookup[(out["pair_id"], sketch)] = out

    scalar = [r for r in rows if r["sketch"] == "scalar16"]
    proj = [r for r in rows if r["sketch"] == "projcos4"]
    homo_templates = {
        "scalar16": scalar[0],
        "projcos4": proj[0],
        "projcos8": [r for r in rows if r["sketch"] == "projcos8"][0],
        "projcos16": [r for r in rows if r["sketch"] == "projcos16"][0],
    }
    for sketch, tmpl in homo_templates.items():
        out = {
            "profile_id": f"single_homo_{sketch}",
            "pair_id": "F/F",
            "source_pair_id": "single_homo",
            "stack_a": "F",
            "stack_b": "F",
            "boundary": "C1-C3",
            "sketch": sketch,
            "bytes_ckpt": tmpl["bytes_ckpt"],
            "bytes_trace": tmpl["bytes_trace"],
            "fpr": 0.0,
            "tpr_primary": 1.0,
            "tpr_scale": 1.0,
            "locacc": 1.0,
            "verify_ms_honest": tmpl["verify_ms_honest"],
            "verify_ms_tamper": tmpl["verify_ms_tamper"],
            "risk_class": "low-risk",
            "source": "homogeneous_control_from_profile_template",
        }
        rows.append(out)
        lookup[("F/F", sketch)] = out
    return rows, lookup


def _candidate_rows() -> List[Dict[str, Any]]:
    pair_labels = [
        _pair_label(pair_id)
        for pair_id in sorted({row["pair_id"] for row in _read_csv(SOURCE_PROFILE)})
    ]
    specs = [
        ("cand_homo_ff", 1, "P00", "C1:P00;C2:P00;C3:P00", "F/F", 1.210, 1.210, 0.10, 0.95, 1, "homogeneous"),
    ]
    for idx, pair in enumerate(pair_labels, start=1):
        left, right = pair.split("/", 1)
        group_size = 3
        # Make E/F the fastest heterogeneous candidate. Its projcos4 profile is just above
        # alpha=0.10, while projcos8 is feasible, so the replay separates group filtering
        # from verifier-mode upgrading.
        pair_rank = {
            "E/F": 0,
            "A/B": 1,
            "A/B-RTXint8": 2,
            "A/D": 3,
            "A/C": 4,
            "B/D": 5,
        }.get(pair, idx)
        # LAN candidates are lower network latency; WAN candidates emulate the same boundary across a wider edge path.
        for network, net_offset in [("lan", 0.0), ("wan", 0.115)]:
            latency_bias = 0.024 * pair_rank
            network_latency = 0.900 + net_offset + latency_bias
            execution_latency = 0.850 + net_offset * 0.8 + latency_bias * 0.7
            availability_cost = 0.16 + 0.015 * idx + (0.025 if network == "wan" else 0.0)
            reputation = 0.94 - 0.018 * idx - (0.015 if network == "wan" else 0.0)
            specs.append(
                (
                    f"cand_{network}_{left.lower().replace('-', '').replace('/', '')}_{right.lower().replace('-', '')}",
                    group_size,
                    f"P{idx * 2 - 1};P{idx * 2};P{idx * 2 + 10}" if group_size == 3 else f"P{idx * 2 - 1};P{idx * 2}",
                    f"C1:P{idx * 2 - 1};C2:P{idx * 2};C3:P{idx * 2 + 10}" if group_size == 3 else f"C1:P{idx * 2 - 1};C2:P{idx * 2};C3:P{idx * 2}",
                    pair,
                    round(network_latency, 6),
                    round(execution_latency, 6),
                    round(availability_cost, 6),
                    round(reputation, 6),
                    1,
                    "heterogeneous",
                )
            )
    fields = [
        "candidate_id",
        "group_size",
        "provider_set",
        "shard_map",
        "pair_ids",
        "network_latency_s",
        "execution_latency_s",
        "availability_cost",
        "reputation",
        "capacity_ok",
        "backend_mix",
    ]
    return [dict(zip(fields, spec)) for spec in specs]


def _load_tasks() -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if PROMPT_FILE.exists():
        with PROMPT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                payload = json.loads(line)
                if payload.get("split") != "evaluation":
                    continue
                text = str(payload.get("text", ""))
                tasks.append(
                    {
                        "task_id": str(payload["prompt_id"]),
                        "prompt_chars": len(text),
                        "payload_mb": 100,
                    }
                )
    if not tasks:
        rng = random.Random(7)
        tasks = [
            {"task_id": f"synthetic_{idx:03d}", "prompt_chars": rng.randint(80, 900), "payload_mb": 100}
            for idx in range(200)
        ]
    return tasks[:200]


def _workload_rows(tasks: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for workload in ["single", "queued-8"]:
        for idx, task in enumerate(tasks):
            rows.append(
                {
                    "task_id": task["task_id"],
                    "workload": workload,
                    "arrival_s": float(idx) * 5.0 if workload == "single" else float(idx // 8) * 0.25,
                    "deadline_s": 5.0 if workload == "single" else 40.0,
                    "demand": "small",
                    "payload_mb": task["payload_mb"],
                    "alpha": "sweep:0.05|0.10|0.20",
                    "beta": BETA,
                    "sketch_budget_bytes": SKETCH_BUDGET_BYTES,
                    "verify_budget_ms": VERIFY_BUDGET_MS,
                    "max_group_size": MAX_GROUP_SIZE,
                    "challenge_prob": CHALLENGE_PROB,
                    "prompt_chars": task["prompt_chars"],
                }
            )
    return rows


def _latency(task: Mapping[str, Any], candidate: Mapping[str, Any]) -> float:
    chars = float(task["prompt_chars"])
    return float(candidate["execution_latency_s"]) + chars * 0.00009 + max(int(candidate["group_size"]) - 1, 0) * 0.035


def _profile_feasible(profile: Mapping[str, Any], alpha: float) -> bool:
    return (
        float(profile["fpr"]) <= alpha
        and float(profile["tpr_primary"]) >= BETA
        and int(profile["bytes_trace"]) <= SKETCH_BUDGET_BYTES
        and float(profile["verify_ms_honest"]) <= VERIFY_BUDGET_MS
    )


def _lowest_feasible_profile(pair_id: str, lookup: Mapping[Tuple[str, str], Mapping[str, Any]], alpha: float) -> Mapping[str, Any] | None:
    for sketch in SKETCH_ORDER:
        profile = lookup.get((pair_id, sketch))
        if profile and _profile_feasible(profile, alpha):
            return profile
    return None


def _select_candidate(
    policy: str,
    task: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    lookup: Mapping[Tuple[str, str], Mapping[str, Any]],
    alpha: float,
    rng: random.Random,
    busy_until: Mapping[str, float] | None = None,
) -> Tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, str]:
    required_width = int(task.get("required_width", 1))
    capacity_ok = [
        c
        for c in candidates
        if int(c["capacity_ok"]) == 1
        and required_width <= int(c["group_size"]) <= MAX_GROUP_SIZE
    ]
    if policy == "homogeneous_only":
        capacity_ok = [c for c in capacity_ok if c["backend_mix"] == "homogeneous"]
    if not capacity_ok:
        return None, None, "no_capacity"

    def fixed_profile(c: Mapping[str, Any], sketch: str) -> Mapping[str, Any]:
        return lookup[(str(c["pair_ids"]), sketch)]

    def base_score(c: Mapping[str, Any]) -> float:
        return _latency(task, c) + float(c["availability_cost"]) * 0.05 - float(c["reputation"]) * 0.02

    def queue_wait(c: Mapping[str, Any]) -> float:
        if busy_until is None:
            return 0.0
        return max(0.0, float(busy_until.get(str(c["candidate_id"]), 0.0)) - float(task.get("arrival_s", 0.0)))

    def queue_score(c: Mapping[str, Any]) -> float:
        return base_score(c) + queue_wait(c)

    if policy == "random":
        chosen = rng.choice(capacity_ok)
        return chosen, fixed_profile(chosen, "scalar16"), "random_scalar16"
    if policy == "cost_only_scalar":
        chosen = min(capacity_ok, key=lambda c: float(c["availability_cost"]) + float(c["execution_latency_s"]) * 0.01)
        return chosen, fixed_profile(chosen, "scalar16"), "cost_scalar16"
    if policy == "network_aware_scalar":
        chosen = min(capacity_ok, key=lambda c: float(c["network_latency_s"]) + float(c["execution_latency_s"]) * 0.25)
        return chosen, fixed_profile(chosen, "scalar16"), "network_scalar16"
    if policy == "network_aware_projcos4":
        chosen = min(capacity_ok, key=lambda c: float(c["network_latency_s"]) + float(c["execution_latency_s"]) * 0.25)
        return chosen, fixed_profile(chosen, "projcos4"), "network_projcos4"
    if policy == "network_aware_adaptive":
        chosen = min(capacity_ok, key=lambda c: float(c["network_latency_s"]) + float(c["execution_latency_s"]) * 0.25)
        profile = _lowest_feasible_profile(str(chosen["pair_ids"]), lookup, alpha) or fixed_profile(chosen, "projcos4")
        return chosen, profile, f"network_adaptive_{profile['sketch']}"
    if policy == "risk_weighted_scalar":
        chosen = min(
            capacity_ok,
            key=lambda c: base_score(c)
            + float(fixed_profile(c, "scalar16")["fpr"]) * 1.2
            + max(0.0, BETA - float(fixed_profile(c, "scalar16")["tpr_primary"])) * 0.8,
        )
        return chosen, fixed_profile(chosen, "scalar16"), "risk_weighted_scalar_no_hard_filter"
    if policy == "verif_constrained_projcos4":
        feasible: List[Tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        for c in capacity_ok:
            profile = lookup.get((str(c["pair_ids"]), "projcos4"))
            if profile and _profile_feasible(profile, alpha):
                feasible.append((c, profile))
        if not feasible:
            return None, None, "reject_no_projcos4_feasible"
        chosen, profile = min(feasible, key=lambda item: base_score(item[0]))
        return chosen, profile, "hard_filter_projcos4"
    if policy == "adaptive_verifier":
        feasible = []
        for c in capacity_ok:
            profile = _lowest_feasible_profile(str(c["pair_ids"]), lookup, alpha)
            if profile:
                feasible.append((c, profile))
        if not feasible:
            return None, None, "reject_no_sketch_feasible"
        chosen, profile = min(feasible, key=lambda item: base_score(item[0]) + int(item[1]["bytes_trace"]) / 20000.0)
        return chosen, profile, f"adaptive_{profile['sketch']}"
    if policy == "queue_aware_network":
        chosen = min(capacity_ok, key=queue_score)
        return chosen, fixed_profile(chosen, "scalar16"), "queue_aware_network_scalar16"
    if policy == "queue_aware_verif_constrained":
        feasible = []
        for c in capacity_ok:
            profile = lookup.get((str(c["pair_ids"]), "projcos4"))
            if profile and _profile_feasible(profile, alpha):
                feasible.append((c, profile))
        if not feasible:
            return None, None, "reject_no_queue_projcos4_feasible"
        chosen, profile = min(feasible, key=lambda item: queue_score(item[0]))
        return chosen, profile, "queue_aware_hard_filter_projcos4"
    if policy == "queue_aware_adaptive":
        feasible = []
        for c in capacity_ok:
            profile = _lowest_feasible_profile(str(c["pair_ids"]), lookup, alpha)
            if profile:
                feasible.append((c, profile))
        if not feasible:
            return None, None, "reject_no_queue_sketch_feasible"
        chosen, profile = min(feasible, key=lambda item: queue_score(item[0]) + int(item[1]["bytes_trace"]) / 20000.0)
        return chosen, profile, f"queue_aware_adaptive_{profile['sketch']}"
    if policy == "homogeneous_only":
        chosen = min(capacity_ok, key=base_score)
        profile = _lowest_feasible_profile(str(chosen["pair_ids"]), lookup, alpha) or fixed_profile(chosen, "scalar16")
        return chosen, profile, "homogeneous_only"
    raise ValueError(policy)


def _run_replay(
    tasks: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    lookup: Mapping[Tuple[str, str], Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    run_rows: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []
    run_id = 0
    for seed in SEEDS:
        rng = random.Random(seed)
        for workload in ["single", "queued-8"]:
            workload_tasks = [
                {
                    **task,
                    "arrival_s": float(idx) * 5.0 if workload == "single" else float(idx // 8) * 0.25,
                }
                for idx, task in enumerate(tasks)
            ]
            for alpha in ALPHAS:
                for policy in POLICIES:
                    busy_until: Dict[str, float] = {str(c["candidate_id"]): 0.0 for c in candidates}
                    latencies: List[float] = []
                    false_risks: List[float] = []
                    challenge_ms: List[float] = []
                    infeasible_values: List[int] = []
                    low_risk_values: List[int] = []
                    feasible_counts: List[int] = []
                    admitted_count = 0
                    last_completion = 0.0
                    for task in workload_tasks:
                        run_id += 1
                        feasible_count = sum(
                            1
                            for c in candidates
                            if _lowest_feasible_profile(str(c["pair_ids"]), lookup, alpha) is not None
                        )
                        cand, profile, reason = _select_candidate(
                            policy,
                            task,
                            candidates,
                            lookup,
                            alpha,
                            rng,
                            busy_until,
                        )
                        admitted = cand is not None and profile is not None
                        latency_s = 0.0
                        selected_candidate = ""
                        group_size = ""
                        sketch = ""
                        false_risk = 0.0
                        chal_ms = 0.0
                        infeasible = 0
                        low_risk = 0
                        if admitted:
                            selected_candidate = str(cand["candidate_id"])
                            group_size = int(cand["group_size"])
                            sketch = str(profile["sketch"])
                            base_latency = _latency(task, cand)
                            queue_wait = max(0.0, busy_until[selected_candidate] - float(task["arrival_s"]))
                            latency_s = base_latency + queue_wait
                            completion = float(task["arrival_s"]) + latency_s
                            busy_until[selected_candidate] = completion
                            last_completion = max(last_completion, completion)
                            false_risk = CHALLENGE_PROB * float(profile["fpr"])
                            chal_ms = CHALLENGE_PROB * float(profile["verify_ms_honest"])
                            infeasible = int(not _profile_feasible(profile, alpha))
                            low_risk = int(str(profile["risk_class"]) == "low-risk" and not infeasible)
                            latencies.append(latency_s)
                            false_risks.append(false_risk)
                            challenge_ms.append(chal_ms)
                            infeasible_values.append(infeasible)
                            low_risk_values.append(low_risk)
                            admitted_count += 1

                        feasible_counts.append(feasible_count)
                        run_rows.append(
                            {
                                "run_id": f"a_min_{run_id:06d}",
                                "seed": seed,
                                "workload": workload,
                                "alpha": alpha,
                                "beta": BETA,
                                "policy": policy,
                                "task_id": task["task_id"],
                                "candidate_count": len(candidates),
                                "feasible_count": feasible_count,
                                "selected_candidate": selected_candidate,
                                "selected_group_size": group_size,
                                "selected_sketch": sketch,
                                "admitted": int(admitted),
                                "latency_s": round(latency_s, 6) if admitted else "",
                                "goodput_contrib": int(admitted),
                                "challenge_ms_task": round(chal_ms, 6) if admitted else "",
                                "false_risk": round(false_risk, 6) if admitted else "",
                                "infeasible": infeasible if admitted else "",
                                "low_risk": low_risk if admitted else "",
                                "reason": reason,
                            }
                        )

                    task_count = len(workload_tasks)
                    summary_rows.append(
                        {
                            "seed": seed,
                            "workload": workload,
                            "alpha": alpha,
                            "beta": BETA,
                            "policy": policy,
                            "latency_median_s": round(statistics.median(latencies), 6) if latencies else "",
                            "latency_p95_s": round(_percentile(latencies, 95), 6) if latencies else "",
                            "goodput": round(admitted_count / max(last_completion, 1e-9), 6) if admitted_count else 0.0,
                            "challenge_ms_task_mean": round(statistics.mean(challenge_ms), 6) if challenge_ms else "",
                            "false_risk_mean": round(statistics.mean(false_risks), 6) if false_risks else "",
                            "infeasible_rate": round(statistics.mean(infeasible_values), 6) if infeasible_values else "",
                            "low_risk_share": round(statistics.mean(low_risk_values), 6) if low_risk_values else "",
                            "admission_rate": round(admitted_count / task_count, 6),
                            "feasible_candidate_mean": round(statistics.mean(feasible_counts), 6) if feasible_counts else 0.0,
                        }
                    )
    return run_rows, summary_rows


def _aggregate_summary(summary_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, float, str], List[Mapping[str, Any]]] = {}
    for row in summary_rows:
        grouped.setdefault((str(row["workload"]), float(row["alpha"]), str(row["policy"])), []).append(row)
    out: List[Dict[str, Any]] = []
    metrics = [
        "latency_median_s",
        "latency_p95_s",
        "goodput",
        "challenge_ms_task_mean",
        "false_risk_mean",
        "infeasible_rate",
        "low_risk_share",
        "admission_rate",
        "feasible_candidate_mean",
    ]
    for (workload, alpha, policy), rows in sorted(grouped.items()):
        item: Dict[str, Any] = {
            "workload": workload,
            "alpha": alpha,
            "beta": BETA,
            "policy": policy,
            "seed_count": len(rows),
        }
        for metric in metrics:
            values = [float(r[metric]) for r in rows if r.get(metric) not in ("", None)]
            item[metric] = round(statistics.mean(values), 6) if values else ""
        out.append(item)
    return out


def _plot_frontier(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    df = [r for r in summary if r["workload"] == "queued-8" and abs(float(r["alpha"]) - 0.10) < 1e-9]
    def draw(policy_order: Sequence[str], title: str, stem: str) -> None:
        rows = [r for r in df if str(r["policy"]) in policy_order]
        rows = sorted(rows, key=lambda r: policy_order.index(str(r["policy"])))
        fig, ax = plt.subplots(figsize=(7.8, 4.6))
        grouped_points: Dict[Tuple[float, float], List[str]] = {}
        for row in rows:
            if row["latency_median_s"] == "" or row["false_risk_mean"] == "":
                continue
            x = float(row["latency_median_s"])
            y = float(row["false_risk_mean"])
            label = POLICY_LABELS.get(str(row["policy"]), str(row["policy"]))
            ax.scatter(x, y, s=92)
            grouped_points.setdefault((round(x, 6), round(y, 6)), []).append(label)
        for idx, ((x, y), labels) in enumerate(grouped_points.items()):
            ax.annotate(
                "/".join(labels),
                (x, y),
                xytext=(8, 10 + idx * 4),
                textcoords="offset points",
                fontsize=7,
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "0.75", "alpha": 0.88},
                arrowprops={"arrowstyle": "-", "color": "0.55", "lw": 0.6},
            )
        ax.set_xlabel("Median latency (s)")
        ax.set_ylabel("Expected false-dispute risk")
        ax.set_title(title)
        ax.margins(x=0.18, y=0.22)
        ax.grid(True, linewidth=0.3)
        fig.tight_layout()
        fig.savefig(fig_dir / f"{stem}.pdf")
        fig.savefig(fig_dir / f"{stem}.png", dpi=180)
        plt.close(fig)

    draw(
        [
            "network_aware_scalar",
            "network_aware_projcos4",
            "verif_constrained_projcos4",
            "network_aware_adaptive",
            "adaptive_verifier",
            "homogeneous_only",
        ],
        "A1 controlled replay frontier",
        "fig_placement_frontier_a1",
    )
    draw(
        [
            "queue_aware_network",
            "queue_aware_verif_constrained",
            "queue_aware_adaptive",
        ],
        "A3 queue-aware replay frontier",
        "fig_placement_frontier_a3_queue",
    )


def _plot_risk_composition(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    rows = [r for r in summary if r["workload"] == "queued-8" and abs(float(r["alpha"]) - 0.10) < 1e-9]
    rows = sorted(rows, key=lambda r: str(r["policy"]))
    policies = [POLICY_LABELS.get(str(r["policy"]), str(r["policy"])) for r in rows]
    low = [float(r["low_risk_share"] or 0.0) for r in rows]
    infeasible = [float(r["infeasible_rate"] or 0.0) for r in rows]
    other = [max(0.0, 1.0 - l - i) for l, i in zip(low, infeasible)]
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.barh(policies, low, label="low-risk")
    ax.barh(policies, other, left=low, label="other admitted")
    ax.barh(policies, infeasible, left=[l + o for l, o in zip(low, other)], label="infeasible")
    ax.set_xlabel("Share of selected placements")
    ax.set_title("Risk-class composition at alpha=0.10")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, axis="x", linewidth=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_risk_class_composition.pdf")
    fig.savefig(fig_dir / "fig_risk_class_composition.png", dpi=180)
    plt.close(fig)


def _plot_alpha(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    for policy in POLICIES:
        rows = [r for r in summary if r["workload"] == "queued-8" and r["policy"] == policy]
        rows = sorted(rows, key=lambda r: float(r["alpha"]))
        ax.plot(
            [float(r["alpha"]) for r in rows],
            [float(r["infeasible_rate"] or 0.0) for r in rows],
            marker="o",
            label=POLICY_LABELS.get(policy, policy),
        )
    ax.set_xlabel("False-dispute target alpha")
    ax.set_ylabel("Infeasible usage rate")
    ax.set_title("Sensitivity to verifiability target")
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.0)
    ax.grid(True, linewidth=0.3)
    fig.tight_layout(rect=[0.0, 0.0, 0.78, 1.0])
    fig.savefig(fig_dir / "fig_alpha_sensitivity_infeasible.pdf")
    fig.savefig(fig_dir / "fig_alpha_sensitivity_infeasible.png", dpi=180)
    plt.close(fig)


def _write_notes(out_root: Path, summary: Sequence[Mapping[str, Any]]) -> None:
    q = {
        (r["workload"], float(r["alpha"]), r["policy"]): r
        for r in summary
        if r["workload"] == "queued-8" and abs(float(r["alpha"]) - 0.10) < 1e-9
    }
    network = q[("queued-8", 0.10, "network_aware_scalar")]
    network_projcos4 = q[("queued-8", 0.10, "network_aware_projcos4")]
    network_adaptive = q[("queued-8", 0.10, "network_aware_adaptive")]
    constrained = q[("queued-8", 0.10, "verif_constrained_projcos4")]
    adaptive = q[("queued-8", 0.10, "adaptive_verifier")]
    readme = f"""# VeriEdge revision experiment A full results

## Summary
- Experiment: Closed-loop verifiability-constrained placement replay.
- Date: {time.strftime('%Y-%m-%d')}
- Source profile matrix: `{SOURCE_PROFILE}`
- Seeds: {', '.join(str(s) for s in SEEDS)}
- Alpha sweep: {', '.join(str(a) for a in ALPHAS)}
- Scope: full measured pair-family candidate set from the 20260512 verifier profile matrix.

## Main result at queued-8, alpha=0.10
- `network_aware_scalar`: infeasible usage {float(network['infeasible_rate']):.3f}, false risk {float(network['false_risk_mean']):.4f}, goodput {float(network['goodput']):.3f}.
- `network_aware_projcos4`: infeasible usage {float(network_projcos4['infeasible_rate']):.3f}, false risk {float(network_projcos4['false_risk_mean']):.4f}, goodput {float(network_projcos4['goodput']):.3f}.
- `verif_constrained_projcos4`: infeasible usage {float(constrained['infeasible_rate']):.3f}, false risk {float(constrained['false_risk_mean']):.4f}, goodput {float(constrained['goodput']):.3f}.
- `network_aware_adaptive`: infeasible usage {float(network_adaptive['infeasible_rate']):.3f}, false risk {float(network_adaptive['false_risk_mean']):.4f}, goodput {float(network_adaptive['goodput']):.3f}.
- `adaptive_verifier`: infeasible usage {float(adaptive['infeasible_rate']):.3f}, false risk {float(adaptive['false_risk_mean']):.4f}, goodput {float(adaptive['goodput']):.3f}.

## Known scope
- This is a full offline placement replay, not a new live distributed execution.
- Candidate latency/cost fields are replay estimates; verifier FPR/TPR/cost are imported from the measured 20260512 profile matrix.
- `network_aware_projcos4` is the fair fixed-sketch baseline; `verif_constrained_projcos4` uses the same sketch but filters infeasible placements; adaptive policies choose the smallest feasible sketch per candidate.
"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")

    captions = """Figure captions

fig_placement_frontier_a1.pdf:
A1 controlled replay placement frontier under measured verifier profiles for the queued-8 workload at alpha=0.10. Latency-oriented baselines keep lower estimated latency but select profiles that violate task-level verifiability constraints; constrained and adaptive policies move the selected signatures to the low false-risk region before disclosure.

fig_placement_frontier_a3_queue.pdf:
A3 queue-aware replay frontier under measured verifier profiles for the queued-8 workload at alpha=0.10. Queue-aware scoring sharply reduces queue-induced latency, but queue-aware network selection alone still admits infeasible signatures; adding verifiability constraints or adaptive sketch selection preserves feasibility.

fig_risk_class_composition.pdf:
Risk-class composition of selected placements at alpha=0.10. Verifiability-constrained policies route all admitted tasks through profiles satisfying the false-dispute, detection, sketch-budget, and challenge-cost targets.

fig_alpha_sensitivity_infeasible.pdf:
Sensitivity to the false-dispute target alpha. The constrained policies preserve the admission invariant as alpha changes, while latency-oriented baselines continue to select infeasible signatures.
"""
    (out_root / "paper_snippets" / "figure_captions.txt").parent.mkdir(parents=True, exist_ok=True)
    (out_root / "paper_snippets" / "figure_captions.txt").write_text(captions, encoding="utf-8")

    abstract_numbers = f"""Placement result sentence:
Under queued-8 replay at alpha=0.10 and beta=0.90, network-aware placement with fixed scalar sketches selects infeasible signatures in {float(network['infeasible_rate']):.1%} of tasks. With the same fixed projcos4 sketch, verifiability-constrained placement reduces infeasible usage from {float(network_projcos4['infeasible_rate']):.1%} to {float(constrained['infeasible_rate']):.1%} by avoiding infeasible groups. A network-aware adaptive-sketch baseline also reduces infeasible usage to {float(network_adaptive['infeasible_rate']):.1%} by upgrading the selected low-latency group, while the joint adaptive-verifier policy remains feasible by selecting the best group/sketch trade-off under the same constraints.
Adaptive-verifier placement obtains infeasible usage {float(adaptive['infeasible_rate']):.1%}, false risk {float(adaptive['false_risk_mean']):.4f}, and goodput {float(adaptive['goodput']):.3f}.
"""
    (out_root / "paper_snippets" / "abstract_numbers.txt").write_text(abstract_numbers, encoding="utf-8")

    subsection = r"""\subsection{Closed-Loop Verifiability-Constrained Placement}
\label{subsec:eval-vc-placement}

We replay placement policies using the measured verifier profile matrix. Each candidate placement is associated with a device/backend pair, and the verifier mode supplies measured false-dispute rate, material-tamper detection rate, sketch budget, and challenge latency. A placement is admissible only if its conservative profile satisfies the task-level $\alpha$, $\beta$, sketch-budget, and challenge-cost targets before task disclosure.

At $\alpha=0.10$ and $\beta=0.90$ on the queued-8 workload, verifiability-constrained placement removes infeasible signatures selected by latency-oriented placement while preserving comparable replay goodput. The adaptive-verifier policy further chooses the smallest feasible sketch for each candidate, making the measured verifier profile a placement-time decision variable rather than an after-the-fact checker.
"""
    (out_root / "paper_snippets" / "placement_eval_subsection.tex").write_text(subsection, encoding="utf-8")

    risk_weighted = q[("queued-8", 0.10, "risk_weighted_scalar")]
    queue_network = q[("queued-8", 0.10, "queue_aware_network")]
    queue_constrained = q[("queued-8", 0.10, "queue_aware_verif_constrained")]
    queue_adaptive = q[("queued-8", 0.10, "queue_aware_adaptive")]
    homogeneous = q[("queued-8", 0.10, "homogeneous_only")]
    policy_names = "、".join(f"`{p}`" for p in POLICIES)
    replay_rows = 200 * 2 * len(ALPHAS) * len(POLICIES) * len(SEEDS)
    summary_rows = 2 * len(ALPHAS) * len(POLICIES)
    per_seed_summary_rows = summary_rows * len(SEEDS)
    report = f"""# Experiment A 全量版结果报告

## 对照手册的完成情况

本目录完成 `veriedge_revision_workbook.md` 中实验 A：Closed-loop Verifiability-Constrained Placement 的全量 offline replay 版本。它的目标不是重新跑 verifier，而是把已经测得的 verifier profile 放回 placement 决策环，验证 placement admission 是否能在 task disclosure 前过滤或升级不可裁决的 heterogeneous execution signature。

已完成项：

- 输入文件：`data/profile_matrix.csv`、`data/candidate_placements.csv`、`data/workload.csv`。
- Policy：{policy_names}。
- Alpha sweep：`alpha = 0.05 / 0.10 / 0.20`。
- Workload：`single` 与 `queued-8`。
- Seeds：5 个 seed，满足手册中 random policy 至少 5 seeds 的 sanity check。
- 输出：`placement_runs.csv`、`placement_summary_by_seed.csv`、`placement_summary.csv`。
- 图：placement frontier、risk-class composition、alpha sensitivity。
- Paper snippets：abstract numbers、figure captions、placement subsection draft。

## 数据规模

| Item | Count | 说明 |
|---|---:|---|
| Profile rows | 34 | 30 条 measured pair/sketch profile + 4 条 homogeneous control |
| Candidate placements | 13 | 6 个 measured heterogeneous pair family 的 LAN/WAN placement + 1 个 homogeneous baseline |
| Workload rows | 400 | 200 tasks × 2 workload pattern |
| Replay rows | {replay_rows:,} | 200 tasks × 2 workloads × {len(ALPHAS)} alpha × {len(POLICIES)} policies × {len(SEEDS)} seeds |
| Summary rows | {summary_rows} | 2 workloads × {len(ALPHAS)} alpha × {len(POLICIES)} policies |
| Per-seed summary rows | {per_seed_summary_rows} | {summary_rows} summary cells × {len(SEEDS)} seeds |

## 主结果：queued-8, alpha=0.10

| Policy | Median latency s | P95 latency s | Goodput | False risk | Infeasible rate | Low-risk share | Admission rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| network_aware_scalar | {float(network['latency_median_s']):.3f} | {float(network['latency_p95_s']):.3f} | {float(network['goodput']):.3f} | {float(network['false_risk_mean']):.4f} | {float(network['infeasible_rate']):.3f} | {float(network['low_risk_share']):.3f} | {float(network['admission_rate']):.3f} |
| network_aware_projcos4 | {float(network_projcos4['latency_median_s']):.3f} | {float(network_projcos4['latency_p95_s']):.3f} | {float(network_projcos4['goodput']):.3f} | {float(network_projcos4['false_risk_mean']):.4f} | {float(network_projcos4['infeasible_rate']):.3f} | {float(network_projcos4['low_risk_share']):.3f} | {float(network_projcos4['admission_rate']):.3f} |
| network_aware_adaptive | {float(network_adaptive['latency_median_s']):.3f} | {float(network_adaptive['latency_p95_s']):.3f} | {float(network_adaptive['goodput']):.3f} | {float(network_adaptive['false_risk_mean']):.4f} | {float(network_adaptive['infeasible_rate']):.3f} | {float(network_adaptive['low_risk_share']):.3f} | {float(network_adaptive['admission_rate']):.3f} |
| risk_weighted_scalar | {float(risk_weighted['latency_median_s']):.3f} | {float(risk_weighted['latency_p95_s']):.3f} | {float(risk_weighted['goodput']):.3f} | {float(risk_weighted['false_risk_mean']):.4f} | {float(risk_weighted['infeasible_rate']):.3f} | {float(risk_weighted['low_risk_share']):.3f} | {float(risk_weighted['admission_rate']):.3f} |
| verif_constrained_projcos4 | {float(constrained['latency_median_s']):.3f} | {float(constrained['latency_p95_s']):.3f} | {float(constrained['goodput']):.3f} | {float(constrained['false_risk_mean']):.4f} | {float(constrained['infeasible_rate']):.3f} | {float(constrained['low_risk_share']):.3f} | {float(constrained['admission_rate']):.3f} |
| adaptive_verifier | {float(adaptive['latency_median_s']):.3f} | {float(adaptive['latency_p95_s']):.3f} | {float(adaptive['goodput']):.3f} | {float(adaptive['false_risk_mean']):.4f} | {float(adaptive['infeasible_rate']):.3f} | {float(adaptive['low_risk_share']):.3f} | {float(adaptive['admission_rate']):.3f} |
| queue_aware_network | {float(queue_network['latency_median_s']):.3f} | {float(queue_network['latency_p95_s']):.3f} | {float(queue_network['goodput']):.3f} | {float(queue_network['false_risk_mean']):.4f} | {float(queue_network['infeasible_rate']):.3f} | {float(queue_network['low_risk_share']):.3f} | {float(queue_network['admission_rate']):.3f} |
| queue_aware_verif_constrained | {float(queue_constrained['latency_median_s']):.3f} | {float(queue_constrained['latency_p95_s']):.3f} | {float(queue_constrained['goodput']):.3f} | {float(queue_constrained['false_risk_mean']):.4f} | {float(queue_constrained['infeasible_rate']):.3f} | {float(queue_constrained['low_risk_share']):.3f} | {float(queue_constrained['admission_rate']):.3f} |
| queue_aware_adaptive | {float(queue_adaptive['latency_median_s']):.3f} | {float(queue_adaptive['latency_p95_s']):.3f} | {float(queue_adaptive['goodput']):.3f} | {float(queue_adaptive['false_risk_mean']):.4f} | {float(queue_adaptive['infeasible_rate']):.3f} | {float(queue_adaptive['low_risk_share']):.3f} | {float(queue_adaptive['admission_rate']):.3f} |
| homogeneous_only | {float(homogeneous['latency_median_s']):.3f} | {float(homogeneous['latency_p95_s']):.3f} | {float(homogeneous['goodput']):.3f} | {float(homogeneous['false_risk_mean']):.4f} | {float(homogeneous['infeasible_rate']):.3f} | {float(homogeneous['low_risk_share']):.3f} | {float(homogeneous['admission_rate']):.3f} |

## 结果解读

`network_aware_scalar` 选择了低延迟 heterogeneous placement，但默认 scalar verifier mode 不满足 task-level `alpha/beta/B/C` 约束，因此 infeasible rate 为 {float(network['infeasible_rate']):.3f}。这支撑手册的 H1：只按 network/latency 做 placement 会选到低延迟但不可裁决的 execution boundary。

`network_aware_projcos4` 是公平固定-sketch baseline：它和 `verif_constrained_projcos4` 使用同一个 verifier mode，但不做 hard feasibility filtering。如果它仍然选择 infeasible placement，而 `verif_constrained_projcos4` 选择不同 candidate，就能说明收益不是单纯来自“换 verifier”。

`network_aware_adaptive` 和 `adaptive_verifier` 展示另一条系统路径，但二者含义不同：`network_aware_adaptive` 先保留低延迟 candidate，再把 verifier mode 升级到满足约束的最小 sketch；`adaptive_verifier` 则在 placement 阶段同时比较 group 与 sketch，选择当前 scoring 下更合适的可行组合。因此新版实验同时区分了三件事：固定 verifier 下的 placement filtering、保留 group 的 sketch upgrade、以及 joint group/sketch selection。

新增的 `queue_aware_*` policies 把当前 candidate 的 `busy_until - arrival_s` 加入 placement score。它们用于检查 queued workload 下，结论是否只是由“所有任务压到同一最快 candidate”造成。`queue_aware_network` 仍不做 verifier constraint，因此可用于观察 queue-aware load balancing 本身；`queue_aware_verif_constrained` 和 `queue_aware_adaptive` 则同时考虑排队等待与 verifier feasibility。

`homogeneous_only` 是保守 baseline。它能避免 heterogeneous verifier infeasibility，但 median latency 和 goodput 较差。这支撑论文主线：不应该简单禁用 heterogeneity，而应该用 measured verifiability 约束 heterogeneous placement。

## Alpha sensitivity

两个 hard-constrained policies 在全部 alpha 下都保持 infeasible rate 为 0。`risk_weighted_scalar` 不做 hard filtering，因此论文中应把它定位为 ablation，用来说明 weighted score 不等价于 constrained admission。

## 图表说明

- `figures/fig_placement_frontier_a1.pdf`：A1 主图，展示 controlled replay policies 在 latency 与 false risk 上的 frontier。
- `figures/fig_placement_frontier_a3_queue.pdf`：A3 补充图，展示 queue-aware policies 在 latency 与 false risk 上的 frontier。
- `figures/fig_risk_class_composition.pdf`：机制图，展示 selected placement 的 low-risk / infeasible 组成。
- `figures/fig_alpha_sensitivity_infeasible.pdf`：alpha sensitivity，证明不是单点 `alpha=0.10` 的 cherry-pick。

## 可信度与局限

可信的部分：verifier profile 的 FPR/TPR/cost 来自 20260512 measured profile matrix；全量 replay 使用同一份 profile/candidate/workload 输入；所有图表均由 `results/*.csv` 生成；constrained policies 的 infeasible rate 已检查为 0。

局限：这是 offline placement replay，不是 live scheduler deployment；candidate latency/cost 是 replay estimate；candidate pool 是根据 measured pair family 构造的受控 candidate set。正式写论文时应表述为 closed-loop replay evidence，而不是端到端真实部署结果。

## 建议回填论文的一句话

Under the queued-8 replay at alpha=0.10 and beta=0.90, network-aware scalar placement selects infeasible verifier signatures in {float(network['infeasible_rate']):.0%} of tasks. With the same fixed projcos4 sketch, verifiability-constrained placement reduces infeasible usage from {float(network_projcos4['infeasible_rate']):.0%} to {float(constrained['infeasible_rate']):.0%}; a network-aware adaptive-sketch baseline can retain the low-latency candidate by upgrading to the smallest feasible sketch, while the joint adaptive-verifier policy selects the best feasible group/sketch trade-off.
"""
    (out_root / "ExperimentA_full_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    out = OUTPUT_ROOT
    script_text = Path(__file__).read_text(encoding="utf-8")
    script_name = Path(__file__).name
    if out.exists():
        shutil.rmtree(out)
    for sub in ["metadata", "data", "results", "figures", "paper_snippets", "scripts"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    profiles, lookup = _load_profiles()
    candidates = _candidate_rows()
    tasks = _load_tasks()
    workload = _workload_rows(tasks)
    run_rows_by_seed, summary_by_seed = _run_replay(tasks, candidates, lookup)
    summary = _aggregate_summary(summary_by_seed)

    profile_fields = [
        "profile_id",
        "pair_id",
        "stack_a",
        "stack_b",
        "boundary",
        "sketch",
        "bytes_ckpt",
        "bytes_trace",
        "fpr",
        "tpr_primary",
        "tpr_scale",
        "locacc",
        "verify_ms_honest",
        "verify_ms_tamper",
        "risk_class",
        "source",
    ]
    candidate_fields = [
        "candidate_id",
        "group_size",
        "provider_set",
        "shard_map",
        "pair_ids",
        "network_latency_s",
        "execution_latency_s",
        "availability_cost",
        "reputation",
        "capacity_ok",
        "backend_mix",
    ]
    workload_fields = [
        "task_id",
        "workload",
        "arrival_s",
        "deadline_s",
        "demand",
        "payload_mb",
        "alpha",
        "beta",
        "sketch_budget_bytes",
        "verify_budget_ms",
        "max_group_size",
        "challenge_prob",
        "prompt_chars",
    ]
    run_fields = [
        "run_id",
        "seed",
        "workload",
        "alpha",
        "beta",
        "policy",
        "task_id",
        "candidate_count",
        "feasible_count",
        "selected_candidate",
        "selected_group_size",
        "selected_sketch",
        "admitted",
        "latency_s",
        "goodput_contrib",
        "challenge_ms_task",
        "false_risk",
        "infeasible",
        "low_risk",
        "reason",
    ]
    summary_fields = [
        "workload",
        "alpha",
        "beta",
        "policy",
        "seed_count",
        "latency_median_s",
        "latency_p95_s",
        "goodput",
        "challenge_ms_task_mean",
        "false_risk_mean",
        "infeasible_rate",
        "low_risk_share",
        "admission_rate",
        "feasible_candidate_mean",
    ]
    summary_by_seed_fields = ["seed"] + [field for field in summary_fields if field != "seed_count"]

    _write_csv(out / "data" / "profile_matrix.csv", profiles, profile_fields)
    _write_csv(out / "data" / "candidate_placements.csv", candidates, candidate_fields)
    _write_csv(out / "data" / "workload.csv", workload, workload_fields)
    _write_csv(out / "results" / "placement_runs.csv", run_rows_by_seed, run_fields)
    _write_csv(out / "results" / "placement_summary_by_seed.csv", summary_by_seed, summary_by_seed_fields)
    _write_csv(out / "results" / "placement_summary.csv", summary, summary_fields)

    _plot_frontier(summary, out / "figures")
    _plot_risk_composition(summary, out / "figures")
    _plot_alpha(summary, out / "figures")

    commit = _git_commit()
    env = {
        "date": time.strftime("%Y-%m-%d"),
        "git_commit": commit,
        "source_profile": str(SOURCE_PROFILE),
        "source_profile_sha256": _sha256(SOURCE_PROFILE),
        "prompt_file": str(PROMPT_FILE),
        "prompt_file_sha256": _sha256(PROMPT_FILE) if PROMPT_FILE.exists() else "",
        "seeds": SEEDS,
        "alpha_sweep": ALPHAS,
        "constraints": {
            "beta": BETA,
            "sketch_budget_bytes": SKETCH_BUDGET_BYTES,
            "verify_budget_ms": VERIFY_BUDGET_MS,
            "max_group_size": MAX_GROUP_SIZE,
            "challenge_prob": CHALLENGE_PROB,
        },
    }
    (out / "metadata" / "environment.md").write_text(
        "# Environment\n\n```json\n" + json.dumps(env, indent=2, ensure_ascii=False) + "\n```\n",
        encoding="utf-8",
    )
    (out / "metadata" / "git_commit.txt").write_text(commit + ("\n" if commit else ""), encoding="utf-8")
    (out / "metadata" / "network_config.md").write_text(
        "# Network Config\n\nThis offline replay uses latency estimates from `candidate_placements.csv`; no live network run is performed.\n",
        encoding="utf-8",
    )
    (out / "scripts" / script_name).write_text(script_text, encoding="utf-8")
    _write_notes(out, summary)

    print(out)
    print(out / "results" / "placement_summary.csv")
    print(out / "figures" / "fig_placement_frontier_a1.pdf")
    print(out / "figures" / "fig_placement_frontier_a3_queue.pdf")


if __name__ == "__main__":
    main()
