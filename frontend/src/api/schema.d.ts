export interface paths {
    "/api/export/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Git export options
         * @description The Git hosts users may push to (if restricted) and the CI systems a pipeline file can be generated for.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["export_settings_api_export_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/export/git": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Save a test to Git
         * @description Builds a ready-to-run performance framework around the approved k6 test (test, config, CI pipeline file, README) and commits and pushes it to the repository and branch given. The access token is used for this call only and never stored.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["export_git_api_scripts__script_id__export_git_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/export/zip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Download a test as a framework zip
         * @description The same framework as 'Save a test to Git', as a .zip download instead of a push.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        post: operations["export_zip_api_scripts__script_id__export_zip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/git/scan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Browse a repository for tests
         * @description Lists the PerfAgent tests and other load scripts found in a repository branch. Read-only; the token is used for this call only.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["git_scan_api_git_scan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/git/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import a test from Git
         * @description Loads one PerfAgent test from a repository back as an editable plan (and its data file, if it was committed).
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["git_import_api_git_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/git/script": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * View another script from Git
         * @description Returns the text of a script in the repository that was not made by PerfAgent, for reference or to run as your own script.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["git_script_api_git_script_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jenkins/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Jenkins options
         * @description The Jenkins hosts users may call, if restricted.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["jenkins_settings_api_jenkins_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jenkins/trigger": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start a Jenkins build
         * @description Starts the Jenkins job for a saved test with the test name and environment as parameters. This causes Jenkins to run the load test.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["jenkins_trigger_api_jenkins_trigger_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jenkins/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Follow a Jenkins build
         * @description Whether the build is queued, running or finished, the next part of its console output, and the k6 results once it is done.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["jenkins_status_api_jenkins_status_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jenkins/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Stop a Jenkins build
         * @description Aborts a running build.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["jenkins_stop_api_jenkins_stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jenkins/setup-job": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create or update the Jenkins job
         * @description Creates the Pipeline job for a framework in Jenkins, or updates it, so the saved tests can be run there.
         *
         *     **Access level:** `integrate` — talks to an outside system (Git / Jenkins) with credentials from the call.
         */
        post: operations["jenkins_setup_job_api_jenkins_setup_job_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/integrations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Saved Git and Jenkins details
         * @description The non-secret details remembered for a plan (repository, branch, job) and the last-used defaults, so forms can be pre-filled. Tokens are never stored, so they are never returned.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_integrations_api_integrations_get"];
        put?: never;
        post?: never;
        /**
         * Forget saved details
         * @description Forgets the saved Git details, Jenkins details, or both, for a plan.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        delete: operations["forget_integrations_api_integrations_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Is conversation mode on, and its limits
         * @description Tells the UI whether the Conversation tab should be shown, and the limits in force (messages per conversation, message size).
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["chat_config_api_chat_config_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List recent conversations
         * @description The most recent planning conversations, newest first, for the 'Recent conversations' menu.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_sessions_api_chat_sessions_get"];
        put?: never;
        /**
         * Start a conversation
         * @description Opens a new planning conversation with the user's first message (and, optionally, a pasted Postman / OpenAPI / HAR collection) and runs the first turn. Secrets in the message are masked before it is stored or sent to the AI.
         *
         *     **Access level:** `write` — creates or changes stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["start_session_api_chat_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Open one conversation
         * @description Returns a conversation as the UI shows it. Used to resume after a page refresh or an app restart.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_session_view_api_chat_sessions__session_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete a conversation
         * @description Forgets a conversation and its saved state. Plans already built from it are kept.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        delete: operations["delete_session_api_chat_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/sessions/{session_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Send the next message
         * @description Adds a user message to a conversation and runs the turn: the AI updates the draft and replies. If the draft is complete and the message asks to go ahead, the plan is built in the same call.
         *
         *     **Access level:** `write` — creates or changes stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["send_message_api_chat_sessions__session_id__messages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/sessions/{session_id}/build": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Build the plan from the draft
         * @description Hands the conversation's draft to the planner and saves the plan for review. Refused with 409 while the target or the endpoints are still missing. Nothing is generated or run.
         *
         *     **Access level:** `write` — creates or changes stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["build_plan_api_chat_sessions__session_id__build_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reporting/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Run history for a stakeholder role
         * @description Past runs, newest first, with each run's fields limited to what the given role may see (executive, qa_lead, engineer, viewer). Optionally filtered by target or verdict. The optional overview aggregates all matching runs independently of pagination and includes up to 120 recent trend points. Reads stored data only.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["reporting_runs_api_reporting_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reporting/trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * A metric's trend across runs
         * @description The chosen metric (p95, p99, error rate, avg or RPS) across recent runs, oldest to newest, as points for a trend chart. Optionally filtered by target or plan. Reads stored data only; no AI.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["reporting_trend_api_reporting_trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List performance projects
         * @description List project names, non-secret repository settings and test counts.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_projects_api_projects_get"];
        put?: never;
        /**
         * Create a performance project
         * @description Create a named project with target, environment and optional Git framework settings.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["create_project_api_projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update project settings
         * @description Update project identity, default target and non-secret Git configuration.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        put: operations["update_project_api_projects__project_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/projects/{project_id}/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Project dashboard summary
         * @description Aggregate test counts, runs, requests and pass rate within one project.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["project_dashboard_api_projects__project_id__dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Administrator overview of all projects
         * @description Cross-project summaries. Requires X-Perfagent-Admin matching ADMIN_API_TOKEN on the server.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["admin_dashboard_api_admin_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}/project": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Assign a test to a project
         * @description Attach an existing plan and its execution history to the selected project.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        put: operations["attach_test_api_plans__plan_id__project_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}/workloads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List saved workload profiles
         * @description List named load shapes and threshold sets saved for this reusable test.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_workloads_api_plans__plan_id__workloads_get"];
        put?: never;
        /**
         * Save a named workload profile
         * @description Save or update a named load shape and threshold set without changing completed runs.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["save_workload_api_plans__plan_id__workloads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health check
         * @description Whether the app is up and can reach its database, which database is in use (SQLite or Postgres) and whether its tables are up to date. Returns 503 if the database cannot be reached. Suitable as a container health check.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Supported load tools
         * @description The load tools a script can be generated for.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["tools_api_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audit log
         * @description Recent actions — plans created, scripts generated, runs started, pushes to Git — with when, on what, and the tokens spent.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_audit_api_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/usage/total": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * AI usage so far
         * @description Total tokens and a rough cost across all AI calls.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["usage_total_api_usage_total_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/traces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * AI call traces
         * @description One record per AI call: which step made it, the model, tokens, time taken, whether it succeeded and how many values were redacted. For debugging and cost review; prompts are stored redacted.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_traces_api_traces_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List past runs
         * @description Runs that have a saved report, newest first.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_runs_api_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sla": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List SLA profiles
         * @description The saved sets of pass/fail thresholds.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_sla_api_sla_get"];
        put?: never;
        /**
         * Save an SLA profile
         * @description Saves a named set of thresholds so it can be applied to other plans.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["create_sla_api_sla_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sla/{sla_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete an SLA profile
         * @description Removes a saved SLA profile. Plans that already use its thresholds are not changed.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        delete: operations["delete_sla_api_sla__sla_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/trend": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Trend across runs of a plan
         * @description The key metrics of a plan's recent runs, oldest to newest, for the trend chart.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["runs_trend_api_runs_trend_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{result_id}/saved-report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Reopen a saved report
         * @description A previously saved report, exactly as it was produced.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_saved_report_api_runs__result_id__saved_report_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload a test-data file
         * @description Uploads a CSV, TSV, TXT, JSON or JSONL file of real values (e.g. user names, branch codes), checks it and stores it. Only the column NAMES are ever shown to the AI; the values stay in the database for the run.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["upload_data_api_data_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/{data_file_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Describe an uploaded data file
         * @description The columns, row count and first rows of a stored data file, so the UI can show what is available to map into requests.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_data_file_api_data__data_file_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/import-endpoints": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import endpoints from a spec
         * @description Reads an uploaded OpenAPI/Swagger file, Postman collection or HAR capture and returns the endpoints found, so they need not be typed. Nothing is stored and no AI is involved.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        post: operations["import_endpoints_api_api_import_endpoints_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Draft a plan from the form
         * @description The AI drafts a plan (journeys, weights, think times, thresholds) from the target, goal, load size and endpoints given. Code then forces the target, the load shape and sane thresholds. The plan is saved and returned for review.
         *
         *     **Access level:** `write` — creates or changes stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["create_plan_api_plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dynamize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suggest a source for each body field
         * @description The AI looks at a request body and proposes, field by field, which values should come from the data file, which should be generated fresh per request and which should stay fixed. Returns the body with ${...} placeholders for the user to review; it does not change the plan.
         *
         *     **Access level:** `read` — only reads stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["dynamize_api_dynamize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/suggest-checks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suggest response checks
         * @description The AI proposes checks (status, body contains, JSON field values) from a sample response pasted by the user. The sample is redacted before the AI sees it. Nothing is added to the plan until the user accepts.
         *
         *     **Access level:** `read` — only reads stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        post: operations["suggest_checks_api_suggest_checks_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/load-profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Build the load shape
         * @description Turns a test type (ramp, spike, soak, stress), a peak number of users and a duration into the list of load stages. Pure calculation — the same inputs always give the same shape, and no AI is involved. Used when the size of a plan is changed during review.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        post: operations["load_profile_api_load_profile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/request-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview the requests that will be sent
         * @description Fills each step of a plan with real rows of the data file and sample generated values, and returns the first few requests exactly as they would be sent. Also lists any ${name} that has no source. Nothing is sent to the target and no AI is involved.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        post: operations["request_preview_api_request_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/{plan_id}/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve a plan and generate its script
         * @description Renders the (possibly edited) plan to a script for k6, Locust, JMeter or Gatling, attaching the data file and custom headers. Generation is deterministic — no AI. This is the human approval step: the edited plan is saved as the approved one.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["generate_api_plan__plan_id__generate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List saved plans
         * @description Every saved plan, newest first, with its target, goal and how many scripts it has.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["list_plans_api_plans_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Open a saved plan
         * @description One saved plan with its full contents and the scripts generated from it.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["get_plan_api_plans__plan_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download a script
         * @description The script as a file.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["download_script_api_scripts__script_id__download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/preflight": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Verify k6 journeys or check plan endpoints
         * @description Exercises each journey of a saved k6 script once with a single virtual user. Using a plan directly checks endpoint reachability.
         *
         *     **Access level:** `run` — sends real requests or load to the system under test.
         */
        post: operations["api_preflight_api_preflight_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check a script without running it
         * @description Asks k6 to load the script and its options (`k6 inspect`). Catches syntax errors and bad options. No request is sent to the target.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        post: operations["api_validate_script_api_scripts__script_id__validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Save an edited script version
         * @description Keeps the source plan, environment and frozen data with the edited content.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["edit_script_api_scripts__script_id__edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Use your own script
         * @description Stores a hand-written or existing k6 script so it can be validated and run, skipping planning.
         *
         *     **Access level:** `write` — creates or changes stored data.
         */
        post: operations["upload_script_api_scripts_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/run/available": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Is the load engine ready
         * @description Whether k6 is present or can be fetched automatically on the first run.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["run_available_api_run_available_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/readiness": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Execution readiness checklist
         * @description Check frozen inputs, engine availability, planned load and the latest verification of this version without sending traffic.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["execution_readiness_api_scripts__script_id__readiness_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scripts/{script_id}/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start a run
         * @description Starts the script with k6 and returns at once. The run continues in the background; poll the run for live metrics. This sends real load to the target.
         *
         *     **Access level:** `run` — sends real requests or load to the system under test.
         */
        post: operations["run_script_api_scripts__script_id__run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Live status of a run
         * @description The run's status and the metrics measured so far (requests, error rate, throughput, percentiles), all computed in code from k6's raw output, plus the recent log lines.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["run_status_api_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Stop a run
         * @description Stops a run in progress. The metrics measured up to that point are kept.
         *
         *     **Access level:** `run` — sends real requests or load to the system under test.
         */
        post: operations["run_stop_api_runs__run_id__stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Report of a finished run
         * @description The pass/fail verdict (decided in code against the plan's thresholds), the diagnosis, the comparison with the previous run of the same plan, and a short summary written by the AI from those numbers (checked so it cannot cite a figure that was not measured). The report is saved.
         *
         *     **Access level:** `write` — creates or changes stored data.
         *
         *     **Uses AI:** yes — spends tokens; inputs are redacted first.
         */
        get: operations["run_report_api_runs__run_id__report_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/logs/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download a run's logs
         * @description k6's output for the run — threshold crossings, the checks summary and the script's own console messages — as a text file. Works for a live run and for a saved one.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["run_logs_download_api_runs__run_id__logs_download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/report/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download the report
         * @description The full report as a self-contained HTML file.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["run_report_download_api_runs__run_id__report_download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Prometheus metrics
         * @description Live run metrics in Prometheus text format for a Prometheus server to scrape and Grafana to chart. Deterministic; no AI. Series are grouped by scenario, environment and load tool; per-run detail lives in the run history, not here.
         *
         *     **Access level:** `read` — only reads stored data.
         */
        get: operations["metrics_api_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Assertion
         * @description A check on a step's response — validates content, not just the status code.
         *
         *     kind:
         *       status        — the HTTP status code (value = expected code, e.g. 200)
         *       json_path     — a field in the JSON body (path = dotted field, value = expected)
         *       body_contains — the response body contains the given text (value = text)
         *     op: eq | ne | contains | gt | lt | exists (exists checks whether a JSON field is present)
         */
        Assertion: {
            /**
             * Kind
             * @description status | json_path | body_contains | not_contains | response_time
             */
            kind: string;
            /**
             * Op
             * @description eq | ne | contains | gt | lt | exists
             * @default eq
             */
            op?: string;
            /**
             * Path
             * @description For json_path: dotted field, e.g. 'data.id'.
             * @default
             */
            path?: string;
            /**
             * Value
             * @description Expected value (as text).
             * @default
             */
            value?: string;
        };
        /** AttachBody */
        AttachBody: {
            /** Project Id */
            project_id: string;
            /**
             * Test Name
             * @default
             */
            test_name?: string;
        };
        /** Body_import_endpoints_api_api_import_endpoints_post */
        Body_import_endpoints_api_api_import_endpoints_post: {
            /** File */
            file: string;
        };
        /** Body_upload_data_api_data_post */
        Body_upload_data_api_data_post: {
            /** File */
            file: string;
        };
        /** ChatMessageBody */
        ChatMessageBody: {
            /** Message */
            message: string;
            /**
             * Collection Text
             * @default
             */
            collection_text?: string;
            /** Project Id */
            project_id?: string | null;
            /**
             * Test Name
             * @default
             */
            test_name?: string;
        };
        /** DataFile */
        DataFile: {
            /** Data File Id */
            data_file_id?: string | null;
            /**
             * Filename
             * @description e.g. 'users.csv'.
             */
            filename: string;
            /** Fields */
            fields: string[];
            /**
             * Row Count
             * @default 0
             */
            row_count?: number;
            /**
             * Source Format
             * @default csv
             */
            source_format?: string;
            /**
             * Row Mode
             * @description How rows are handed to requests: 'random' (any row, repeats possible), 'sequential' (in file order, starting again at the top) or 'unique' (each row once; the test stops when rows run out).
             * @default random
             */
            row_mode?: string;
        };
        /** DynamizeBody */
        DynamizeBody: {
            /** Body */
            body: {
                [key: string]: unknown;
            };
            /** Data File Id */
            data_file_id?: string | null;
        };
        /** EditScriptBody */
        EditScriptBody: {
            /** Content */
            content: string;
        };
        /**
         * EndpointSpec
         * @description One endpoint the user wants covered.
         */
        EndpointSpec: {
            /** @default GET */
            method?: components["schemas"]["HttpMethod"];
            /** Path */
            path: string;
            /** Description */
            description?: string | null;
            /** Example Body */
            example_body?: {
                [key: string]: unknown;
            } | null;
            /** Assertions */
            assertions?: components["schemas"]["Assertion"][] | null;
        };
        /** ExportBody */
        ExportBody: {
            /**
             * Framework Name
             * @description Framework folder name, e.g. 'payments-perf'
             * @default
             */
            framework_name?: string;
            /**
             * Test Name
             * @description Test folder name, e.g. 'checkout-peak'
             * @default
             */
            test_name?: string;
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /** Git Token */
            git_token?: string | null;
            /** Ci */
            ci?: string[];
            /**
             * Include Data
             * @default false
             */
            include_data?: boolean;
            /** Data File Id */
            data_file_id?: string | null;
            /** Commit Message */
            commit_message?: string | null;
        };
        /**
         * Extract
         * @description Capture a value from a step's response into a variable for later steps.
         *
         *     var  — the variable name; later steps reference it as ${var}
         *     source — where to read from: 'json' (a field path in the JSON body)
         *     path — for json: a dotted field path, e.g. 'token' or 'data.id'
         */
        Extract: {
            /**
             * Var
             * @description Variable name, usable later as ${var}.
             */
            var: string;
            /**
             * Source
             * @description Where to read from: 'json' (body field), 'header', 'cookie', or 'regex'.
             * @default json
             */
            source?: string;
            /**
             * Path
             * @description json: dotted path, supports arrays e.g. 'data[0].id'; header: the header name e.g. 'X-Auth-Token'; cookie: the cookie name e.g. 'session'; regex: a pattern with one capture group, e.g. 'token=([A-Za-z0-9]+)'.
             */
            path: string;
        };
        /** GenerateBody */
        GenerateBody: {
            /**
             * Tool
             * @default k6
             */
            tool?: string;
            load_model?: components["schemas"]["LoadModel"] | null;
            /** Data File Id */
            data_file_id?: string | null;
            /** Data Row Mode */
            data_row_mode?: string | null;
            /** Headers */
            headers?: {
                [key: string]: string;
            } | null;
        };
        /** GitSource */
        GitSource: {
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /** Git Token */
            git_token?: string | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HttpMethod
         * @enum {string}
         */
        HttpMethod: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
        /** ImportBody */
        ImportBody: {
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /** Git Token */
            git_token?: string | null;
            /** Project Id */
            project_id?: string | null;
            /**
             * Framework Path
             * @default
             */
            framework_path?: string;
            /**
             * Test
             * @default
             */
            test?: string;
            /** Secrets */
            secrets?: {
                [key: string]: string;
            };
            /** Expected Commit */
            expected_commit?: string | null;
        };
        /** LoadModel */
        LoadModel: {
            /**
             * Test Name
             * @default
             */
            test_name?: string;
            /**
             * Script Filename
             * @default
             */
            script_filename?: string;
            /** Target Base Url */
            target_base_url: string;
            /** Scenarios */
            scenarios: components["schemas"]["Scenario"][];
            load_profile: components["schemas"]["LoadProfile"];
            /** Thresholds */
            thresholds?: components["schemas"]["Threshold"][];
            data_file?: components["schemas"]["DataFile"] | null;
            /** Headers */
            headers?: {
                [key: string]: string;
            };
            /**
             * Environment
             * @description Environment label (dev/staging/prod).
             * @default
             */
            environment?: string;
            /**
             * Insecure Tls
             * @description Skip TLS verification (test hosts only).
             * @default false
             */
            insecure_tls?: boolean;
        };
        /** LoadProfile */
        LoadProfile: {
            /** @default ramp */
            type?: components["schemas"]["LoadProfileType"];
            /** Stages */
            stages: components["schemas"]["Stage"][];
            /**
             * Arrival Rate
             * @description Journey iterations per second; k6 only.
             */
            arrival_rate?: number | null;
            /**
             * Target Request Rate
             * @description HTTP requests per second for a single-request k6 test.
             */
            target_request_rate?: number | null;
            /**
             * Pre Allocated Vus
             * @default 10
             */
            pre_allocated_vus?: number;
            /**
             * Graceful Stop Seconds
             * @default 30
             */
            graceful_stop_seconds?: number;
            /**
             * Start Users
             * @default 0
             */
            start_users?: number;
        };
        /** LoadProfileBody */
        LoadProfileBody: {
            /** @default ramp */
            type?: components["schemas"]["LoadProfileType"];
            /** Max Users */
            max_users: number;
            /** Duration Seconds */
            duration_seconds: number;
        };
        /**
         * LoadProfileType
         * @enum {string}
         */
        LoadProfileType: "ramp" | "spike" | "soak" | "stress";
        /**
         * PlanRequest
         * @description Everything the Planner needs to draft a LoadModel.
         */
        PlanRequest: {
            /** Target Base Url */
            target_base_url: string;
            /** Endpoints */
            endpoints: components["schemas"]["EndpointSpec"][];
            /**
             * Goal
             * @default
             */
            goal?: string;
            /** Project Id */
            project_id?: string | null;
            /**
             * Test Name
             * @default
             */
            test_name?: string;
            /**
             * Max Users
             * @default 100
             */
            max_users?: number;
            /**
             * Duration Seconds
             * @default 300
             */
            duration_seconds?: number;
            /** @default ramp */
            profile_type?: components["schemas"]["LoadProfileType"];
            /**
             * Environment
             * @default
             */
            environment?: string;
            /**
             * Insecure Tls
             * @default false
             */
            insecure_tls?: boolean;
            /** Thresholds */
            thresholds?: components["schemas"]["Threshold"][] | null;
            /** Target Request Rate */
            target_request_rate?: number | null;
            /** Stages */
            stages?: components["schemas"]["Stage"][] | null;
        };
        /** PreflightBody */
        PreflightBody: {
            load_model?: components["schemas"]["LoadModel"] | null;
            /** Script Id */
            script_id?: string | null;
            /** Data File Id */
            data_file_id?: string | null;
            /** Headers */
            headers?: {
                [key: string]: string;
            } | null;
        };
        /** ProjectBody */
        ProjectBody: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description?: string;
            /**
             * Target Url
             * @default
             */
            target_url?: string;
            /**
             * Environment
             * @default staging
             */
            environment?: string;
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /**
             * Framework Name
             * @default
             */
            framework_name?: string;
            /** Ci */
            ci?: string[];
        };
        /** RequestPreviewBody */
        RequestPreviewBody: {
            load_model: components["schemas"]["LoadModel"];
            /** Data File Id */
            data_file_id?: string | null;
            /** Data Row Mode */
            data_row_mode?: string | null;
            /**
             * Samples
             * @default 3
             */
            samples?: number;
        };
        /**
         * Role
         * @enum {string}
         */
        Role: "executive" | "qa_lead" | "engineer" | "viewer";
        /** RunOptions */
        RunOptions: {
            /**
             * Smoke
             * @default false
             */
            smoke?: boolean;
            /** Baseline Id */
            baseline_id?: string | null;
            /**
             * Release Label
             * @default
             */
            release_label?: string;
        };
        /** Scenario */
        Scenario: {
            /** Name */
            name: string;
            /**
             * Weight
             * @default 1
             */
            weight?: number;
            /** Steps */
            steps: components["schemas"]["Step"][];
            think_time?: components["schemas"]["ThinkTime"];
        };
        /** ScriptBody */
        ScriptBody: {
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /** Git Token */
            git_token?: string | null;
            /**
             * Path
             * @default
             */
            path?: string;
        };
        /** SetupBody */
        SetupBody: {
            /**
             * Jenkins Url
             * @default
             */
            jenkins_url?: string;
            /**
             * Username
             * @default
             */
            username?: string;
            /** Api Token */
            api_token?: string | null;
            /**
             * Job
             * @default
             */
            job?: string;
            /** Plan Id */
            plan_id?: string | null;
            /**
             * Repo Url
             * @default
             */
            repo_url?: string;
            /**
             * Branch
             * @default main
             */
            branch?: string;
            /**
             * Framework
             * @default
             */
            framework?: string;
            /**
             * Git Credentials Id
             * @default
             */
            git_credentials_id?: string;
        };
        /** SlaProfileBody */
        SlaProfileBody: {
            /** Name */
            name: string;
            /** Thresholds */
            thresholds: {
                [key: string]: unknown;
            }[];
        };
        /** Stage */
        Stage: {
            /** Duration Seconds */
            duration_seconds: number;
            /** Target Users */
            target_users: number;
        };
        /** StatusBody */
        StatusBody: {
            /**
             * Jenkins Url
             * @default
             */
            jenkins_url?: string;
            /**
             * Username
             * @default
             */
            username?: string;
            /** Api Token */
            api_token?: string | null;
            /**
             * Job
             * @default
             */
            job?: string;
            /** Plan Id */
            plan_id?: string | null;
            /** Queue Id */
            queue_id?: number | null;
            /** Build Number */
            build_number?: number | null;
            /**
             * Log Start
             * @default 0
             */
            log_start?: number;
            /**
             * Include Results
             * @default true
             */
            include_results?: boolean;
        };
        /**
         * Step
         * @description A single request within a scenario (one call in a user journey).
         *
         *     Paths, bodies and header values may contain ${name} placeholders filled from a
         *     data-file row OR from a variable captured earlier via `extract`.
         */
        Step: {
            /**
             * Name
             * @description Human-readable label, e.g. 'view products'.
             */
            name: string;
            /** @default GET */
            method?: components["schemas"]["HttpMethod"];
            /**
             * Path
             * @description Path relative to the target base URL.
             */
            path: string;
            /**
             * Body
             * @description JSON body for POST/PUT/PATCH.
             */
            body?: {
                [key: string]: unknown;
            } | null;
            /**
             * Extract
             * @description Values to capture from this response for later steps.
             */
            extract?: components["schemas"]["Extract"][];
            /**
             * Assertions
             * @description Checks on the response body/status beyond a 2xx.
             */
            assertions?: components["schemas"]["Assertion"][];
            /**
             * Graphql Query
             * @description If set, this step is a GraphQL request: the body is sent as {query, variables}. The method should be POST.
             * @default
             */
            graphql_query?: string;
        };
        /** StopBody */
        StopBody: {
            /**
             * Jenkins Url
             * @default
             */
            jenkins_url?: string;
            /**
             * Username
             * @default
             */
            username?: string;
            /** Api Token */
            api_token?: string | null;
            /**
             * Job
             * @default
             */
            job?: string;
            /** Plan Id */
            plan_id?: string | null;
            /**
             * Build Number
             * @default 0
             */
            build_number?: number;
        };
        /** SuggestChecksBody */
        SuggestChecksBody: {
            /** Sample Response */
            sample_response: string;
        };
        /** ThinkTime */
        ThinkTime: {
            /**
             * Min Seconds
             * @default 1
             */
            min_seconds?: number;
            /**
             * Max Seconds
             * @default 3
             */
            max_seconds?: number;
        };
        /** Threshold */
        Threshold: {
            /**
             * Metric
             * @description e.g. 'p95_ms', 'error_rate'.
             */
            metric: string;
            /**
             * Op
             * @description Comparison operator: '<', '<=', '>', '>='.
             */
            op: string;
            /** Value */
            value: number;
        };
        /** TriggerBody */
        TriggerBody: {
            /**
             * Jenkins Url
             * @default
             */
            jenkins_url?: string;
            /**
             * Username
             * @default
             */
            username?: string;
            /** Api Token */
            api_token?: string | null;
            /**
             * Job
             * @default
             */
            job?: string;
            /** Plan Id */
            plan_id?: string | null;
            /**
             * Test
             * @default all
             */
            test?: string;
            /**
             * Environment
             * @default dev
             */
            environment?: string;
        };
        /** UploadScriptBody */
        UploadScriptBody: {
            /** Project Id */
            project_id?: string | null;
            /**
             * Test Name
             * @default
             */
            test_name?: string;
            /**
             * Filename
             * @default
             */
            filename?: string;
            /** Content */
            content: string;
            /**
             * Target Base Url
             * @default
             */
            target_base_url?: string;
            /**
             * Tool
             * @default k6
             */
            tool?: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** WorkloadBody */
        WorkloadBody: {
            /** Name */
            name: string;
            load_profile: components["schemas"]["LoadProfile"];
            /** Thresholds */
            thresholds?: components["schemas"]["Threshold"][];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    export_settings_api_export_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `allowed_hosts`, `ci_options`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    export_git_api_scripts__script_id__export_git_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportBody"];
            };
        };
        responses: {
            /** @description `framework`, `test`, `repo_url`, `branch`, `commit`, `changed`, `files`, `required_secrets`, `warnings`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_zip_api_scripts__script_id__export_zip_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportBody"];
            };
        };
        responses: {
            /** @description A .zip file, as an attachment. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    git_scan_api_git_scan_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GitSource"];
            };
        };
        responses: {
            /** @description `repo_url`, `branch`, `commit`, `frameworks` (importable tests), `other_scripts` (viewable), `truncated`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    git_import_api_git_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportBody"];
            };
        };
        responses: {
            /** @description `plan_id`, `load_model`, `framework`, `test`, `commit`, `data_file_id`, `data_fields`, `missing_secrets`, `warnings`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    git_script_api_git_script_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScriptBody"];
            };
        };
        responses: {
            /** @description The script's path, tool and content. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    jenkins_settings_api_jenkins_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `allowed_hosts`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    jenkins_trigger_api_jenkins_trigger_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TriggerBody"];
            };
        };
        responses: {
            /** @description `queue_id` (to follow), `job`, `warnings`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    jenkins_status_api_jenkins_status_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusBody"];
            };
        };
        responses: {
            /** @description `state`, `build_number`, `build_url`, `log` (+ `log_next`, `log_more`), `result`, `results`, `verdict`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    jenkins_stop_api_jenkins_stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StopBody"];
            };
        };
        responses: {
            /** @description `stopped`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    jenkins_setup_job_api_jenkins_setup_job_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetupBody"];
            };
        };
        responses: {
            /** @description `action` (created / updated), `job`, `warnings`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_integrations_api_integrations_get: {
        parameters: {
            query?: {
                plan_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `plan_id`, `git`, `jenkins`, `saved`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    forget_integrations_api_integrations_delete: {
        parameters: {
            query: {
                section: string;
                plan_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description What remains saved: `plan_id`, `git`, `jenkins`, `saved`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chat_config_api_chat_config_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `enabled`, `max_turns`, `max_message_chars`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_sessions_api_chat_sessions_get: {
        parameters: {
            query?: {
                limit?: number;
                project_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `sessions`: id, title, status, turns, linked plan. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_session_api_chat_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatMessageBody"];
            };
        };
        responses: {
            /** @description The conversation view: messages, the draft so far, what is still missing. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_view_api_chat_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The conversation view. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_api_chat_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `deleted`: the conversation id. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    send_message_api_chat_sessions__session_id__messages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatMessageBody"];
            };
        };
        responses: {
            /** @description The updated conversation view. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    build_plan_api_chat_sessions__session_id__build_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The conversation view, including `plan` (ready for review). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reporting_runs_api_reporting_runs_get: {
        parameters: {
            query?: {
                role?: components["schemas"]["Role"];
                /** @description Filter by target base URL */
                target?: string | null;
                /** @description pass | fail | inconclusive */
                verdict?: string | null;
                limit?: number;
                offset?: number;
                since?: string | null;
                until?: string | null;
                plan_id?: string | null;
                project_id?: string | null;
                environment?: string | null;
                release_label?: string | null;
                include_overview?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `role`, `count`, `total`, `runs` and optional `overview`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reporting_trend_api_reporting_trend_get: {
        parameters: {
            query?: {
                metric?: string;
                /** @description Filter by target base URL */
                target?: string | null;
                /** @description Filter by plan */
                plan_id?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `metric`, `target`, `plan_id`, `points`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_projects_api_projects_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_project_api_projects_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectBody"];
            };
        };
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_project_api_projects__project_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectBody"];
            };
        };
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    project_dashboard_api_projects__project_id__dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    admin_dashboard_api_admin_dashboard_get: {
        parameters: {
            query?: never;
            header?: {
                "x-perfagent-admin"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    attach_test_api_plans__plan_id__project_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AttachBody"];
            };
        };
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_workloads_api_plans__plan_id__workloads_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_workload_api_plans__plan_id__workloads_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkloadBody"];
            };
        };
        responses: {
            /** @description Successful response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `status`, `database` (backend, host, name, schema state). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    tools_api_tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `tools`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_audit_api_audit_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `events`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    usage_total_api_usage_total_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `tokens`, `cost_usd`, `ai_calls`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_traces_api_traces_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `traces`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_api_runs_get: {
        parameters: {
            query?: {
                limit?: number;
                project_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `runs`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sla_api_sla_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `profiles`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    create_sla_api_sla_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SlaProfileBody"];
            };
        };
        responses: {
            /** @description `id`, `name`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_sla_api_sla__sla_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sla_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `deleted`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    runs_trend_api_runs_trend_get: {
        parameters: {
            query?: {
                plan_id?: string;
                limit?: number;
                workload_version?: string;
                mode?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `points`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_saved_report_api_runs__result_id__saved_report_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                result_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The saved report. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_data_api_data_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_data_api_data_post"];
            };
        };
        responses: {
            /** @description `data_file_id`, `filename`, `fields`, `row_count`, `source_format`, `warnings`, `sample_rows`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_data_file_api_data__data_file_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                data_file_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `data_file_id`, `filename`, `fields`, `row_count`, `source_format`, `sample_rows`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_endpoints_api_api_import_endpoints_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_endpoints_api_api_import_endpoints_post"];
            };
        };
        responses: {
            /** @description `endpoints` (method, path, example body), `source`, `base_url`, `warnings`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_plan_api_plan_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanRequest"];
            };
        };
        responses: {
            /** @description `plan_id`, `load_model`, `evaluation` (grounding checks), `guardrail` (what was redacted), `rationale`, `usage`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    dynamize_api_dynamize_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DynamizeBody"];
            };
        };
        responses: {
            /** @description `body`, `changed_fields`, `notes`, `guardrail`, `usage`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suggest_checks_api_suggest_checks_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuggestChecksBody"];
            };
        };
        responses: {
            /** @description `checks`, `notes`, `guardrail` (what was redacted), `usage`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    load_profile_api_load_profile_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoadProfileBody"];
            };
        };
        responses: {
            /** @description `load_profile` (stages), `max_users`, `peak_users`, `total_seconds`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    request_preview_api_request_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RequestPreviewBody"];
            };
        };
        responses: {
            /** @description `steps` — for each: `requests` (method, url, body), `fields` (source of each value), `run_time_values`, `undefined` — plus `row_mode`, `rows_available`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_api_plan__plan_id__generate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerateBody"];
            };
        };
        responses: {
            /** @description `script_id`, `plan_id`, `tool`, `filename`, `content`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_plans_api_plans_get: {
        parameters: {
            query?: {
                project_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `plans`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_plan_api_plans__plan_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `plan_id`, `target`, `goal`, `load_model`, `scripts`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_script_api_scripts__script_id__download_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The script text, as an attachment. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/plain": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    api_preflight_api_preflight_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreflightBody"];
            };
        };
        responses: {
            /** @description Journey requests and checks, or endpoint reachability results. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    api_validate_script_api_scripts__script_id__validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `ok`, `status`, `message`, `detail`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_script_api_scripts__script_id__edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditScriptBody"];
            };
        };
        responses: {
            /** @description `script_id`, `plan_id`, and `script_edited` for a modified version. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_script_api_scripts_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadScriptBody"];
            };
        };
        responses: {
            /** @description `script_id`, `plan_id`, `tool`, `filename`, `content`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_available_api_run_available_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `k6` (true / false). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    execution_readiness_api_scripts__script_id__readiness_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `checks`, `execution`, `target`, `smoke_supported`, `verification`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_script_api_scripts__script_id__run_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                script_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["RunOptions"] | null;
            };
        };
        responses: {
            /** @description `run_id`, `status`, `message`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_status_api_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `run_id`, `status`, `message`, `elapsed_s`, `planned_load`, `snapshot`, `logs`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_stop_api_runs__run_id__stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `run_id`, `status`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_report_api_runs__run_id__report_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description `run_id`, `target`, `verdict`, `narrative`, `evaluation`, `diagnostics`, `baseline`, `logs`. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_logs_download_api_runs__run_id__logs_download_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The log text, as an attachment. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_report_download_api_runs__run_id__report_download_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description An HTML file, as an attachment. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metrics_api_metrics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Prometheus exposition text (not JSON). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
