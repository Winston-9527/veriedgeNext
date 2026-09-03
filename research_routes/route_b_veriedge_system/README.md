# Route B: VeriEdge Risk-Adaptive Verification System

Route B studies **VeriEdge**, a risk-adaptive verification system for
cross-provider LLM inference at the edge. Its active technical core is **PACT**
(Post-commit Activation Consistency Test): the prover commits to execution
evidence before an unpredictable challenge seed is revealed, and the verifier
uses randomized projections to distinguish acceptable heterogeneous drift from
output-affecting deviations.

> Research status (2026-09-03): active prototype and experiment snapshot. This
> repository is not a production security system, and the included six-prompt
> subset is not sufficient for a paper-level 1% false-positive-rate claim.

## Multi-Route Repository Hierarchy

Route B remains one sibling in the long-term repository layout. The current
private upload includes only the overview and Route B; Route A and Route C will
be added later at the same level.

```text
research_routes/
├── README.md
├── route_a_detection_ceiling/    # future upload
├── route_b_veriedge_system/      # current upload
└── route_c_minimax_theory/       # future upload
```

## Start Here

- New student: read [`docs/ROUTE_B_STUDENT_RESEARCH_HANDBOOK_2026-09-03.md`](docs/ROUTE_B_STUDENT_RESEARCH_HANDBOOK_2026-09-03.md).
- Project history and claim ledger: read [`docs/VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md`](docs/VERIEDGE_ROUTE_B_RESEARCH_HANDBOOK_2026-08-24.md).
- PACT protocol design: read [`docs/ROUTE_B_REDESIGN_PACT_2026-08-24.md`](docs/ROUTE_B_REDESIGN_PACT_2026-08-24.md).
- Runnable experiments: enter [`experiments/pact_offline/`](experiments/pact_offline/).
- Before the first push: complete [`GITHUB_UPLOAD_CHECKLIST.md`](GITHUB_UPLOAD_CHECKLIST.md).

## Repository Map

| Path | Role | Status |
| --- | --- | --- |
| [`docs/`](docs/) | Research handbooks, design notes, review analysis, hardware notes | Mixed: active and historical |
| [`experiments/pact_offline/`](experiments/pact_offline/) | PACT-G/G16 simulations, protocol transcript, state machine, calibration audit | Active |
| [`experiments/pcra_offline_retired/`](experiments/pcra_offline_retired/) | Coordinate-opening design and negative results | Retired |
| [`shared/accountedge_runtime_and_captures/`](shared/accountedge_runtime_and_captures/) | Runtime prototype, three-node harness, derived data, raw heterogeneous captures | Shared baseline asset |
| [`shared/literature/`](shared/literature/) | Local copies of related work | Private reference material |
| [`legacy_veriedge_eurosys/`](legacy_veriedge_eurosys/) | Earlier EuroSys manuscript, figures, scripts, and experiments | Archival; not the new paper claim set |
| [`scripts/`](scripts/) | Repository maintenance utilities | Active |
| [`FILE_MANIFEST_SHA256.csv`](FILE_MANIFEST_SHA256.csv) | File sizes and SHA-256 checksums | Regenerated for repository snapshots |

## Quick Start

Run these commands from the repository root. Python 3.10 or newer is
recommended; this snapshot was validated with Python 3.11.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r research_routes/route_b_veriedge_system/requirements.txt
```

Validate the bundled capture subset and run the fast PACT path:

```powershell
python research_routes/route_b_veriedge_system/shared/accountedge_runtime_and_captures/scripts/validate_raw_captures.py

python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_projection.py --smoke `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/onboarding_smoke

python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_protocol.py `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/onboarding_g16

python research_routes/route_b_veriedge_system/experiments/pact_offline/pact_g16_state_machine.py `
  --output research_routes/route_b_veriedge_system/experiments/pact_offline/results/onboarding_state_machine
```

The experiment-specific README contains the complete command matrix and the
interpretation limits for every result family.

## Naming and Claim Boundary

- **VeriEdge** is the complete system direction.
- **PACT** is the active verification protocol.
- **PACT-G** is the ideal Gaussian analysis model.
- **PACT-G16** is the deterministic 16-bit inverse-CDF LUT implementation candidate.
- **PCRA** is a retired coordinate-opening design retained as a negative result.

The strongest completed evidence covers projection geometry, known-seed
nullspace attacks, conditional power, G16 coefficient coverage, transcript
binding, replay protection, and transactional state transitions. The main open
work is reference-execution architecture, independent-prompt calibration,
semantic attacks, three-node integration, end-to-end cost, and external
baselines.

## Data and Reproducibility

The bundled raw subset contains 48 capture files and supports smoke tests and
protocol development. Repeated random seeds improve Monte Carlo precision but
do not create additional independent prompts. Treat existing `results/` files
as a traceable snapshot, not as final paper numbers; regenerate any number that
will enter a manuscript and record the command, environment, seed policy, and
input manifest.

## Private Repository Notice

This directory is being prepared for a private research repository. It contains
working copies of third-party papers, old review/manuscript material, hardware
notes, and data with no blanket open-source license. Keep repository access
restricted. Before any future public release, review redistribution rights,
anonymity requirements, sensitive infrastructure details, and code/data
licensing separately.
