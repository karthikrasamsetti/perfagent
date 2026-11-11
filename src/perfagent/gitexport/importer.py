"""Import performance tests from a Git repository back into PerfAgent.

Two kinds of things are found in a repository:

1. PerfAgent frameworks: any folder with a perfagent.json written by PerfAgent.
   Each test's plan.json is loaded back as an editable plan. It then goes through
   the normal flow (review/approve -> generate -> run), so the approval gate and the
   deterministic generator still apply. Secrets were never committed, so the user
   supplies them again at import time; committed test data is imported too.
   If someone edited loadtest.js directly in Git, the import reports it: PerfAgent
   regenerates the script from the plan, so those hand edits are not carried over.

2. Other load-test scripts (k6 .js/.ts, Locust .py, JMeter .jmx) not made by
   PerfAgent. These are listed and can be viewed. A k6 script can then be loaded
   through the existing "Already have a k6 script?" path (POST /api/scripts/upload),
   after the user has seen it and given its target URL.

Everything read from the repository is untrusted input: paths are confined to the
clone, file sizes are capped, and plans are validated by the LoadModel contract.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from perfagent.contracts.load_model import LoadModel
from perfagent.data import DataValidationError, load_data

from .framework import ExportError, render_export_script

MAX_FILE_BYTES = 1_000_000        # plan/test/script files we will read
MAX_DATA_BYTES = 20_000_000       # committed test-data file
MAX_FILES_SCANNED = 20_000
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
              "target", ".idea", ".vscode", "results"}
_SECRET_PLACEHOLDER = re.compile(r"^<from environment variable ([A-Z0-9_]+)>$")
_K6_IMPORT = re.compile(r"""(from\s+['"]k6(/[\w-]+)?['"])|(require\(\s*['"]k6)""")
_LOCUST_IMPORT = re.compile(r"^\s*(from\s+locust\s+import|import\s+locust)\b", re.M)


# ------------------------------------------------------------------ safe file access

def safe_path(repo: Path, rel: str) -> Path:
    """Resolve a repo-relative path, refusing anything that leaves the clone."""
    if not rel or "\\" in rel or rel.startswith("/"):
        raise ExportError(f"invalid path {rel!r}")
    parts = PurePosixPath(rel).parts
    if any(p in ("..", "") for p in parts) or parts[0] == ".git":
        raise ExportError(f"invalid path {rel!r}")
    path = (repo / rel)
    root = repo.resolve()
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ExportError(f"invalid path {rel!r}")
    if path.is_symlink():
        raise ExportError(f"refusing to read a symlink: {rel}")
    return path


def read_text(repo: Path, rel: str, limit: int = MAX_FILE_BYTES) -> str:
    path = safe_path(repo, rel)
    if not path.is_file():
        raise ExportError(f"file not found in repository: {rel}")
    if path.stat().st_size > limit:
        raise ExportError(f"{rel} is too large to import ({path.stat().st_size} bytes)")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ExportError(f"{rel} is not UTF-8 text") from e


# ------------------------------------------------------------------ scanning

@dataclass
class TestInfo:
    test: str
    target_base_url: str = ""
    profile: str = ""
    peak_users: int | None = None
    duration_seconds: int | None = None
    required_secrets: list[str] = field(default_factory=list)
    data_file: str | None = None
    data_committed: bool = False
    exported_at: str = ""
    edited_in_git: bool = False       # loadtest.js differs from what the plan generates
    error: str | None = None          # plan.json missing/invalid: shown, not importable


@dataclass
class FrameworkInfo:
    name: str
    path: str                         # repo-relative folder
    tool: str = "k6"
    tests: list[TestInfo] = field(default_factory=list)


@dataclass
class OtherScript:
    path: str
    tool: str                         # k6 | locust | jmeter
    size: int


@dataclass
class RepoScan:
    commit: str
    frameworks: list[FrameworkInfo] = field(default_factory=list)
    other_scripts: list[OtherScript] = field(default_factory=list)
    truncated: bool = False


def _rel(repo: Path, p: Path) -> str:
    return p.relative_to(repo).as_posix()


def _load_plan(repo: Path, test_dir: str) -> LoadModel:
    raw = read_text(repo, f"{test_dir}/plan.json")
    try:
        return LoadModel.model_validate_json(raw)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(x) for x in first.get("loc", ()))
        raise ExportError(f"plan.json is not a valid plan ({where}: {first.get('msg')})") from None


def _scan_test(repo: Path, fw_rel: str, test_dir: Path) -> TestInfo:
    name = test_dir.name
    rel = f"{fw_rel}/tests/{name}" if fw_rel else f"tests/{name}"
    info = TestInfo(test=name)
    try:
        meta = json.loads(read_text(repo, f"{rel}/test.json"))
        info.exported_at = str(meta.get("exported_at", ""))
    except (ExportError, json.JSONDecodeError):
        meta = {}
    try:
        model = _load_plan(repo, rel)
    except ExportError as e:
        info.error = str(e)
        return info

    info.target_base_url = model.target_base_url
    info.profile = model.load_profile.type.value
    info.peak_users = model.load_profile.peak_users
    info.duration_seconds = model.load_profile.total_seconds
    info.required_secrets = sorted(
        m.group(1) for v in (model.headers or {}).values()
        if (m := _SECRET_PLACEHOLDER.match(str(v)))
    )
    if model.data_file:
        info.data_file = model.data_file.filename
        try:
            info.data_committed = safe_path(repo, f"{rel}/{model.data_file.filename}").is_file()
        except ExportError:
            info.data_committed = False
    try:
        script = read_text(repo, f"{rel}/loadtest.js")
        info.edited_in_git = script != render_export_script(model)[0]
    except ExportError:
        info.edited_in_git = True
    return info


def scan_repo(repo: Path, commit: str) -> RepoScan:
    scan = RepoScan(commit=commit)
    framework_dirs: list[Path] = []
    candidates: list[Path] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
        here = Path(dirpath)
        for fname in sorted(filenames):
            seen += 1
            if seen > MAX_FILES_SCANNED:
                scan.truncated = True
                break
            p = here / fname
            if p.is_symlink():
                continue
            if fname == "perfagent.json":
                framework_dirs.append(here)
            elif p.suffix in (".js", ".ts", ".py", ".jmx"):
                candidates.append(p)
        if scan.truncated:
            break

    managed: list[Path] = []
    for fw_dir in framework_dirs:
        fw_rel = _rel(repo, fw_dir) if fw_dir != repo else ""
        try:
            manifest = json.loads(read_text(repo, f"{fw_rel}/perfagent.json" if fw_rel else "perfagent.json"))
        except (ExportError, json.JSONDecodeError):
            continue
        if manifest.get("generator") != "PerfAgent":
            continue
        fw = FrameworkInfo(name=str(manifest.get("framework") or fw_dir.name),
                           path=fw_rel or ".", tool=str(manifest.get("tool", "k6")))
        tests_dir = fw_dir / "tests"
        if tests_dir.is_dir():
            for td in sorted(d for d in tests_dir.iterdir() if d.is_dir() and not d.is_symlink()):
                if (td / "plan.json").exists() or (td / "test.json").exists():
                    fw.tests.append(_scan_test(repo, fw_rel, td))
        scan.frameworks.append(fw)
        managed.append(fw_dir)

    for p in candidates:
        if any(m == p or m in p.parents for m in managed):
            continue
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        tool = None
        if p.suffix in (".js", ".ts") and _K6_IMPORT.search(head):
            tool = "k6"
        elif p.suffix == ".py" and _LOCUST_IMPORT.search(head):
            tool = "locust"
        elif p.suffix == ".jmx" and "<jmeterTestPlan" in head[:2000]:
            tool = "jmeter"
        if tool:
            scan.other_scripts.append(OtherScript(path=_rel(repo, p), tool=tool, size=size))
    return scan


# ------------------------------------------------------------------ importing

@dataclass
class ImportedTest:
    model: LoadModel
    framework: str
    test: str
    data_file: tuple[str, str] | None = None     # (filename, content) if committed
    missing_secrets: list[str] = field(default_factory=list)
    edited_in_git: bool = False
    warnings: list[str] = field(default_factory=list)


def import_test(repo: Path, framework_path: str, test: str,
                secrets: dict[str, str] | None = None) -> ImportedTest:
    """Load one PerfAgent test from a cloned repo as a plan, restoring secrets."""
    secrets = {k: v for k, v in (secrets or {}).items() if v}
    fw_rel = "" if framework_path in ("", ".") else framework_path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", test or ""):
        raise ExportError(f"invalid test name {test!r}")
    manifest_rel = f"{fw_rel}/perfagent.json" if fw_rel else "perfagent.json"
    try:
        manifest = json.loads(read_text(repo, manifest_rel))
    except json.JSONDecodeError as e:
        raise ExportError("perfagent.json is not valid JSON") from e
    if manifest.get("generator") != "PerfAgent":
        raise ExportError(f"{framework_path} is not a PerfAgent framework")

    test_rel = f"{fw_rel}/tests/{test}" if fw_rel else f"tests/{test}"
    model = _load_plan(repo, test_rel)
    result = ImportedTest(model=model, framework=str(manifest.get("framework") or framework_path),
                          test=test)

    try:
        result.edited_in_git = read_text(repo, f"{test_rel}/loadtest.js") != render_export_script(model)[0]
    except ExportError:
        result.edited_in_git = True
    if result.edited_in_git:
        result.warnings.append(
            "loadtest.js was edited directly in Git. PerfAgent rebuilds the script from the "
            "plan, so those hand edits are not imported - put the change in the plan instead."
        )

    headers: dict[str, str] = {}
    for name, value in (model.headers or {}).items():
        m = _SECRET_PLACEHOLDER.match(str(value))
        if not m:
            headers[name] = value
        elif m.group(1) in secrets:
            headers[name] = secrets[m.group(1)]
        else:
            result.missing_secrets.append(m.group(1))
    if result.missing_secrets:
        result.warnings.append(
            "No value given for " + ", ".join(result.missing_secrets)
            + "; those headers were left out. Add them under Custom headers before generating."
        )

    if model.data_file:
        fname = model.data_file.filename
        data_rel = f"{test_rel}/{fname}"
        try:
            exists = safe_path(repo, data_rel).is_file()
        except ExportError:
            exists = False
        if exists:
            content = read_text(repo, data_rel, MAX_DATA_BYTES)
            try:
                load_data(fname, content)
            except DataValidationError as e:
                raise ExportError(f"committed data file {fname} is invalid: {e}") from e
            result.data_file = (fname, content)
        else:
            result.warnings.append(
                f"Test data '{fname}' is not in Git. Upload it in Step 1 before generating."
            )

    result.model = model.model_copy(update={"headers": headers})
    return result


def read_other_script(repo: Path, rel: str) -> tuple[str, str]:
    """Return (tool, content) of a non-PerfAgent script, for read-only viewing."""
    content = read_text(repo, rel)
    if rel.endswith((".js", ".ts")) and _K6_IMPORT.search(content):
        return "k6", content
    if rel.endswith(".py") and _LOCUST_IMPORT.search(content):
        return "locust", content
    if rel.endswith(".jmx") and "<jmeterTestPlan" in content[:2000]:
        return "jmeter", content
    raise ExportError(f"{rel} is not a k6, Locust or JMeter script")