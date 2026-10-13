# E0 自动报告（ref = `torch_fp32`）

- contexts：33280（520 个 prompt）；α=0.001，β=0.001
- 诚实栈：torch_fp32_eager, torch_bf16, torch_fp16, mlx_bf16, apple_mps_fp32, apple_mps_bf16, apple_mps_fp16, apple_mlx_bf16, torch_rtn_w8g128, torch_bnb_int8, mlx_8bit, apple_mlx_8bit；作弊栈：torch_rtn_w4g128, torch_gptq_w4g128, torch_bnb_nf4, mlx_q4, apple_mps_rtn_w4g128, apple_mlx_q4；升级目标：`mlx_8bit`

## A. 总体 top-1 失配率

| 栈 | 角色 | 失配率 | 95% CI | 翻转处自身 margin 中位数 | 全体自身 margin 中位数 |
|---|---|---|---|---|---|
| `torch_fp32_eager` | honest | 0.0000 | [0.0000, 0.0000] | — | 1.363 |
| `torch_bf16` | honest | 0.0179 | [0.0164, 0.0194] | 0.000 | 1.375 |
| `torch_fp16` | honest | 0.0019 | [0.0014, 0.0024] | 0.000 | 1.359 |
| `mlx_bf16` | honest | 0.0185 | [0.0170, 0.0201] | 0.000 | 1.375 |
| `apple_mps_fp32` | honest | 0.0000 | [0.0000, 0.0000] | — | 1.363 |
| `apple_mps_bf16` | honest | 0.0192 | [0.0176, 0.0207] | 0.000 | 1.375 |
| `apple_mps_fp16` | honest | 0.0022 | [0.0017, 0.0028] | 0.000 | 1.359 |
| `apple_mlx_bf16` | honest | 0.0169 | [0.0155, 0.0184] | 0.000 | 1.375 |
| `torch_rtn_w8g128` | honest | 0.0246 | [0.0230, 0.0264] | 0.000 | 1.375 |
| `torch_bnb_int8` | honest | 0.0387 | [0.0364, 0.0410] | 0.094 | 1.359 |
| `mlx_8bit` | honest | 0.0249 | [0.0232, 0.0267] | 0.000 | 1.375 |
| `apple_mlx_8bit` | honest | 0.0276 | [0.0257, 0.0295] | 0.000 | 1.375 |
| `torch_rtn_w4g128` | cheat | 0.2174 | [0.2102, 0.2248] | 0.375 | 1.250 |
| `torch_gptq_w4g128` | cheat | 0.1076 | [0.1030, 0.1125] | 0.250 | 1.250 |
| `torch_bnb_nf4` | cheat | 0.1687 | [0.1629, 0.1743] | 0.250 | 1.250 |
| `mlx_q4` | cheat | 0.1975 | [0.1909, 0.2042] | 0.375 | 1.250 |
| `apple_mps_rtn_w4g128` | cheat | 0.2170 | [0.2094, 0.2238] | 0.375 | 1.250 |
| `apple_mlx_q4` | cheat | 0.1969 | [0.1900, 0.2035] | 0.375 | 1.250 |

诚实栈最大失配率（全局）：0.0387

## C. 升级攻击（区间在偶数 prompt 上选、奇数 prompt 上报告；p_h 用 Wilson 95% 上界）

| 作弊栈 | 升级成本 | 残余失配(全体) | 区间 p_h(上界) | 区间 p_q | N*(Chernoff) | N(exact) |
|---|---|---|---|---|---|---|
| `torch_rtn_w4g128` | 0.000 | 0.2174 | 0.0108 | 0.3677 | 6.8 | 31 |
| `torch_rtn_w4g128` | 0.010 | 0.2110 | 0.0202 | 0.4075 | 7.46 | 31 |
| `torch_rtn_w4g128` | 0.020 | 0.2058 | 0.0202 | 0.3990 | 7.7 | 32 |
| `torch_rtn_w4g128` | 0.050 | 0.1890 | 0.0202 | 0.3652 | 8.84 | 35 |
| `torch_rtn_w4g128` | 0.100 | 0.1629 | 0.0108 | 0.2598 | 11.27 | 52 |
| `torch_rtn_w4g128` | 0.200 | 0.1163 | 0.0036 | 0.1439 | 17.24 | 86 |
| `torch_rtn_w4g128` | 0.300 | 0.0808 | 0.0036 | 0.0872 | 34.93 | 165 |
| `torch_rtn_w4g128` | 0.500 | 0.0377 | 0.0023 | 0.0141 | 489.65 | 1908 |
| `torch_gptq_w4g128` | 0.000 | 0.1076 | 0.0202 | 0.1620 | 33.48 | 133 |
| `torch_gptq_w4g128` | 0.010 | 0.1030 | 0.0202 | 0.1518 | 37.6 | 143 |
| `torch_gptq_w4g128` | 0.020 | 0.0982 | 0.0202 | 0.1427 | 42.01 | 162 |
| `torch_gptq_w4g128` | 0.050 | 0.0864 | 0.0202 | 0.1179 | 59.9 | 222 |
| `torch_gptq_w4g128` | 0.100 | 0.0687 | 0.0202 | 0.0816 | 126.71 | 457 |
| `torch_gptq_w4g128` | 0.200 | 0.0473 | 0.0202 | 0.0435 | 666.09 | 2117 |
| `torch_gptq_w4g128` | 0.300 | 0.0360 | 0.0108 | 0.0147 | 10401.74 | — |
| `torch_gptq_w4g128` | 0.500 | 0.0270 | 0.0008 | 0.0000 | ∞ | — |
| `torch_bnb_nf4` | 0.000 | 0.1687 | 0.0202 | 0.3156 | 11.11 | 47 |
| `torch_bnb_nf4` | 0.010 | 0.1633 | 0.0202 | 0.3041 | 11.78 | 48 |
| `torch_bnb_nf4` | 0.020 | 0.1582 | 0.0202 | 0.2914 | 12.6 | 51 |
| `torch_bnb_nf4` | 0.050 | 0.1432 | 0.0202 | 0.2576 | 15.36 | 64 |
| `torch_bnb_nf4` | 0.100 | 0.1200 | 0.0202 | 0.2062 | 22.15 | 89 |
| `torch_bnb_nf4` | 0.200 | 0.0819 | 0.0202 | 0.1197 | 58.18 | 219 |
| `torch_bnb_nf4` | 0.300 | 0.0563 | 0.0036 | 0.0513 | 76.89 | 346 |
| `torch_bnb_nf4` | 0.500 | 0.0311 | 0.0023 | 0.0066 | 2499.18 | 8492 |
| `mlx_q4` | 0.000 | 0.1975 | 0.0202 | 0.3676 | 8.75 | 35 |
| `mlx_q4` | 0.010 | 0.1920 | 0.0202 | 0.3585 | 9.1 | 36 |
| `mlx_q4` | 0.020 | 0.1860 | 0.0202 | 0.3446 | 9.67 | 42 |
| `mlx_q4` | 0.050 | 0.1697 | 0.0202 | 0.3077 | 11.56 | 48 |
| `mlx_q4` | 0.100 | 0.1441 | 0.0202 | 0.2527 | 15.84 | 66 |
| `mlx_q4` | 0.200 | 0.1012 | 0.0202 | 0.1620 | 33.48 | 133 |
| `mlx_q4` | 0.300 | 0.0691 | 0.0108 | 0.0712 | 90.86 | 353 |
| `mlx_q4` | 0.500 | 0.0345 | 0.0011 | 0.0073 | 914.37 | 3490 |
| `apple_mps_rtn_w4g128` | 0.000 | 0.2170 | 0.0202 | 0.4256 | 6.97 | 29 |
| `apple_mps_rtn_w4g128` | 0.010 | 0.2112 | 0.0202 | 0.4117 | 7.34 | 31 |
| `apple_mps_rtn_w4g128` | 0.020 | 0.2056 | 0.0202 | 0.4057 | 7.51 | 31 |
| `apple_mps_rtn_w4g128` | 0.050 | 0.1884 | 0.0202 | 0.3682 | 8.73 | 35 |
| `apple_mps_rtn_w4g128` | 0.100 | 0.1627 | 0.0108 | 0.2631 | 11.06 | 51 |
| `apple_mps_rtn_w4g128` | 0.200 | 0.1172 | 0.0108 | 0.1778 | 19.91 | 87 |
| `apple_mps_rtn_w4g128` | 0.300 | 0.0806 | 0.0036 | 0.0901 | 33.27 | 159 |
| `apple_mps_rtn_w4g128` | 0.500 | 0.0375 | 0.0023 | 0.0159 | 393.67 | 1601 |
| `apple_mlx_q4` | 0.000 | 0.1969 | 0.0202 | 0.3646 | 8.86 | 35 |
| `apple_mlx_q4` | 0.010 | 0.1915 | 0.0202 | 0.3573 | 9.14 | 36 |
| `apple_mlx_q4` | 0.020 | 0.1859 | 0.0202 | 0.3434 | 9.73 | 42 |
| `apple_mlx_q4` | 0.050 | 0.1690 | 0.0202 | 0.3065 | 11.63 | 48 |
| `apple_mlx_q4` | 0.100 | 0.1447 | 0.0202 | 0.2588 | 15.25 | 64 |
| `apple_mlx_q4` | 0.200 | 0.1018 | 0.0202 | 0.1657 | 32.2 | 130 |
| `apple_mlx_q4` | 0.300 | 0.0691 | 0.0108 | 0.0736 | 85.53 | 341 |
| `apple_mlx_q4` | 0.500 | 0.0342 | 0.0011 | 0.0079 | 793.69 | 3226 |

**预注册判据**（N 取精确二项设计；升级成本 ≤10% 时 N ≥ max(10·N(无升级), 1000)）：

- `torch_rtn_w4g128`：N(无升级)=31，N(成本≤10%)=52 → motivation_holds = **False**
- `torch_gptq_w4g128`：N(无升级)=133，N(成本≤10%)=457 → motivation_holds = **False**
- `torch_bnb_nf4`：N(无升级)=47，N(成本≤10%)=89 → motivation_holds = **False**
- `mlx_q4`：N(无升级)=35，N(成本≤10%)=66 → motivation_holds = **False**
- `apple_mps_rtn_w4g128`：N(无升级)=29，N(成本≤10%)=51 → motivation_holds = **False**
- `apple_mlx_q4`：N(无升级)=35，N(成本≤10%)=64 → motivation_holds = **False**

## D. 量化器感知的 canary 池（选翻转且 selector 最自信的 K 个 context）

| selector | oracle | K | 作弊栈 | 升级成本 | p_h(上界) | p_q | N(exact) |
|---|---|---|---|---|---|---|---|
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.000 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.050 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.100 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.200 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.000 | 0.4146 | 0.6400 | 188 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.050 | 0.4146 | 0.6400 | 188 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.100 | 0.4146 | 0.6000 | 277 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.200 | 0.4146 | 0.5400 | 609 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.4146 | 0.6200 | 229 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.4146 | 0.5800 | 355 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.4146 | 0.5600 | 453 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.4146 | 0.5200 | 860 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.4146 | 0.8800 | 36 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.4146 | 0.8600 | 40 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.4146 | 0.8400 | 46 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.4146 | 0.7800 | 65 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.4146 | 1.0000 | 8 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.4146 | 0.8600 | 40 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.4146 | 0.8600 | 40 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.4146 | 0.8000 | 59 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.4146 | 0.7600 | 73 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.000 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.050 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.100 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.200 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.000 | 0.2397 | 0.5250 | 110 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.050 | 0.2397 | 0.4800 | 154 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.100 | 0.2397 | 0.4250 | 248 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.200 | 0.2397 | 0.3450 | 714 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.2397 | 0.4800 | 154 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.2397 | 0.4250 | 248 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.2397 | 0.3850 | 387 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.2397 | 0.3150 | 1349 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.2397 | 0.7800 | 30 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.2397 | 0.7550 | 33 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.2397 | 0.7050 | 40 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.2397 | 0.6250 | 60 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.2397 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.2397 | 0.7950 | 28 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.2397 | 0.7500 | 33 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.2397 | 0.6950 | 44 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.2397 | 0.6050 | 67 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.000 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.050 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.100 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.200 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.000 | 0.1601 | 0.4070 | 123 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.050 | 0.1601 | 0.3440 | 211 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.100 | 0.1601 | 0.2860 | 422 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.200 | 0.1601 | 0.2080 | 2507 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.1601 | 0.4530 | 91 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.1601 | 0.4050 | 127 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.1601 | 0.3610 | 177 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.1601 | 0.2770 | 473 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.1601 | 0.6810 | 31 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.1601 | 0.6260 | 39 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.1601 | 0.5670 | 51 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.1601 | 0.4760 | 81 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.1601 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.1601 | 0.9990 | 6 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.1601 | 0.6810 | 31 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.1601 | 0.6210 | 39 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.1601 | 0.5760 | 47 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.1601 | 0.4820 | 77 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.000 | 0.3293 | 0.7400 | 53 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.050 | 0.3293 | 0.7000 | 65 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.100 | 0.3293 | 0.6800 | 76 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.200 | 0.3293 | 0.6200 | 109 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.000 | 0.3293 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.050 | 0.3293 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.100 | 0.3293 | 1.0000 | 7 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.200 | 0.3293 | 1.0000 | 7 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.3293 | 0.5000 | 316 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.3293 | 0.4600 | 538 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.3293 | 0.4400 | 749 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.3293 | 0.3600 | 9204 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.3293 | 0.5400 | 209 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.3293 | 0.5400 | 209 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.3293 | 0.5200 | 259 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.3293 | 0.4800 | 406 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.3293 | 0.7200 | 60 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.3293 | 0.7000 | 65 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.3293 | 0.6800 | 76 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.3293 | 0.6200 | 109 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.3293 | 0.5600 | 175 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.3293 | 0.5600 | 175 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.3293 | 0.5200 | 259 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.3293 | 0.4400 | 749 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.000 | 0.2929 | 0.6550 | 71 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.050 | 0.2929 | 0.6050 | 95 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.100 | 0.2929 | 0.5550 | 134 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.200 | 0.2929 | 0.4750 | 272 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.000 | 0.2929 | 1.0000 | 6 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.050 | 0.2929 | 1.0000 | 6 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.100 | 0.2929 | 1.0000 | 6 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.200 | 0.2929 | 1.0000 | 6 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.2929 | 0.5300 | 165 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.2929 | 0.4850 | 245 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.2929 | 0.4150 | 586 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.2929 | 0.3600 | 1879 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.2929 | 0.5650 | 126 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.2929 | 0.5100 | 197 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.2929 | 0.4550 | 338 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.2929 | 0.3700 | 1432 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.2929 | 0.6250 | 84 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.2929 | 0.5950 | 99 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.2929 | 0.5550 | 134 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.2929 | 0.4900 | 233 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.2929 | 0.5600 | 131 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.2929 | 0.4950 | 219 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.2929 | 0.4550 | 338 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.2929 | 0.3600 | 1879 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.000 | 0.2485 | 0.6480 | 56 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.050 | 0.2485 | 0.5950 | 76 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.100 | 0.2485 | 0.5490 | 98 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.200 | 0.2485 | 0.4460 | 220 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.000 | 0.2485 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.050 | 0.2485 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.100 | 0.2485 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.200 | 0.2485 | 0.9140 | 17 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.2485 | 0.5430 | 102 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.2485 | 0.4950 | 146 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.2485 | 0.4260 | 271 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.2485 | 0.3400 | 948 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.2485 | 0.6130 | 65 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.2485 | 0.5550 | 97 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.2485 | 0.5030 | 139 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.2485 | 0.3890 | 425 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.2485 | 0.6430 | 58 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.2485 | 0.5960 | 76 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.2485 | 0.5540 | 97 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.2485 | 0.4460 | 220 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.2485 | 0.6140 | 65 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.2485 | 0.5600 | 92 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.2485 | 0.4990 | 142 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.2485 | 0.3850 | 444 |
