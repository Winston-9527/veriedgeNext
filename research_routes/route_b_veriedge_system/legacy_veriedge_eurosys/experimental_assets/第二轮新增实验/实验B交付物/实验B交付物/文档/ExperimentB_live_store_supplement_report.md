# Experiment B Live-Store Supplement

## Scope

This supplement upgrades the cache-control part of Experiment B from modeled unique IDs to real fresh ciphertext objects. Every run creates a fresh encrypted payload, derives the object key from the SHA-256 hash of the actual ciphertext, writes a real local object-store file for PPD, and makes providers fetch and hash-verify the object.

This is still a local-store microbenchmark, not a geographically distributed deployment. Its purpose is to close the workbook requirement that each run use fresh payload/object content and avoid cache reuse.

## Matrix

| Dimension | Values |
|---|---|
| Payload size | 100MB |
| Group size | 1, 2, 4, 8 |
| Modes | RPD, PPD |
| Runs per cell | 30 |
| Total runs | 240 |

## Results

| k | RPD median ms | PPD median ms | Median reduction | RPD requester MB | PPD requester MB | PPD store MB | Requester egress reduction |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 992.8 | 1033.0 | -4.0% | 100.0 | 100.001 | 100.0 | -0.0% |
| 2 | 997.2 | 1034.0 | -3.7% | 200.0 | 100.001 | 200.0 | 50.0% |
| 4 | 1048.1 | 1045.7 | 0.2% | 400.0 | 100.003 | 400.0 | 75.0% |
| 8 | 1065.3 | 1089.2 | -2.2% | 800.0 | 100.005 | 800.0 | 87.5% |

At k=8, PPD reduces requester egress by 87.5%. The latency result is local-store specific and should not replace the calibrated LAN/WAN latency model; it validates fresh content-hash/object-store semantics.

## Audit

Audit status: **PASS**

- Every run has a unique SHA-256 content hash.
- PPD object keys are derived from actual ciphertext hashes.
- Providers fetch real local-store objects and verify hashes.
- RPD and PPD use the same payload size and group sizes.
