import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'
import { initializeDisabled } from '../components/initializeDisabled'

export function TestWorkspacePage() {
return <>
<section className={"view"} id={"view-create"}>
<div className={"project-context"} id={"testProjectContext"}>

</div>
<div className={"stepper"} id={"stepper"}>
<div className={"step"} data-step={"1"}>
<div className={"num"}>
{"1"}
</div>
<div>
<div className={"lbl"}>
{"Describe"}
</div>
<div className={"sub"}>
{"target & endpoints"}
</div>
</div>
</div>
<div className={"step"} data-step={"2"}>
<div className={"num"}>
{"2"}
</div>
<div>
<div className={"lbl"}>
{"Review plan"}
</div>
<div className={"sub"}>
{"edit & approve"}
</div>
</div>
</div>
<div className={"step"} data-step={"3"}>
<div className={"num"}>
{"3"}
</div>
<div>
<div className={"lbl"}>
{"Script"}
</div>
<div className={"sub"}>
{"generated code"}
</div>
</div>
</div>
<div className={"step"} data-step={"4"}>
<div className={"num"}>
{"4"}
</div>
<div>
<div className={"lbl"}>
{"Run"}
</div>
<div className={"sub"}>
{"live metrics"}
</div>
</div>
</div>
<div className={"step"} data-step={"5"}>
<div className={"num"}>
{"5"}
</div>
<div>
<div className={"lbl"}>
{"Report"}
</div>
<div className={"sub"}>
{"verdict"}
</div>
</div>
</div>
</div>
<div className={"wrap"}>
<div className={"panel show"} id={"panel1"}>
<div className={"card"}>
<h2>
{"How do you want to start?"}
</h2>
<div className={"modeswitch"} role={"tablist"} aria-label={"How to start"}>
<button className={"modebtn"} role={"tab"} id={"modeConvBtn"} onClick={handlers.h13} style={{"display": "none"} as CSSProperties}>
{"💬 Conversation"}
</button>
<button className={"modebtn active"} role={"tab"} id={"modeManualBtn"} onClick={handlers.h14}>
{"📝 Manual form"}
</button>
<button className={"modebtn"} role={"tab"} id={"modeScriptBtn"} onClick={handlers.h15}>
{"⚡ My k6 script"}
</button>
<button className={"modebtn"} role={"tab"} id={"modeGitBtn"} onClick={handlers.h16}>
{"📂 Import from Git"}
</button>
</div>
<p className={"hint"} id={"modeHint"} style={{"margin": "-4px 0 14px"} as CSSProperties}>

</p>
<div id={"modeConv"} style={{"display": "none"} as CSSProperties}>
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
<div id={"modeManual"}>
<p className={"hint"}>
{"Fill in the target and its endpoints. The AI drafts a plan from them; you add test data, checks and limits on the next step."}
</p>
<div className={"grid2"}>
<div className={"field"}>
<label>
{"Target base URL"}
</label>
<input id={"target"} defaultValue={"http://127.0.0.1:8000"} />
</div>
<div className={"field"}>
<label>
{"Goal (plain language)"}
</label>
<input id={"goal"} defaultValue={"Realistic load test of browsing and checkout"} />
</div>
</div>
<div className={"grid2"}>
<div className={"field"}>
<label>
{"Max users"}
</label>
<input id={"maxUsers"} type={"number"} defaultValue={"50"} />
</div>
<div className={"field"}>
<label>
{"Duration (seconds)"}
</label>
<input id={"duration"} type={"number"} defaultValue={"60"} />
</div>
</div>
<div className={"field"}>
<div className={"lblrow"}>
<label>
{"Test type"}
</label>
<i className={"infohint"} data-tip={"Ramp = gradual up/steady/down. Spike = sudden burst. Soak = long steady load (find leaks). Stress = step past the limit to find the breaking point."}>
{"i"}
</i>
</div>
<select id={"profileType"}>
<option value={"ramp"}>
{"Ramp — up, steady, down (balanced, default)"}
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
{"✨ Draft plan with AI"}
</button>
<span className={"hint"} style={{"margin": "0"} as CSSProperties}>
{"Calls your configured LLM (key in .env)"}
</span>
</div>
<div className={"statusline"} id={"planStatus"}>

</div>
</div>
<div id={"modeScript"} style={{"display": "none"} as CSSProperties}>
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
<div id={"modeGit"} style={{"display": "none"} as CSSProperties}>
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
<div className={"panel"} id={"panel2"}>
<div className={"card rv"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "4px", "flexWrap": "wrap"} as CSSProperties}>
<h2 style={{"margin": "0"} as CSSProperties}>
{"Review & approve the plan"}
</h2>
<span className={"pill ghost"} id={"planMeta"} style={{"display": "none"} as CSSProperties}>

</span>
</div>
<p className={"hint"}>
{"Read the summary. Open a section only if you want to change it. Nothing is sent to the target on this page."}
</p>
<div className={"note"} id={"importNote"} style={{"display": "none"} as CSSProperties}>

</div>
<div id={"planSummary"} style={{"display": "none", "background": "#f1f8f5", "border": "1px solid #cbe8dc", "borderRadius": "12px", "padding": "14px 16px", "margin": "10px 0 6px"} as CSSProperties}>

</div>
<div className={"rv-trust"}>
<span className={"rv-chip"} id={"guardrailBadge"} style={{"display": "none"} as CSSProperties}>

</span>
<span className={"rv-chip"} id={"planEval"} style={{"display": "none"} as CSSProperties}>

</span>
<span className={"rv-chip"} id={"usagePill"} style={{"display": "none"} as CSSProperties}>

</span>
</div>
<div id={"planForm"}>
<section className={"rv-sec"}>
<h3>
<span className={"rv-n"}>
{"1"}
</span>
{"Target & load"}
</h3>
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
<input id={"pfScriptFilename"} maxLength={120} placeholder={"e.g. checkout-flow.js"} onInput={handlers.h35} />
</div>
</div>
<div className={"rv-grid"}>
<div className={"field"} style={{"gridColumn": "span 2"} as CSSProperties}>
<label htmlFor={"pfTarget"}>
{"Target base URL"}
</label>
<input id={"pfTarget"} onInput={handlers.h36} />
</div>
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
<div className={"grid2"} style={{"marginTop": "12px"} as CSSProperties}>
<div className={"field"}>
<label htmlFor={"pfArrival"}>
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
</section>
<section className={"rv-sec"}>
<h3>
<span className={"rv-n"}>
{"2"}
</span>
{"Test data file "}
<span className={"rv-opt"}>
{"optional"}
</span>
</h3>
<p className={"hint"} style={{"margin": "0 0 8px"} as CSSProperties}>
{"Real values your API expects, such as user names or branch codes. Each column can then be used in a request below."}
</p>
<div className={"dz"} id={"dz"} onClick={handlers.h48}>
{"📁 Click to upload a CSV / TSV / TXT / JSON file"}
</div>
<input type={"file"} id={"dataFile"} accept={".csv,.tsv,.txt,.json,.jsonl"} style={{"display": "none"} as CSSProperties} onChange={handlers.h49} />
<div className={"note err"} id={"dataInfo"} style={{"display": "none"} as CSSProperties}>

</div>
<div id={"dataCard"} style={{"display": "none"} as CSSProperties}>

</div>
</section>
<section className={"rv-sec"}>
<h3>
<span className={"rv-n"}>
{"3"}
</span>
{"Journeys "}
<span className={"rv-opt"}>
{"what each virtual user does"}
</span>
</h3>
<div id={"scenarios"}>

</div>
<div className={"btnrow"} style={{"marginTop": "4px"} as CSSProperties}>
<button className={"btn ghost sm"} onClick={handlers.h50}>
{"+ Add journey"}
</button>
<div className={"spacer"}>

</div>
<button className={"btn ghost sm"} id={"previewBtn"} onClick={handlers.h51}>
{"🔍 Preview the requests"}
</button>
</div>
<div id={"previewBox"} style={{"display": "none"} as CSSProperties}>

</div>
</section>
<section className={"rv-sec"}>
<h3>
<span className={"rv-n"}>
{"4"}
</span>
{"Pass / fail rules"}
</h3>
<p className={"hint"} style={{"margin": "0 0 8px"} as CSSProperties}>
{"The test passes only if every rule holds."}
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
</section>
</div>
<textarea id={"planJson"} style={{"display": "none", "minHeight": "340px", "fontFamily": "ui-monospace,Menlo,monospace", "fontSize": "12.5px"} as CSSProperties}>

</textarea>
<label className={"toggle"} style={{"margin": "14px 0 4px"} as CSSProperties}>
<input type={"checkbox"} id={"rawToggle"} style={{"width": "auto"} as CSSProperties} onChange={handlers.h55} />
{" Advanced: edit the whole plan as raw JSON\n      "}
</label>
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
{"✓ Approve & generate script"}
</button>
</div>
</div>
</div>
</div>
<div className={"panel"} id={"panel3"}>
<div className={"card"}>
<div style={{"display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<h2 style={{"margin": "0"} as CSSProperties}>
{"Generated script"}
</h2>
<span className={"pill ghost"} id={"scriptPill"} style={{"display": "none"} as CSSProperties}>

</span>
</div>
<p className={"hint"} id={"scriptMeta"}>
{"Deterministic — same plan always produces the same script. You can edit it below to add custom logging or debugging."}
</p>
<pre id={"scriptOut"}>
{"The generated script appears here."}
</pre>
<textarea id={"scriptEdit"} style={{"display": "none", "minHeight": "360px", "width": "100%", "fontFamily": "ui-monospace,Menlo,Consolas,monospace", "fontSize": "11.5px", "lineHeight": "1.5"} as CSSProperties}>

</textarea>
<div className={"note info"} id={"editNote"} style={{"display": "none", "marginTop": "8px"} as CSSProperties}>
{"✏️ Editing mode — your changes (e.g. extra console.log for debugging) will be used when you validate or run. Click \"Regenerate\" to discard edits and restore the generated script."}
</div>
<div className={"field"} style={{"marginTop": "16px"} as CSSProperties}>
<label htmlFor={"releaseLabel"}>
{"Release or commit label (optional)"}
</label>
<input id={"releaseLabel"} maxLength={100} placeholder={"e.g. release-2.4 or commit SHA"} />
</div>
<div className={"btnrow"}>
<button className={"btn ghost"} onClick={handlers.h58}>
{"Check readiness"}
</button>
<button className={"btn ghost"} onClick={handlers.h59}>
{"Run 10-second smoke test"}
</button>
<span className={"muted"}>
{"Generated k6 scripts: one user per journey."}
</span>
</div>
<div id={"readinessResult"} className={"note info"} style={{"display": "none"} as CSSProperties} role={"status"}>

</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} onClick={handlers.h60}>
{"← Back to plan"}
</button>
<button className={"btn ghost sm"} id={"editBtn"} onClick={handlers.h61}>
{"✏️ Edit script"}
</button>
<button className={"btn ghost sm"} id={"regenBtn"} onClick={handlers.h62} style={{"display": "none"} as CSSProperties}>
{"↻ Regenerate"}
</button>
<button className={"btn ghost sm"} id={"dlBtn"} onClick={handlers.h63} ref={initializeDisabled}>
{"⬇ Download"}
</button>
<div className={"spacer"}>

</div>
<button className={"btn ghost"} id={"validateBtn"} onClick={handlers.h64} ref={initializeDisabled}>
{"✓ Validate script"}
</button>
<button className={"btn ghost"} id={"preflightBtn"} onClick={handlers.h65} ref={initializeDisabled}>
{"✈ Pre-flight check"}
</button>
<button className={"btn"} id={"runBtn"} onClick={handlers.h66} ref={initializeDisabled}>
{"▶ Run & monitor live"}
</button>
</div>
<div className={"note warn"} id={"runHint"} style={{"marginTop": "10px", "display": "none"} as CSSProperties}>

</div>
<div className={"note"} id={"validateResult"} style={{"display": "none"} as CSSProperties}>

</div>
<div className={"note"} id={"preflightResult"} style={{"display": "none"} as CSSProperties}>

</div>
</div>
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
<div className={"statusline"} id={"runStatus"}>

</div>
<canvas id={"liveChart"} height={"120"} style={{"width": "100%", "margin": "6px 0 14px", "border": "1px solid var(--line)", "borderRadius": "12px", "background": "#fcfcfb"} as CSSProperties}>

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
<div className={"card"} style={{"padding": "0", "overflow": "hidden"} as CSSProperties}>
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
<div className={"btnrow"} style={{"margin": "16px 0"} as CSSProperties}>
<button className={"btn"} id={"rerunBtn"} onClick={handlers.h75} ref={initializeDisabled}>
{"Run again"}
</button>
<span className={"muted"} id={"rerunNote"} role={"status"}>

</span>
</div>
<div className={"btnrow"}>
<button className={"btn ghost sm"} onClick={handlers.h76}>
{"Use as baseline"}
</button>
<button className={"btn ghost sm"} onClick={handlers.h77}>
{"Clear selected baseline"}
</button>
<span className={"muted"} id={"baselineSelection"} role={"status"}>

</span>
</div>
<div id={"reportContext"} className={"note info"}>

</div>
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
<div id={"reportDetails"} className={"card"}>

</div>
<div className={"rpt-cols"}>
<div className={"card"}>
<div className={"rpt-section-h"}>
{"📉 During this run"}
</div>
<canvas id={"tsChart"} height={"150"} style={{"width": "100%", "marginTop": "10px"} as CSSProperties}>

</canvas>
<div className={"muted"} style={{"fontSize": "11.5px", "marginTop": "4px"} as CSSProperties}>
{"RPS (teal) · p95 ms (amber) · error % (red) over time"}
</div>
</div>
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
</div>
<div className={"card"}>
<div className={"rpt-section-h"}>
{"📝 Executive summary "}
<span className={"note ok"} id={"reportEval"} style={{"display": "none", "margin": "0", "padding": "3px 9px", "fontSize": "11px"} as CSSProperties}>

</span>
</div>
<p id={"reportSummary"} style={{"fontSize": "14px", "lineHeight": "1.6", "margin": "8px 0 0"} as CSSProperties}>

</p>
</div>
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
<div className={"card"} id={"checksCard"} style={{"display": "none"} as CSSProperties}>
<div className={"rpt-section-h"}>
{"✔ Response checks"}
</div>
<div id={"checksBody"} style={{"marginTop": "8px"} as CSSProperties}>

</div>
</div>
<div className={"card"} id={"reportLogsCard"} style={{"display": "none"} as CSSProperties}>
<div className={"rpt-section-h"}>
{"📜 Run logs "}
<button className={"btn ghost sm"} style={{"marginLeft": "8px"} as CSSProperties} onClick={handlers.h78}>
{"⬇ Download"}
</button>
</div>
<pre id={"reportLogs"} style={{"marginTop": "8px", "background": "#16201c", "color": "#d7e4dd", "padding": "12px 14px", "borderRadius": "10px", "fontFamily": "ui-monospace,Menlo,Consolas,monospace", "fontSize": "11.5px", "lineHeight": "1.5", "maxHeight": "300px", "overflow": "auto", "whiteSpace": "pre-wrap"} as CSSProperties}>

</pre>
</div>
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
