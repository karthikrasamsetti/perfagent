"""Freeze script inputs once; reports expose hashes, never headers or data values."""
import hashlib
import json

from fastapi import HTTPException

from perfagent.contracts.load_model import LoadModel
from perfagent.db import DataFileRow
from perfagent.db.models import ScriptSnapshotRow
from perfagent.api.test_identity import model_identity


def planned_phases(model: LoadModel) -> list[dict]:
    profile = model.load_profile
    if profile.arrival_rate:
        return [{"label": "Constant arrival rate", "start_s": 0, "end_s": profile.total_seconds}]
    phases = []
    elapsed, users = 0, profile.start_users
    for stage in profile.stages:
        end = elapsed + stage.duration_seconds
        label = ("Ramp up" if stage.target_users > users
                 else "Ramp down" if stage.target_users < users else "Steady state")
        phases.append({"label": label, "start_s": elapsed, "end_s": end})
        elapsed, users = end, stage.target_users
    return phases


def script_workload_version(content: str, model_json: str, data_content: str) -> str:
    return hashlib.sha256((content + model_json + data_content).encode()).hexdigest()


def freeze_script(session, script, model: LoadModel, *, generated=False):
    saved = session.get(ScriptSnapshotRow, script.id)
    if saved is not None:
        return saved
    filename, content = "", ""
    if model.data_file:
        data = (session.get(DataFileRow, model.data_file.data_file_id)
                if model.data_file.data_file_id else
                session.query(DataFileRow).filter(DataFileRow.filename == model.data_file.filename)
                .order_by(DataFileRow.created_at.desc()).first())
        if data is None:
            raise HTTPException(400, "The test data file is missing. Attach it before running.")
        filename, content = data.filename, data.content
        model.data_file.data_file_id = data.id
    model_json = model.model_dump_json()
    signature = script_workload_version(script.content, model_json, content)
    metadata = {
        **model_identity(model, script.filename),
        "workload_version": signature,
        "data_version": hashlib.sha256(content.encode()).hexdigest() if content else None,
        "environment": model.environment,
        "duration_seconds": model.load_profile.total_seconds,
        "peak_users": model.load_profile.peak_users,
        "arrival_rate": model.load_profile.arrival_rate,
        "target_request_rate": model.load_profile.target_request_rate,
        "generated": generated,
    }
    saved = ScriptSnapshotRow(script_id=script.id, load_model_json=model_json,
                              data_filename=filename, data_content=content,
                              metadata_json=json.dumps(metadata))
    session.add(saved)
    return saved
