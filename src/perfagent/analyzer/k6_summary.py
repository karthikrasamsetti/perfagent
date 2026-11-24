"""Read both k6 summary-export and handleSummary metric representations."""


def metric_values(metric: dict) -> dict:
    values = metric.get("values")
    return values if isinstance(values, dict) else metric


def threshold_result(outcome: object) -> bool | None:
    if isinstance(outcome, bool):
        # The original summary export records whether a threshold was breached.
        return not outcome
    if isinstance(outcome, dict) and isinstance(outcome.get("ok"), bool):
        return outcome["ok"]
    return None
