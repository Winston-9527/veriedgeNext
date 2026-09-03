# Route B Experiments

This directory separates the active PACT line from a retained negative-result
line.

## Active

[`pact_offline/`](pact_offline/) contains the runnable PACT-G and PACT-G16 work:

- dense Gaussian and quantized projection experiments;
- known-seed nullspace negative control;
- calibration and conditional-power analysis;
- adaptive-K evidence policy;
- commit-before-seed G16 transcript checks;
- persistent replay-safe protocol state machine.

Its scripts default to the bundled data under
`../shared/accountedge_runtime_and_captures/raw_captures/e2_live_subset` when
invoked from the project root. See its README for commands and limitations.

## Retired

[`pcra_offline_retired/`](pcra_offline_retired/) contains the earlier
coordinate-opening design. Sparse attacks exposed a support-hit ceiling, so it
is preserved for provenance and negative-result analysis, not for extension as
the Route B main line.

## Result Policy

Committed `results/` directories are evidence snapshots. New runs should use a
new descriptive output directory and retain the command, input-data identity,
random-seed policy, environment, and summary JSON. Do not overwrite a
paper-referenced result without recording why it changed.
