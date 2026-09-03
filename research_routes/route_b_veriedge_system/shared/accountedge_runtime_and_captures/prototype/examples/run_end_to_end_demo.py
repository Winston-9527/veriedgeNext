from __future__ import annotations

import json

import numpy as np

from prototype.ledger_interface import MockLedger
from prototype.orchestrator import CandidatePlacement, TaskDescriptor, VerifierProfile, rank_and_commit
from prototype.ppd_runtime import publish_payload, recover_payload
from prototype.tstc_verifier import compare_digest_chains, sketch_tensor


def _provider_keys(provider_ids: tuple[str, ...]) -> dict[str, str]:
    return {provider_id: f"public-key-for-{provider_id}" for provider_id in provider_ids}


def _toy_checkpoint_captures() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    rng = np.random.default_rng(11)
    honest = {
        "C1": rng.normal(size=(6, 8)),
        "C2": rng.normal(size=(6, 8)),
        "C3": rng.normal(size=(6, 8)),
    }
    tampered = {name: value.copy() for name, value in honest.items()}
    tampered["C2"][2, :] += 0.75
    return honest, tampered


def run_demo() -> dict:
    task = TaskDescriptor(
        task_id="task_demo_001",
        model_ref="anonymous-model-ref",
        input_ref="synthetic-payload-ref",
        required_checkpoints=("C1", "C2", "C3"),
        max_latency_ms=1200.0,
        risk_budget=0.05,
    )
    verifier_profiles = {
        "profile_projcos4": VerifierProfile(
            profile_id="profile_projcos4",
            sketch="projcos4",
            fpr=0.02,
            tpr=1.0,
            verify_ms=3.8,
            sketch_bytes=256,
            feasible=True,
        ),
        "profile_scalar16": VerifierProfile(
            profile_id="profile_scalar16",
            sketch="scalar16",
            fpr=0.15,
            tpr=0.76,
            verify_ms=3.6,
            sketch_bytes=64,
            feasible=False,
        ),
    }
    candidates = [
        CandidatePlacement(
            candidate_id="candidate_fast_but_risky",
            provider_ids=("provider_a", "provider_b", "provider_c"),
            shard_map={"C1": "provider_a", "C2": "provider_b", "C3": "provider_c"},
            verifier_profile_id="profile_scalar16",
            estimated_latency_ms=880.0,
            expected_false_dispute_risk=0.15,
            expected_challenge_ms=3.6,
        ),
        CandidatePlacement(
            candidate_id="candidate_verifiable",
            provider_ids=("provider_a", "provider_d", "provider_e"),
            shard_map={"C1": "provider_a", "C2": "provider_d", "C3": "provider_e"},
            verifier_profile_id="profile_projcos4",
            estimated_latency_ms=940.0,
            expected_false_dispute_risk=0.02,
            expected_challenge_ms=3.8,
        ),
    ]
    commitment = rank_and_commit(task, candidates, verifier_profiles)

    ledger = MockLedger()
    ledger.record_placement(commitment)

    payload = b"synthetic prompt and tensor descriptor"
    provider_keys = _provider_keys(commitment.provider_ids)
    published, packages = publish_payload(payload, provider_keys, nonce=b"0" * 32)
    recovered = {
        package.provider_id: recover_payload(published, package, provider_keys[package.provider_id]).decode()
        for package in packages
    }

    honest, tampered = _toy_checkpoint_captures()
    sketches_a = {name: sketch_tensor(tensor, sketch_dim=4, seed=17) for name, tensor in honest.items()}
    sketches_b = {name: sketch_tensor(tensor, sketch_dim=4, seed=17) for name, tensor in tampered.items()}
    challenge = compare_digest_chains(sketches_a, sketches_b, tolerance=0.25)

    challenge_record = ledger.record_challenge(task.task_id, challenge)
    settlement = ledger.settle(task.task_id)

    return {
        "public_input": {
            "task": task.__dict__,
            "candidate_count": len(candidates),
            "verifier_profiles": {key: value.__dict__ for key, value in verifier_profiles.items()},
        },
        "placement_commitment": commitment.__dict__,
        "ppd_delivery": {
            "object_id": published.object_id,
            "ciphertext_bytes": len(published.ciphertext),
            "access_package_count": len(packages),
            "providers_recovered_payload": sorted(recovered),
        },
        "tstc_challenge": challenge_record.__dict__,
        "settlement": settlement.__dict__,
        "ledger_snapshot": ledger.snapshot(),
    }


def main() -> None:
    result = run_demo()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

