"""Exit with a CI verdict from an existing PerfAgent JSON report."""

import argparse
import json
import sys
from pathlib import Path


def gate_report(report: object, *, environment: str | None = None, release: str | None = None) -> int:
    """Return 0 for ready, 1 for blocked, or 2 when evidence is insufficient."""
    if not isinstance(report, dict):
        return 2
    execution = report.get("execution")
    decision = report.get("release_readiness")
    if not isinstance(execution, dict) or not isinstance(decision, dict):
        return 2
    if environment is not None and execution.get("environment") != environment:
        return 2
    if release is not None and execution.get("release_label") != release:
        return 2
    if report.get("status") != "finished" or execution.get("mode") != "full":
        return 2

    status = decision.get("status")
    if status == "blocked":
        return 1
    verdict = report.get("verdict")
    if status == "ready" and isinstance(verdict, dict) and verdict.get("overall_passed") is True:
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="JSON file from the saved report endpoint")
    parser.add_argument("--environment", help="Expected report environment")
    parser.add_argument("--release", help="Expected report release label")
    options = parser.parse_args(argv)

    try:
        report = json.loads(options.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        print("Needs evidence: could not read the JSON report.", file=sys.stderr)
        return 2

    result = gate_report(report, environment=options.environment, release=options.release)
    print(("Ready", "Blocked", "Needs evidence")[result])
    return result


if __name__ == "__main__":
    sys.exit(main())
