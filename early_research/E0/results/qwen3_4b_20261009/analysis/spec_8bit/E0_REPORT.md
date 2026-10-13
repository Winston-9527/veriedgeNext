# E0 自动报告（ref = `torch_fp32`）

- contexts：33280（520 个 prompt）；α=0.001，β=0.001
- 诚实栈：torch_bf16, torch_fp16, mlx_bf16, apple_mps_bf16, apple_mps_fp16, apple_mlx_bf16, torch_rtn_w8g128, torch_bnb_int8, mlx_8bit, apple_mlx_8bit；作弊栈：torch_rtn_w4g128, torch_gptq_w4g128, torch_bnb_nf4, mlx_q4, apple_mps_rtn_w4g128, apple_mlx_q4, mlx_q4_L0-11, mlx_q4_L12-23, mlx_q4_L24-35, torch_gptq_w4g128_L0-11, torch_gptq_w4g128_L12-23, torch_gptq_w4g128_L24-35, torch_rtn_w4g128_L0-11, torch_rtn_w4g128_L12-23, torch_rtn_w4g128_L24-35；升级目标：`mlx_8bit`

## A. 总体 top-1 失配率

| 栈 | 角色 | 失配率 | 95% CI | 翻转处自身 margin 中位数 | 全体自身 margin 中位数 |
|---|---|---|---|---|---|
| `torch_bf16` | honest | 0.0134 | [0.0122, 0.0145] | 0.000 | 2.000 |
| `torch_fp16` | honest | 0.0017 | [0.0013, 0.0022] | 0.000 | 2.047 |
| `mlx_bf16` | honest | 0.0133 | [0.0121, 0.0145] | 0.000 | 2.000 |
| `apple_mps_bf16` | honest | 0.0142 | [0.0129, 0.0156] | 0.000 | 2.000 |
| `apple_mps_fp16` | honest | 0.0016 | [0.0012, 0.0020] | 0.000 | 2.047 |
| `apple_mlx_bf16` | honest | 0.0129 | [0.0118, 0.0141] | 0.000 | 2.000 |
| `torch_rtn_w8g128` | honest | 0.0167 | [0.0154, 0.0181] | 0.000 | 2.000 |
| `torch_bnb_int8` | honest | 0.0407 | [0.0383, 0.0429] | 0.141 | 2.047 |
| `mlx_8bit` | honest | 0.0188 | [0.0174, 0.0202] | 0.000 | 2.000 |
| `apple_mlx_8bit` | honest | 0.0184 | [0.0169, 0.0198] | 0.000 | 2.000 |
| `torch_rtn_w4g128` | cheat | 0.1280 | [0.1240, 0.1319] | 0.375 | 2.125 |
| `torch_gptq_w4g128` | cheat | 0.0627 | [0.0597, 0.0654] | 0.250 | 2.000 |
| `torch_bnb_nf4` | cheat | 0.1137 | [0.1097, 0.1173] | 0.375 | 2.000 |
| `mlx_q4` | cheat | 0.1315 | [0.1273, 0.1357] | 0.375 | 2.125 |
| `apple_mps_rtn_w4g128` | cheat | 0.1274 | [0.1234, 0.1313] | 0.375 | 2.125 |
| `apple_mlx_q4` | cheat | 0.1325 | [0.1284, 0.1367] | 0.375 | 2.125 |
| `mlx_q4_L0-11` | cheat | 0.0625 | [0.0598, 0.0653] | 0.250 | 2.000 |
| `mlx_q4_L12-23` | cheat | 0.0724 | [0.0694, 0.0755] | 0.250 | 2.125 |
| `mlx_q4_L24-35` | cheat | 0.0653 | [0.0624, 0.0681] | 0.250 | 2.125 |
| `torch_gptq_w4g128_L0-11` | cheat | 0.0343 | [0.0322, 0.0363] | 0.125 | 2.000 |
| `torch_gptq_w4g128_L12-23` | cheat | 0.0413 | [0.0391, 0.0433] | 0.125 | 2.000 |
| `torch_gptq_w4g128_L24-35` | cheat | 0.0348 | [0.0327, 0.0369] | 0.125 | 2.000 |
| `torch_rtn_w4g128_L0-11` | cheat | 0.0713 | [0.0683, 0.0743] | 0.250 | 2.000 |
| `torch_rtn_w4g128_L12-23` | cheat | 0.0831 | [0.0800, 0.0865] | 0.250 | 2.125 |
| `torch_rtn_w4g128_L24-35` | cheat | 0.0706 | [0.0676, 0.0736] | 0.250 | 2.125 |

诚实栈最大失配率（全局）：0.0407

## C. 升级攻击（区间在偶数 prompt 上选、奇数 prompt 上报告；p_h 用 Wilson 95% 上界）

| 作弊栈 | 升级成本 | 残余失配(全体) | 区间 p_h(上界) | 区间 p_q | N*(Chernoff) | N(exact) |
|---|---|---|---|---|---|---|
| `torch_rtn_w4g128` | 0.000 | 0.1280 | 0.0888 | 0.3207 | 32.56 | 109 |
| `torch_rtn_w4g128` | 0.010 | 0.1231 | 0.0888 | 0.3041 | 37.01 | 124 |
| `torch_rtn_w4g128` | 0.020 | 0.1184 | 0.0321 | 0.1844 | 37.86 | 139 |
| `torch_rtn_w4g128` | 0.050 | 0.1040 | 0.0213 | 0.1198 | 60.75 | 230 |
| `torch_rtn_w4g128` | 0.100 | 0.0852 | 0.0139 | 0.0681 | 124.09 | 471 |
| `torch_rtn_w4g128` | 0.200 | 0.0567 | 0.0036 | 0.0315 | 168.82 | 713 |
| `torch_rtn_w4g128` | 0.300 | 0.0389 | 0.0036 | 0.0220 | 319.17 | 1222 |
| `torch_rtn_w4g128` | 0.500 | 0.0239 | 0.0036 | 0.0065 | 7057.71 | — |
| `torch_gptq_w4g128` | 0.000 | 0.0627 | 0.0575 | 0.1028 | 443.49 | 1362 |
| `torch_gptq_w4g128` | 0.010 | 0.0587 | 0.0321 | 0.0513 | 1376.08 | 4132 |
| `torch_gptq_w4g128` | 0.020 | 0.0544 | 0.0321 | 0.0483 | 1888.22 | 5649 |
| `torch_gptq_w4g128` | 0.050 | 0.0455 | 0.0076 | 0.0117 | 7087.86 | — |
| `torch_gptq_w4g128` | 0.100 | 0.0358 | 0.0036 | 0.0053 | 18300.22 | — |
| `torch_gptq_w4g128` | 0.200 | 0.0263 | 0.0036 | 0.0018 | ∞ | — |
| `torch_gptq_w4g128` | 0.300 | 0.0221 | 0.0036 | 0.0006 | ∞ | — |
| `torch_gptq_w4g128` | 0.500 | 0.0193 | 0.3133 | 0.1864 | ∞ | — |
| `torch_bnb_nf4` | 0.000 | 0.1137 | 0.0888 | 0.3133 | 34.43 | 116 |
| `torch_bnb_nf4` | 0.010 | 0.1086 | 0.0888 | 0.2955 | 39.71 | 128 |
| `torch_bnb_nf4` | 0.020 | 0.1037 | 0.0888 | 0.2857 | 43.21 | 142 |
| `torch_bnb_nf4` | 0.050 | 0.0905 | 0.0321 | 0.1348 | 71.74 | 254 |
| `torch_bnb_nf4` | 0.100 | 0.0725 | 0.0321 | 0.1020 | 136.68 | 466 |
| `torch_bnb_nf4` | 0.200 | 0.0471 | 0.0076 | 0.0255 | 522.33 | 1789 |
| `torch_bnb_nf4` | 0.300 | 0.0328 | 0.0036 | 0.0143 | 761.45 | 2752 |
| `torch_bnb_nf4` | 0.500 | 0.0217 | 0.0018 | 0.0012 | ∞ | — |
| `mlx_q4` | 0.000 | 0.1315 | 0.0888 | 0.3642 | 24.23 | 85 |
| `mlx_q4` | 0.010 | 0.1268 | 0.0888 | 0.3470 | 27.06 | 89 |
| `mlx_q4` | 0.020 | 0.1212 | 0.0888 | 0.3329 | 29.8 | 101 |
| `mlx_q4` | 0.050 | 0.1068 | 0.0575 | 0.2232 | 45.27 | 156 |
| `mlx_q4` | 0.100 | 0.0848 | 0.0321 | 0.1277 | 80.84 | 289 |
| `mlx_q4` | 0.200 | 0.0529 | 0.0076 | 0.0267 | 468.79 | 1660 |
| `mlx_q4` | 0.300 | 0.0353 | 0.0036 | 0.0089 | 2463.82 | 7961 |
| `mlx_q4` | 0.500 | 0.0224 | 0.3133 | 0.1973 | ∞ | — |
| `apple_mps_rtn_w4g128` | 0.000 | 0.1274 | 0.0321 | 0.2017 | 31.89 | 120 |
| `apple_mps_rtn_w4g128` | 0.010 | 0.1227 | 0.0321 | 0.1915 | 35.18 | 127 |
| `apple_mps_rtn_w4g128` | 0.020 | 0.1175 | 0.0213 | 0.1430 | 43.54 | 162 |
| `apple_mps_rtn_w4g128` | 0.050 | 0.1042 | 0.0213 | 0.1244 | 56.58 | 210 |
| `apple_mps_rtn_w4g128` | 0.100 | 0.0848 | 0.0139 | 0.0681 | 124.09 | 471 |
| `apple_mps_rtn_w4g128` | 0.200 | 0.0567 | 0.0076 | 0.0355 | 253.82 | 951 |
| `apple_mps_rtn_w4g128` | 0.300 | 0.0395 | 0.0036 | 0.0196 | 396.44 | 1515 |
| `apple_mps_rtn_w4g128` | 0.500 | 0.0238 | 0.0036 | 0.0065 | 7057.71 | — |
| `apple_mlx_q4` | 0.000 | 0.1325 | 0.0888 | 0.3660 | 23.96 | 81 |
| `apple_mlx_q4` | 0.010 | 0.1274 | 0.0888 | 0.3532 | 25.99 | 88 |
| `apple_mlx_q4` | 0.020 | 0.1219 | 0.0888 | 0.3348 | 29.42 | 101 |
| `apple_mlx_q4` | 0.050 | 0.1075 | 0.0888 | 0.2808 | 45.15 | 149 |
| `apple_mlx_q4` | 0.100 | 0.0850 | 0.0213 | 0.0991 | 88.85 | 321 |
| `apple_mlx_q4` | 0.200 | 0.0534 | 0.0139 | 0.0377 | 487.69 | 1645 |
| `apple_mlx_q4` | 0.300 | 0.0351 | 0.0076 | 0.0135 | 3633.88 | 11150 |
| `apple_mlx_q4` | 0.500 | 0.0221 | 0.3133 | 0.1961 | ∞ | — |
| `mlx_q4_L0-11` | 0.000 | 0.0625 | 0.0575 | 0.1001 | 497.01 | 1513 |
| `mlx_q4_L0-11` | 0.010 | 0.0580 | 0.0213 | 0.0422 | 846.22 | 2661 |
| `mlx_q4_L0-11` | 0.020 | 0.0531 | 0.0213 | 0.0385 | 1194.71 | 3662 |
| `mlx_q4_L0-11` | 0.050 | 0.0452 | 0.0139 | 0.0195 | 6791.01 | — |
| `mlx_q4_L0-11` | 0.100 | 0.0355 | 0.0139 | 0.0152 | 108887.42 | — |
| `mlx_q4_L0-11` | 0.200 | 0.0261 | 0.0076 | 0.0075 | ∞ | — |
| `mlx_q4_L0-11` | 0.300 | 0.0225 | 0.3133 | 0.1949 | ∞ | — |
| `mlx_q4_L0-11` | 0.500 | 0.0195 | 0.3133 | 0.1882 | ∞ | — |
| `mlx_q4_L12-23` | 0.000 | 0.0724 | 0.0888 | 0.1796 | 171.11 | 528 |
| `mlx_q4_L12-23` | 0.010 | 0.0687 | 0.0888 | 0.1662 | 229.59 | 712 |
| `mlx_q4_L12-23` | 0.020 | 0.0643 | 0.0888 | 0.1502 | 351.8 | 1054 |
| `mlx_q4_L12-23` | 0.050 | 0.0549 | 0.0213 | 0.0431 | 784.08 | 2469 |
| `mlx_q4_L12-23` | 0.100 | 0.0425 | 0.0139 | 0.0188 | 8450.25 | — |
| `mlx_q4_L12-23` | 0.200 | 0.0289 | 0.0139 | 0.0097 | ∞ | — |
| `mlx_q4_L12-23` | 0.300 | 0.0232 | 0.3133 | 0.1937 | ∞ | — |
| `mlx_q4_L12-23` | 0.500 | 0.0195 | 0.3133 | 0.1894 | ∞ | — |
| `mlx_q4_L24-35` | 0.000 | 0.0653 | 0.0888 | 0.1576 | 285.18 | 860 |
| `mlx_q4_L24-35` | 0.010 | 0.0611 | 0.0888 | 0.1422 | 456.07 | 1359 |
| `mlx_q4_L24-35` | 0.020 | 0.0565 | 0.0888 | 0.1300 | 745.52 | 2219 |
| `mlx_q4_L24-35` | 0.050 | 0.0472 | 0.0888 | 0.1006 | 8471.49 | — |
| `mlx_q4_L24-35` | 0.100 | 0.0350 | 0.0036 | 0.0024 | ∞ | — |
| `mlx_q4_L24-35` | 0.200 | 0.0244 | 0.0036 | 0.0012 | ∞ | — |
| `mlx_q4_L24-35` | 0.300 | 0.0207 | 0.3133 | 0.1906 | ∞ | — |
| `mlx_q4_L24-35` | 0.500 | 0.0190 | 0.3133 | 0.1876 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.000 | 0.0343 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.010 | 0.0313 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.020 | 0.0281 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.050 | 0.0247 | 0.0036 | 0.0018 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.100 | 0.0226 | 0.3133 | 0.1967 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.200 | 0.0204 | 0.3133 | 0.1961 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.300 | 0.0194 | 0.3133 | 0.1876 | ∞ | — |
| `torch_gptq_w4g128_L0-11` | 0.500 | 0.0189 | 0.3133 | 0.1876 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.000 | 0.0413 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.010 | 0.0382 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.020 | 0.0349 | 0.0036 | 0.0024 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.050 | 0.0290 | 0.0036 | 0.0018 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.100 | 0.0245 | 0.3133 | 0.1906 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.200 | 0.0207 | 0.3133 | 0.1888 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.300 | 0.0196 | 0.3133 | 0.1882 | ∞ | — |
| `torch_gptq_w4g128_L12-23` | 0.500 | 0.0190 | 0.3133 | 0.1876 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.000 | 0.0348 | 0.3133 | 0.2708 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.010 | 0.0317 | 0.3133 | 0.2544 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.020 | 0.0286 | 0.3133 | 0.2295 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.050 | 0.0249 | 0.3133 | 0.2137 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.100 | 0.0224 | 0.3133 | 0.2004 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.200 | 0.0202 | 0.3133 | 0.1906 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.300 | 0.0193 | 0.3133 | 0.1906 | ∞ | — |
| `torch_gptq_w4g128_L24-35` | 0.500 | 0.0188 | 0.3133 | 0.1876 | ∞ | — |
| `torch_rtn_w4g128_L0-11` | 0.000 | 0.0713 | 0.0888 | 0.1778 | 177.6 | 547 |
| `torch_rtn_w4g128_L0-11` | 0.010 | 0.0668 | 0.0888 | 0.1619 | 255.02 | 781 |
| `torch_rtn_w4g128_L0-11` | 0.020 | 0.0622 | 0.0575 | 0.1028 | 443.49 | 1362 |
| `torch_rtn_w4g128_L0-11` | 0.050 | 0.0535 | 0.0036 | 0.0154 | 641.12 | 2367 |
| `torch_rtn_w4g128_L0-11` | 0.100 | 0.0422 | 0.0036 | 0.0137 | 836.51 | 2969 |
| `torch_rtn_w4g128_L0-11` | 0.200 | 0.0297 | 0.0036 | 0.0095 | 2051.26 | 6815 |
| `torch_rtn_w4g128_L0-11` | 0.300 | 0.0242 | 0.0036 | 0.0059 | 10657.25 | — |
| `torch_rtn_w4g128_L0-11` | 0.500 | 0.0200 | 0.3133 | 0.1870 | ∞ | — |
| `torch_rtn_w4g128_L12-23` | 0.000 | 0.0831 | 0.0888 | 0.2158 | 93.51 | 294 |
| `torch_rtn_w4g128_L12-23` | 0.010 | 0.0783 | 0.0888 | 0.1987 | 121.31 | 381 |
| `torch_rtn_w4g128_L12-23` | 0.020 | 0.0738 | 0.0888 | 0.1833 | 159.19 | 498 |
| `torch_rtn_w4g128_L12-23` | 0.050 | 0.0642 | 0.0575 | 0.1119 | 317.79 | 993 |
| `torch_rtn_w4g128_L12-23` | 0.100 | 0.0494 | 0.0146 | 0.0278 | 1439.65 | 4508 |
| `torch_rtn_w4g128_L12-23` | 0.200 | 0.0328 | 0.0036 | 0.0053 | 18300.22 | — |
| `torch_rtn_w4g128_L12-23` | 0.300 | 0.0255 | 0.0012 | 0.0010 | ∞ | — |
| `torch_rtn_w4g128_L12-23` | 0.500 | 0.0199 | 0.3133 | 0.1888 | ∞ | — |
| `torch_rtn_w4g128_L24-35` | 0.000 | 0.0706 | 0.0888 | 0.1815 | 164.98 | 516 |
| `torch_rtn_w4g128_L24-35` | 0.010 | 0.0659 | 0.0888 | 0.1692 | 213.78 | 658 |
| `torch_rtn_w4g128_L24-35` | 0.020 | 0.0618 | 0.0888 | 0.1533 | 321.35 | 966 |
| `torch_rtn_w4g128_L24-35` | 0.050 | 0.0525 | 0.0888 | 0.1183 | 1406.72 | 4093 |
| `torch_rtn_w4g128_L24-35` | 0.100 | 0.0392 | 0.0076 | 0.0087 | 84985.0 | — |
| `torch_rtn_w4g128_L24-35` | 0.200 | 0.0265 | 0.3133 | 0.1998 | ∞ | — |
| `torch_rtn_w4g128_L24-35` | 0.300 | 0.0221 | 0.3133 | 0.1900 | ∞ | — |
| `torch_rtn_w4g128_L24-35` | 0.500 | 0.0194 | 0.3133 | 0.1882 | ∞ | — |

**预注册判据**（N 取精确二项设计；升级成本 ≤10% 时 N ≥ max(10·N(无升级), 1000)）：

- `torch_rtn_w4g128`：N(无升级)=109，N(成本≤10%)=471 → motivation_holds = **False**
- `torch_gptq_w4g128`：N(无升级)=1362，N(成本≤10%)=None → motivation_holds = **True**
- `torch_bnb_nf4`：N(无升级)=116，N(成本≤10%)=466 → motivation_holds = **False**
- `mlx_q4`：N(无升级)=85，N(成本≤10%)=289 → motivation_holds = **False**
- `apple_mps_rtn_w4g128`：N(无升级)=120，N(成本≤10%)=471 → motivation_holds = **False**
- `apple_mlx_q4`：N(无升级)=81，N(成本≤10%)=321 → motivation_holds = **False**
- `mlx_q4_L0-11`：N(无升级)=1513，N(成本≤10%)=None → motivation_holds = **True**
- `mlx_q4_L12-23`：N(无升级)=528，N(成本≤10%)=None → motivation_holds = **True**
- `mlx_q4_L24-35`：N(无升级)=860，N(成本≤10%)=None → motivation_holds = **True**
- `torch_gptq_w4g128_L0-11`：N(无升级)=None，N(成本≤10%)=None → motivation_holds = **None**
- `torch_gptq_w4g128_L12-23`：N(无升级)=None，N(成本≤10%)=None → motivation_holds = **None**
- `torch_gptq_w4g128_L24-35`：N(无升级)=None，N(成本≤10%)=None → motivation_holds = **None**
- `torch_rtn_w4g128_L0-11`：N(无升级)=547，N(成本≤10%)=2969 → motivation_holds = **False**
- `torch_rtn_w4g128_L12-23`：N(无升级)=294，N(成本≤10%)=4508 → motivation_holds = **True**
- `torch_rtn_w4g128_L24-35`：N(无升级)=516，N(成本≤10%)=None → motivation_holds = **True**

## D. 量化器感知的 canary 池（选翻转且 selector 最自信的 K 个 context）

| selector | oracle | K | 作弊栈 | 升级成本 | p_h(上界) | p_q | N(exact) |
|---|---|---|---|---|---|---|---|
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.000 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.050 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.100 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.200 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.000 | 0.3725 | 0.4200 | 4066 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.050 | 0.3725 | 0.3800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.100 | 0.3725 | 0.3600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.200 | 0.3725 | 0.3200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.3725 | 0.3600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.3725 | 0.6000 | 182 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.3725 | 0.5800 | 224 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.3725 | 0.5600 | 270 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.3725 | 1.0000 | 7 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.3725 | 0.6200 | 156 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.3725 | 0.5800 | 224 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.3725 | 0.5200 | 430 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.000 | 0.3725 | 0.4400 | 2036 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.050 | 0.3725 | 0.4000 | 11990 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.100 | 0.3725 | 0.4000 | 11990 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.200 | 0.3725 | 0.3200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.000 | 0.3725 | 0.3000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.050 | 0.3725 | 0.2400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.100 | 0.3725 | 0.2400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.200 | 0.3725 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.000 | 0.3725 | 0.3400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.050 | 0.3725 | 0.3000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.100 | 0.3725 | 0.2800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.200 | 0.3725 | 0.2600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.3725 | 0.2200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.3725 | 0.1800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.3725 | 0.1800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.3725 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.3725 | 0.1600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.3725 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.3725 | 0.1000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.3725 | 0.0600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.3725 | 0.1600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.3725 | 0.1600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.3725 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.3725 | 0.1000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.3725 | 0.6800 | 99 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.3725 | 0.6200 | 156 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.3725 | 0.6000 | 182 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.3725 | 0.5400 | 339 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.3725 | 0.6200 | 156 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.3725 | 0.5600 | 270 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.3725 | 0.5000 | 580 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.3725 | 0.4400 | 2036 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.3725 | 0.4800 | 807 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.3725 | 0.4600 | 1211 |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.3725 | 0.3400 | ∞ |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.000 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.050 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.100 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.200 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.000 | 0.2664 | 0.3750 | 704 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.050 | 0.2664 | 0.3350 | 1715 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.100 | 0.2664 | 0.2850 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.200 | 0.2664 | 0.2350 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.2664 | 0.5050 | 159 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.2664 | 0.4850 | 182 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.2664 | 0.4500 | 263 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.2664 | 0.3750 | 704 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.2664 | 0.5850 | 87 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.2664 | 0.5600 | 104 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.2664 | 0.5200 | 138 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.2664 | 0.4600 | 235 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.2664 | 1.0000 | 6 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.2664 | 0.5900 | 86 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.2664 | 0.5350 | 123 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.2664 | 0.5150 | 149 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.2664 | 0.4650 | 225 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.000 | 0.2664 | 0.4200 | 368 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.050 | 0.2664 | 0.3650 | 851 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.100 | 0.2664 | 0.3050 | 5260 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.200 | 0.2664 | 0.2300 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.000 | 0.2664 | 0.3500 | 1183 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.050 | 0.2664 | 0.3250 | 2339 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.100 | 0.2664 | 0.2700 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.200 | 0.2664 | 0.2050 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.000 | 0.2664 | 0.3200 | 2775 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.050 | 0.2664 | 0.2800 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.100 | 0.2664 | 0.2300 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.200 | 0.2664 | 0.1750 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.2664 | 0.2350 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.2664 | 0.1900 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.2664 | 0.1650 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.2664 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.2664 | 0.2250 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.2664 | 0.1850 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.2664 | 0.1600 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.2664 | 0.1150 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.2664 | 0.1700 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.2664 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.2664 | 0.1050 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.2664 | 0.0750 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.2664 | 0.6400 | 68 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.2664 | 0.5550 | 112 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.2664 | 0.5400 | 122 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.2664 | 0.4600 | 235 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.2664 | 0.6350 | 68 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.2664 | 0.6050 | 80 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.2664 | 0.5450 | 116 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.2664 | 0.4700 | 215 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.2664 | 0.4850 | 182 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.2664 | 0.4300 | 323 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.2664 | 0.4050 | 440 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.2664 | 0.3050 | 5260 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.000 | 0.2351 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.050 | 0.2351 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.100 | 0.2351 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.200 | 0.2351 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.000 | 0.2351 | 0.3180 | 1114 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.050 | 0.2351 | 0.2590 | 12432 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.100 | 0.2351 | 0.2220 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.200 | 0.2351 | 0.1680 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.2351 | 0.4580 | 172 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.2351 | 0.3990 | 308 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.2351 | 0.3440 | 669 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.2351 | 0.2670 | 7051 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.2351 | 0.5530 | 87 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.2351 | 0.5120 | 113 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.2351 | 0.4510 | 182 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.2351 | 0.3530 | 571 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.2351 | 0.9990 | 7 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.2351 | 0.9980 | 7 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.2351 | 0.9980 | 7 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.2351 | 0.9910 | 9 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.2351 | 0.5560 | 84 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.2351 | 0.4930 | 130 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.2351 | 0.4510 | 182 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.2351 | 0.3650 | 476 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.000 | 0.2351 | 0.3600 | 510 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.050 | 0.2351 | 0.2930 | 2223 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.100 | 0.2351 | 0.2480 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.200 | 0.2351 | 0.1790 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.000 | 0.2351 | 0.3610 | 509 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.050 | 0.2351 | 0.3110 | 1322 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.100 | 0.2351 | 0.2630 | 9176 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.200 | 0.2351 | 0.1890 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.000 | 0.2351 | 0.3070 | 1461 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.050 | 0.2351 | 0.2530 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.100 | 0.2351 | 0.2070 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.200 | 0.2351 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.2351 | 0.1900 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.2351 | 0.1530 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.2351 | 0.1300 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.2351 | 0.1010 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.2351 | 0.2110 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.2351 | 0.1660 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.2351 | 0.1410 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.2351 | 0.0990 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.2351 | 0.1740 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.2351 | 0.1430 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.2351 | 0.1170 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.2351 | 0.0960 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.2351 | 0.5230 | 104 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.2351 | 0.4510 | 182 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.2351 | 0.3920 | 337 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.2351 | 0.2820 | 3345 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.2351 | 0.6090 | 64 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.2351 | 0.5290 | 103 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.2351 | 0.4500 | 188 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.2351 | 0.3330 | 816 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.2351 | 0.4730 | 154 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.2351 | 0.4180 | 250 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.2351 | 0.3500 | 601 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.2351 | 0.2390 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.000 | 0.4963 | 0.6200 | 622 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.050 | 0.4963 | 0.6200 | 622 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.100 | 0.4963 | 0.5200 | 17055 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.200 | 0.4963 | 0.4800 | ∞ |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.000 | 0.4963 | 1.0000 | 10 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.050 | 0.4963 | 1.0000 | 10 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.100 | 0.4963 | 1.0000 | 10 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.200 | 0.4963 | 1.0000 | 10 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.4963 | 0.5800 | 1357 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.4963 | 0.5600 | 2352 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.4963 | 0.5200 | 17055 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.4963 | 0.4600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.4963 | 0.6400 | 458 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.4963 | 0.6200 | 622 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.4963 | 0.5600 | 2352 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.4963 | 0.5000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.4963 | 0.5800 | 1357 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.4963 | 0.5400 | 5013 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.4963 | 0.5400 | 5013 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.4963 | 0.5200 | 17055 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.4963 | 0.6400 | 458 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.4963 | 0.6000 | 883 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.4963 | 0.5600 | 2352 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.4963 | 0.5200 | 17055 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.000 | 0.4963 | 0.4800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.050 | 0.4963 | 0.4800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.100 | 0.4963 | 0.4800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L0-11` | 0.200 | 0.4963 | 0.3800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.000 | 0.4963 | 0.4000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.050 | 0.4963 | 0.3400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.100 | 0.4963 | 0.3200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L12-23` | 0.200 | 0.4963 | 0.2400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.000 | 0.4963 | 0.2800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.050 | 0.4963 | 0.2400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.100 | 0.4963 | 0.2200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4_L24-35` | 0.200 | 0.4963 | 0.2400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.4963 | 0.6600 | 353 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.4963 | 0.6200 | 622 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.4963 | 0.6400 | 458 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.4963 | 0.4600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.4963 | 0.7200 | 182 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.4963 | 0.6600 | 353 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.4963 | 0.6200 | 622 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.4963 | 0.5200 | 17055 |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.4963 | 0.3800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.4963 | 0.3000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.4963 | 0.2800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.4963 | 0.2400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.4963 | 0.4800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.4963 | 0.4400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.4963 | 0.3800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.4963 | 0.3600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.4963 | 0.5800 | 1357 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.4963 | 0.5000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.4963 | 0.4200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.4963 | 0.3600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.4963 | 0.3600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.4963 | 0.3400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.4963 | 0.3200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.4963 | 0.3200 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.000 | 0.3505 | 0.5950 | 160 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.050 | 0.3505 | 0.5500 | 235 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.100 | 0.3505 | 0.5000 | 414 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.200 | 0.3505 | 0.4450 | 1024 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.000 | 0.3505 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.050 | 0.3505 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.100 | 0.3505 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.200 | 0.3505 | 1.0000 | 7 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.3505 | 0.5200 | 326 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.3505 | 0.4800 | 552 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.3505 | 0.4500 | 937 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.3505 | 0.3450 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.3505 | 0.5200 | 326 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.3505 | 0.4950 | 445 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.3505 | 0.4750 | 596 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.3505 | 0.4100 | 2554 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.3505 | 0.5900 | 165 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.3505 | 0.5550 | 229 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.3505 | 0.5250 | 310 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.3505 | 0.4300 | 1446 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.3505 | 0.5450 | 248 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.3505 | 0.4900 | 483 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.3505 | 0.4700 | 653 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.3505 | 0.4000 | 3681 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.000 | 0.3505 | 0.4000 | 3681 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.050 | 0.3505 | 0.3600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.100 | 0.3505 | 0.3250 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L0-11` | 0.200 | 0.3505 | 0.2900 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.000 | 0.3505 | 0.3850 | 7495 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.050 | 0.3505 | 0.3300 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.100 | 0.3505 | 0.2950 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L12-23` | 0.200 | 0.3505 | 0.2600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.000 | 0.3505 | 0.3300 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.050 | 0.3505 | 0.2700 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.100 | 0.3505 | 0.2450 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4_L24-35` | 0.200 | 0.3505 | 0.1900 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.3505 | 0.4950 | 445 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.3505 | 0.4450 | 1024 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.3505 | 0.4150 | 2187 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.3505 | 0.2850 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.3505 | 0.6300 | 121 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.3505 | 0.5800 | 180 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.3505 | 0.5050 | 397 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.3505 | 0.3550 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.3505 | 0.4750 | 596 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.3505 | 0.4050 | 3037 |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.3505 | 0.3550 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.3505 | 0.2750 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.3505 | 0.4450 | 1024 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.3505 | 0.4000 | 3681 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.3505 | 0.3500 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.3505 | 0.3050 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.3505 | 0.5100 | 365 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.3505 | 0.4250 | 1641 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.3505 | 0.3650 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.3505 | 0.2900 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.3505 | 0.3750 | 14741 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.3505 | 0.3400 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.3505 | 0.3050 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.3505 | 0.2450 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.000 | 0.3090 | 0.5460 | 168 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.050 | 0.3090 | 0.4980 | 258 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.100 | 0.3090 | 0.4530 | 439 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.200 | 0.3090 | 0.3580 | 3546 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.000 | 0.3090 | 1.0000 | 6 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.050 | 0.3090 | 1.0000 | 6 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.100 | 0.3090 | 0.8590 | 27 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.200 | 0.3090 | 0.4410 | 513 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.3090 | 0.5100 | 232 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.3090 | 0.4590 | 407 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.3090 | 0.4060 | 935 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.3090 | 0.3070 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.3090 | 0.5340 | 185 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.3090 | 0.4850 | 300 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.3090 | 0.4290 | 616 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.3090 | 0.3370 | 10695 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.3090 | 0.5560 | 152 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.3090 | 0.4950 | 269 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.3090 | 0.4460 | 483 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.3090 | 0.3550 | 4028 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.3090 | 0.5430 | 171 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.3090 | 0.4840 | 303 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.3090 | 0.4310 | 601 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.3090 | 0.3420 | 7749 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.000 | 0.3090 | 0.4090 | 884 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.050 | 0.3090 | 0.3380 | 10004 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.100 | 0.3090 | 0.2810 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L0-11` | 0.200 | 0.3090 | 0.2110 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.000 | 0.3090 | 0.3850 | 1514 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.050 | 0.3090 | 0.3210 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.100 | 0.3090 | 0.2660 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L12-23` | 0.200 | 0.3090 | 0.2020 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.000 | 0.3090 | 0.3590 | 3423 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.050 | 0.3090 | 0.2960 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.100 | 0.3090 | 0.2500 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4_L24-35` | 0.200 | 0.3090 | 0.1790 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.000 | 0.3090 | 0.4170 | 764 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.050 | 0.3090 | 0.3500 | 5040 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.100 | 0.3090 | 0.2690 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L0-11` | 0.200 | 0.3090 | 0.1880 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.000 | 0.3090 | 0.5380 | 175 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.050 | 0.3090 | 0.4320 | 597 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.100 | 0.3090 | 0.3350 | 12426 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L12-23` | 0.200 | 0.3090 | 0.2140 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.000 | 0.3090 | 0.4270 | 640 |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.050 | 0.3090 | 0.3270 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.100 | 0.3090 | 0.2450 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_gptq_w4g128_L24-35` | 0.200 | 0.3090 | 0.1800 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.000 | 0.3090 | 0.4550 | 427 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.050 | 0.3090 | 0.3850 | 1514 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.100 | 0.3090 | 0.3280 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L0-11` | 0.200 | 0.3090 | 0.2410 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.000 | 0.3090 | 0.4170 | 764 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.050 | 0.3090 | 0.3530 | 4385 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.100 | 0.3090 | 0.2960 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L12-23` | 0.200 | 0.3090 | 0.2310 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.000 | 0.3090 | 0.3660 | 2647 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.050 | 0.3090 | 0.3130 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.100 | 0.3090 | 0.2700 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128_L24-35` | 0.200 | 0.3090 | 0.2020 | ∞ |
