#!/usr/bin/env python3
import argparse
import math

import pandas as pd


def wilson(successes: int, trials: int, z: float = 1.96):
    if trials <= 0:
        return float("nan"), float("nan")
    phat = successes / trials
    denom = 1 + z * z / trials
    center = (phat + z * z / (2 * trials)) / denom
    half = z * math.sqrt((phat * (1 - phat) + z * z / (4 * trials)) / trials) / denom
    return center - half, center + half


def main():
    parser = argparse.ArgumentParser(description="Compute Wilson 95% confidence intervals for verifier profiles.")
    parser.add_argument("--infile", default="data/verifier_profiles.csv")
    parser.add_argument("--out", default="data/verifier_profiles_with_ci.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.infile)
    rows = []
    for _, row in df.iterrows():
        out = row.to_dict()
        fpr_lo, fpr_hi = wilson(int(row["fpr_false_positives"]), int(row["fpr_trials"]))
        tpr_lo, tpr_hi = wilson(int(row["tpr_true_positives"]), int(row["tpr_trials"]))
        out["fpr_wilson95_lo"] = fpr_lo
        out["fpr_wilson95_hi"] = fpr_hi
        out["tpr_wilson95_lo"] = tpr_lo
        out["tpr_wilson95_hi"] = tpr_hi
        rows.append(out)

    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
