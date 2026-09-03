# VeriEdge Revision Experiment B: Selective Delivery Group-Size Sweep

## Summary
- Experiment: Selective delivery under placement width.
- Payload size: 100MB encrypted payload.
- Group sizes: 1, 2, 4, 8.
- Networks: LAN and WAN/emulated-WAN model.
- Modes: RPD and PPD.
- Runs per cell: 30.
- Audit status: PASS.

## Main Results
- LAN k=8: PPD requester egress reduction vs RPD = 87.5%; median latency reduction = 74.8%.
- WAN k=8: PPD requester egress reduction vs RPD = 87.5%; median latency reduction = 81.1%.
- RPD requester egress grows from 100.0MB at k=1 to 800.0MB at k=8.
- PPD requester egress grows from 100.0MB at k=1 to 100.0MB at k=8.

## Scope
- This is a calibrated delivery-path replay/microbenchmark, not a live multi-provider deployment.
- AES-GCM encryption throughput and RSA access-package sizes are measured locally.
- LAN/WAN transfer times are computed from the recorded bandwidth/RTT model in `metadata/network_config.md`.
- RPD uses concurrent sends with a shared requester-uplink bottleneck.
- PPD publishes one ciphertext, sends per-provider access packages, then models parallel provider fetches from the store.
