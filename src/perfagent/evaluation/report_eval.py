"""Evaluate the quality of an AI-written report narrative — deterministically.

The single most important check: every number the AI states in the narrative must
trace to a real computed metric. A figure in the text that isn't in the actual
results is a hallucination, and this catches it.

This is the "how do we know the report is trustworthy" answer: the verdict and the
metrics are computed by code; this verifies the AI only *described* those numbers
and did not invent any.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Numbers that are always acceptable in prose regardless of the metrics
# (percentile labels, common round references). Kept deliberately small.
_ALWAYS_OK = {"50", "90", "95", "99", "100", "0", "1", "2", "3", "5", "10"}

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class ReportEvaluation:
    unsupported_numbers: list[str] = field(default_factory=list)
    total_numbers: int = 0

    @property
    def hallucinated(self) -> int:
        return len(self.unsupported_numbers)

    @property
    def grounded(self) -> bool:
        return self.hallucinated == 0

    def summary(self) -> dict:
        return {
            "grounded": self.grounded,
            "numbers_in_text": self.total_numbers,
            "hallucinated": self.hallucinated,
            "unsupported": self.unsupported_numbers,
        }


def _allowed_numbers(snapshot: dict, verdict: dict) -> set[str]:
    """Every numeric value that legitimately appears in the computed results."""
    allowed: set[str] = set(_ALWAYS_OK)

    def add(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            # add several string forms: int, one-decimal, two-decimal, and pct
            allowed.add(str(int(x)) if float(x).is_integer() else str(x))
            allowed.add(f"{x:.0f}")
            allowed.add(f"{x:.1f}")
            allowed.add(f"{x:.2f}")
            # error_rate as a percentage (0.0 -> 0.00, 0.01 -> 1.00 / 1)
            allowed.add(f"{x * 100:.0f}")
            allowed.add(f"{x * 100:.1f}")
            allowed.add(f"{x * 100:.2f}")

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        else:
            add(v)

    walk(snapshot)
    walk(verdict)
    return allowed


def evaluate_report(narrative_text: str, snapshot: dict, verdict: dict) -> ReportEvaluation:
    """Check that every number in the narrative traces to a computed metric."""
    allowed = _allowed_numbers(snapshot, verdict)
    found = _NUMBER.findall(narrative_text)
    unsupported = []
    for token in found:
        # normalise: strip trailing .0 for comparison convenience
        candidates = {token}
        try:
            f = float(token)
            candidates.add(str(int(f)) if f.is_integer() else token)
            candidates.add(f"{f:.1f}")
            candidates.add(f"{f:.2f}")
            candidates.add(f"{f:.0f}")
        except ValueError:
            pass
        if not (candidates & allowed):
            unsupported.append(token)
    return ReportEvaluation(unsupported_numbers=unsupported, total_numbers=len(found))