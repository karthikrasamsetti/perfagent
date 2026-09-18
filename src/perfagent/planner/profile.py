"""Deterministic load-profile builder.

The *shape* of load over time (ramp up -> steady -> ramp down) is not a judgement
call for the LLM - it is a well-understood pattern. Code owns it. The AI decides
what journeys to test and their weights; this module decides how the load ramps.

Given a peak user count and a total duration, it produces the classic three-phase
shape for each profile type:

  ramp   : ramp up (20%) -> hold at peak (60%) -> ramp down (20%)
  spike  : quick ramp to peak (10%) -> hold (30%) -> quick down (10%), on a low base
  soak   : short ramp (10%) -> long hold at peak (85%) -> short down (5%)
  stress : stepped ramp all the way up (no steady hold, no ramp down)
"""

from __future__ import annotations

from perfagent.contracts.load_model import LoadProfile, LoadProfileType, Stage


def build_profile(
    profile_type: LoadProfileType,
    peak_users: int,
    total_seconds: int,
) -> LoadProfile:
    peak = max(1, peak_users)
    total = max(3, total_seconds)

    if profile_type == LoadProfileType.SPIKE:
        up = max(1, int(total * 0.10))
        hold = max(1, int(total * 0.30))
        down = max(1, total - up - hold)
        base = max(1, peak // 5)
        stages = [
            Stage(duration_seconds=up, target_users=peak),      # sudden spike up
            Stage(duration_seconds=hold, target_users=peak),    # hold the spike
            Stage(duration_seconds=down, target_users=base),    # drop back to base
        ]
    elif profile_type == LoadProfileType.SOAK:
        up = max(1, int(total * 0.10))
        down = max(1, int(total * 0.05))
        hold = max(1, total - up - down)
        stages = [
            Stage(duration_seconds=up, target_users=peak),      # ramp up
            Stage(duration_seconds=hold, target_users=peak),    # long steady soak
            Stage(duration_seconds=down, target_users=0),       # ramp down
        ]
    elif profile_type == LoadProfileType.STRESS:
        # Stepped increase to peak in 3 steps, no hold, no ramp down.
        step = max(1, total // 3)
        stages = [
            Stage(duration_seconds=step, target_users=max(1, peak // 3)),
            Stage(duration_seconds=step, target_users=max(1, (peak * 2) // 3)),
            Stage(duration_seconds=max(1, total - 2 * step), target_users=peak),
        ]
    else:  # RAMP (the default, classic shape)
        up = max(1, int(total * 0.20))
        down = max(1, int(total * 0.20))
        hold = max(1, total - up - down)
        stages = [
            Stage(duration_seconds=up, target_users=peak),      # ramp up
            Stage(duration_seconds=hold, target_users=peak),    # steady state
            Stage(duration_seconds=down, target_users=0),       # ramp down
        ]

    return LoadProfile(type=profile_type, stages=stages)