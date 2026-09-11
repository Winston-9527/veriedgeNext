"""Formula-boundary and self-check tests for the E09 risk-cost model."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from simulate_reference_economics import (  # noqa: E402
    d_single, d_m, expected_cost, load_modes, p_a_min_m, p_a_min_single, run_self_checks,
)

CONFIG_DIR = HERE.parent / "configs"


def _modes():
    return load_modes(CONFIG_DIR / "reference_modes.csv")


def test_d_single_is_product():
    assert d_single(0.2, 0.9) == pytest.approx(0.18)
    assert d_single(0.0, 1.0) == 0.0
    assert d_single(1.0, 1.0) == 1.0


def test_d_m_boundaries():
    assert d_m(0.0, 1.0, 100) == 0.0
    assert d_m(1.0, 1.0, 1) == 1.0
    assert d_m(0.01, 1.0, 100) == pytest.approx(1 - 0.99 ** 100)


def test_d_m_monotone_in_m():
    seq = [d_m(0.05, 0.9, m) for m in (1, 5, 10, 50, 100)]
    assert all(b >= a for a, b in zip(seq, seq[1:]))


def test_p_a_min_single():
    assert p_a_min_single(0.99, 0.99) == pytest.approx(1.0)
    assert math.isinf(p_a_min_single(1.0, 0.9))   # r > d is unreachable


def test_p_a_min_m_reachable():
    assert p_a_min_m(0.99, 1.0, 10) == pytest.approx(1 - 0.01 ** 0.1)


def test_expected_cost_pa0_is_c_always():
    mode = _modes()[0]
    assert expected_cost(mode, 0.0, 1.0) == mode["c_always"]


def test_self_checks_pass():
    modes = _modes()
    grid = {"p_a_grid": [0, 0.01, 0.5, 1.0], "m_grid": [1, 10], "d_grid": [0.5, 1.0], "u_grid": [0, 1.0]}
    _checks, failures = run_self_checks(modes, grid)
    assert failures == []


def test_v0_is_not_an_active_guarantee():
    v0 = next(m for m in _modes() if m["mode_id"] == "V0_passive")
    assert v0["c_ref"] == 0.0 and v0["c_check"] == 0.0
