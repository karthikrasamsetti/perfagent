# Local setup and verification

[Back to PerfAgent](../README.md)

## Prerequisites

| Requirement | Why | Check | Get it |
|---|---|---|---|
| **Python 3.11+** | The service is Python | `python --version` | <https://www.python.org/downloads/> |
| **uv** *(or pip)* | Dependency manager | `uv --version` | <https://docs.astral.sh/uv/getting-started/installation/> |
| **k6** *(optional)* | Runs & validates the load tests — **downloaded automatically** on first run if missing | `k6 version` | Not needed; see *k6 is installed automatically* below |
| **Git 2.31+** | Clone / push, and Save to Git / Import from Git | `git --version` | <https://git-scm.com/downloads> |
| **LLM API key** | AI planning + narration | — | [OpenAI](https://platform.openai.com/) · [Anthropic](https://console.anthropic.com/) |

> [!NOTE]
> - You **don't** need to install k6. On the first run or validation PerfAgent downloads the pinned, checksum-verified k6 into `~/.perfagent/bin/` (see below).
> - You **don't** need an API key to run the test suite — the tests mock the LLM.
> - Set a **spend cap** on your provider account before using the AI features.

---

## Setup

<details>
<summary><b>Option A — uv (recommended)</b></summary>

```bash
git clone https://github.com/karthikrasamsetti/perfagent.git
cd perfagent
uv sync
```
</details>

<details>
<summary><b>Option B — pip + venv</b></summary>

```bash
git clone https://github.com/karthikrasamsetti/perfagent.git
cd perfagent
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
```
</details>

Then create your environment file (`cp .env.example .env` on macOS/Linux or `Copy-Item .env.example .env` in PowerShell) and fill it in:

```ini
LLM_PROVIDER=openai             # or "anthropic"
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=
LOG_LEVEL=INFO
GUARDRAIL_DEBUG=0               # set 1 temporarily to log the (redacted) prompt sent to the AI
```

> Keep provider keys and target credentials in local server-side configuration. Commit only placeholders in `.env.example`.

---

## Running the app

**Terminal 1 — the agent (web UI + API):**
```bash
uv run uvicorn perfagent.api.app:app --reload --port 8080
```
Open **<http://127.0.0.1:8080>**.

**Terminal 2 — the built-in mock target (safe to load-test):**
```bash
uv run python -m perfagent.sample_target.app      # http://127.0.0.1:8000
```

Then follow **Describe → Review Plan → Verify → Run → Report**. For frontend development, run `npm ci` and `npm run dev` from `frontend/` while the API is running. See the [frontend guide](../frontend/README.md).

## First UI test

Start PerfAgent and the sample target using the commands above. Use port **8080** for the packaged UI or the URL printed by Vite for frontend development. The sample target runs on port **8000**.

1. Create a project and select **Open project**. Confirm the workspace shows its tests and the configured Git framework. The tree previews the export layout. **Import / sync Git** is where you browse a repository.
2. Choose **Create test**, give it a unique name, and enter `http://127.0.0.1:8000` and `POST /checkout` in Describe. Set the optional response check to `order_id`. The sample response contains that field. AI drafting uses the provider configured in `.env`.
3. Use a small workload such as **2 peak VUs for 15 seconds**. In Review, confirm the path, response check, load chart, and thresholds. **Preview sample requests** displays sample input. **Approve & continue to Verify** saves the script version.
4. Select **Verify test** and confirm the response check passes. Start the load test and compare the dashboard measurements with the saved report. Open the report and download the standalone HTML.
5. Return to the plan and approve it again without edits. Verify should show **Latest version reused — no changes**. Then change a threshold and approve again. From **Project workspace → View history**, confirm you can inspect or download the older script while Verify stays on the latest version. Smoke run artifacts have a separate group.

---

### k6 is installed automatically

PerfAgent looks for k6 in this order and uses the first one it finds:

1. `PERFAGENT_K6_PATH` — an explicit path to a k6 binary.
2. A bundled copy at `src/perfagent/runner/bin/<os>-<arch>/k6` (`k6.exe` on Windows), e.g. `windows-amd64`, `linux-amd64`, `macos-arm64`.
3. The cache at `~/.perfagent/bin/k6-v1.3.0/` (change the base folder with `PERFAGENT_HOME`).
4. A `k6` already on `PATH`.
5. Otherwise it downloads the official k6 v1.3.0 for this OS from GitHub, verifies its SHA-256
   against a hash pinned in `runner/k6_binary.py`, and stores it in the cache (step 3).

The first run shows "Setting up the load engine (first run only)…" while this happens. For machines
without internet access, use option 1 or 2. In Docker, install k6 in the image and set
`PERFAGENT_K6_PATH` so nothing is downloaded at runtime.

> [!NOTE]
> k6 prints Unicode (box-drawing and ✓/✗ characters) in its summary. PerfAgent decodes k6's
> output as UTF-8 so the **run logs** render those characters correctly on every platform,
> including Windows.

## Running the tests

The suite mocks the LLM and uses local fixtures. Tests that exercise k6 directly require an available binary or skip when it is unavailable:

```bash
uv run pytest -q
```

For a faster local run, execute the suite in parallel (the Git/Jenkins tests shell out to
real `git`, which is slower on Windows):

```bash
uv run pytest -q -n auto            # needs pytest-xdist
uv run pytest -q -k "not git"       # skip the slow Git integration tests
```

A few tests exercise POSIX-only behaviour (symlinks, `sh`) and are **skipped on Windows**;
they run in full on Linux/macOS CI.

Lint: `uv run ruff check src/ tests/`

## Troubleshooting

| Symptom | Fix |
|---|---|
| Run logs show garbled characters (`â–ˆ`, `âœ"`) | Update to the current runner — k6 output is now decoded as UTF-8. |
| A run PASSes even though the API returned an error payload | Add an assertion (e.g. **does NOT contain** the error string, or a **JSON field** check). Failed assertions count as errors. |
| Save to Git: "folder already exists and was not created by PerfAgent" | Choose a new framework name; PerfAgent never writes into folders it didn't create. |
| Save to Git / Import: "git ... failed: Authentication failed" | Check the token has access to that repository (push rights for Save to Git). |
| Jenkins log: `Cannot run program "sh"` | The job ran an old Jenkinsfile on a Windows agent. Push the test again with **Save to Git** (the new Jenkinsfile supports Windows), then run again. |
| Run in Jenkins: "doesn't accept parameters yet" | Run the job once in Jenkins, or use **Set up Jenkins job**. |
| Run in Jenkins: "rejected the user name or API token" | Use a Jenkins **API token** (not your password) for that user. |
| Jenkins build fails with "Could not find credentials entry with ID 'PERF_HEADER_…'" | Add that Secret text credential in Jenkins. |
| "could not download k6" | The machine can't reach github.com. Set `HTTPS_PROXY`, or point `PERFAGENT_K6_PATH` at a k6 binary. |
| "no prebuilt k6 for this platform" | Unusual OS/CPU — install k6 manually and set `PERFAGENT_K6_PATH`. |
| "OPENAI_API_KEY is not set" | Fill the key in `.env` and restart the app. |
| Run shows 0 requests / "Run error" | The target isn't running, or the URL is wrong. Start the target and retry. |
| A step shows "values with no source" | A `${name}` in its body is not a data-file column, not generated and not captured. Open the step and pick a source, or upload a file with that column. |
| The run stopped with "the data file ran out of rows" | Rows are set to *Each row once* and there were fewer rows than requests. Add rows, shorten the test, or let rows repeat. |
| Conversation tab is missing | `CHAT_CONVERSATION_ENABLED` is `false`, or dependencies are stale — run `uv sync`. |
| Imported a spec but no endpoints | Confirm it's valid OpenAPI (JSON/YAML), a Postman collection, or a `.har`. |
| `/me` (or a protected call) is 401 in pre-flight | Expected — pre-flight hits endpoints alone; correlation flows the token only in a full run. |
| `table ... already exists` on startup | Delete the SQLite DB once (new tables/columns were added) and restart. |
| Tests fail on import | Run `uv sync` again; make sure you're in the project `.venv`. |
