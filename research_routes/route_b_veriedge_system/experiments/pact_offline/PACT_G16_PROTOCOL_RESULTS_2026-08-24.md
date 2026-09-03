# PACT-G16 executable protocol prototype

Date: 2026-08-24  
Status: local transcript prototype; HMAC authentication is not a deployment signature

## Implemented transcript

1. Canonicalize each tensor as C-order little-endian float32 with shape/dtype
   metadata.
2. Commit actual and reference tensors with domain-separated SHA-256.
3. Derive a 256-bit seed with SHAKE256 over task, boundary, model, shape, dtype,
   both tensor roots, and beacon output.
4. Derive each projection row independently with domain-separated SHAKE256,
   permitting deterministic prefix expansion and row-addressable computation.
5. Interpret each two-byte PRG output as a LUT16 index and compute the sketch.
6. Have the receiver and reference witness authenticate canonical receipts that
   bind roots, peer root, task, boundary, seed ID, K, coefficient digest, sketch
   dtype, bytes, and sketch hash.
7. Adjudicate only after cross-checking both authenticated receipts against the
   committed context.

The LUT16 little-endian float32 table is pinned by SHA-256
`8babbcaf96568f10165a1eab530c0e5c92d04de96761b6dbb3dadfa94baba37f`;
the prototype refuses to run if the table differs.

## Security/binding checks

All implemented checks pass:

- identical transcript produces an identical seed and sketch;
- the first 32 rows of K=64 equal a separately generated K=32 prefix;
- actual, reference, and residual witnesses derive identical coefficient flows;
- float64 linearity error is `4.93e-12`;
- changing task, boundary, model, shape, either root, or beacon changes the seed;
- altered receipt fields and the wrong authentication key are rejected;
- an otherwise valid receipt pair replayed under a different task is rejected;
- the adjudicator checks roles, cross-roots, seed, K, coefficient digest, sketch
  encoding, and context before returning a statistic.

The local environment lacks Ed25519. Receipts therefore use HMAC-SHA256 behind
a replaceable signer boundary. HMAC validates canonicalization, binding, and
tamper rejection, but does not provide public verifiability or non-repudiation.

## Real-boundary matrix

The full receipt/adjudication path succeeds on eval_001 and eval_005 at C1--C3,
covering tensor lengths 15,360 and 16,384. All six cases have matching
coefficient digests and adjudicated/direct statistics.

At K=16, estimator-to-exact-energy ratios range from 0.61 to 1.52. This is
expected projection variance at small K, not a transcript inconsistency, and
supports retaining the adaptive K policy.

## Evidence and local runtime

- K=64 JSON/HMAC receipt pair: 2,809 B with float64 sketches; 2,129 B with
  float32 sketches.
- K=16 float32 receipt pair in the six-boundary matrix: 1,619 B.
- Raw two-sketch payloads range from 64 B (K=8 float32) to 1,024 B (K=64
  float64); JSON/base64/context dominate the prototype envelope.

Representative same-run projection medians for N=16,384:

| K | float32 | float64 |
|---:|---:|---:|
| 8 | 2.31 ms | 3.82 ms |
| 16 | 4.90 ms | 9.67 ms |
| 32 | 13.12 ms | 16.35 ms |
| 64 | 20.60 ms | 22.07 ms |

Tensor commitment, seed derivation, and receipt create+verify are roughly
0.16 ms, 0.02 ms, and 0.08 ms respectively; projection dominates.

float32 reduces cost and raw evidence. Its projected energy differs from
float64 by only `1.42e-5` relatively on the primary capture, but per-row
linearity error reaches `0.0198`. Cross-hardware reproducibility has not been
tested, so float64 remains the conservative prototype default.

## Remaining deployment work

1. Replace HMAC with Ed25519 (or the system's committed public-key signature
   scheme) and verify public-key identity/certificate binding.
2. Replace the prototype beacon string with a real unpredictable beacon or
   commit--reveal service and specify timeout/failure behavior.
3. Specify the cryptographic PRG/XOF version, counter encoding, table bytes,
   accumulation kernel, and receipt schema as a versioned wire standard.
4. Test float32/float64 sketches on the actual heterogeneous nodes.
5. Add durable storage, replay protection, timestamps/nonces, and settlement
   state transitions.
6. Collect enough independent prompts for honest-envelope calibration.

## Artifacts

- `pact_g16_protocol.py`: executable transcript and adjudicator.
- `results/g16_protocol/protocol_checks.json`: checks and evidence sizes.
- `results/g16_protocol/protocol_matrix.csv`: six real boundaries.
- `results/g16_protocol/protocol_benchmark.csv`: float32/float64 timing.
- `results/g16_protocol/sample_receipts.json`: canonical receipt examples.
