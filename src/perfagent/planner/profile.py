"""Deterministic load-profile builder — code owns the *shape*, not the AI.

Each profile type produces a genuinely different stage pattern over the total
duration, so choosing spike/soak/stress actually changes how load is applied:

  ramp   — ramp up, hold steady, ramp down (the default, balanced test)
  spike  — small baseline, a sudden sharp spike to peak, then back down
  soak   — quick ramp, then a long steady hold (endurance / memory-leak hunting)
  stress — step the load up in stages, pushing past the target to find limits
"""

from __future__ import annotations

from perfagent.contracts.load_model import LoadProfile, LoadProfileType, Stage


def _secs(fraction: float, total: int) -> int:
    return max(1, int(round(total * fraction)))


def build_profile(profile_type: LoadProfileType, peak_users: int,
                  total_seconds: int) -> LoadProfile:
    """Build a stage list whose SHAPE matches the profile type."""
    peak = max(1, int(peak_users))
    total = max(3, int(total_seconds))
    t = profile_type

    if t == LoadProfileType.SPIKE:
        # baseline, sharp spike to peak, hold briefly, drop back, settle
        base = max(1, peak // 5)
        stages = [
            Stage(duration_seconds=_secs(0.25, total), target_users=base),
            Stage(duration_seconds=_secs(0.05, total), target_users=peak),   # sudden spike
            Stage(duration_seconds=_secs(0.20, total), target_users=peak),   # hold the spike
            Stage(duration_seconds=_secs(0.05, total), target_users=base),   # drop
            Stage(duration_seconds=_secs(0.45, total), target_users=base),   # recover/observe
        ]
    elif t == LoadProfileType.SOAK:
        # quick ramp, then a long steady hold (endurance), short ramp down
        stages = [
            Stage(duration_seconds=_secs(0.08, total), target_users=peak),   # quick ramp up
            Stage(duration_seconds=_secs(0.84, total), target_users=peak),   # long steady soak
            Stage(duration_seconds=_secs(0.08, total), target_users=0),      # ramp down
        ]
    elif t == LoadProfileType.STRESS:
        # step the load up in increasing stages, pushing past the target
        q = max(1, peak // 4)
        stages = [
            Stage(duration_seconds=_secs(0.18, total), target_users=q),
            Stage(duration_seconds=_secs(0.18, total), target_users=q * 2),
            Stage(duration_seconds=_secs(0.18, total), target_users=q * 3),
            Stage(duration_seconds=_secs(0.18, total), target_users=peak),
            Stage(duration_seconds=_secs(0.18, total), target_users=int(peak * 1.3)),  # past target
            Stage(duration_seconds=_secs(0.10, total), target_users=0),
        ]
    else:  # RAMP (default)
        stages = [
            Stage(duration_seconds=_secs(0.2, total), target_users=peak),    # ramp up
            Stage(duration_seconds=_secs(0.6, total), target_users=peak),    # steady
            Stage(duration_seconds=_secs(0.2, total), target_users=0),       # ramp down
        ]

    return LoadProfile(type=t, stages=stages)