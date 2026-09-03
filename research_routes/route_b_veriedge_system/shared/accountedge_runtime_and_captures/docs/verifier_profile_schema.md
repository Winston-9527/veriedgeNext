# Verifier Profile Schema

`data/verifier_profiles.csv` contains measured operating points used by the
placement replay and uncertainty scripts.

| Column | Meaning |
|---|---|
| `profile_id` | Anonymous profile identifier |
| `pair` | Anonymous stack-pair identifier |
| `sketch` | Verifier sketch variant |
| `alpha`, `beta` | Target FPR and TPR thresholds |
| `fpr`, `tpr` | Held-out point estimates |
| `sketch_bytes` | Signature payload size |
| `verify_ms` | Verification latency estimate |
| `n_eval`, `n_calib` | Evaluation and calibration prompt counts |
| `fpr_false_positives`, `fpr_trials` | Raw counts for FPR Wilson CI |
| `tpr_true_positives`, `tpr_trials` | Raw counts for TPR Wilson CI |
| `risk_class` | Profile risk category used by placement |
| `feasible` | Whether the profile satisfies default alpha/beta constraints |

The paper reports point estimates for space. This artifact includes Wilson 95%
confidence intervals computed from the held-out evaluation counts.
