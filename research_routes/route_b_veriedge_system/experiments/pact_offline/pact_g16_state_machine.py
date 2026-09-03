#!/usr/bin/env python3
"""Transactional PACT-G16 commit-reveal and replay-protection prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROUTE_ROOT = HERE.parents[1]
PCRA_DIR = HERE.parent / "pcra_offline_retired"
DEFAULT_DATA_ROOT = (
    ROUTE_ROOT
    / "shared"
    / "accountedge_runtime_and_captures"
    / "raw_captures"
    / "e2_live_subset"
)
sys.path.insert(0, str(PCRA_DIR))

from pact_g16_protocol import (  # noqa: E402
    SeedContext,
    adjudicate_receipt_pair,
    canonical_json,
    commit_tensor,
    derive_seed,
    make_receipt,
    project_lut16,
    verify_receipt,
)
from pcra_offline import load_pairs  # noqa: E402


BEACON_COMMIT_DOMAIN = b"PACT-BEACON-COMMIT-v1\x00"
BEACON_OUTPUT_DOMAIN = b"PACT-BEACON-OUTPUT-v1\x00"


class ProtocolError(RuntimeError):
    pass


def beacon_commitment(
    participant: str, task_id: str, boundary: str, secret: bytes
) -> str:
    transcript = canonical_json(
        {
            "participant": participant,
            "task_id": task_id,
            "boundary": boundary,
            "secret_hex": secret.hex(),
        }
    )
    return hashlib.sha256(BEACON_COMMIT_DOMAIN + transcript).hexdigest()


def beacon_output(
    task_id: str, boundary: str, reveals: list[tuple[str, bytes]]
) -> str:
    ordered = sorted((participant, secret.hex()) for participant, secret in reveals)
    transcript = canonical_json(
        {"task_id": task_id, "boundary": boundary, "reveals": ordered}
    )
    return hashlib.sha256(BEACON_OUTPUT_DOMAIN + transcript).hexdigest()


class PactLedger:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT NOT NULL,
                boundary TEXT NOT NULL,
                model_id TEXT NOT NULL,
                shape_json TEXT NOT NULL,
                tensor_dtype TEXT NOT NULL,
                actual_root TEXT NOT NULL,
                reference_root TEXT NOT NULL,
                status TEXT NOT NULL,
                beacon_commit_deadline INTEGER NOT NULL,
                beacon_reveal_deadline INTEGER NOT NULL,
                receipt_deadline INTEGER NOT NULL,
                beacon_output TEXT,
                seed_id TEXT,
                statistic REAL,
                failure_reason TEXT,
                PRIMARY KEY (task_id, boundary)
            );
            CREATE TABLE IF NOT EXISTS beacon_entries (
                task_id TEXT NOT NULL,
                boundary TEXT NOT NULL,
                participant TEXT NOT NULL,
                commitment TEXT NOT NULL,
                reveal_hex TEXT,
                PRIMARY KEY (task_id, boundary, participant),
                FOREIGN KEY (task_id, boundary) REFERENCES tasks(task_id, boundary)
            );
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                boundary TEXT NOT NULL,
                role TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                received_at INTEGER NOT NULL,
                UNIQUE (task_id, boundary, role),
                FOREIGN KEY (task_id, boundary) REFERENCES tasks(task_id, boundary)
            );
            """
        )

    def close(self) -> None:
        self.connection.close()

    def create_task(
        self,
        context_without_beacon: SeedContext,
        commit_deadline: int,
        reveal_deadline: int,
        receipt_deadline: int,
    ) -> None:
        if not commit_deadline < reveal_deadline < receipt_deadline:
            raise ProtocolError("Deadlines must be strictly increasing")
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                    """,
                    (
                        context_without_beacon.task_id,
                        context_without_beacon.boundary,
                        context_without_beacon.model_id,
                        json.dumps(list(context_without_beacon.tensor_shape)),
                        context_without_beacon.tensor_dtype,
                        context_without_beacon.actual_root,
                        context_without_beacon.reference_root,
                        "ROOTS_COMMITTED",
                        commit_deadline,
                        reveal_deadline,
                        receipt_deadline,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ProtocolError("Task/boundary replay or duplicate") from error

    def task(self, task_id: str, boundary: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM tasks WHERE task_id=? AND boundary=?", (task_id, boundary)
        ).fetchone()
        if row is None:
            raise ProtocolError("Unknown task/boundary")
        return row

    def replace_roots(self, task_id: str, boundary: str, *_: str) -> None:
        self.task(task_id, boundary)
        raise ProtocolError("Committed roots are immutable")

    def add_beacon_commit(
        self, task_id: str, boundary: str, participant: str, commitment: str, now: int
    ) -> None:
        row = self.task(task_id, boundary)
        if row["status"] not in {"ROOTS_COMMITTED", "BEACON_COMMITTING"}:
            raise ProtocolError("Beacon commitment is not allowed in current state")
        if now > row["beacon_commit_deadline"]:
            raise ProtocolError("Beacon commitment is late")
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO beacon_entries VALUES (?, ?, ?, ?, NULL)",
                    (task_id, boundary, participant, commitment),
                )
                count = self.connection.execute(
                    "SELECT COUNT(*) FROM beacon_entries WHERE task_id=? AND boundary=?",
                    (task_id, boundary),
                ).fetchone()[0]
                if count > 2:
                    raise ProtocolError("Prototype requires exactly two beacon parties")
                self.connection.execute(
                    "UPDATE tasks SET status=? WHERE task_id=? AND boundary=?",
                    ("BEACON_COMMITTED" if count == 2 else "BEACON_COMMITTING", task_id, boundary),
                )
        except sqlite3.IntegrityError as error:
            raise ProtocolError("Duplicate beacon participant") from error

    def reveal(
        self, task_id: str, boundary: str, participant: str, secret: bytes, now: int
    ) -> str | None:
        task = self.task(task_id, boundary)
        if task["status"] not in {"BEACON_COMMITTED", "BEACON_REVEALING"}:
            raise ProtocolError("Reveal rejected until every party has committed")
        if now > task["beacon_reveal_deadline"]:
            raise ProtocolError("Beacon reveal is late")
        entry = self.connection.execute(
            """SELECT * FROM beacon_entries
               WHERE task_id=? AND boundary=? AND participant=?""",
            (task_id, boundary, participant),
        ).fetchone()
        if entry is None:
            raise ProtocolError("Participant did not commit")
        if entry["reveal_hex"] is not None:
            raise ProtocolError("Duplicate reveal")
        expected = beacon_commitment(participant, task_id, boundary, secret)
        if expected != entry["commitment"]:
            raise ProtocolError("Reveal does not match commitment")

        with self.connection:
            self.connection.execute(
                """UPDATE beacon_entries SET reveal_hex=?
                   WHERE task_id=? AND boundary=? AND participant=?""",
                (secret.hex(), task_id, boundary, participant),
            )
            revealed = self.connection.execute(
                """SELECT participant, reveal_hex FROM beacon_entries
                   WHERE task_id=? AND boundary=? AND reveal_hex IS NOT NULL""",
                (task_id, boundary),
            ).fetchall()
            if len(revealed) < 2:
                self.connection.execute(
                    "UPDATE tasks SET status='BEACON_REVEALING' WHERE task_id=? AND boundary=?",
                    (task_id, boundary),
                )
                return None
            output = beacon_output(
                task_id,
                boundary,
                [(row["participant"], bytes.fromhex(row["reveal_hex"])) for row in revealed],
            )
            context = self.seed_context(task_id, boundary, output_override=output)
            seed_id = hashlib.sha256(derive_seed(context)).hexdigest()
            self.connection.execute(
                """UPDATE tasks SET status='SEED_READY', beacon_output=?, seed_id=?
                   WHERE task_id=? AND boundary=?""",
                (output, seed_id, task_id, boundary),
            )
            return output

    def seed_context(
        self, task_id: str, boundary: str, output_override: str | None = None
    ) -> SeedContext:
        row = self.task(task_id, boundary)
        output = output_override if output_override is not None else row["beacon_output"]
        if output is None:
            raise ProtocolError("Beacon output is not ready")
        return SeedContext(
            task_id=row["task_id"],
            boundary=row["boundary"],
            model_id=row["model_id"],
            tensor_shape=tuple(json.loads(row["shape_json"])),
            tensor_dtype=row["tensor_dtype"],
            actual_root=row["actual_root"],
            reference_root=row["reference_root"],
            beacon_hex=output,
        )

    def submit_receipt(
        self,
        task_id: str,
        boundary: str,
        receipt: dict[str, object],
        role_key: bytes,
        actual_key: bytes,
        reference_key: bytes,
        now: int,
    ) -> float | None:
        task = self.task(task_id, boundary)
        if task["status"] not in {"SEED_READY", "RECEIPTS_PENDING"}:
            raise ProtocolError("Receipt is not allowed in current state")
        if now > task["receipt_deadline"]:
            raise ProtocolError("Receipt is late")
        if not verify_receipt(receipt, role_key):
            raise ProtocolError("Receipt authentication failed")
        payload = receipt.get("payload")
        if not isinstance(payload, dict):
            raise ProtocolError("Malformed receipt payload")
        role = str(payload.get("role"))
        if role not in {"actual_receiver", "reference_witness"}:
            raise ProtocolError("Unknown receipt role")
        context = self.seed_context(task_id, boundary)
        expected_root = context.actual_root if role == "actual_receiver" else context.reference_root
        expected_peer = context.reference_root if role == "actual_receiver" else context.actual_root
        if payload.get("task_id") != task_id or payload.get("boundary") != boundary:
            raise ProtocolError("Receipt context mismatch")
        if payload.get("tensor_root") != expected_root or payload.get("peer_root") != expected_peer:
            raise ProtocolError("Receipt roots mismatch")
        if payload.get("seed_id") != task["seed_id"]:
            raise ProtocolError("Receipt seed mismatch")

        serialized = canonical_json(receipt).decode("utf-8")
        receipt_id = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        existing = self.connection.execute(
            "SELECT * FROM receipts WHERE task_id=? AND boundary=? AND role=?",
            (task_id, boundary, role),
        ).fetchone()
        if existing is not None:
            if existing["receipt_id"] == receipt_id:
                raise ProtocolError("Duplicate receipt replay")
            with self.connection:
                self.connection.execute(
                    """UPDATE tasks SET status='FROZEN_CONFLICT', failure_reason=?
                       WHERE task_id=? AND boundary=?""",
                    (f"conflicting authenticated receipt for {role}", task_id, boundary),
                )
            raise ProtocolError("Conflicting authenticated receipt; task frozen")

        with self.connection:
            self.connection.execute(
                "INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?)",
                (receipt_id, task_id, boundary, role, serialized, now),
            )
            self.connection.execute(
                "UPDATE tasks SET status='RECEIPTS_PENDING' WHERE task_id=? AND boundary=?",
                (task_id, boundary),
            )
            stored = self.connection.execute(
                "SELECT role, receipt_json FROM receipts WHERE task_id=? AND boundary=?",
                (task_id, boundary),
            ).fetchall()
            if len(stored) < 2:
                return None
            by_role = {row["role"]: json.loads(row["receipt_json"]) for row in stored}
            accepted, value = adjudicate_receipt_pair(
                by_role["actual_receiver"],
                by_role["reference_witness"],
                actual_key,
                reference_key,
                context,
            )
            if not accepted or value is None:
                self.connection.execute(
                    """UPDATE tasks SET status='FROZEN_CONFLICT', failure_reason='pair adjudication failed'
                       WHERE task_id=? AND boundary=?""",
                    (task_id, boundary),
                )
                raise ProtocolError("Receipt pair failed adjudication")
            self.connection.execute(
                """UPDATE tasks SET status='ADJUDICATED', statistic=?
                   WHERE task_id=? AND boundary=?""",
                (value, task_id, boundary),
            )
            return value

    def expire(self, task_id: str, boundary: str, now: int) -> None:
        task = self.task(task_id, boundary)
        if task["status"] in {"ADJUDICATED", "FROZEN_CONFLICT", "ABORTED"}:
            return
        reason = None
        if task["status"] in {"ROOTS_COMMITTED", "BEACON_COMMITTING"} and now > task[
            "beacon_commit_deadline"
        ]:
            reason = "beacon commit timeout"
        elif task["status"] in {"BEACON_COMMITTED", "BEACON_REVEALING"} and now > task[
            "beacon_reveal_deadline"
        ]:
            reason = "beacon reveal timeout"
        elif task["status"] in {"SEED_READY", "RECEIPTS_PENDING"} and now > task[
            "receipt_deadline"
        ]:
            reason = "receipt timeout"
        if reason is None:
            raise ProtocolError("Task is not expired")
        with self.connection:
            self.connection.execute(
                """UPDATE tasks SET status='ABORTED', failure_reason=?
                   WHERE task_id=? AND boundary=?""",
                (reason, task_id, boundary),
            )


def base_context(task_id: str, boundary: str, actual: np.ndarray, reference: np.ndarray) -> SeedContext:
    return SeedContext(
        task_id=task_id,
        boundary=boundary,
        model_id="anonymous-heterogeneous-qwen",
        tensor_shape=actual.shape,
        tensor_dtype="float32-le",
        actual_root=commit_tensor(actual),
        reference_root=commit_tensor(reference),
        beacon_hex="",
    )


def prepare_seed(
    ledger: PactLedger,
    context: SeedContext,
    secret_a: bytes,
    secret_b: bytes,
) -> SeedContext:
    ledger.create_task(context, 10, 20, 30)
    ledger.add_beacon_commit(
        context.task_id,
        context.boundary,
        "party-A",
        beacon_commitment("party-A", context.task_id, context.boundary, secret_a),
        1,
    )
    ledger.add_beacon_commit(
        context.task_id,
        context.boundary,
        "party-B",
        beacon_commitment("party-B", context.task_id, context.boundary, secret_b),
        2,
    )
    if ledger.reveal(context.task_id, context.boundary, "party-A", secret_a, 11) is not None:
        raise AssertionError("Beacon finalized before both reveals")
    output = ledger.reveal(context.task_id, context.boundary, "party-B", secret_b, 12)
    if output is None:
        raise AssertionError("Beacon did not finalize")
    return ledger.seed_context(context.task_id, context.boundary)


def expect_failure(checks: dict[str, bool], name: str, action) -> None:
    try:
        action()
    except ProtocolError:
        checks[name] = True
    else:
        checks[name] = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "g16_state_machine")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    database_path = args.output / "state_machine.sqlite"
    if database_path.exists():
        database_path.unlink()

    pair = next(
        pair
        for pair in load_pairs(args.data_root, "eval")
        if pair.prompt_id == "eval_001" and pair.checkpoint == "prefill__C1"
    )
    actual = np.asarray(pair.candidate, dtype=np.float32)
    reference = np.asarray(pair.reference, dtype=np.float32)
    receiver_key = hashlib.sha256(b"state receiver key").digest()
    reference_key = hashlib.sha256(b"state reference key").digest()
    secret_a = hashlib.sha256(b"honest party A secret").digest()
    secret_b = hashlib.sha256(b"party B secret").digest()
    ledger = PactLedger(database_path)
    checks: dict[str, bool] = {}

    # Valid end-to-end state transition.
    context = base_context("valid-task", "prefill__C1", actual, reference)
    ready = prepare_seed(ledger, context, secret_a, secret_b)
    seed = derive_seed(ready)
    actual_sketch, actual_digest = project_lut16(actual, seed, 16, accumulation="float32")
    reference_sketch, reference_digest = project_lut16(
        reference, seed, 16, accumulation="float32"
    )
    actual_receipt = make_receipt(
        "actual_receiver",
        "receiver-C1",
        ready.task_id,
        ready.boundary,
        ready.actual_root,
        ready.reference_root,
        seed,
        actual_digest,
        actual_sketch,
        receiver_key,
    )
    reference_receipt = make_receipt(
        "reference_witness",
        "reference-C1",
        ready.task_id,
        ready.boundary,
        ready.reference_root,
        ready.actual_root,
        seed,
        reference_digest,
        reference_sketch,
        reference_key,
    )
    first = ledger.submit_receipt(
        ready.task_id,
        ready.boundary,
        actual_receipt,
        receiver_key,
        receiver_key,
        reference_key,
        21,
    )
    final = ledger.submit_receipt(
        ready.task_id,
        ready.boundary,
        reference_receipt,
        reference_key,
        receiver_key,
        reference_key,
        22,
    )
    checks["valid_flow_adjudicates"] = (
        first is None
        and final is not None
        and ledger.task(ready.task_id, ready.boundary)["status"] == "ADJUDICATED"
    )
    checks["ledger_seed_matches_transcript"] = ledger.task(
        ready.task_id, ready.boundary
    )["seed_id"] == hashlib.sha256(seed).hexdigest()

    expect_failure(
        checks,
        "duplicate_task_rejected",
        lambda: ledger.create_task(context, 10, 20, 30),
    )
    expect_failure(
        checks,
        "committed_root_replacement_rejected",
        lambda: ledger.replace_roots(context.task_id, context.boundary, "00" * 32, "11" * 32),
    )
    expect_failure(
        checks,
        "terminal_receipt_replay_rejected",
        lambda: ledger.submit_receipt(
            ready.task_id,
            ready.boundary,
            actual_receipt,
            receiver_key,
            receiver_key,
            reference_key,
            23,
        ),
    )

    # Early and invalid reveals.
    early = base_context("early-reveal", "prefill__C1", actual, reference)
    ledger.create_task(early, 10, 20, 30)
    ledger.add_beacon_commit(
        early.task_id,
        early.boundary,
        "party-A",
        beacon_commitment("party-A", early.task_id, early.boundary, secret_a),
        1,
    )
    expect_failure(
        checks,
        "reveal_before_all_commits_rejected",
        lambda: ledger.reveal(early.task_id, early.boundary, "party-A", secret_a, 2),
    )

    wrong = base_context("wrong-reveal", "prefill__C1", actual, reference)
    ledger.create_task(wrong, 10, 20, 30)
    for participant, secret in (("party-A", secret_a), ("party-B", secret_b)):
        ledger.add_beacon_commit(
            wrong.task_id,
            wrong.boundary,
            participant,
            beacon_commitment(participant, wrong.task_id, wrong.boundary, secret),
            1,
        )
    expect_failure(
        checks,
        "wrong_reveal_rejected",
        lambda: ledger.reveal(wrong.task_id, wrong.boundary, "party-A", b"wrong", 11),
    )

    # Incomplete beacon aborts instead of silently choosing a seed.
    timeout = base_context("timeout-task", "prefill__C1", actual, reference)
    ledger.create_task(timeout, 10, 20, 30)
    ledger.add_beacon_commit(
        timeout.task_id,
        timeout.boundary,
        "party-A",
        beacon_commitment("party-A", timeout.task_id, timeout.boundary, secret_a),
        1,
    )
    ledger.expire(timeout.task_id, timeout.boundary, 11)
    timeout_row = ledger.task(timeout.task_id, timeout.boundary)
    checks["incomplete_beacon_aborts"] = (
        timeout_row["status"] == "ABORTED" and timeout_row["seed_id"] is None
    )

    # A second authenticated receipt for the same role freezes settlement.
    conflict = base_context("conflict-task", "prefill__C1", actual, reference)
    conflict_ready = prepare_seed(ledger, conflict, secret_a, secret_b)
    conflict_seed = derive_seed(conflict_ready)
    conflict_sketch, conflict_digest = project_lut16(
        actual, conflict_seed, 16, accumulation="float32"
    )
    conflict_receipt = make_receipt(
        "actual_receiver",
        "receiver-C1",
        conflict_ready.task_id,
        conflict_ready.boundary,
        conflict_ready.actual_root,
        conflict_ready.reference_root,
        conflict_seed,
        conflict_digest,
        conflict_sketch,
        receiver_key,
    )
    ledger.submit_receipt(
        conflict_ready.task_id,
        conflict_ready.boundary,
        conflict_receipt,
        receiver_key,
        receiver_key,
        reference_key,
        21,
    )
    conflicting_sketch = conflict_sketch.copy()
    conflicting_sketch[0] = np.nextafter(conflicting_sketch[0], np.float32(np.inf))
    conflicting_receipt = make_receipt(
        "actual_receiver",
        "receiver-C1",
        conflict_ready.task_id,
        conflict_ready.boundary,
        conflict_ready.actual_root,
        conflict_ready.reference_root,
        conflict_seed,
        conflict_digest,
        conflicting_sketch,
        receiver_key,
    )
    expect_failure(
        checks,
        "conflicting_authenticated_receipt_rejected",
        lambda: ledger.submit_receipt(
            conflict_ready.task_id,
            conflict_ready.boundary,
            conflicting_receipt,
            receiver_key,
            receiver_key,
            reference_key,
            22,
        ),
    )
    checks["conflict_freezes_settlement"] = ledger.task(
        conflict_ready.task_id, conflict_ready.boundary
    )["status"] == "FROZEN_CONFLICT"

    # A seed-ready task receiving no timely receipt aborts without a verdict.
    receipt_timeout = base_context("receipt-timeout", "prefill__C1", actual, reference)
    receipt_timeout_ready = prepare_seed(ledger, receipt_timeout, secret_a, secret_b)
    expect_failure(
        checks,
        "late_receipt_rejected",
        lambda: ledger.submit_receipt(
            receipt_timeout_ready.task_id,
            receipt_timeout_ready.boundary,
            actual_receipt,
            receiver_key,
            receiver_key,
            reference_key,
            31,
        ),
    )
    ledger.expire(receipt_timeout_ready.task_id, receipt_timeout_ready.boundary, 31)
    checks["receipt_timeout_aborts"] = ledger.task(
        receipt_timeout_ready.task_id, receipt_timeout_ready.boundary
    )["status"] == "ABORTED"

    # Close and reopen SQLite before the final audit: replay protection must be
    # durable rather than an in-process set.
    ledger.close()
    ledger = PactLedger(database_path)
    checks["terminal_states_survive_restart"] = (
        ledger.task(ready.task_id, ready.boundary)["status"] == "ADJUDICATED"
        and ledger.task(conflict_ready.task_id, conflict_ready.boundary)["status"]
        == "FROZEN_CONFLICT"
        and ledger.task(receipt_timeout_ready.task_id, receipt_timeout_ready.boundary)["status"]
        == "ABORTED"
    )
    expect_failure(
        checks,
        "task_replay_rejected_after_restart",
        lambda: ledger.create_task(context, 10, 20, 30),
    )
    checks["beacon_output_context_bound"] = beacon_output(
        "context-A", "prefill__C1", [("party-A", secret_a), ("party-B", secret_b)]
    ) != beacon_output(
        "context-B", "prefill__C1", [("party-A", secret_a), ("party-B", secret_b)]
    )

    if not all(checks.values()):
        raise AssertionError(checks)
    task_rows = [dict(row) for row in ledger.connection.execute("SELECT * FROM tasks ORDER BY task_id")]
    result = {
        "status": "transactional state-machine prototype",
        "checks": checks,
        "valid_final_statistic": final,
        "valid_final_state": ledger.task(ready.task_id, ready.boundary)["status"],
        "timeout_state": timeout_row["status"],
        "conflict_state": ledger.task(conflict_ready.task_id, conflict_ready.boundary)["status"],
        "beacon_security_scope": (
            "unpredictable if at least one party commits an unknown secret; "
            "a last revealer can still abort, causing availability loss"
        ),
        "database": str(database_path.resolve()),
        "tasks": task_rows,
    }
    (args.output / "state_machine_checks.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    ledger.close()
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
