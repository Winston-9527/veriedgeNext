#!/usr/bin/env python3
"""Executable PACT-G16 commit-before-seed transcript prototype.

The prototype uses HMAC-SHA256 receipts because no public-key signature package
is present in the local environment. HMAC validates canonicalization and binding
logic but is not a replacement for publicly verifiable deployment signatures.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROUTE_ROOT = HERE.parents[1]
PCRA_DIR = HERE.parent / "pcra_offline_retired"
DEFAULT_DATA_ROOT = (
    ROUTE_ROOT
    / "shared"
    / "accountedge_runtime_and_captures"
    / "raw_captures"
    / "e2_live_subset"
)
sys.path.insert(0, str(PCRA_DIR))

from pcra_offline import load_pairs  # noqa: E402
from quantized_gaussian import lut_table  # noqa: E402


TENSOR_DOMAIN = b"PACT-TENSOR-COMMIT-v1\x00"
SEED_DOMAIN = b"PACT-G16-SEED-v1\x00"
ROW_DOMAIN = b"PACT-G16-ROW-v1\x00"
RECEIPT_DOMAIN = b"PACT-RECEIPT-v1\x00"
EXPECTED_TABLE_HASH = "8babbcaf96568f10165a1eab530c0e5c92d04de96761b6dbb3dadfa94baba37f"


@dataclass(frozen=True)
class SeedContext:
    task_id: str
    boundary: str
    model_id: str
    tensor_shape: tuple[int, ...]
    tensor_dtype: str
    actual_root: str
    reference_root: str
    beacon_hex: str


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def length_prefix(value: bytes) -> bytes:
    return len(value).to_bytes(8, "little") + value


def canonical_tensor(tensor: np.ndarray) -> tuple[np.ndarray, bytes, bytes]:
    array = np.asarray(tensor, dtype="<f4", order="C")
    metadata = canonical_json(
        {"dtype": "float32-le", "shape": list(array.shape), "order": "C"}
    )
    payload = array.tobytes(order="C")
    return array, metadata, payload


def commit_tensor(tensor: np.ndarray) -> str:
    _, metadata, payload = canonical_tensor(tensor)
    digest = hashlib.sha256()
    digest.update(TENSOR_DOMAIN)
    digest.update(length_prefix(metadata))
    digest.update(length_prefix(payload))
    return digest.hexdigest()


def derive_seed(context: SeedContext) -> bytes:
    transcript = canonical_json(asdict(context))
    return hashlib.shake_256(SEED_DOMAIN + length_prefix(transcript)).digest(32)


def table_hash() -> str:
    return hashlib.sha256(lut_table(16).astype("<f4").tobytes()).hexdigest()


def row_codes(seed: bytes, row: int, n: int) -> bytes:
    if row < 0 or row >= 2**32:
        raise ValueError("row outside uint32 domain")
    transcript = ROW_DOMAIN + seed + row.to_bytes(4, "little")
    return hashlib.shake_256(transcript).digest(2 * n)


def project_lut16(
    tensor: np.ndarray,
    seed: bytes,
    k: int,
    row_batch: int = 8,
    accumulation: str = "float64",
) -> tuple[np.ndarray, str]:
    array, _, _ = canonical_tensor(tensor)
    if accumulation not in {"float32", "float64"}:
        raise ValueError("accumulation must be float32 or float64")
    dtype = np.float32 if accumulation == "float32" else np.float64
    vector = np.asarray(array.reshape(-1), dtype=dtype)
    n = vector.size
    table = lut_table(16)
    if table_hash() != EXPECTED_TABLE_HASH:
        raise RuntimeError("LUT16 table hash mismatch; refuse protocol execution")
    sketch = np.empty(k, dtype="<f4" if accumulation == "float32" else "<f8")
    coefficient_digest = hashlib.sha256()
    for start in range(0, k, row_batch):
        stop = min(start + row_batch, k)
        encoded_rows = [row_codes(seed, row, n) for row in range(start, stop)]
        for encoded in encoded_rows:
            coefficient_digest.update(length_prefix(encoded))
        codes = np.frombuffer(b"".join(encoded_rows), dtype="<u2").reshape(stop - start, n)
        coefficients = np.asarray(table[codes], dtype=dtype)
        sketch[start:stop] = coefficients @ vector
    return sketch, coefficient_digest.hexdigest()


def statistic(actual: np.ndarray, reference: np.ndarray, n: int) -> float:
    if actual.shape != reference.shape:
        raise ValueError("Sketch shape mismatch")
    return float(np.mean(np.square(actual - reference)) / n)


def make_receipt(
    role: str,
    signer_id: str,
    task_id: str,
    boundary: str,
    tensor_root: str,
    peer_root: str,
    seed: bytes,
    coefficient_digest: str,
    sketch: np.ndarray,
    key: bytes,
) -> dict[str, object]:
    sketch_dtype = "float32-le" if np.asarray(sketch).dtype.itemsize == 4 else "float64-le"
    sketch_bytes = np.asarray(
        sketch, dtype="<f4" if sketch_dtype == "float32-le" else "<f8"
    ).tobytes()
    payload = {
        "version": "PACT-G16-receipt-v1",
        "role": role,
        "signer_id": signer_id,
        "task_id": task_id,
        "boundary": boundary,
        "tensor_root": tensor_root,
        "peer_root": peer_root,
        "seed_id": hashlib.sha256(seed).hexdigest(),
        "K": int(sketch.size),
        "coefficient_digest": coefficient_digest,
        "sketch_dtype": sketch_dtype,
        "sketch_b64": base64.b64encode(sketch_bytes).decode("ascii"),
        "sketch_sha256": hashlib.sha256(sketch_bytes).hexdigest(),
    }
    payload_bytes = canonical_json(payload)
    tag = hmac.new(key, RECEIPT_DOMAIN + length_prefix(payload_bytes), hashlib.sha256).digest()
    return {
        "authentication": "HMAC-SHA256-prototype-only",
        "payload": payload,
        "tag_b64": base64.b64encode(tag).decode("ascii"),
    }


def verify_receipt(receipt: dict[str, object], key: bytes) -> bool:
    try:
        payload = receipt["payload"]
        tag = base64.b64decode(str(receipt["tag_b64"]), validate=True)
        payload_bytes = canonical_json(payload)
        expected = hmac.new(
            key, RECEIPT_DOMAIN + length_prefix(payload_bytes), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(tag, expected):
            return False
        assert isinstance(payload, dict)
        sketch_bytes = base64.b64decode(str(payload["sketch_b64"]), validate=True)
        return hashlib.sha256(sketch_bytes).hexdigest() == payload["sketch_sha256"]
    except (KeyError, ValueError, TypeError, AssertionError):
        return False


def decode_sketch(payload: dict[str, object]) -> np.ndarray:
    dtype_name = str(payload["sketch_dtype"])
    if dtype_name == "float32-le":
        dtype = "<f4"
    elif dtype_name == "float64-le":
        dtype = "<f8"
    else:
        raise ValueError("Unsupported sketch dtype")
    raw = base64.b64decode(str(payload["sketch_b64"]), validate=True)
    sketch = np.frombuffer(raw, dtype=dtype)
    if sketch.size != int(payload["K"]):
        raise ValueError("Sketch length does not match K")
    return sketch


def adjudicate_receipt_pair(
    actual_receipt: dict[str, object],
    reference_receipt: dict[str, object],
    actual_key: bytes,
    reference_key: bytes,
    context: SeedContext,
) -> tuple[bool, float | None]:
    if not verify_receipt(actual_receipt, actual_key) or not verify_receipt(
        reference_receipt, reference_key
    ):
        return False, None
    try:
        actual_payload = actual_receipt["payload"]
        reference_payload = reference_receipt["payload"]
        assert isinstance(actual_payload, dict) and isinstance(reference_payload, dict)
        expected_seed_id = hashlib.sha256(derive_seed(context)).hexdigest()
        common_expected = {
            "task_id": context.task_id,
            "boundary": context.boundary,
            "seed_id": expected_seed_id,
        }
        for key, expected in common_expected.items():
            if actual_payload[key] != expected or reference_payload[key] != expected:
                return False, None
        if actual_payload["role"] != "actual_receiver":
            return False, None
        if reference_payload["role"] != "reference_witness":
            return False, None
        if actual_payload["tensor_root"] != context.actual_root:
            return False, None
        if actual_payload["peer_root"] != context.reference_root:
            return False, None
        if reference_payload["tensor_root"] != context.reference_root:
            return False, None
        if reference_payload["peer_root"] != context.actual_root:
            return False, None
        if actual_payload["K"] != reference_payload["K"]:
            return False, None
        if actual_payload["coefficient_digest"] != reference_payload["coefficient_digest"]:
            return False, None
        actual_sketch = decode_sketch(actual_payload)
        reference_sketch = decode_sketch(reference_payload)
        return True, statistic(actual_sketch, reference_sketch, int(np.prod(context.tensor_shape)))
    except (KeyError, ValueError, TypeError, AssertionError):
        return False, None


def context_binding_checks(context: SeedContext) -> dict[str, bool]:
    baseline = derive_seed(context)
    mutations = {
        "task_id": replace(context, task_id=context.task_id + "-changed"),
        "boundary": replace(context, boundary=context.boundary + "-changed"),
        "model_id": replace(context, model_id=context.model_id + "-changed"),
        "shape": replace(context, tensor_shape=context.tensor_shape + (1,)),
        "actual_root": replace(context, actual_root="00" * 32),
        "reference_root": replace(context, reference_root="11" * 32),
        "beacon": replace(context, beacon_hex="22" * 32),
    }
    return {name: derive_seed(candidate) != baseline for name, candidate in mutations.items()}


def benchmark_projection(
    tensor: np.ndarray, context: SeedContext, repeats: int
) -> list[dict[str, object]]:
    seed = derive_seed(context)
    rows: list[dict[str, object]] = []
    for k in (8, 16, 32, 64):
        for accumulation in ("float32", "float64"):
            samples: list[float] = []
            for _ in range(repeats):
                start = time.perf_counter_ns()
                project_lut16(tensor, seed, k, accumulation=accumulation)
                samples.append((time.perf_counter_ns() - start) / 1e6)
            rows.append(
                {
                    "K": k,
                    "N": tensor.size,
                    "accumulation": accumulation,
                    "repeats": repeats,
                    "median_projection_ms": statistics.median(samples),
                    "p90_projection_ms": float(np.quantile(samples, 0.90)),
                    "raw_two_sketch_bytes": 2
                    * k
                    * (4 if accumulation == "float32" else 8),
                }
            )
    return rows


def benchmark_transcript(
    tensor: np.ndarray, context: SeedContext, key: bytes, repeats: int
) -> dict[str, float]:
    commitment: list[float] = []
    seed_derivation: list[float] = []
    receipt_roundtrip: list[float] = []
    seed = derive_seed(context)
    sketch, coefficient_digest = project_lut16(tensor, seed, 64)
    for _ in range(repeats):
        start = time.perf_counter_ns()
        commit_tensor(tensor)
        commitment.append((time.perf_counter_ns() - start) / 1e6)
        start = time.perf_counter_ns()
        derive_seed(context)
        seed_derivation.append((time.perf_counter_ns() - start) / 1e6)
        start = time.perf_counter_ns()
        receipt = make_receipt(
            "benchmark",
            "benchmark-signer",
            context.task_id,
            context.boundary,
            context.actual_root,
            context.reference_root,
            seed,
            coefficient_digest,
            sketch,
            key,
        )
        if not verify_receipt(receipt, key):
            raise AssertionError("Receipt roundtrip failed")
        receipt_roundtrip.append((time.perf_counter_ns() - start) / 1e6)
    return {
        "median_commitment_ms": statistics.median(commitment),
        "median_seed_derivation_ms": statistics.median(seed_derivation),
        "median_receipt_create_verify_ms": statistics.median(receipt_roundtrip),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def protocol_matrix(
    pairs,
    receiver_key: bytes,
    reference_key: bytes,
    k: int = 16,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pair in pairs:
        if pair.prompt_id not in {"eval_001", "eval_005"}:
            continue
        actual = np.asarray(pair.candidate, dtype=np.float32)
        reference = np.asarray(pair.reference, dtype=np.float32)
        actual_root = commit_tensor(actual)
        reference_root = commit_tensor(reference)
        context = SeedContext(
            task_id=f"matrix-{pair.prompt_id}",
            boundary=pair.checkpoint,
            model_id="anonymous-heterogeneous-qwen",
            tensor_shape=actual.shape,
            tensor_dtype="float32-le",
            actual_root=actual_root,
            reference_root=reference_root,
            beacon_hex=hashlib.sha256(
                f"matrix-beacon|{pair.prompt_id}|{pair.checkpoint}".encode("utf-8")
            ).hexdigest(),
        )
        seed = derive_seed(context)
        actual_sketch, actual_digest = project_lut16(
            actual, seed, k, accumulation="float32"
        )
        reference_sketch, reference_digest = project_lut16(
            reference, seed, k, accumulation="float32"
        )
        actual_receipt = make_receipt(
            "actual_receiver",
            f"receiver-{pair.checkpoint}",
            context.task_id,
            context.boundary,
            actual_root,
            reference_root,
            seed,
            actual_digest,
            actual_sketch,
            receiver_key,
        )
        reference_receipt = make_receipt(
            "reference_witness",
            f"reference-{pair.checkpoint}",
            context.task_id,
            context.boundary,
            reference_root,
            actual_root,
            seed,
            reference_digest,
            reference_sketch,
            reference_key,
        )
        accepted, adjudicated = adjudicate_receipt_pair(
            actual_receipt,
            reference_receipt,
            receiver_key,
            reference_key,
            context,
        )
        direct = statistic(actual_sketch, reference_sketch, actual.size)
        exact = float(
            np.mean(
                np.square(
                    np.asarray(actual, dtype=np.float64)
                    - np.asarray(reference, dtype=np.float64)
                )
            )
        )
        rows.append(
            {
                "prompt_id": pair.prompt_id,
                "checkpoint": pair.checkpoint,
                "N": actual.size,
                "K": k,
                "accepted": accepted,
                "same_coefficient_digest": actual_digest == reference_digest,
                "adjudicated_matches_direct": bool(
                    adjudicated is not None
                    and np.isclose(adjudicated, direct, rtol=0.0, atol=1e-12)
                ),
                "projected_statistic": direct,
                "exact_full_residual_energy": exact,
                "estimator_to_exact_ratio": direct / exact,
                "combined_receipt_bytes": len(canonical_json(actual_receipt))
                + len(canonical_json(reference_receipt)),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "g16_protocol")
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()

    pairs = load_pairs(args.data_root, "eval")
    pair = next(
        item
        for item in pairs
        if item.prompt_id == "eval_001" and item.checkpoint == "prefill__C1"
    )
    reference = np.asarray(pair.reference.reshape(1, 16, 1024), dtype=np.float32)
    actual = np.asarray(pair.candidate.reshape(1, 16, 1024), dtype=np.float32)
    actual_root = commit_tensor(actual)
    reference_root = commit_tensor(reference)
    context = SeedContext(
        task_id="pact-prototype-eval-001",
        boundary="prefill__C1",
        model_id="anonymous-heterogeneous-qwen",
        tensor_shape=actual.shape,
        tensor_dtype="float32-le",
        actual_root=actual_root,
        reference_root=reference_root,
        beacon_hex=hashlib.sha256(b"PACT prototype beacon 2026-08-24").hexdigest(),
    )
    seed = derive_seed(context)

    actual_64, actual_coefficients = project_lut16(actual, seed, 64)
    reference_64, reference_coefficients = project_lut16(reference, seed, 64)
    residual_64, residual_coefficients = project_lut16(actual - reference, seed, 64)
    actual_32, actual_coefficients_32 = project_lut16(actual, seed, 32)
    actual_64_f32, _ = project_lut16(actual, seed, 64, accumulation="float32")
    reference_64_f32, _ = project_lut16(reference, seed, 64, accumulation="float32")
    residual_64_f32, _ = project_lut16(
        actual - reference, seed, 64, accumulation="float32"
    )

    receiver_key = hashlib.sha256(b"PACT receiver prototype key").digest()
    reference_key = hashlib.sha256(b"PACT reference prototype key").digest()
    actual_receipt = make_receipt(
        "actual_receiver",
        "receiver-C1",
        context.task_id,
        context.boundary,
        actual_root,
        reference_root,
        seed,
        actual_coefficients,
        actual_64,
        receiver_key,
    )
    reference_receipt = make_receipt(
        "reference_witness",
        "reference-C1",
        context.task_id,
        context.boundary,
        reference_root,
        actual_root,
        seed,
        reference_coefficients,
        reference_64,
        reference_key,
    )
    actual_receipt_f32 = make_receipt(
        "actual_receiver",
        "receiver-C1",
        context.task_id,
        context.boundary,
        actual_root,
        reference_root,
        seed,
        actual_coefficients,
        actual_64_f32,
        receiver_key,
    )
    reference_receipt_f32 = make_receipt(
        "reference_witness",
        "reference-C1",
        context.task_id,
        context.boundary,
        reference_root,
        actual_root,
        seed,
        reference_coefficients,
        reference_64_f32,
        reference_key,
    )
    tampered = json.loads(json.dumps(actual_receipt))
    tampered["payload"]["boundary"] = "prefill__C2"

    pair_valid, adjudicated_statistic = adjudicate_receipt_pair(
        actual_receipt,
        reference_receipt,
        receiver_key,
        reference_key,
        context,
    )
    replay_context = replace(context, task_id=context.task_id + "-replay")
    replay_valid, _ = adjudicate_receipt_pair(
        actual_receipt,
        reference_receipt,
        receiver_key,
        reference_key,
        replay_context,
    )

    linear_error = float(np.max(np.abs((actual_64 - reference_64) - residual_64)))
    linear_error_f32 = float(
        np.max(
            np.abs(
                (actual_64_f32.astype(np.float64) - reference_64_f32)
                - residual_64_f32
            )
        )
    )
    statistic_f64 = statistic(actual_64, reference_64, actual.size)
    statistic_f32 = statistic(actual_64_f32, reference_64_f32, actual.size)
    checks = {
        "table_hash_matches_frozen_spec": table_hash() == EXPECTED_TABLE_HASH,
        "same_seed_same_sketch": bool(np.array_equal(actual_64, project_lut16(actual, seed, 64)[0])),
        "prefix_rows_stable": bool(np.array_equal(actual_64[:32], actual_32)),
        "prefix_coefficient_digest_differs_by_length": actual_coefficients != actual_coefficients_32,
        "all_witnesses_use_same_coefficients": (
            actual_coefficients == reference_coefficients == residual_coefficients
        ),
        "linearity_max_abs_error": linear_error,
        "linearity_within_1e_7": linear_error <= 1e-7,
        "float32_linearity_max_abs_error": linear_error_f32,
        "actual_receipt_authenticates": verify_receipt(actual_receipt, receiver_key),
        "reference_receipt_authenticates": verify_receipt(reference_receipt, reference_key),
        "tampered_receipt_rejected": not verify_receipt(tampered, receiver_key),
        "wrong_key_rejected": not verify_receipt(actual_receipt, reference_key),
        "receipt_pair_adjudicates": pair_valid,
        "adjudicated_statistic_matches": bool(
            adjudicated_statistic is not None
            and np.isclose(adjudicated_statistic, statistic_f64, rtol=0.0, atol=1e-15)
        ),
        "authenticated_receipt_replay_rejected_in_changed_context": not replay_valid,
        "context_mutations_change_seed": context_binding_checks(context),
    }
    required_checks = [
        value
        if isinstance(value, bool)
        else all(value.values())
        if isinstance(value, dict)
        else True
        for value in checks.values()
    ]
    if not all(required_checks):
        raise AssertionError(checks)

    benchmark_rows = benchmark_projection(actual, context, args.repeats)
    matrix_rows = protocol_matrix(pairs, receiver_key, reference_key)
    if not all(
        bool(row["accepted"])
        and bool(row["same_coefficient_digest"])
        and bool(row["adjudicated_matches_direct"])
        for row in matrix_rows
    ):
        raise AssertionError(matrix_rows)
    actual_receipt_bytes = len(canonical_json(actual_receipt))
    reference_receipt_bytes = len(canonical_json(reference_receipt))
    actual_receipt_f32_bytes = len(canonical_json(actual_receipt_f32))
    reference_receipt_f32_bytes = len(canonical_json(reference_receipt_f32))
    result = {
        "status": "executable transcript prototype; HMAC receipts are not public signatures",
        "context": asdict(context),
        "seed_id": hashlib.sha256(seed).hexdigest(),
        "table_hash": table_hash(),
        "checks": checks,
        "K": 64,
        "N": actual.size,
        "projected_statistic": statistic_f64,
        "float32_projected_statistic": statistic_f32,
        "float32_statistic_relative_difference": abs(statistic_f32 - statistic_f64)
        / statistic_f64,
        "exact_full_residual_energy": float(
            np.mean(np.square(np.asarray(actual, dtype=np.float64) - reference))
        ),
        "actual_receipt_bytes": actual_receipt_bytes,
        "reference_receipt_bytes": reference_receipt_bytes,
        "combined_receipt_bytes": actual_receipt_bytes + reference_receipt_bytes,
        "combined_float32_receipt_bytes": actual_receipt_f32_bytes
        + reference_receipt_f32_bytes,
        "authentication_limitation": "replace HMAC signer with Ed25519 before deployment",
        "transcript_microbenchmark": benchmark_transcript(
            actual, context, receiver_key, args.repeats
        ),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "protocol_checks.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "sample_receipts.json").write_text(
        json.dumps(
            {"actual": actual_receipt, "reference": reference_receipt}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(args.output / "protocol_benchmark.csv", benchmark_rows)
    write_csv(args.output / "protocol_matrix.csv", matrix_rows)
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
