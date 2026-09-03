# Paper 1 Revision Plan

Project:

`VeriEdge: Verification-Aware Orchestration for Trustworthy Decentralized Edge LLM Inference`

Main draft:

- `eurosys_draft.tex`

Related planning files:

- `PAPER1_KICKOFF_MANUAL.md`
- `PAPER1_EXPERIMENT_COMPLETION_MANUAL.md`
- `PAPER1_E1_E2_E4_E5_CONSTRUCTION_BOARD.md`

## One-Sentence Goal

Revise the paper into a coherent systems paper around:

`verification-aware orchestration for trustworthy heterogeneous decentralized edge LLM inference`

The revision should not treat new experiments as disconnected additions. Each result must close a specific claim gap in the main draft and make the system story stronger.

## Revision Principle

Start writing before the final experimental data arrives.

The goal of the current phase is to turn the draft into a data-ready structure:

- every major claim has a defined evaluation slot
- every key experiment has a table or figure position
- every result section has a systems takeaway
- every claim has a clear scope boundary

When the data arrives, the remaining work should be filling numbers, replacing placeholders, polishing captions, and calibrating claim strength.

## Core Narrative

The paper should not read as a blockchain resource-market paper. Blockchain and contracts are coordination substrate components, not the main novelty.

The main narrative should be:

1. Decentralized edge inference is constrained by heterogeneous execution, selective task disclosure, and accountable settlement.
2. These constraints make orchestration verification-aware by necessity.
3. VeriEdge combines lightweight placement, selective task delivery, and layered verification.
4. TSTC provides a practical dispute-escalation point under heterogeneous execution.
5. Placement should account for network cost, collaboration width, and verification risk, not only nominal resource cost.

## Evidence Chain

The revised Evaluation should close five connected claims.

### Claim 1: Collaborative inference has real systems cost

Existing support:

- EXO deployment results
- latency, TTFT, OTPS, and success-rate degradation as provider count increases

Revision role:

- motivate why placement cannot simply recruit more providers
- connect deployment cost to E5
- frame collaboration width as an orchestration decision

### Claim 2: Selective delivery is both privacy and performance infrastructure

Existing support:

- PPD vs RPD delivery latency
- requester-side time breakdown

Revision role:

- keep selective disclosure as a system-path result
- avoid presenting PPD as an isolated privacy add-on
- connect it to the end-to-end orchestration path

### Claim 3: Strict THC is brittle under honest heterogeneity

New support:

- E1 real heterogeneous honest-honest paired capture

Revision role:

- replace pending rows in the paired-capture table
- show that THC false positives are not merely a synthetic artifact
- strengthen the need for heterogeneity-tolerant verification

### Claim 4: TSTC has an interpretable operating point

New support:

- E2 sample-size sweep
- E2 tolerance-scale sweep
- E2 checkpoint-specific vs global tolerance comparison
- runtime per trace

Revision role:

- move beyond the current noise-response figure
- explain why the chosen sample size and tolerance map are reasonable
- report FPR, TPR, localization accuracy, and runtime together

### Claim 5: Verification and placement have systems tradeoffs

New support:

- E4 verifier operational overhead
- E5 verification-aware placement comparison

Revision role:

- turn verifier overhead from pending scope facts into deployability evidence
- turn the placement proxy into a policy-to-metrics comparison
- establish that orchestration must reason jointly about network cost and verification risk

## Proposed Main-Draft Structure

The current broad structure can remain, but Evaluation should become more explicitly claim-driven.

Recommended Evaluation structure:

1. `Methodology and Scope`
2. `End-to-End Deployment Cost`
3. `Privacy-Preserving Delivery Overhead`
4. `Verification Under Heterogeneous Execution`
5. `Cross-Device Paired Capture`
6. `TSTC Ablation and Operating Point`
7. `Verifier Operational Overhead`
8. `Verification-Aware Placement`

Each subsection should follow the same local pattern:

1. question or claim gap
2. method
3. result
4. systems takeaway
5. scope boundary where needed

## Section-Level Revision Plan

### Abstract

Tasks:

- strengthen the framing around verification-aware orchestration
- keep blockchain and settlement as substrate details
- mention E1/E2/E4/E5 results only after data is finalized
- avoid overclaiming deployability until E4 numbers are integrated

Expected final role:

- state that VeriEdge combines selective delivery, lightweight orchestration, and layered verification
- summarize the strongest evidence chain in one compact paragraph

### Introduction

Tasks:

- sharpen the problem statement around heterogeneous decentralized inference
- reduce market-mechanism language
- make verification-aware orchestration the central systems problem
- update contributions so they match the final evidence

Contribution shape:

1. framing: verification-aware orchestration for heterogeneous decentralized inference
2. design: selective delivery plus layered accountability with TSTC escalation
3. implementation and evaluation: EXO/IPFS/contracts prototype with deployment, delivery, verification, overhead, and placement evidence

### Problem Setting and Design Goals

Tasks:

- ensure design goals map directly to later evaluations
- make heterogeneity tolerance and escalable accountability explicit
- avoid adding new mechanism-theoretic goals that the paper does not evaluate

### System Overview

Tasks:

- preserve the three-plane architecture
- make placement, delivery, and verification read as one loop
- clarify how verification signals can feed orchestration decisions

### Verification-Aware Orchestration

Tasks:

- keep placement lightweight in the base system
- avoid presenting pricing or resource-market logic as the novelty
- prepare the reader for E5 by explaining why verification-aware placement is a natural extension of the base orchestrator

### Prototype Implementation

Tasks:

- convert implementation details into evaluation-relevant interfaces
- describe the instrumentation needed for E4
- weaken or remove pending/deferred language once new data is inserted
- keep prototype-scale boundaries clear

### Evaluation

Tasks:

- rewrite the top-level evaluation questions after E1/E2/E4/E5 data arrives
- ensure each subsection has one decisive takeaway
- remove all `pending` entries before submission
- prevent the section from becoming a list of experiments without narrative connection

### Discussion

Tasks:

- update design lessons based on final E1/E2/E4/E5 results
- keep the strongest lesson: more providers are not automatically better
- explain why accountability should be layered
- explain why selective delivery is performance-relevant, not just privacy-relevant

### Limitations

Tasks:

- replace pending-oriented limitations with scope-oriented limitations
- be explicit about prototype scale, workload scope, prefill-focused verification, and non-cryptographic guarantees
- avoid undermining completed results while still being honest

### Conclusion

Tasks:

- close on accountable decentralized inference, not resource pooling
- summarize the evidence chain
- avoid introducing new claims not supported in Evaluation

## Experiment Write-Back Plan

### E1: Real Heterogeneous Honest-Honest Paired Capture

Target location:

- Cross-device paired-capture subsection

Required main-text output:

- completed paired-capture table
- one paragraph explaining THC FPR vs TSTC FPR under real device/backend pairs
- one systems takeaway about heterogeneous execution

Required data:

- pairwise summary table
- pairwise details table
- checkpoint mismatch distribution

Acceptance criteria:

- no pending rows
- calibration and evaluation split is clear
- both THC and TSTC are reported

### E2: TSTC Ablation

Target location:

- TSTC ablation and operating-point subsection

Required main-text output:

- sample-size sweep figure or table
- tolerance-scale figure or table
- checkpoint-specific vs global tolerance comparison
- one paragraph explaining why the selected operating point is reasonable

Required metrics:

- FPR
- TPR
- localization accuracy
- runtime per trace

Acceptance criteria:

- not just a noise-response curve
- includes runtime
- includes real heterogeneous traces when available

### E4: Verifier Operational Overhead

Target location:

- Verifier operational-overhead subsection

Required main-text output:

- overhead table with byte and time units
- breakdown across honest, challenged, and tamper or failed-challenge traces
- one systems takeaway about deployability

Required metrics:

- checkpoint capture size
- commitment size
- verifier replay runtime
- end-to-end challenge latency
- validator-side storage footprint

Acceptance criteria:

- no unitless estimates
- no pending rows
- measurement object is explicit

### E5: Verification-Aware Placement

Target location:

- Verification-aware placement subsection

Required main-text output:

- policy-to-metrics comparison figure or table
- updated text that keeps the current proxy as supporting evidence
- one orchestration takeaway

Required policies:

- random
- cost-only
- reputation-aware
- network-aware
- verification-aware

Required metrics:

- task latency
- success rate
- challenge rate
- verifier workload
- goodput

Acceptance criteria:

- not only cost-only vs verification-aware
- not only latency
- workload is comparable to the deployment evaluation

## Data-Ready Writing Tasks Before Final Results Arrive

These can start immediately:

- clean terminology across the draft
- reduce blockchain-market framing
- rewrite Evaluation introductions around claim gaps
- prepare final captions for E1/E2/E4/E5 figures and tables
- replace vague pending prose with clearly marked internal placeholders
- draft result paragraphs with placeholders for numeric values
- prepare limitations text with adjustable claim strength
- check that every major result has a systems takeaway

## Four-Day Revision Schedule After Data Arrives

### Day 1: Structural Revision

Goals:

- update Introduction and contributions
- reshape Evaluation around the evidence chain
- mark all final data insertion points
- ensure E1/E2/E4/E5 have clear table or figure slots

Deliverable:

- data-ready `eurosys_draft.tex`

### Day 2: Verification Evidence

Goals:

- integrate E1 paired-capture results
- integrate E2 ablation results
- update verifier-related claims in Abstract, Introduction, Evaluation, Discussion, and Limitations

Deliverable:

- completed verification evidence chain

### Day 3: Systems Evidence

Goals:

- integrate E4 overhead results
- integrate E5 placement comparison results
- strengthen orchestration and deployability takeaways
- update prototype instrumentation description if needed

Deliverable:

- completed systems evidence chain

### Day 4: Full-Paper Polish

Goals:

- unify terminology
- tighten captions
- calibrate claim strength
- remove placeholders and pending language
- compile LaTeX
- inspect references, figures, tables, and overfull boxes

Deliverable:

- submission-oriented draft

## Review Checklist

Before considering the revision complete, check:

- every Evaluation subsection answers a specific question
- every new experiment has raw data saved outside the PDF
- every figure or table has a final caption
- every result has one explicit systems takeaway
- no `pending` remains in the main draft
- no unsupported deployability or generality claim is introduced
- the paper does not drift back into pricing, auction, or broad market-platform framing
- the conclusion restates the evidence chain rather than adding new claims

## Risk Controls

If E1 data is weaker than expected:

- keep the claim scoped to measured device/backend pairs
- emphasize reduction rather than elimination of false positives
- avoid claiming deployment-wide heterogeneity robustness

If E2 ablation is noisy:

- report the stable operating region
- move weaker sweep details to appendix
- keep the main text focused on the clearest design choice

If E4 overhead is higher than expected:

- frame it as challenge-path cost, not common-path cost
- emphasize layered verification and bounded escalation
- discuss when escalation is worth paying for

If E5 policy comparison is partial:

- preserve the existing proxy as motivation
- include the strongest completed policies
- explicitly state which signal is still approximated
- avoid claiming a fully optimized scheduler

## Final Writing Rule

Do not add experiments for volume.

Only add results that make one of the main claims harder to dismiss.

