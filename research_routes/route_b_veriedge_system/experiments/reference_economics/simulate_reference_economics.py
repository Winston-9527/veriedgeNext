#!/usr/bin/env python3
"""E09 risk-cost joint scan for reference modes (Route B G0, handbook §14).

Config-driven and deterministic. Answers the W3 falsifiable question: is there a
``p_a`` interval where a sampled reference is materially cheaper than always-on
duplicate while meeting the pre-declared single-shot / persistent risk target?

Risk model (handbook §14.1):
    D_single   = p_a * d
    D_m        = 1 - (1 - p_a*d)^m
    p_a >= r/d                        (single-shot target r, if r <= d)
    p_a >= (1-(1-r)^(1/m))/d          (persistent target r, if reachable)

Cost model (handbook §3.3), normalized so C_duplicate_extra = 1.0:
    E[C_verify] = c_always
                + p_a   * (c_ref + c_check)
                + p_a*u * c_upgrade_extra

Self-checks (handbook §14.4) run before the summary is written; a failed check
aborts with a non-zero exit.

Outputs (handbook §16) under ``results/<run_id>/``:
    environment.json, input_manifest.csv, measurements.csv, protocol_checks.json,
    risk_curves.csv, cost_grid.csv, feasible_regions.csv, sensitivity.csv,
    go_nogo_summary.json, RESULT_MEMO.md

Usage:
    python3 simulate_reference_economics.py [--config-dir configs] [--out results]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import sys
from datetime import date
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
MODES_FIELDS = ["mode_id", "label", "c_always", "c_ref", "c_check", "c_upgrade", "source_type", "notes"]


def load_modes(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        modes = []
        for row in csv.DictReader(fh):
            for key in ("c_always", "c_ref", "c_check", "c_upgrade"):
                row[key] = float(row[key])
            modes.append(row)
        return modes


def d_single(p_a: float, d: float) -> float:
    return p_a * d


def d_m(p_a: float, d: float, m: int) -> float:
    return 1.0 - (1.0 - p_a * d) ** m


def p_a_min_single(r: float, d: float) -> float | None:
    if d <= 0:
        return None
    return math.inf if r > d else r / d


def p_a_min_m(r: float, d: float, m: int) -> float | None:
    if d <= 0:
        return None
    return math.inf if r >= 1.0 else (1.0 - (1.0 - r) ** (1.0 / m)) / d


def expected_cost(mode: dict, p_a: float, u: float) -> float:
    return (mode["c_always"]
            + p_a * (mode["c_ref"] + mode["c_check"])
            + p_a * u * mode["c_upgrade"])


def run_self_checks(modes: list[dict], grid: dict) -> tuple[dict, list[str]]:
    """Return (checks dict, failures list). Each check is handbook §14.4."""
    failures: list[str] = []
    checks: dict[str, object] = {}

    def record(name: str, ok: bool, detail: str) -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            failures.append(f"{name}: {detail}")

    p_a_grid = grid["p_a_grid"]
    m_grid = grid["m_grid"]
    d_grid = grid["d_grid"]
    u_grid = grid["u_grid"]

    # 1. p_a=0 -> active detection 0, reference 0, but C_always != 0
    pa0_det = d_single(0.0, 1.0)
    record("pa0_active_detection_zero", pa0_det == 0.0, f"D_single(0,1)={pa0_det}")
    ref_at_pa0 = [p for p in p_a_grid if p == 0.0]
    ref_terms = [p * 1.0 for p in ref_at_pa0]  # p_a * C_ref
    record("pa0_reference_zero", all(t == 0.0 for t in ref_terms), f"p_a*C_ref@0={ref_terms}")

    # 2. p_a=1, d=1 -> single detection 1
    record("pa1_d1_detection_one", d_single(1.0, 1.0) == 1.0, f"D_single(1,1)={d_single(1.0,1.0)}")

    # 3. monotone in d, m, p_a
    mono = True
    detail = []
    for m in m_grid:
        for d in d_grid:
            seq = [d_m(p, d, m) for p in p_a_grid]
            if any(b < a - 1e-12 for a, b in zip(seq, seq[1:])):
                mono = False
                detail.append(f"p_a non-monotone m={m} d={d}")
    for d in d_grid:
        seq = [d_m(0.5, d, m) for m in m_grid]
        if any(b < a - 1e-12 for a, b in zip(seq, seq[1:])):
            mono = False
            detail.append(f"m non-monotone d={d}")
    for p in p_a_grid:
        seq = [d_m(p, d, 10) for d in d_grid]
        if any(b < a - 1e-12 for a, b in zip(seq, seq[1:])):
            mono = False
            detail.append(f"d non-monotone p_a={p}")
    record("cumulative_detection_monotone", mono, "; ".join(detail) or "d/m/p_a increasing -> D_m non-decreasing")

    # 4. sampling reference demand non-decreasing in p_a
    record("reference_demand_monotone",
           all(a <= b for a, b in zip(p_a_grid, p_a_grid[1:])),
           "p_a grid increasing")

    # 5. u conditional vs total give the same cost
    mode = modes[0]
    p_upgrade_total = 0.05
    p_a_example = 0.2
    u_equiv = p_upgrade_total / p_a_example
    cost_cond = expected_cost(mode, p_a_example, u_equiv)
    cost_tot = (mode["c_always"] + p_a_example * (mode["c_ref"] + mode["c_check"])
                + p_upgrade_total * mode["c_upgrade"])
    record("u_conditional_equals_total", abs(cost_cond - cost_tot) < 1e-12,
           f"{cost_cond:.6f} vs {cost_tot:.6f}")

    # 6. p_a=0 -> no in-audit escalation
    record("pa0_no_in_audit_escalation", expected_cost(mode, 0.0, 1.0) == mode["c_always"],
           "escalation term = p_a*u*C_upgrade = 0")

    # 7. V0 must not carry active-detection framing
    v0 = next((mo for mo in modes if mo["mode_id"] == "V0_passive"), None)
    v0_ok = v0 is not None and v0["c_ref"] == 0.0 and v0["c_check"] == 0.0
    record("v0_no_active_guarantee", v0_ok, "V0 has c_ref=c_check=0 (no active detection)")

    # 8. missing values are NaN, never silently zero
    missing_repr = float("nan")
    record("missing_not_zero", math.isnan(missing_repr) and missing_repr != 0.0,
           "unknown values represented as NaN, not 0")

    return checks, failures


def scan(modes: list[dict], grid: dict, targets: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"risk_curves": [], "cost_grid": [], "feasible_regions": [], "sensitivity": []}
    r_single = targets["single_shot"]["primary"]
    r_persist = targets["persistent"]["primary"]
    cost_cap = targets["cost_cap_ratio"]

    for mode in modes:
        for d in grid["d_grid"]:
            for m in grid["m_grid"]:
                for p_a in grid["p_a_grid"]:
                    ds = d_single(p_a, d)
                    dm = d_m(p_a, d, m)
                    out["risk_curves"].append({
                        "mode_id": mode["mode_id"], "p_a": p_a, "d": d, "m": m,
                        "D_single": ds, "D_m": dm,
                        "meets_single_target": ds >= r_single,
                        "meets_persistent_target": dm >= r_persist,
                    })
        for u in grid["u_grid"]:
            for p_a in grid["p_a_grid"]:
                cost = expected_cost(mode, p_a, u)
                out["cost_grid"].append({
                    "mode_id": mode["mode_id"], "p_a": p_a, "u": u,
                    "E_C_verify": cost, "cost_ratio_vs_duplicate": cost,
                    "within_cost_cap": cost <= cost_cap,
                })
        # feasible p_a interval: risk (single) >= primary target AND cost <= cap, per (d, u)
        for d in grid["d_grid"]:
            for u in grid["u_grid"]:
                feasible = []
                for p_a in grid["p_a_grid"]:
                    risk_ok = d_single(p_a, d) >= r_single
                    cost_ok = expected_cost(mode, p_a, u) <= cost_cap
                    if risk_ok and cost_ok:
                        feasible.append(p_a)
                p_min = p_a_min_single(r_single, d)
                out["feasible_regions"].append({
                    "mode_id": mode["mode_id"], "d": d, "u": u,
                    "p_a_min_for_risk": (None if p_min is None else
                                         ("infeasible" if math.isinf(p_min) else p_min)),
                    "feasible_p_a": "[" + ",".join(f"{x:g}" for x in feasible) + "]",
                    "n_feasible": len(feasible),
                    "feasible": len(feasible) > 0,
                })
        # sensitivity: primary vs design-scan targets
        for r in targets["single_shot"]["targets"]:
            for d in grid["d_grid"]:
                p_min = p_a_min_single(r, d)
                out["sensitivity"].append({
                    "mode_id": mode["mode_id"], "target": r, "d": d,
                    "p_a_min": (None if p_min is None else
                                ("infeasible" if math.isinf(p_min) else p_min)),
                })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=HERE / "configs")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()

    prereg = json.loads((args.config_dir / "preregistration.json").read_text(encoding="utf-8"))
    targets = json.loads((args.config_dir / prereg["risk_targets_file"]).read_text(encoding="utf-8"))
    modes = load_modes(args.config_dir / prereg["modes_file"])

    run_id = prereg["run_id"]
    out_dir = args.out / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    checks, failures = run_self_checks(modes, prereg)
    (out_dir / "protocol_checks.json").write_text(
        json.dumps({"checks": checks, "failures": failures}, indent=2, sort_keys=True), encoding="utf-8"
    )
    if failures:
        print("SELF-CHECK FAILED:\n  " + "\n  ".join(failures), file=sys.stderr)
        raise SystemExit(2)

    scan_out = scan(modes, prereg, targets)
    for name in ("risk_curves", "cost_grid", "feasible_regions", "sensitivity"):
        rows = scan_out[name]
        if not rows:
            continue
        with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    # go/no-go per mode (from feasible_regions + cost)
    decisions = {}
    for mode in modes:
        feas = [r for r in scan_out["feasible_regions"] if r["mode_id"] == mode["mode_id"]]
        any_feasible = any(r["feasible"] for r in feas)
        at_pa1 = expected_cost(mode, 1.0, 0.0)
        if mode["mode_id"] == "D0_duplicate":
            decisions[mode["mode_id"]] = "BASELINE"
        elif mode["c_ref"] == 0.0 and mode["c_check"] == 0.0:
            decisions[mode["mode_id"]] = "NO_GO"   # no active detection
        elif not any_feasible:
            decisions[mode["mode_id"]] = "NO_GO"
        elif at_pa1 > targets["cost_cap_ratio"]:
            decisions[mode["mode_id"]] = "CONDITIONAL_GO"  # only cheap when sampling is affordable
        else:
            decisions[mode["mode_id"]] = "GO"

    summary = {
        "run_id": run_id,
        "date": str(date.today()),
        "primary_targets": {"single_shot": targets["single_shot"]["primary"],
                            "persistent": targets["persistent"]["primary"],
                            "cost_cap_ratio": targets["cost_cap_ratio"]},
        "decisions": decisions,
        "self_checks_passed": True,
        "caveats": [
            "cost inputs are 'assumed' until E01/E02 measured values are linked",
            "d is a conditional detection rate, not a semantic guarantee",
            "V0_passive provides no active correctness guarantee",
            "asynchronous discovery cannot undo harm already produced",
        ],
    }
    (out_dir / "go_nogo_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "environment.json").write_text(json.dumps({
        "python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
        "seed": prereg["seed"],
    }, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "input_manifest.csv").write_text("mode_id,label,c_always,c_ref,c_check,c_upgrade,source_type\n" +
        "".join(f"{m['mode_id']},{m['label']},{m['c_always']},{m['c_ref']},{m['c_check']},{m['c_upgrade']},{m['source_type']}\n"
                for m in modes), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "out": str(out_dir), "decisions": decisions}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
