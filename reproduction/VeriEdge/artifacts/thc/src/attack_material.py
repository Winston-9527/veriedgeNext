from __future__ import annotations

from typing import Dict

import numpy as np

from attack import clone_checkpoint_bundle


def inject_stale_replay(
    bundle: Dict[str, Dict[str, np.ndarray]],
    donor_bundle: Dict[str, Dict[str, np.ndarray]],
    checkpoint: str,
) -> Dict[str, Dict[str, np.ndarray]]:
    tampered = clone_checkpoint_bundle(bundle)
    for stage, stage_map in tampered.items():
        if checkpoint not in stage_map:
            raise KeyError(f"checkpoint {checkpoint} missing from target stage {stage}")
        donor_stage = donor_bundle.get(stage)
        if donor_stage is None or checkpoint not in donor_stage:
            raise KeyError(f"checkpoint {checkpoint} missing from donor stage {stage}")
        stage_map[checkpoint] = np.array(donor_stage[checkpoint], copy=True)
    return tampered


def inject_wrong_prompt_checkpoint(
    bundle: Dict[str, Dict[str, np.ndarray]],
    donor_bundle: Dict[str, Dict[str, np.ndarray]],
    checkpoint: str,
) -> Dict[str, Dict[str, np.ndarray]]:
    return inject_stale_replay(bundle, donor_bundle, checkpoint)
