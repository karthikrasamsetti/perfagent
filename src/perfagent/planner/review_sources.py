"""Track source labels separately from executable plans and their input values."""

from perfagent.contracts.load_model import LoadModel
from perfagent.planner.spec import PlanRequest


def draft_review_sources(request: PlanRequest, model: LoadModel) -> dict:
    endpoints = {(endpoint.method, endpoint.path): endpoint for endpoint in request.endpoints}
    journeys = []
    for scenario in model.scenarios:
        steps = []
        for step in scenario.steps:
            supplied = endpoints[(step.method, step.path)]
            steps.append({
                "endpoint": "user",
                "body": "user" if supplied.example_body is not None else "suggested" if step.body is not None else None,
                "checks": "user" if supplied.assertions is not None else "suggested" if step.assertions else None,
            })
        journeys.append({"source": "suggested", "steps": steps})
    return {
        "target": "user",
        "load": ("traffic" if request.traffic_sample_rate and request.target_request_rate
                 else "user" if request.stages or request.target_request_rate
                 or request.target_iteration_rate or request.executor_options else "profile"),
        "thresholds": "user" if request.thresholds is not None else "suggested",
        "journeys": journeys,
    }


def update_review_sources(sources: dict, before: LoadModel, after: LoadModel) -> dict:
    def label(original, previous, current):
        return "edited" if previous != current else original

    result = {
        "target": label(sources["target"], (before.target_base_url, before.environment, before.insecure_tls),
                        (after.target_base_url, after.environment, after.insecure_tls)),
        "load": label(sources["load"], before.load_profile, after.load_profile),
        "thresholds": label(sources["thresholds"], before.thresholds, after.thresholds),
        "journeys": [],
    }
    for index, scenario in enumerate(after.scenarios):
        if index >= len(before.scenarios):
            result["journeys"].append({"source": "edited", "steps": [
                {"endpoint": "edited", "body": "edited" if step.body is not None else None,
                 "checks": "edited" if step.assertions else None} for step in scenario.steps
            ]})
            continue
        previous = before.scenarios[index]
        existing = sources["journeys"][index]
        journey = {
            "source": label(existing["source"], previous.model_dump(exclude={"steps"}),
                            scenario.model_dump(exclude={"steps"})),
            "steps": [],
        }
        for position, step in enumerate(scenario.steps):
            old_step = previous.steps[position] if position < len(previous.steps) else None
            old_labels = existing["steps"][position] if old_step is not None else {}
            journey["steps"].append({
                "endpoint": label(old_labels.get("endpoint"), (old_step.method, old_step.path) if old_step else None,
                                  (step.method, step.path)),
                "body": label(old_labels.get("body"), old_step.body if old_step else None, step.body),
                "checks": label(old_labels.get("checks"), old_step.assertions if old_step else [], step.assertions),
            })
        result["journeys"].append(journey)
    return result
