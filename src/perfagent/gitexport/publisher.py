"""Commit and push an exported framework to a Git repository.

Uses the git command line (git 2.31+), so it works with GitHub, GitLab, Azure
DevOps, Bitbucket or any self-hosted Git server, over HTTPS or SSH.

Credentials:
  * HTTPS: the access token the user typed in the UI is sent as an HTTP Basic auth header through
    git's GIT_CONFIG_* environment variables. It never appears in the remote URL,
    in the process list (argv), in .git/config, in the database, or in any error
    message we return. It is used for this one push and then discarded.
  * SSH (git@host:org/repo.git): uses the server's SSH key; no token needed.

Every publish works in a fresh temporary clone that is deleted afterwards, so
nothing about the repository is left on the PerfAgent server.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .framework import ExportError

_SSH_URL = re.compile(r"^(?:ssh://)?[A-Za-z0-9._-]+@([A-Za-z0-9.-]+)[:/][A-Za-z0-9._/~-]+$")
_BRANCH_OK = re.compile(r"^(?!-)(?!.*\.\.)(?!.*//)[A-Za-z0-9._/-]{1,100}(?<![./])$")
_TIMEOUT = 180


@dataclass
class GitTarget:
    repo_url: str
    branch: str = "main"
    token: str = ""                     # access token for HTTPS; empty for SSH
    author_name: str = "PerfAgent"
    author_email: str = "perfagent@localhost"
    allowed_hosts: list[str] = field(default_factory=list)  # empty = any host
    allow_local: bool = False           # file:// and local paths, for tests only


@dataclass
class PublishResult:
    repo_url: str
    branch: str
    commit: str | None        # None when nothing changed
    changed: bool
    files: list[str]


class GitPublishError(RuntimeError):
    pass


def validate_target(t: GitTarget) -> None:
    url = (t.repo_url or "").strip()
    if not url:
        raise ExportError("enter the Git repository URL")
    if not _BRANCH_OK.match(t.branch or ""):
        raise ExportError(f"invalid branch name {t.branch!r}")

    host: str | None
    if url.startswith("https://"):
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            raise ExportError("enter the token in the Access token field, not inside the repository URL")
        host = parsed.hostname
    elif m := _SSH_URL.match(url):
        host = m.group(1)
    elif t.allow_local and (url.startswith("file://") or Path(url).exists()):
        return
    else:
        raise ExportError("repository URL must be https://... or an SSH URL like git@host:org/repo.git")

    allowed = [h.strip().lower() for h in t.allowed_hosts if h.strip()]
    if allowed and (host or "").lower() not in allowed:
        raise ExportError(f"Git host {host!r} is not in the allowed list ({', '.join(allowed)})")


def token_username(repo_url: str) -> str:
    """The user name sent with an access token. Git hosts check only the token, but
    HTTPS Basic auth needs some user name, and a few hosts expect a specific one."""
    host = (urlparse(repo_url).hostname or "").lower()
    if host == "github.com" or host.endswith(".github.com") or "github" in host:
        return "x-access-token"
    if "gitlab" in host:
        return "oauth2"
    if host == "bitbucket.org":
        return "x-token-auth"
    # Azure DevOps, Gitea, Bitbucket Server and most others accept any name with a token.
    return "perfagent"


def _git_env(t: GitTarget) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}
    env.update({
        "GIT_TERMINAL_PROMPT": "0",          # never hang waiting for a password prompt
        "GCM_INTERACTIVE": "never",
        "GIT_AUTHOR_NAME": t.author_name, "GIT_AUTHOR_EMAIL": t.author_email,
        "GIT_COMMITTER_NAME": t.author_name, "GIT_COMMITTER_EMAIL": t.author_email,
    })
    if t.token and t.repo_url.startswith("https://"):
        basic = base64.b64encode(f"{token_username(t.repo_url)}:{t.token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
            "GIT_CONFIG_KEY_1": "credential.helper",   # don't let a helper store/override it
            "GIT_CONFIG_VALUE_1": "",
        })
    return env


class _Git:
    def __init__(self, t: GitTarget, cwd: Path):
        self.t, self.cwd, self.env = t, cwd, _git_env(t)
        self._hide = [s for s in (t.token, self.env.get("GIT_CONFIG_VALUE_0", "")) if s]

    def _scrub(self, text: str) -> str:
        for s in self._hide:
            text = text.replace(s, "***")
        return text.strip()[-800:]

    def __call__(self, *args: str, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
        try:
            proc = subprocess.run(
                ["git", *args], cwd=cwd or self.cwd, env=self.env,
                capture_output=True, text=True, timeout=_TIMEOUT,
            )
        except FileNotFoundError as e:
            raise GitPublishError("git is not installed on the PerfAgent server") from e
        except subprocess.TimeoutExpired as e:
            raise GitPublishError(f"git {args[0]} timed out after {_TIMEOUT}s") from e
        if check and proc.returncode != 0:
            raise GitPublishError(f"git {args[0]} failed: {self._scrub(proc.stderr or proc.stdout)}")
        return proc


def publish(
    target: GitTarget,
    build: Callable[[Path], list[str]],
    commit_message: str,
) -> PublishResult:
    """Clone the repo, let `build(repo_dir)` write files (returns their repo-relative
    paths), then commit and push them to target.branch."""
    validate_target(target)
    work = Path(tempfile.mkdtemp(prefix="perfagent_git_"))
    repo = work / "repo"
    git = _Git(target, work)
    try:
        heads = git("ls-remote", "--heads", target.repo_url, target.branch).stdout.strip()
        if heads:
            git("clone", "--depth", "1", "--branch", target.branch, "--single-branch",
                target.repo_url, str(repo))
        else:
            # Branch doesn't exist yet: start it from the default branch (or an empty repo).
            git("clone", "--depth", "1", target.repo_url, str(repo))
            git("checkout", "-b", target.branch, cwd=repo)

        files = build(repo)
        if not files:
            raise ExportError("nothing to export")
        git("add", "--", *files, cwd=repo)

        status = git("status", "--porcelain", cwd=repo).stdout.strip()
        if not status:
            return PublishResult(target.repo_url, target.branch, None, False, files)

        git("commit", "-m", commit_message, cwd=repo)
        push = git("push", "origin", f"HEAD:refs/heads/{target.branch}", check=False, cwd=repo)
        if push.returncode != 0:
            # Someone pushed in between: rebase our single commit on top and retry once.
            git("pull", "--rebase", "origin", target.branch, cwd=repo)
            git("push", "origin", f"HEAD:refs/heads/{target.branch}", cwd=repo)

        sha = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        return PublishResult(target.repo_url, target.branch, sha, True, files)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@contextmanager
def cloned_repo(target: GitTarget) -> Iterator[tuple[Path, str]]:
    """Read-only shallow clone of target.branch. Yields (repo_dir, commit_sha) and
    deletes the clone afterwards. Symlinks are checked out as plain text files, so a
    malicious repository can't point PerfAgent at files outside the clone."""
    validate_target(target)
    work = Path(tempfile.mkdtemp(prefix="perfagent_git_"))
    repo = work / "repo"
    git = _Git(target, work)
    try:
        heads = git("ls-remote", "--heads", target.repo_url, target.branch).stdout.strip()
        if not heads:
            raise ExportError(f"branch {target.branch!r} not found (or the repository is empty)")
        git("-c", "core.symlinks=false", "clone", "--depth", "1", "--branch", target.branch,
            "--single-branch", "--no-tags", target.repo_url, str(repo))
        sha = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        yield repo, sha
    finally:
        shutil.rmtree(work, ignore_errors=True)