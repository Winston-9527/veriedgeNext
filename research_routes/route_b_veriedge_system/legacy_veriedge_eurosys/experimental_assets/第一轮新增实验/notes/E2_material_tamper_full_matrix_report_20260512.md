# E2 Material-Tamper Full Matrix Report (2026-05-12)

## Status

This report supersedes `E2_material_tamper_full_matrix_report_20260507.md`.

The 2026-05-12 run should be interpreted as a **tamper-family differentiation study**, not as a single "which verifier wins everywhere" table. The main positive claim is that projected-token cosine verification is strong on attacks that change representation direction or semantic content. The main limitation is that cosine-only sketches are weak on direction-preserving scale perturbations.

## Scope

- Protocol: offline replay on real checkpoint captures, not online adversarial deployment.
- Pair coverage: 6 strict 40/200 pairs.
- Methods: `scalar16`, `scalar64`, `projcos4`, `projcos8`, `projcos16`.
- Main attacks emphasized in the paper text: `gaussian`, `cross_prompt_stale_substitution`, `wrong_shard_output`, `layer_skip`.
- Negative control: `same_prompt_old_run_replay`.
- Limitation attack: `scale_perturbation`.
- Attack checkpoint: `C2`.
- Output-affecting subset: available only on a focus matrix over `scalar16` and `projcos4`. It is a **next-token top-k output-affecting** study, not yet a full-variant-family result and not a full-generation output study.

## Artifacts

- Selected operating points: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_selected_operating_points.csv`
- Attack summary: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_attack_summary.csv`
- Detail table: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_detail.csv`
- Strength sweep: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_material_tamper_full_matrix_strength_sweep.csv`
- Material focus panel: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_material_tamper_full_matrix_material_focus_panel.png`
- Strength sweep figure: `/Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_material_tamper_full_matrix_strength_sweep_focus.png`

## Coverage Check

- Selected operating points: `30 = 6 pairs x 5 methods`.
- Attack summary rows: `180 = 6 pairs x 5 methods x 6 attacks`.
- Detail rows: `36000 = 6 pairs x 5 methods x 6 attacks x 200 prompts`.
- Strength sweep rows: `360 = 6 pairs x 5 methods x 2 attacks x 6 strengths`.

The selected operating point table now includes `calib_feasible_count`, `selected_from_feasible`, and `selection_fallback_reason`, so scalar fallback rows are visible rather than silently mixed into the main interpretation.

## Main Result

On direction-changing or semantic-substitution attacks, projected-token cosine sketches are consistently strong.

Across all 6 pairs, mean detection rates are:

| Attack family | scalar16 | scalar64 | projcos4 | projcos8 | projcos16 |
|-|-:|-:|-:|-:|-:|
| gaussian | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| cross_prompt_stale_substitution | 0.7608 | 0.8967 | 1.0000 | 1.0000 | 1.0000 |
| wrong_shard_output | 0.7608 | 0.8967 | 1.0000 | 1.0000 | 1.0000 |
| layer_skip | 0.7542 | 0.9817 | 1.0000 | 1.0000 | 1.0000 |

For the two focus pairs:

| Pair | Method | Gaussian | Cross-prompt stale | Wrong-shard output | Layer skip |
|-|-|-:|-:|-:|-:|
| A/B | scalar16 | 1.00 | 0.76 | 0.76 | 0.83 |
| A/B | projcos4 | 1.00 | 1.00 | 1.00 | 1.00 |
| B/D | scalar16 | 1.00 | 0.95 | 0.95 | 1.00 |
| B/D | projcos4 | 1.00 | 1.00 | 1.00 | 1.00 |

This supports the narrower claim that projected-token cosine sketches are effective for attacks that replace, replay, skip, or otherwise change the direction/semantic content of intermediate representations.

## Negative Control

`same_prompt_old_run_replay` should not be used as primary material-tamper evidence.

In this protocol, when a same-prompt old-run donor exists, the replacement is often very close to an honest rerun. Low detection is therefore expected and useful: it shows the verifier is not simply flagging every rerun-consistent checkpoint substitution. This attack is better described as a rerun-consistency negative control.

In the paper, keep it out of the main attack success table or put it in an appendix/control row.

## Limitation: Scale Perturbation

`scale_perturbation` is a direction-preserving attack: it multiplies the target checkpoint tensor by `1 + scale_delta`.

This exposes a real boundary of cosine-only projected-token verification. Because cosine normalizes vector magnitude, pure scaling can preserve direction while changing norm. As a result, `projcos4` is weak on this attack:

| Pair | Method | Scale perturbation TPR at strength 0.15 |
|-|-|-:|
| A/B | scalar16 | 0.52 |
| A/B | projcos4 | 0.00 |
| B/D | scalar16 | 0.72 |
| B/D | projcos4 | 0.00 |

The strength sweep confirms the same pattern: scalar-coordinate checks become more sensitive as scale increases, while projected cosine remains near zero on pure scale changes.

The correct paper wording is:

> Projected-token cosine sketches are strong for direction-changing material tamper, but cosine-only sketches intentionally discard norm information and therefore do not detect pure scale-only perturbations. A norm-aware or hybrid sketch is needed for stronger coverage.

## Output-Affecting Subset

This handbook item is now partially completed via a replay-to-logits pipeline on a focus matrix:

- pair coverage: all 6 strict pairs
- variant coverage: `scalar16`, `projcos4`
- attack coverage: `gaussian`, `cross_prompt_stale_substitution`, `wrong_shard_output`, `layer_skip`, `scale_perturbation`

The implementation replays clean and attacked `C2` tensors through layers 16-23 and then compares next-token logits. A sample is labeled `output_affecting` when:

- `top1_changed == 1`, or
- the clean and attacked top-5 token sets differ

This yields a valid **next-token top-k output-affecting subset**, but not yet a full-variant-family output-affecting matrix and not a full-generation output benchmark.

The main result matches the broader material-tamper story:

- `projcos4` stays near-perfect on output-affecting `cross_prompt_stale_substitution`, `wrong_shard_output`, and `layer_skip`
- `projcos4` still fails on output-affecting `scale_perturbation`

So the subset does not weaken the main message; it sharpens it. The strong claim is limited to direction-changing / semantic-substitution attacks, while the scale-only blind spot remains real.

## Possible Next Step: Hybrid Sketch

The scale perturbation result suggests a small follow-up prototype:

- keep `projcos4` for direction-sensitive detection
- add a low-cost norm statistic, such as per-token projected norm ratio or hidden-state norm gap
- flag mismatch if either cosine gap or norm gap exceeds its calibrated threshold

This would directly answer the reviewer question raised by the scale-only blind spot without abandoning the projected-token approach.
