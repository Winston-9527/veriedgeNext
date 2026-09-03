#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path


PROVIDERS = ["C1", "C2", "C3"]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def provider_target(env: dict[str, str], role: str) -> str:
    user = env[f"PROVIDER_{role}_USER"]
    host = env[f"PROVIDER_{role}_HOST"]
    return f"{user}@{host}"


def remote_command(env: dict[str, str], role: str, max_prompts: int) -> str:
    remote_workdir = env.get("REMOTE_WORKDIR", "/tmp/veriedge_remote_capture")
    model_id = env.get("MODEL_ID", "Qwen/Qwen3-0.6B")
    backend = env.get(f"PROVIDER_{role}_BACKEND", "default")
    output = f"{remote_workdir}/out_{role.lower()}_{backend}"
    return " && ".join(
        [
            f"mkdir -p {shlex.quote(remote_workdir)}",
            f"cd {shlex.quote(remote_workdir)}",
            "python -m venv .venv",
            ". .venv/bin/activate",
            "pip install -q numpy pandas torch transformers accelerate",
            (
                "python collect_hf_verifier_profiles.py "
                f"--backend hf --model-id {shlex.quote(model_id)} "
                f"--max-prompts {max_prompts} --out-dir {shlex.quote(output)}"
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run-first multi-node checkpoint collection coordinator.")
    parser.add_argument("--env", default="multi_node_runner/env.example")
    parser.add_argument("--max-prompts", type=int, default=8)
    parser.add_argument("--execute", action="store_true", help="Actually run SSH/rsync commands.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing; default behavior.")
    args = parser.parse_args()

    env = read_env(Path(args.env))
    local_output = Path(env.get("LOCAL_OUTPUT_DIR", "collected_multinode"))
    commands = []
    for role in PROVIDERS:
        target = provider_target(env, role)
        remote = remote_command(env, role, args.max_prompts)
        commands.append(["ssh", target, f"mkdir -p {shlex.quote(env.get('REMOTE_WORKDIR', '/tmp/veriedge_remote_capture'))}"])
        commands.append(
            [
                "scp",
                "data_collection/collect_hf_verifier_profiles.py",
                f"{target}:{env.get('REMOTE_WORKDIR', '/tmp/veriedge_remote_capture')}/collect_hf_verifier_profiles.py",
            ]
        )
        commands.append(["ssh", target, remote])
        commands.append(["rsync", "-av", f"{target}:{env.get('REMOTE_WORKDIR', '/tmp/veriedge_remote_capture')}/out_{role.lower()}_*", str(local_output)])

    execute = args.execute and not args.dry_run
    for command in commands:
        printable = " ".join(shlex.quote(part) for part in command)
        print(printable)
        if execute:
            subprocess.run(command, check=True)

    if not execute:
        print("\nDry run only. Re-run with --execute after replacing placeholders in .env.")


if __name__ == "__main__":
    main()
