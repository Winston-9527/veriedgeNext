# Artifact Claim Mapping

## C1: Placement

Claim:
Verifiability-constrained placement uses measured verifier profiles to reject
or upgrade candidates before task disclosure.

Evidence path:

1. `data/verifier_profiles.csv` defines per-profile FPR/TPR/size/cost.
2. `data/placement_candidates.csv` defines candidate groups and profile keys.
3. `data/placement_results.csv` records selected candidates under each policy.
4. `scripts/summarize_placement.py` computes goodput, infeasible usage, false
   risk, and latency.
5. `scripts/plot_placement_replay.py` regenerates the core placement figure.
6. `scripts/plot_extended_figures.py` regenerates the full figure set from
   included CSVs, including placement frontiers and policy-comparison panels.

The replay log is the measured deterministic policy output; scripts validate
the inputs and reproduce the paper summaries and figures from the included
logs. The artifact does not claim to rerun hardware-dependent placement
generation from scratch.

## C2: Selective Delivery

Claim:
PPD replaces per-provider payload replication with one ciphertext publication
plus small per-provider access packages, so its benefit grows with group width.

Evidence path:

1. `data/delivery_runs.csv` records RPD/PPD runs by network and group size.
2. `scripts/summarize_delivery.py` computes median/p95 all-ready time and
   requester egress.
3. `scripts/plot_delivery_sweep.py` regenerates the delivery sweep figure.
4. `data/delivery_live_store_runs.csv` provides a local-store supplement showing
   fresh ciphertext, content-hash object IDs, and provider fetch verification.

## C3: Verifier Profile Uncertainty

Claim:
Verifier profiles are measured operating points, not universal guarantees.

Evidence path:

1. `data/verifier_profiles.csv` records held-out counts.
2. `scripts/compute_wilson_ci.py` computes Wilson 95% confidence intervals.
3. `data/verifier_profiles_with_ci.csv` exposes uncertainty.

## Interface-Level Prototype

Claim:
The artifact exposes the prototype interfaces used by the evaluation pipeline
without claiming production deployment.

Evidence path:

1. `prototype/orchestrator/` performs admission and emits a committed placement
   tuple from public task/profile inputs.
2. `prototype/ppd_runtime/` publishes one toy ciphertext object and
   per-provider access packages.
3. `prototype/tstc_verifier/` computes small tensor sketches, digest chains,
   tolerance comparison, and first-mismatch localization.
4. `prototype/ledger_interface/` records placement, challenge, and settlement
   updates in a local mock state machine.
5. `python -m prototype.examples.run_end_to_end_demo` runs the complete smoke
   flow end to end.

## Optional Data Collection

Claim:
The artifact exposes an anonymized checkpoint-capture collection path for
reviewers who want to inspect how verifier-profile CSV rows can be generated.

Evidence path:

1. `data_collection/collect_hf_verifier_profiles.py` can run a small Hugging
   Face model forward pass with `output_hidden_states=True`.
2. The same script extracts C1/C2/C3-style checkpoint tensors, computes scalar
   and projected-token cosine sketches, calibrates an honest threshold, and
   writes `verifier_profiles_collected.csv`.
3. `data_collection/README.md` documents both a Hugging Face run and a
   no-download synthetic schema smoke run.

This collection path is illustrative. The submitted figures use the measured
CSV summaries included under `data/`, not reviewer-local model downloads.

## Raw Capture and Multi-Node Recollection Support

Claim:
The artifact exposes the raw checkpoint-capture schema and an anonymized
multi-device recollection template without leaking author infrastructure.

Evidence path:

1. `raw_captures/e2_live_subset/` includes a small anonymized subset of real
   `.npz` checkpoint captures with C1/C2/C3 tensors.
2. `scripts/validate_raw_captures.py` validates file hashes, checkpoint keys,
   tensor ranks, and numeric dtypes for the included raw subset.
3. `multi_node_runner/env.example` and
   `multi_node_runner/run_remote_collection.py` provide a dry-run-first
   SSH/rsync coordinator template using reviewer-local hosts.
4. `docs/model_and_device_collection.md` documents the Hugging Face model,
   anonymous device roles, capture schema, and recollection boundary.

The raw subset is not the full internal raw corpus. It is included to expose the
capture schema and enable small local checks; paper figures are regenerated from
the measured CSVs under `data/`.
