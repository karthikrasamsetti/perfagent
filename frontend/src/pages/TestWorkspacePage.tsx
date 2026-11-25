import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'
import { initializeDisabled } from '../components/initializeDisabled'

export function TestWorkspacePage() {
return <>
<section className={"view"} id={"view-create"}>
<div className={"project-context"} id={"testProjectContext"}>

</div>
<nav className="stepper" id="stepper" aria-label="Test workflow">
  {[
    ['Describe', 'Target and endpoints'],
    ['Review plan', 'Edit and approve'],
    ['Verify', 'Checks and script'],
    ['Run', 'Live metrics'],
    ['Report', 'Verdict and evidence'],
  ].map(([title, description], index)=>
    <button type="button" className="step" data-step={index+1} key={title} aria-controls={'panel'+(index+1)}>
      <span className="num" aria-hidden="true">{index+1}</span>
      <span><span className="lbl">{title}</span><span className="sub">{description}</span></span>
    </button>
  )}
</nav>
<p className="sr-only" role="status" id="workflowAnnouncement" />
<div className={"wrap"}>
<div className={"panel show"} id={"panel1"}>
<div className="card workflow-stage-card">
<h2>
{"How do you want to start?"}
</h2>
<div className={"modeswitch"} role={"tablist"} aria-label={"How to start"}>
<button className={"modebtn"} role={"tab"} aria-controls="modeConv" id={"modeConvBtn"} onClick={handlers.h13} style={{"display": "none"} as CSSProperties}>
{"Conversation"}
</button>
<button className={"modebtn active"} role={"tab"} aria-controls="modeManual" id={"modeManualBtn"} onClick={handlers.h14}>
{"Manual form"}
</button>
<button className={"modebtn"} role={"tab"} aria-controls="modeScript" id={"modeScriptBtn"} onClick={handlers.h15}>
{"Import script"}
</button>
<button className={"modebtn"} role={"tab"} aria-controls="modeGit" id={"modeGitBtn"} onClick={handlers.h16}>
{"Import from Git"}
</button>
</div>
<p className={"hint"} id={"modeHint"} style={{"margin": "-4px 0 14px"} as CSSProperties}>

</p>
<div role="tabpanel" aria-labelledby="modeConvBtn" id={"modeConv"} style={{"display": "none"} as CSSProperties}>
<div className={"conv"}>
<div className={"conv-main"}>
<div className={"conv-head"}>
<b style={{"color": "var(--teal-d)"} as CSSProperties}>
{"Plan it in a conversation"}
</b>
<span className={"pill ghost"} id={"convStatus"}>
{"new"}
</span>
<div className={"spacer"}>

</div>
<select id={"convHistory"} onChange={handlers.h17} aria-label={"Recent conversations"}>
<option value={""}>
{"Recent conversations…"}
</option>
</select>
<button className={"btn ghost sm"} onClick={handlers.h18}>
{"＋ New"}
</button>
</div>
<div className={"conv-log"} id={"convLog"} aria-live={"polite"}>

</div>
<div className={"conv-compose"}>
<textarea id={"convInput"} placeholder={"Say what you want to test, answer a question, or ask for a change…"} aria-label={"Message"}>

</textarea>
<details style={{"marginTop": "6px"} as CSSProperties}>
<summary style={{"cursor": "pointer", "fontSize": "12.5px", "color": "var(--teal-d)"} as CSSProperties}>
{"+ attach a Postman / OpenAPI / HAR collection to this message (optional)"}
</summary>
<textarea id={"convCollection"} style={{"minHeight": "90px", "marginTop": "6px", "fontFamily": "ui-monospace,Menlo,monospace", "fontSize": "11.5px"} as CSSProperties} placeholder={"Paste collection JSON here (optional)"}>

</textarea>
</details>
<div className={"btnrow"}>
<button className={"btn"} id={"convSendBtn"} onClick={handlers.h19}>
{"Send"}
</button>
<span className={"muted"} style={{"fontSize": "12px"} as CSSProperties} id={"convHint"}>
{"Enter to send · Shift+Enter for a new line"}
</span>
<div className={"spacer"}>

</div>
<button className={"btn danger sm"} id={"convDeleteBtn"} onClick={handlers.h20} style={{"display": "none"} as CSSProperties}>
{"Delete conversation"}
</button>
</div>
<div className={"note err"} id={"convError"} style={{"display": "none"} as CSSProperties}>

</div>
</div>
</div>
<aside className={"conv-draft"}>
<div className={"conv-draft-title"}>
{"📝 Draft so far"}
</div>
<div id={"convDraft"}>

</div>
<div className={"note ok"} id={"convGuard"} style={{"display": "none"} as CSSProperties}>

</div>
<div className={"btnrow"} style={{"marginTop": "12px"} as CSSProperties}>
<button className={"btn"} id={"convBuildBtn"} onClick={handlers.h21} ref={initializeDisabled}>
{"Build plan →"}
</button>
</div>
<p className={"hint"} style={{"margin": "8px 0 0"} as CSSProperties}>
{"Builds a plan for you to review and edit. Nothing is generated or run until you approve it."}
</p>
</aside>
</div>
</div>
<div role="tabpanel" aria-labelledby="modeManualBtn" id={"modeManual"}>
<p className={"hint"}>
{"Enter a URL for a page test, or add endpoints for an API or journey. Review the suggested workload before sending traffic."}
</p>
<div className="describe-section">
  <h3>Target</h3>
  <div className="grid2">
    <div className="field">
      <label htmlFor="target">Target URL</label>
      <input id="target" type="url" placeholder="https://staging.example.com/products" />
    </div>
    <div className="field">
      <label htmlFor="goal">What should this test measure? <span className="muted">(optional)</span></label>
      <input id="goal" placeholder="e.g. Check product search during normal traffic" />
    </div>
  </div>
</div>
<div className="describe-section describe-load">
  <h3>Traffic and duration</h3>
  <div className="grid2">
    <div className="field">
      <label htmlFor="draftSchedule">How should traffic be scheduled?</label>
      <select id="draftSchedule" defaultValue="users">
        <option value="users">Virtual users with stages</option>
        <option value="rate">Requests per second</option>
        <option value="journey-rate">Journey starts per second</option>
        <option value="constant-vus">Keep virtual users steady</option>
        <option value="ramping-arrival-rate">Ramp journey starts per second</option>
        <option value="shared-iterations">Complete a total number of journeys</option>
        <option value="per-vu-iterations">Complete a set number of journeys per user</option>
      </select>
    </div>
    <div className="field">
      <label htmlFor="duration"><span className="describe-duration">Duration</span><span className="describe-fixed-only">Maximum duration</span> (seconds)</label>
      <input id="duration" type="number" min={1} step={1} defaultValue={60} required />
    </div>
  </div>
  <div className="grid2 describe-vu-only">
    <div className="field">
      <label htmlFor="profileType">Load profile</label>
      <select id="profileType" defaultValue="ramp">
        <option value="ramp">Load · ramp up, steady state, ramp down</option>
        <option value="stress">Stress · increase load in steps</option>
        <option value="spike">Spike · burst and recovery</option>
        <option value="soak">Soak · sustained traffic</option>
      </select>
    </div>
  </div>
  <div className="field describe-rate-only">
    <label htmlFor="draftRequestRate">Target requests per second</label>
    <input id="draftRequestRate" type="number" min={1} max={1000000} step={1} placeholder="15" />
    <p className="hint">PerfAgent uses the endpoints in Describe order as one journey. Review shows how many journey starts per second are needed for the request target.</p>
  </div>
  <div className="field describe-journey-rate-only">
    <label htmlFor="draftJourneyRate">Target journey starts per second</label>
    <input id="draftJourneyRate" type="number" min={1} max={1000000} step={1} placeholder="5" />
    <p className="hint">One iteration starts one journey. Each journey may send multiple HTTP requests.</p>
  </div>
  <div className="field describe-fixed-only">
    <label htmlFor="draftIterations">Iterations <span className="describe-per-user">per virtual user</span><span className="describe-shared-count">across all virtual users</span></label>
    <input id="draftIterations" type="number" min={1} max={1000000} step={1} defaultValue={100} />
    <p className="hint">One iteration completes one journey. k6 stops scheduling when the count or maximum duration is reached.</p>
  </div>
  <div className="describe-arrival-only">
    <div className="field"><label htmlFor="draftStartRate">Starting journeys per second</label><input id="draftStartRate" type="number" min={0} step={1} defaultValue={0} /></div>
    <div className="grid3">
      {['Ramp up', 'Hold', 'Ramp down'].map((phase,index)=><div className="field" key={phase}>
        <label htmlFor={'draftRateDuration'+index}>{phase} duration (seconds)</label>
        <input id={'draftRateDuration'+index} type="number" min={1} step={1} defaultValue={[12,36,12][index]} />
        <label htmlFor={'draftRateTarget'+index}>Target at end of {phase.toLowerCase()} (journeys/s)</label>
        <input id={'draftRateTarget'+index} type="number" min={0} step={1} defaultValue={[15,15,0][index]} />
      </div>)}
    </div>
    <p className="hint">Stage durations must add up to the test duration. The rate targets journey starts, and each journey can include multiple requests.</p>
  </div>
  <details className="field describe-ramp-only">
    <summary>Set exact ramp stages</summary>
    <div className="grid3">
      <div className="field"><label htmlFor="draftRampUp">Ramp up (seconds)</label><input id="draftRampUp" type="number" min={1} step={1} placeholder="12" /></div>
      <div className="field"><label htmlFor="draftHold">Steady state (seconds)</label><input id="draftHold" type="number" min={1} step={1} placeholder="36" /></div>
      <div className="field"><label htmlFor="draftRampDown">Ramp down (seconds)</label><input id="draftRampDown" type="number" min={1} step={1} placeholder="12" /></div>
    </div>
    <p className="hint">Enter all three durations. They must add up to the test duration.</p>
  </details>
  <div className="field describe-capacity">
    <label htmlFor="maxUsers"><span className="describe-user-label">Virtual users</span><span className="describe-open-label">Preallocated virtual users</span></label>
    <input id="maxUsers" type="number" min={1} max={1000000} step={1} defaultValue={50} required />
  </div>
</div>
<details className="field">
  <summary>Pass rules (optional)</summary>
  <div className="grid2">
    <div className="field">
      <label htmlFor="draftP95">Maximum p95 latency (ms)</label>
      <input id="draftP95" type="number" min="0" step="any" placeholder="500" />
    </div>
    <div className="field">
      <label htmlFor="draftErrorRate">Error rate must be below (%)</label>
      <input id="draftErrorRate" type="number" min="0" max="100" step="any" placeholder="1" />
    </div>
  </div>
  <p className="hint">Leave both blank to get suggested rules.</p>
</details>
<div className={"field"} style={{"marginTop": "4px"} as CSSProperties}>
<div className={"lblrow"}>
<label>
{"Import endpoints (optional)"}
</label>
<i className={"infohint"} data-tip={"Load endpoints automatically from an OpenAPI/Swagger spec, a Postman collection, or a HAR capture — instead of typing them."}>
{"i"}
</i>
</div>
<div className={"dz"} id={"impdz"} onClick={handlers.h22} style={{"padding": "10px"} as CSSProperties}>
{"\n          📥 Click to import from OpenAPI / Postman / HAR\n        "}
</div>
<input type={"file"} id={"importFile"} accept={".json,.har"} style={{"display": "none"} as CSSProperties} onChange={handlers.h23} />
<div className={"note info"} id={"importInfo"} style={{"display": "none"} as CSSProperties}>

</div>
</div>
<div className={"lblrow"}>
<label>
{"Endpoints"}
</label>
<i className={"infohint"} data-tip={"The API paths to test (method + path, e.g. POST /login). Add a body for POST/PUT. These become the requests each virtual user sends."}>
{"i"}
</i>
</div>
<div id={"endpoints"}>

</div>
<button className={"btn ghost sm"} onClick={handlers.h24}>
{"+ Add endpoint"}
</button>
<div className={"btnrow"}>
<button className={"btn"} id={"planBtn"} onClick={handlers.h25}>
{"Draft test"}
</button>
<span className={"hint"} style={{"margin": "0"} as CSSProperties}>
{"Calls your configured LLM (key in .env)"}
</span>
</div>
<div className={"statusline"} id={"planStatus"} role="status">

</div>
</div>
<div role="tabpanel" aria-labelledby="modeScriptBtn" id={"modeScript"} style={{"display": "none"} as CSSProperties}>
<div className={"field"}>
<label htmlFor={"exTestName"}>
{"Test name"}
</label>
<input id={"exTestName"} maxLength={120} placeholder={"e.g. Checkout regression"} />
</div>
<div className={"lblrow"}>
<label>
{"Target base URL"}
</label>
<i className={"infohint"} data-tip={"Where the script sends traffic — used for the report. The script's own BASE_URL still applies at run time."}>
{"i"}
</i>
</div>
<input id={"exTarget"} defaultValue={"http://127.0.0.1:8000"} />
<label style={{"marginTop": "12px"} as CSSProperties}>
{"Your k6 script"}
</label>
<label className={"dropzone"} htmlFor={"exFile"}>
<span className={"dz-icon"}>
{"📄"}
</span>
<span id={"exFileName"}>
{"Choose a "}
<b>
{".js"}
</b>
{" file — or paste the script below"}
</span>
</label>
<input type={"file"} id={"exFile"} accept={".js"} onChange={handlers.h26} style={{"display": "none"} as CSSProperties} />
<textarea id={"exContent"} style={{"minHeight": "150px", "marginTop": "8px", "fontFamily": "ui-monospace,Menlo,Consolas,monospace", "fontSize": "12px"} as CSSProperties} placeholder={"// paste your k6 script here, or choose a file above"}>

</textarea>
<div className={"btnrow"}>
<button className={"btn"} onClick={handlers.h27}>
{"Use this script →"}
</button>
<span className={"hint"} style={{"margin": "0"} as CSSProperties}>
{"Goes straight to the Script step, ready to validate & run."}
</span>
</div>
<div className={"statusline"} id={"exStatus"}>

</div>
</div>
<div role="tabpanel" aria-labelledby="modeGitBtn" id={"modeGit"} style={{"display": "none"} as CSSProperties}>
<div className={"grid3"} style={{"marginTop": "14px"} as CSSProperties}>
<div className={"field"}>
<label>
{"Repository URL"}
</label>
<input id={"impRepo"} placeholder={"https://github.com/org/perf-tests.git"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Branch"}
</label>
<input id={"impBranch"} defaultValue={"main"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Access token"}
</label>
<input id={"impToken"} type={"password"} placeholder={"Token with read access"} autoComplete={"new-password"} spellCheck={"false"} />
</div>
</div>
<p className={"hint"} style={{"margin": "6px 0 0"} as CSSProperties}>
{"The token is used only to read the repository and is never saved. Not needed for public repositories or SSH URLs (git@…)."}
</p>
<div className={"btnrow"} style={{"marginTop": "10px"} as CSSProperties}>
<button className={"btn ghost"} id={"impBrowseBtn"} onClick={handlers.h28}>
{"🔍 Browse repository"}
</button>
</div>
<div className={"statusline"} id={"impStatus"}>

</div>
<div id={"impResults"}>

</div>
<div id={"impScriptView"} style={{"display": "none", "marginTop": "12px"} as CSSProperties}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<b id={"impScriptTitle"}>

</b>
<span className={"pill ghost"} id={"impScriptTool"}>

</span>
<div className={"spacer"}>

</div>
<button className={"btn ghost sm"} onClick={handlers.h29}>
{"Close"}
</button>
</div>
<pre id={"impScriptBody"} style={{"maxHeight": "340px"} as CSSProperties}>

</pre>
<div id={"impUseRow"} style={{"display": "none"} as CSSProperties}>
<div className={"grid2"} style={{"alignItems": "end"} as CSSProperties}>
<div className={"field"}>
<label>
{"Target base URL for this script"}
</label>
<input id={"impUseTarget"} defaultValue={"http://127.0.0.1:8000"} />
</div>
<div className={"btnrow"} style={{"margin": "0 0 14px"} as CSSProperties}>
<button className={"btn"} onClick={handlers.h30}>
{"Use this script →"}
</button>
</div>
</div>
<p className={"hint"} style={{"margin": "0"} as CSSProperties}>
{"Loads it like the \"My k6 script\" tab: you can validate and run it, but it isn't linked to a PerfAgent plan."}
</p>
</div>
<p className={"hint"} id={"impViewOnly"} style={{"display": "none", "margin": "0"} as CSSProperties}>
{"Shown for reference — only k6 scripts can be run in PerfAgent."}
</p>
</div>
</div>
</div>
</div>
<div className="panel" id="panel2">
  <div className="card rv review-card">
    <header className="section-header review-heading">
      <div>
        <h2>Review test plan</h2>
        <p className="hint">Confirm the target, requests, and load before approving. Review sends no traffic.</p>
      </div>
      <span className="pill ghost" id="planMeta" style={{display: 'none'}} />
    </header>
    <div className="note" id="importNote" style={{display: 'none'}} />
    <section className="review-guide" aria-labelledby="reviewGuideTitle">
      <h3 id="reviewGuideTitle">Before you approve</h3>
      <p id="reviewDraftExplanation" hidden />
      <p>Confirm the target and load, then open each request to check what it sends and what a successful response looks like.</p>
      <ul id="reviewFindings" />
    </section>
    <div className="review-layout">
      <aside id="planSummary" className="review-summary" aria-label="What will run" />
      <div id="planForm" className="review-sections">
        <section className="review-section" aria-labelledby="reviewTargetTitle">
          <h3 id="reviewTargetTitle">Target</h3>
          <div id="reviewTargetOverview" />
          <details className="review-editor" name="review-editors">
            <summary>Edit target and connection</summary>
            <div className="review-editor-content">
<div className={"grid2"}>
<div className={"field"}>
<label htmlFor={"pfTestName"}>
{"Test name"}
</label>
<input id={"pfTestName"} maxLength={120} placeholder={"e.g. Checkout flow - staging"} onInput={handlers.h33} onChange={handlers.h34} />
</div>
<div className={"field"}>
<label htmlFor={"pfScriptFilename"}>
{"Script filename"}
</label>
<input id={"pfScriptFilename"} maxLength={120} placeholder={"e.g. checkout-flow.js"} aria-describedby="pfFilenameHint" onInput={handlers.h35} />
<p className="hint" id="pfFilenameHint">Use a filename without spaces or folders. For k6, end it in .js.</p>
</div>
</div>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<label htmlFor={"pfTarget"}>
{"Target base URL"}
</label>
<input id={"pfTarget"} onInput={handlers.h36} />
</div>
<div className={"btnrow"}>
<select id={"environmentPreset"} aria-label={"Saved environment"} style={{"width": "auto"} as CSSProperties} onChange={handlers.h43}>
<option value={""}>
{"Saved environments"}
</option>
</select>
<button className={"btn ghost sm"} onClick={handlers.h44}>
{"Save current environment"}
</button>
</div>
<details className={"rv-more"} id={"connDetails"}>
<summary>
{"Connection options — headers, environment, TLS "}
<span className={"muted"} id={"connCount"}>

</span>
</summary>
<div className={"rv-grid"} style={{"marginTop": "10px"} as CSSProperties}>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<label htmlFor={"environment"}>
{"Environment "}
<span className={"muted"} style={{"fontWeight": "400"} as CSSProperties}>
{"(optional label)"}
</span>
</label>
<input id={"environment"} placeholder={"dev / staging / prod"} onInput={handlers.h45} />
</div>
<div className={"field"} style={{"gridColumn": "span 2", "alignSelf": "end"} as CSSProperties}>
<label style={{"display": "inline-flex", "alignItems": "center", "gap": "7px", "cursor": "pointer", "fontSize": "13px", "marginBottom": "9px"} as CSSProperties}>
<input type={"checkbox"} id={"insecureTls"} style={{"width": "auto"} as CSSProperties} onChange={handlers.h46} />
{" Skip TLS certificate verification"}
<i className={"infohint"} data-tip={"For test or dev hosts whose HTTPS certificate does not match the hostname. Never use against production."}>
{"i"}
</i>
</label>
</div>
</div>
<div className={"lblrow"}>
<label>
{"Custom headers"}
</label>
<i className={"infohint"} data-tip={"Headers added to every request, e.g. Authorization: Bearer TOKEN or an API key. Values can reference a captured token as ${token}."}>
{"i"}
</i>
</div>
<div id={"headersList"}>

</div>
<button className={"btn ghost sm"} onClick={handlers.h47}>
{"+ Add header"}
</button>
</details>
            </div>
          </details>
        </section>
        <section className="review-section" aria-labelledby="reviewRequestsTitle">
          <h3 id="reviewRequestsTitle">Journeys &amp; response checks</h3>
          <details className="review-help">
            <summary>How do checks and changing values work?</summary>
            <dl>
              <dt>Response check</dt>
              <dd>Open a request and choose Add check. For JSON, select JSON field compares and enter a path such as <code>order.id</code>. Use a sample response if you need help choosing a check.</dd>
              <dt>Dataset value</dt>
              <dd>Upload a file under Test data. In the request body, choose From data file and select a column. In a path, use a placeholder such as <code>{'/accounts/${account_id}'}</code>.</dd>
              <dt>Generated value</dt>
              <dd>In the request body, choose Generated for a value the script should create at runtime, such as a random ID.</dd>
              <dt>Value from an earlier response</dt>
              <dd>Open the request that returns the value and add a capture, such as <code>order.id</code> saved as <code>order_id</code>. In a later request in the same journey, choose From an earlier response for a body field or use <code>{'${order_id}'}</code> in its path.</dd>
            </dl>
          </details>
          <div id="reviewRequestsOverview" />
          <details className="review-editor" name="review-editors">
            <summary>Edit journeys and requests</summary>
            <div className="review-editor-content">
<div id={"scenarios"}>

</div>
<div className={"btnrow"} style={{"marginTop": "4px"} as CSSProperties}>
<button className={"btn ghost sm"} onClick={handlers.h50}>
{"+ Add journey"}
</button>
</div>
            </div>
          </details>
          <div className="btnrow">
            <button className="btn ghost sm" id="previewBtn" onClick={handlers.h51}>Preview sample requests</button>
            <span className="hint">See what will be sent. Verify runs the requests and evaluates the checks.</span>
          </div>
          <div id="previewBox" style={{display: 'none'}} />
        </section>
        <section className="review-section" aria-labelledby="reviewWorkloadTitle">
          <h3 id="reviewWorkloadTitle">Load &amp; pass rules</h3>
          <details className="review-editor" name="review-editors">
            <summary>Edit load and pass rules</summary>
            <div className="review-editor-content">
<div className={"btnrow"}>
<select id={"savedWorkload"} aria-label={"Saved workload"} style={{"width": "auto"} as CSSProperties} onChange={handlers.h31}>
<option value={""}>
{"Saved workload profiles"}
</option>
</select>
<input id={"workloadName"} aria-label={"Workload profile name"} placeholder={"Average load / stress / soak"} style={{"width": "220px"} as CSSProperties} />
<button className={"btn ghost sm"} onClick={handlers.h32}>
{"Save workload"}
</button>
</div>
<div className="rv-grid">
<div className={"field"}>
<label htmlFor={"pfUsers"}>
{"Peak users"}
</label>
<input id={"pfUsers"} type={"number"} min={"1"} onChange={handlers.h37} />
</div>
<div className={"field"}>
<label htmlFor={"pfDuration"}>
{"Duration (seconds)"}
</label>
<input id={"pfDuration"} type={"number"} min={"3"} onChange={handlers.h38} />
</div>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<div className={"lblrow"} style={{"marginTop": "0"} as CSSProperties}>
<label htmlFor={"pfType"}>
{"Test type"}
</label>
<i className={"infohint"} data-tip={"Ramp = gradual up/steady/down. Spike = sudden burst. Soak = long steady load (find leaks). Stress = step past the limit to find the breaking point."}>
{"i"}
</i>
</div>
<select id={"pfType"} onChange={handlers.h39}>
<option value={"ramp"}>
{"Ramp — up, steady, down (balanced)"}
</option>
<option value={"spike"}>
{"Spike — sudden sharp burst to peak"}
</option>
<option value={"soak"}>
{"Soak — long steady hold (endurance)"}
</option>
<option value={"stress"}>
{"Stress — step up past the target to find limits"}
</option>
</select>
</div>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<label htmlFor={"tool"}>
{"Load tool"}
</label>
<select id={"tool"} onChange={handlers.h40}>

</select>
</div>
</div>
<div className={"rv-shape"} id={"pfShape"}>

</div>
<div id="pfExecutorOptions" />
<div className={"grid2"} style={{"marginTop": "12px"} as CSSProperties}>
<div className={"field"}>
<label htmlFor={"pfArrival"} id="pfArrivalLabel">
{"Target iterations/second (k6, optional)"}
</label>
<input id={"pfArrival"} type={"number"} min={"1"} max={"1000000"} placeholder={"Leave empty for user-based load"} onChange={handlers.h41} />
</div>
<div className={"field"}>
<label htmlFor={"pfArrivalVus"}>
{"Preallocated users for rate mode"}
</label>
<input id={"pfArrivalVus"} type={"number"} min={"1"} defaultValue={"10"} onChange={handlers.h42} />
</div>
</div>
<p className={"hint"}>
{"An iteration runs one journey and may send several requests. Rate mode uses the total duration above; ramp stages apply to user-based mode."}
</p>
<div id={"thresholds"}>

</div>
<div className={"btnrow"} style={{"marginTop": "4px", "flexWrap": "wrap"} as CSSProperties}>
<button className={"btn ghost sm"} onClick={handlers.h52}>
{"+ Add rule"}
</button>
<div className={"spacer"}>

</div>
<span className={"muted"} style={{"fontSize": "12px"} as CSSProperties}>
{"Saved rule sets:"}
</span>
<select id={"slaSelect"} style={{"width": "auto", "padding": "5px 8px"} as CSSProperties}>
<option value={""}>
{"— choose —"}
</option>
</select>
<button className={"btn ghost sm"} onClick={handlers.h53}>
{"Apply"}
</button>
<button className={"btn ghost sm"} onClick={handlers.h54}>
{"Save these…"}
</button>
</div>
            </div>
          </details>
        </section>
        <section className="review-section" aria-labelledby="reviewDataTitle">
          <h3 id="reviewDataTitle">Test data</h3>
          <p id="reviewDataOverview" className="hint" />
          <details className="review-editor" name="review-editors">
            <summary>Manage dataset</summary>
            <div className="review-editor-content">
<p className={"hint"} style={{"margin": "0 0 8px"} as CSSProperties}>
{"Real values your API expects, such as user names or branch codes. Each column can then be used in a request below."}
</p>
<button type="button" className="dz" id="dz" onClick={handlers.h48}>
{"Upload CSV, TSV, TXT, JSON, JSONL, or NDJSON"}
</button>
<input type={"file"} id={"dataFile"} accept={".csv,.tsv,.txt,.json,.jsonl,.ndjson"} style={{"display": "none"} as CSSProperties} onChange={handlers.h49} />
<div className={"note err"} id={"dataInfo"} style={{"display": "none"} as CSSProperties}>

</div>
<div id={"dataCard"} style={{"display": "none"} as CSSProperties}>

</div>
            </div>
          </details>
        </section>
      </div>
    </div>
    <details className="review-advanced">
      <summary>Advanced plan details</summary>
      <div className="review-editor-content">
<div className={"rv-trust"}>
<span className={"rv-chip"} id={"guardrailBadge"} style={{"display": "none"} as CSSProperties}>

</span>
<span className={"rv-chip"} id={"planEval"} style={{"display": "none"} as CSSProperties}>

</span>
<span className={"rv-chip"} id={"usagePill"} style={{"display": "none"} as CSSProperties}>

</span>
</div>
        <p id="reviewRationale" className="hint" />
<textarea id={"planJson"} style={{"display": "none", "minHeight": "340px", "fontFamily": "ui-monospace,Menlo,monospace", "fontSize": "12.5px"} as CSSProperties}>

</textarea>
<label className={"toggle"} style={{"margin": "14px 0 4px"} as CSSProperties}>
<input type={"checkbox"} id={"rawToggle"} style={{"width": "auto"} as CSSProperties} onChange={handlers.h55} />
{" Advanced: edit the whole plan as raw JSON\n      "}
</label>
      </div>
    </details>
<div className={"rv-actions"}>
<div className={"statusline"} id={"genStatus"}>

</div>
<div className={"rv-actions-row"}>
<button className={"btn ghost sm"} onClick={handlers.h56}>
{"← Back"}
</button>
<div className={"spacer"}>

</div>
<button className={"btn amber"} id={"genBtn"} onClick={handlers.h57}>
{"Approve & continue to Verify"}
</button>
</div>
</div>
</div>
</div>
<div className="panel" id="panel3">
  <section className="card verify-card" aria-labelledby="verifyHeading">
    <header className="section-header">
      <div>
        <h2 id="verifyHeading">Verify and run</h2>
        <p className="hint" id="scriptMeta">Generate a script from the approved test to continue.</p>
      </div>
      <span className="pill ghost" id="scriptPill" style={{display: 'none'}} />
    </header>
    <p className="verify-description">Verify sends requests with one virtual user to check each journey. Start load only when you’re ready to run the configured workload.</p>
    <div className="verify-controls">
      <div className="field">
        <label htmlFor="releaseLabel">Release or commit label <span className="muted">(optional)</span></label>
        <input id="releaseLabel" maxLength={100} placeholder="e.g. release-2.4" />
      </div>
      <div className="btnrow">
        <button className="btn" id="preflightBtn" onClick={handlers.h65} ref={initializeDisabled}>Verify test</button>
        <button className="btn ghost" id="runBtn" onClick={handlers.h66} ref={initializeDisabled}>Start load test</button>
      </div>
    </div>
    <div className="note" id="preflightResult" role="status" style={{display: 'none'}} />
    <div className="verify-secondary btnrow">
      <button className="btn ghost sm" onClick={handlers.h60}>Back to plan</button>
      <button className="btn ghost sm" onClick={handlers.h58}>Check readiness</button>
      <button className="btn ghost sm" onClick={handlers.h59}>Run 10-second smoke test</button>
    </div>
    <div id="readinessResult" className="note info" style={{display: 'none'}} role="status" />
    <div className="note warn" id="runHint" style={{display: 'none'}} />
  </section>
  <details className="card script-details">
    <summary>Generated script</summary>
    <div className="btnrow">
      <button className="btn ghost sm" id="editBtn" onClick={handlers.h61}>Edit script</button>
      <button className="btn ghost sm" id="regenBtn" onClick={handlers.h62} style={{display: 'none'}}>Regenerate</button>
      <button className="btn ghost sm" id="dlBtn" onClick={handlers.h63} ref={initializeDisabled}>Download</button>
      <button className="btn ghost sm" id="validateBtn" onClick={handlers.h64} ref={initializeDisabled}>Validate syntax</button>
    </div>
    <div className="note" id="validateResult" role="status" style={{display: 'none'}} />
    <pre id="scriptOut">The generated script appears here.</pre>
    <textarea id="scriptEdit" aria-label="Edit generated script" style={{display: 'none'}} />
    <div className="note info" id="editNote" style={{display: 'none'}}>Edits create a new script version when you verify, validate, or run.</div>
  </details>
  <details className="card script-version-history" id="scriptVersionHistory">
    <summary>Script history</summary>
    <p className="hint">Versions preserve the script and inputs used for each run. Open an older version here to inspect or download it.</p>
    <div id="scriptVersionList" />
    <pre id="scriptVersionPreview" hidden />
  </details>
<div className={"card"} id={"gitCard"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"} as CSSProperties}>
<h2 style={{"margin": "0"} as CSSProperties}>
{"Save to Git for CI/CD"}
</h2>
<span className={"muted"} id={"gitSaved"} style={{"fontSize": "12px", "display": "none"} as CSSProperties}>

</span>
</div>
<p className={"hint"}>
{"Saves this test into a named k6 framework with ready-made pipelines. Secrets (auth headers) are never committed; CI provides them."}
</p>
<div className={"grid2"}>
<div className={"field"}>
<label>
{"Framework name"}
</label>
<input id={"gitFw"} placeholder={"e.g. payments-perf"} />
</div>
<div className={"field"}>
<label>
{"Test name"}
</label>
<input id={"gitTest"} placeholder={"e.g. checkout-peak"} />
</div>
</div>
<div className={"grid3"}>
<div className={"field"}>
<label>
{"Repository URL"}
</label>
<input id={"gitRepo"} placeholder={"https://github.com/org/perf-tests.git"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Branch"}
</label>
<input id={"gitBranch"} defaultValue={"main"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Access token"}
</label>
<input id={"gitToken"} type={"password"} placeholder={"Token with push access"} autoComplete={"new-password"} spellCheck={"false"} />
</div>
</div>
<p className={"hint"} id={"gitHint"} style={{"margin": "-6px 0 12px"} as CSSProperties}>
{"The token is used only for this push and is never saved. Not needed for SSH URLs (git@…). Use a new framework name for a new folder — PerfAgent never writes into folders it didn't create."}
</p>
<div className={"field"}>
<label>
{"Pipelines to include"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"gitCi"} defaultValue={"github"} defaultChecked />
{" GitHub Actions"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"gitCi"} defaultValue={"jenkins"} defaultChecked />
{" Jenkins"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"gitCi"} defaultValue={"azure"} defaultChecked />
{" Azure DevOps"}
</label>
<label className={"chk"}>
<input type={"checkbox"} className={"gitCi"} defaultValue={"gitlab"} defaultChecked />
{" GitLab"}
</label>
</div>
<div className={"field"}>
<label className={"chk"}>
<input type={"checkbox"} id={"gitData"} />
{" Also commit the test-data file (only if it holds no real customer data)"}
</label>
</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} id={"gitZipBtn"} onClick={handlers.h67} ref={initializeDisabled}>
{"⬇ Download framework (.zip)"}
</button>
<div className={"spacer"}>

</div>
<button className={"btn"} id={"gitBtn"} onClick={handlers.h68} ref={initializeDisabled}>
{"⇪ Push to Git"}
</button>
</div>
<div className={"statusline"} id={"gitStatus"}>

</div>
</div>
<div className={"card"} id={"jenkinsCard"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0"} as CSSProperties}>
{"Run in Jenkins"}
</h2>
<span className={"pill ghost"} id={"jkPill"} style={{"display": "none"} as CSSProperties}>

</span>
<a id={"jkLink"} href={"#"} target={"_blank"} rel={"noopener"} style={{"display": "none", "fontSize": "12.5px"} as CSSProperties}>
{"Open build in Jenkins ↗"}
</a>
<span className={"muted"} id={"jkSaved"} style={{"fontSize": "12px", "display": "none"} as CSSProperties}>

</span>
</div>
<p className={"hint"}>
{"Triggers the Jenkins pipeline for a test you saved to Git and follows it here. Jenkins runs the version in Git — push your latest changes first."}
</p>
<div className={"grid3"}>
<div className={"field"}>
<label>
{"Jenkins URL"}
</label>
<input id={"jkUrl"} placeholder={"https://jenkins.mycompany.com"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Jenkins user name"}
</label>
<input id={"jkUser"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"API token"}
</label>
<input id={"jkToken"} type={"password"} placeholder={"Jenkins → your name → Security → API Token"} autoComplete={"new-password"} spellCheck={"false"} />
</div>
</div>
<div className={"grid3"}>
<div className={"field"}>
<label>
{"Job name"}
</label>
<input id={"jkJob"} placeholder={"e.g. demo-perf  (folders: perf/demo-perf)"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Test"}
</label>
<input id={"jkTest"} placeholder={"test name, or all"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Environment"}
</label>
<input id={"jkEnv"} defaultValue={"dev"} autoComplete={"off"} />
</div>
</div>
<p className={"hint"} id={"jkHint"} style={{"margin": "-6px 0 12px"} as CSSProperties}>
{"The API token is used only for these calls and is never saved. The job needs Jenkins credentials for the test's secrets (e.g. PERF_HEADER_AUTHORIZATION)."}
</p>
<div id={"jkSetup"} style={{"display": "none", "border": "1px solid var(--line)", "borderRadius": "12px", "padding": "12px 14px", "marginBottom": "12px"} as CSSProperties}>
<b style={{"fontSize": "13px"} as CSSProperties}>
{"Set up the Jenkins job"}
</b>
<p className={"hint"} style={{"margin": "4px 0 10px"} as CSSProperties}>
{"Creates the Pipeline job (or updates it if it exists) so it builds "}
<code className={"k"}>
{"<framework>/ci/Jenkinsfile"}
</code>
{" from your repository, with the Test and Environment parameters ready — no manual first build. Needs the Job/Create permission."}
</p>
<div className={"grid2"}>
<div className={"field"}>
<label>
{"Repository URL"}
</label>
<input id={"jkRepo"} placeholder={"https://github.com/org/perf-tests.git"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Branch"}
</label>
<input id={"jkBranch"} defaultValue={"main"} autoComplete={"off"} />
</div>
</div>
<div className={"grid2"}>
<div className={"field"}>
<label>
{"Framework name"}
</label>
<input id={"jkFw"} placeholder={"e.g. demo-perf"} autoComplete={"off"} />
</div>
<div className={"field"}>
<label>
{"Git credentials ID in Jenkins (private repositories)"}
</label>
<input id={"jkGitCred"} placeholder={"optional, e.g. github-pat"} autoComplete={"off"} />
</div>
</div>
<div className={"btnrow"} style={{"marginTop": "4px"} as CSSProperties}>
<button className={"btn ghost sm"} onClick={handlers.h69}>
{"Create / update job"}
</button>
</div>
</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} onClick={handlers.h70}>
{"⚙ Set up Jenkins job"}
</button>
<div className={"spacer"}>

</div>
<button className={"btn ghost"} id={"jkStopBtn"} onClick={handlers.h71} ref={initializeDisabled}>
{"■ Stop"}
</button>
<button className={"btn"} id={"jkRunBtn"} onClick={handlers.h72}>
{"▶ Run in Jenkins"}
</button>
</div>
<div className={"statusline"} id={"jkStatus"}>

</div>
<div id={"jkResults"} style={{"display": "none", "marginTop": "12px"} as CSSProperties}>

</div>
<pre id={"jkLog"} style={{"display": "none", "maxHeight": "260px", "marginTop": "12px", "fontSize": "11.5px"} as CSSProperties}>

</pre>
</div>
</div>
<div className={"panel"} id={"panel4"}>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0"} as CSSProperties}>
{"Live run"}
</h2>
<span className={"pill ghost"} id={"runPill"}>
{"idle"}
</span>
<div className={"spacer"}>

</div>
<button className={"btn danger sm"} id={"stopBtn"} onClick={handlers.h73} ref={initializeDisabled}>
{"■ Stop"}
</button>
</div>
<div className="statusline" id="runStatus" role="status">

</div>
<canvas id={"liveChart"} role="img" aria-label="Live throughput, latency, and errors over time" height={"120"} style={{"width": "100%", "margin": "6px 0 14px", "border": "1px solid var(--line)", "borderRadius": "12px", "background": "#fcfcfb"} as CSSProperties}>

</canvas>
<div className={"tiles"}>
<div className={"tile"}>
<div className={"v"} id={"mElapsed"}>
{"0s"}
</div>
<div className={"l"}>
{"Elapsed"}
</div>
</div>
<div className={"tile"}>
<div className={"v"} id={"mReqs"}>
{"0"}
</div>
<div className={"l"}>
{"Requests"}
</div>
</div>
<div className={"tile"}>
<div className={"v"} id={"mRps"}>
{"0"}
</div>
<div className={"l"}>
{"Req/sec"}
</div>
</div>
<div className={"tile"}>
<div className={"v"} id={"mErr"}>
{"0%"}
</div>
<div className={"l"}>
{"Error rate"}
</div>
</div>
<div className={"tile"}>
<div className={"v"} id={"mP95"}>
{"0 ms"}
</div>
<div className={"l"}>
{"p95 latency"}
</div>
</div>
<div className={"tile"}>
<div className={"v"} id={"mP99"}>
{"0 ms"}
</div>
<div className={"l"}>
{"p99 latency"}
</div>
</div>
<div className="tile">
  <div className="v" id="mActiveVus">—</div>
  <div className="l">Active VUs / planned peak</div>
</div>
<div className="tile">
  <div className="v" id="mIterationRate">—</div>
  <div className="l">Iterations/s / target</div>
</div>
<div className="tile" id="mIterationsTile" hidden>
  <div className="v" id="mIterations">—</div>
  <div className="l" id="mIterationsLabel">Iterations completed / planned</div>
</div>
<div className="tile">
  <div className="v" id="mDroppedIterations">—</div>
  <div className="l">Dropped iterations</div>
</div>
</div>
<table id={"epTable"}>
<thead>
<tr>
<th>
{"Endpoint"}
</th>
<th>
{"Requests"}
</th>
<th>
{"Failed"}
</th>
<th>
{"Avg (ms)"}
</th>
<th>
{"p95 (ms)"}
</th>
</tr>
</thead>
<tbody>

</tbody>
</table>
<details style={{"marginTop": "14px"} as CSSProperties} id={"logDetails"}>
<summary style={{"cursor": "pointer", "fontSize": "13px", "fontWeight": "600", "color": "var(--teal-d)"} as CSSProperties}>
{"📜 Live run logs "}
<span className={"muted"} id={"logCount"}>

</span>
</summary>
<pre id={"runLogs"} style={{"marginTop": "8px", "background": "#16201c", "color": "#d7e4dd", "padding": "12px 14px", "borderRadius": "10px", "fontFamily": "ui-monospace,Menlo,Consolas,monospace", "fontSize": "11.5px", "lineHeight": "1.5", "maxHeight": "280px", "overflow": "auto", "whiteSpace": "pre-wrap"} as CSSProperties}>

</pre>
</details>
</div>
</div>
<div className={"panel"} id={"panel5"}>
<div className="card report-result" style={{"padding": "0", "overflow": "hidden"} as CSSProperties}>
<div className={"rpt-hero na"} id={"verdictHero"}>
<div className={"rpt-hero-emoji"} id={"verdictEmoji"}>
{"⏳"}
</div>
<div style={{"flex": "1"} as CSSProperties}>
<div className={"rpt-hero-title"} id={"verdictHeadline"}>
{"Waiting for a finished run…"}
</div>
<div className={"rpt-hero-sub"} id={"verdictSub"}>

</div>
</div>
<button className={"btn"} onClick={handlers.h74} style={{"background": "rgba(255,255,255,.22)", "border": "1px solid rgba(255,255,255,.3)"} as CSSProperties}>
{"⬇ Download report"}
</button>
</div>
<div id="reportContext" className="report-identity" />
<div className="report-overview">
<section className="report-story" aria-labelledby="reportStoryTitle">
  <h2 id="reportStoryTitle">What happened</h2>
  <p id="reportSummary" />
  <p hidden id="reportDropsSummary"><a id="reportDropsLink" href="#reportTimeline" /></p>
  <p id="reportPartial" className="note warn" hidden />
</section>
<aside className="report-evidence-summary" id="reportEvidenceSummary" aria-label="Key evidence" hidden />
</div>
<div className={"btnrow"} style={{"margin": "16px 0"} as CSSProperties}>
<button className={"btn"} id={"rerunBtn"} onClick={handlers.h75} ref={initializeDisabled}>
{"Run again"}
</button>
<span className={"muted"} id={"rerunNote"} role={"status"}>

</span>
</div>
<details className="report-baseline-actions"><summary>Baseline options</summary><div className={"btnrow"}>
<button className={"btn ghost sm"} onClick={handlers.h76}>
{"Use as baseline"}
</button>
<button className={"btn ghost sm"} onClick={handlers.h77}>
{"Clear selected baseline"}
</button>
<span className={"muted"} id={"baselineSelection"} role={"status"}>

</span>
</div></details>
<div className={"kpi-grid"} id={"kpiGrid"}>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kRequests"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"Requests"}
</div>
</div>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kErr"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"Error rate"}
</div>
</div>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kRps"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"Throughput"}
</div>
</div>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kP95"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"p95 latency"}
</div>
</div>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kP99"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"p99 latency"}
</div>
</div>
<div className={"kpi"}>
<div className={"kpi-v"} id={"kAvg"}>
{"—"}
</div>
<div className={"kpi-l"}>
{"Avg latency"}
</div>
</div>
</div>
</div>
<section id="reportHighlights" className="card" aria-label="Threshold results" />
<details className="card report-drilldown" id="reportTimeline" open>
  <summary>Timeline &amp; trends</summary>
  <p className="hint" id="reportSampleNote" />
  <div id="reportTimelineCharts" hidden>
    <p className="hint" id="reportPlannedPhases" hidden />
    <p className="hint" id="reportDropMarker" hidden />
    <div className="report-sample-picker">
      <label htmlFor="reportSampleIndex">Inspect a recorded sample</label>
      <input type="range" id="reportSampleIndex" min="0" step="1" />
      <output id="reportSampleReadout" htmlFor="reportSampleIndex" />
    </div>
    <div className="report-metric-charts">
      <figure><figcaption>Throughput (requests/s)</figcaption><canvas id="reportLoadChart" role="img" aria-label="Throughput by elapsed time" /></figure>
      <figure><figcaption>p95 latency (ms)</figcaption><canvas id="reportLatencyChart" role="img" aria-label="p95 latency by elapsed time" /></figure>
      <figure><figcaption>Error rate (%)</figcaption><canvas id="reportErrorsChart" role="img" aria-label="Error rate by elapsed time" /></figure>
    </div>
  </div>
  <details id="reportTimelineData"><summary>View recorded samples</summary><div id="reportSampleTable" className="table-scroll" /></details>
<div className={"card"}>
<div className={"rpt-section-h"}>
{"📊 Trend across runs"}
</div>
<canvas id={"trendChart"} height={"150"} style={{"width": "100%", "marginTop": "10px"} as CSSProperties}>

</canvas>
<div className={"muted"} style={{"fontSize": "11.5px", "marginTop": "4px"} as CSSProperties} id={"trendNote"}>
{"p95 latency across recent runs of this plan"}
</div>
</div>
</details>
<details className="card report-drilldown" id="reportEndpointDetails">
  <summary>Requests, journeys &amp; workload</summary>
  <div id="reportDetails" />
  <div id="checksCard" style={{display: 'none'}}>
    <h3>Response checks</h3>
    <div id="checksBody" />
  </div>
</details>
<details className="card report-drilldown" id="reportDiagnosisDetails">
  <summary>Diagnosis &amp; baseline comparison</summary>
  <span className="note" id="reportEval" style={{display: 'none'}} />
<div className={"rpt-cols"}>
<div className={"card"}>
<div className={"rpt-section-h"}>
{"🔍 Diagnosis"}
</div>
<div id={"diagnostics"}>

</div>
</div>
<div className={"card"}>
<div className={"rpt-section-h"}>
{"📈 vs. previous run"}
</div>
<div id={"baseline"}>

</div>
</div>
</div>
</details>
<details className="card report-drilldown" id="reportLogsCard" style={{display: 'none'}}>
<summary>Run logs</summary>
<div className="rpt-section-h">
<button className={"btn ghost sm"} style={{"marginLeft": "8px"} as CSSProperties} onClick={handlers.h78}>
{"⬇ Download"}
</button>
</div>
<pre id={"reportLogs"} style={{"marginTop": "8px", "background": "#16201c", "color": "#d7e4dd", "padding": "12px 14px", "borderRadius": "10px", "fontFamily": "ui-monospace,Menlo,Consolas,monospace", "fontSize": "11.5px", "lineHeight": "1.5", "maxHeight": "300px", "overflow": "auto", "whiteSpace": "pre-wrap"} as CSSProperties}>

</pre>
</details>
<div className={"rpt-cols"}>
<div className={"card"}>
<div id={"reportObs"}>

</div>
</div>
<div className={"card"}>
<div id={"reportRecs"}>

</div>
</div>
</div>
</div>
</div>
</section>
</>
}
