#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd


REQUIRED_RESULT_COLUMNS = {
    "policy",
    "task_id",
    "candidate_id",
    "admitted",
    "selected",
    "latency_s",
    "goodput",
    "infeasible_usage",
    "false_risk",
    "verify_ms",
    "sketch",
    "reason",
}


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the included deterministic placement replay log after "
            "validating candidate, workload, and verifier-profile inputs."
        )
    )
    parser.add_argument("--profiles", default="data/verifier_profiles.csv")
    parser.add_argument("--candidates", default="data/placement_candidates.csv")
    parser.add_argument("--workload", default="data/placement_workload.csv")
    parser.add_argument("--replay-log", default="data/placement_replay_log.csv")
    parser.add_argument("--out", default="data/placement_results.csv")
    args = parser.parse_args()

    profiles = pd.read_csv(args.profiles)
    candidates = pd.read_csv(args.candidates)
    workload = pd.read_csv(args.workload)
    replay = pd.read_csv(args.replay_log)

    missing = REQUIRED_RESULT_COLUMNS - set(replay.columns)
    if missing:
        raise SystemExit(f"replay log is missing required columns: {sorted(missing)}")
    if profiles.empty or candidates.empty or workload.empty or replay.empty:
        raise SystemExit("input tables must be non-empty")

    known_tasks = set(workload["task_id"])
    unknown_tasks = set(replay["task_id"]) - known_tasks
    if unknown_tasks:
        sample = sorted(unknown_tasks)[:5]
        raise SystemExit(f"replay log references unknown tasks: {sample}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    replay.to_csv(args.out, index=False)
    print(f"validated {len(replay)} replay rows and wrote {args.out}")


if __name__ == "__main__":
    main()
