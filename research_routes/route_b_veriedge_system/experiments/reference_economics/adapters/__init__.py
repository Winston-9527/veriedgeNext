"""Adapter interfaces: model sharding + snapshot/restore.

These are **interfaces only** -- they define what E03/E04/E05 must implement on a
host with the model and state interface available.  No implementation ships here
because this environment has no runnable model / decode-state interface, so any
"measured" number from these adapters would be fabricated.  Callers must record
``source_type`` per the handbook (§4): ``measured`` only when the adapter
actually ran.

See docs/ROUTE_B_G0_EXPERIMENT_HANDBOOK_2026-09-07.md §8 (E03), §9 (E04).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Snapshot:
    """An opaque boundary state (activation / KV / position / mask records)."""

    boundary: str
    tensors: dict
    bytes_on_disk: int
    source_type: str   # measured | derived | assumed | legacy_measured


@dataclass(frozen=True)
class RestoreResult:
    ok: bool
    matched_reference: bool
    note: str
    source_type: str


@runtime_checkable
class ShardAdapter(Protocol):
    """Model-sharding + snapshot/restore surface that E03/E04/E05 implement."""

    def snapshot(self, boundary: str) -> Snapshot: ...

    def restore(self, snap: Snapshot) -> RestoreResult: ...

    def replay_from(self, boundary: str, snap: Snapshot) -> dict:
        """Reconstruct downstream boundaries from a snapshot; returns activations."""
        ...

    def full_duplicate(self) -> dict:
        """Always-on duplicate baseline (the C_duplicate_extra=1.0 anchor)."""
        ...


UNKNOWN = "UNKNOWN: no runnable model/state interface in this environment"
