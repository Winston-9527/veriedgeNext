# E0 自动报告（ref = `torch_fp32`）

- contexts：33280（520 个 prompt）；α=0.001，β=0.001
- 诚实栈：torch_fp32_eager, torch_bf16, torch_fp16, mlx_bf16, apple_mps_fp32, apple_mps_bf16, apple_mps_fp16, apple_mlx_bf16；作弊栈：torch_rtn_w8g128, torch_bnb_int8, mlx_8bit, apple_mlx_8bit, torch_rtn_w4g128, torch_gptq_w4g128, torch_bnb_nf4, mlx_q4, apple_mps_rtn_w4g128, apple_mlx_q4；升级目标：`torch_bf16`

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
| `torch_rtn_w8g128` | cheat | 0.0246 | [0.0230, 0.0264] | 0.000 | 1.375 |
| `torch_bnb_int8` | cheat | 0.0387 | [0.0364, 0.0410] | 0.094 | 1.359 |
| `mlx_8bit` | cheat | 0.0249 | [0.0232, 0.0267] | 0.000 | 1.375 |
| `apple_mlx_8bit` | cheat | 0.0276 | [0.0257, 0.0295] | 0.000 | 1.375 |
| `torch_rtn_w4g128` | cheat | 0.2174 | [0.2102, 0.2248] | 0.375 | 1.250 |
| `torch_gptq_w4g128` | cheat | 0.1076 | [0.1030, 0.1125] | 0.250 | 1.250 |
| `torch_bnb_nf4` | cheat | 0.1687 | [0.1629, 0.1743] | 0.250 | 1.250 |
| `mlx_q4` | cheat | 0.1975 | [0.1909, 0.2042] | 0.375 | 1.250 |
| `apple_mps_rtn_w4g128` | cheat | 0.2170 | [0.2094, 0.2238] | 0.375 | 1.250 |
| `apple_mlx_q4` | cheat | 0.1969 | [0.1900, 0.2035] | 0.375 | 1.250 |

诚实栈最大失配率（全局）：0.0192

## C. 升级攻击（区间在偶数 prompt 上选、奇数 prompt 上报告；p_h 用 Wilson 95% 上界）

| 作弊栈 | 升级成本 | 残余失配(全体) | 区间 p_h(上界) | 区间 p_q | N*(Chernoff) | N(exact) |
|---|---|---|---|---|---|---|
| `torch_rtn_w8g128` | 0.000 | 0.0246 | 0.0046 | 0.0105 | 2502.66 | 8104 |
| `torch_rtn_w8g128` | 0.010 | 0.0226 | 0.0046 | 0.0087 | 4931.17 | 15386 |
| `torch_rtn_w8g128` | 0.020 | 0.0194 | 0.0015 | 0.0024 | 29920.6 | — |
| `torch_rtn_w8g128` | 0.050 | 0.0163 | 0.1976 | 0.1529 | ∞ | — |
| `torch_rtn_w8g128` | 0.100 | 0.0173 | 0.1976 | 0.1626 | ∞ | — |
| `torch_rtn_w8g128` | 0.200 | 0.0179 | 0.1976 | 0.1717 | ∞ | — |
| `torch_rtn_w8g128` | 0.300 | 0.0179 | 0.1976 | 0.1711 | ∞ | — |
| `torch_rtn_w8g128` | 0.500 | 0.0179 | 0.1976 | 0.1711 | ∞ | — |
| `torch_bnb_int8` | 0.000 | 0.0387 | 0.0046 | 0.0608 | 67.87 | 291 |
| `torch_bnb_int8` | 0.010 | 0.0359 | 0.0046 | 0.0527 | 85.1 | 366 |
| `torch_bnb_int8` | 0.020 | 0.0330 | 0.0046 | 0.0440 | 114.29 | 474 |
| `torch_bnb_int8` | 0.050 | 0.0271 | 0.0046 | 0.0261 | 291.0 | 1085 |
| `torch_bnb_int8` | 0.100 | 0.0221 | 0.0023 | 0.0101 | 960.29 | 3491 |
| `torch_bnb_int8` | 0.200 | 0.0186 | 0.0008 | 0.0015 | 29539.95 | — |
| `torch_bnb_int8` | 0.300 | 0.0181 | 0.0004 | 0.0003 | ∞ | — |
| `torch_bnb_int8` | 0.500 | 0.0179 | 0.1976 | 0.1699 | ∞ | — |
| `mlx_8bit` | 0.000 | 0.0249 | 0.0046 | 0.0136 | 1203.04 | 4104 |
| `mlx_8bit` | 0.010 | 0.0219 | 0.0046 | 0.0112 | 2099.47 | 6897 |
| `mlx_8bit` | 0.020 | 0.0188 | 0.0046 | 0.0056 | 77777.94 | — |
| `mlx_8bit` | 0.050 | 0.0157 | 0.0023 | 0.0012 | ∞ | — |
| `mlx_8bit` | 0.100 | 0.0171 | 0.1976 | 0.1584 | ∞ | — |
| `mlx_8bit` | 0.200 | 0.0176 | 0.1976 | 0.1681 | ∞ | — |
| `mlx_8bit` | 0.300 | 0.0179 | 0.1976 | 0.1711 | ∞ | — |
| `mlx_8bit` | 0.500 | 0.0179 | 0.1976 | 0.1711 | ∞ | — |
| `apple_mlx_8bit` | 0.000 | 0.0276 | 0.0046 | 0.0186 | 577.83 | 2036 |
| `apple_mlx_8bit` | 0.010 | 0.0236 | 0.0046 | 0.0124 | 1551.21 | 5120 |
| `apple_mlx_8bit` | 0.020 | 0.0208 | 0.0046 | 0.0105 | 2502.66 | 8104 |
| `apple_mlx_8bit` | 0.050 | 0.0160 | 0.1976 | 0.1450 | ∞ | — |
| `apple_mlx_8bit` | 0.100 | 0.0169 | 0.1976 | 0.1553 | ∞ | — |
| `apple_mlx_8bit` | 0.200 | 0.0175 | 0.1976 | 0.1675 | ∞ | — |
| `apple_mlx_8bit` | 0.300 | 0.0178 | 0.1976 | 0.1705 | ∞ | — |
| `apple_mlx_8bit` | 0.500 | 0.0179 | 0.1976 | 0.1711 | ∞ | — |
| `torch_rtn_w4g128` | 0.000 | 0.2174 | 0.0023 | 0.4636 | 3.25 | 16 |
| `torch_rtn_w4g128` | 0.010 | 0.2118 | 0.0023 | 0.4489 | 3.38 | 17 |
| `torch_rtn_w4g128` | 0.020 | 0.2058 | 0.0023 | 0.4354 | 3.52 | 17 |
| `torch_rtn_w4g128` | 0.050 | 0.1884 | 0.0023 | 0.3904 | 4.05 | 20 |
| `torch_rtn_w4g128` | 0.100 | 0.1617 | 0.0023 | 0.3301 | 5.03 | 30 |
| `torch_rtn_w4g128` | 0.200 | 0.1135 | 0.0023 | 0.2171 | 8.66 | 47 |
| `torch_rtn_w4g128` | 0.300 | 0.0769 | 0.0023 | 0.1323 | 16.64 | 94 |
| `torch_rtn_w4g128` | 0.500 | 0.0317 | 0.0015 | 0.0251 | 146.66 | 650 |
| `torch_gptq_w4g128` | 0.000 | 0.1076 | 0.0046 | 0.2885 | 7.26 | 35 |
| `torch_gptq_w4g128` | 0.010 | 0.1025 | 0.0046 | 0.2711 | 7.89 | 37 |
| `torch_gptq_w4g128` | 0.020 | 0.0976 | 0.0046 | 0.2630 | 8.22 | 38 |
| `torch_gptq_w4g128` | 0.050 | 0.0848 | 0.0046 | 0.2159 | 10.77 | 56 |
| `torch_gptq_w4g128` | 0.100 | 0.0660 | 0.0046 | 0.1551 | 17.03 | 80 |
| `torch_gptq_w4g128` | 0.200 | 0.0425 | 0.0023 | 0.0570 | 53.25 | 255 |
| `torch_gptq_w4g128` | 0.300 | 0.0294 | 0.0023 | 0.0257 | 177.16 | 757 |
| `torch_gptq_w4g128` | 0.500 | 0.0198 | 0.0005 | 0.0012 | 23266.51 | — |
| `torch_bnb_nf4` | 0.000 | 0.1687 | 0.0023 | 0.3735 | 4.29 | 26 |
| `torch_bnb_nf4` | 0.010 | 0.1632 | 0.0023 | 0.3576 | 4.54 | 27 |
| `torch_bnb_nf4` | 0.020 | 0.1580 | 0.0023 | 0.3445 | 4.76 | 28 |
| `torch_bnb_nf4` | 0.050 | 0.1424 | 0.0023 | 0.3059 | 5.55 | 32 |
| `torch_bnb_nf4` | 0.100 | 0.1180 | 0.0023 | 0.2431 | 7.47 | 42 |
| `torch_bnb_nf4` | 0.200 | 0.0779 | 0.0023 | 0.1433 | 14.96 | 74 |
| `torch_bnb_nf4` | 0.300 | 0.0512 | 0.0023 | 0.0762 | 35.26 | 167 |
| `torch_bnb_nf4` | 0.500 | 0.0242 | 0.0015 | 0.0140 | 371.03 | 1509 |
| `mlx_q4` | 0.000 | 0.1975 | 0.0023 | 0.4244 | 3.64 | 18 |
| `mlx_q4` | 0.010 | 0.1915 | 0.0023 | 0.4109 | 3.79 | 18 |
| `mlx_q4` | 0.020 | 0.1861 | 0.0023 | 0.3999 | 3.93 | 19 |
| `mlx_q4` | 0.050 | 0.1689 | 0.0023 | 0.3607 | 4.49 | 27 |
| `mlx_q4` | 0.100 | 0.1428 | 0.0023 | 0.2985 | 5.73 | 33 |
| `mlx_q4` | 0.200 | 0.0979 | 0.0023 | 0.1975 | 9.8 | 53 |
| `mlx_q4` | 0.300 | 0.0647 | 0.0046 | 0.1371 | 20.27 | 103 |
| `mlx_q4` | 0.500 | 0.0279 | 0.0023 | 0.0190 | 293.31 | 1187 |
| `apple_mps_rtn_w4g128` | 0.000 | 0.2170 | 0.0023 | 0.4657 | 3.23 | 16 |
| `apple_mps_rtn_w4g128` | 0.010 | 0.2114 | 0.0023 | 0.4516 | 3.36 | 16 |
| `apple_mps_rtn_w4g128` | 0.020 | 0.2060 | 0.0023 | 0.4345 | 3.53 | 17 |
| `apple_mps_rtn_w4g128` | 0.050 | 0.1881 | 0.0023 | 0.3947 | 4.0 | 19 |
| `apple_mps_rtn_w4g128` | 0.100 | 0.1612 | 0.0023 | 0.3255 | 5.12 | 30 |
| `apple_mps_rtn_w4g128` | 0.200 | 0.1135 | 0.0023 | 0.2189 | 8.56 | 47 |
| `apple_mps_rtn_w4g128` | 0.300 | 0.0769 | 0.0023 | 0.1344 | 16.29 | 79 |
| `apple_mps_rtn_w4g128` | 0.500 | 0.0319 | 0.0023 | 0.0300 | 138.72 | 596 |
| `apple_mlx_q4` | 0.000 | 0.1969 | 0.0023 | 0.4222 | 3.66 | 18 |
| `apple_mlx_q4` | 0.010 | 0.1914 | 0.0023 | 0.4097 | 3.81 | 19 |
| `apple_mlx_q4` | 0.020 | 0.1855 | 0.0023 | 0.3983 | 3.95 | 19 |
| `apple_mlx_q4` | 0.050 | 0.1686 | 0.0023 | 0.3582 | 4.53 | 27 |
| `apple_mlx_q4` | 0.100 | 0.1430 | 0.0023 | 0.3022 | 5.64 | 33 |
| `apple_mlx_q4` | 0.200 | 0.0986 | 0.0023 | 0.2009 | 9.58 | 52 |
| `apple_mlx_q4` | 0.300 | 0.0647 | 0.0046 | 0.1352 | 20.67 | 104 |
| `apple_mlx_q4` | 0.500 | 0.0276 | 0.0023 | 0.0202 | 263.67 | 1115 |

**预注册判据**（N 取精确二项设计；升级成本 ≤10% 时 N ≥ max(10·N(无升级), 1000)）：

- `torch_rtn_w8g128`：N(无升级)=8104，N(成本≤10%)=None → motivation_holds = **True**
- `torch_bnb_int8`：N(无升级)=291，N(成本≤10%)=3491 → motivation_holds = **True**
- `mlx_8bit`：N(无升级)=4104，N(成本≤10%)=None → motivation_holds = **True**
- `apple_mlx_8bit`：N(无升级)=2036，N(成本≤10%)=None → motivation_holds = **True**
- `torch_rtn_w4g128`：N(无升级)=16，N(成本≤10%)=30 → motivation_holds = **False**
- `torch_gptq_w4g128`：N(无升级)=35，N(成本≤10%)=80 → motivation_holds = **False**
- `torch_bnb_nf4`：N(无升级)=26，N(成本≤10%)=42 → motivation_holds = **False**
- `mlx_q4`：N(无升级)=18，N(成本≤10%)=33 → motivation_holds = **False**
- `apple_mps_rtn_w4g128`：N(无升级)=16，N(成本≤10%)=30 → motivation_holds = **False**
- `apple_mlx_q4`：N(无升级)=18，N(成本≤10%)=33 → motivation_holds = **False**

## D. 量化器感知的 canary 池（选翻转且 selector 最自信的 K 个 context）

| selector | oracle | K | 作弊栈 | 升级成本 | p_h(上界) | p_q | N(exact) |
|---|---|---|---|---|---|---|---|
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.000 | 0.2392 | 0.2000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.050 | 0.2392 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.100 | 0.2392 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.200 | 0.2392 | 0.1000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_int8` | 0.000 | 0.2392 | 0.3000 | 2047 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_int8` | 0.050 | 0.2392 | 0.2200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_int8` | 0.100 | 0.2392 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_int8` | 0.200 | 0.2392 | 0.1400 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_8bit` | 0.000 | 0.2392 | 0.1000 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_8bit` | 0.050 | 0.2392 | 0.0600 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_8bit` | 0.100 | 0.2392 | 0.0800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `mlx_8bit` | 0.200 | 0.2392 | 0.0800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_8bit` | 0.000 | 0.2392 | 0.2200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_8bit` | 0.050 | 0.2392 | 0.1800 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_8bit` | 0.100 | 0.2392 | 0.1200 | ∞ |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_8bit` | 0.200 | 0.2392 | 0.1000 | ∞ |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.000 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.050 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.100 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | True | 50 | `torch_rtn_w4g128` | 0.200 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.000 | 0.2392 | 0.6400 | 57 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.050 | 0.2392 | 0.6600 | 53 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.100 | 0.2392 | 0.6600 | 53 |
| `torch_rtn_w4g128` | False | 50 | `torch_gptq_w4g128` | 0.200 | 0.2392 | 0.5800 | 78 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.2392 | 0.6200 | 63 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.2392 | 0.6000 | 69 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.2392 | 0.5600 | 88 |
| `torch_rtn_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.2392 | 0.5000 | 128 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.2392 | 0.8800 | 18 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.2392 | 0.8400 | 23 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.2392 | 0.8400 | 23 |
| `torch_rtn_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.2392 | 0.8000 | 26 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.2392 | 1.0000 | 5 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.2392 | 0.8600 | 20 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.2392 | 0.8600 | 20 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.2392 | 0.7800 | 30 |
| `torch_rtn_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.2392 | 0.7400 | 36 |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.000 | 0.1116 | 0.1250 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.050 | 0.1116 | 0.0800 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.100 | 0.1116 | 0.0700 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.200 | 0.1116 | 0.0650 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_int8` | 0.000 | 0.1116 | 0.1900 | 794 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_int8` | 0.050 | 0.1116 | 0.1550 | 2347 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_int8` | 0.100 | 0.1116 | 0.1050 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_int8` | 0.200 | 0.1116 | 0.0750 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_8bit` | 0.000 | 0.1116 | 0.0900 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_8bit` | 0.050 | 0.1116 | 0.0400 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_8bit` | 0.100 | 0.1116 | 0.0500 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `mlx_8bit` | 0.200 | 0.1116 | 0.0600 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_8bit` | 0.000 | 0.1116 | 0.1050 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_8bit` | 0.050 | 0.1116 | 0.0600 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_8bit` | 0.100 | 0.1116 | 0.0550 | ∞ |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_8bit` | 0.200 | 0.1116 | 0.0550 | ∞ |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.000 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.050 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.100 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | True | 200 | `torch_rtn_w4g128` | 0.200 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.000 | 0.1116 | 0.5250 | 43 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.050 | 0.1116 | 0.4900 | 50 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.100 | 0.1116 | 0.4350 | 69 |
| `torch_rtn_w4g128` | False | 200 | `torch_gptq_w4g128` | 0.200 | 0.1116 | 0.3300 | 133 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.1116 | 0.4800 | 54 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.1116 | 0.4200 | 72 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.1116 | 0.3800 | 94 |
| `torch_rtn_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.1116 | 0.2900 | 182 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.1116 | 0.7800 | 18 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.1116 | 0.7350 | 19 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.1116 | 0.7050 | 22 |
| `torch_rtn_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.1116 | 0.6250 | 31 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.1116 | 1.0000 | 4 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.1116 | 0.7950 | 15 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.1116 | 0.7550 | 19 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.1116 | 0.6950 | 23 |
| `torch_rtn_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.1116 | 0.6150 | 31 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.000 | 0.0758 | 0.0980 | 6158 |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.050 | 0.0758 | 0.0620 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.100 | 0.0758 | 0.0570 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.200 | 0.0758 | 0.0560 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_int8` | 0.000 | 0.0758 | 0.1410 | 850 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_int8` | 0.050 | 0.0758 | 0.1070 | 3241 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_int8` | 0.100 | 0.0758 | 0.0830 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_int8` | 0.200 | 0.0758 | 0.0650 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_8bit` | 0.000 | 0.0758 | 0.0850 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_8bit` | 0.050 | 0.0758 | 0.0560 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_8bit` | 0.100 | 0.0758 | 0.0510 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `mlx_8bit` | 0.200 | 0.0758 | 0.0550 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.000 | 0.0758 | 0.0970 | 6715 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.050 | 0.0758 | 0.0540 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.100 | 0.0758 | 0.0520 | ∞ |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.200 | 0.0758 | 0.0530 | ∞ |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.000 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.050 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.100 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | True | 1000 | `torch_rtn_w4g128` | 0.200 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.000 | 0.0758 | 0.4070 | 55 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.050 | 0.0758 | 0.3390 | 84 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.100 | 0.0758 | 0.2800 | 122 |
| `torch_rtn_w4g128` | False | 1000 | `torch_gptq_w4g128` | 0.200 | 0.0758 | 0.1880 | 333 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.0758 | 0.4530 | 46 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.0758 | 0.3950 | 61 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.0758 | 0.3520 | 77 |
| `torch_rtn_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.0758 | 0.2620 | 146 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.0758 | 0.6810 | 20 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.0758 | 0.6240 | 24 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.0758 | 0.5670 | 28 |
| `torch_rtn_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.0758 | 0.4620 | 45 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.0758 | 1.0000 | 3 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.0758 | 0.6810 | 20 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.0758 | 0.6240 | 24 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.0758 | 0.5720 | 27 |
| `torch_rtn_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.0758 | 0.4670 | 44 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.000 | 0.1915 | 0.1000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.050 | 0.1915 | 0.0600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.100 | 0.1915 | 0.0800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w8g128` | 0.200 | 0.1915 | 0.0800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_int8` | 0.000 | 0.1915 | 0.2200 | 7733 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_int8` | 0.050 | 0.1915 | 0.2000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_int8` | 0.100 | 0.1915 | 0.2000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_int8` | 0.200 | 0.1915 | 0.1600 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_8bit` | 0.000 | 0.1915 | 0.0400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_8bit` | 0.050 | 0.1915 | 0.1000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_8bit` | 0.100 | 0.1915 | 0.0800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `mlx_8bit` | 0.200 | 0.1915 | 0.0800 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_8bit` | 0.000 | 0.1915 | 0.1200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_8bit` | 0.050 | 0.1915 | 0.1200 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_8bit` | 0.100 | 0.1915 | 0.1400 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_8bit` | 0.200 | 0.1915 | 0.1000 | ∞ |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.000 | 0.1915 | 0.7400 | 28 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.050 | 0.1915 | 0.7200 | 30 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.100 | 0.1915 | 0.7000 | 33 |
| `torch_gptq_w4g128` | False | 50 | `torch_rtn_w4g128` | 0.200 | 0.1915 | 0.6000 | 51 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.000 | 0.1915 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.050 | 0.1915 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.100 | 0.1915 | 1.0000 | 5 |
| `torch_gptq_w4g128` | True | 50 | `torch_gptq_w4g128` | 0.200 | 0.1915 | 1.0000 | 5 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.000 | 0.1915 | 0.5000 | 88 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.050 | 0.1915 | 0.4600 | 115 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.100 | 0.1915 | 0.4400 | 132 |
| `torch_gptq_w4g128` | False | 50 | `torch_bnb_nf4` | 0.200 | 0.1915 | 0.3800 | 220 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.000 | 0.1915 | 0.5400 | 70 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.050 | 0.1915 | 0.5400 | 70 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.100 | 0.1915 | 0.5400 | 70 |
| `torch_gptq_w4g128` | False | 50 | `mlx_q4` | 0.200 | 0.1915 | 0.5400 | 70 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.000 | 0.1915 | 0.7200 | 30 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.050 | 0.1915 | 0.7000 | 33 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.100 | 0.1915 | 0.6800 | 37 |
| `torch_gptq_w4g128` | False | 50 | `apple_mps_rtn_w4g128` | 0.200 | 0.1915 | 0.6200 | 45 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.000 | 0.1915 | 0.5600 | 62 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.050 | 0.1915 | 0.5600 | 62 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.100 | 0.1915 | 0.5600 | 62 |
| `torch_gptq_w4g128` | False | 50 | `apple_mlx_q4` | 0.200 | 0.1915 | 0.5000 | 88 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.000 | 0.1116 | 0.1100 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.050 | 0.1116 | 0.0650 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.100 | 0.1116 | 0.0600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w8g128` | 0.200 | 0.1116 | 0.0600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_int8` | 0.000 | 0.1116 | 0.2400 | 328 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_int8` | 0.050 | 0.1116 | 0.1750 | 1170 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_int8` | 0.100 | 0.1116 | 0.1300 | 12051 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_int8` | 0.200 | 0.1116 | 0.0950 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_8bit` | 0.000 | 0.1116 | 0.0750 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_8bit` | 0.050 | 0.1116 | 0.0400 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_8bit` | 0.100 | 0.1116 | 0.0550 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `mlx_8bit` | 0.200 | 0.1116 | 0.0650 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_8bit` | 0.000 | 0.1116 | 0.1000 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_8bit` | 0.050 | 0.1116 | 0.0600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_8bit` | 0.100 | 0.1116 | 0.0650 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_8bit` | 0.200 | 0.1116 | 0.0600 | ∞ |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.000 | 0.1116 | 0.6550 | 27 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.050 | 0.1116 | 0.5950 | 33 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.100 | 0.1116 | 0.5450 | 41 |
| `torch_gptq_w4g128` | False | 200 | `torch_rtn_w4g128` | 0.200 | 0.1116 | 0.4600 | 59 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.000 | 0.1116 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.050 | 0.1116 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.100 | 0.1116 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 200 | `torch_gptq_w4g128` | 0.200 | 0.1116 | 1.0000 | 4 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.000 | 0.1116 | 0.5300 | 43 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.050 | 0.1116 | 0.4750 | 54 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.100 | 0.1116 | 0.4050 | 78 |
| `torch_gptq_w4g128` | False | 200 | `torch_bnb_nf4` | 0.200 | 0.1116 | 0.3200 | 145 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.000 | 0.1116 | 0.5650 | 37 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.050 | 0.1116 | 0.5200 | 44 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.100 | 0.1116 | 0.4650 | 59 |
| `torch_gptq_w4g128` | False | 200 | `mlx_q4` | 0.200 | 0.1116 | 0.3900 | 88 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.000 | 0.1116 | 0.6250 | 31 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.050 | 0.1116 | 0.5950 | 33 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.100 | 0.1116 | 0.5550 | 38 |
| `torch_gptq_w4g128` | False | 200 | `apple_mps_rtn_w4g128` | 0.200 | 0.1116 | 0.4950 | 49 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.000 | 0.1116 | 0.5600 | 38 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.050 | 0.1116 | 0.5150 | 44 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.100 | 0.1116 | 0.4750 | 54 |
| `torch_gptq_w4g128` | False | 200 | `apple_mlx_q4` | 0.200 | 0.1116 | 0.3900 | 88 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.000 | 0.1199 | 0.1230 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.050 | 0.1199 | 0.0880 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.100 | 0.1199 | 0.0850 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w8g128` | 0.200 | 0.1199 | 0.0850 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_int8` | 0.000 | 0.1199 | 0.2260 | 478 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_int8` | 0.050 | 0.1199 | 0.1650 | 2307 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_int8` | 0.100 | 0.1199 | 0.1420 | 8948 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_int8` | 0.200 | 0.1199 | 0.0980 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_8bit` | 0.000 | 0.1199 | 0.1190 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_8bit` | 0.050 | 0.1199 | 0.0720 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_8bit` | 0.100 | 0.1199 | 0.0820 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `mlx_8bit` | 0.200 | 0.1199 | 0.0840 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.000 | 0.1199 | 0.1390 | 11826 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.050 | 0.1199 | 0.0880 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.100 | 0.1199 | 0.0830 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_8bit` | 0.200 | 0.1199 | 0.0840 | ∞ |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.000 | 0.1199 | 0.6480 | 29 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.050 | 0.1199 | 0.5970 | 35 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.100 | 0.1199 | 0.5510 | 41 |
| `torch_gptq_w4g128` | False | 1000 | `torch_rtn_w4g128` | 0.200 | 0.1199 | 0.4280 | 76 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.000 | 0.1199 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.050 | 0.1199 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.100 | 0.1199 | 1.0000 | 4 |
| `torch_gptq_w4g128` | True | 1000 | `torch_gptq_w4g128` | 0.200 | 0.1199 | 0.9180 | 10 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.000 | 0.1199 | 0.5430 | 44 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.050 | 0.1199 | 0.4830 | 59 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.100 | 0.1199 | 0.4120 | 83 |
| `torch_gptq_w4g128` | False | 1000 | `torch_bnb_nf4` | 0.200 | 0.1199 | 0.3200 | 156 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.000 | 0.1199 | 0.6130 | 34 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.050 | 0.1199 | 0.5450 | 44 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.100 | 0.1199 | 0.4940 | 55 |
| `torch_gptq_w4g128` | False | 1000 | `mlx_q4` | 0.200 | 0.1199 | 0.3600 | 114 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.000 | 0.1199 | 0.6430 | 30 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.050 | 0.1199 | 0.6000 | 35 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.100 | 0.1199 | 0.5460 | 44 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mps_rtn_w4g128` | 0.200 | 0.1199 | 0.4290 | 76 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.000 | 0.1199 | 0.6140 | 34 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.050 | 0.1199 | 0.5570 | 40 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.100 | 0.1199 | 0.4940 | 55 |
| `torch_gptq_w4g128` | False | 1000 | `apple_mlx_q4` | 0.200 | 0.1199 | 0.3760 | 105 |
