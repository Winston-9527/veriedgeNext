# exp_e2_20260512_equal_budget_live_ab

- Protocol: select each variant's operating point on calibration-only A/B live captures, then report held-out evaluation metrics on 200 eval prompts.
- Selection rule: prefer calibration honest-hetero FPR <= 0.10; within feasible points maximize (TPR - FPR), then TPR, then LocAcc.
- Variants: scalar16, scalar64, projscalar1_abs, projcos4, projcos16.
- Bridge variant: projscalar1_abs uses 16 prefill tokens x d=1 random projection and compares mean absolute projected gap. The real signature payload is 16 fp32 scalars / 64B per checkpoint on these captures; the handbook table's 256B row appears to contain an arithmetic typo for 16 x 1.
- Candidate grid CSV: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_equal_budget_live_ab_candidate_grid.csv
- Selected summary CSV: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260512_equal_budget_live_ab_selected_summary.csv
- Figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/figures/exp_e2_20260512_equal_budget_live_ab_fpr_tpr_vs_budget.png

## Selected held-out results

- scalar16: bytes/ckpt=64, mode=global_shared, p=99.99, scale=1.5, eval FPR=0.15, eval TPR=1.0, eval LocAcc=1.0, selected_from_feasible=0.
- scalar64: bytes/ckpt=256, mode=global_shared, p=99.99, scale=2.0, eval FPR=0.415, eval TPR=1.0, eval LocAcc=1.0, selected_from_feasible=0.
- projscalar1_abs: bytes/ckpt=64, mode=checkpoint_specific, p=99.0, scale=1.5, eval FPR=0.0, eval TPR=1.0, eval LocAcc=1.0, selected_from_feasible=1.
- projcos4: bytes/ckpt=256, mode=checkpoint_specific, p=99.0, scale=1.5, eval FPR=0.02, eval TPR=1.0, eval LocAcc=1.0, selected_from_feasible=1.
- projcos16: bytes/ckpt=1024, mode=checkpoint_specific, p=99.0, scale=1.5, eval FPR=0.12, eval TPR=1.0, eval LocAcc=1.0, selected_from_feasible=1.
