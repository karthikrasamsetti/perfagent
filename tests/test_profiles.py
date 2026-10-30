"""Tests for the load-profile builder — distinct shapes per type."""

from __future__ import annotations

from perfagent.contracts.load_model import LoadProfileType
from perfagent.planner.profile import build_profile


def test_ramp_shape():
    p = build_profile(LoadProfileType.RAMP, 100, 100)
    assert p.peak_users == 100
    assert p.stages[-1].target_users == 0   # ramps down to 0


def test_spike_has_sudden_peak():
    p = build_profile(LoadProfileType.SPIKE, 100, 100)
    targets = [s.target_users for s in p.stages]
    assert 100 in targets                    # reaches peak
    assert targets[0] < 100                  # starts low (baseline)
    # the spike stage is short relative to the baseline
    peak_stage = next(s for s in p.stages if s.target_users == 100)
    assert peak_stage.duration_seconds <= p.total_seconds * 0.3


def test_soak_has_long_hold():
    p = build_profile(LoadProfileType.SOAK, 100, 100)
    # the longest stage holds at peak for most of the duration
    longest = max(p.stages, key=lambda s: s.duration_seconds)
    assert longest.target_users == 100
    assert longest.duration_seconds >= p.total_seconds * 0.6


def test_stress_steps_past_target():
    p = build_profile(LoadProfileType.STRESS, 100, 100)
    assert max(s.target_users for s in p.stages) > 100   # pushes past the target


def test_all_four_are_distinct():
    shapes = {
        t.value: tuple((s.target_users, s.duration_seconds)
                       for s in build_profile(t, 100, 100).stages)
        for t in LoadProfileType
    }
    assert len(set(shapes.values())) == 4
