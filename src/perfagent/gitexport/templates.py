"""Text templates for the exported framework.

Plain strings with @@TOKEN@@ placeholders: CI YAML is full of ${{ }} and shell
${VAR}, so Jinja or str.format would fight with it.
"""

from __future__ import annotations


def _sub(text: str, **values: str) -> str:
    for key, value in values.items():
        if not isinstance(value, str):
            continue
        text = text.replace(f"@@{key.upper()}@@", value)
    return text


def secret_guard(secrets: list[str]) -> str:
    if not secrets:
        return ""
    names = ", ".join(f"'{s}'" for s in secrets)
    return (
        "\n// Secrets come from environment variables / CI secrets - never from Git.\n"
        f"const REQUIRED_SECRETS = [{names}];\n"
        "for (const name of REQUIRED_SECRETS) {\n"
        "  if (!__ENV[name]) {\n"
        "    throw new Error(`Missing required secret ${name}: set it as an environment variable or CI secret`);\n"
        "  }\n"
        "}\n"
    )


def env_file(env: str, base_url: str) -> str:
    return (
        f"# Settings for the '{env}' environment. Copy this file to staging.env, uat.env...\n"
        "# for other environments and pick one with: run-tests.sh <test|all> <env>\n"
        "# Never put secrets here - set PERF_HEADER_* as environment variables / CI secrets.\n"
        "# Variables already set in the environment take priority over this file.\n"
        f"BASE_URL={base_url}\n"
    )


GITIGNORE = """\
# k6 run output
results/*
!results/.gitkeep
# local secrets
*.local.env
.env
"""


RUN_SH = r"""#!/bin/sh
# Managed by PerfAgent - regenerated on every export, edit environments/ instead.
#
# Usage:  sh scripts/run-tests.sh [test-name|all] [environment]
#   sh scripts/run-tests.sh all dev
#   sh scripts/run-tests.sh checkout-peak uat
#
# Exit code: 0 = every test passed its thresholds, 1 = a test failed or errored,
# 2 = bad arguments. CI uses this exit code to pass or fail the build.
set -u
cd "$(dirname "$0")/.." || exit 2

TEST="${1:-all}"
ENVIRONMENT="${2:-dev}"
case "$TEST$ENVIRONMENT" in */*|*..*|*\\*) echo "Invalid test or environment name" >&2; exit 2 ;; esac

ENV_FILE="environments/${ENVIRONMENT}.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 2
fi

# Load KEY=VALUE lines. Values already set (e.g. CI secrets) are not overridden.
while IFS= read -r line || [ -n "$line" ]; do
  line=$(printf '%s' "$line" | tr -d '\r')
  case "$line" in ''|'#'*) continue ;; esac
  key=${line%%=*}
  value=${line#*=}
  case "$key" in ''|[0-9]*|*[!A-Za-z0-9_]*) echo "Skipping invalid line in $ENV_FILE" >&2; continue ;; esac
  eval "current=\${$key:-}"
  if [ -z "$current" ]; then export "$key=$value"; fi
done < "$ENV_FILE"

command -v k6 >/dev/null 2>&1 || { echo "k6 is not on PATH" >&2; exit 2; }
mkdir -p results

if [ "$TEST" = "all" ]; then
  TESTS=$(ls tests)
else
  TESTS=$TEST
fi

status=0
for t in $TESTS; do
  if [ ! -f "tests/$t/loadtest.js" ]; then
    echo "No such test: $t" >&2
    status=1
    continue
  fi
  echo "=== $t (environment: $ENVIRONMENT) ==="
  k6 run --summary-export "results/$t-summary.json" "tests/$t/loadtest.js"
  rc=$?
  case $rc in
    0)  echo "PASS   $t" ;;
    99) echo "FAIL   $t - thresholds breached"; status=1 ;;
    *)  echo "ERROR  $t - k6 exited with code $rc"; status=1 ;;
  esac
done
exit $status
"""


RUN_PS1 = r"""# Managed by PerfAgent - regenerated on every export, edit environments/ instead.
# Usage:  pwsh scripts/run-tests.ps1 [-Test all|<name>] [-Environment dev]
param(
  [string]$Test = "all",
  [string]$Environment = "dev"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if ("$Test$Environment" -match '[\\/]|\.\.') { Write-Error "Invalid test or environment name"; exit 2 }
$envFile = "environments/$Environment.env"
if (-not (Test-Path $envFile)) { Write-Error "Environment file not found: $envFile"; exit 2 }

foreach ($line in Get-Content $envFile) {
  $line = $line.Trim()
  if ($line -eq "" -or $line.StartsWith("#")) { continue }
  $key, $value = $line -split "=", 2
  if ($key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { continue }
  if (-not [Environment]::GetEnvironmentVariable($key)) {
    [Environment]::SetEnvironmentVariable($key, $value, "Process")
  }
}

if (-not (Get-Command k6 -ErrorAction SilentlyContinue)) { Write-Error "k6 is not on PATH"; exit 2 }
New-Item -ItemType Directory -Force -Path results | Out-Null

$tests = if ($Test -eq "all") { Get-ChildItem tests -Directory | ForEach-Object Name } else { @($Test) }
$status = 0
foreach ($t in $tests) {
  if (-not (Test-Path "tests/$t/loadtest.js")) { Write-Host "No such test: $t"; $status = 1; continue }
  Write-Host "=== $t (environment: $Environment) ==="
  & k6 run --summary-export "results/$t-summary.json" "tests/$t/loadtest.js"
  switch ($LASTEXITCODE) {
    0  { Write-Host "PASS   $t" }
    99 { Write-Host "FAIL   $t - thresholds breached"; $status = 1 }
    default { Write-Host "ERROR  $t - k6 exited with code $LASTEXITCODE"; $status = 1 }
  }
}
exit $status
"""


# --------------------------------------------------------------------------- CI

_INSTALL_K6 = """\
curl -fsSL -o /tmp/k6.tgz https://github.com/grafana/k6/releases/download/@@K6_VERSION@@/@@K6_TAR@@
echo "@@K6_SHA@@  /tmp/k6.tgz" | sha256sum -c -
tar -xzf /tmp/k6.tgz -C /tmp"""


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def github(ctx: dict) -> str:
    secrets = "".join(
        f"      {s}: ${{{{ secrets.{s} }}}}\n" for s in ctx["secrets"]
    ) or "      # no secrets needed by the current tests\n"
    install = _sub(_INSTALL_K6, **ctx) + "\nsudo mv /tmp/@@K6_DIR@@/k6 /usr/local/bin/k6\nk6 version"
    body = """\
# Managed by PerfAgent - regenerated on every export of the '@@FW@@' framework.
# Add the secrets listed under env: in Settings > Secrets and variables > Actions.
name: "Performance - @@FW@@"

on:
  workflow_dispatch:
    inputs:
      test:
        description: "Test folder under @@FW@@/tests, or 'all'"
        default: all
        required: true
      environment:
        description: "Environment file under @@FW@@/environments (without .env)"
        default: dev
        required: true
  # Uncomment to run on every pull request that touches the framework:
  # pull_request:
  #   paths: ["@@FW@@/**"]
  # Uncomment for a nightly run (UTC):
  # schedule:
  #   - cron: "30 20 * * *"

jobs:
  performance:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    defaults:
      run:
        working-directory: @@FW@@
    env:
      TEST: ${{ inputs.test || 'all' }}
      PERF_ENV: ${{ inputs.environment || 'dev' }}
@@SECRETS@@    steps:
      - uses: actions/checkout@v4

      - name: Install k6 @@K6_VERSION@@ (pinned, checksum-verified)
        run: |
@@INSTALL@@

      - name: Run performance tests
        run: sh scripts/run-tests.sh "$TEST" "$PERF_ENV"

      - name: Upload k6 results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: perf-results-@@FW@@
          path: @@FW@@/results/
"""
    out = body.replace("@@SECRETS@@", secrets).replace("@@INSTALL@@", _indent(install, 10))
    return _sub(out, fw=ctx["fw"], k6_version=ctx["k6_version"],
                k6_dir=ctx["k6_tar"].removesuffix(".tar.gz"))


def jenkins(ctx: dict) -> str:
    install = _sub(_INSTALL_K6, **ctx) + (
        '\nmkdir -p "$WORKSPACE/.bin" && mv /tmp/@@K6_DIR@@/k6 "$WORKSPACE/.bin/k6"'
    )
    run = 'sh \'PATH="$WORKSPACE/.bin:$PATH" sh scripts/run-tests.sh "$TEST" "$PERF_ENV"\''
    if ctx["secrets"]:
        creds = ",\n".join(
            f"              string(credentialsId: '{s}', variable: '{s}')" for s in ctx["secrets"]
        )
        run_block = (
            "            withCredentials([\n" + creds + "\n            ]) {\n"
            f"              {run}\n            }}"
        )
    else:
        run_block = f"            {run}"
    body = """\
// Managed by PerfAgent - regenerated on every export of the '@@FW@@' framework.
// In your Jenkins job set "Script Path" to: @@FW@@/ci/Jenkinsfile
// Create a "Secret text" credential for each secret below (ID = variable name).
pipeline {
  agent any
  parameters {
    string(name: 'TEST', defaultValue: 'all', description: "Test folder under @@FW@@/tests, or 'all'")
    string(name: 'PERF_ENV', defaultValue: 'dev', description: 'Environment file under @@FW@@/environments')
  }
  options { timeout(time: 2, unit: 'HOURS') }
  stages {
    stage('Install k6') {
      steps {
        sh '''
@@INSTALL@@
'''
      }
    }
    stage('Performance tests') {
      steps {
        dir('@@FW@@') {
@@RUN@@
        }
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: '@@FW@@/results/*.json', allowEmptyArchive: true
    }
  }
}
"""
    out = body.replace("@@INSTALL@@", _indent(install, 10)).replace("@@RUN@@", run_block)
    return _sub(out, fw=ctx["fw"], k6_dir=ctx["k6_tar"].removesuffix(".tar.gz"))


def azure(ctx: dict) -> str:
    secrets = "".join(f"      {s}: $({s})\n" for s in ctx["secrets"])
    install = _sub(_INSTALL_K6, **ctx) + "\nsudo mv /tmp/@@K6_DIR@@/k6 /usr/local/bin/k6\nk6 version"
    body = """\
# Managed by PerfAgent - regenerated on every export of the '@@FW@@' framework.
# Create the pipeline from this file: @@FW@@/ci/azure-pipelines.yml
# Add each PERF_HEADER_* below as a secret pipeline variable (or a variable group).
trigger: none

parameters:
  - name: test
    displayName: "Test folder under @@FW@@/tests, or 'all'"
    type: string
    default: all
  - name: environment
    displayName: "Environment file under @@FW@@/environments"
    type: string
    default: dev

pool:
  vmImage: ubuntu-latest

steps:
  - checkout: self

  - bash: |
@@INSTALL@@
    displayName: Install k6 @@K6_VERSION@@ (pinned, checksum-verified)

  - bash: sh scripts/run-tests.sh "$TEST" "$PERF_ENV"
    displayName: Run performance tests
    workingDirectory: @@FW@@
    env:
      TEST: ${{ parameters.test }}
      PERF_ENV: ${{ parameters.environment }}
@@SECRETS@@

  - task: PublishPipelineArtifact@1
    displayName: Publish k6 results
    condition: always()
    inputs:
      targetPath: @@FW@@/results
      artifact: perf-results-@@FW@@
"""
    out = body.replace("@@INSTALL@@", _indent(install, 6)).replace("@@SECRETS@@\n", secrets)
    return _sub(out, fw=ctx["fw"], k6_version=ctx["k6_version"],
                k6_dir=ctx["k6_tar"].removesuffix(".tar.gz"))


def gitlab(ctx: dict) -> str:
    note = (" ".join(ctx["secrets"]) + " as masked CI/CD variables") if ctx["secrets"] else "no secrets"
    body = """\
# Managed by PerfAgent - regenerated on every export of the '@@FW@@' framework.
# Include it from your root .gitlab-ci.yml:
#   include:
#     - local: '@@FW@@/ci/gitlab-ci.yml'
# Needs: @@NOTE@@ (Settings > CI/CD > Variables).
perf-@@FW@@:
  stage: test
  image:
    name: grafana/k6:@@K6_NUM@@
    entrypoint: [""]
  variables:
    TEST: "all"
    PERF_ENV: "dev"
  rules:
    - when: manual
  script:
    - cd @@FW@@
    - sh scripts/run-tests.sh "$TEST" "$PERF_ENV"
  artifacts:
    when: always
    paths:
      - @@FW@@/results/
"""
    return _sub(body, fw=ctx["fw"], note=note, k6_num=ctx["k6_version"].lstrip("v"))


def readme(fw: str, tests: list[str], secrets: list[str], ci: list[str]) -> str:
    test_lines = "\n".join(f"- `{t}`" for t in tests)
    secret_lines = "\n".join(f"- `{s}`" for s in secrets) or "- none for the current tests"
    ci_files = {
        "github": f"- **GitHub Actions:** `.github/workflows/perf-{fw}.yml` (Actions tab > Run workflow)",
        "jenkins": f"- **Jenkins:** set the job's Script Path to `{fw}/ci/Jenkinsfile`",
        "azure": f"- **Azure DevOps:** new pipeline from `{fw}/ci/azure-pipelines.yml`",
        "gitlab": f"- **GitLab:** `include: local: '{fw}/ci/gitlab-ci.yml'` in your root `.gitlab-ci.yml`",
    }
    ci_lines = "\n".join(ci_files[c] for c in ci if c in ci_files)
    return f"""# {fw} - performance test framework

Generated by PerfAgent. Each folder under `tests/` is one approved load test,
written as a k6 script. Thresholds from the approved plan are built into each
script, so a run that breaches them exits with code 99 and fails the build.

## Tests

{test_lines}

(This list was written when the framework was created; `perfagent.json` always
holds the current list.)

## Run locally

Install k6 (https://grafana.com/docs/k6/latest/set-up/install-k6/), set any
secrets, then:

```sh
export PERF_HEADER_AUTHORIZATION="Bearer ..."   # example
sh scripts/run-tests.sh all dev                  # every test against dev
sh scripts/run-tests.sh <test-name> uat          # one test against uat
```

On Windows: `pwsh scripts/run-tests.ps1 -Test all -Environment dev`

Results are written to `results/<test>-summary.json`.

## Environments

`environments/<name>.env` holds non-secret settings such as `BASE_URL`. Copy
`dev.env` to create `staging.env`, `uat.env` and so on.

## Secrets

Secrets are never stored in this repository. Set these as environment variables
locally, or as secrets in your CI system:

{secret_lines}

A test refuses to start if a secret it needs is missing.

## CI/CD

{ci_lines}

Files marked "Managed by PerfAgent" are regenerated whenever a test is exported
again; put your own changes in `environments/` or in separate pipeline files.

## Updating a test

Change the plan in PerfAgent and export again with the same framework and test
name. PerfAgent commits the new version, so Git history shows every change.
"""