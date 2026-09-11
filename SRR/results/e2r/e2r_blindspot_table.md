# E2-R blindspot table (fixed rho = 0.010, TPR@1%FPR, state by $TPR\le 2\times evalFPR$)

> 单元格格式：TPR [Wilson 95%% CI] (三态)。n=520 下 TPR≈FPR 的盲点标签 CI 跨分界（如 0.010 [0.004,0.022]），joint_null 的 TPR==honest FPR 精确相等故结构性结论稳健。

| attack_family × threat_model | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| sign_balanced_sr · TM1_seed_secret | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| sign_balanced_sr · TM2_seed_known | 0.010 [0.004,0.022] (blind) | 0.048 [0.033,0.070] (partial) | 0.040 [0.027,0.061] (partial) |
| null_space_projcos · TM1_seed_secret | 0.040 [0.027,0.061] (partial) | 0.050 [0.034,0.072] (partial) | 0.060 [0.042,0.083] (partial) |
| null_space_projcos · TM2_seed_known | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| joint_null · TM1_seed_secret | 0.040 [0.027,0.061] (partial) | 0.050 [0.034,0.072] (partial) | 0.060 [0.042,0.083] (partial) |
| joint_null · TM2_seed_known | 0.010 [0.004,0.022] (blind) | 0.015 [0.008,0.030] (blind) | 0.010 [0.004,0.022] (blind) |
| tol_hug_sr · TM1_seed_secret | 0.033 [0.021,0.052] (partial) | 0.046 [0.031,0.068] (partial) | 0.058 [0.041,0.081] (partial) |
| tol_hug_sr · TM2_seed_known | 0.008 [0.003,0.020] (blind) | 0.048 [0.033,0.070] (partial) | 0.040 [0.027,0.061] (partial) |
| tol_hug_projcos · TM1_seed_secret | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| tol_hug_projcos · TM2_seed_known | 0.037 [0.024,0.056] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_combined · TM1_seed_secret | 0.031 [0.019,0.049] (partial) | 0.042 [0.028,0.063] (partial) | 0.052 [0.036,0.074] (partial) |
| tol_hug_combined · TM2_seed_known | 0.010 [0.004,0.022] (blind) | 0.015 [0.008,0.030] (blind) | 0.010 [0.004,0.022] (blind) |

## All injection boundaries (rho = 0.010)
| family × TM × boundary | SignRadial | ProjCos4 | Combined |
|---|---|---|---|
| sign_balanced_sr·TM1_seed_secret·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| sign_balanced_sr·TM1_seed_secret·C2 | 0.979 [0.963,0.988] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| sign_balanced_sr·TM1_seed_secret·C3 | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| sign_balanced_sr·TM2_seed_known·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| sign_balanced_sr·TM2_seed_known·C2 | 0.875 [0.844,0.901] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| sign_balanced_sr·TM2_seed_known·C3 | 0.010 [0.004,0.022] (blind) | 0.048 [0.033,0.070] (partial) | 0.040 [0.027,0.061] (partial) |
| null_space_projcos·TM1_seed_secret·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| null_space_projcos·TM1_seed_secret·C2 | 0.971 [0.953,0.982] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| null_space_projcos·TM1_seed_secret·C3 | 0.040 [0.027,0.061] (partial) | 0.050 [0.034,0.072] (partial) | 0.060 [0.042,0.083] (partial) |
| null_space_projcos·TM2_seed_known·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| null_space_projcos·TM2_seed_known·C2 | 0.987 [0.972,0.993] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| null_space_projcos·TM2_seed_known·C3 | 0.038 [0.025,0.059] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| joint_null·TM1_seed_secret·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| joint_null·TM1_seed_secret·C2 | 0.971 [0.953,0.982] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| joint_null·TM1_seed_secret·C3 | 0.040 [0.027,0.061] (partial) | 0.050 [0.034,0.072] (partial) | 0.060 [0.042,0.083] (partial) |
| joint_null·TM2_seed_known·C1 | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| joint_null·TM2_seed_known·C2 | 0.867 [0.835,0.894] (detected) | 1.000 [0.993,1.000] (detected) | 1.000 [0.993,1.000] (detected) |
| joint_null·TM2_seed_known·C3 | 0.010 [0.004,0.022] (blind) | 0.015 [0.008,0.030] (blind) | 0.010 [0.004,0.022] (blind) |
| tol_hug_sr·TM1_seed_secret·C1 | 0.931 [0.906,0.950] (detected) | 0.983 [0.967,0.991] (detected) | 0.985 [0.970,0.992] (detected) |
| tol_hug_sr·TM1_seed_secret·C2 | 0.692 [0.651,0.730] (detected) | 0.873 [0.842,0.899] (detected) | 0.881 [0.850,0.906] (detected) |
| tol_hug_sr·TM1_seed_secret·C3 | 0.033 [0.021,0.052] (partial) | 0.046 [0.031,0.068] (partial) | 0.058 [0.041,0.081] (partial) |
| tol_hug_sr·TM2_seed_known·C1 | 0.890 [0.861,0.914] (detected) | 0.956 [0.935,0.970] (detected) | 0.971 [0.953,0.982] (detected) |
| tol_hug_sr·TM2_seed_known·C2 | 0.513 [0.471,0.556] (detected) | 0.773 [0.735,0.807] (detected) | 0.785 [0.747,0.818] (detected) |
| tol_hug_sr·TM2_seed_known·C3 | 0.008 [0.003,0.020] (blind) | 0.048 [0.033,0.070] (partial) | 0.040 [0.027,0.061] (partial) |
| tol_hug_projcos·TM1_seed_secret·C1 | 0.512 [0.469,0.554] (detected) | 0.660 [0.618,0.699] (detected) | 0.688 [0.647,0.727] (detected) |
| tol_hug_projcos·TM1_seed_secret·C2 | 0.060 [0.042,0.083] (partial) | 0.154 [0.125,0.187] (partial) | 0.138 [0.111,0.171] (partial) |
| tol_hug_projcos·TM1_seed_secret·C3 | 0.037 [0.024,0.056] (partial) | 0.048 [0.033,0.070] (partial) | 0.062 [0.044,0.086] (partial) |
| tol_hug_projcos·TM2_seed_known·C1 | 0.606 [0.563,0.647] (detected) | 0.775 [0.737,0.809] (detected) | 0.804 [0.768,0.836] (detected) |
| tol_hug_projcos·TM2_seed_known·C2 | 0.327 [0.288,0.368] (partial) | 0.565 [0.522,0.607] (detected) | 0.579 [0.536,0.621] (detected) |
| tol_hug_projcos·TM2_seed_known·C3 | 0.037 [0.024,0.056] (partial) | 0.015 [0.008,0.030] (blind) | 0.031 [0.019,0.049] (partial) |
| tol_hug_combined·TM1_seed_secret·C1 | 0.331 [0.292,0.372] (partial) | 0.410 [0.368,0.452] (partial) | 0.437 [0.395,0.479] (partial) |
| tol_hug_combined·TM1_seed_secret·C2 | 0.027 [0.016,0.045] (partial) | 0.079 [0.059,0.105] (partial) | 0.067 [0.049,0.092] (partial) |
| tol_hug_combined·TM1_seed_secret·C3 | 0.031 [0.019,0.049] (partial) | 0.042 [0.028,0.063] (partial) | 0.052 [0.036,0.074] (partial) |
| tol_hug_combined·TM2_seed_known·C1 | 0.383 [0.342,0.425] (partial) | 0.537 [0.494,0.579] (detected) | 0.567 [0.524,0.609] (detected) |
| tol_hug_combined·TM2_seed_known·C2 | 0.162 [0.132,0.196] (partial) | 0.375 [0.334,0.417] (partial) | 0.381 [0.340,0.423] (partial) |
| tol_hug_combined·TM2_seed_known·C3 | 0.010 [0.004,0.022] (blind) | 0.015 [0.008,0.030] (blind) | 0.010 [0.004,0.022] (blind) |
