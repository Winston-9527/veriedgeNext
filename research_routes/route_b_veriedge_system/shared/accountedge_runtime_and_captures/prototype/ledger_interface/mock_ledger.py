from __future__ import annotations

from dataclasses import asdict, dataclass

from prototype.orchestrator import PlacementCommitment
from prototype.tstc_verifier import ChallengeResult


@dataclass(frozen=True)
class ChallengeRecord:
    task_id: str
    accepted: bool
    first_mismatch_checkpoint: str | None
    max_delta: float


@dataclass(frozen=True)
class SettlementRecord:
    task_id: str
    status: str
    provider_action: str


class MockLedger:
    """Local contract-like state machine for the artifact smoke demo."""

    def __init__(self) -> None:
        self.placements: dict[str, dict] = {}
        self.challenges: dict[str, dict] = {}
        self.settlements: dict[str, dict] = {}

    def record_placement(self, commitment: PlacementCommitment) -> None:
        self.placements[commitment.task_id] = asdict(commitment)

    def record_challenge(self, task_id: str, result: ChallengeResult) -> ChallengeRecord:
        record = ChallengeRecord(
            task_id=task_id,
            accepted=result.accepted,
            first_mismatch_checkpoint=result.first_mismatch_checkpoint,
            max_delta=result.max_delta,
        )
        self.challenges[task_id] = asdict(record)
        return record

    def settle(self, task_id: str) -> SettlementRecord:
        challenge = self.challenges[task_id]
        if challenge["accepted"]:
            record = SettlementRecord(task_id=task_id, status="released", provider_action="pay selected providers")
        else:
            record = SettlementRecord(task_id=task_id, status="disputed", provider_action="hold payment and slash mismatching shard")
        self.settlements[task_id] = asdict(record)
        return record

    def snapshot(self) -> dict[str, dict]:
        return {
            "placements": self.placements,
            "challenges": self.challenges,
            "settlements": self.settlements,
        }

