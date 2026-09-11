# E2-R blindspot table (fixed rho = 0.010, TPR@1%FPR, state by $TPR\le 2\times evalFPR$)

> 单元格格式：TPR [Wilson 95%% CI] (三态)。n=520 下 TPR≈FPR 的盲点标签 CI 跨分界（如 0.010 [0.004,0.022]），joint_null 的 TPR==honest FPR 精确相等故结构性结论稳健。

| attack_family × threat_model | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| sign_balanced_sr · TM1b_knownP | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| null_space_projcos · TM1b_knownP | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| joint_null · TM1b_knownP | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_sr · TM1b_knownP | 0.033 [0.021,0.052] (partial) | 0.046 [0.031,0.068] (partial) | 0.058 [0.041,0.081] (partial) |
| tol_hug_projcos · TM1b_knownP | 0.037 [0.024,0.056] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_combined · TM1b_knownP | 0.031 [0.019,0.049] (partial) | 0.015 [0.008,0.030] (blind) | 0.027 [0.016,0.045] (partial) |

## All injection boundaries (rho = 0.010)
| family × TM × boundary | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| sign_balanced_sr·TM1b_knownP·C1 | - | - | - |
| sign_balanced_sr·TM1b_knownP·C2 | - | - | - |
| sign_balanced_sr·TM1b_knownP·C3 | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| null_space_projcos·TM1b_knownP·C1 | - | - | - |
| null_space_projcos·TM1b_knownP·C2 | - | - | - |
| null_space_projcos·TM1b_knownP·C3 | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| joint_null·TM1b_knownP·C1 | - | - | - |
| joint_null·TM1b_knownP·C2 | - | - | - |
| joint_null·TM1b_knownP·C3 | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_sr·TM1b_knownP·C1 | - | - | - |
| tol_hug_sr·TM1b_knownP·C2 | - | - | - |
| tol_hug_sr·TM1b_knownP·C3 | 0.033 [0.021,0.052] (partial) | 0.046 [0.031,0.068] (partial) | 0.058 [0.041,0.081] (partial) |
| tol_hug_projcos·TM1b_knownP·C1 | - | - | - |
| tol_hug_projcos·TM1b_knownP·C2 | - | - | - |
| tol_hug_projcos·TM1b_knownP·C3 | 0.037 [0.024,0.056] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_combined·TM1b_knownP·C1 | - | - | - |
| tol_hug_combined·TM1b_knownP·C2 | - | - | - |
| tol_hug_combined·TM1b_knownP·C3 | 0.031 [0.019,0.049] (partial) | 0.015 [0.008,0.030] (blind) | 0.027 [0.016,0.045] (partial) |
