# PACT offline P0 experiment

This directory tests the central geometric claim in the PACT redesign using
the repository's real heterogeneous checkpoint captures. It compares fixed
1-, 16-, and 256-coordinate perturbations with equal full-vector L2 strength
under exact dense Rademacher projections.

The adversary knows the check policy and threshold distribution. It selects a
candidate using a dedicated seed domain, commits that candidate, and is then
evaluated using an independent final-test seed domain. For support at least 16,
the perturbation is orthogonal to the measured honest residual; the attack
therefore cannot improve its apparent result by cancelling heterogeneous drift.

Run the validation-sized version:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_projection.py --smoke `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/smoke
```

Run the default P0 matrix:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_projection.py
```

Run the support-invariant Gaussian variant with high Monte Carlo precision:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_projection.py --family gaussian `
  --calibration-draws 512 --selection-draws 256 --test-draws 4096 `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/gaussian_p0
```

Validate its exact Gram-matrix sampler and benchmark materialized projections:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/validate_gaussian_sampler.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/benchmark_projection_cost.py
```

Simulate the chi-square-calibrated adaptive evidence policy:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/adaptive_gaussian_policy.py
```

Run the known-seed nullspace negative control:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/known_seed_nullspace.py
```

Compute exact conditional power and boundary-aware K requirements:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/conditional_power.py
```

Evaluate deterministic quantized/LUT Gaussian coefficients:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/quantized_gaussian.py
python research_routes/route_b_veriedge_system/experiments/pact_offline/quantized_gaussian.py `
  --families lut16,gaussian --calibration-draws 100000 --test-draws 100000 `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/lut16_high_precision
```

Run the executable commit-before-seed G16 transcript prototype:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_protocol.py
```

Run the commit-reveal beacon and transactional replay/state tests:

```powershell
python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_state_machine.py
```

This is not a paper-level 1% false-positive result. The local subset has only
six calibration prompts; repeated projection seeds improve Monte Carlo
precision but do not create new independent prompts.
