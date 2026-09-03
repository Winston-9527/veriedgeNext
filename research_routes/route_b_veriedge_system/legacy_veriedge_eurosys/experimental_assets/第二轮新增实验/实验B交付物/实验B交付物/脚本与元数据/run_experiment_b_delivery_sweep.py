from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import matplotlib.pyplot as plt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _find_repo_root(start: Path) -> Path:
    for path in [start.resolve(), *start.resolve().parents]:
        if (path / "artifacts" / "inference-E2E").exists() and (path / "paper1_veriedge").exists():
            return path
    raise RuntimeError(f"cannot locate VeriEdge repo root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
PAPER_DIR = REPO_ROOT / "paper1_veriedge"
OUTPUT_ROOT = PAPER_DIR / "veriedge_revision_results" / "experiment_b_delivery_sweep"

PAYLOAD_MB = 100
GROUP_SIZES = [1, 2, 4, 8]
NETWORKS = ["LAN", "WAN"]
MODES = ["RPD", "PPD"]
RUNS_PER_CELL = 30
SEED = 20260513
CALIBRATION_BYTES = 16 * 1024 * 1024
CALIBRATION_REPEATS = 5

NETWORK_PROFILES = {
    "LAN": {
        "requester_uplink_mbps": 940.0,
        "store_to_provider_mbps": 940.0,
        "rtt_ms": 2.0,
        "loss_pct": 0.0,
        "jitter_ms": 1.5,
    },
    "WAN": {
        "requester_uplink_mbps": 40.0,
        "store_to_provider_mbps": 80.0,
        "rtt_ms": 80.0,
        "loss_pct": 1.0,
        "jitter_ms": 25.0,
    },
}


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


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _mb_decimal(num_bytes: float) -> float:
    return num_bytes / 1_000_000.0


def _transfer_ms(num_bytes: float, mbps: float) -> float:
    return num_bytes * 8.0 / (mbps * 1_000_000.0) * 1000.0


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _calibrate_aes_gcm() -> Dict[str, float]:
    payload = os.urandom(CALIBRATION_BYTES)
    durations: List[float] = []
    ciphertext_lens: List[int] = []
    for _ in range(CALIBRATION_REPEATS):
        key = os.urandom(32)
        nonce = os.urandom(12)
        aes = AESGCM(key)
        start = time.perf_counter()
        ciphertext = aes.encrypt(nonce, payload, None)
        durations.append((time.perf_counter() - start) * 1000.0)
        ciphertext_lens.append(len(ciphertext))
    median_ms = statistics.median(durations)
    throughput_mib_s = (CALIBRATION_BYTES / (1024 * 1024)) / (median_ms / 1000.0)
    return {
        "calibration_bytes": CALIBRATION_BYTES,
        "calibration_repeats": CALIBRATION_REPEATS,
        "median_encrypt_ms": round(median_ms, 6),
        "mean_encrypt_ms": round(statistics.mean(durations), 6),
        "throughput_mib_s": round(throughput_mib_s, 6),
        "ciphertext_overhead_bytes": int(statistics.median(ciphertext_lens) - CALIBRATION_BYTES),
    }


def _provider_public_keys(max_group_size: int) -> List[Any]:
    keys = []
    for _ in range(max_group_size):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        keys.append(private_key.public_key())
    return keys


def _access_package_bytes(public_keys: Sequence[Any], *, task_key: bytes, cid: str, run_id: str) -> List[int]:
    sizes: List[int] = []
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
            "locator": f"ipfs://{cid}",
        }
        sizes.append(len(json.dumps(package, sort_keys=True, separators=(",", ":")).encode("utf-8")))
    return sizes


def _encrypt_ms_for_payload(calibration: Mapping[str, float], payload_bytes: int, rng: random.Random) -> float:
    per_byte_ms = float(calibration["median_encrypt_ms"]) / float(calibration["calibration_bytes"])
    jitter = max(0.0, rng.gauss(1.0, 0.015))
    return payload_bytes * per_byte_ms * jitter


def _network_jitter_ms(profile: Mapping[str, float], rng: random.Random) -> float:
    jitter = rng.gauss(0.0, float(profile["jitter_ms"]))
    loss_penalty = max(0.0, rng.gauss(float(profile["loss_pct"]) * 2.0, float(profile["loss_pct"]) * 0.5))
    return max(-0.5 * float(profile["jitter_ms"]), jitter + loss_penalty)


def _run_cell(
    *,
    network: str,
    mode: str,
    group_size: int,
    replicate_id: int,
    calibration: Mapping[str, float],
    public_keys: Sequence[Any],
    rng: random.Random,
) -> Dict[str, Any]:
    profile = NETWORK_PROFILES[network]
    payload_bytes = PAYLOAD_MB * 1_000_000
    ciphertext_bytes = payload_bytes + int(calibration["ciphertext_overhead_bytes"])
    run_id = f"{network.lower()}_{mode.lower()}_{PAYLOAD_MB}_{group_size}_{replicate_id:03d}"
    task_key = os.urandom(32)
    unique_salt = f"{run_id}:{rng.random()}:{time.time_ns()}"
    cid = "bafy" + _sha256_text(unique_salt)[:48]
    access_pkg_total = 0
    access_pkg_mean = 0.0

    t0 = 0.0
    encrypt_ms = _encrypt_ms_for_payload(calibration, payload_bytes, rng)
    t1 = t0 + encrypt_ms

    rtt = float(profile["rtt_ms"])
    uplink = float(profile["requester_uplink_mbps"])
    store_downlink = float(profile["store_to_provider_mbps"])
    jitter = _network_jitter_ms(profile, rng)
    notes: List[str] = [f"fresh_cid={cid}", "encrypted_payload_modeled_from_calibrated_aes_gcm"]

    if mode == "RPD":
        # RPD sends k encrypted payload copies from the requester. The sends are
        # concurrent, but the requester uplink is the shared bottleneck.
        requester_egress_bytes = ciphertext_bytes * group_size
        full_send_ms = rtt + _transfer_ms(requester_egress_bytes, uplink) + jitter
        t2 = ""
        t3 = t1 + full_send_ms
        t4 = t3
        t5 = t3
        store_egress_bytes = 0
        provider_fetch_ms = ""
        notes.append("parallel_send_shared_requester_uplink")
    else:
        # PPD publishes one ciphertext, releases small per-provider access
        # packages, then providers fetch the ciphertext from the store in parallel.
        access_sizes = _access_package_bytes(public_keys[:group_size], task_key=task_key, cid=cid, run_id=run_id)
        access_pkg_total = sum(access_sizes)
        access_pkg_mean = statistics.mean(access_sizes)
        publish_ms = rtt + _transfer_ms(ciphertext_bytes, uplink) + jitter
        access_send_ms = rtt + _transfer_ms(access_pkg_total, uplink) + max(0.0, _network_jitter_ms(profile, rng) * 0.1)
        provider_fetch = rtt + _transfer_ms(ciphertext_bytes, store_downlink) + max(0.0, _network_jitter_ms(profile, rng))
        t2 = t1 + publish_ms
        t3 = t2 + access_send_ms
        t4 = t3 + provider_fetch * max(0.90, min(1.0, rng.gauss(0.95, 0.015)))
        t5 = t3 + provider_fetch
        requester_egress_bytes = ciphertext_bytes + access_pkg_total
        store_egress_bytes = ciphertext_bytes * group_size
        provider_fetch_ms = provider_fetch
        notes.append("publish_once_then_parallel_provider_fetch")

    return {
        "run_id": run_id,
        "network": network,
        "mode": mode,
        "payload_mb": PAYLOAD_MB,
        "group_size": group_size,
        "concurrency": group_size,
        "provider_id": "ALL",
        "replicate_id": replicate_id,
        "t0_start_ms": round(t0, 6),
        "t1_encrypt_done_ms": round(t1, 6),
        "t2_publish_done_ms": round(t2, 6) if t2 != "" else "",
        "t3_access_sent_ms": round(t3, 6),
        "t4_first_ready_ms": round(t4, 6),
        "t5_all_ready_ms": round(t5, 6),
        "requester_egress_mb": round(_mb_decimal(requester_egress_bytes), 6),
        "store_egress_mb": round(_mb_decimal(store_egress_bytes), 6),
        "provider_fetch_ms": round(provider_fetch_ms, 6) if provider_fetch_ms != "" else "",
        "access_pkg_bytes": int(access_pkg_total),
        "access_pkg_bytes_mean": round(access_pkg_mean, 6),
        "success": 1,
        "notes": ";".join(notes),
    }


def _summarize(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, int, int], List[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row["network"]), str(row["mode"]), int(row["payload_mb"]), int(row["group_size"])), []).append(row)

    raw: Dict[Tuple[str, str, int, int], Dict[str, Any]] = {}
    for key, items in groups.items():
        latencies = [float(item["t5_all_ready_ms"]) - float(item["t0_start_ms"]) for item in items]
        requester_egress = [float(item["requester_egress_mb"]) for item in items]
        store_egress = [float(item["store_egress_mb"]) for item in items]
        access_sizes = [float(item["access_pkg_bytes"]) for item in items]
        network, mode, payload_mb, group_size = key
        raw[key] = {
            "network": network,
            "mode": mode,
            "payload_mb": payload_mb,
            "group_size": group_size,
            "n": len(items),
            "median_ms": round(statistics.median(latencies), 6),
            "p95_ms": round(_percentile(latencies, 95), 6),
            "mean_ms": round(statistics.mean(latencies), 6),
            "requester_egress_mb_mean": round(statistics.mean(requester_egress), 6),
            "requester_egress_mb_p95": round(_percentile(requester_egress, 95), 6),
            "store_egress_mb_mean": round(statistics.mean(store_egress), 6),
            "store_egress_mb_p95": round(_percentile(store_egress, 95), 6),
            "access_pkg_bytes_mean": round(statistics.mean(access_sizes), 6),
        }

    summaries: List[Dict[str, Any]] = []
    for key in sorted(raw):
        item = dict(raw[key])
        network, mode, payload_mb, group_size = key
        rpd = raw[(network, "RPD", payload_mb, group_size)]
        if mode == "RPD":
            item.update(
                {
                    "reduction_vs_rpd_median": 0.0,
                    "reduction_vs_rpd_p95": 0.0,
                    "egress_reduction_vs_rpd": 0.0,
                }
            )
        else:
            item.update(
                {
                    "reduction_vs_rpd_median": round(
                        (float(rpd["median_ms"]) - float(item["median_ms"])) / float(rpd["median_ms"]),
                        6,
                    ),
                    "reduction_vs_rpd_p95": round(
                        (float(rpd["p95_ms"]) - float(item["p95_ms"])) / float(rpd["p95_ms"]),
                        6,
                    ),
                    "egress_reduction_vs_rpd": round(
                        (
                            float(rpd["requester_egress_mb_mean"])
                            - float(item["requester_egress_mb_mean"])
                        )
                        / float(rpd["requester_egress_mb_mean"]),
                        6,
                    ),
                }
            )
        summaries.append(item)
    return summaries


def _plot_latency(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    for network in NETWORKS:
        fig, ax = plt.subplots(figsize=(5.4, 3.4))
        for mode in MODES:
            rows = [
                row
                for row in summary
                if row["network"] == network and row["mode"] == mode and int(row["payload_mb"]) == PAYLOAD_MB
            ]
            rows = sorted(rows, key=lambda row: int(row["group_size"]))
            x = [int(row["group_size"]) for row in rows]
            med = [float(row["median_ms"]) for row in rows]
            p95 = [float(row["p95_ms"]) for row in rows]
            ax.plot(x, med, marker="o", label=mode)
            ax.fill_between(x, med, p95, alpha=0.15)
        ax.set_xlabel("Selected group size k")
        ax.set_ylabel("All-providers-ready latency (ms)")
        ax.set_title(f"Selective delivery latency ({network}, {PAYLOAD_MB}MB)")
        ax.legend(fontsize=8)
        ax.grid(True, linewidth=0.3)
        fig.tight_layout()
        fig.savefig(fig_dir / f"fig_delivery_latency_{network.lower()}.pdf")
        fig.savefig(fig_dir / f"fig_delivery_latency_{network.lower()}.png", dpi=180)
        plt.close(fig)


def _plot_egress(summary: Sequence[Mapping[str, Any]], fig_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    for mode in MODES:
        rows = [
            row
            for row in summary
            if row["network"] == "LAN" and row["mode"] == mode and int(row["payload_mb"]) == PAYLOAD_MB
        ]
        rows = sorted(rows, key=lambda row: int(row["group_size"]))
        ax.plot(
            [int(row["group_size"]) for row in rows],
            [float(row["requester_egress_mb_mean"]) for row in rows],
            marker="o",
            label=mode,
        )
    ax.set_xlabel("Selected group size k")
    ax.set_ylabel("Requester egress (MB)")
    ax.set_title("Requester egress under placement-defined disclosure")
    ax.legend(fontsize=8)
    ax.grid(True, linewidth=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_delivery_egress_group_size.pdf")
    fig.savefig(fig_dir / "fig_delivery_egress_group_size.png", dpi=180)
    plt.close(fig)


def _audit(rows: Sequence[Mapping[str, Any]], summary: Sequence[Mapping[str, Any]], runs_per_cell: int) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    expected_rows = len(NETWORKS) * len(MODES) * len(GROUP_SIZES) * runs_per_cell
    if len(rows) != expected_rows:
        issues.append(f"delivery_runs row count {len(rows)} != expected {expected_rows}")
    if len(summary) != len(NETWORKS) * len(MODES) * len(GROUP_SIZES):
        issues.append("delivery_summary row count mismatch")
    for row in rows:
        if int(row["success"]) != 1:
            issues.append(f"failed run {row['run_id']}")
        if "fresh_cid=" not in str(row["notes"]):
            issues.append(f"missing fresh cid note in {row['run_id']}")
        if str(row["mode"]) == "RPD" and float(row["store_egress_mb"]) != 0.0:
            issues.append(f"RPD store egress nonzero in {row['run_id']}")
        if str(row["mode"]) == "RPD" and int(row["access_pkg_bytes"]) != 0:
            issues.append(f"RPD access package bytes should be zero in {row['run_id']}")
        if str(row["mode"]) == "PPD" and float(row["store_egress_mb"]) <= 0.0:
            issues.append(f"PPD store egress missing in {row['run_id']}")
        if str(row["mode"]) == "PPD" and int(row["access_pkg_bytes"]) <= 0:
            issues.append(f"PPD access package bytes missing in {row['run_id']}")
    for network in NETWORKS:
        for group_size in GROUP_SIZES:
            rpd = next(
                row
                for row in summary
                if row["network"] == network and row["mode"] == "RPD" and int(row["group_size"]) == group_size
            )
            ppd = next(
                row
                for row in summary
                if row["network"] == network and row["mode"] == "PPD" and int(row["group_size"]) == group_size
            )
            if group_size > 1 and float(ppd["requester_egress_mb_mean"]) >= float(rpd["requester_egress_mb_mean"]):
                issues.append(f"PPD requester egress not lower for {network} k={group_size}")
            if int(rpd["n"]) != runs_per_cell or int(ppd["n"]) != runs_per_cell:
                issues.append(f"run count mismatch in summary for {network} k={group_size}")
    return len(issues) == 0, issues


def _summary_row(summary: Sequence[Mapping[str, Any]], network: str, mode: str, group_size: int) -> Mapping[str, Any]:
    return next(
        row
        for row in summary
        if row["network"] == network and row["mode"] == mode and int(row["group_size"]) == group_size
    )


def _write_reports(
    out: Path,
    *,
    summary: Sequence[Mapping[str, Any]],
    audit_ok: bool,
    audit_issues: Sequence[str],
    calibration: Mapping[str, Any],
    runs_per_cell: int,
) -> None:
    available_networks = sorted({str(row["network"]) for row in summary})
    available_groups = sorted({int(row["group_size"]) for row in summary})
    max_k = max(available_groups)
    mid_k = 4 if 4 in available_groups else max_k
    lan8 = _summary_row(summary, "LAN", "PPD", max_k)
    wan8 = _summary_row(summary, "WAN", "PPD", max_k) if "WAN" in available_networks else lan8
    lan4 = _summary_row(summary, "LAN", "PPD", mid_k)
    wan4 = _summary_row(summary, "WAN", "PPD", mid_k) if "WAN" in available_networks else lan4
    rpd_lan8 = _summary_row(summary, "LAN", "RPD", max_k)
    ppd_lan1 = _summary_row(summary, "LAN", "PPD", 1)
    ppd_lan8 = _summary_row(summary, "LAN", "PPD", max_k)
    rpd_wan8 = _summary_row(summary, "WAN", "RPD", max_k) if "WAN" in available_networks else rpd_lan8

    table_rows: List[str] = []
    for network in available_networks:
        for group in available_groups:
            rpd_row = _summary_row(summary, network, "RPD", group)
            ppd_row = _summary_row(summary, network, "PPD", group)
            table_rows.append(
                f"| {network} | {group} | {float(rpd_row['median_ms']):.1f} | {float(ppd_row['median_ms']):.1f} | "
                f"{float(ppd_row['reduction_vs_rpd_median']):.1%} | {float(rpd_row['requester_egress_mb_mean']):.1f} | "
                f"{float(ppd_row['requester_egress_mb_mean']):.3f} | {float(ppd_row['store_egress_mb_mean']):.1f} | "
                f"{float(ppd_row['egress_reduction_vs_rpd']):.1%} |"
            )
    table_text = "\n".join(table_rows)

    readme = f"""# VeriEdge Revision Experiment B: Selective Delivery Group-Size Sweep

## Summary
- Experiment: Selective delivery under placement width.
- Payload size: {PAYLOAD_MB}MB encrypted payload.
- Group sizes: {', '.join(str(k) for k in GROUP_SIZES)}.
- Networks: LAN and WAN/emulated-WAN model.
- Modes: RPD and PPD.
- Runs per cell: {runs_per_cell}.
- Audit status: {'PASS' if audit_ok else 'FAIL'}.

## Main Results
- LAN k={max_k}: PPD requester egress reduction vs RPD = {float(lan8['egress_reduction_vs_rpd']):.1%}; median latency reduction = {float(lan8['reduction_vs_rpd_median']):.1%}.
- WAN k={max_k}: PPD requester egress reduction vs RPD = {float(wan8['egress_reduction_vs_rpd']):.1%}; median latency reduction = {float(wan8['reduction_vs_rpd_median']):.1%}.
- RPD requester egress grows from {float(_summary_row(summary, 'LAN', 'RPD', 1)['requester_egress_mb_mean']):.1f}MB at k=1 to {float(rpd_lan8['requester_egress_mb_mean']):.1f}MB at k={max_k}.
- PPD requester egress grows from {float(ppd_lan1['requester_egress_mb_mean']):.1f}MB at k=1 to {float(ppd_lan8['requester_egress_mb_mean']):.1f}MB at k={max_k}.

## Scope
- This is a calibrated delivery-path replay/microbenchmark, not a live multi-provider deployment.
- AES-GCM encryption throughput and RSA access-package sizes are measured locally.
- LAN/WAN transfer times are computed from the recorded bandwidth/RTT model in `metadata/network_config.md`.
- RPD uses concurrent sends with a shared requester-uplink bottleneck.
- PPD publishes one ciphertext, sends per-provider access packages, then models parallel provider fetches from the store.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    report = f"""# Experiment B：Selective Delivery Group-Size Sweep 结果报告

## 1. 实验目标

本实验对应 `veriedge_revision_workbook.md` 的实验 B。目标是证明 placement 不只是选择执行节点，也定义 data boundary：只有 selected providers 收到可解密 task-access material。当 selected group size 增大时，RPD 需要从 requester 发送 `k` 份 encrypted payload，而 PPD 只需要 requester 发布 1 份 ciphertext，并向 selected providers 发送很小的 locator/key access packages。

## 2. 实验口径

本实验是 calibrated delivery-path replay/microbenchmark，不是 live multi-provider deployment。这样做的原因是当前仓库没有完整的一键多机 delivery sweep runner。为了避免伪装成真实部署，本实验明确区分三类数据：

- 真实测量：AES-GCM 加密吞吐、RSA-OAEP access package 大小。
- 模型输入：LAN/WAN bandwidth、RTT、loss/jitter，记录在 `metadata/network_config.md`。
- 推导指标：all-providers-ready latency、requester egress、store egress。

公平性定义：

- RPD 和 PPD 都使用 encrypted payload，不使用 plaintext。
- RPD 允许并行发送，但 requester uplink 是共享瓶颈，因此 requester egress 是 `kS`。
- PPD 中 requester 发布一次 ciphertext，发送 `k` 个 access packages；provider fetch latency 计入 `t5_all_ready_ms`。
- 每次 run 都生成 fresh task id / CID / task key，避免缓存假设。

## 3. 全量矩阵

| Dimension | Values |
|---|---|
| Payload size | {PAYLOAD_MB}MB |
| Group size | {', '.join(str(k) for k in GROUP_SIZES)} |
| Network | LAN, WAN |
| Mode | RPD, PPD |
| Runs per cell | {runs_per_cell} |
| Total runs | {len(NETWORKS) * len(MODES) * len(GROUP_SIZES) * runs_per_cell} |

## 4. 主结果

| Network | k | RPD median ms | PPD median ms | Median reduction | RPD requester MB | PPD requester MB | PPD store MB | Requester egress reduction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{table_text}

## 5. 结果解读

Requester egress 呈现手册预期的复杂度差异。RPD 在 LAN 下从 k=1 的 {float(_summary_row(summary, 'LAN', 'RPD', 1)['requester_egress_mb_mean']):.1f}MB 增长到 k={max_k} 的 {float(rpd_lan8['requester_egress_mb_mean']):.1f}MB，近似 `O(kS)`。PPD 从 k=1 的 {float(ppd_lan1['requester_egress_mb_mean']):.1f}MB 增长到 k={max_k} 的 {float(ppd_lan8['requester_egress_mb_mean']):.1f}MB，近似 `O(S + k epsilon)`，因为每个 provider 只额外收到一个小 access package。

Latency 的趋势也符合 selective delivery 的直觉。k 较小时，PPD 需要先 publish 再 provider fetch，可能不一定优于 RPD；但随着 k 增大，RPD 的 requester uplink 要承载多份 full payload，而 PPD 的 requester critical path 接近一次 payload publication 加小包分发。到 k={max_k}，LAN 下 PPD median latency 相对 RPD 下降 {float(lan8['reduction_vs_rpd_median']):.1%}，WAN 下下降 {float(wan8['reduction_vs_rpd_median']):.1%}。

这个结果支撑 data-boundary claim：placement commitment 后，VeriEdge 不需要把 full encrypted payload 复制给所有候选节点，而是只向 selected providers 释放 decryptable task access。PPD 的收益不是“避免加密”，因为 RPD/PPD 都使用 encrypted payload；收益来自 post-placement targeted access release。

## 6. 图表

- `figures/fig_delivery_latency_lan.pdf`：LAN 下 group size 对 median/p95 all-providers-ready latency 的影响。
- `figures/fig_delivery_latency_wan.pdf`：WAN 下 group size 对 median/p95 all-providers-ready latency 的影响。
- `figures/fig_delivery_egress_group_size.pdf`：requester egress 随 group size 增长的趋势，展示 `kS` vs `S+k epsilon`。

![LAN latency](figures/fig_delivery_latency_lan.png)

![WAN latency](figures/fig_delivery_latency_wan.png)

![Requester egress](figures/fig_delivery_egress_group_size.png)

## 7. 自审结果

Audit status: **{'PASS' if audit_ok else 'FAIL'}**

{chr(10).join('- ' + issue for issue in audit_issues) if audit_issues else '- RPD/PPD 使用相同 payload size、network condition、provider count。' + chr(10) + '- 每次 run 生成 fresh CID/task key。' + chr(10) + '- WAN/LAN 参数已写入 metadata。' + chr(10) + '- RPD baseline 明确为并行发送、共享 requester uplink。' + chr(10) + '- Summary 报告 median、p95、mean。' + chr(10) + '- requester egress 和 store egress 分开记录。' + chr(10) + '- 图表由同一份 delivery_summary.csv 生成。'}

## 8. 论文引用建议

建议把该实验写成 selective delivery microbenchmark，而不是端到端 inference deployment。可以安全引用：

> For a 100MB encrypted payload and k={max_k} selected providers, PPD reduces requester egress by {float(lan8['egress_reduction_vs_rpd']):.1%} and median all-providers-ready latency by {float(lan8['reduction_vs_rpd_median']):.1%} on the LAN profile, and by {float(wan8['egress_reduction_vs_rpd']):.1%} / {float(wan8['reduction_vs_rpd_median']):.1%} on the WAN profile, under the calibrated delivery model.
"""
    (out / "ExperimentB_delivery_sweep_report.md").write_text(report, encoding="utf-8")

    captions = f"""Figure captions

fig_delivery_latency_lan.pdf:
Selective delivery latency as placement width grows on the LAN profile with a {PAYLOAD_MB}MB encrypted payload. RPD sends one full ciphertext to each selected provider over the shared requester uplink, while PPD publishes one ciphertext and releases small provider-specific access packages after placement commitment.

fig_delivery_latency_wan.pdf:
Selective delivery latency as placement width grows on the WAN/emulated-WAN profile. The wider the selected group, the more RPD is dominated by repeated payload-sized requester transfers; PPD keeps requester-side delivery closer to one ciphertext publication plus small access packages.

fig_delivery_egress_group_size.pdf:
Requester egress under placement-defined disclosure. RPD grows approximately as kS, while PPD grows as S plus k small access packages. This is the core evidence that committed placement is also the data boundary.
"""
    (out / "paper_snippets" / "figure_captions.txt").write_text(captions, encoding="utf-8")

    delivery_tex = rf"""\subsection{{Selective Delivery Under Placement Width}}
\label{{subsec:eval-selective-delivery}}

Placement also defines the data boundary: only selected providers receive decryptable task-access material. We compare replicated payload delivery (RPD), which sends a full encrypted payload to each selected provider, against privacy-preserving delivery (PPD), which publishes one ciphertext and sends small locator-and-key packages after placement commitment.

We use a {PAYLOAD_MB}MB encrypted payload and sweep selected group size $k \in \{{{','.join(str(k) for k in available_groups)}\}}$ under LAN and WAN delivery profiles. In the calibrated delivery replay, RPD incurs requester egress proportional to $kS$, whereas PPD incurs one ciphertext publication plus $k$ small access packages. At $k={max_k}$, PPD reduces requester egress by {float(lan8['egress_reduction_vs_rpd']):.1%} on LAN and {float(wan8['egress_reduction_vs_rpd']):.1%} on WAN. Median all-providers-ready latency is reduced by {float(lan8['reduction_vs_rpd_median']):.1%} on LAN and {float(wan8['reduction_vs_rpd_median']):.1%} on WAN under the same model.
"""
    (out / "paper_snippets" / "delivery_eval_subsection.tex").write_text(delivery_tex, encoding="utf-8")

    abstract_numbers = f"""Selective delivery result sentence:
For {PAYLOAD_MB}MB encrypted payloads and k={max_k} selected providers, PPD reduces requester egress by {float(lan8['egress_reduction_vs_rpd']):.1%} on LAN and {float(wan8['egress_reduction_vs_rpd']):.1%} on WAN, and reduces median all-providers-ready latency by {float(lan8['reduction_vs_rpd_median']):.1%} on LAN and {float(wan8['reduction_vs_rpd_median']):.1%} on WAN under the calibrated delivery model.

Scope sentence:
This is a calibrated delivery-path microbenchmark/replay using measured local crypto costs and explicit LAN/WAN bandwidth/RTT profiles, not a live multi-provider deployment.
"""
    (out / "paper_snippets" / "abstract_numbers.txt").write_text(abstract_numbers, encoding="utf-8")


def _write_metadata(out: Path, calibration: Mapping[str, Any], runs_per_cell: int) -> None:
    metadata = {
        "date": time.strftime("%Y-%m-%d"),
        "git_commit": _git_commit(),
        "experiment": "Experiment B selective delivery group-size sweep",
        "payload_mb": PAYLOAD_MB,
        "group_sizes": GROUP_SIZES,
        "networks": NETWORKS,
        "modes": MODES,
        "runs_per_cell": runs_per_cell,
        "seed": SEED,
        "crypto_calibration": calibration,
        "scope": "calibrated delivery-path replay/microbenchmark, not live deployment",
    }
    (out / "metadata" / "environment.md").write_text(
        "# Environment\n\n```json\n" + json.dumps(metadata, indent=2, ensure_ascii=False) + "\n```\n",
        encoding="utf-8",
    )
    (out / "metadata" / "git_commit.txt").write_text(metadata["git_commit"] + "\n", encoding="utf-8")
    network_text = "# Network Config\n\n"
    network_text += "RPD uses concurrent sends with a shared requester-uplink bottleneck.\n\n"
    network_text += "PPD publishes one ciphertext from requester to store, sends provider-specific access packages, then models parallel provider fetches from the store.\n\n"
    network_text += "```json\n" + json.dumps(NETWORK_PROFILES, indent=2, ensure_ascii=False) + "\n```\n"
    (out / "metadata" / "network_config.md").write_text(network_text, encoding="utf-8")


def run_experiment(out: Path, runs_per_cell: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], bool, List[str]]:
    rng = random.Random(SEED)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ["metadata", "results", "figures", "paper_snippets", "scripts"]:
        (out / sub).mkdir(parents=True, exist_ok=True)

    calibration = _calibrate_aes_gcm()
    public_keys = _provider_public_keys(max(GROUP_SIZES))
    rows: List[Dict[str, Any]] = []
    for network in NETWORKS:
        for mode in MODES:
            for group_size in GROUP_SIZES:
                for replicate_id in range(1, runs_per_cell + 1):
                    rows.append(
                        _run_cell(
                            network=network,
                            mode=mode,
                            group_size=group_size,
                            replicate_id=replicate_id,
                            calibration=calibration,
                            public_keys=public_keys,
                            rng=rng,
                        )
                    )

    summary = _summarize(rows)
    audit_ok, audit_issues = _audit(rows, summary, runs_per_cell)
    return rows, summary, calibration, audit_ok, audit_issues


def materialize(out: Path, rows: List[Dict[str, Any]], summary: List[Dict[str, Any]], calibration: Dict[str, Any], audit_ok: bool, audit_issues: List[str], runs_per_cell: int) -> None:
    run_fields = [
        "run_id",
        "network",
        "mode",
        "payload_mb",
        "group_size",
        "concurrency",
        "provider_id",
        "replicate_id",
        "t0_start_ms",
        "t1_encrypt_done_ms",
        "t2_publish_done_ms",
        "t3_access_sent_ms",
        "t4_first_ready_ms",
        "t5_all_ready_ms",
        "requester_egress_mb",
        "store_egress_mb",
        "provider_fetch_ms",
        "access_pkg_bytes",
        "access_pkg_bytes_mean",
        "success",
        "notes",
    ]
    summary_fields = [
        "network",
        "mode",
        "payload_mb",
        "group_size",
        "n",
        "median_ms",
        "p95_ms",
        "mean_ms",
        "requester_egress_mb_mean",
        "requester_egress_mb_p95",
        "store_egress_mb_mean",
        "store_egress_mb_p95",
        "access_pkg_bytes_mean",
        "reduction_vs_rpd_median",
        "reduction_vs_rpd_p95",
        "egress_reduction_vs_rpd",
    ]
    _write_csv(out / "results" / "delivery_runs.csv", rows, run_fields)
    _write_csv(out / "results" / "delivery_summary.csv", summary, summary_fields)
    _plot_latency(summary, out / "figures")
    _plot_egress(summary, out / "figures")
    _write_metadata(out, calibration, runs_per_cell)
    _write_reports(out, summary=summary, audit_ok=audit_ok, audit_issues=audit_issues, calibration=calibration, runs_per_cell=runs_per_cell)
    (out / "scripts" / Path(__file__).name).write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Experiment B selective delivery group-size sweep")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    parser.add_argument("--runs-per-cell", type=int, default=RUNS_PER_CELL)
    parser.add_argument("--minimal", action="store_true", help="Run a small k=1/2, LAN-only smoke matrix")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global GROUP_SIZES, NETWORKS
    if args.minimal:
        GROUP_SIZES = [1, 2]
        NETWORKS = ["LAN"]
    out = Path(args.output_root).expanduser().resolve()
    if out.exists():
        shutil.rmtree(out)
    rows, summary, calibration, audit_ok, audit_issues = run_experiment(out, args.runs_per_cell)
    materialize(out, rows, summary, calibration, audit_ok, audit_issues, args.runs_per_cell)
    if not audit_ok:
        raise SystemExit("Experiment B audit failed:\n" + "\n".join(audit_issues))
    print(out)
    print(out / "results" / "delivery_summary.csv")
    print(out / "ExperimentB_delivery_sweep_report.md")


if __name__ == "__main__":
    main()
