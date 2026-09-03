# PACT-G16 commit-reveal and transactional state machine

Date: 2026-08-24  
Status: completed local protocol-control prototype

## Implemented controls

The prototype adds a two-party commit-reveal beacon and a SQLite-backed task
ledger around the executable PACT-G16 transcript.

Each `(task_id, boundary)` moves through explicit states:

`ROOTS_COMMITTED -> BEACON_COMMITTING -> BEACON_COMMITTED ->`
`BEACON_REVEALING -> SEED_READY -> RECEIPTS_PENDING -> ADJUDICATED`.

Failure terminals are `ABORTED` and `FROZEN_CONFLICT`.

The beacon commitments bind participant, task, boundary, and a 256-bit secret.
Reveals are accepted only after both commitments exist. The final beacon output
hashes the context and both ordered reveals, then enters the ordinary PACT-G16
seed transcript together with both immutable tensor roots.

The ledger enforces unique tasks, unique participant commitments, one receipt
per role, increasing deadlines, immutable roots, authenticated receipt context,
and durable terminal states using SQLite transactions and constraints.

## Tests

All 15 paths pass:

- valid flow reaches `ADJUDICATED` and stores the transcript-derived seed ID;
- duplicate task/boundary is rejected;
- committed roots cannot be replaced;
- receipt replay after adjudication is rejected;
- reveal before all parties commit is rejected;
- a reveal inconsistent with its commitment is rejected;
- incomplete beacon commitment expires to `ABORTED` without a seed;
- late receipt is rejected and receipt timeout becomes `ABORTED`;
- a second, different, authenticated receipt for the same role is rejected and
  freezes settlement as `FROZEN_CONFLICT`;
- terminal states survive database close/reopen;
- task replay remains rejected after restart;
- identical secrets under a different task produce a different beacon output.

The generated database contains representative `ADJUDICATED`, `ABORTED`, and
`FROZEN_CONFLICT` tasks and is retained for inspection.

## Security scope

If at least one party chooses an unpredictable secret and commits before seeing
the other's reveal, the eventual seed is unpredictable at tensor commitment.
A malicious last revealer can still abort after seeing the other reveal. This
causes availability loss but does not permit silently selecting a different
seed: the ledger records `ABORTED` and produces no verifier verdict.

A deployment must address this abort channel with a public randomness beacon,
threshold commit-reveal, deposits/penalties, or a committed fallback. Treating
timeout as PASS would destroy the security property.

SQLite supplies local durability and atomicity, not Byzantine consensus or a
tamper-evident public log. The marketplace/settlement record must provide those
properties in the deployed system.

## Artifacts

- `pact_g16_state_machine.py`: beacon, ledger, and adversarial path tests.
- `results/g16_state_machine/state_machine_checks.json`: complete audit.
- `results/g16_state_machine/state_machine.sqlite`: persisted protocol states.
