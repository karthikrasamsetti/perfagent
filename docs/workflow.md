# PerfAgent workflow

[Back to PerfAgent](../README.md)

For project setup, Git frameworks, saved workloads, and administration, see the [project workspace guide](../PROJECT_WORKFLOW.md).

## Four ways to start

From a project, choose **Create test** to describe a target and its requests. Use conversation mode when configured, or import an existing script or Git framework from the workspace.

Open **Help → Guided tour** for a walkthrough of the actual screens. The tour uses an isolated sample project. **Next** and **Previous** navigate between pages and place the tour card beside the highlighted control.

## Resume a saved test or run

In a project’s Test Library, select **Latest report** to open the most recent saved result and see its k6 verdict. Select **Resume test** to continue working on the test. A saved plan opens in Review. When a full script has been generated, the test opens in Verify and restores verification for that script version if available.

Use **Copy run link** after the run starts, or **Copy report link** from a saved report. A recipient needs access to the workspace. You can also bookmark Live Run after the run starts. Reloading that URL reconnects to the same run while the backend still has it. PerfAgent saves completed and stopped reports even if the browser tab is closed. The same bookmark opens the saved report after the run is no longer in memory. If the backend loses an active run, the bookmark initially waits for the runner’s checkpoint. After the checkpoint expires, it opens an inconclusive partial report with the last saved measurements. Opening the bookmark never starts traffic. If you no longer have the bookmark, open **Runs & reports** in the Test Library and select **Recover interrupted local runs**. Opening a saved plan, run, or report sends no load. In Verify, **Workload to run** shows the target and settings saved with the selected script. Imported or edited scripts define their own execution settings. **Start load test** is the explicit action that starts a new run.

## Reviewing the plan

Start with **Before you approve** and **What will run**. Confirm the target, masked authentication,
planned load shape, journey order, and pass rules. Open a request with its **Edit** button to
change its method, path, body, or response checks.

- **Response checks** verify the content that came back. For example, enter `order.id` under the
  Describe endpoint's optional response check, then confirm the field-existence rule in Review.
  For a value comparison, edit the request's response checks in Review.
- **Changing values** can come from uploaded data, runtime generators, or an earlier response
  in the same journey. Review flags unresolved values and links to the affected request.
- **Preview sample requests** shows sample URLs and bodies. **Approve & continue to Verify**
  generates the execution script. Use **Verify** to send requests and evaluate the checks.

---

## Conversation mode

A multi-turn chat that builds the plan with you. A **Draft so far** panel beside the chat
shows the target, endpoints and load size as they firm up, so the plan is never a surprise.

- **The draft is the source of truth, not the chat text.** Each turn the AI returns a
  schema-validated update; code merges it into the draft, so a later message can't silently
  drop something you said earlier.
- **Code decides when it's ready.** A plan can be built once there is a target URL and at
  least one endpoint. Users and duration fall back to 20 users / 60 s and are marked
  *default* until you state them.
- **Build when you're happy** — press **Build plan**, or just say "go ahead". The plan opens
  in Step 2 like any other. Come back and keep chatting to refine it; the button becomes
  **Rebuild plan** when the draft has changed.
- **It only plans.** The conversation never generates a script or fires load — you still
  review and approve in Step 2.
- **Conversations are saved.** A refresh or an app restart resumes where you left off, and
  recent conversations can be reopened from the drop-down.
- **Secrets are masked before they are stored or sent.** Passwords, tokens and emails typed
  into the chat are replaced with placeholders before the message is saved and before the AI
  sees it; set real values in the review step or use a data file.

Under the hood it is a small **LangGraph** graph — `understand → await_user → build_plan` —
checkpointed per conversation in `perfagent_chat.db`. The wait for your reply is a LangGraph
*interrupt*, the same mechanism the approval gate will use when the run steps join the graph.

| Setting (`.env`) | Default | Meaning |
|---|---|---|
| `CHAT_CONVERSATION_ENABLED` | `true` | Turn the mode off to hide the Conversation tab. |
| `CHAT_CHECKPOINT_DB` | `perfagent_chat.db` | Where conversations are saved; `:memory:` keeps them in memory only. |
| `CHAT_MAX_TURNS` | `40` | Most user messages in one conversation. |
| `CHAT_HISTORY_WINDOW` | `12` | Recent messages replayed to the AI each turn (the draft carries the rest). |
| `CHAT_MAX_MESSAGE_CHARS` | `8000` | Largest single message. |

API: `POST /api/chat/sessions`, `POST /api/chat/sessions/{id}/messages`,
`POST /api/chat/sessions/{id}/build`, `GET /api/chat/sessions[/{id}]`,
`DELETE /api/chat/sessions/{id}`.

---

## The 5-step workflow

1. **Describe** the target, endpoints, response checks, and workload. Choose VU-based traffic, journey starts per second, or an HTTP request-rate goal for one ordered journey.
2. **Review Plan** to inspect the draft, change any request, attach test data, and confirm checks and thresholds.
3. **Verify** the generated or imported script. Validate its syntax, verify the requests and assertions, and optionally run a short smoke test.
4. **Run** the load test and watch throughput, latency, errors, VUs, dropped iterations, and live logs.
5. **Report** on the verdict and the evidence behind it. Reopen saved reports, compare compatible runs, or export a standalone HTML report.

---

## Feature highlights

### 🧭 Discover & import
- **OpenAPI / Swagger** (JSON **or YAML**), **Postman collections** (incl. nested folders),
  **HAR captures** — endpoints, sample bodies, and target URL imported automatically.
- **Import from Git** — pull a test PerfAgent previously saved back as an editable plan, or
  pick up another k6 script from a repository.

### 🔐 Real-world auth & data
- **Correlation** — capture a value from a response (**JSON field, header, cookie, or
  regex**, incl. array indices like `data[0].id`) and reuse it later as `${var}`. Auto-set-up for login flows.
- **Assertions** — validate the response, not just the status: body **contains** / **does NOT
  contain** text, **status code is** N, a **JSON field compares** (eq/ne/gt/lt/contains), or
  **response time under** N ms. A failed assertion counts as an error and fails the run.
- **✨ Suggest checks from a response** — paste a real API response and the AI proposes the
  right checks (which elements must be present, which errors to guard against, which numbers
  should be positive); the response is redacted before it's sent, and you keep only the checks you want.
- **Custom headers** — global `Authorization` / API-key headers; values can use captured vars.
- **Dynamic test data** — three sources per field (see below), assigned by the AI with one click.

### ⏱ Realistic load
- **Test types** — ramp, spike, soak, stress, each a genuinely different load shape.
- **Guided k6 executors** — ramping VUs, constant VUs, constant and ramping journey arrival rates, shared iterations, and per-VU iterations. For a constant HTTP request-rate goal, PerfAgent schedules the Describe endpoints as one ordered journey and shows the conversion in Review.
- **Environment & TLS** — tag a run with an environment name (dev/staging/prod), and for test
  or dev hosts optionally **skip TLS certificate verification** (never against production).
- **Protocols** — REST/HTTP and **GraphQL** (a step can send a `{query, variables}` request).
- **Multi-tool** — generate scripts for **k6** (primary, with a live runner), **Locust**,
  **JMeter** (`.jmx`), and **Gatling** (`.scala`) from the same plan.
- **Editable plan form** — scenarios, weights, think-times, thresholds (raw-JSON toggle too).

### ✅ Trust & safety
- **Data guardrails** — secrets/PII/URLs redacted before the AI; output scrubbed.
- **AI evaluation** — plan grounding (no invented endpoints) + report citation (no fabricated numbers).
- **Fail-closed verdict** — an unmeasurable threshold → **INCONCLUSIVE**, never a silent PASS.

### Plan from sampled traffic

1. In **Describe → Traffic and duration**, open **Plan from sampled traffic**.
2. Download the example CSV or prepare a file with `window_start,window_seconds,method,route,requests`. Use UTC timestamps, non-overlapping windows, and one aggregate count per method and route template in each window. Keep queries, headers, request bodies, and customer identifiers out of the file.
3. Import the CSV. Review the route shares, the busiest window and the time-weighted average. Choose a rate and select **Use … requests/s**. The file stays in your browser.
4. Set the target, endpoints, duration, and virtual-user allocation. Draft the plan, then confirm the requested HTTP rate, the estimated journey starts per second, the executor, and the order of the steps in **Review plan**. Route counts show traffic mix. Journey order and relationships need to come from the test you define.

[Traffic planning screen](screenshots/traffic-planning.png)

For multiple journeys, open **Review plan → Suggest journey weights from traffic** and choose the aggregate CSV again. Select one observed route unique to each journey. PerfAgent divides the sampled route count by its occurrences in that journey, then turns those estimated starts into relative weights. It previews the shares and the ideal HTTP request rate for a constant journey-start workload before you apply them. Shared routes and journeys without a sampled route need manual weights. For example, 800 browse starts and 200 checkout starts suggest an 80/20 allocation. If browse sends one request and checkout sends two, 10 journey starts/s imply about 12 HTTP requests/s before k6 allocation rounding.

[Journey weighting screen](screenshots/journey-weighting.png)

### 🔎 Run & diagnose
- **Pre-flight check**, **script validation** (`k6 inspect`), **live monitoring + chart**,
  **live run logs** (k6's output streamed as it runs — threshold crossings, the checks
  summary, and your script's own `console.*` messages), a **diagnosis engine** (bottlenecks,
  latency tail, concurrency), and **baseline/regression**.
- **Editable script** — tweak the generated k6 before running (e.g. add custom `console.log`
  debugging, or your own validation); **Regenerate** restores the deterministic version.

### 📊 Report & history
- **Performance dashboard** shows comparable historical runs across latency, throughput, error rate, and daily outcomes, with environment and release filters and links to saved reports.
- **Run report** opens with the verdict, What happened, and linked key evidence, followed by thresholds, synchronized timelines, endpoint rankings, and baseline comparison. When samples record dropped iterations, the report links to the first affected sample.
- **Release readiness** uses approved baselines and budgets stored per test and environment. Open a completed full run that passed its k6 thresholds without dropped iterations, then use **Set release budgets and approve this run as the baseline**. Run the same workload against a new release to see the decision in the project dashboard, saved report, and HTML export. Review the rule, endpoint comparisons, and recorded throughput before sharing the result. Saved reports evaluate the current policy when reopened. An exported HTML file captures the decision at download time.
- **Response checks panel** — each assertion with its pass/fail count, so you can see exactly
  which checks failed and why the run passed or failed.
- **Run logs** — the full k6 output for the run is shown on the report, **saved with it**, and
  **downloadable as a `.txt`** — reopen a run from history and its logs are still there.
- **Time-series + trend charts** — latency/RPS/errors over the run, and p95/error trends across recent runs.
- **SLA profiles** — save reusable threshold sets (e.g. "p95<300ms, errors<1%") and apply to any plan.
- **Runs & reports history** — every finished run saved; click to reopen its full report.
- **Downloadable HTML report** for stakeholders.

### 🚀 Ship to CI/CD
- **Save to Git** — export the test into a named k6 framework with ready-made **GitHub
  Actions, Jenkins, Azure DevOps and GitLab** pipelines; secrets are never committed.
- **Run in Jenkins** — trigger the pipeline for a saved test and follow it live in PerfAgent
  (queued → running → finished, console log streaming, archived k6 results and verdict).

### 🧰 Convenience
- **Run an existing script**, **saved plans** (reopen & re-run), **token-usage** visibility,
  and **saved (non-secret) Git/Jenkins details** so you don't retype them.

---

## Dynamic test data — the three sources

Real request bodies mix three kinds of values. On the Review step, open a step and its
**Request data** table lists every field of the body with a **Comes from** choice — no
`${...}` to type by hand:

| Comes from | When to use | You pick | In the script |
|---|---|---|---|
| **Fixed value** | A constant | the value (text, number, true/false, empty) | kept as-is |
| **From data file** | A *real existing* value the API validates | a column of the uploaded file | `row.branch` (k6 `SharedArray`) |
| **Generated** | A value that must be *new for every request* | Unique ID, Unique email, Random number between…, Random pick from a list…, names, addresses, dates… | self-contained k6 helpers (`uuidv4()`, `fakeName()`, …) |

A fourth kind appears on its own: **From an earlier step** — a value captured from a
previous response (for example a login token).

**How to make every request unique**

1. On the Review step, upload the file under **2 · Test data file**. Its columns and first
   rows are shown.
2. Under **3 · Journeys**, click the step. For each field choose *From data file* (a column
   with the same name is picked for you) or *Generated*. **✨ Suggest with AI** proposes a
   source for every field at once — review it, or press *Undo*.
3. Choose how the rows are used:

   | Use the rows | Behaviour |
   |---|---|
   | In random order *(default)* | Any row; a row can be used more than once. |
   | In file order | Row 1, 2, 3 … shared by all virtual users; starts again at the top. |
   | Each row once | No row is ever reused. With several journeys each gets its own share of the rows. When the rows run out the test stops and says so. |

4. Click **🔍 Preview the requests** to see three real examples per step.

Nested bodies work the same way (fields are listed as `address.city`, `items[0].sku`);
*Edit as JSON* is there for structural changes. A name that is neither a column, nor
generated, nor captured is flagged — in the step, in the preview and before generating —
because it would be sent empty.

The same `${...}` placeholders still work if you prefer to type them:
`${username}` (column), `${uuid}`, `${randomEmail}`, `${randomInt(1,5)}`,
`${randomString(8)}`, `${randomFrom(a,b,c)}`, `${timestamp}`, `${sequential}`,
`${dateOffset(3,'days')}`, `${randomFullName}`, `${randomCity}` and the other realistic
generators. Postman-style `{{var}}` / `{{$randomX}}` is also accepted and converted. The
realistic generators are **self-contained helper functions** — no external faker library.

Only the **column names** of a data file are ever sent to the AI; the values stay in the
database for the run. Data files are built into **k6** scripts (the other tools ignore them).
The pre-flight check fills in a real row and sample generated values too, so it sends
realistic requests.

---

## Validating the response — assertions & suggested checks

A load test that only checks the HTTP status can **pass while the API is returning errors** —
many APIs answer `200 OK` with an error payload in the body. Assertions close that gap.

**Assertion kinds** (added per step, in plain English):

| Check | Passes when | Example |
|---|---|---|
| **Response body contains** | the body includes the text | contains `<Rate>` |
| **Response body does NOT contain** | the body is free of the text | does NOT contain `Invalid Parameters` |
| **Status code is** | the status equals N | status is `200` |
| **JSON field compares** | a field eq/ne/gt/lt/contains a value | `data.total` **gt** `0` |
| **Response time under (ms)** | the request finished in time | under `2000` ms |

A failed assertion is counted as an **error** (not just a failed k6 check), so it raises the
error rate and can **fail the run** — assertions are enforced, not decorative. The
**response-checks panel** on the report shows each check's pass/fail count.

**✨ Suggest checks from a response** — rather than hand-writing every check, paste a **real
response** you captured (from Postman or curl) and the AI proposes a layered set: the
structural elements that should always be present, the error strings to guard against, and
the numeric fields that should be positive. You review the list and keep what you want. The
pasted response is **redacted** (secrets/PII removed) before it is sent to the AI — only the
structure is shared.
