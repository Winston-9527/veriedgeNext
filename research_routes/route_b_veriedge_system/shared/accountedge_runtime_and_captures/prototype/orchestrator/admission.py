from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class TaskDescriptor:
    task_id: str
    model_ref: str
    input_ref: str
    required_checkpoints: tuple[str, ...]
    max_latency_ms: float
    risk_budget: float


@dataclass(frozen=True)
class ProviderProfile:
    provider_id: str
    public_key: str
    latency_ms: float
    reputation: float


@dataclass(frozen=True)
class VerifierProfile:
    profile_id: str
    sketch: str
    fpr: float
    tpr: float
    verify_ms: float
    sketch_bytes: int
    feasible: bool


@dataclass(frozen=True)
class CandidatePlacement:
    candidate_id: str
    provider_ids: tuple[str, ...]
    shard_map: dict[str, str]
    verifier_profile_id: str
    estimated_latency_ms: float
    expected_false_dispute_risk: float
    expected_challenge_ms: float


@dataclass(frozen=True)
class PlacementCommitment:
    task_id: str
    candidate_id: str
    provider_ids: tuple[str, ...]
    shard_map: dict[str, str]
    verifier_profile_id: str
    commitment_hash: str
    admitted: bool
    reason: str


def canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def rank_and_commit(
    task: TaskDescriptor,
    candidates: Iterable[CandidatePlacement],
    verifier_profiles: dict[str, VerifierProfile],
) -> PlacementCommitment:
    """Admit the lowest-latency candidate that satisfies public verifier constraints."""
    feasible: list[CandidatePlacement] = []
    for candidate in candidates:
        profile = verifier_profiles[candidate.verifier_profile_id]
        if not profile.feasible:
            continue
        if candidate.estimated_latency_ms > task.max_latency_ms:
            continue
        if candidate.expected_false_dispute_risk > task.risk_budget:
            continue
        feasible.append(candidate)

    if not feasible:
        empty = {
            "task": asdict(task),
            "candidate": None,
            "reason": "no candidate satisfied latency, feasibility, and risk constraints",
        }
        return PlacementCommitment(
            task_id=task.task_id,
            candidate_id="none",
            provider_ids=(),
            shard_map={},
            verifier_profile_id="none",
            commitment_hash=canonical_digest(empty),
            admitted=False,
            reason=empty["reason"],
        )

    selected = min(
        feasible,
        key=lambda c: (
            c.estimated_latency_ms + c.expected_challenge_ms,
            c.expected_false_dispute_risk,
            c.candidate_id,
        ),
    )
    commitment_payload = {
        "task": asdict(task),
        "candidate": asdict(selected),
    }
    return PlacementCommitment(
        task_id=task.task_id,
        candidate_id=selected.candidate_id,
        provider_ids=selected.provider_ids,
        shard_map=selected.shard_map,
        verifier_profile_id=selected.verifier_profile_id,
        commitment_hash=canonical_digest(commitment_payload),
        admitted=True,
        reason="selected lowest cost candidate within public verifier constraints",
    )

