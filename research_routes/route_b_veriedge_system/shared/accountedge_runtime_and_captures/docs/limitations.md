# Artifact Limitations

This artifact is intentionally scoped.

1. It is a reproducibility capsule for the main evaluation tables and figures,
   not a production edge-inference deployment.
2. Hardware-dependent verifier measurements are included as measured profile
   tables and replay logs.
3. Placement replay uses controlled candidate and workload inputs to isolate the
   effect of measured verifier profiles on admission and policy selection.
4. Delivery results are reported as a delivery-path group-size sweep. LAN/WAN
   values are derived from explicit delivery profiles. The local-store run
   validates protocol bookkeeping and fresh object generation; it is not claimed
   as a live geo-distributed WAN deployment.
5. The verifier profiles are evaluated as policy-scoped checkpoint evidence, not
   as a cryptographic proof of semantic correctness for arbitrary model outputs.
6. The `prototype/` code is an interface-level smoke prototype. It uses toy
   payloads, local state, and small tensor fixtures; it does not perform
   multi-node orchestration, production encryption, model inference, or on-chain
   deployment.
7. The optional `data_collection/` scripts can collect small checkpoint-capture
   smoke profiles from Hugging Face or synthetic tensors. They are not expected
   to reproduce the paper's exact multi-device measured numbers.
8. The included raw checkpoint captures are an anonymized subset of the full raw
   corpus. They are sufficient for schema inspection and small verifier checks,
   but the complete multi-device corpus is represented in the artifact by the
   measured CSV summaries under `data/`.
