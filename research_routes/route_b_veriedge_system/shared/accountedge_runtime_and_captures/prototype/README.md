# Interface-Level Prototype

This directory contains a small runnable prototype for the interface flow used
by the artifact. It is intentionally not a production deployment and does not
include model weights, private task payloads, distributed execution, or a real
blockchain.

## Modules

- `orchestrator/`: reads public task descriptors, candidate placements, and
  verifier profiles; performs admission/ranking; emits a committed placement
  tuple.
- `ppd_runtime/`: publishes one toy ciphertext object and per-provider access
  packages for a synthetic payload.
- `tstc_verifier/`: builds small tensor sketches, digest chains, tolerance
  comparisons, and first-mismatch localization from numpy fixtures.
- `ledger_interface/`: local mock contract/state machine for placement,
  challenge, and settlement records.
- `examples/`: executable smoke demo.
- `tests/`: minimal unit test for the smoke demo.

## Smoke Demo

Run from the repository root:

```bash
python -m prototype.examples.run_end_to_end_demo
```

The demo prints JSON showing:

1. public descriptor/profile input;
2. placement admission and commitment;
3. selected providers receiving PPD access packages;
4. TSTC challenge localization at the first mismatching checkpoint;
5. ledger/interface state recording the settlement outcome.

Optional test:

```bash
python -m unittest prototype.tests.test_end_to_end_demo
```

