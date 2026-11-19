"""Deterministic reporting layer: role-scoped historical + coverage views.

Serves run history, metric trends, and flow coverage off the run_records
table. No LLM calls; the only AI-authored column surfaced is the existing
narrator output, read-only and engineer-scoped.
"""
from .service import Role, project  # noqa: F401
