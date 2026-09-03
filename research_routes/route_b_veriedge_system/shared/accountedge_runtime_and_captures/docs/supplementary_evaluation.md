# Supplementary Evaluation Reproduction Map

This file maps the supplementary evaluation figures and tables to the CSV inputs
and scripts included in the anonymous artifact.

Run the complete regeneration path from the repository root:

```bash
bash scripts/reproduce_all_artifacts.sh
```

This writes regenerated figures to `figs/` and regenerated table CSV/Markdown
files to `tables/`.

## Figures

| Supplement item | Output | CSV inputs | Script |
| --- | --- | --- | --- |
| Figure 1: verifier-profile risk composition | `figs/fig_risk_class_composition.{pdf,png}` | `data/verifier_profiles.csv` | `scripts/plot_extended_figures.py` |
| Figure 2: selective-delivery scaling | `figs/fig_delivery_scaling.{pdf,png}` | `data/delivery_summary.csv` | `scripts/plot_extended_figures.py` |
| Figure 3: live local-store delivery validation | `figs/fig_delivery_live_store.{pdf,png}` | `data/delivery_live_store_summary.csv` | `scripts/plot_extended_figures.py` |
| Figure 4: projected-scalar multiseed stability | `figs/fig_projscalar_multiseed_stability.{pdf,png}` | `data/extended/projscalar_multiseed_pair_summary.csv` | `scripts/plot_extended_figures.py` |
| Figure 5: projected-scalar attack and strength sweep | `figs/fig_projscalar_attack_sweep.{pdf,png}` | `data/extended/projscalar_attack_summary.csv`, `data/extended/projscalar_strength_sweep_summary.csv` | `scripts/plot_extended_figures.py` |
| Figure 6: material-tamper strength sweep | `figs/fig_material_tamper_strength_sweep.{pdf,png}` | `data/extended/material_tamper_strength_sweep.csv` | `scripts/plot_extended_figures.py` |
| Figure 7: sketch payload and challenge latency | `figs/fig_verifier_payload_latency.{pdf,png}` | `data/extended/verifier_payload_latency.csv` | `scripts/plot_extended_figures.py` |
| Figure 8: queued-workload policy comparison | `figs/fig_e5_policy_compare.{pdf,png}` | `data/extended/e5_policy_compare.csv` | `scripts/plot_extended_figures.py` |

The repository also regenerates the main-paper placement and delivery panels:
`fig_placement_replay`, `fig_delivery_sweep`, `fig_placement_frontier_a1`,
`fig_placement_frontier_a3_queue`, `fig_alpha_sensitivity_infeasible`, and
`fig_material_tamper_focus`.

## Tables

| Supplement item | Regenerated output | CSV inputs | Script |
| --- | --- | --- | --- |
| Table 1: measured verifier profiles | `tables/table_1_verifier_profiles.{csv,md}` | `data/verifier_profiles.csv` | `scripts/export_supplementary_tables.py` |
| Table 2: replay inputs | `tables/table_2_replay_inputs.{csv,md}` | `data/placement_candidates.csv`, `data/placement_workload.csv` | `scripts/export_supplementary_tables.py` |
| Table 3: queued-8 placement replay | `tables/table_3_queued8_placement_replay.{csv,md}` | `data/placement_summary.csv` | `scripts/export_supplementary_tables.py` |
| Table 4: delivery group-size sweep | `tables/table_4_delivery_sweep.{csv,md}` | `data/delivery_summary.csv` | `scripts/export_supplementary_tables.py` |
| Table 5: live local-store validation | `tables/table_5_live_store_validation.{csv,md}` | `data/delivery_live_store_summary.csv` | `scripts/export_supplementary_tables.py` |
| Table 6: material-tamper TPR | `tables/table_6_material_tamper_tpr.{csv,md}` | `data/extended/material_tamper_attack_summary.csv` | `scripts/export_supplementary_tables.py` |
| Table 7: output-affecting subset availability | `tables/table_7_output_affecting_subset.{csv,md}` | `data/extended/material_tamper_attack_summary.csv` | `scripts/export_supplementary_tables.py` |

Table 7 is an availability table. The included checkpoint captures do not
contain logits, top-k outputs, or final outputs, so output-affecting subset
counts are documented as unavailable rather than silently inferred.

