# Git and Jenkins integrations

[Back to PerfAgent](../README.md)

## Save tests to Git and import them back

### Save to Git (Step 3)

After generating a k6 script, the **Save to Git for CI/CD** card exports it into a named
framework and pushes it. Enter a framework name, a test name, the repository URL, branch
and an access token with push rights (not needed for SSH URLs). The token is used for that
push only and is never stored; no user name is needed. The exported script is built by the
**same deterministic generator** used in the app, so it carries your assertions, correlation,
dynamic data, GraphQL and TLS settings — with secret header values swapped for CI-provided
environment variables.

```
<framework>/
  tests/<test>/loadtest.js · plan.json · test.json
  environments/dev.env          BASE_URL (copy for uat.env, staging.env, …)
  scripts/run-tests.sh · .ps1   run one test or all
  ci/Jenkinsfile · azure-pipelines.yml · gitlab-ci.yml
  README.md · perfagent.json
.github/workflows/perf-<framework>.yml
```

* Pushing into an existing repository only **adds** files; nothing else is touched.
  PerfAgent refuses to write into a folder it didn't create, so pick a new framework name.
* Secret header values are never committed: the script reads `PERF_HEADER_<NAME>` from the
  environment and stops if one is missing. Add them as CI secrets.
* Test data is only committed if you tick the box. A final scan aborts the push if any secret
  value ended up in a file.
* Thresholds are enforced by k6, so a breach exits with code 99 and fails the pipeline.
* Exporting again with the same names updates the test in a new commit.
* **Download framework (.zip)** gives the same files without Git.
* Uploaded scripts (the "My k6 script" tab) can't be saved to Git yet.

### Import from Git (a tab on Step 1)

**Import an existing test from Git** lists what's on a branch:

* **Tests PerfAgent saved** — *Import* loads one back as an editable plan (Step 2), asking
  again for its secrets; committed test data comes along. Tests whose `loadtest.js` was
  edited by hand are flagged, because PerfAgent rebuilds scripts from the plan.
* **Other load-test scripts** (k6, Locust, JMeter) — *View* shows them; a k6 script can be
  loaded with *Use this script*, exactly like the "My k6 script" tab.

Every push and import is recorded in the activity log. The server needs `git` 2.31+.
Admins can set `GIT_ALLOWED_HOSTS`, `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` in `.env`.

API: `POST /api/scripts/{id}/export/git`, `POST /api/scripts/{id}/export/zip`,
`GET /api/export/settings`, `POST /api/git/scan`, `POST /api/git/import`, `POST /api/git/script`.

## Run in Jenkins (Step 3)

The **Run in Jenkins** card triggers the Jenkins pipeline for a test you saved to Git and
follows it in PerfAgent: queued → running → finished, with the console log streaming in, a
link to the build, and — when it finishes — the k6 results the Jenkinsfile archived
(requests, req/sec, error rate, avg / p95 / max, each threshold, and a PASS / FAIL verdict).
**Stop** aborts the build.

Enter the Jenkins URL, your Jenkins user name, an **API token** (Jenkins → your name →
Security → API Token), the job name (`folder/job` for folders), the test (or `all`) and the
environment. The token is sent with each call and never stored.

**Set up Jenkins job** creates the Pipeline job — or updates it if it exists — pointing at
`<framework>/ci/Jenkinsfile` in your repository, with the `TEST` and `PERF_ENV` parameters
declared, so no manual first build is needed (needs the *Job/Create* permission; give a Git
credentials ID for private repositories). If you create the job by hand instead, run it once
in Jenkins so it learns its parameters.

Jenkins side: Pipeline + Git plugins; a Linux/macOS agent with `curl`, `sha256sum` and `tar`, or a
Windows agent with PowerShell (the Jenkinsfile picks the right one and downloads k6 once per
workspace, verifying its checksum); and a
*Secret text* credential for each secret the test needs (e.g. `PERF_HEADER_AUTHORIZATION`).
PerfAgent must be able to reach Jenkins, and Jenkins must reach Git and the application.
Admins can restrict which Jenkins servers may be called with `JENKINS_ALLOWED_HOSTS`.

API: `POST /api/jenkins/trigger`, `/api/jenkins/status`, `/api/jenkins/stop`, `/api/jenkins/setup-job`.

### Saved Git and Jenkins details

PerfAgent remembers the **non-secret** details you used, per plan, so you don't retype them:
the Git repository, branch, framework, test and pipelines; the Jenkins URL, user name, job,
test and environment, and the job set-up details (repository, branch, framework, Git
credentials ID). They are saved only after something **succeeds** — a push, an import, a
Jenkins run or job set-up — and filled in when you open the plan again from *Saved plans*.
A brand-new plan starts with the last-used repository, branch, Jenkins URL, user name,
Git credentials ID and environment.

**Never saved:** Git tokens, Jenkins API tokens and test secrets — you enter those each time.
URLs that contain credentials are refused. *Forget saved details* on each card removes them
(for that plan and from the last-used defaults). They live in the `integration_settings`
table, which is added automatically to existing databases.

API: `GET /api/integrations?plan_id=…`, `DELETE /api/integrations?plan_id=…&section=git|jenkins|all`.
