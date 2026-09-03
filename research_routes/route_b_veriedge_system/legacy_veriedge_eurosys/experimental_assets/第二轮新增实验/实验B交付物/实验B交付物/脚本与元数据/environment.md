# Environment

```json
{
  "date": "2026-05-13",
  "git_commit": "d21ba80ceb6ccf74a11a19beec8c493daf7f00af",
  "experiment": "Experiment B selective delivery group-size sweep",
  "payload_mb": 100,
  "group_sizes": [
    1,
    2,
    4,
    8
  ],
  "networks": [
    "LAN",
    "WAN"
  ],
  "modes": [
    "RPD",
    "PPD"
  ],
  "runs_per_cell": 30,
  "seed": 20260513,
  "crypto_calibration": {
    "calibration_bytes": 16777216,
    "calibration_repeats": 5,
    "median_encrypt_ms": 1.7575,
    "mean_encrypt_ms": 1.997,
    "throughput_mib_s": 9103.840683,
    "ciphertext_overhead_bytes": 16
  },
  "scope": "calibrated delivery-path replay/microbenchmark, not live deployment"
}
```
