# Extended Figure Data

This directory contains normalized CSV inputs for the additional artifact
figures. These are measured-data summaries, not raw multi-node captures.

The script `scripts/plot_extended_figures.py` reads these CSVs and regenerates
the extended figure set in `figs/`.

Included inputs:

- `material_tamper_attack_summary.csv`
- `material_tamper_strength_sweep.csv`
- `projscalar_attack_summary.csv`
- `projscalar_strength_sweep_summary.csv`
- `projscalar_multiseed_overall_summary.csv`
- `projscalar_multiseed_pair_summary.csv`
- `verifier_payload_latency.csv`
- `verifier_overhead_summary.csv`
- `e5_policy_compare.csv`
- `e5_placement_mix.csv`
