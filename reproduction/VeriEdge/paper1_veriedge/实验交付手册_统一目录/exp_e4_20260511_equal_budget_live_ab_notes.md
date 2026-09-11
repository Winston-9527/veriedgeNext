# exp_e4_20260511_equal_budget_live_ab

- Selected configs source: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E2/tables/exp_e2_20260511_equal_budget_live_ab_selected_summary.csv
- Context: same live A/B 40-calibration / 200-evaluation captures used by equal-budget E2.
- Commitment bytes count only digest-chain storage; reveal payload bytes count sketch disclosure on challenge path.
- `challenge_latency_ms` includes capture load + commitment generation + replay + compare.
- `challenge_latency_no_commit_ms` excludes commitment generation for compatibility with earlier drafts.
- `reference_storage_head_bytes` is validator-retained reference storage; `candidate_working_set_*` and `challenge_working_set_*` are challenge-path working-set sizes.
- Detail CSV: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/tables/exp_e4_20260511_equal_budget_live_ab_detail.csv
- Summary CSV: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/tables/exp_e4_20260511_equal_budget_live_ab_summary.csv
- Main table CSV: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/tables/exp_e4_20260511_equal_budget_live_ab_main_table.csv
- Figure: /Users/siyuan/Developer/Veriedge/VeriEdge/paper1_veriedge/E4/figures/exp_e4_20260511_equal_budget_live_ab_payload_latency.png

## Main comparison

- projcos16: reveal=3072 B/trace, hetero latency=4.121868 ms (no-commit 3.784912 ms), tamper latency=4.062752 ms (no-commit 3.736074 ms), hetero detect rate=0.12, tamper detect rate=1.0.
- projcos4: reveal=768 B/trace, hetero latency=3.771044 ms (no-commit 3.572865 ms), tamper latency=3.810353 ms (no-commit 3.61431 ms), hetero detect rate=0.02, tamper detect rate=1.0.
- scalar16: reveal=192 B/trace, hetero latency=4.161692 ms (no-commit 4.055206 ms), tamper latency=3.532271 ms (no-commit 3.444044 ms), hetero detect rate=0.15, tamper detect rate=1.0.
- scalar64: reveal=768 B/trace, hetero latency=3.580513 ms (no-commit 3.479813 ms), tamper latency=3.541837 ms (no-commit 3.448797 ms), hetero detect rate=0.415, tamper detect rate=1.0.
