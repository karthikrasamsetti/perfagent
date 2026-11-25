"""Human-readable identity for distinct workloads against the same host."""
import json

from perfagent.db.models import ScriptRow, ScriptSnapshotRow


def model_identity(model, filename):
    endpoints = list(dict.fromkeys(
        f"{step.method.value} {step.path.split('?')[0]}"
        for scenario in model.scenarios for step in scenario.steps))
    # Uploaded scripts have a placeholder plan; its '/' is not an observed endpoint.
    uploaded = len(model.scenarios) == 1 and model.scenarios[0].name == "uploaded"
    return {"test_name": model.test_name.strip() or " / ".join(s.name for s in model.scenarios),
            "script_name": filename,
            "endpoint_summary": "Not recorded (uploaded script)" if uploaded else ", ".join(endpoints),
            "endpoint_count": None if uploaded else len(endpoints)}


def saved_identity(row, session=None):
    report = json.loads(row.report_json or "{}")
    execution = report.get("execution", {})
    identity = {key: execution.get(key) for key in
                ("test_name", "script_name", "endpoint_summary", "endpoint_count")}
    if not identity["test_name"] and session is not None and report.get("script_id"):
        from perfagent.contracts.load_model import LoadModel
        script = session.get(ScriptRow, report["script_id"])
        snapshot = session.get(ScriptSnapshotRow, report["script_id"])
        if snapshot is not None:
            identity = model_identity(LoadModel.model_validate_json(snapshot.load_model_json),
                                      script.filename if script else "Not recorded")
        elif script is not None:
            identity["script_name"] = script.filename
    identity["test_name"] = identity["test_name"] or row.goal or "Test " + row.plan_id[:8]
    identity["script_name"] = identity["script_name"] or "Not recorded"
    identity["endpoint_summary"] = identity["endpoint_summary"] or "Not recorded"
    return identity
