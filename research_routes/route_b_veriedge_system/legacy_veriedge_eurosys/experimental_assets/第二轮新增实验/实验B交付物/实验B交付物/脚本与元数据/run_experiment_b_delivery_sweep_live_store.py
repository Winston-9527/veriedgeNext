from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import matplotlib.pyplot as plt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _find_repo_root(start: Path) -> Path:
    for path in [start.resolve(), *start.resolve().parents]:
        if (path / "paper1_veriedge").exists() and (path / "artifacts").exists():
            return path
    raise RuntimeError(f"cannot locate VeriEdge repo root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
OUTPUT_ROOT = REPO_ROOT / "paper1_veriedge" / "veriedge_revision_results" / "experiment_b_delivery_sweep_live_store"
DEFAULT_GROUP_SIZES = [1, 2, 4, 8]
DEFAULT_RUNS_PER_CELL = 30
SEED_BYTES = b"veriedge-experiment-b-live-store-20260514"


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _percentile(values: Sequence[float], pct: float) -> float:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _mb(num_bytes: float) -> float:
    return num_bytes / 1_000_000.0


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _deterministic_payload(payload_bytes: int, run_id: str) -> bytes:
    # Deterministic stream keeps the experiment reproducible while still giving
    # every run unique content. The encrypted ciphertext is also nonce-unique.
    seed = hashlib.sha256(SEED_BYTES + run_id.encode("utf-8")).digest()
    blocks: List[bytes] = []
    produced = 0
    counter = 0
    while produced < payload_bytes:
        block = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        blocks.append(block)
        produced += len(block)
        counter += 1
    return b"".join(blocks)[:payload_bytes]


def _encrypt_payload(payload: bytes, run_id: str) -> Tuple[bytes, bytes, bytes, float]:
    key = hashlib.sha256(b"key:" + SEED_BYTES + run_id.encode("utf-8")).digest()
    nonce = hashlib.sha256(b"nonce:" + SEED_BYTES + run_id.encode("utf-8")).digest()[:12]
    aes = AESGCM(key)
    start = time.perf_counter()
    ciphertext = aes.encrypt(nonce, payload, None)
    encrypt_ms = (time.perf_counter() - start) * 1000.0
    return key, nonce, ciphertext, encrypt_ms


def _provider_public_keys(max_group_size: int) -> List[Any]:
    return [
        rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
        for _ in range(max_group_size)
    ]


def _access_package_bytes(public_keys: Sequence[Any], *, task_key: bytes, cid: str, run_id: str) -> int:
    total = 0
    for idx, public_key in enumerate(public_keys, start=1):
        encrypted_key = public_key.encrypt(
            task_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        package = {
            "task_id": run_id,
            "provider_id": f"P{idx}",
            "cid": cid,
            "encrypted_task_key_b64": base64.b64encode(encrypted_key).decode("ascii"),
            "cipher": "AES-256-GCM",
            "locator": f"local-store://{cid}",
        }
        total += len(json.dumps(package, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return total


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def _copy_file(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst.stat().st_size


def _fetch_and_verify(src: Path, dst: Path, expected_hash: str) -> Tuple[int, bool]:
    copied = _copy_file(src, dst)
    return copied, _sha256_file(dst) == expected_hash


def _run_cell(
    *,
    mode: str,
    payload_mb: int,
    group_size: int,
    replicate_id: int,
    public_keys: Sequence[Any],
    work_dir: Path,
    keep_artifacts: bool,
) -> Dict[str, Any]:
    payload_bytes = payload_mb * 1_000_000
    run_id = f"live_{mode.lower()}_{payload_mb}_{group_size}_{replicate_id:03d}"
    run_dir = work_dir / run_id
    store_dir = run_dir / "object_store"
    providers_dir = run_dir / "providers"

    t0 = time.perf_counter()
    payload = _deterministic_payload(payload_bytes, run_id)
    task_key, _nonce, ciphertext, encrypt_ms = _encrypt_payload(payload, run_id)
    t1 = time.perf_counter()
    ciphertext_hash = hashlib.sha256(ciphertext).hexdigest()
    cid = f"sha256-{ciphertext_hash}"
    ciphertext_size = len(ciphertext)
    access_pkg_bytes = 0
    store_egress_bytes = 0
    provider_fetch_ms = ""
    success = True

    try:
        if mode == "RPD":
            # Requester sends one full fresh ciphertext to each selected provider.
            run_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=run_dir, delete=False) as tmp:
                tmp.write(ciphertext)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = Path(tmp.name)
            t2 = ""
            with ThreadPoolExecutor(max_workers=group_size) as pool:
                results = list(
                    pool.map(
                        lambda idx: _fetch_and_verify(
                            tmp_path,
                            providers_dir / f"P{idx}" / f"{cid}.bin",
                            ciphertext_hash,
                        ),
                        range(1, group_size + 1),
                    )
                )
            t5 = time.perf_counter()
            t3 = t5
            t4 = t5
            requester_egress_bytes = ciphertext_size * group_size
            success = all(ok for _copied, ok in results)
            tmp_path.unlink(missing_ok=True)
            notes = "fresh_ciphertext;fresh_content_hash;rpd_parallel_provider_copy"
        else:
            # Requester publishes one fresh ciphertext object. Providers fetch by
            # content-addressed object key, and every fetch verifies the hash.
            store_path = store_dir / f"{cid}.bin"
            _write_bytes(store_path, ciphertext)
            t2 = time.perf_counter()
            access_pkg_bytes = _access_package_bytes(public_keys[:group_size], task_key=task_key, cid=cid, run_id=run_id)
            t3 = time.perf_counter()
            fetch_start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=group_size) as pool:
                results = list(
                    pool.map(
                        lambda idx: _fetch_and_verify(
                            store_path,
                            providers_dir / f"P{idx}" / f"{cid}.bin",
                            ciphertext_hash,
                        ),
                        range(1, group_size + 1),
                    )
                )
            t5 = time.perf_counter()
            t4 = t5
            provider_fetch_ms = (t5 - fetch_start) * 1000.0
            requester_egress_bytes = ciphertext_size + access_pkg_bytes
            store_egress_bytes = ciphertext_size * group_size
            success = all(ok for _copied, ok in results)
            notes = "fresh_ciphertext;fresh_content_hash;ppd_publish_once_real_provider_fetch"

        return {
            "run_id": run_id,
            "mode": mode,
            "payload_mb": payload_mb,
            "group_size": group_size,
            "concurrency": group_size,
            "provider_id": "ALL",
            "replicate_id": replicate_id,
            "content_hash": ciphertext_hash,
            "object_key": cid,
            "t0_start_ms": 0.0,
            "t1_encrypt_done_ms": round((t1 - t0) * 1000.0, 6),
            "t2_publish_done_ms": round((t2 - t0) * 1000.0, 6) if mode == "PPD" else "",
            "t3_access_sent_ms": round((t3 - t0) * 1000.0, 6),
            "t4_first_ready_ms": round((t4 - t0) * 1000.0, 6),
            "t5_all_ready_ms": round((t5 - t0) * 1000.0, 6),
            "encrypt_ms": round(encrypt_ms, 6),
            "requester_egress_mb": round(_mb(requester_egress_bytes), 6),
            "store_egress_mb": round(_mb(store_egress_bytes), 6),
            "provider_fetch_ms": round(provider_fetch_ms, 6) if provider_fetch_ms != "" else "",
            "access_pkg_bytes": int(access_pkg_bytes),
            "success": int(success),
            "notes": notes,
        }
    finally:
        if not keep_artifacts:
            shutil.rmtree(run_dir, ignore_errors=True)


def _summarize(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, int, int], List[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row["mode"]), int(row["payload_mb"]), int(row["group_size"])), []).append(row)

    raw: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for key, items in grouped.items():
        lat = [float(row["t5_all_ready_ms"]) for row in items]
        egress = [float(row["requester_egress_mb"]) for row in items]
        store = [float(row["store_egress_mb"]) for row in items]
        access = [float(row["access_pkg_bytes"]) for row in items]
        mode, payload_mb, group_size = key
        raw[key] = {
            "mode": mode,
            "payload_mb": payload_mb,
            "group_size": group_size,
            "n": len(items),
            "median_ms": round(statistics.median(lat), 6),
            "p95_ms": round(_percentile(lat, 95), 6),
            "mean_ms": round(statistics.mean(lat), 6),
            "requester_egress_mb_mean": round(statistics.mean(egress), 6),
            "requester_egress_mb_p95": round(_percentile(egress, 95), 6),
            "store_egress_mb_mean": round(statistics.mean(store), 6),
            "store_egress_mb_p95": round(_percentile(store, 95), 6),
            "access_pkg_bytes_mean": round(statistics.mean(access), 6),
        }

    summaries: List[Dict[str, Any]] = []
    for key in sorted(raw):
        item = dict(raw[key])
        mode, payload_mb, group_size = key
        rpd = raw[("RPD", payload_mb, group_size)]
        if mode == "RPD":
            item.update({"reduction_vs_rpd_median": 0.0, "reduction_vs_rpd_p95": 0.0, "egress_reduction_vs_rpd": 0.0})
        else:
            item.update(
                {
                    "reduction_vs_rpd_median": round((float(rpd["median_ms"]) - float(item["median_ms"])) / float(rpd["median_ms"]), 6),
                    "reduction_vs_rpd_p95": round((float(rpd["p95_ms"]) - float(item["p95_ms"])) / float(rpd["p95_ms"]), 6),
                    "egress_reduction_vs_rpd": round((float(rpd["requester_egress_mb_mean"]) - float(item["requester_egress_mb_mean"])) / float(rpd["requester_egress_mb_mean"]), 6),
                }
            )
        summaries.append(item)
    return summaries


def _plot(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.8), constrained_layout=True)
    for mode in ["RPD", "PPD"]:
        rows = sorted([row for row in summary if row["mode"] == mode], key=lambda row: int(row["group_size"]))
        x = [int(row["group_size"]) for row in rows]
        axes[0].plot(x, [float(row["median_ms"]) for row in rows], marker="o", label=mode)
        axes[0].fill_between(x, [float(row["median_ms"]) for row in rows], [float(row["p95_ms"]) for row in rows], alpha=0.15)
        axes[1].plot(x, [float(row["requester_egress_mb_mean"]) for row in rows], marker="o", label=mode)
    axes[0].set_title("Live local-store delivery latency")
    axes[0].set_xlabel("Selected group size k")
    axes[0].set_ylabel("All-providers-ready latency (ms)")
    axes[0].grid(True, linewidth=0.3)
    axes[0].legend(fontsize=8)
    axes[1].set_title("Requester egress")
    axes[1].set_xlabel("Selected group size k")
    axes[1].set_ylabel("Requester egress (MB)")
    axes[1].grid(True, linewidth=0.3)
    axes[1].legend(fontsize=8)
    fig.savefig(fig_dir / "fig_delivery_live_store_latency_egress.pdf")
    fig.savefig(fig_dir / "fig_delivery_live_store_latency_egress.png", dpi=180)
    plt.close(fig)


def _audit(rows: Sequence[Mapping[str, Any]], summary: Sequence[Mapping[str, Any]], *, group_sizes: Sequence[int], runs_per_cell: int) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    expected = 2 * len(group_sizes) * runs_per_cell
    if len(rows) != expected:
        issues.append(f"row count {len(rows)} != expected {expected}")
    if len(summary) != 2 * len(group_sizes):
        issues.append("summary row count mismatch")
    seen_hashes = set()
    for row in rows:
        if int(row["success"]) != 1:
            issues.append(f"failed run {row['run_id']}")
        content_hash = str(row["content_hash"])
        if content_hash in seen_hashes:
            issues.append(f"duplicate content hash {content_hash}")
        seen_hashes.add(content_hash)
        if not str(row["object_key"]).startswith("sha256-"):
            issues.append(f"object key is not content hash for {row['run_id']}")
        if "fresh_ciphertext" not in str(row["notes"]):
            issues.append(f"fresh ciphertext note missing in {row['run_id']}")
        if row["mode"] == "PPD" and int(row["access_pkg_bytes"]) <= 0:
            issues.append(f"missing PPD access package bytes for {row['run_id']}")
    for group_size in group_sizes:
        rpd = next(row for row in summary if row["mode"] == "RPD" and int(row["group_size"]) == group_size)
        ppd = next(row for row in summary if row["mode"] == "PPD" and int(row["group_size"]) == group_size)
        if group_size > 1 and float(ppd["requester_egress_mb_mean"]) >= float(rpd["requester_egress_mb_mean"]):
            issues.append(f"PPD requester egress not lower for k={group_size}")
    return not issues, issues


def _write_report(out: Path, summary: Sequence[Mapping[str, Any]], audit_ok: bool, audit_issues: Sequence[str], *, payload_mb: int, group_sizes: Sequence[int], runs_per_cell: int) -> None:
    max_k = max(group_sizes)
    ppd_max = next(row for row in summary if row["mode"] == "PPD" and int(row["group_size"]) == max_k)
    rpd_max = next(row for row in summary if row["mode"] == "RPD" and int(row["group_size"]) == max_k)
    rows = []
    for group_size in group_sizes:
        rpd = next(row for row in summary if row["mode"] == "RPD" and int(row["group_size"]) == group_size)
        ppd = next(row for row in summary if row["mode"] == "PPD" and int(row["group_size"]) == group_size)
        rows.append(
            f"| {group_size} | {float(rpd['median_ms']):.1f} | {float(ppd['median_ms']):.1f} | "
            f"{float(ppd['reduction_vs_rpd_median']):.1%} | {float(rpd['requester_egress_mb_mean']):.1f} | "
            f"{float(ppd['requester_egress_mb_mean']):.3f} | {float(ppd['store_egress_mb_mean']):.1f} | "
            f"{float(ppd['egress_reduction_vs_rpd']):.1%} |"
        )
    report = f"""# Experiment B Live-Store Supplement

## Scope

This supplement upgrades the cache-control part of Experiment B from modeled unique IDs to real fresh ciphertext objects. Every run creates a fresh encrypted payload, derives the object key from the SHA-256 hash of the actual ciphertext, writes a real local object-store file for PPD, and makes providers fetch and hash-verify the object.

This is still a local-store microbenchmark, not a geographically distributed deployment. Its purpose is to close the workbook requirement that each run use fresh payload/object content and avoid cache reuse.

## Matrix

| Dimension | Values |
|---|---|
| Payload size | {payload_mb}MB |
| Group size | {', '.join(str(k) for k in group_sizes)} |
| Modes | RPD, PPD |
| Runs per cell | {runs_per_cell} |
| Total runs | {2 * len(group_sizes) * runs_per_cell} |

## Results

| k | RPD median ms | PPD median ms | Median reduction | RPD requester MB | PPD requester MB | PPD store MB | Requester egress reduction |
|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

At k={max_k}, PPD reduces requester egress by {float(ppd_max['egress_reduction_vs_rpd']):.1%}. The latency result is local-store specific and should not replace the calibrated LAN/WAN latency model; it validates fresh content-hash/object-store semantics.

## Audit

Audit status: **{'PASS' if audit_ok else 'FAIL'}**

{chr(10).join('- ' + issue for issue in audit_issues) if audit_issues else '- Every run has a unique SHA-256 content hash.' + chr(10) + '- PPD object keys are derived from actual ciphertext hashes.' + chr(10) + '- Providers fetch real local-store objects and verify hashes.' + chr(10) + '- RPD and PPD use the same payload size and group sizes.'}
"""
    (out / "ExperimentB_live_store_supplement_report.md").write_text(report, encoding="utf-8")


def run(out: Path, *, payload_mb: int, group_sizes: Sequence[int], runs_per_cell: int, keep_workdir: bool) -> None:
    if out.exists():
        shutil.rmtree(out)
    for sub in ["results", "figures", "metadata", "scripts"]:
        (out / sub).mkdir(parents=True, exist_ok=True)
    work_dir = out / "objects" if keep_workdir else Path(tempfile.mkdtemp(prefix="veriedge_b_live_store_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    public_keys = _provider_public_keys(max(group_sizes))
    rows: List[Dict[str, Any]] = []
    try:
        for mode in ["RPD", "PPD"]:
            for group_size in group_sizes:
                for replicate_id in range(1, runs_per_cell + 1):
                    rows.append(
                        _run_cell(
                            mode=mode,
                            payload_mb=payload_mb,
                            group_size=group_size,
                            replicate_id=replicate_id,
                            public_keys=public_keys,
                            work_dir=work_dir,
                            keep_artifacts=keep_workdir,
                        )
                    )
                    print(f"completed {mode} payload={payload_mb}MB k={group_size} rep={replicate_id}", flush=True)
        summary = _summarize(rows)
        audit_ok, audit_issues = _audit(rows, summary, group_sizes=group_sizes, runs_per_cell=runs_per_cell)
        fields = [
            "run_id", "mode", "payload_mb", "group_size", "concurrency", "provider_id", "replicate_id",
            "content_hash", "object_key", "t0_start_ms", "t1_encrypt_done_ms", "t2_publish_done_ms",
            "t3_access_sent_ms", "t4_first_ready_ms", "t5_all_ready_ms", "encrypt_ms",
            "requester_egress_mb", "store_egress_mb", "provider_fetch_ms", "access_pkg_bytes", "success", "notes",
        ]
        summary_fields = [
            "mode", "payload_mb", "group_size", "n", "median_ms", "p95_ms", "mean_ms",
            "requester_egress_mb_mean", "requester_egress_mb_p95", "store_egress_mb_mean",
            "store_egress_mb_p95", "access_pkg_bytes_mean", "reduction_vs_rpd_median",
            "reduction_vs_rpd_p95", "egress_reduction_vs_rpd",
        ]
        _write_csv(out / "results" / "delivery_live_store_runs.csv", rows, fields)
        _write_csv(out / "results" / "delivery_live_store_summary.csv", summary, summary_fields)
        _plot(summary, out / "figures")
        _write_report(out, summary, audit_ok, audit_issues, payload_mb=payload_mb, group_sizes=group_sizes, runs_per_cell=runs_per_cell)
        metadata = {
            "date": time.strftime("%Y-%m-%d"),
            "git_commit": _git_commit(),
            "payload_mb": payload_mb,
            "group_sizes": list(group_sizes),
            "runs_per_cell": runs_per_cell,
            "scope": "live local object-store fresh-ciphertext supplement",
            "kept_objects": keep_workdir,
        }
        (out / "metadata" / "environment.md").write_text("# Environment\n\n```json\n" + json.dumps(metadata, indent=2) + "\n```\n", encoding="utf-8")
        (out / "scripts" / Path(__file__).name).write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
        if not audit_ok:
            raise SystemExit("audit failed:\n" + "\n".join(audit_issues))
    finally:
        if not keep_workdir and work_dir.exists():
            shutil.rmtree(work_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Experiment B live local-store supplement")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    parser.add_argument("--payload-mb", type=int, default=100)
    parser.add_argument("--group-sizes", default="1,2,4,8")
    parser.add_argument("--runs-per-cell", type=int, default=DEFAULT_RUNS_PER_CELL)
    parser.add_argument("--smoke", action="store_true", help="Use 10MB payload, k=1/2, 2 runs per cell")
    parser.add_argument("--keep-objects", action="store_true", help="Keep generated object/provider files for inspection")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload_mb = args.payload_mb
    group_sizes = [int(x) for x in args.group_sizes.split(",") if x.strip()]
    runs_per_cell = args.runs_per_cell
    if args.smoke:
        payload_mb = 10
        group_sizes = [1, 2]
        runs_per_cell = 2
    out = Path(args.output_root).expanduser().resolve()
    run(out, payload_mb=payload_mb, group_sizes=group_sizes, runs_per_cell=runs_per_cell, keep_workdir=args.keep_objects)
    print(out)
    print(out / "ExperimentB_live_store_supplement_report.md")


if __name__ == "__main__":
    main()
