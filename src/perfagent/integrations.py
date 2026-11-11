"""Remember the non-secret Git and Jenkins details a user entered, per plan.

Saved automatically after something WORKED (a successful push, import, Jenkins run or
job set-up), so typos from failed attempts aren't remembered. When a saved plan is
opened, PerfAgent fills the Save to Git and Run in Jenkins cards from here; the user
only types their tokens.

Never stored: Git tokens, Jenkins API tokens, test secrets. Only the whitelisted keys
below are ever written, and a URL that embeds credentials (https://user:pass@host)
is refused rather than saved.

Besides one row per plan, a "__last__" row keeps the most recently used values; a new
plan gets a few of them (repository, branch, Jenkins URL, user name, Git credentials
ID) as defaults. Framework, test and job names are per plan, so they are not copied.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from sqlalchemy import select

from perfagent.db import IntegrationSettingsRow, PlanRow, get_session

LAST = "__last__"

GIT_KEYS = ("repo_url", "branch", "framework", "test", "ci")
JENKINS_KEYS = ("url", "username", "job", "test", "environment",
                "repo_url", "branch", "framework", "git_credentials_id")
# Values a brand-new plan inherits from the last-used row.
DEFAULT_GIT_KEYS = ("repo_url", "branch")
DEFAULT_JENKINS_KEYS = ("url", "username", "git_credentials_id", "environment")

_MAX_LEN = 500
_CI_OK = {"github", "jenkins", "azure", "gitlab"}
_SECTIONS = ("git", "jenkins")


def _has_credentials(url: str) -> bool:
    if url.startswith(("https://", "http://", "ssh://")):
        p = urlparse(url)
        return bool(p.password) or (bool(p.username) and not url.startswith("ssh://"))
    return False


def _clean(section: str, values: dict) -> dict:
    """Keep only whitelisted, non-empty, sane values for a section."""
    keys = GIT_KEYS if section == "git" else JENKINS_KEYS
    out: dict = {}
    for k in keys:
        v = values.get(k)
        if v is None:
            continue
        if k == "ci":
            if isinstance(v, (list, tuple)):
                ci = [str(c).lower() for c in v if str(c).lower() in _CI_OK]
                out[k] = ci
            continue
        v = str(v).strip()
        if not v or len(v) > _MAX_LEN or "\n" in v or "\r" in v:
            continue
        if k in ("repo_url", "url") and _has_credentials(v):
            continue                      # never keep credentials embedded in a URL
        if k == "username" and re.search(r"\s", v):
            continue
        out[k] = v
    return out


def _load(row: IntegrationSettingsRow | None, section: str) -> dict:
    if row is None:
        return {}
    try:
        data = json.loads(getattr(row, f"{section}_json") or "{}")
    except ValueError:
        return {}
    return _clean(section, data if isinstance(data, dict) else {})


def _row(s, plan_id: str) -> IntegrationSettingsRow | None:
    return s.scalars(select(IntegrationSettingsRow)
                     .where(IntegrationSettingsRow.plan_id == plan_id)).first()


def save(plan_id: str | None, *, git: dict | None = None, jenkins: dict | None = None) -> None:
    """Merge the given details into the plan's row (if the plan exists) and into the
    last-used row. Best-effort: a failure here never breaks the user's action."""
    updates = {k: _clean(k, v) for k, v in (("git", git), ("jenkins", jenkins)) if v}
    updates = {k: v for k, v in updates.items() if v}
    if not updates:
        return
    try:
        with get_session() as s:
            targets = [LAST]
            if plan_id and plan_id != LAST and s.get(PlanRow, plan_id) is not None:
                targets.insert(0, plan_id)
            for pid in targets:
                row = _row(s, pid)
                if row is None:
                    row = IntegrationSettingsRow(plan_id=pid, git_json="{}", jenkins_json="{}")
                    s.add(row)
                for section, values in updates.items():
                    merged = {**_load(row, section), **values}
                    setattr(row, f"{section}_json", json.dumps(merged))
            s.commit()
    except Exception:  # noqa: BLE001 - remembering details must never fail a push/run
        pass


def get(plan_id: str | None) -> dict:
    """Details for a plan. Values saved for the plan win; anything missing is filled
    from the last-used defaults. 'saved' tells the UI which sections came from the plan."""
    with get_session() as s:
        plan_row = _row(s, plan_id) if plan_id and plan_id != LAST else None
        last = _row(s, LAST)
        result: dict = {"plan_id": plan_id, "saved": []}
        for section, default_keys in (("git", DEFAULT_GIT_KEYS), ("jenkins", DEFAULT_JENKINS_KEYS)):
            own = _load(plan_row, section)
            defaults = {k: v for k, v in _load(last, section).items() if k in default_keys}
            result[section] = {**defaults, **own}
            if own:
                result["saved"].append(section)
        return result


def forget(plan_id: str | None, section: str) -> None:
    """Remove saved details for a section ('git', 'jenkins' or 'all') from the plan
    and from the last-used defaults."""
    sections = _SECTIONS if section == "all" else (section,)
    if any(x not in _SECTIONS for x in sections):
        raise ValueError("section must be 'git', 'jenkins' or 'all'")
    with get_session() as s:
        for pid in {plan_id, LAST} - {None, ""}:
            row = _row(s, pid)
            if row is None:
                continue
            for x in sections:
                setattr(row, f"{x}_json", "{}")
        s.commit()