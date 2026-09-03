# Paper 1 Restructure Plan

## Paper Identity

Working title:

`VeriEdge: Verification-Aware Orchestration for Trustworthy Decentralized Edge LLM Inference`

One-sentence positioning:

This paper is a **systems paper** about how to orchestrate decentralized heterogeneous edge inference with selective task delivery, cheap routine screening, and accountable dispute escalation, rather than a paper about blockchain market design.

## Core Contributions

- C1. We formulate **verification-aware orchestration** as the central systems problem in decentralized heterogeneous edge inference, and build an end-to-end architecture that connects placement, private task delivery, layered verification, and settlement.
- C2. We design a dispute-escalation verifier based on **TSTC**, which reduces false alarms under honest heterogeneity while preserving tamper detection and first-mismatch localization relative to a strict THC baseline.
- C3. We implement a prototype spanning EXO-based collaborative inference, IPFS-based ciphertext publication, and contract-mediated settlement, and evaluate deployment cost, delivery overhead, verification behavior, and verification-aware placement tradeoffs.

## Formal TOC

1. Introduction
2. Problem Setting and Design Goals
3. System Overview
4. Verification-Aware Orchestration
5. Prototype Implementation
6. Evaluation
7. Discussion and Limitations
8. Related Work
9. Conclusion

## Abstract Draft

Edge devices expose a large aggregate compute pool for AI inference, but turning that pool into a trustworthy decentralized service remains difficult. A practical system must decide how to assemble heterogeneous providers into an execution group, distribute task data without exposing plaintext to the whole network, and verify disputed executions without paying the cost of full deterministic replay on every task. Existing decentralized AI systems show that collaborative inference is feasible, but they leave accountability and verification under-specified; meanwhile, strict checkpoint hashing is brittle under heterogeneous execution, while heavyweight cryptographic verification remains too expensive for routine large-model inference.

This paper presents VeriEdge, a verification-aware orchestration framework for decentralized edge LLM inference. VeriEdge combines lightweight off-chain placement with on-chain commitments and settlement, but treats blockchain as a coordination substrate rather than as the core contribution. The system integrates three components: a lightweight orchestration layer that selects providers for collaborative execution, a privacy-preserving task delivery path based on off-chain ciphertext publication and targeted key release, and a layered verification service that uses cheap screening for routine checks and a tolerance-aware sampled tensor chain (TSTC) for dispute escalation under heterogeneous execution.

We implement a prototype on top of EXO, IPFS, and contract-mediated settlement. Our current results show that the delivery path reduces large-payload task-distribution latency relative to replicated encrypted delivery, and that TSTC substantially lowers false positives under honest heterogeneous execution while preserving tamper detection and shard-level localization on the current prefill-focused evaluation object. These results suggest that decentralized edge inference is better framed as a verification-aware systems problem than as a mechanism-centric resource market.

## Keep / Delete / Move Plan

### Keep as Paper 1 Core

From `eurosys_draft.tex`:

- `Introduction`
- `Problem Setting and Design Goals`
- `System Overview`
- `Verification-Aware Orchestration`
- `Prototype Implementation`
- `Evaluation`
- `Discussion`
- `Related Work`
- `Conclusion`

From `jrnl_overleaf.tex`:

- privacy-preserving delivery description
- EXO deployment setup details that help explain prototype realism
- THC / TSTC verifier definition and the prefill-focused scope
- verification feasibility experiments

### Delete from Paper 1 Main Story

These belong to paper 2 or should be removed from the paper 1 main body:

- reputation-aware greedy matching as a headline contribution
- max-cost-based uniform pricing as a headline contribution
- guarded pricing
- demand sanity cap
- allocation/pricing welfare and utility experiments
- adversarial robustness experiments for market manipulation
- long discussions of EigenLayer as if it were a core novelty
- zkLLM / DSperse as contribution-level items

### Keep but Downgrade

- TIQE: keep only as routine screening background, not as a primary contribution
- EXO functional equivalence: condense heavily, move to appendix if space gets tight
- EXO deployment cost: keep, but frame as deployment lesson rather than as a positive scale-up result
- blockchain contracts: keep as coordination substrate, not as novelty

### Move / Rewrite

| Source | Current Content | Action | Destination in Paper 1 |
| --- | --- | --- | --- |
| `eurosys_draft.tex` | Lightweight Placement and Matching | Keep but narrow | Section 4.1, only as supporting orchestration substrate |
| `jrnl_overleaf.tex` | Privacy Mechanism Evaluation | Move and rewrite | Section 6.2 Delivery Overhead |
| `jrnl_overleaf.tex` | EXO Functional Equivalence | Condense | Section 6.1 or appendix |
| `jrnl_overleaf.tex` | EXO Implementation Evaluation | Keep and reframe | Section 6.1 End-to-End Deployment Cost |
| `jrnl_overleaf.tex` | Verification Feasibility Evaluation | Keep and strengthen | Section 6.3 Verification Under Heterogeneous Execution |
| `jrnl_overleaf.tex` | TSTC Numeric Perturbation Response | Keep | Section 6.3 or 6.4 as verifier mechanism probe |
| `jrnl_overleaf.tex` | System workflow prose | Extract only necessary parts | Sections 2 and 3 |

## Section-by-Section Writing Guidance

### 1. Introduction

- Start from trustworthy decentralized inference, not from blockchain markets.
- State the heterogeneity problem early.
- Introduce verification-aware orchestration as the key systems abstraction.

### 2. Problem Setting and Design Goals

- Define requesters, providers, orchestrator, storage backend, verification service, contracts.
- Keep the threat model crisp.
- Explicitly say what the paper does **not** claim.

### 3. System Overview

- Use one architecture figure.
- Show the data path and the verification path separately.
- Minimize economic-mechanism detail here.

### 4. Verification-Aware Orchestration

- 4.1 Lightweight placement: only enough detail to make deployment concrete.
- 4.2 Private task delivery: emphasize selective disclosure and payload scaling.
- 4.3 Layered verification: routine screening vs dispute escalation.
- 4.4 TSTC details: sampling, quantization, chain commitment, localization.

### 5. Prototype Implementation

- Make this concrete: EXO hooks, checkpoint capture, task publication, challenge path.
- Include implementation boundaries and omissions.

### 6. Evaluation

- Q1: End-to-end deployment cost
- Q2: Privacy-preserving delivery overhead
- Q3: Verification under heterogeneous execution
- Q4: Overhead and ablation of the escalation verifier
- Q5: Verification-aware placement or orchestration tradeoffs

### 7. Discussion and Limitations

- Be honest, but do not undersell the contribution.
- Separate scope limitations from future work.

## Required New Evidence Before Submission

- paired real honest-hetero capture
- TSTC ablation on sample size and tolerance
- attack coverage beyond synthetic noise
- verifier storage / runtime / challenge overhead
- a placement comparison that uses verification-aware metrics, not just utility

## File Organization for Paper 1

Suggested paper 1 writing area:

- `paper1_veriedge/`
  - `eurosys_draft.tex`
  - `eurosys_draft.pdf`
  - build artifacts
  - `PAPER1_RESTRUCTURE_PLAN.md`
  - `handbook/`
  - `img/`
  - `bibtex/bib/`

This keeps paper 1 self-contained without disturbing the journal-style paper 2 materials at the repository root.
