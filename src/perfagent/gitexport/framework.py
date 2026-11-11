"""Build a Git-ready k6 performance framework from an approved PerfAgent plan.

The framework is a plain folder of files, so the same builder feeds both the
"push to Git" path (publisher.py) and the "download as .zip" path.

Layout written inside the repository (``<framework>`` is the user's name, slugged):

    <framework>/
      README.md                     how to run locally and in CI      (created once)
      perfagent.json                manifest: every test + lineage    (always updated)
      environments/dev.env          BASE_URL and other non-secret settings (created once)
      tests/<test>/loadtest.js      the k6 script; secrets come from env vars
      tests/<test>/plan.json        the approved LoadModel, secrets removed
      tests/<test>/test.json        lineage, thresholds, required secrets, data file
      scripts/run-tests.sh          run one test or all (POSIX sh)    (managed)
      scripts/run-tests.ps1         same, for Windows                 (managed)
      ci/Jenkinsfile                                                  (managed)
      ci/azure-pipelines.yml                                          (managed)
      ci/gitlab-ci.yml                                                (managed)
      results/                      k6 summaries, gitignored
      .gitignore
    .github/workflows/perf-<framework>.yml                            (managed)

"created once" files are never overwritten, so teams can edit them. "managed" files
are regenerated on every export so new tests and secrets are always wired in.

Secrets: static values of auth-like headers (Authorization, API keys, cookies...)
are NOT written to the repository. The script reads them from environment
variables named PERF_HEADER_<NAME>, which CI provides from its secret store, and
it refuses to start if one is missing. A final scan aborts the export if any real
secret value (or, when not committed, any data-file content) ended up in a file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from perfagent.contracts.load_model import LoadModel
from perfagent.generator import render
from perfagent.runner.k6_binary import _ARCHIVES, K6_VERSION

from . import templates

ALL_CI = ("github", "jenkins", "azure", "gitlab")

_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9_-]{0,59}$")
_SECRET_HINT = re.compile(
    r"auth|token|key|secret|cookie|session|password|passwd|signature|credential", re.I
)
_PLACEHOLDER = re.compile(r"\$\{[^}]+\}")
_SENTINEL = "__PERFAGENT_ENV__{}__"


class ExportError(ValueError):
    """Raised for bad input or when the export would leak a secret."""


@dataclass
class ExportResult:
    framework: str
    test: str
    files: list[str] = field(default_factory=list)      # repo-relative paths written
    required_secrets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- names

def slugify(name: str, kind: str = "name") -> str:
    """Turn a user-given name into a safe folder name, or raise ExportError.

    'Payments Perf Suite' -> 'payments-perf-suite'. Path separators, '..', and
    anything outside [a-z0-9_-] are removed so a name can never escape the repo.
    """
    slug = re.sub(r"[^a-z0-9_-]+", "-", (name or "").strip().lower()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)[:60].strip("-_")
    if not _SLUG_OK.match(slug):
        raise ExportError(
            f"{kind} {name!r} is not usable; use letters, numbers, '-' or '_' (max 60)"
        )
    return slug


def secret_env_name(header: str) -> str:
    return "PERF_HEADER_" + re.sub(r"[^A-Z0-9]+", "_", header.upper()).strip("_")


def is_secret_header(header: str, value: str) -> bool:
    """Static values of auth-like headers are secrets. Values built from ${vars}
    (correlated at run time, e.g. 'Bearer ${token}') contain nothing secret."""
    if not isinstance(value, str) or _PLACEHOLDER.search(value):
        return False
    return bool(_SECRET_HINT.search(header))


# ------------------------------------------------------------------------ rendering

def render_export_script(model: LoadModel) -> tuple[str, dict[str, str], LoadModel]:
    """Render the k6 script with secret header values replaced by __ENV lookups.

    Returns (script, {ENV_NAME: header_name}, sanitized_model_for_plan_json).
    """
    secrets: dict[str, str] = {}
    export_headers: dict[str, str] = {}
    plan_headers: dict[str, str] = {}
    for name, value in (model.headers or {}).items():
        if is_secret_header(name, value):
            env = secret_env_name(name)
            secrets[env] = name
            export_headers[name] = _SENTINEL.format(env)
            plan_headers[name] = f"<from environment variable {env}>"
        else:
            export_headers[name] = value
            plan_headers[name] = value

    render_model = model.model_copy(update={"headers": export_headers})
    _filename, script = render(render_model, "k6")

    for env in secrets:
        quoted = json.dumps(_SENTINEL.format(env))
        if quoted not in script:  # renderer changed shape; never silently ship a literal
            raise ExportError(f"could not wire secret {env} into the script")
        script = script.replace(quoted, f"(__ENV.{env} || '')")

    guard = templates.secret_guard(sorted(secrets))
    anchor = "const errorRate = new Rate('errors');"
    if guard:
        if anchor not in script:
            raise ExportError("unexpected k6 script layout; cannot add secret checks")
        script = script.replace(anchor, anchor + "\n" + guard, 1)

    header = (
        "// Exported by PerfAgent for CI/CD. Regenerate from PerfAgent rather than\n"
        "// editing by hand, so the script stays in step with its approved plan.\n"
    )
    script = header + script
    sanitized = model.model_copy(update={"headers": plan_headers})
    return script, secrets, sanitized


# ------------------------------------------------------------------------- building

def _write(root: Path, rel: str, content: str, result: ExportResult, *, overwrite: bool = True,
           executable: bool = False) -> None:
    path = root / rel
    if path.exists() and not overwrite:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(path.stat().st_mode | 0o111)
    result.files.append(rel)


def _read_env_base_url(env_file: Path) -> str | None:
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("BASE_URL="):
            return line.split("=", 1)[1].strip()
    return None


def _all_tests(fw_dir: Path) -> dict[str, dict]:
    """Read test.json of every test already in the framework (from earlier exports)."""
    tests: dict[str, dict] = {}
    tdir = fw_dir / "tests"
    if tdir.is_dir():
        for meta in sorted(tdir.glob("*/test.json")):
            try:
                tests[meta.parent.name] = json.loads(meta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                tests[meta.parent.name] = {}
    return tests


def build_framework(
    repo_root: Path,
    *,
    framework_name: str,
    test_name: str,
    model: LoadModel,
    plan_id: str,
    script_id: str,
    data_file: tuple[str, str] | None = None,   # (filename, content)
    include_data: bool = False,
    ci: list[str] | tuple[str, ...] = ALL_CI,
) -> ExportResult:
    """Write (or update) the framework under repo_root and return what was written."""
    fw = slugify(framework_name, "framework name")
    test = slugify(test_name, "test name")
    ci_set = {c.lower() for c in ci}
    unknown = ci_set - set(ALL_CI)
    if unknown:
        raise ExportError(f"unknown CI option(s): {', '.join(sorted(unknown))}")

    result = ExportResult(framework=fw, test=test)
    fw_dir = repo_root / fw
    _check_folder_is_ours(repo_root, fw)
    fw_rel = fw + "/"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    script, secrets, sanitized = render_export_script(model)
    result.required_secrets = sorted(secrets)

    # ---- the test itself -------------------------------------------------------
    tdir = f"{fw_rel}tests/{test}/"
    _write(repo_root, tdir + "loadtest.js", script, result)
    _write(repo_root, tdir + "plan.json", sanitized.model_dump_json(indent=2) + "\n", result)

    data_meta = None
    if model.data_file:
        fname = model.data_file.filename
        if "/" in fname or "\\" in fname or fname.startswith("."):
            raise ExportError(f"unsafe data file name {fname!r}")
        committed = bool(include_data and data_file)
        data_meta = {"filename": fname, "rows": model.data_file.row_count, "committed": committed}
        if committed:
            _write(repo_root, tdir + fname, data_file[1], result)  # type: ignore[index]
            result.warnings.append(
                f"Test data '{fname}' was committed to Git. Make sure it holds no real customer data."
            )
        else:
            _write(repo_root, tdir + ".gitignore", f"# test data is supplied by CI, never committed\n{fname}\n", result)
            result.warnings.append(
                f"Test data '{fname}' was NOT committed. CI must place it in {tdir} before the run."
            )

    test_meta = {
        "test": test,
        "plan_id": plan_id,
        "script_id": script_id,
        "exported_at": now,
        "target_base_url": model.target_base_url,
        "profile": model.load_profile.type.value,
        "peak_users": model.load_profile.peak_users,
        "duration_seconds": model.load_profile.total_seconds,
        "thresholds": [t.model_dump() for t in model.thresholds],
        "required_secrets": result.required_secrets,
        "data_file": data_meta,
    }
    _write(repo_root, tdir + "test.json", json.dumps(test_meta, indent=2) + "\n", result)

    # ---- framework-wide files ----------------------------------------------------
    tests = _all_tests(fw_dir)
    tests[test] = test_meta
    all_secrets = sorted({s for t in tests.values() for s in t.get("required_secrets", [])})

    env_file = fw_dir / "environments" / "dev.env"
    existing = _read_env_base_url(env_file)
    if existing and existing.rstrip("/") != model.target_base_url.rstrip("/"):
        result.warnings.append(
            f"environments/dev.env sets BASE_URL={existing}, but this test targets "
            f"{model.target_base_url}. The env file wins when the tests run."
        )
    _write(repo_root, f"{fw_rel}environments/dev.env",
           templates.env_file("dev", model.target_base_url), result, overwrite=False)

    manifest = {
        "framework": fw,
        "generator": "PerfAgent",
        "tool": "k6",
        "k6_version": K6_VERSION,
        "updated_at": now,
        "tests": {name: {k: meta.get(k) for k in ("plan_id", "script_id", "exported_at", "target_base_url")}
                  for name, meta in sorted(tests.items())},
    }
    _write(repo_root, f"{fw_rel}perfagent.json", json.dumps(manifest, indent=2) + "\n", result)

    _write(repo_root, f"{fw_rel}README.md",
           templates.readme(fw, sorted(tests), all_secrets, sorted(ci_set)), result, overwrite=False)
    _write(repo_root, f"{fw_rel}.gitignore", templates.GITIGNORE, result, overwrite=False)
    _write(repo_root, f"{fw_rel}results/.gitkeep", "", result, overwrite=False)
    _write(repo_root, f"{fw_rel}scripts/run-tests.sh", templates.RUN_SH, result, executable=True)
    _write(repo_root, f"{fw_rel}scripts/run-tests.ps1", templates.RUN_PS1, result)

    k6_tar, k6_sha = _ARCHIVES[("linux", "amd64")]
    k6_win_zip, k6_win_sha = _ARCHIVES[("windows", "amd64")]
    ctx = {"fw": fw, "secrets": all_secrets, "k6_version": K6_VERSION,
           "k6_tar": k6_tar, "k6_sha": k6_sha, "k6_win_zip": k6_win_zip, "k6_win_sha": k6_win_sha}
    if "github" in ci_set:
        _write(repo_root, f".github/workflows/perf-{fw}.yml", templates.github(ctx), result)
    if "jenkins" in ci_set:
        _write(repo_root, f"{fw_rel}ci/Jenkinsfile", templates.jenkins(ctx), result)
    if "azure" in ci_set:
        _write(repo_root, f"{fw_rel}ci/azure-pipelines.yml", templates.azure(ctx), result)
    if "gitlab" in ci_set:
        _write(repo_root, f"{fw_rel}ci/gitlab-ci.yml", templates.gitlab(ctx), result)

    # ---- last line of defence: nothing secret may be in any written file ---------
    forbidden = [v for n, v in (model.headers or {}).items() if is_secret_header(n, v) and len(v) >= 6]
    if data_file and not (include_data and data_file):
        forbidden += [ln.strip() for ln in data_file[1].splitlines()[1:] if len(ln.strip()) >= 8][:500]
    scan_for_leaks(repo_root, result.files, forbidden)
    return result


def _check_folder_is_ours(repo_root: Path, fw: str) -> None:
    """Refuse to write into an existing folder (or workflow file) PerfAgent didn't create,
    so existing scripts in a client's repository can never be overwritten."""
    fw_dir = repo_root / fw
    if fw_dir.is_symlink() or (fw_dir.exists() and not fw_dir.is_dir()):
        raise ExportError(f"'{fw}' already exists in the repository and is not a folder; choose another framework name")
    if fw_dir.is_dir() and any(fw_dir.iterdir()):
        manifest = fw_dir / "perfagent.json"
        ours = False
        if manifest.is_file() and not manifest.is_symlink():
            try:
                ours = json.loads(manifest.read_text(encoding="utf-8")).get("generator") == "PerfAgent"
            except (OSError, json.JSONDecodeError):
                ours = False
        if not ours:
            raise ExportError(
                f"the folder '{fw}' already exists in the repository and was not created by "
                "PerfAgent; choose another framework name so existing files aren't overwritten"
            )
    wf = repo_root / ".github" / "workflows" / f"perf-{fw}.yml"
    if wf.exists():
        head = wf.read_text(encoding="utf-8", errors="ignore")[:200] if wf.is_file() else ""
        if "Managed by PerfAgent" not in head:
            raise ExportError(
                f".github/workflows/perf-{fw}.yml already exists and was not created by PerfAgent; "
                "choose another framework name"
            )


def scan_for_leaks(repo_root: Path, files: list[str], forbidden: list[str]) -> None:
    for rel in files:
        text = (repo_root / rel).read_text(encoding="utf-8", errors="ignore")
        for value in forbidden:
            if value and value in text:
                raise ExportError(f"export aborted: a secret or data value would be written to {rel}")