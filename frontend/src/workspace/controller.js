/**
 * Compatibility controller extracted from the former single-page script.
 * React renders the page components; this module retains the advanced editor.
 * Window bindings exist only for generated editor rows with legacy DOM handlers.
 * New UI state should use React hooks and the typed API client instead.
 */
import { requestJson } from '../api/client'
import { resolveRoute } from '../routing/routes'
import { maxTrafficBytes, summarizeTraffic } from './trafficSummary'
import { journeyRouteOptions, normalizedJourneyWeights } from './journeyWeights'

let projects=[],currentProject=null,editingProjectId=null,newTestName='',importAfterProject=false,savedWorkloads=[];
let currentPlanId=null, currentScriptId=null, currentDataFileId=null, currentRunId=null, pollTimer=null;
let planModel=null;        // the editable plan object
let dataColumns=[];        // uploaded data file columns

/* ---------- stepper ---------- */
function goStep(n){
  const priorPanel=document.querySelector('#view-create.show .panel.show');
  const shouldMoveFocus=priorPanel&&priorPanel.id!=='panel'+n&&priorPanel.contains(document.activeElement);
  const verification=document.getElementById('preflightResult');
  if(n===3 && verification && verification.dataset.scriptId!==currentScriptId){
    verification.style.display='none';
    if(currentScriptId) loadSavedVerification(currentScriptId, verification);
  }
  if(n===3) loadScriptHistory();
  // the 5 panels live inside the Create view; make sure it is the visible view
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('show', s.id==='view-create'));
  markNavigation('create');
  closeMobNav();
  const mt=(typeof VIEW_META!=='undefined')?VIEW_META.create:null;
  if(mt){ document.getElementById('viewTitle').textContent=mt[0]; document.getElementById('viewSub').textContent=mt[1]; }
  if(n===5){document.getElementById('viewTitle').textContent=reportContext?.testName?reportContext.testName+' - report':'Performance report';document.getElementById('viewSub').textContent='Measured results, thresholds and workload comparisons';}
  for(let i=1;i<=5;i++){
    document.getElementById('panel'+i).classList.toggle('show', i===n);
  }
  document.querySelectorAll('.step').forEach(s=>{
    const si=+s.dataset.step;
    s.classList.toggle('active', si===n);
    s.classList.toggle('done', si<n);
    if(si===n) s.setAttribute('aria-current','step');
    else s.removeAttribute('aria-current');
    if(s instanceof HTMLButtonElement){
      s.disabled=si!==n&&!canOpenStep(si);
    }
  });
  const announcement=document.getElementById('workflowAnnouncement');
  const activeStep=document.querySelector('.step.active');
  if(announcement&&activeStep){
    const message='Step '+n+' of 5. '+activeStep.querySelector('.lbl').textContent;
    if(announcement.textContent!==message)announcement.textContent=message;
  }
  if(shouldMoveFocus)activeStep?.focus({preventScroll:true});
  if(document.documentElement.dataset.tour!=='true')window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});

publishStep(n);
}




/* ---------- step 1 mode toggle (chat / manual) ---------- */
const MODES={
  conv:  ['modeConv','modeConvBtn','Talk it through with the AI. It asks for what it needs and builds the plan with you.'],
  manual:['modeManual','modeManualBtn','Enter the target and endpoints yourself; the AI drafts the plan from them.'],
  script:['modeScript','modeScriptBtn','Already have a k6 script? Upload or paste it and go straight to validating and running it — no AI planning.'],
  git:   ['modeGit','modeGitBtn','Pull a test that PerfAgent saved to Git back as an editable plan, or pick up another k6 script from the repository.'],
};
function setMode(m){
  for(const k in MODES){
    document.getElementById(MODES[k][0]).style.display = (k===m)?'block':'none';
    const b=document.getElementById(MODES[k][1]);
    b.classList.toggle('active', k===m); b.setAttribute('aria-selected', k===m?'true':'false');
    if(b.getAttribute('role')==='tab')b.tabIndex=k===m?0:-1;
  }
  document.getElementById('modeHint').textContent=MODES[m][2];
}

function canOpenStep(n){
  return n===1||n===2&&Boolean(planModel)||n===3&&Boolean(currentScriptId)||
    n===4&&Boolean(currentRunId&&currentScriptId)||
    n===5&&Boolean(currentRunId&&reportContext?.runId===currentRunId);
}

/* ---------- conversation mode (multi-turn planning chat) ----------
   Talks to /api/chat/sessions. The server keeps the conversation (LangGraph,
   checkpointed), so a refresh or restart resumes it. The chat only builds the
   draft; "Build plan" hands it to the normal Review step. */
let convId=null, convView=null, convBusy=false;
const CONV_KEY='perfagent.conversation';
const CONV_EXAMPLES=[
  'Load test login and products at http://127.0.0.1:8000 with 10 users for 20 seconds',
  'Stress test POST /checkout on https://staging.example.com — each order needs a unique id',
  'I want to soak test my API for 10 minutes. What do you need from me?'
];

async function convApi(path, opts){
  if(path==='/sessions'&&opts?.method==='POST'){opts={...opts,body:JSON.stringify({...JSON.parse(opts.body||'{}'),project_id:currentProject?.project_id,test_name:newTestName})};}
  const r=await fetch('/api/chat'+path, opts||{});
  let j={}; try{ j=await r.json(); }catch(e){}
  if(!r.ok){ const err=new Error(j.detail||('request failed ('+r.status+')')); err.status=r.status; throw err; }
  return j;
}
function convRemember(id){ try{ if(id) localStorage.setItem(CONV_KEY+':'+(currentProject?.project_id||'legacy'),id); else localStorage.removeItem(CONV_KEY+':'+(currentProject?.project_id||'legacy')); }catch(e){} }
function convRecall(){ try{ return localStorage.getItem(CONV_KEY+':'+(currentProject?.project_id||'legacy')); }catch(e){ return null; } }

async function initConversation(){
  let cfg; try{ cfg=await convApi('/config'); }catch(e){ return; }
  if(!cfg.enabled) return;                       // switched off -> the other three tabs
  document.getElementById('modeConvBtn').style.display='';
  document.getElementById('convInput').addEventListener('keydown', e=>{
    if(e.key==='Enter' && !e.shiftKey && !e.isComposing){ e.preventDefault(); convSend(); }
  }, {signal:workspaceEvents.signal});
  const saved=convRecall();                      // read before the empty render clears it
  setMode('conv');
  convRender(null);
  convLoadHistory();
  if(saved) convOpen(saved, true);
}

async function convLoadHistory(){
  try{
    if(!currentProject)return;
    const j=await convApi('/sessions?limit=20'+projectQuery());
    const sel=document.getElementById('convHistory');
    const label={collecting:'gathering',ready:'ready',planned:'plan built'};
    sel.innerHTML='<option value="">Recent conversations…</option>'+j.sessions.map(x=>{
      const t=(x.title||'Untitled').slice(0,48)+((x.title||'').length>48?'…':'');
      return '<option value="'+esc(x.session_id)+'">'+esc(t)+' · '+(label[x.status]||x.status)+'</option>';
    }).join('');
    sel.value='';
  }catch(e){}
}
function convPick(id){ if(id) convOpen(id,false); document.getElementById('convHistory').value=''; }

async function convOpen(id, quiet){
  try{ convRender(await convApi('/sessions/'+encodeURIComponent(id))); }
  catch(e){
    if(e.status===404){ convRemember(null); convRender(null); }
    if(!quiet) convShowError(e.status===404?'That conversation no longer exists.':e.message);
  }
}
function convNew(){ convRemember(null); convShowError(''); convRender(null); document.getElementById('convInput').focus(); }

async function convDelete(){
  if(!convId || convBusy) return;
  if(!confirm('Delete this conversation? Plans already built from it are kept.')) return;
  try{ await convApi('/sessions/'+encodeURIComponent(convId),{method:'DELETE'}); }
  catch(e){ if(e.status!==404){ convShowError(e.message); return; } }
  convNew(); convLoadHistory();
}

function convShowError(msg){
  const el=document.getElementById('convError');
  el.style.display=msg?'flex':'none'; el.textContent=msg||'';
}
function convSetBusy(b){
  convBusy=b;
  document.getElementById('convSendBtn').disabled=b;
  document.getElementById('convBuildBtn').disabled=b || !(convView&&convView.ready);
}
function convBubble(role, kind, text){
  const d=document.createElement('div');
  d.className='msg '+(role==='user'?'user':'assistant')+(kind&&kind!=='text'?(' '+kind):'');
  d.textContent=text;                               // textContent: never interpreted as HTML
  return d;
}
function convScroll(){ const log=document.getElementById('convLog'); log.scrollTop=log.scrollHeight; }

function convRender(v){
  convView=v; convId=v?v.session_id:null; convRemember(convId);
  const log=document.getElementById('convLog'); log.innerHTML='';
  if(!v){
    const e=document.createElement('div'); e.className='conv-empty';
    e.innerHTML='<b>What would you like to load test?</b>Describe it in your own words. I\'ll ask for anything I still need, and you can keep refining before a plan is built.';
    CONV_EXAMPLES.forEach(t=>{
      const b=document.createElement('button'); b.type='button'; b.className='conv-chip'; b.textContent=t;
      b.onclick=()=>{ const i=document.getElementById('convInput'); i.value=t; i.focus(); };
      e.appendChild(b);
    });
    log.appendChild(e);
  } else {
    v.messages.forEach(m=>log.appendChild(convBubble(m.role, m.kind, m.content)));
  }
  const st=document.getElementById('convStatus');
  const names={collecting:['gathering details','pill na'],ready:['ready to build','pill pass'],planned:['plan built','pill pass']};
  const n=v?names[v.status]:null;
  st.textContent=n?n[0]:'new'; st.className=n?n[1]:'pill ghost';
  document.getElementById('convDeleteBtn').style.display=v?'':'none';
  document.getElementById('convHint').textContent=(v && v.turns_left<=3)
    ? (v.turns_left+' message'+(v.turns_left===1?'':'s')+' left in this conversation')
    : 'Enter to send · Shift+Enter for a new line';
  convRenderDraft(v);
  convSetBusy(convBusy);
  convScroll();
}

function convRenderDraft(v){
  const el=document.getElementById('convDraft');
  const guard=document.getElementById('convGuard');
  const btn=document.getElementById('convBuildBtn');
  if(!v){
    el.innerHTML='<p class="muted" style="margin:0;font-size:12.5px">The target, endpoints and load size appear here as we talk, so you can see exactly what the plan will be built from.</p>';
    guard.style.display='none'; btn.innerHTML='Build plan &rarr;'; return;
  }
  const d=v.draft, miss=v.missing||[];
  const dur=s=>s>=60 ? (Math.floor(s/60)+' min'+(s%60?(' '+(s%60)+' s'):'')) : (s+' s');
  const tag=a=>a?'<span class="dtag" title="You didn\'t say, so this default will be used">default</span>':'';
  let h='';
  h+='<div class="drow"><span class="dk">Target</span>'+(d.target_base_url
      ? '<span class="dv">'+esc(d.target_base_url)+'</span>'
      : '<span class="dv todo">needed</span>')+'</div>';
  h+='<div class="drow"><span class="dk">Test type</span><span class="dv">'+esc(d.profile_type)+'</span></div>';
  h+='<div class="drow"><span class="dk">Peak users</span><span class="dv">'+d.max_users+tag(d.assumed.max_users)+'</span></div>';
  h+='<div class="drow"><span class="dk">Duration</span><span class="dv">'+dur(d.duration_seconds)+tag(d.assumed.duration_seconds)+'</span></div>';
  h+='<div class="dsec">Endpoints</div>';
  if(d.endpoints.length){
    h+=d.endpoints.map(e=>'<div class="dep"><span class="m">'+esc(e.method)+'</span><span>'+esc(e.path)+
        (e.example_body?' <span class="dtag">body</span>':'')+'</span></div>'+
        (e.assertions||[]).map(check=>'<div class="muted">'+esc(checkLabel(check))+'</div>').join('')).join('');
  } else { h+='<div class="drow" style="border:0"><span class="dv todo">needed</span></div>'; }
  if(d.thresholds?.length){
    h+='<div class="dsec">Pass rules</div>'+d.thresholds.map(rule=>{
      const value=rule.metric==='error_rate'?Number((rule.value*100).toPrecision(15))+'%':rule.value+' ms';
      return '<div class="drow">'+esc(rule.metric+' '+rule.op+' '+value)+'</div>';
    }).join('');
  }
  const open=(v.questions||[]);
  if(open.length){
    h+='<div class="dsec">'+(miss.length?'Still needed':'Open questions')+'</div><ul class="dlist">'+
       open.map(q=>'<li>'+esc(q)+'</li>').join('')+'</ul>';
  }
  if(d.notes){ h+='<div class="dsec">Assumptions</div><div style="font-size:12.5px">'+esc(d.notes)+'</div>'; }
  if(d.secrets_masked){
    h+='<div class="note warn" style="margin-top:10px">🔒 A secret value was masked before the AI saw it. Set the real value in the review step, or use a data file.</div>';
  }
  el.innerHTML=h;
  const g=v.guardrail;
  if(g && g.total>0){ guard.style.display='flex';
    guard.innerHTML='🛡 <span><b>'+g.total+' sensitive value'+(g.total!==1?'s':'')+'</b> masked before the AI saw them ('+esc(g.detail)+')</span>'; }
  else guard.style.display='none';
  btn.innerHTML = v.plan_current ? 'Open plan in review &rarr;' : (v.plan ? 'Rebuild plan &rarr;' : 'Build plan &rarr;');
}

async function convSend(){
  if(convBusy) return;
  const input=document.getElementById('convInput'), coll=document.getElementById('convCollection');
  const text=input.value.trim(); if(!text){ input.focus(); return; }
  convShowError('');
  const log=document.getElementById('convLog');
  if(!convId) log.innerHTML='';
  log.appendChild(convBubble('user','text',text));           // show it straight away
  const typing=convBubble('assistant','typing','Thinking…'); log.appendChild(typing); convScroll();
  convSetBusy(true);
  const hadPlan=!!(convView&&convView.plan_current);
  const starting=!convId;
  try{
    const body=JSON.stringify({message:text, collection_text:coll.value.trim()});
    const opts={method:'POST',headers:{'Content-Type':'application/json'},body};
    const v=await convApi(starting?'/sessions':('/sessions/'+encodeURIComponent(convId)+'/messages'), opts);
    input.value=''; coll.value='';
    convBusy=false; convRender(v); refreshUsage();
    if(starting) convLoadHistory();
    // "go ahead" in chat built a fresh plan -> take the user to review it
    if(v.plan_current && !hadPlan) convOpenPlan(v.plan);
  }catch(e){
    typing.remove(); convBusy=false; convSetBusy(false);
    if(convView) convRender(convView); else if(starting) convRender(null);
    input.value=text;                                          // keep what they typed
    convShowError(e.message);
  }
  input.focus();
}

async function convBuild(){
  if(convBusy || !convView || !convView.ready) return;
  if(convView.plan_current){ convOpenPlan(convView.plan); return; }   // already built, nothing changed
  convShowError('');
  const log=document.getElementById('convLog');
  const typing=convBubble('assistant','typing','Drafting the plan…'); log.appendChild(typing); convScroll();
  convSetBusy(true);
  try{
    const v=await convApi('/sessions/'+encodeURIComponent(convId)+'/build',{method:'POST'});
    convBusy=false; convRender(v); refreshUsage(); convLoadHistory();
    if(v.plan_current) convOpenPlan(v.plan);
    else if(v.error) convShowError('The plan could not be drafted. Try again in a moment.');
  }catch(e){ typing.remove(); convBusy=false; convSetBusy(false); convShowError(e.message); }
}

/* Hand a conversation-built plan to the Review step — same as the other two modes. */
async function convOpenPlan(p){
  if(!p) return;
  if(currentPlanId!==p.plan_id){                    // don't overwrite edits made in review
    const projectId=currentProject?.project_id;
    const name=newTestName||p.load_model.test_name;
    if(projectId){
      try{await attachCurrentTest(p.plan_id,projectId,name);}
      catch(e){convShowError(e.message);return;}
      if(currentProject?.project_id!==projectId) return;
    }
    currentPlanId=p.plan_id; planModel=p.load_model;
    if(projectId) planModel.test_name=name;
    planRationale=p.rationale||'';
    setReviewSources(p.review_sources);
    document.getElementById('importNote').style.display='none';
    applyIntegrations(p.plan_id);
    renderPlanForm(); renderRawFromModel();
    showGuardrail(p.guardrail); showPlanEval(p.evaluation); showUsage(p.usage);
    document.getElementById('planMeta').style.display='inline-flex';
    document.getElementById('planMeta').textContent='drafted by '+p.provider+' (from conversation)';
    loadPlans();
  }
  goStep(2);
}


/* ---------- endpoints (step 1) ---------- */
function addEndpoint(method="GET",path="",body=""){
  const d=document.createElement('div');d.className='endpoint';
  d.innerHTML=`<select>${["GET","POST","PUT","PATCH","DELETE"].map(m=>`<option ${m===method?'selected':''}>${m}</option>`).join('')}</select>
    <input placeholder="/path" aria-label="Endpoint path" />
    <input class="bodyInput" aria-label="JSON request body" placeholder='body JSON e.g. {"user":"demo"}' />
    <button class="iconbtn gbtn" type="button" aria-label="Edit request body" title="Edit request body" onclick="openBodyEditor(this)">⋯</button>
    <button class="iconbtn" type="button" aria-label="Remove endpoint" onclick="this.parentElement.remove()">×</button>
    <details style="grid-column:1 / -1">
      <summary>Require a JSON field in the response</summary>
      <label>JSON field path <input class="draftJsonPath" placeholder="e.g. order.id" /></label>
      <p class="hint">Use this when a field must be present, even when the endpoint returns a successful status.</p>
    </details>`;
  const [pathInput, bodyInput]=d.querySelectorAll('input');
  pathInput.value=path;
  bodyInput.value=body;
  d.querySelector('select').setAttribute('aria-label', 'HTTP method');
  document.getElementById('endpoints').appendChild(d);
}


/* ---------- body editor modal + AI dynamize ---------- */
let _bodyTargetInput = null;
function openBodyEditor(btn){
  const row = btn.parentElement;
  _bodyTargetInput = row.querySelector('.bodyInput');
  const path = row.querySelectorAll('input')[0].value || '(no path)';
  document.getElementById('bodyModalPath').textContent = path;
  // pretty-print existing JSON if possible
  let v = _bodyTargetInput.value.trim();
  try { v = JSON.stringify(JSON.parse(v), null, 2); } catch(e) {}
  document.getElementById('bodyModalText').value = v;
  const hint=document.getElementById('bodyModalNote');
  if(currentDataFileId && dataColumns && dataColumns.length){
    hint.style.display='flex'; hint.className='note info';
    hint.innerHTML='📁 Data file columns available — the AI can pull real values from: '+
      dataColumns.map(c=>'<code class="k">${'+esc(c)+'}</code>').join(' ');
  } else { hint.style.display='none'; }
  document.getElementById('bodyModal').style.display='flex';
}
function closeBodyEditor(){ document.getElementById('bodyModal').style.display='none'; _bodyTargetInput=null; }
function saveBodyEditor(){
  const txt = document.getElementById('bodyModalText').value.trim();
  if(txt){
    try { JSON.parse(txt); } catch(e){
      const n=document.getElementById('bodyModalNote'); n.style.display='flex'; n.className='note err';
      n.textContent='Body is not valid JSON: '+e.message; return;
    }
  }
  if(_bodyTargetInput){ _bodyTargetInput.value = txt ? JSON.stringify(JSON.parse(txt)) : ''; }
  closeBodyEditor();
}
async function dynamizeBody(){
  const n=document.getElementById('bodyModalNote');
  const txt=document.getElementById('bodyModalText').value.trim();
  let parsed;
  try { parsed = JSON.parse(txt); } catch(e){
    n.style.display='flex'; n.className='note err'; n.textContent='Enter a valid JSON body first: '+e.message; return;
  }
  n.style.display='flex'; n.className='note info'; n.textContent='AI is adding dynamic data to the fields that should vary...';
  document.getElementById('dynBtn').disabled=true;
  try{
    const payload={body:parsed}; if(currentDataFileId) payload.data_file_id=currentDataFileId;
    const r=await fetch('/api/dynamize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'failed');
    document.getElementById('bodyModalText').value = JSON.stringify(j.body, null, 2);
    n.className='note ok';
    n.innerHTML = '✅ '+esc(j.notes||'Dynamic data added')+
      (j.changed_fields&&j.changed_fields.length ? '<br><span class="muted">Changed: '+j.changed_fields.map(esc).join(', ')+'</span>' : '');
  }catch(e){ n.className='note err'; n.textContent='Error: '+e.message; }
  finally{ document.getElementById('dynBtn').disabled=false; }
}

/* ---------- generator helper (insert dynamic data tokens) ---------- */
const GENERATORS = [
  ["${uuid}",                 "Unique ID (uuid)"],
  ["${randomEmail}",          "Unique email"],
  ["${randomFullName}",       "Random full name"],
  ["${randomCompanyName}",    "Random company"],
  ["${randomStreetAddress}",  "Random street address"],
  ["${randomCity}",           "Random city"],
  ["${randomState}",          "Random state"],
  ["${randomZipCode}",        "Random zip code"],
  ["${randomPhone}",          "Random phone"],
  ["${randomCatchPhrase}",    "Random phrase / note"],
  ["${randomBic}",            "Random code (BIC-like)"],
  ["${randomInt(1,100)}",     "Random number 1–100"],
  ["${randomString(8)}",      "Random text (8 chars)"],
  ["${dateOffset(3,'days')}", "Date N days from now"],
  ["${timestamp}",            "Current timestamp"],
  ["${randomFrom(a,b,c)}",    "Random choice from a list"],
  ["${sequential}",           "Unique per user+iteration"],
];
function toggleGenMenu(btn){
  // close any open menu first
  document.querySelectorAll('.genmenu').forEach(m=>m.remove());
  const existing = btn._menuOpen;
  if(existing){ btn._menuOpen=false; return; }
  const bodyInput = btn.parentElement.querySelector('.bodyInput');
  const menu=document.createElement('div'); menu.className='genmenu';
  menu.innerHTML = '<div class="genmenu-h">Insert dynamic value — each request gets a fresh one</div>' +
    GENERATORS.map(([tok,label])=>
      `<div class="genmenu-item" onmousedown="insertGen(event,this,'${tok.replace(/'/g,"\\'")}')">`+
      `<code>${tok}</code><span>${label}</span></div>`).join('');
  document.body.appendChild(menu);
  const r=btn.getBoundingClientRect();
  menu.style.left=(r.left-240+window.scrollX)+'px';
  menu.style.top=(r.bottom+4+window.scrollY)+'px';
  menu._bodyInput=bodyInput; btn._menuOpen=true;
  // close on outside click
  setTimeout(()=>{document.addEventListener('mousedown',closeGenMenus,{once:true});},0);
}
function closeGenMenus(){ document.querySelectorAll('.genmenu').forEach(m=>m.remove());
  document.querySelectorAll('.gbtn').forEach(b=>b._menuOpen=false); }
function insertGen(ev, item, token){
  ev.preventDefault();
  const menu=item.closest('.genmenu'); const inp=menu._bodyInput;
  // if the body is empty, start a JSON object with a field; else insert at cursor
  let v=inp.value;
  if(!v.trim()){
    const field = token.includes('Email')?'email':token.includes('uuid')?'id':'value';
    inp.value = `{"${field}": "${token}"}`;
  } else {
    const start=inp.selectionStart ?? v.length;
    inp.value = v.slice(0,start) + token + v.slice(inp.selectionEnd ?? start);
  }
  inp.focus();
  closeGenMenus();
}
function readEndpoints(){
  return [...document.querySelectorAll('#endpoints .endpoint')].map(d=>{
    const method=d.querySelector('select').value;
    const ins=d.querySelectorAll('input');
    const path=ins[0].value.trim(); const bodyRaw=ins[1].value.trim();
    const jsonPath=d.querySelector('.draftJsonPath').value.trim();
    if(!path){
      if(bodyRaw||jsonPath) throw new Error('Enter a path for the endpoint with a body or response check.');
      return null;
    }
    const ep={method,path};
    if(jsonPath) ep.assertions=[{kind:'json_path',op:'exists',path:jsonPath}];
    if(bodyRaw){ try{ep.example_body=JSON.parse(bodyRaw)}catch(e){throw new Error(`Body for ${method} ${path} isn't valid JSON: ${e.message}`)} }
    return ep;
  }).filter(Boolean);
}

async function loadTools(){
  const j=await (await fetch('/api/tools')).json();
  document.getElementById('tool').innerHTML=j.tools.map(t=>`<option value="${t}">${t}</option>`).join('');
}

/* ---------- draft plan ---------- */
export function applyTrafficRate(rate){
  const schedule=document.getElementById('draftSchedule');
  const input=document.getElementById('draftRequestRate');
  schedule.value='rate';
  schedule.dispatchEvent(new Event('change',{bubbles:true}));
  input.value=String(rate);
  input.dataset.trafficRate=String(rate);
}
async function doPlan(){
  if(!currentProject||!newTestName){showNewTestForm();return;}
  const status=document.getElementById('planStatus');
  let eps; try{eps=readEndpoints()}catch(e){status.className='statusline err';status.textContent=e.message;return;}
  status.className='statusline';status.textContent='Asking the AI to draft a plan…';
  document.getElementById('planBtn').disabled=true;
  try{
    let target=document.getElementById('target').value.trim();
    if(!eps.length){
      const url=new URL(target);
      if(!['http:','https:'].includes(url.protocol)||url.username||url.password){
        throw new Error('Enter an HTTP or HTTPS URL without credentials.');
      }
      eps=[{method:'GET',path:url.pathname+url.search}];
      target=url.origin;
    }
    const rules=[];
    for(const [id,metric,op,divisor] of [
      ['draftP95','p95_ms','<=',1], ['draftErrorRate','error_rate','<',100],
    ]){
      const input=document.getElementById(id);
      if(!input.checkValidity()) throw new Error('Enter valid latency and error rate limits.');
      if(input.value!=='') rules.push({metric,op,value:input.valueAsNumber/divisor});
    }
    const wholeNumber=(id,label,min=1)=>{
      const value=document.getElementById(id).valueAsNumber;
      if(!Number.isInteger(value)||value<min) throw new Error(label+' must be a whole number of at least '+min+'.');
      return value;
    };
    const schedule=document.getElementById('draftSchedule').value;
    const rateMode=schedule==='rate';
    const journeyRateMode=schedule==='journey-rate';
    const rampRate=schedule==='ramping-arrival-rate';
    const fixedIterations=['shared-iterations','per-vu-iterations'].includes(schedule);
    const users=wholeNumber('maxUsers',rateMode||journeyRateMode||rampRate?'Preallocated virtual users':'Virtual users');
    const duration=wholeNumber('duration','Duration',schedule==='users'?3:1);
    const profileType=schedule==='users'?document.getElementById('profileType').value:'ramp';
    const rate=rateMode?wholeNumber('draftRequestRate','Requests per second'):null;
    const journeyRate=journeyRateMode?wholeNumber('draftJourneyRate','Journey starts per second'):null;
    if(users>1000000||rate>1000000||journeyRate>1000000) throw new Error('Enter values up to 1,000,000.');
    const stageFields=['draftRampUp','draftHold','draftRampDown'];
    const customStages=schedule==='users'&&profileType==='ramp'&&stageFields.some(id=>document.getElementById(id).value!=='');
    const stages=customStages?stageFields.map((id,index)=>({
      duration_seconds:wholeNumber(id,['Ramp up','Steady state','Ramp down'][index]),
      target_users:index===2?0:users,
    })):null;
    if(stages&&stages.reduce((sum,stage)=>sum+stage.duration_seconds,0)!==duration){
      throw new Error('Ramp up, steady state, and ramp down must add up to '+duration+' seconds.');
    }
    const executorOptions=schedule==='users'||rateMode||journeyRateMode?null:{executor:schedule};
    if(fixedIterations){
      executorOptions.iterations=wholeNumber('draftIterations','Iterations');
      if(schedule==='shared-iterations'&&executorOptions.iterations<users) throw Error('Shared iterations must be at least the number of virtual users.');
    }
    if(rampRate){
      executorOptions.start_rate=wholeNumber('draftStartRate','Starting rate',0);
      executorOptions.rate_stages=[0,1,2].map(index=>({
        duration_seconds:wholeNumber('draftRateDuration'+index,'Stage '+(index+1)+' duration'),
        target_rate:wholeNumber('draftRateTarget'+index,'Stage '+(index+1)+' arrival rate',0),
      }));
      if(executorOptions.rate_stages.reduce((sum,stage)=>sum+stage.duration_seconds,0)!==duration)
        throw Error('Arrival-rate stages must add up to the test duration.');
    }
    const body={project_id:currentProject.project_id,test_name:newTestName,environment:currentProject.environment||'',target_base_url:target,
      goal:document.getElementById('goal').value.trim(),
      max_users:users, duration_seconds:duration, profile_type:profileType, endpoints:eps,
      ...(rate?{target_request_rate:rate, ...(document.getElementById('draftRequestRate').dataset.trafficRate===String(rate)?{traffic_sample_rate:true}:{})}:{}), ...(journeyRate?{target_iteration_rate:journeyRate}:{}), ...(stages?{stages}:{}),
      ...(executorOptions?{executor_options:executorOptions}:{}), ...(rules.length?{thresholds:rules}:{})};
    const r=await fetch('/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'plan failed');
    currentPlanId=j.plan_id; planModel=j.load_model; planRationale=j.rationale||'';
    setReviewSources(j.review_sources);
    document.getElementById('importNote').style.display='none';
    applyIntegrations(j.plan_id);
    renderPlanForm(); renderRawFromModel();
    showGuardrail(j.guardrail); showPlanEval(j.evaluation); showUsage(j.usage); refreshUsage();
    document.getElementById('planMeta').style.display='inline-flex';
    document.getElementById('planMeta').textContent='drafted by '+j.provider;
    goStep(2); loadPlans();
  }catch(e){ status.className='statusline err'; status.textContent='Error: '+e.message; }
  finally{ document.getElementById('planBtn').disabled=false; }
}

function showGuardrail(g){
  const b=document.getElementById('guardrailBadge'); b.style.display='inline-flex';
  if(g&&g.total>0){ b.className='rv-chip ok'; b.textContent='🛡 '+g.total+' sensitive value'+(g.total!==1?'s':'')+' hidden from the AI';
    b.title='Redacted before the AI saw them: '+g.detail; }
  else { b.className='rv-chip'; b.textContent='🛡 Nothing sensitive in the inputs'; b.title='The guardrail found nothing to redact.'; }
}
function showPlanEval(e){
  const el=document.getElementById('planEval'); if(!e){el.style.display='none';return;} el.style.display='inline-flex';
  if(e.grounded){ el.className='rv-chip ok'; el.textContent='Plan validation passed ('+e.passed+'/'+e.total+' checks)';
    el.title='Checks the draft against its configured inputs. Verification sends requests to the target.'; }
  else { const f=(e.checks||[]).filter(c=>!c.passed).map(c=>c.name).join(', ');
         el.className='rv-chip warn'; el.textContent='⚠ Review needed — '+e.passed+'/'+e.total+' checks passed';
         el.title='Issues: '+(f||'see the plan'); }
}

/* ---------- session token usage (top bar) ---------- */
async function refreshUsage(){
  try{
    const j=await (await fetch('/api/usage/total')).json();
    const t=document.getElementById('sessionTokens'); const c=document.getElementById('sessionCost');
    if(t) t.textContent=(j.tokens||0).toLocaleString();
    if(c) c.textContent = j.cost_usd ? ('· ~$'+j.cost_usd.toFixed(4)) : '';
  }catch(e){}
}

/* ---------- token usage display ---------- */
function showUsage(u){
  const pill=document.getElementById('usagePill'); if(!pill) return;
  if(u && u.total_tokens){
    pill.style.display='inline-flex';
    const cost = u.cost_usd ? ' (~$'+u.cost_usd.toFixed(4)+')' : '';
    pill.className='rv-chip';
    pill.textContent = '🪙 '+u.total_tokens.toLocaleString()+' tokens'+cost;
    pill.title = (u.prompt_tokens||0)+' in + '+(u.completion_tokens||0)+' out · '+(u.model||'');
  } else { pill.style.display='none'; }
}



/* ---------- suggest checks from a response (Option B) ---------- */
let _suggestTarget=null; let _suggested=[];
function openSuggestChecks(si,sti){
  _suggestTarget={si,sti};
  document.getElementById('suggestSample').value='';
  document.getElementById('suggestNote').style.display='none';
  document.getElementById('suggestResults').style.display='none';
  document.getElementById('applySuggestBtn').style.display='none';
  document.getElementById('suggestModal').style.display='flex';
}
function closeSuggestChecks(){ document.getElementById('suggestModal').style.display='none'; _suggestTarget=null; _suggested=[]; }
async function runSuggestChecks(){
  const sample=document.getElementById('suggestSample').value.trim();
  const n=document.getElementById('suggestNote');
  if(!sample){ n.style.display='flex'; n.className='note err'; n.textContent='Paste a response first.'; return; }
  n.style.display='flex'; n.className='note info'; n.textContent='AI is analyzing the response and suggesting checks...';
  document.getElementById('suggestBtn').disabled=true;
  try{
    const r=await fetch('/api/suggest-checks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sample_response:sample})});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'failed');
    _suggested=j.checks||[];
    if(!_suggested.length){ n.className='note warn'; n.textContent='No checks suggested — try a fuller response.'; return; }
    n.style.display='none';
    const res=document.getElementById('suggestResults'); res.style.display='block';
    res.innerHTML='<div class="mini">Suggested checks — untick any you don\'t want</div>'+
      _suggested.map((c,i)=>{
        const label=checkLabel(c);
        return `<label style="display:flex;gap:8px;align-items:flex-start;padding:6px 8px;background:#f7faf8;border-radius:8px;margin-bottom:4px;cursor:pointer">`+
          `<input type="checkbox" checked data-ci="${i}" style="margin-top:3px"/>`+
          `<div><div style="font-size:12.5px"><b>${esc(label)}</b></div>`+
          (c.reason?`<div class="muted" style="font-size:11px">${esc(c.reason)}</div>`:'')+`</div></label>`;
      }).join('');
    document.getElementById('applySuggestBtn').style.display='inline-flex';
  }catch(e){ n.className='note err'; n.textContent='Error: '+e.message; }
  finally{ document.getElementById('suggestBtn').disabled=false; }
}
function checkLabel(c){
  if(c.kind==='body_contains') return 'Body contains "'+c.value+'"';
  if(c.kind==='not_contains')  return 'Body does NOT contain "'+c.value+'"';
  if(c.kind==='status')        return 'Status is '+c.value;
  if(c.kind==='response_time') return 'Response under '+c.value+'ms';
  if(c.kind==='json_path')     return 'Field '+c.path+(c.op==='exists'?' exists':' '+c.op+' '+c.value);
  return c.kind;
}
function applySuggestedChecks(){
  if(!_suggestTarget) return;
  const picks=[...document.querySelectorAll('#suggestResults input[type=checkbox]:checked')].map(cb=>_suggested[+cb.dataset.ci]);
  const st=planModel.scenarios[_suggestTarget.si].steps[_suggestTarget.sti];
  if(!st.assertions) st.assertions=[];
  picks.forEach(c=>st.assertions.push({kind:c.kind,op:c.op||'eq',path:c.path||'',value:c.value||''}));
  closeSuggestChecks(); renderPlanForm();
}

/* ---------- SLA / threshold profiles ---------- */
async function loadSlaProfiles(){
  try{
    const j=await (await fetch('/api/sla')).json();
    window._slaProfiles=j.profiles||[];
    const sel=document.getElementById('slaSelect'); if(!sel) return;
    sel.innerHTML='<option value="">— choose —</option>'+
      window._slaProfiles.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
  }catch(e){}
}
function applySla(){
  const id=document.getElementById('slaSelect').value; if(!id||!planModel) return;
  const p=(window._slaProfiles||[]).find(x=>x.id===id); if(!p) return;
  planModel.thresholds=JSON.parse(JSON.stringify(p.thresholds||[]));
  renderPlanForm();
}
async function saveSla(){
  if(!planModel||!planModel.thresholds||!planModel.thresholds.length){ alert('Add some thresholds first.'); return; }
  const name=prompt('Name this SLA profile (e.g. "API SLA — p95<300, err<1%"):');
  if(!name) return;
  try{
    const r=await fetch('/api/sla',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name, thresholds:planModel.thresholds})});
    if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'failed'); }
    await loadSlaProfiles();
  }catch(e){ alert('Could not save SLA: '+e.message); }
}

/* ---------- plain-English plan summary ---------- */
let planRationale = "";   // the AI's "why", set when a plan is drafted
let reviewDraftInputs=null;
function formatJourneyRate(rate){
  const rounded=Number(rate.toPrecision(4));
  return (rounded===rate?'':'≈ ')+rounded;
}
function setReviewSources(sources){
  reviewDraftInputs=sources?{planId:currentPlanId,snapshot:structuredClone(planModel),sources}:null;
}
function reviewLoadChart(profile, stages, duration, peak){
  if(!duration) return '';
  const arrival=profile?.arrival_rate;
  const options=profile?.executor_options;
  if(options?.iterations!=null) return '';
  const rampRate=options?.executor==='ramping-arrival-rate';
  const startValue=arrival||(rampRate?options.start_rate:options?.executor==='constant-vus'?peak:profile?.start_users||0);
  const levels=rampRate?options.rate_stages.map(stage=>({duration_seconds:stage.duration_seconds,target_users:stage.target_rate})):stages;
  const maximum=arrival||Math.max(1,startValue,...levels.map(stage=>stage.target_users));
  let elapsed=0;
  const point=(time,level)=>time/duration*100+'% '+(100-level/maximum*100)+'%';
  const start=point(0,startValue);
  const targets=arrival?[point(duration,arrival)]:levels.map(stage=>{
    elapsed+=stage.duration_seconds;
    return point(elapsed,stage.target_users);
  });
  const area=['0% 100%',start,...targets,'100% 100%'].join(',');
  const unit=arrival||rampRate?(profile.target_request_rate?'req/s':'iterations/s'):'VUs';
  return '<figure class="review-load-chart" aria-label="Planned load over time">'+
    '<div class="review-load-axis" aria-hidden="true"><span>'+esc(maximum+' '+unit)+'</span><span>0</span></div>'+
    '<div class="review-load-plot" aria-hidden="true"><div style="clip-path:polygon('+area+')"></div></div>'+
    '<figcaption><span>0 s</span><span>'+esc(duration)+' s</span></figcaption></figure>';
}

function renderSummary(){
  const summary=document.getElementById('planSummary');
  if(!summary||!planModel) return;

  const scenarios=planModel.scenarios||[];
  const totalWeight=scenarios.reduce((sum,scenario)=>sum+(scenario.weight||0),0)||1;
  const requestCount=scenarios.reduce((sum,scenario)=>sum+scenario.steps.length,0);
  const profile=planModel.load_profile;
  const {type,duration,stages}=loadOfProfile(profile);
  const peak=stages.reduce((max,stage)=>Math.max(max,stage.target_users),0);
  const typeLabel={ramp:'Load',stress:'Stress',spike:'Spike',soak:'Soak'}[type]||type;
  const arrival=profile?.arrival_rate;
  const requestRate=profile?.target_request_rate;
  const journeyRate=requestRate&&scenarios.length===1&&requestCount?requestRate/requestCount:null;
  const options=profile?.executor_options;
  const executor=options?.executor||(arrival?'constant-arrival-rate':'ramping-vus');
  const iterations=options?.iterations;
  const plannedIterations=executor==='per-vu-iterations'?iterations*peak:iterations;
  const rateStages=options?.rate_stages||[];
  const inputs=reviewDraftInputs?.planId===currentPlanId?reviewDraftInputs:null;
  const sourceLabel=(source,previous,current,subject='')=>{
    if(!inputs) return '';
    const key=JSON.stringify(previous)===JSON.stringify(current)?source:'edited';
    const label={user:'From you',suggested:'Suggested by PerfAgent',profile:'Load shape uses profile defaults',traffic:'From an aggregate traffic sample',
      edited:'Edited in Review'}[key];
    return label?'<small class="review-source">'+esc(subject?subject+' · '+label:label)+'</small>':'';
  };
  const targetValues=model=>[model.target_base_url,model.environment||'',Boolean(model.insecure_tls)];
  const stageNames={
    ramp:['Ramp up','Steady state','Ramp down'], soak:['Ramp up','Steady hold','Ramp down'],
    spike:['Baseline','Spike up','Peak hold','Drop','Recovery'],
  }[type];
  const stageRows=stages.map((stage,index)=>'<li><span>'+esc(stageNames?.[index]||'Stage '+(index+1))+
    '</span><strong>'+esc(stage.target_users)+' VUs · '+esc(stage.duration_seconds)+' s</strong></li>').join('');
  const rules=(planModel.thresholds||[]).map(rule=>{
    const labels={p50_ms:'p50',p90_ms:'p90',p95_ms:'p95',p99_ms:'p99',avg_ms:'Average latency',median_ms:'Median latency',
      max_ms:'Maximum latency',error_rate:'Error rate'};
    const value=rule.metric==='error_rate'?Number((rule.value*100).toPrecision(15))+'%':rule.value+' ms';
    return '<li><span>'+esc(labels[rule.metric]||rule.metric)+'</span><strong>'+esc(rule.op+' '+value)+'</strong></li>';
  }).join('');
  summary.innerHTML='<h3>What will run</h3><p>'+esc(requestCount)+' '+(requestCount===1?'request':'requests')+' across '+
    esc(scenarios.length)+' '+(scenarios.length===1?'journey':'journeys')+'</p><div class="review-summary-load"><strong>'+
    esc(requestRate?requestRate+' requests/s':arrival?arrival+' iterations/s':
      iterations!=null?plannedIterations+' planned iterations':
      rateStages.length?Math.max(options.start_rate,...rateStages.map(stage=>stage.target_rate))+' peak iterations/s':peak+' peak VUs')+
    '</strong><span>'+esc(executor)+(options?'':' · '+esc(requestRate?'Constant request rate':arrival?'Constant journey rate':typeLabel))+' · '+esc(duration)+' s'+(iterations!=null?' max':'')+'</span></div>'+
    sourceLabel(inputs?.sources.load,inputs?.snapshot.load_profile,profile)+
    reviewLoadChart(profile,stages,duration,peak)+
    (arrival?'<p>'+esc(profile.pre_allocated_vus)+' preallocated VUs</p>'+(requestRate?
      (journeyRate!=null?'<p>'+esc(requestRate)+' requests/s ÷ '+esc(requestCount)+' '+(requestCount===1?'request':'requests')+
        ' per journey = '+esc(formatJourneyRate(journeyRate))+' journey starts/s. Actual throughput depends on completed requests and available VUs.</p>':
        '<p>Combine requests into one ordered journey to generate an HTTP request-rate target.</p>')+
      '<p>At least '+esc(requestRate*duration)+' HTTP requests and zero dropped iterations.</p>':
      '<p>Each iteration starts one journey and can send multiple requests.</p>'):
      rateStages.length?'<p>Start at '+esc(options.start_rate)+' iterations/s with '+esc(peak)+' preallocated VUs.</p><ol class="review-summary-list" aria-label="Arrival-rate stages">'+rateStages.map(stage=>'<li><span>'+esc(stage.duration_seconds)+' s</span><strong>'+esc(stage.target_rate)+' iterations/s at end</strong></li>').join('')+'</ol>':
      iterations!=null?'<p>'+esc(peak)+' VUs · '+(executor==='per-vu-iterations'?esc(iterations)+' iterations per VU':'iterations shared across users')+'</p>':
      executor==='constant-vus'?'<p>Hold '+esc(peak)+' virtual users for '+esc(duration)+' seconds.</p>':
      stageRows?'<ol class="review-summary-list" aria-label="Load stages">'+stageRows+'</ol>':'')+
    '<h4>Pass rules</h4>'+sourceLabel(inputs?.sources.thresholds,inputs?.snapshot.thresholds,planModel.thresholds)+
    (rules?'<ul class="review-summary-list">'+rules+'</ul>':'<p>No thresholds configured.</p>');

  const headers=Object.entries(readHeaders()).filter(([,value])=>value);
  const headerCount=headers.length;
  const usesAuth=headers.some(([name])=>/^(authorization|x-api-key|api-key|cookie)$/i.test(name));
  document.getElementById('reviewTargetOverview').innerHTML='<p class="review-url">'+esc(planModel.target_base_url||'Enter a target URL')+
    '</p><p class="hint">'+esc(planModel.environment||'No environment label')+' · '+
    esc(headerCount?headerCount+(headerCount===1?' custom header':' custom headers'):'No custom headers')+
    (usesAuth?' · Authentication configured':'')+
    (planModel.insecure_tls?' · TLS verification off':'')+'</p>'+
    sourceLabel(inputs?.sources.target,inputs?targetValues(inputs.snapshot):null,targetValues(planModel));

  const columns=new Set(dataColumns);
  const allCaptures=capturedVars();
  const findings=[];
  const requests=document.getElementById('reviewRequestsOverview');
  requests.innerHTML=scenarios.map((scenario,si)=>{
    const capturedHere=new Set();
    const originalJourney=inputs?.snapshot.scenarios[si];
    const journeySources=inputs?.sources.journeys[si];
    const journeyFields=value=>value&&[value.name,value.weight,value.think_time];
    const rows=scenario.steps.map((step,sti)=>{
      const requestInputs=[
        ['Request path',step.path],
        ...headers.map(([name,value])=>['Header '+name,value]),
        ...flattenBody(step.body||{}).map(field=>['Body field '+pathLabel(field.path),field.value]),
      ];
      const sources=new Set();
      const unavailable=new Set();
      for(const [destination,input] of requestInputs){
        if(typeof input!=='string') continue;
        for(const match of input.matchAll(/\$\{([^}]+)\}/g)){
          const token=match[1].trim();
          const generator=token.split('(')[0];
          if(GEN_NAMES.has(generator)) sources.add('Generated · '+generator+' → '+destination);
          else if(capturedHere.has(token)) sources.add('Earlier response · '+token+' → '+destination);
          else if(allCaptures.has(token)) unavailable.add('Check capture order · '+token+' → '+destination);
          else if(columns.has(token)) sources.add('Dataset · '+token+' → '+destination);
          else unavailable.add('Unresolved · '+token+' → '+destination);
        }
      }
      if(unavailable.size) findings.push({si,sti,label:step.name||step.path||'Request',messages:[...unavailable]});
      const captures=[];
      for(const capture of step.extract||[]){
        if(capture.var){
          capturedHere.add(capture.var);
          captures.push('Captures '+capture.var+(capture.path?' from '+capture.path:''));
        }
      }
      const group=(label,values)=>values.length?'<div><strong>'+label+'</strong> '+values.map(esc).join(' · ')+'</div>':'';
      const checks=(step.assertions||[]).map(checkLabel);
      const originalStep=originalJourney?.steps[sti];
      const stepSources=journeySources?.steps[sti];
      const endpoint=value=>value&&[value.method||'GET',value.path];
      return '<li class="review-request"><span class="review-method">'+esc(step.method||'GET')+'</span>'+
        '<div class="review-request-path"><code>'+esc(step.path||'Path required')+'</code>'+
        '<button type="button" class="btn ghost sm" data-review-step="'+si+':'+sti+
        '" aria-label="Edit '+esc((step.method||'GET')+' '+(step.path||'request'))+'">Edit</button></div>'+
        '<div class="review-request-tags">'+sourceLabel(stepSources?.endpoint,endpoint(originalStep),endpoint(step),'Endpoint')+
        sourceLabel(stepSources?.body,originalStep?.body??null,step.body??null,'Request body')+
        group('Checks',checks.length?checks:['Default HTTP status check'])+
        sourceLabel(stepSources?.checks,originalStep?.assertions||[],step.assertions||[],'Checks')+
        group('Data sources',[...sources,...unavailable])+group('Capture for later requests',captures)+'</div></li>';
    }).join('');
    return '<div class="review-journey"><div class="review-journey-title"><strong>'+esc(scenario.name||'Journey')+
      '</strong><span>'+Math.round((scenario.weight||0)/totalWeight*100)+'% of traffic</span>'+
      sourceLabel(journeySources?.source,journeyFields(originalJourney),journeyFields(scenario))+'</div><ol>'+rows+'</ol></div>';
  }).join('')||'<p class="hint">Add a journey to define the requests.</p>';
  const reviewFindings=document.getElementById('reviewFindings');
  if(reviewFindings){
    reviewFindings.innerHTML=findings.map(({si,sti,label,messages})=>'<li><button type="button" class="btn ghost sm" data-review-step="'+si+':'+sti+
      '">Review '+esc(label)+'</button> '+messages.map(esc).join(' · ')+'</li>').join('');
    reviewFindings.hidden=!findings.length;
  }
  for(const container of [requests,reviewFindings]){
    container?.querySelectorAll('[data-review-step]').forEach(button=>{
      button.onclick=()=>{
        const key=button.dataset.reviewStep;
        const editor=document.getElementById('scenarios').closest('details');
        if(editor) editor.open=true;
        openSteps.add(key);
        renderPlanForm();
        document.getElementById('review-step-'+key)?.focus();
      };
    });
  }

  const modes={random:'Random rows',sequential:'Read in order',unique:'Use each row once'};
  document.getElementById('reviewDataOverview').textContent=dataFileInfo
    ? dataFileInfo.filename+' · '+dataFileInfo.row_count+' rows · '+(modes[dataRowMode]||modes.random)
    : 'No dataset attached.';
  document.getElementById('reviewRationale').textContent=planRationale;
  const explanation=document.getElementById('reviewDraftExplanation');
  if(explanation){
    explanation.hidden=!planRationale;
    explanation.textContent=planRationale?'Why this plan was drafted — '+planRationale:'';
  }
}

/* ---------- editable plan form (review step) ----------
   Summary first, details on demand: each journey lists its steps as one line each;
   clicking a step opens its request data, checks and advanced options. */
const METHODS=["GET","POST","PUT","PATCH","DELETE"];
let _reviewPlanId=null;                 // which plan the review state below belongs to
let openSteps=new Set();                // "si:sti" of steps whose details are open
let jsonSteps=new Set();                // steps whose body is being edited as raw JSON
let advSteps=new Set();                 // steps whose "Advanced" block is open
let dynUndo={};                         // "si:sti" -> body before the last AI suggestion
let dataFileInfo=null;                  // {filename,row_count,sample_rows} of the attached file
let dataRowMode='random';               // random | sequential | unique
let _loadAsked=null;                    // {users,duration} as typed on this page, if changed

function stepKey(si,sti){ return si+':'+sti; }

/* A different plan was opened: start its review from a clean slate. */
function resetReviewState(){
  openSteps=new Set(); jsonSteps=new Set(); advSteps=new Set(); dynUndo={}; _loadAsked=null;
  document.getElementById('previewBox').style.display='none';
  document.getElementById('journeyWeightCsv').value='';
  document.getElementById('journeyWeightStatus').textContent='';
  document.getElementById('journeyWeightPreview').replaceChildren();
  // data file: use what the plan itself says (a file uploaded for another plan is dropped)
  const df=planModel.data_file;
  currentDataFileId=null;
  dataColumns = df ? (df.fields||[]) : [];
  dataFileInfo = df ? {filename:df.filename,row_count:df.row_count||0,sample_rows:[]} : null;
  dataRowMode = (df&&df.row_mode)||'random';
  // connection options come from the plan too
  document.getElementById('headersList').innerHTML='';
  Object.entries(planModel.headers||{}).forEach(([k,v])=>addHeader(k,v));
  document.getElementById('connDetails').open=false;
  document.querySelectorAll('.review-editor, .review-advanced').forEach(editor=>{editor.open=false;});
}

export function openReviewEditor(contentId, focusId){
  const panel=document.getElementById(contentId)?.closest('details');
  if(!panel)return;
  panel.open=true;
  (focusId?document.getElementById(focusId):panel.querySelector('summary'))?.focus();
}

function renderPlanForm(){
  _rdPaths=[];
  if(_reviewPlanId!==currentPlanId){ _reviewPlanId=currentPlanId; resetReviewState(); }
  document.getElementById('pfTarget').value=planModel.target_base_url||'';
  document.getElementById('pfTestName').value=planModel.test_name||'';
  document.getElementById('pfScriptFilename').value=planModel.script_filename||'';
  loadWorkloadProfiles();
  document.getElementById('environment').value=planModel.environment||'';
  document.getElementById('insecureTls').checked=!!planModel.insecure_tls;
  renderLoad(); renderDataCard(); renderConnCount();
  document.getElementById("pfArrival").value=planModel.load_profile.arrival_rate||"";
  document.getElementById("pfArrivalVus").value=planModel.load_profile.pre_allocated_vus||10;
  renderEnvironmentPresets();
  const host=document.getElementById('scenarios'); host.innerHTML='';
  (planModel.scenarios||[]).forEach((sc,si)=>host.appendChild(scenarioCard(sc,si)));
  const th=document.getElementById('thresholds'); th.innerHTML='';
  (planModel.thresholds||[]).forEach((t,ti)=>th.appendChild(thresholdRow(t,ti)));
  if(!(planModel.thresholds||[]).length){
    th.innerHTML='<div class="note warn">No rules yet — without at least one, the result cannot be judged pass or fail.</div>';
  }
  updateWeightBadges();
  renderSummary();
}

/* ----- 1 · target & load ----- */
function loadOfProfile(lp){
  const stages=(lp&&lp.stages)||[];
  const type=(lp&&lp.type)||'ramp';
  const peak=stages.reduce((m,s)=>Math.max(m,s.target_users||0),0);
  // a stress test steps past the number asked for; the 4th of its 6 stages is that number
  const users=(type==='stress'&&stages.length===6) ? (stages[3].target_users||peak) : peak;
  return {type, users, duration:stages.reduce((a,s)=>a+(s.duration_seconds||0),0), stages};
}
function renderLoad(){
  const l=loadOfProfile(planModel.load_profile);
  const asked=_loadAsked||{};
  document.getElementById('pfType').value=l.type;
  document.getElementById('pfUsers').value=asked.users||l.users||'';
  document.getElementById('pfDuration').value=asked.duration||l.duration||'';
  const options=planModel.load_profile.executor_options;
  document.getElementById('pfType').disabled=Boolean(options);
  document.getElementById('pfDuration').disabled=options?.executor==='ramping-arrival-rate';
  document.getElementById('pfDuration').min=options?'1':'3';
  document.getElementById('pfArrival').disabled=Boolean(options);
  const rateLabel=document.getElementById('pfArrivalLabel');
  if(rateLabel) rateLabel.textContent=planModel.load_profile.target_request_rate?
    'Target HTTP requests per second':'Target journey starts per second (optional)';
  document.getElementById('pfArrivalVus').disabled=Boolean(options);
  document.getElementById('pfShape').textContent = l.stages.length
    ? 'Load shape: '+l.stages.map(s=>s.target_users+' users for '+s.duration_seconds+'s').join(' → ') : '';
  if(options) document.getElementById('pfShape').textContent=options.executor;
  renderExecutorOptions(options);
}
function renderExecutorOptions(options){
  const host=document.getElementById('pfExecutorOptions');
  if(!host)return;
  host.replaceChildren();
  if(!options)return;
  const numberInput=(label,value,min,apply)=>{
    const field=document.createElement('label');
    field.className='field';
    field.textContent=label;
    const input=document.createElement('input');
    input.type='number';input.step='1';input.min=String(min);input.max='1000000';input.value=String(value);
    input.onchange=()=>{
      const next=input.valueAsNumber;
      if(!input.checkValidity()||!Number.isInteger(next)||!apply(next)){
        showError('Enter a valid whole number for '+label.toLowerCase()+'.');
        input.value=String(value);
        return;
      }
      value=next;
      renderRawFromModel();
      renderSummary();
    };
    field.append(input);
    return field;
  };
  const profile=planModel.load_profile;
  if(options.iterations!=null){
    const shared=options.executor==='shared-iterations';
    host.append(numberInput(shared?'Total iterations':'Iterations per virtual user',options.iterations,
      shared?profile.stages[0].target_users:1,value=>{options.iterations=value;return true;}));
  }
  if(options.executor==='ramping-arrival-rate'){
    const changeRate=(item,key,value)=>{
      if(!value&&!(item!==options&&options.start_rate)&&
        !options.rate_stages.some(stage=>stage!==item&&stage.target_rate))return false;
      item[key]=value;
      return true;
    };
    host.append(numberInput('Starting iterations per second',options.start_rate,0,value=>changeRate(options,'start_rate',value)));
    options.rate_stages.forEach((stage,index)=>{
      const row=document.createElement('div');row.className='grid2';
      row.append(numberInput('Stage '+(index+1)+' duration (seconds)',stage.duration_seconds,1,value=>{
        stage.duration_seconds=value;
        const duration=options.rate_stages.reduce((sum,item)=>sum+item.duration_seconds,0);
        profile.stages[0].duration_seconds=duration;
        document.getElementById('pfDuration').value=String(duration);
        return true;
      }),numberInput('Stage '+(index+1)+' target iterations per second',stage.target_rate,0,value=>changeRate(stage,'target_rate',value)));
      host.append(row);
    });
  }
}
async function updateLoad(){
  const users=parseInt(document.getElementById('pfUsers').value,10);
  const duration=parseInt(document.getElementById('pfDuration').value,10);
  const status=document.getElementById('genStatus');
  if(!(users>0) || !(duration>0)){ status.className='statusline err'; status.textContent='Peak users and duration must be whole numbers above 0.'; return; }
  const options=planModel.load_profile.executor_options;
  if(options){
    if(options.executor==='shared-iterations'&&users>options.iterations){
      status.className='statusline err'; status.textContent='Shared iterations must be at least the number of virtual users.';return;
    }
    planModel.load_profile.stages=[{target_users:users,duration_seconds:duration}];
    _loadAsked=null;
    renderLoad();renderSummary();return;
  }
  try{
    const r=await fetch('/api/load-profile',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({type:document.getElementById('pfType').value,max_users:users,duration_seconds:duration})});
    const j=await r.json(); if(!r.ok) throw new Error('that load size is not valid');
    const {arrival_rate:arrival, pre_allocated_vus:vus, target_request_rate:requestRate}=planModel.load_profile;
    planModel.load_profile={...j.load_profile,arrival_rate:arrival,target_request_rate:requestRate,pre_allocated_vus:vus||10};
    _loadAsked={users,duration};                 // what was asked for, not the rounded total
    status.className='statusline'; status.textContent='';
    renderLoad(); renderSummary();
  }catch(e){ status.className='statusline err'; status.textContent='Could not update the load: '+e.message; }
}
function renderConnCount(){
  const n=document.querySelectorAll('#headersList .endpoint').length;
  const bits=[]; if(n) bits.push(n+' header'+(n===1?'':'s'));
  if(planModel.environment) bits.push(planModel.environment);
  if(planModel.insecure_tls) bits.push('TLS check off');
  document.getElementById('connCount').textContent = bits.length ? '· '+bits.join(' · ') : '';
  renderSummary();
}

/* ----- 2 · test data file ----- */
const ROW_MODES=[
  ['random','In random order — a row can be used more than once'],
  ['sequential','In file order — starts again at the top when rows run out'],
  ['unique','Each row once — the test stops when rows run out'],
];
function renderDataCard(){
  const card=document.getElementById('dataCard'), dz=document.getElementById('dz');
  if(!dataFileInfo){ card.style.display='none'; dz.style.display='block';
    dz.textContent='Upload CSV, TSV, TXT, JSON, JSONL, or NDJSON'; return; }
  dz.style.display='none'; card.style.display='block';
  const cols=dataColumns||[], rows=dataFileInfo.sample_rows||[];
  let table='';
  if(cols.length && rows.length){
    table='<div class="dfile-scroll"><table><thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'+
      rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(r[c]===undefined||r[c]===null?'':r[c])+'</td>').join('')+'</tr>').join('')+
      '</tbody></table></div><div class="muted" style="font-size:11.5px;margin-top:4px">First '+rows.length+' of '+dataFileInfo.row_count+' rows.</div>';
  } else if(cols.length){
    table='<div style="margin-top:8px;font-size:12.5px">Columns: '+cols.map(c=>'<code class="k">'+esc(c)+'</code>').join(' ')+'</div>';
  }
  const tool=document.getElementById('tool').value;
  card.innerHTML='<div class="dfile"><div class="dfile-head">📁 <b>'+esc(dataFileInfo.filename)+'</b>'+
    '<span class="muted">'+(dataFileInfo.row_count||0).toLocaleString()+' rows · '+cols.length+' column'+(cols.length===1?'':'s')+'</span>'+
    '<div class="spacer"></div>'+
    '<button class="btn ghost sm" onclick="document.getElementById(\'dataFile\').click()">Replace</button>'+
    '<button class="btn danger sm" onclick="removeDataFile()">Remove</button></div>'+table+
    '<div class="dfile-mode"><label for="rowMode" style="margin:0">Use the rows</label>'+
    '<select id="rowMode" onchange="dataRowMode=this.value;renderDataCard();renderSummary()">'+
      ROW_MODES.map(m=>'<option value="'+m[0]+'" '+(m[0]===dataRowMode?'selected':'')+'>'+m[1]+'</option>').join('')+'</select></div>'+
    (dataRowMode==='unique' ? '<div class="muted" style="font-size:11.5px;margin-top:6px">With more than one journey, each journey gets its own share of the rows. '+(dataFileInfo.row_count||0).toLocaleString()+' rows allow that many journey runs in total.</div>' : '')+
    (tool && tool!=='k6' ? '<div class="note warn" style="margin-top:8px">Data files are only built into k6 scripts. A '+esc(tool)+' script will not read this file.</div>' : '')+
    '</div>';
}
async function uploadData(){
  const input=document.getElementById('dataFile'); const info=document.getElementById('dataInfo');
  if(!input.files||!input.files.length) return;
  const fd=new FormData(); fd.append('file',input.files[0]);
  info.style.display='flex'; info.className='note info'; info.textContent='Uploading & checking the file…';
  try{
    const r=await fetch('/api/data',{method:'POST',body:fd}); const j=await r.json();
    if(!r.ok) throw new Error(j.detail||'upload failed');
    currentDataFileId=j.data_file_id; dataColumns=j.fields;
    dataFileInfo={filename:j.filename,row_count:j.row_count,sample_rows:j.sample_rows||[]};
    if((j.warnings||[]).length){ info.className='note warn'; info.textContent=j.warnings.join(' '); }
    else info.style.display='none';
    renderPlanForm();                         // columns are now offered in every request
  }catch(e){ info.className='note err'; info.textContent='Could not use that file: '+e.message; }
  input.value='';
}
function removeDataFile(){
  currentDataFileId=null; dataColumns=[]; dataFileInfo=null; dataRowMode='random';
  if(planModel) planModel.data_file=null;
  document.getElementById('dataInfo').style.display='none';
  renderPlanForm();
}

/* ----- 3 · journeys ----- */
function scenarioCard(sc,si){
  const el=document.createElement('div'); el.className='scn'; el.dataset.si=si;
  const tt=sc.think_time||{min_seconds:1,max_seconds:3};
  el.innerHTML=`
    <div class="scn-head">
      <input class="name" value="${esc(sc.name||'')}" oninput="planModel.scenarios[${si}].name=this.value;renderSummary()" placeholder="Journey name" aria-label="Journey name"/>
      <div class="weightwrap">
        <span class="muted" style="font-size:11px;white-space:nowrap">Traffic share<i class="infohint" data-tip="How much of the scheduled workload this journey receives. With several journeys, relative weights are normalized into shares. With one journey it is always 100%.">i</i></span>
        ${(planModel.scenarios||[]).length>1
          ? `<input type="number" min="0" max="1000000" step="any" value="${esc(sc.weight)}" onchange="if(!setWeight(${si},this.value)) this.value=planModel.scenarios[${si}].weight" aria-label="Relative journey weight"/>`
          : ''}
        <span class="wbadge" id="wb${si}">—</span>
      </div>
      <button class="iconbtn" title="Remove this journey" onclick="delScenario(${si})">×</button>
    </div>
    <div id="steps${si}"></div>
    <div class="btnrow" style="margin-top:6px;flex-wrap:wrap">
      <button class="btn ghost sm" onclick="addStep(${si})">+ Add step</button>
      <div class="spacer"></div>
      <span class="muted" style="font-size:12px">Pause between steps<i class="infohint" data-tip="Real users pause between actions. Each virtual user waits a random time in this range after every step.">i</i></span>
      <input type="number" min="0" step="0.5" value="${tt.min_seconds}" style="width:64px;margin:0;padding:5px 7px;font-size:12.5px" aria-label="Shortest pause (seconds)" onchange="setThink(${si},'min_seconds',this.value)"/>
      <span class="muted" style="font-size:12px">to</span>
      <input type="number" min="0" step="0.5" value="${tt.max_seconds}" style="width:64px;margin:0;padding:5px 7px;font-size:12.5px" aria-label="Longest pause (seconds)" onchange="setThink(${si},'max_seconds',this.value)"/>
      <span class="muted" style="font-size:12px">seconds</span>
    </div>`;
  const sh=el.querySelector('#steps'+si);
  (sc.steps||[]).forEach((st,sti)=>sh.appendChild(stepRow(si,sti,st)));
  return el;
}
function setThink(si,key,v){
  const sc=planModel.scenarios[si]; sc.think_time=sc.think_time||{min_seconds:1,max_seconds:3};
  sc.think_time[key]=Math.max(0,parseFloat(v)||0);
  if(sc.think_time.max_seconds<sc.think_time.min_seconds){
    if(key==='min_seconds') sc.think_time.max_seconds=sc.think_time.min_seconds;
    else sc.think_time.min_seconds=sc.think_time.max_seconds;
  }
  renderPlanForm();
}
function toggleStep(si,sti){ const k=stepKey(si,sti); if(openSteps.has(k)) openSteps.delete(k); else openSteps.add(k); renderPlanForm(); }

/* one line per step; details only when open */
function stepRow(si,sti,st){
  const k=stepKey(si,sti), open=openSteps.has(k);
  const el=document.createElement('div'); el.className='stp'+(open?' open':'');
  const fields=st.body?flattenBody(st.body):[];
  const kinds=fields.map(f=>classifyValue(f.value).source);
  const nDyn=kinds.filter(s=>s==='file'||s==='generated'||s==='mixed').length;
  const missing=fields.filter(f=>{ const c=classifyValue(f.value); return c.source==='captured' && !capturedVars().has(c.token); }).length;
  const tags=[];
  if(st.body) tags.push(nDyn ? `<span class="stp-tag dyn">${nDyn} changing value${nDyn===1?'':'s'}</span>` : '<span class="stp-tag">fixed body</span>');
  if(missing) tags.push(`<span class="stp-tag warn">${missing} value${missing===1?'':'s'} with no source</span>`);
  const nChk=(st.assertions||[]).length; if(nChk) tags.push(`<span class="stp-tag">${nChk} check${nChk===1?'':'s'}</span>`);
  const ex=(st.extract&&st.extract[0])||null; if(ex&&ex.var) tags.push(`<span class="stp-tag">captures ${esc(ex.var)}</span>`);
  if(st.graphql_query) tags.push('<span class="stp-tag">GraphQL</span>');
  const head=document.createElement('div'); head.className='stp-head';
  head.id='review-step-'+k;
  head.setAttribute('role','button'); head.setAttribute('tabindex','0'); head.setAttribute('aria-expanded',open?'true':'false');
  head.onclick=()=>toggleStep(si,sti);
  head.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); toggleStep(si,sti); } };
  head.innerHTML=`<span class="stp-chev">▶</span><span class="stp-m ${esc(st.method||'GET')}">${esc(st.method||'GET')}</span>`+
    `<span class="stp-path">${esc(st.path||'/')}</span><span class="stp-tags">${tags.join('')}</span>`;
  const del=document.createElement('button'); del.className='iconbtn'; del.title='Remove this step'; del.textContent='×';
  del.onclick=e=>{ e.stopPropagation(); delStep(si,sti); };
  head.appendChild(del);
  el.appendChild(head);
  if(!open) return el;

  const body=document.createElement('div'); body.className='stp-body';
  let h=`<div class="stp-req">
      <select aria-label="Method" onchange="planModel.scenarios[${si}].steps[${sti}].method=this.value;renderPlanForm()">
        ${METHODS.map(m=>`<option ${m===(st.method||'GET')?'selected':''}>${m}</option>`).join('')}</select>
      <input aria-label="Path" value="${esc(st.path||'')}" placeholder="/path" oninput="planModel.scenarios[${si}].steps[${sti}].path=this.value" onchange="renderPlanForm()"/>
    </div>`;
  h+=requestDataHtml(si,sti,st);
  // checks
  h+=`<div class="stp-h">Checks on the response<i class="infohint" data-tip="Beyond a successful status: confirm the response really is right (contains a value, a field equals something, answers fast enough).">i</i></div>`;
  (st.assertions||[]).forEach((a,ai)=>{ h+=assertRowHtml(si,sti,ai,a); });
  if(!(st.assertions||[]).length) h+='<div class="rd-empty">None yet — only the status code is checked.</div>';
  h+=`<button class="btn ghost sm" style="padding:4px 10px" onclick="addAssertion(${si},${sti})">✔ Add check</button> `+
     `<button class="btn ghost sm" style="padding:4px 10px" onclick="openSuggestChecks(${si},${sti})">✨ Suggest checks from a response</button>`;
  // advanced: capture + GraphQL
  const advOpen=advSteps.has(k)||!!ex||!!st.graphql_query;
  h+=`<details class="rv-more" ${advOpen?'open':''} ontoggle="this.open?advSteps.add('${k}'):advSteps.delete('${k}')">
        <summary>Advanced — reuse a value from this response, GraphQL</summary><div style="margin-top:10px">`;
  if(ex){
    const src=ex.source||'json';
    const srcOpts=['json','header','cookie','regex'].map(o=>`<option ${o===src?'selected':''}>${o}</option>`).join('');
    const ph=src==='header'?'header name e.g. X-Auth-Token':src==='cookie'?'cookie name e.g. session':src==='regex'?'pattern e.g. token=([A-Za-z0-9]+)':'json path e.g. token or data[0].id';
    h+=`<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap;font-size:12.5px;color:var(--muted)">🔗 Capture
        <input style="width:110px;margin:0;padding:5px 8px" value="${esc(ex.var)}" placeholder="name" oninput="setExtract(${si},${sti},'var',this.value)" onchange="renderPlanForm()"/> from the
        <select style="width:auto;margin:0;padding:5px 8px" onchange="setExtract(${si},${sti},'source',this.value);renderPlanForm()">${srcOpts}</select>
        <input style="width:170px;margin:0;padding:5px 8px" value="${esc(ex.path)}" placeholder="${ph}" oninput="setExtract(${si},${sti},'path',this.value)" onchange="renderSummary()"/>
        then use it in later steps as <code class="k">\${${esc(ex.var||'name')}}</code>
        <button class="iconbtn" onclick="removeExtract(${si},${sti})" style="padding:2px 7px">×</button></div>`;
  } else {
    h+=`<button class="btn ghost sm" style="padding:4px 10px" onclick="addExtract(${si},${sti})">🔗 Capture a value from this response to reuse later</button>`;
  }
  h+='<div style="margin-top:8px">';
  if(st.graphql_query){
    h+=`<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;font-size:12.5px;color:var(--muted)">⬡ GraphQL query<i class="infohint" data-tip="This step sends a GraphQL request: body = {query, variables}. The request data above becomes the variables.">i</i><button class="iconbtn" style="padding:2px 7px" onclick="removeGql(${si},${sti})">×</button></div>`+
       `<textarea style="width:100%;min-height:60px;font-family:ui-monospace,monospace;font-size:11.5px" oninput="setGql(${si},${sti},this.value)" placeholder="query { ... }">${esc(st.graphql_query)}</textarea>`;
  } else {
    h+=`<button class="btn ghost sm" style="padding:4px 10px" onclick="addGql(${si},${sti})">⬡ Make this a GraphQL query</button>`;
  }
  h+='</div></div></details>';
  body.innerHTML=h;
  el.appendChild(body);
  return el;
}

/* ----- request data: where each value of the body comes from -----
   A value is one of:  fixed text/number · a column of the data file (${column}) ·
   generated fresh for every request (${uuid}, ${randomEmail} …) · captured from an
   earlier response (${token}).  No ${...} has to be typed by hand. */
const GEN_KINDS=[
  ['uuid','Unique ID'],['randomEmail','Unique email'],['sequential','Unique number'],
  ['randomInt','Random number between…'],['randomString','Random text of length…'],
  ['randomFrom','Random pick from a list…'],['timestamp','Current time (ms)'],
  ['dateOffset','Date some days from now…'],
  ['randomFullName','Random full name'],['randomFirstName','Random first name'],['randomLastName','Random last name'],
  ['randomCompanyName','Random company'],['randomStreetAddress','Random street address'],['randomCity','Random city'],
  ['randomState','Random state'],['randomZipCode','Random zip code'],['randomPhone','Random phone'],
  ['randomCatchPhrase','Random phrase'],['randomBic','Random code (BIC-like)'],
];
const GEN_NAMES=new Set(GEN_KINDS.map(g=>g[0]).concat(['vu','iter','randomBankAccountBic']));
const GEN_DEFAULT_ARGS={randomInt:'1,100',randomString:'8',randomFrom:'a,b,c',dateOffset:"3,'days'"};

function flattenBody(v,path){
  path=path||[]; const out=[];
  if(Array.isArray(v)){ if(!v.length&&path.length) out.push({path,value:v}); v.forEach((x,i)=>out.push(...flattenBody(x,path.concat(i)))); }
  else if(v&&typeof v==='object'){ const ks=Object.keys(v); if(!ks.length&&path.length) out.push({path,value:v}); ks.forEach(k=>out.push(...flattenBody(v[k],path.concat(k)))); }
  else out.push({path,value:v});
  return out;
}
function pathLabel(path){ return path.map((p,i)=>typeof p==='number'?'['+p+']':(i?'.':'')+p).join(''); }
function getAt(obj,path){ return path.reduce((o,k)=>(o==null?o:o[k]),obj); }
function setAt(obj,path,val){ let o=obj; for(let i=0;i<path.length-1;i++) o=o[path[i]]; o[path[path.length-1]]=val; }
function delAt(obj,path){ let o=obj; for(let i=0;i<path.length-1;i++) o=o[path[i]]; const k=path[path.length-1]; if(Array.isArray(o)) o.splice(k,1); else delete o[k]; }
function capturedVars(){
  const s=new Set(); (planModel.scenarios||[]).forEach(sc=>(sc.steps||[]).forEach(st=>(st.extract||[]).forEach(e=>{ if(e.var) s.add(e.var); })));
  return s;
}
function classifyValue(v){
  if(typeof v!=='string') return {source:'fixed',token:''};
  const m=v.trim().match(/^\$\{([^}]+)\}$/);
  if(!m) return {source:/\$\{[^}]+\}/.test(v)?'mixed':'fixed',token:''};
  const token=m[1].trim(), base=token.split('(')[0];
  if(GEN_NAMES.has(base)) return {source:'generated',token,base,args:(token.match(/\((.*)\)$/)||[,''])[1]};
  if(capturedVars().has(token)) return {source:'captured',token};
  if((dataColumns||[]).includes(token)) return {source:'file',token};
  return {source:'captured',token};
}
let _rdPaths=[];        // field paths of the open tables, addressed by index from the handlers
function requestDataHtml(si,sti,st){
  const k=stepKey(si,sti);
  let h=`<div class="stp-h">Request data<i class="infohint" data-tip="What this step sends. For each value choose: Fixed (always the same), From data file (a column of your uploaded file), or Generated (new for every request, so requests are unique).">i</i></div>`;
  if(!st.body){
    return h+`<div class="rd-empty">This request sends no body.</div>`+
      `<button class="btn ghost sm" style="padding:4px 10px" onclick="planModel.scenarios[${si}].steps[${sti}].body={};renderPlanForm()">+ Add a body</button>`;
  }
  if(jsonSteps.has(k)){
    h+=`<textarea id="bodyJson_${si}_${sti}" style="width:100%;min-height:150px;font-family:ui-monospace,Menlo,monospace;font-size:12px" oninput="setBodyJson(${si},${sti},this.value)">${esc(JSON.stringify(st.body,null,2))}</textarea>`+
       `<div class="statusline" id="bodyJsonMsg_${si}_${sti}"></div>`+
       `<button class="btn ghost sm" style="padding:4px 10px" onclick="jsonSteps.delete('${k}');renderPlanForm()">← Back to the field list</button>`;
    return h;
  }
  const fields=flattenBody(st.body);
  if(!fields.length) h+='<div class="rd-empty">The body is empty — add a field.</div>';
  else{
    h+='<table class="rd"><thead><tr><th>Field</th><th>Comes from</th><th>Value</th><th></th></tr></thead><tbody>';
    fields.forEach(f=>{ const fi=_rdPaths.push({si,sti,path:f.path})-1; h+=fieldRowHtml(fi,f); });
    h+='</tbody></table>';
  }
  h+=`<div class="btnrow" style="margin-top:8px;flex-wrap:wrap">
        <input id="newField_${si}_${sti}" placeholder="new field name" style="width:170px;margin:0;padding:6px 8px;font-size:12.5px" aria-label="New field name"
               onkeydown="if(event.key==='Enter'){event.preventDefault();addBodyField(${si},${sti})}"/>
        <button class="btn ghost sm" style="padding:4px 10px" onclick="addBodyField(${si},${sti})">+ Add field</button>
        <div class="spacer"></div>
        <button class="btn ghost sm" style="padding:4px 10px" id="dynBtn_${si}_${sti}" onclick="suggestSources(${si},${sti})">✨ Suggest with AI</button>
        <button class="btn ghost sm" style="padding:4px 10px" onclick="jsonSteps.add('${k}');renderPlanForm()">Edit as JSON</button>
      </div>
      <div class="note" id="dynNote_${si}_${sti}" style="display:none;margin-top:8px"></div>`;
  if(dynUndo[k]){
    h+=`<div class="note ok" style="margin-top:8px"><span>✨ The AI filled in the sources above. Check them — nothing is final until you approve.</span>
        <button class="btn ghost sm" style="padding:3px 9px;margin-left:auto" onclick="undoSuggest(${si},${sti})">Undo</button></div>`;
  }
  return h;
}
function fieldRowHtml(fi,f){
  const c=classifyValue(f.value);
  const {si,sti}=_rdPaths[fi];
  const earlier=earlierResponseValues(si,sti);
  const opts=[['fixed','Fixed value'],['file','From data file'],['generated','Generated']];
  if(earlier.length||c.source==='captured') opts.push(['captured','From an earlier response']);
  if(c.source==='mixed') opts.push(['mixed','Text with values in it']);
  const srcSel=`<select aria-label="Where ${esc(pathLabel(f.path))} comes from" onchange="setFieldSource(${fi},this.value)">`+
    opts.map(o=>`<option value="${o[0]}" ${o[0]===c.source?'selected':''}>${o[1]}</option>`).join('')+'</select>';
  let val='';
  if(c.source==='fixed'){
    const t = f.value===null?'null':typeof f.value==='boolean'?'bool':typeof f.value==='number'?'number':typeof f.value==='object'?'json':'text';
    const shown = t==='text'?f.value:(t==='null'?'':JSON.stringify(f.value));
    val=`<div class="rd-val"><input value="${esc(shown)}" ${t==='null'?'disabled placeholder="(empty)"':''} aria-label="Value" oninput="setFieldFixed(${fi},this.value)"/>`+
        `<select class="sm" aria-label="Kind of value" onchange="setFieldType(${fi},this.value)">`+
        [['text','text'],['number','number'],['bool','true / false'],['null','empty (null)']].concat(t==='json'?[['json','list / object']]:[])
          .map(o=>`<option value="${o[0]}" ${o[0]===t?'selected':''}>${o[1]}</option>`).join('')+'</select></div>';
  } else if(c.source==='file'){
    const cols=(dataColumns||[]);
    val=`<div class="rd-val"><select aria-label="Column" onchange="setFieldToken(${fi},this.value)">`+
        cols.map(col=>`<option value="${esc(col)}" ${col===c.token?'selected':''}>column: ${esc(col)}</option>`).join('')+'</select></div>';
  } else if(c.source==='generated'){
    const known=GEN_KINDS.some(g=>g[0]===c.base);
    val=`<div class="rd-val"><select aria-label="What to generate" onchange="setFieldGen(${fi},this.value)">`+
        GEN_KINDS.map(g=>`<option value="${g[0]}" ${g[0]===c.base?'selected':''}>${g[1]}</option>`).join('')+
        (known?'':`<option selected value="${esc(c.base)}">${esc(c.token)}</option>`)+'</select>'+genArgsHtml(fi,c)+'</div>';
  } else if(c.source==='captured'){
    const unavailable=earlier.includes(c.token)?'':`<option value="" selected disabled>${esc(c.token)} (unavailable)</option>`;
    val=`<div class="rd-val"><select aria-label="Captured response value" onchange="setFieldToken(${fi},this.value)">`+
        unavailable+earlier.map(name=>`<option value="${esc(name)}" ${name===c.token?'selected':''}>${esc(name)}</option>`).join('')+
        '</select></div>';
  } else {
    val=`<div class="rd-val"><input value="${esc(f.value)}" aria-label="Text" oninput="setFieldRaw(${fi},this.value)"/></div>`;
  }
  return `<tr class="${c.source}"><td class="f" title="${esc(pathLabel(f.path))}">${esc(pathLabel(f.path))}</td><td class="src">${srcSel}</td><td>${val}</td>`+
         `<td class="x"><button class="iconbtn" title="Remove this field" style="padding:2px 7px" onclick="delBodyField(${fi})">×</button></td></tr>`;
}
function genArgsHtml(fi,c){
  const a=(c.args||'').split(',').map(s=>s.trim());
  if(c.base==='randomInt') return `<input class="sm" type="number" value="${esc(a[0]||'1')}" aria-label="From" onchange="setFieldGenArgs(${fi},this.value+','+this.nextElementSibling.nextElementSibling.value)"/><span class="muted">to</span><input class="sm" type="number" value="${esc(a[1]||'100')}" aria-label="To" onchange="setFieldGenArgs(${fi},this.previousElementSibling.previousElementSibling.value+','+this.value)"/>`;
  if(c.base==='randomString') return `<input class="sm" type="number" min="1" value="${esc(a[0]||'8')}" aria-label="Length" onchange="setFieldGenArgs(${fi},this.value)"/><span class="muted">characters</span>`;
  if(c.base==='randomFrom') return `<input value="${esc(c.args||'')}" placeholder="a, b, c" aria-label="Choices, comma-separated" onchange="setFieldGenArgs(${fi},this.value)"/>`;
  if(c.base==='dateOffset') return `<input class="sm" type="number" value="${esc(a[0]||'3')}" aria-label="How many" onchange="setFieldGenArgs(${fi},this.value+',\\'days\\'')"/><span class="muted">days from now</span>`;
  return '';
}
function rdTarget(fi){ const t=_rdPaths[fi]; return {t, body:planModel.scenarios[t.si].steps[t.sti].body}; }
function earlierResponseValues(si,sti){
  return [...new Set(planModel.scenarios[si].steps.slice(0,sti)
    .flatMap(step=>(step.extract||[]).map(capture=>capture.var)).filter(Boolean))];
}
function rdSet(fi,value,rerender){ const {t,body}=rdTarget(fi); setAt(body,t.path,value); if(rerender) renderPlanForm(); }
function setFieldSource(fi,src){
  const {t,body}=rdTarget(fi); const cur=getAt(body,t.path);
  if(src==='fixed') return rdSet(fi, typeof cur==='string'&&/\$\{/.test(cur)?'':cur, true);
  if(src==='generated') return rdSet(fi,'${uuid}',true);
  if(src==='captured'){
    const [name]=earlierResponseValues(t.si,t.sti);
    if(name) return setFieldToken(fi,name);
  }
  if(src==='file'){
    if(!(dataColumns||[]).length){
      const sec=document.getElementById('dz'); renderPlanForm();
      const editor=sec.closest('details');
      if(editor) editor.open=true;
      const n=document.getElementById('dataInfo'); n.style.display='flex'; n.className='note warn';
      n.textContent='Upload a data file first — then its columns can be chosen for a field.';
      sec.scrollIntoView({behavior:'smooth',block:'center'}); return;
    }
    // prefer a column whose name matches the field
    const name=String(t.path[t.path.length-1]).toLowerCase();
    const col=dataColumns.find(c=>c.toLowerCase()===name)||dataColumns[0];
    return rdSet(fi,'${'+col+'}',true);
  }
  renderPlanForm();
}
function setFieldFixed(fi,text){
  const {t,body}=rdTarget(fi); const cur=getAt(body,t.path);
  let v=text;
  if(typeof cur==='number'){ const n=Number(text); v=(text.trim()!==''&&!isNaN(n))?n:cur; }
  else if(typeof cur==='boolean'){ v=/^(true|yes|1)$/i.test(text.trim()); }
  else if(cur&&typeof cur==='object'){ try{ v=JSON.parse(text); }catch(e){ return; } }
  setAt(body,t.path,v);
}
function setFieldType(fi,type){
  const {t,body}=rdTarget(fi); const cur=getAt(body,t.path);
  const text = cur===null?'':(typeof cur==='object'?JSON.stringify(cur):String(cur));
  let v=text;
  if(type==='number'){ const n=Number(text); v=isNaN(n)||text.trim()===''?0:n; }
  else if(type==='bool') v=/^(true|yes|1)$/i.test(text.trim());
  else if(type==='null') v=null;
  rdSet(fi,v,true);
}
function setFieldToken(fi,token){ rdSet(fi,'${'+token+'}',true); }
function setFieldGen(fi,base){ rdSet(fi,'${'+base+(GEN_DEFAULT_ARGS[base]?'('+GEN_DEFAULT_ARGS[base]+')':'')+'}',true); }
function setFieldGenArgs(fi,args){
  const {t,body}=rdTarget(fi); const c=classifyValue(getAt(body,t.path));
  rdSet(fi,'${'+c.base+'('+String(args).trim()+')}',false);
}
function setFieldRaw(fi,text){ rdSet(fi,text,false); }
function delBodyField(fi){ const {t,body}=rdTarget(fi); delAt(body,t.path); renderPlanForm(); }
function addBodyField(si,sti){
  const inp=document.getElementById('newField_'+si+'_'+sti); const name=(inp.value||'').trim();
  if(!name){ inp.focus(); return; }
  const st=planModel.scenarios[si].steps[sti]; if(!st.body||Array.isArray(st.body)) st.body={};
  // "address.city" adds a field inside address
  const parts=name.split('.').map(s=>s.trim()).filter(Boolean); let o=st.body;
  parts.slice(0,-1).forEach(p=>{ if(!o[p]||typeof o[p]!=='object'||Array.isArray(o[p])) o[p]={}; o=o[p]; });
  o[parts[parts.length-1]]='';
  renderPlanForm();
  const again=document.getElementById('newField_'+si+'_'+sti); if(again) again.focus();
}
function setBodyJson(si,sti,text){
  const msg=document.getElementById('bodyJsonMsg_'+si+'_'+sti);
  try{
    const v=text.trim()?JSON.parse(text):null;
    if(v!==null&&(typeof v!=='object'||Array.isArray(v))) throw new Error('the body must be a JSON object { … }');
    planModel.scenarios[si].steps[sti].body=v; msg.className='statusline ok'; msg.textContent='✓ Valid JSON — saved.';
  }catch(e){ msg.className='statusline err'; msg.textContent='Not saved yet: '+e.message; }
}
/* AI proposes a source for each field; the user reviews (and can undo). */
async function suggestSources(si,sti){
  const st=planModel.scenarios[si].steps[sti], k=stepKey(si,sti);
  const n=document.getElementById('dynNote_'+si+'_'+sti), btn=document.getElementById('dynBtn_'+si+'_'+sti);
  n.style.display='flex'; n.className='note info'; n.textContent='The AI is choosing a source for each field…'; btn.disabled=true;
  try{
    const payload={body:st.body}; if(currentDataFileId) payload.data_file_id=currentDataFileId;
    const r=await fetch('/api/dynamize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'failed');
    dynUndo[k]=JSON.parse(JSON.stringify(st.body));
    st.body=j.body; refreshUsage(); renderPlanForm();
  }catch(e){ n.className='note err'; n.textContent='Could not get a suggestion: '+e.message; btn.disabled=false; }
}
function undoSuggest(si,sti){ const k=stepKey(si,sti); if(dynUndo[k]){ planModel.scenarios[si].steps[sti].body=dynUndo[k]; delete dynUndo[k]; } renderPlanForm(); }

/* ----- preview: the requests that will be sent (nothing is sent now) ----- */
async function fetchPreview(){
  const payload={load_model:planModel, samples:3};
  if(currentDataFileId){ payload.data_file_id=currentDataFileId; payload.data_row_mode=dataRowMode; }
  else if(planModel.data_file){ payload.data_row_mode=dataRowMode; }
  const r=await fetch('/api/request-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const j=await r.json(); if(!r.ok) throw new Error(typeof j.detail==='string'?j.detail:'the plan has a value that is not valid yet');
  return j;
}
async function previewRequests(){
  const box=document.getElementById('previewBox'), btn=document.getElementById('previewBtn');
  box.style.display='block'; box.innerHTML='<div class="pv muted">Building the preview…</div>'; btn.disabled=true;
  try{
    const j=await fetchPreview();
    let h='<div class="pv"><div style="display:flex;align-items:center;gap:8px"><b>What will be sent</b>'+
      '<span class="muted" style="font-size:12px">sample values — nothing was sent to the target</span><div class="spacer"></div>'+
      '<button class="btn ghost sm" style="padding:3px 9px" onclick="document.getElementById(\'previewBox\').style.display=\'none\'">Close</button></div>';
    j.steps.forEach(s=>{
      h+='<div class="pv-step"><div style="font-size:12.5px"><span class="stp-m '+esc(s.method)+'">'+esc(s.method)+'</span> <b>'+esc(s.path)+'</b> <span class="muted">· '+esc(s.scenario)+'</span>'+
         (s.dynamic?'':' <span class="muted">· the same every time</span>')+'</div>';
      s.requests.forEach(q=>{
        h+='<div class="pv-req"><div class="pv-url">'+esc(q.method)+' '+esc(q.url)+(q.row_number?' <span class="muted" style="font-weight:400">· data row '+q.row_number+'</span>':'')+'</div>'+
           (q.body?'<pre>'+esc(JSON.stringify(q.body,null,2))+'</pre>':'')+'</div>';
      });
      if(s.run_time_values.length) h+='<div class="muted" style="font-size:12px">Filled in while the test runs (from an earlier response): '+s.run_time_values.map(v=>'<code class="k">'+esc(v)+'</code>').join(' ')+'</div>';
      if(s.undefined.length) h+='<div class="note warn" style="margin-top:6px">⚠ No source for '+s.undefined.map(v=>'<code class="k">'+esc(v)+'</code>').join(' ')+' — it would be sent empty. Pick a data-file column or another source for it.</div>';
      h+='</div>';
    });
    box.innerHTML=h+'</div>';
  }catch(e){ box.innerHTML='<div class="note err">Could not build the preview: '+esc(e.message)+'</div>'; }
  finally{ btn.disabled=false; }
}

function setGql(si,sti,v){ planModel.scenarios[si].steps[sti].graphql_query=v; }
function addGql(si,sti){ const st=planModel.scenarios[si].steps[sti]; st.graphql_query='query {\n  \n}'; if(st.method==='GET'){st.method='POST';} advSteps.add(stepKey(si,sti)); renderPlanForm(); }
function removeGql(si,sti){ planModel.scenarios[si].steps[sti].graphql_query=''; renderPlanForm(); }
const CHECK_TYPES=[
  {k:'body_contains', label:'Response body contains', vph:'text e.g. <Rate>'},
  {k:'not_contains',  label:'Response body does NOT contain', vph:'text e.g. <Error>'},
  {k:'status',        label:'Status code is', vph:'e.g. 200'},
  {k:'json_path',     label:'JSON field compares', vph:'expected value', path:true},
  {k:'response_time', label:'Response time under (ms)', vph:'e.g. 2000'},
];
function assertRowHtml(si,sti,ai,a){
  const typeOpts=CHECK_TYPES.map(t=>`<option value="${t.k}" ${t.k===a.kind?'selected':''}>${t.label}</option>`).join('');
  const ct=CHECK_TYPES.find(t=>t.k===a.kind)||CHECK_TYPES[0];
  const ops=['eq','ne','gt','lt','contains','exists'];
  const opOpts=ops.map(o=>`<option ${o===a.op?'selected':''}>${o}</option>`).join('');
  return `<div style="display:flex;gap:6px;align-items:center;margin-bottom:5px;flex-wrap:wrap;background:#f7faf8;padding:6px 8px;border-radius:8px">`+
    `<span style="color:var(--teal-d)">✔</span>`+
    `<select style="width:auto;padding:4px 7px" onchange="setAssert(${si},${sti},${ai},'kind',this.value);renderPlanForm()">${typeOpts}</select>`+
    (ct.path?`<input style="width:100px;padding:4px 7px" value="${esc(a.path||'')}" placeholder="field" oninput="setAssert(${si},${sti},${ai},'path',this.value)"/>`+
      `<select style="width:auto;padding:4px 7px" onchange="setAssert(${si},${sti},${ai},'op',this.value);renderPlanForm()">${opOpts}</select>`:'')+
    (ct.path&&a.op==='exists'?'':`<input style="width:130px;padding:4px 7px" value="${esc(a.value||'')}" placeholder="${ct.vph}" oninput="setAssert(${si},${sti},${ai},'value',this.value)"/>`)+
    `<button class="iconbtn" style="padding:2px 7px" onclick="removeAssertion(${si},${sti},${ai})">×</button></div>`;
}
function setAssert(si,sti,ai,key,val){
  const st=planModel.scenarios[si].steps[sti];
  if(!st.assertions) st.assertions=[];
  if(!st.assertions[ai]) st.assertions[ai]={kind:'status',op:'eq',path:'',value:''};
  st.assertions[ai][key]=val;
}
function addAssertion(si,sti){
  const st=planModel.scenarios[si].steps[sti];
  if(!st.assertions) st.assertions=[];
  st.assertions.push({kind:'status',op:'eq',path:'',value:'200'});
  renderPlanForm();
}
function removeAssertion(si,sti,ai){
  planModel.scenarios[si].steps[sti].assertions.splice(ai,1);
  renderPlanForm();
}
function setExtract(si,sti,key,val){
  const st=planModel.scenarios[si].steps[sti];
  if(!st.extract||!st.extract.length) st.extract=[{var:'',source:'json',path:''}];
  st.extract[0][key]=val;
}
function addExtract(si,sti){
  planModel.scenarios[si].steps[sti].extract=[{var:'token',source:'json',path:'token'}];
  renderPlanForm();
}
function removeExtract(si,sti){
  planModel.scenarios[si].steps[sti].extract=[];
  renderPlanForm();
}
const RULES=[
  ['p95_ms','95% of responses are faster than','ms'],
  ['p99_ms','99% of responses are faster than','ms'],
  ['p50_ms','Half of responses are faster than','ms'],
  ['avg_ms','The average response is faster than','ms'],
  ['max_ms','The slowest response is faster than','ms'],
  ['error_rate','The error rate stays under','%'],
];
function thresholdRow(t,ti){
  const el=document.createElement('div');
  const rule=RULES.find(r=>r[0]===t.metric);
  if(rule && (t.op==='<'||t.op==='<=')){
    // a sentence: only the number needs editing
    el.className='rule';
    const pct=rule[2]==='%';
    const shown=pct ? +(t.value*100).toFixed(4) : t.value;
    el.innerHTML=`<select aria-label="Rule" onchange="setRuleMetric(${ti},this.value)">
        ${RULES.map(r=>`<option value="${r[0]}" ${r[0]===t.metric?'selected':''}>${r[1]}</option>`).join('')}</select>
      <input type="number" step="any" min="0" value="${shown}" aria-label="Limit" oninput="setRuleValue(${ti},this.value)"/>
      <span class="unit">${pct?'%':'ms'}</span>
      <button class="iconbtn" title="Remove this rule" onclick="delThreshold(${ti})">×</button>`;
    return el;
  }
  // anything unusual (a custom metric, or a "greater than" rule) keeps the full editor
  el.className='thr';
  const metrics=RULES.map(r=>r[0]);
  el.innerHTML=`
    <select onchange="planModel.thresholds[${ti}].metric=this.value;renderPlanForm()">
      ${metrics.map(m=>`<option ${m===t.metric?'selected':''}>${m}</option>`).join('')}
      ${metrics.includes(t.metric)?'':`<option selected>${esc(t.metric)}</option>`}</select>
    <select onchange="planModel.thresholds[${ti}].op=this.value;renderPlanForm()">
      ${["<","<=",">",">="].map(o=>`<option ${o===t.op?'selected':''}>${o}</option>`).join('')}</select>
    <input type="number" step="any" value="${t.value}" oninput="planModel.thresholds[${ti}].value=parseFloat(this.value);renderSummary()"/>
    <button class="iconbtn" onclick="delThreshold(${ti})">×</button>`;
  return el;
}
function setRuleMetric(ti,metric){
  const t=planModel.thresholds[ti]; const wasPct=t.metric==='error_rate', isPct=metric==='error_rate';
  t.metric=metric;
  if(wasPct!==isPct) t.value = isPct ? 0.05 : 500;      // the old number was in the other unit
  renderPlanForm();
}
function setRuleValue(ti,text){
  const t=planModel.thresholds[ti]; const n=parseFloat(text); if(isNaN(n)) return;
  t.value = t.metric==='error_rate' ? n/100 : n;
  renderSummary();
}
export async function previewJourneyWeights(file){
  const editor=document.getElementById('journeyWeightPreview');
  const status=document.getElementById('journeyWeightStatus');
  const input=document.getElementById('journeyWeightCsv');
  editor.replaceChildren();
  status.textContent='';
  if(!file||!planModel)return;
  const plan=planModel;
  const signature=()=>JSON.stringify([planModel?.scenarios,planModel?.load_profile]);
  const current=signature();
  if(plan.scenarios.length<2){status.textContent='Add at least two journeys before mapping the sample.';return;}
  if(plan.load_profile.target_request_rate){
    status.textContent='An exact HTTP request-rate target uses one journey. Choose a journey-start or virtual-user workload for multiple journeys.';
    return;
  }
  try{
    if(file.size>maxTrafficBytes)throw Error('Choose a CSV file up to 256 KiB.');
    const summary=summarizeTraffic(await file.text());
    if(input.files[0]!==file||planModel!==plan||signature()!==current)return;
    const options=journeyRouteOptions(plan.scenarios,summary.mix);
    if(options.some(items=>!items.length)){
      const names=plan.scenarios.filter((_,index)=>!options[index].length).map(item=>item.name);
      status.textContent='No exclusive sampled route for '+names.join(', ')+'. Adjust those weights manually.';
      return;
    }
    editor.innerHTML=`<div class="release-grid">${options.map((items,index)=>`<label>${esc(plan.scenarios[index].name)}
      <select>${items.map(item=>`<option>${esc(item.route)} · ${item.count.toLocaleString()} requests</option>`).join('')}</select>
      <output></output></label>`).join('')}</div>
      <p class="hint" data-rate-estimate></p><button type="button" class="btn ghost sm">Apply suggested weights</button>`;
    const selectors=[...editor.querySelectorAll('select')];
    const outputs=editor.querySelectorAll('output');
    const weights=()=>normalizedJourneyWeights(selectors.map((select,index)=>options[index][select.selectedIndex]));
    const render=()=>{
      const shares=weights();
      shares.forEach((share,index)=>{outputs[index].textContent=Number((share*100).toFixed(2))+'% suggested share';});
      const avg=shares.reduce((sum,share,index)=>sum+share*plan.scenarios[index].steps.length,0);
      const profile=plan.load_profile;
      const rate=profile.arrival_rate&&!profile.target_request_rate&&!profile.executor_options?profile.arrival_rate:null;
      editor.querySelector('[data-rate-estimate]').textContent='About '+Number(avg.toFixed(2))+' HTTP requests per journey start'+
        (rate?' · about '+Number((rate*avg).toFixed(2))+' req/s at '+rate+' journey starts/s before k6 allocation rounding.':'. Actual throughput depends on the workload and target.');
    };
    for(const select of selectors)select.onchange=render;
    render();
    editor.querySelector('button').onclick=()=>{
      if(planModel!==plan||signature()!==current){
        editor.replaceChildren();
        status.textContent='The journeys changed. Choose the CSV again to rebuild the mapping.';
        input.value='';
        return;
      }
      weights().forEach((weight,index)=>{plan.scenarios[index].weight=weight;});
      editor.replaceChildren();
      status.textContent='Applied. Review the updated journey shares before approving.';
      input.value='';
      renderPlanForm();
    };
    status.textContent='Choose one representative route per journey.';
  }catch(error){
    if(input.files[0]===file&&planModel===plan)status.textContent=error.message;
  }
}
function setWeight(si,value){
  const weight=Number(value);
  if(!Number.isFinite(weight)||weight<=0||weight>1000000){showError('Journey weight must be greater than zero and no more than 1,000,000.');return false;}
  planModel.scenarios[si].weight=weight;
  updateWeightBadges();
  renderSummary();
  return true;
}
function updateWeightBadges(){
  const total=(planModel.scenarios||[]).reduce((a,s)=>a+(s.weight||0),0)||1;
  (planModel.scenarios||[]).forEach((s,i)=>{
    const b=document.getElementById('wb'+i); if(b) b.textContent=Math.round((s.weight/total)*100)+'%';
  });
}
function addScenario(){ planModel.scenarios.push({name:"New scenario",weight:1,
  steps:[{name:"step",method:"GET",path:"/",body:null}],think_time:{min_seconds:1,max_seconds:3}});
  openSteps.add(stepKey(planModel.scenarios.length-1,0)); renderPlanForm(); }
function forgetOpenSteps(){ openSteps=new Set(); jsonSteps=new Set(); advSteps=new Set(); dynUndo={}; }
function delScenario(si){
  if((planModel.scenarios||[]).length<=1){ alert('A plan needs at least one journey.'); return; }
  planModel.scenarios.splice(si,1); forgetOpenSteps(); renderPlanForm(); }
function addStep(si){
  const steps=planModel.scenarios[si].steps; steps.push({name:"step",method:"GET",path:"/",body:null});
  openSteps.add(stepKey(si,steps.length-1)); renderPlanForm(); }     // open it, ready to fill in
function delStep(si,sti){
  if(planModel.scenarios[si].steps.length<=1){ alert('A journey needs at least one step.'); return; }
  planModel.scenarios[si].steps.splice(sti,1); forgetOpenSteps(); renderPlanForm(); }
function addThreshold(){ planModel.thresholds=planModel.thresholds||[];
  planModel.thresholds.push({metric:"p95_ms",op:"<=",value:500}); renderPlanForm(); }
function delThreshold(ti){ planModel.thresholds.splice(ti,1); renderPlanForm(); }

/* raw <-> form sync */
function renderRawFromModel(){ document.getElementById('planJson').value=JSON.stringify(planModel,null,2); }
function toggleRaw(){
  const raw=document.getElementById('rawToggle').checked;
  if(raw){ renderRawFromModel(); document.getElementById('planForm').style.display='none';
           document.getElementById('planJson').style.display='block'; }
  else{ try{ planModel=JSON.parse(document.getElementById('planJson').value); }catch(e){ alert('Raw JSON is invalid — fix it before switching back.'); document.getElementById('rawToggle').checked=true; return; }
        document.getElementById('planForm').style.display='block';
        document.getElementById('planJson').style.display='none'; _loadAsked=null; renderPlanForm(); }
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

/* ---------- generate ---------- */
async function doGenerate(){
  const status=document.getElementById('genStatus');
  // sync model from the active editor
  document.getElementById('pfTarget') && (planModel.target_base_url=document.getElementById('pfTarget').value.trim());
  if(document.getElementById('rawToggle').checked){
    try{ planModel=JSON.parse(document.getElementById('planJson').value); }
    catch(e){ status.className='statusline err'; status.textContent='Raw JSON invalid: '+e.message; return; }
  }
  const filename=planModel.script_filename||'';
  const extension={k6:'.js',locust:'.py',jmeter:'.jmx',gatling:'.scala'}[document.getElementById('tool').value];
  if(filename&&(!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(filename)||filename.includes('..')||filename.length>120||
      (extension&&!filename.endsWith(extension)))){
    status.className='statusline err';
    status.textContent='Use a script filename of up to 120 characters, without folders, spaces, or ".."'+
      (extension?', ending in '+extension+'.':'.');
    const field=document.getElementById('pfScriptFilename');
    if(!document.getElementById('rawToggle').checked&&field){
      const editor=field.closest('details');
      if(editor) editor.open=true;
      field.focus();
    }
    return;
  }
  // Accuracy guard: a ${name} with no source would be sent as an empty value.
  try{
    const pv=await fetchPreview();
    const bad=[...new Set(pv.steps.flatMap(st=>st.undefined.map(u=>u+'  ('+st.method+' '+st.path+')')))];
    if(bad.length && !confirm('These values have no source and would be sent empty:\n\n  '+bad.join('\n  ')+
        '\n\nGenerate the script anyway?')){
      status.className='statusline err'; status.textContent='Not generated — give those values a source first.'; return;
    }
  }catch(e){ status.className='statusline err'; status.textContent='The plan is not valid yet: '+e.message; return; }
  status.className='statusline'; status.textContent='Generating script…';
  try{
    const payload={tool:document.getElementById('tool').value, load_model:planModel};
    if(currentDataFileId) payload.data_file_id=currentDataFileId;
    if(currentDataFileId || planModel.data_file) payload.data_row_mode=dataRowMode;
    // The header list on this page is the truth (so removing a header really removes it).
    const hdrs=readHeaders(); planModel.headers=hdrs; if(Object.keys(hdrs).length) payload.headers=hdrs;
    const r=await fetch(`/api/plan/${currentPlanId}/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'generate failed');
    setReviewSources(j.review_sources);
    currentScriptId=j.script_id; _scriptEdited=false;
    if(!j.reused) document.getElementById('preflightResult').style.display='none';
    document.getElementById('scriptOut').textContent=j.content;
    document.getElementById('dlBtn').disabled=false;
    document.getElementById('runBtn').disabled=(j.tool!=='k6');
    document.getElementById('preflightBtn').disabled=false;
    document.getElementById('validateBtn').disabled=false;
    setGitExport(j.tool==='k6', '');
    document.getElementById('scriptMeta').textContent=`${j.filename} (${j.tool}) · ${j.reused?'Latest version reused — no changes':'Latest script version'}`;
    const pill=document.getElementById('scriptPill'); pill.style.display='inline-flex'; pill.textContent=j.tool;
    if(j.tool!=='k6'){ const h=document.getElementById('runHint'); h.style.display='flex'; h.textContent='Live run is implemented for k6; download and run this '+j.tool+' script yourself.'; }
    status.textContent='';
    goStep(3); loadPlans();
  }catch(e){ status.className='statusline err'; status.textContent='Error: '+e.message; }
}

/* Attach a data file that is already stored (e.g. one imported from Git). */
async function attachStoredDataFile(id){
  try{
    const r=await fetch('/api/data/'+encodeURIComponent(id)); const j=await r.json(); if(!r.ok) return;
    currentDataFileId=j.data_file_id; dataColumns=j.fields;
    dataFileInfo={filename:j.filename,row_count:j.row_count,sample_rows:j.sample_rows||[]};
    renderPlanForm();
  }catch(e){}
}
function download(){ if(currentScriptId) downloadArtifact('/api/scripts/'+encodeURIComponent(currentScriptId)+'/download','demo-script.js'); }

function downloadArtifact(path, filename){
  if(import.meta.env.MODE!=='demo'){location=path;return;}
  void fetch(path).then(response=>{
    if(!response.ok)throw Error('This demo download is unavailable.');
    return response.blob();
  }).then(blob=>{
    const url=URL.createObjectURL(blob);
    const link=document.createElement('a');
    link.href=url;
    link.download=filename;
    link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }).catch(error=>showError(error.message));
}

/* ---------- saved (non-secret) Git & Jenkins details ---------- */
const GIT_FIELDS={repo_url:'gitRepo', branch:'gitBranch', framework:'gitFw', test:'gitTest'};
const JK_FIELDS={url:'jkUrl', username:'jkUser', job:'jkJob', test:'jkTest', environment:'jkEnv',
                 repo_url:'jkRepo', branch:'jkBranch', framework:'jkFw', git_credentials_id:'jkGitCred'};
const FIELD_DEFAULTS={gitBranch:'main', jkBranch:'main', jkEnv:'dev'};
let integrationsSeq=0;
function setFields(map, values){
  Object.entries(map).forEach(([key,id])=>{
    const el=document.getElementById(id); if(!el) return;
    el.value = values[key] ?? FIELD_DEFAULTS[id] ?? '';
  });
}
async function applyIntegrations(planId){
  const seq=++integrationsSeq;
  try{
    const j=await (await fetch('/api/integrations'+(planId?`?plan_id=${encodeURIComponent(planId)}`:''))).json();
    if(seq!==integrationsSeq) return;            // a newer plan was opened meanwhile
    const gitSettings={...projectGitDefaults(),...(j.git||{})};setFields(GIT_FIELDS,gitSettings);
    if(Array.isArray(gitSettings.ci))document.querySelectorAll('.gitCi').forEach(c=>c.checked=gitSettings.ci.includes(c.value));
    const jv={...(j.jenkins||{})};
    if(!jv.repo_url && j.git && j.git.repo_url) jv.repo_url=j.git.repo_url;
    if(!jv.framework && j.git && j.git.framework) jv.framework=j.git.framework;
    if(!jv.job && j.git && j.git.framework) jv.job=j.git.framework;
    if(!jv.test && j.git && j.git.test) jv.test=j.git.test;
    setFields(JK_FIELDS, jv);
    showSaved('gitSaved', (j.saved||[]).includes('git'), 'git');
    showSaved('jkSaved', (j.saved||[]).includes('jenkins'), 'jenkins');
  }catch(e){ /* saved details are a convenience; never block the page */ }
}
function showSaved(id, saved, section){
  const el=document.getElementById(id);
  if(!saved){ el.style.display='none'; el.innerHTML=''; return; }
  el.style.display='inline';
  el.innerHTML=`· saved details loaded — just enter your token · <a href="#" onclick="forgetIntegrations('${section}');return false">Forget saved details</a>`;
}
async function forgetIntegrations(section){
  if(!confirm(`Forget the saved ${section==='git'?'Git':'Jenkins'} details for this plan (and the last-used defaults)? Tokens were never saved.`)) return;
  try{
    await fetch(`/api/integrations?section=${section}`+(currentPlanId?`&plan_id=${encodeURIComponent(currentPlanId)}`:''),{method:'DELETE'});
    applyIntegrations(currentPlanId);
  }catch(e){}
}


/* ---------- run in Jenkins ---------- */
let jk={queueId:null, build:null, logNext:0, timer:null, errors:0};
function jkVal(id){ return document.getElementById(id).value.trim(); }
function fillIfEmpty(id, v){ const el=document.getElementById(id); if(!el.value.trim() && v) el.value=v; }
function syncJenkinsDefaults(){
  fillIfEmpty('jkJob', jkVal('gitFw')); fillIfEmpty('jkTest', jkVal('gitTest'));
  fillIfEmpty('jkRepo', jkVal('gitRepo')); fillIfEmpty('jkFw', jkVal('gitFw'));
  if(jkVal('gitBranch') && jkVal('jkBranch')==='main') document.getElementById('jkBranch').value=jkVal('gitBranch');
}
function jkAuth(){
  return {jenkins_url:jkVal('jkUrl'), username:jkVal('jkUser'), api_token:jkVal('jkToken'), job:jkVal('jkJob'), plan_id:currentPlanId||null};
}
function jkCheck(st){
  const a=jkAuth();
  if(!a.jenkins_url||!a.username||!a.api_token){ st.className='statusline err'; st.textContent='Enter the Jenkins URL, user name and API token.'; return null; }
  if(!a.job){ st.className='statusline err'; st.textContent='Enter the Jenkins job name.'; return null; }
  return a;
}
function toggleJenkinsSetup(){
  syncJenkinsDefaults();
  const el=document.getElementById('jkSetup'); el.style.display = el.style.display==='none' ? 'block' : 'none';
}
function jkSetPill(text, cls){
  const p=document.getElementById('jkPill'); p.style.display='inline-flex'; p.textContent=text; p.className='pill '+cls;
}
async function jenkinsSetup(){
  const st=document.getElementById('jkStatus'); const a=jkCheck(st); if(!a) return;
  const body={...a, repo_url:jkVal('jkRepo'), branch:jkVal('jkBranch')||'main', framework:jkVal('jkFw'), git_credentials_id:jkVal('jkGitCred')};
  if(!body.repo_url||!body.framework){ st.className='statusline err'; st.textContent='Enter the repository URL and framework name for the job.'; return; }
  st.className='statusline'; st.textContent='Setting up the Jenkins job…';
  try{
    const j=await gitPost('/api/jenkins/setup-job', body);
    st.className='statusline ok';
    applyIntegrations(currentPlanId);
    st.textContent=`Job '${j.job}' ${j.action}. It builds ${body.framework}/ci/Jenkinsfile from ${body.branch}.`+(j.warnings.length?' Note: '+j.warnings.join(' '):'');
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}
async function jenkinsRun(){
  syncJenkinsDefaults();
  const st=document.getElementById('jkStatus'); const a=jkCheck(st); if(!a) return;
  if(jk.timer){ clearInterval(jk.timer); jk.timer=null; }
  jk={queueId:null, build:null, logNext:0, timer:null, errors:0};
  const log=document.getElementById('jkLog'); log.textContent=''; log.style.display='none';
  document.getElementById('jkResults').style.display='none';
  document.getElementById('jkLink').style.display='none';
  st.className='statusline'; st.textContent='Triggering Jenkins…';
  document.getElementById('jkRunBtn').disabled=true;
  try{
    const j=await gitPost('/api/jenkins/trigger', {...a, test:jkVal('jkTest')||'all', environment:jkVal('jkEnv')||'dev'});
    jk.queueId=j.queue_id; jkSetPill('queued','ghost'); applyIntegrations(currentPlanId);
    st.textContent=`Triggered job '${j.job}'. Waiting for Jenkins…`+(j.warnings.length?' Note: '+j.warnings.join(' '):'');
    jk.timer=setInterval(jenkinsPoll, 3000); jenkinsPoll();
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; document.getElementById('jkRunBtn').disabled=false; }
}
async function jenkinsPoll(){
  if(jk.polling) return; jk.polling=true;
  const st=document.getElementById('jkStatus'), log=document.getElementById('jkLog');
  try{
    const body={...jkAuth(), log_start:jk.logNext};
    if(jk.build) body.build_number=jk.build; else body.queue_id=jk.queueId;
    const j=await gitPost('/api/jenkins/status', body); jk.errors=0;
    if(j.build_number && !jk.build){ jk.build=j.build_number; document.getElementById('jkStopBtn').disabled=false; }
    if(j.build_url){ const l=document.getElementById('jkLink'); l.href=j.build_url; l.style.display='inline'; }
    if(j.log){ log.style.display='block'; const atEnd=log.scrollTop+log.clientHeight>=log.scrollHeight-20;
      log.textContent+=j.log; if(atEnd) log.scrollTop=log.scrollHeight; }
    jk.logNext=j.log_next;
    if(j.state==='queued'){ jkSetPill('queued','ghost'); st.className='statusline'; st.textContent='Queued in Jenkins: '+(j.why||'waiting'); }
    else if(j.state==='running'){ jkSetPill('running','pass'); st.className='statusline'; st.textContent=`Build #${j.build_number} is running…`; }
    else if(j.state==='cancelled'){ jenkinsDone(); jkSetPill('cancelled','na'); st.className='statusline err'; st.textContent=j.why||'Cancelled.'; }
    else if(j.state==='finished' && !j.log_more){
      jenkinsDone();
      const v=j.verdict, res=j.result||'';
      jkSetPill(v?v.toUpperCase():res, v==='pass'?'pass':v==='fail'?'fail':(res==='SUCCESS'?'pass':res==='ABORTED'?'na':'fail'));
      st.className='statusline '+((v==='pass'||(!v&&res==='SUCCESS'))?'ok':'err');
      st.textContent=`Build #${j.build_number} finished: ${res}`+(j.duration_ms?` in ${Math.round(j.duration_ms/1000)}s`:'')
        +(v?` · verdict ${v.toUpperCase()}`:(res==='SUCCESS'?'':' · no k6 results were archived (see the console log)'));
      renderJenkinsResults(j.results||[]);
    }
  }catch(e){
    jk.errors++;
    if(jk.errors>=3){ jenkinsDone(); st.className='statusline err'; st.textContent='Stopped following the build: '+e.message; }
  }finally{ jk.polling=false; }
}
function jenkinsDone(){
  if(jk.timer){ clearInterval(jk.timer); jk.timer=null; }
  document.getElementById('jkRunBtn').disabled=false; document.getElementById('jkStopBtn').disabled=true;
}
function renderJenkinsResults(results){
  const el=document.getElementById('jkResults'); if(!results.length){ el.style.display='none'; return; }
  const fmt=(v,suf)=> v===null||v===undefined ? '—' : v+suf;
  el.innerHTML=results.map(r=>`
    <div style="display:flex;align-items:center;gap:8px;margin:6px 0"><b>${esc(r.test)}</b>
      <span class="pill ${r.verdict==='pass'?'pass':r.verdict==='fail'?'fail':'na'}">${esc(r.verdict.toUpperCase())}</span></div>
    <div class="tiles">
      <div class="tile"><div class="v">${r.requests}</div><div class="l">Requests</div></div>
      <div class="tile"><div class="v">${r.rps}</div><div class="l">Req/sec</div></div>
      <div class="tile"><div class="v">${(r.error_rate*100).toFixed(2)}%</div><div class="l">Error rate</div></div>
      <div class="tile"><div class="v">${fmt(r.avg_ms,' ms')}</div><div class="l">Avg</div></div>
      <div class="tile"><div class="v">${fmt(r.p95_ms,' ms')}</div><div class="l">p95</div></div>
      <div class="tile"><div class="v">${fmt(r.max_ms,' ms')}</div><div class="l">Max</div></div>
    </div>
    ${r.thresholds.length?'<table><thead><tr><th>Metric</th><th>Threshold</th><th>Result</th></tr></thead><tbody>'+
      r.thresholds.map(t=>`<tr><td>${esc(t.metric)}</td><td><code class="k">${esc(t.threshold)}</code></td><td><span class="pill ${t.passed===true?'pass':t.passed===false?'fail':'na'}">${t.passed===true?'passed':t.passed===false?'failed':'unavailable'}</span></td></tr>`).join('')+'</tbody></table>':''}`).join('');
  el.style.display='block';
}
async function jenkinsStop(){
  if(!jk.build) return;
  const st=document.getElementById('jkStatus');
  try{ await gitPost('/api/jenkins/stop', {...jkAuth(), build_number:jk.build}); st.className='statusline'; st.textContent=`Stopping build #${jk.build}…`; }
  catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}


/* ---------- save to Git ---------- */
function setGitExport(enabled, reason){
  document.getElementById('gitBtn').disabled=!enabled;
  document.getElementById('gitZipBtn').disabled=!enabled;
  const st=document.getElementById('gitStatus');
  st.className='statusline'; st.textContent=reason||'';
}
async function loadExportSettings(){
  try{ const j=await (await fetch('/api/export/settings')).json();
    if(j.allowed_hosts&&j.allowed_hosts.length)
      document.getElementById('gitHint').textContent+=' Allowed Git hosts: '+j.allowed_hosts.join(', ')+'.';
  }catch(e){}
}
function exportBody(){
  return {
    framework_name:document.getElementById('gitFw').value.trim(),
    test_name:document.getElementById('gitTest').value.trim(),
    repo_url:document.getElementById('gitRepo').value.trim(),
    branch:document.getElementById('gitBranch').value.trim()||'main',
    ci:[...document.querySelectorAll('.gitCi:checked')].map(c=>c.value),
    include_data:document.getElementById('gitData').checked,
    data_file_id:currentDataFileId||null,
  };
}
function exportReady(st){
  const b=exportBody();
  if(!currentScriptId){ st.className='statusline err'; st.textContent='Generate a k6 script first.'; return null; }
  if(!b.framework_name||!b.test_name){ st.className='statusline err'; st.textContent='Enter a framework name and a test name.'; return null; }
  return b;
}
function secretsNote(list){ return list&&list.length ? ' Add these as CI secrets: '+list.join(', ')+'.' : ''; }
async function exportGit(){
  const st=document.getElementById('gitStatus'); const b=exportReady(st); if(!b) return;
  if(!b.repo_url){ st.className='statusline err'; st.textContent='Enter the Git repository URL.'; return; }
  const token=document.getElementById('gitToken').value.trim();
  if(b.repo_url.startsWith('https://')&&!token){ st.className='statusline err'; st.textContent='Enter an access token that can push to this repository.'; return; }
  b.git_token=token||null;
  st.className='statusline'; st.textContent='Pushing to Git…';
  const btn=document.getElementById('gitBtn'); btn.disabled=true;
  try{
    const r=await fetch(`/api/scripts/${currentScriptId}/export/git`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'export failed');
    applyIntegrations(currentPlanId);
    st.className='statusline ok';
    st.textContent=(j.changed ? `Committed ${j.commit.slice(0,8)} to ${j.branch}: ${j.framework}/tests/${j.test}.` : `No changes — ${j.framework}/tests/${j.test} is already up to date on ${j.branch}.`)
      + secretsNote(j.required_secrets) + (j.warnings.length ? ' Note: '+j.warnings.join(' ') : '');
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
  finally{ btn.disabled=false; }
}
async function exportZip(){
  const st=document.getElementById('gitStatus'); const b=exportReady(st); if(!b) return;
  st.className='statusline'; st.textContent='Building framework…';
  try{
    const r=await fetch(`/api/scripts/${currentScriptId}/export/zip`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
    if(!r.ok){ const j=await r.json(); throw new Error(j.detail||'export failed'); }
    const blob=await r.blob(); const a=document.createElement('a');
    const name=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/);
    a.href=URL.createObjectURL(blob); a.download=name?name[1]:'framework.zip'; a.click(); URL.revokeObjectURL(a.href);
    const sec=(r.headers.get('X-Required-Secrets')||'').split(',').filter(Boolean);
    st.className='statusline ok'; st.textContent='Framework downloaded.'+secretsNote(sec);
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}


/* ---------- import from Git ---------- */
let gitScan=null, gitViewed=null;
function gitSource(){
  const s={repo_url:document.getElementById('impRepo').value.trim(),
           branch:document.getElementById('impBranch').value.trim()||'main'};
  const t=document.getElementById('impToken').value.trim(); if(t) s.git_token=t;
  return s;
}
async function gitPost(url, body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json(); if(!r.ok) throw new Error(j.detail||'request failed'); return j;
}
async function gitBrowse(){
  const st=document.getElementById('impStatus'), out=document.getElementById('impResults');
  const src=gitSource();
  if(!src.repo_url){ st.className='statusline err'; st.textContent='Enter the Git repository URL.'; return; }
  st.className='statusline'; st.textContent='Reading repository…'; out.innerHTML='';
  document.getElementById('impScriptView').style.display='none';
  const btn=document.getElementById('impBrowseBtn'); btn.disabled=true;
  try{
    gitScan=await gitPost('/api/git/scan', src);
    const nTests=gitScan.frameworks.reduce((a,f)=>a+f.tests.length,0);
    st.className='statusline ok';
    st.textContent=`Commit ${gitScan.commit.slice(0,8)} on ${gitScan.branch}: ${gitScan.frameworks.length} PerfAgent framework(s), ${nTests} test(s), ${gitScan.other_scripts.length} other script(s).`
      +(gitScan.truncated?' Large repository: only part of it was scanned.':'');
    renderGitScan();
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
  finally{ btn.disabled=false; }
}
function renderGitScan(){
  const out=document.getElementById('impResults'); let h='';
  gitScan.frameworks.forEach((f,fi)=>{
    h+=`<h3 style="margin:16px 0 4px;font-size:14px">${esc(f.name)} <button class="btn ghost sm" onclick="importWholeFramework(${fi})">Import / sync all tests</button> <span class="pill ghost">${esc(f.tool)}</span> ${f.path!==f.name?`<span class="muted" style="font-weight:400">${esc(f.path)}</span>`:''}</h3>
      <table><thead><tr><th>Test</th><th>Target</th><th>Load</th><th>Needs</th><th>Status</th><th></th></tr></thead><tbody>`;
    f.tests.forEach((t,ti)=>{
      const load=t.error?'':`${esc(t.profile)} · ${t.peak_users} users · ${t.duration_seconds}s`;
      const needs=[...(t.required_secrets||[]).map(x=>'🔑 '+esc(x)), t.data_file?('📁 '+esc(t.data_file)+(t.data_committed?'':' (not in Git)')):''].filter(Boolean).join('<br>')||'—';
      const status=t.error?`<span class="pill fail">invalid</span>`:(t.edited_in_git?`<span class="pill na" title="loadtest.js was changed by hand in Git">edited in Git</span>`:`<span class="pill pass">ok</span>`);
      const action=t.error?`<span class="muted">${esc(t.error)}</span>`:`<button class="btn ghost sm" onclick="gitImportStart(${fi},${ti})">Import</button>`;
      h+=`<tr class="histrow"><td><b>${esc(t.test)}</b></td><td>${esc(t.target_base_url||'')}</td><td>${load}</td><td>${needs}</td><td>${status}</td><td>${action}</td></tr>
          <tr id="impRow_${fi}_${ti}" style="display:none"><td colspan="6"></td></tr>`;
    });
    h+='</tbody></table>';
  });
  if(gitScan.other_scripts.length){
    h+=`<h3 style="margin:16px 0 4px;font-size:14px">Other load-test scripts</h3>
      <table><thead><tr><th>Path</th><th>Tool</th><th>Size</th><th></th></tr></thead><tbody>`+
      gitScan.other_scripts.map((o,i)=>`<tr class="histrow"><td><code class="k">${esc(o.path)}</code></td><td>${esc(o.tool)}</td><td>${(o.size/1024).toFixed(1)} KB</td>
        <td><button class="btn ghost sm" onclick="gitViewScript(${i})">View</button></td></tr>`).join('')+'</tbody></table>';
  }
  if(!gitScan.frameworks.length && !gitScan.other_scripts.length)
    h='<div class="note info">No PerfAgent frameworks or load-test scripts were found on this branch.</div>';
  out.innerHTML=h;
}
function gitImportStart(fi,ti){
  const t=gitScan.frameworks[fi].tests[ti];
  const row=document.getElementById(`impRow_${fi}_${ti}`); const cell=row.firstElementChild;
  const secrets=(t.required_secrets||[]).map(x=>`<div class="field"><label>${esc(x)}</label>
      <input type="password" class="impSecret" data-name="${esc(x)}" placeholder="Value for this secret (optional now)" autocomplete="new-password"/></div>`).join('');
  cell.innerHTML=`<div style="padding:8px 0">${secrets?'<p class="hint">This test needs secrets that were never stored in Git. Enter them now, or add them later under Custom headers.</p>'+secrets:''}
     ${t.edited_in_git?'<div class="note warn">loadtest.js was edited directly in Git. PerfAgent rebuilds the script from the plan, so those hand edits will not be imported.</div>':''}
     ${t.data_file&&!t.data_committed?`<div class="note warn">Test data '${esc(t.data_file)}' is not in Git; upload it in Step 1 before generating.</div>`:''}
     <div class="btnrow"><button class="btn sm" onclick="gitImport(${fi},${ti})">Import as plan →</button>
     <button class="btn ghost sm" onclick="this.closest('tr').style.display='none'">Cancel</button></div></div>`;
  row.style.display='';
}
async function gitImport(fi,ti){
  const f=gitScan.frameworks[fi], t=f.tests[ti];
  const row=document.getElementById(`impRow_${fi}_${ti}`), st=document.getElementById('impStatus');
  const secrets={}; row.querySelectorAll('.impSecret').forEach(i=>{ if(i.value.trim()) secrets[i.dataset.name]=i.value.trim(); });
  st.className='statusline'; st.textContent=`Importing ${f.name}/${t.test}…`;
  try{
    const j=await gitPost('/api/git/import',{...gitSource(), project_id:currentProject?.project_id,framework_path:f.path, test:t.test, secrets, expected_commit:gitScan.commit});
    currentPlanId=j.plan_id; planModel=j.load_model; planRationale=''; currentScriptId=null;
    const toolSel=document.getElementById('tool'); if([...toolSel.options].some(o=>o.value==='k6')) toolSel.value='k6';
    applyIntegrations(j.plan_id);
    renderPlanForm(); renderRawFromModel();      // headers + data file are read from the plan
    if(j.data_file_id) attachStoredDataFile(j.data_file_id);   // the file committed with the test
    document.getElementById('guardrailBadge').style.display='none';
    document.getElementById('planEval').style.display='none';
    const meta=document.getElementById('planMeta'); meta.style.display='inline-flex';
    meta.textContent=`imported from Git · ${j.framework}/${j.test} @ ${j.commit.slice(0,8)}`;
    const note=document.getElementById('importNote');
    if(j.warnings.length){ note.className='note warn'; note.innerHTML=j.warnings.map(esc).join('<br>'); }
    else{ note.className='note ok'; note.textContent='Imported from Git. Review the plan, then approve and generate.'; }
    note.style.display='flex';
    st.className='statusline ok'; st.textContent=`Imported ${j.framework}/${j.test}.`;
    loadPlans();
    goStep(2);return true;
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message;return false; }
}
async function importWholeFramework(fi){
  if(!currentProject)return;
  const framework=gitScan.frameworks[fi];let imported=0,failed=0;
  try{
    currentProject=await projectApi('/api/projects/'+currentProject.project_id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...currentProject,framework_name:framework.name,repo_url:gitSource().repo_url,branch:gitSource().branch})});
    for(let ti=0;ti<framework.tests.length;ti++){
      if(framework.tests[ti].error){failed++;continue;}
      if(await gitImport(fi,ti))imported++;else failed++;
    }
    await loadProjects();showView('history');
    if(failed)showError('Imported '+imported+' tests; '+failed+' tests need attention. Reopen Git import to inspect them.');
  }catch(e){showError(e.message);}
}
async function gitViewScript(i){
  const o=gitScan.other_scripts[i], st=document.getElementById('impStatus');
  st.className='statusline'; st.textContent=`Loading ${o.path}…`;
  try{
    const j=await gitPost('/api/git/script',{...gitSource(), path:o.path});
    gitViewed=j;
    document.getElementById('impScriptTitle').textContent=j.path;
    document.getElementById('impScriptTool').textContent=j.tool;
    document.getElementById('impScriptBody').textContent=j.content;
    document.getElementById('impUseRow').style.display = j.tool==='k6' ? 'block' : 'none';
    document.getElementById('impViewOnly').style.display = j.tool==='k6' ? 'none' : 'block';
    document.getElementById('impScriptView').style.display='block';
    st.className='statusline'; st.textContent='';
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}
async function gitUseScript(){
  if(!gitViewed||gitViewed.tool!=='k6') return;
  const st=document.getElementById('impStatus');
  st.className='statusline'; st.textContent='Loading script…';
  try{
    const body={filename:gitViewed.path.split('/').pop()||'loadtest.js', content:gitViewed.content,
                target_base_url:document.getElementById('impUseTarget').value.trim(), tool:'k6'};
    const j=await gitPost('/api/scripts/upload', body);
    currentScriptId=j.script_id; currentPlanId=j.plan_id; currentDataFileId=null;
    applyIntegrations(j.plan_id);
    document.getElementById('scriptOut').textContent=j.content;
    document.getElementById('dlBtn').disabled=false;
    document.getElementById('runBtn').disabled=(j.tool!=='k6');
    document.getElementById('preflightBtn').disabled=true;
    document.getElementById('validateBtn').disabled=false;
    document.getElementById('scriptMeta').textContent=`${j.filename} (${j.tool}) — from Git: ${gitViewed.path} @ ${gitScan.commit.slice(0,8)}`;
    const pill=document.getElementById('scriptPill'); pill.style.display='inline-flex'; pill.textContent=j.tool;
    setGitExport(false, 'Scripts loaded as-is from Git are run directly and can\'t be pushed back from here.');
    st.className='statusline ok'; st.textContent=`Loaded ${gitViewed.path}.`;
    goStep(3);
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}

/* ---------- run ---------- */

/* ---------- editable script ---------- */
let _scriptEdited=false;
let scriptEditorSourceId=null;
function toggleEditScript(){
  const pre=document.getElementById('scriptOut'); const ta=document.getElementById('scriptEdit');
  const editing = ta.style.display==='none';
  if(editing){
    scriptEditorSourceId=currentScriptId;
    document.getElementById('preflightResult').style.display='none';
    ta.value=pre.textContent; ta.style.display='block'; pre.style.display='none';
    document.getElementById('editNote').style.display='block';
    document.getElementById('editBtn').textContent='✓ Done editing';
    document.getElementById('regenBtn').style.display='inline-flex';
  } else {
    if(scriptEditorSourceId===currentScriptId){
      _scriptEdited=_scriptEdited || ta.value!==pre.textContent;
      pre.textContent=ta.value;
    }
    ta.style.display='none'; pre.style.display='block';
    document.getElementById('editNote').style.display='none';
    document.getElementById('editBtn').textContent='✏️ Edit script';
  }
}
async function regenScript(){
  // re-generate from the plan, discarding edits
  document.getElementById('scriptEdit').style.display='none';
  document.getElementById('scriptOut').style.display='block';
  document.getElementById('editNote').style.display='none';
  document.getElementById('editBtn').textContent='✏️ Edit script';
  document.getElementById('regenBtn').style.display='none';
  _scriptEdited=false;
  await doGenerate();   // existing generate flow
}
function currentScriptText(){
  const ta=document.getElementById('scriptEdit');
  return (ta.style.display!=='none' && scriptEditorSourceId===currentScriptId) ? ta.value : document.getElementById('scriptOut').textContent;
}
// Save edits as a new version of the current script.
async function ensureScriptId(){
  if(!currentScriptId) return currentScriptId;
  const output=document.getElementById('scriptOut');
  const content=currentScriptText();
  if(!_scriptEdited && content===output.textContent) return currentScriptId;
  const j=await gitPost(`/api/scripts/${currentScriptId}/edit`, {content});
  output.textContent=content;
  if(scriptEditorSourceId===currentScriptId) scriptEditorSourceId=j.script_id;
  currentScriptId=j.script_id; _scriptEdited=false;
  if(j.script_edited){
    document.getElementById('scriptMeta').textContent='Edited script · Latest version';
    loadScriptHistory();
  }
  return currentScriptId;
}

async function runScript(smoke=false){
  if(pollTimer||runStarting){showError("Wait for the active run to finish first.");return;}
  runStarting=true;
  try{
  if(!currentScriptId){showError('Generate or import a script before running.');return;}
  try{ await ensureScriptId(); }catch(e){ showError(e.message); return; }
  goStep(4);
  resetChart();
  document.getElementById('liveRunScope').textContent=smoke?'Smoke test':'Full workload';
  document.getElementById('runPill').textContent='Starting';
  document.getElementById('runPill').className='pill ghost';
  for(const id of ['mElapsed','mReqs','mRps','mErr','mP95','mP99','mActiveVus','mIterationRate','mIterations','mDroppedIterations']){
    document.getElementById(id).textContent='—';
  }
  document.getElementById('mIterationsTile').hidden=true;
  document.querySelector('#epTable tbody').replaceChildren();
  document.getElementById('runLogs').textContent='';
  document.getElementById('logCount').textContent='';
  const rs=document.getElementById('runStatus'); rs.className='statusline'; rs.textContent='Starting run…';
  try{ const av=await (await fetch('/api/run/available')).json();
    if(!av.k6){ document.getElementById('runPill').textContent='Engine unavailable'; rs.className='statusline err'; rs.textContent=av.reason||'The load engine is not available on this platform. Ask your administrator to set PERFAGENT_K6_PATH.'; return; } }catch(e){}
  try{
    const r=await fetch(`/api/scripts/${currentScriptId}/run`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({smoke,release_label:document.getElementById('releaseLabel').value,baseline_id:smoke?null:getSelectedBaseline()})}); const j=await r.json();
    if(!r.ok) throw new Error(j.detail||'run failed');
    currentRunId=j.run_id; document.getElementById('runBtn').disabled=true;
    document.getElementById('stopBtn').disabled=false; pollTimer=setInterval(pollRun,500);
  }catch(e){
    document.getElementById('runPill').textContent='Start failed';
    rs.className='statusline err'; rs.textContent='Error: '+e.message;
  }
  }finally{runStarting=false;}
}
async function pollRun(){
  const runId=currentRunId, timer=pollTimer;
  if(!runId) return;
  try{
    const response=await fetch(`/api/runs/${runId}`);
    if(!response.ok)throw new Error('Unable to refresh run status.');
    const j=await response.json();
    if(runId!==currentRunId||timer!==pollTimer)return;
    const rs=document.getElementById('runStatus'); const pill=document.getElementById('runPill');
    const updateStatus=(style,message)=>{
      rs.className=style;
      if(rs.textContent!==message)rs.textContent=message;
    };
    pill.textContent=({running:'Running',finished:'Finished',stopped:'Stopped',error:'Run error'})[j.status]||j.status; pill.className='pill '+(j.status==='running'?'pass':j.status==='finished'?'pass':j.status==='error'?'fail':'ghost');
    const s=j.snapshot||{}; const lat=s.latency||{}; window._lastSnap=s; window._lastElapsed=j.elapsed_s;
    document.getElementById('mElapsed').textContent=(j.elapsed_s??0)+'s';
    document.getElementById('mReqs').textContent=s.requests??0;
    const planned=j.planned_load||{};
    const runScope=[j.mode==='smoke'?'Smoke test':'Full workload'];
    if(j.target)runScope.push(j.target);
    if(planned.duration_seconds)runScope.push(planned.duration_seconds+' s planned');
    document.getElementById('liveRunScope').textContent=runScope.join(' · ');
    document.getElementById('mRps').textContent=(s.rps??0)+(planned.requests_per_second?' / '+planned.requests_per_second:'');
    document.getElementById('mActiveVus').textContent=(s.active_vus??'—')+' / '+(planned.peak_users??'—');
    document.getElementById('mIterationRate').textContent=(s.iterations_per_second??'—')+' / '+(planned.iterations_per_second==null?'—':formatJourneyRate(planned.iterations_per_second));
    const iterationsTile=document.getElementById('mIterationsTile');
    if(iterationsTile){
      iterationsTile.hidden=planned.iterations==null&&planned.iterations_per_second==null;
      document.getElementById('mIterations').textContent=(s.iterations??0)+(planned.iterations==null?'':' / '+planned.iterations);
      document.getElementById('mIterationsLabel').textContent=planned.iterations==null?'Iterations completed':'Iterations completed / planned';
    }
    document.getElementById('mDroppedIterations').textContent=s.dropped_iterations??'—';
    document.getElementById('mErr').textContent=((s.error_rate??0)*100).toFixed(2)+'%';
    document.getElementById('mP95').textContent=lat.samples===0||lat.p95_ms==null?'—':lat.p95_ms+' ms';
    document.getElementById('mP99').textContent=lat.samples===0||lat.p99_ms==null?'—':lat.p99_ms+' ms';
    pushChart(j.elapsed_s??0, s.rps??null, lat.samples===0?null:lat.p95_ms??null, s.error_rate??null);
    document.querySelector('#epTable tbody').innerHTML=(s.per_endpoint||[]).map(e=>
      `<tr><td>${esc(e.name)}</td><td>${esc(e.requests??'—')}</td><td>${esc(e.failed??'—')}</td><td>${esc(e.avg_ms??'—')}</td><td>${esc(e.p95_ms??'—')}</td></tr>`).join('');
    // live logs
    const logs=j.logs||[];
    if(logs.length){
      const pre=document.getElementById('runLogs');
      const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
      pre.textContent=logs.join('\n');
      document.getElementById('logCount').textContent='('+logs.length+' lines)';
      if(atBottom) pre.scrollTop=pre.scrollHeight;   // autoscroll unless user scrolled up
    }
    if(j.status==='starting'||j.status==='preparing')updateStatus('statusline',j.message||'Starting…');
    else if(j.status==='running')updateStatus('statusline',document.getElementById('stopBtn').disabled&&pollTimer?'Stopping run…':'Collecting measurements…');
    else{
      clearInterval(pollTimer); pollTimer=null;
      document.getElementById('runBtn').disabled=false; document.getElementById('stopBtn').disabled=true;
      if(j.status==='finished'){updateStatus('statusline ok','Run finished.');loadReport();}
      else if(j.status==='stopped'){updateStatus('statusline',j.message||'Run stopped.');loadReport();}
      else updateStatus('statusline err','Run error: '+(j.message||'unknown'));
    }
  }catch(e){
    if(runId!==currentRunId||timer!==pollTimer)return;
    const status=document.getElementById('runStatus');
    const message='Status update failed: '+e.message+' Retrying…';
    status.className='statusline err';
    if(status.textContent!==message)status.textContent=message;
  }
}
async function stopRun(){
  const runId=currentRunId;
  const button=document.getElementById('stopBtn');
  if(!runId||button.disabled)return;
  button.disabled=true;
  try{
    const response=await fetch(`/api/runs/${encodeURIComponent(runId)}/stop`,{method:'POST'});
    if(!response.ok)throw Error('Stop request failed.');
  }catch(error){
    if(currentRunId===runId&&pollTimer)button.disabled=false;
    showError(error.message);
  }
}

/* ---------- report ---------- */
async function loadReport(){
  if(!currentRunId) return;
  try{
    const r=await fetch(`/api/runs/${currentRunId}/report`); const j=await r.json(); if(!r.ok)throw Error(j.detail||'Report could not be loaded.');
    renderReport(j);
  }catch(e){showError(e.message+' Reopen the run from History to retry.');}
}


/* ---------- report charts: time-series + trend ---------- */
function _lineChart(canvas, series, opts={}){
  const c=canvas; if(!c) return;
  const dpr=window.devicePixelRatio||1; const W=c.clientWidth||600, H=opts.height||150;
  c.width=W*dpr; c.height=H*dpr; const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  const pad=30;
  const valid=p=>p.y!=null&&Number.isFinite(Number(p.y));
  const points=series.flatMap(s=>s.data.filter(valid));
  if(!points.length){ x.fillStyle='#5f6876'; x.font='11px system-ui'; x.fillText('No measurements recorded',10,20); return; }
  const allY=points.map(p=>p.y), allX=points.map(p=>p.x);
  const maxY=Math.max(...allY)||1;
  const [minX,maxX]=opts.domain||[Math.min(...allX),Math.max(...allX)];
  const sx=v=>pad+((v-minX)/((maxX-minX)||1))*(W-pad*1.4);
  const sy=v=>H-pad-(v/maxY)*(H-pad*1.5);
  x.font='11px Geist Variable, system-ui';
  for(let index=0;index<=3;index++){
    const value=maxY*index/3, y=sy(value);
    x.strokeStyle='#e5e9f1'; x.lineWidth=1; x.beginPath(); x.moveTo(pad,y); x.lineTo(W-6,y); x.stroke();
    x.fillStyle='#566174'; x.textAlign='right';
    x.fillText(new Intl.NumberFormat(undefined,{notation:'compact',maximumSignificantDigits:2}).format(value),pad-5,y+3);
    x.textAlign='left';
  }
  if(opts.domain){
    x.save(); x.setLineDash([4,3]); x.strokeStyle='#9586bb';
    for(const boundary of opts.boundaries||[]){
      if(boundary<=minX||boundary>=maxX) continue;
      x.beginPath(); x.moveTo(sx(boundary),8); x.lineTo(sx(boundary),H-pad); x.stroke();
    }
    x.restore();
    const labels=opts.axisLabels||[minX+' s',maxX+' s'];
    x.fillText(labels[0],pad,H-10);
    x.textAlign='right'; x.fillText(labels[1],W-6,H-10); x.textAlign='left';
    if(Number.isFinite(opts.selected)){
      x.strokeStyle='#777185'; x.beginPath(); x.moveTo(sx(opts.selected),8); x.lineTo(sx(opts.selected),H-pad); x.stroke();
    }
    if(Number.isFinite(opts.droppedAt)){
      x.strokeStyle='#a32d2d'; x.lineWidth=2;
      x.beginPath(); x.moveTo(sx(opts.droppedAt),8); x.lineTo(sx(opts.droppedAt),H-pad); x.stroke();
    }
  }
  series.forEach(s=>{
    if(s.data.length<1) return;
    x.setLineDash(s.dash||[]);
    x.beginPath(); x.strokeStyle=s.color; x.lineWidth=2;
    let drawing=false;
    s.data.forEach(p=>{
      if(!valid(p)){drawing=false;return;}
      const px=sx(p.x),py=sy(p.y); drawing?x.lineTo(px,py):x.moveTo(px,py); drawing=true;
    });
    x.stroke();
    x.setLineDash([]);
    // dots for trend (few points)
    x.fillStyle=s.color;
    s.data.filter(p=>valid(p)&&(s.data.length<=12||p.x===opts.selected)).forEach(p=>{
      x.beginPath(); x.arc(sx(p.x),sy(p.y),2.5,0,7); x.fill();
    });
  });
}
function drawTsChart(samples, phases=[], dropped=null){
  const panel=document.getElementById('reportTimelineCharts');
  if(panel){
    const timeline=samples.filter(sample=>Number.isFinite(sample.t)).sort((a,b)=>a.t-b.t);
    panel.hidden=!timeline.length;
    if(!timeline.length) return;
    const phaseNote=document.getElementById('reportPlannedPhases');
    phaseNote.hidden=!phases.length;
    phaseNote.textContent=phases.length?'Planned phases · '+phases.map(phase=>
      phase.label+' '+phase.start_s+'–'+phase.end_s+' s').join(' · '):'';
    const boundaries=phases.map(phase=>phase.end_s);
    const marker=document.getElementById('reportDropMarker');
    marker.hidden=!dropped;
    marker.textContent=dropped?'Red marker · first recorded drops at '+dropped.elapsed_s+' s ('+dropped.count+' cumulative).':'';
    const input=document.getElementById('reportSampleIndex');
    input.max=String(timeline.length-1);
    input.value=input.max;
    input.disabled=timeline.length===1;
    const domain=[0,timeline.at(-1).t];
    const readout=document.getElementById('reportSampleReadout');
    const format=(value,unit)=>Number.isFinite(value)?Number(value.toPrecision(4))+' '+unit:'Unavailable';
    const draw=()=>{
      const sample=timeline[Number(input.value)];
      readout.textContent=sample.t+' s · Throughput '+format(sample.rps,'req/s')+
        ' · p95 '+format(sample.p95,'ms')+' · Errors '+format(sample.err,'%')+
        ' · Dropped iterations '+(sample.dropped_iterations??'Unavailable');
      input.setAttribute('aria-valuetext',sample.t+' seconds');
      for(const [id,key,color] of [
        ['reportLoadChart','rps','#0f7a5f'],
        ['reportLatencyChart','p95','#6250bd'],
        ['reportErrorsChart','err','#b4342b'],
      ]){
        _lineChart(document.getElementById(id),[{data:timeline.map(item=>({x:item.t,y:item[key]})),color}],
          {domain,selected:sample.t,boundaries,droppedAt:dropped?.elapsed_s});
      }
    };
    input.oninput=draw;
    draw();
    return;
  }
  const c=document.getElementById('tsChart'); if(!c)return;
  const chartData=samples||[];
  if(!chartData.length){_lineChart(c,[]);return;}
  _lineChart(c,[
    {data:chartData.map(d=>({x:d.t,y:d.rps})),  color:'#0f7a5f'},
    {data:chartData.map(d=>({x:d.t,y:d.p95})),  color:'#9a6412'},
    {data:chartData.map(d=>({x:d.t,y:d.err||0})),color:'#b4342b'},
  ]);
}
async function loadTrend(planId){
  const c=document.getElementById('trendChart'); if(!c) return;
  try{
    const pid=planId||'';
    if(!pid){_lineChart(c,[]);document.getElementById('trendNote').textContent='No plan recorded for this report.';return;}
    const version=reportContext.workloadVersion,mode=reportContext.mode;
    const response=await fetch('/api/runs/trend?'+new URLSearchParams({limit:'10',plan_id:pid,workload_version:version,mode}));
    if(!response.ok)throw Error('Plan trend could not be loaded.');
    const j=await response.json();
    if(reportContext?.planId!==pid||reportContext.workloadVersion!==version)return;
    const pts=j.points||[];
    if(pts.length<2){ document.getElementById('trendNote').textContent='Run this plan again to see a trend across runs.'; }
    else { document.getElementById('trendNote').textContent='p95 latency (amber) · error % (red) across the last '+pts.length+' runs'; }
    _lineChart(c,[
      {data:pts.map((p,i)=>({x:i,y:p.p95_ms})),         color:'#9a6412'},
      {data:pts.map((p,i)=>({x:i,y:(p.error_rate||0)*100})), color:'#b4342b'},
    ]);
  }catch(e){_lineChart(c,[]);document.getElementById('trendNote').textContent='Trend unavailable. Reopen the report to retry.';}
}

function renderReport(j){
  reportContext={planId:j.plan_id||null,scriptId:j.script_id||null,runId:j.run_id||null,savedId:j.saved_result_id||j.run_id||null,testName:j.execution?.test_name||'',workloadVersion:j.execution?.workload_version||'',mode:j.execution?.mode||'full'};
  renderReleaseReport(j);
  renderReportDetails(j);
  renderReportEvidenceSummary(j);
  document.getElementById('rerunBtn').disabled=!reportContext.planId;
  document.getElementById('verifyRerunNotice').hidden=true;
  document.getElementById('rerunNote').textContent=reportContext.scriptId?'Opens Verify with the saved script so you can label the next run.':reportContext.planId?'Older report: opens the saved plan for review before running.':'This report has no saved plan to rerun.';
  try{
    const v=j.verdict.overall_passed;
    const hero=document.getElementById('verdictHero');
    hero.className='rpt-hero '+(v===true?'pass':v===false?'fail':'na');
    // Metrics belong to this report; older reports can have unavailable fields.
    const s=j.snapshot||{}; const lat=s.latency||{};
    const setK=(id,val)=>{const el=document.getElementById(id); if(el) el.textContent=val;};
    setK('kRequests', s.requests==null?'Unavailable':s.requests.toLocaleString());
    const er=s.error_rate==null?null:s.error_rate*100; const erEl=document.getElementById('kErr');
    if(erEl){ erEl.textContent=er==null?'Unavailable':er.toFixed(2)+'%'; erEl.classList.toggle('bad', er>0); }
    const targetRps=j.evidence?.metrics.target_rps??(j.execution?.script_edited?null:j.execution?.target_request_rate);
    setK('kRps', s.rps==null?'Unavailable':s.rps.toFixed(2)+(targetRps!=null?' / '+targetRps:'')+' req/s');
    const p95Rule=(j.verdict.checks||[]).find(check=>check.metric==='p95_ms'&&check.target!=null);
    setK('kP95',lat.p95_ms==null?'Unavailable':lat.p95_ms+' ms'+(p95Rule?' / '+p95Rule.op+' '+p95Rule.target+' ms':''));
    setK('kP99', lat.p99_ms==null?'Unavailable':lat.p99_ms+' ms');
    setK('kAvg', lat.avg_ms==null?'Unavailable':lat.avg_ms+' ms');
    const dropped=j.evidence?.first_dropped_sample;
    drawTsChart(j.samples||[],j.execution?.planned_phases||[],dropped); loadTrend(reportContext.planId);

    // run logs panel (persisted with the report)
    window._reportLogs = j.logs || (j.snapshot&&j.snapshot.logs) || [];
    const lc=document.getElementById('reportLogsCard'); const lp=document.getElementById('reportLogs');
    if(lc&&lp&&window._reportLogs.length){
      lc.style.display='block';
      lp.textContent=window._reportLogs.join('\n');
    } else if(lc){ lc.style.display='none'; }


    // response checks / assertions panel
    const chk=(j.snapshot||{}).checks||[];
    const cc=document.getElementById('checksCard'); const cb=document.getElementById('checksBody');
    if(cc&&cb&&chk.length){
      cc.style.display='block';
      const failing=chk.filter(c=>c.failed>0).length;
      const head=failing
        ? `<div class="note err" style="margin:0 0 8px">${failing} check${failing>1?'s':''} failing — check the threshold results for their effect on the verdict.</div>`
        : `<div class="note ok" style="margin:0 0 8px">All response checks passed.</div>`;
      cb.innerHTML=head+'<table><thead><tr><th>Check</th><th>Passed</th><th>Result</th></tr></thead><tbody>'+
        chk.map(c=>{
          const ok=c.failed===0;
          return `<tr><td>${esc(c.name)}</td><td>${c.passed}/${c.total}</td>`+
            `<td style="color:${ok?'#0f7a5f':'#b4342b'};font-weight:600">${ok?'✓ pass':'✗ fail'}</td></tr>`;
        }).join('')+'</tbody></table>';
    } else if(cc){ cc.style.display='none'; }

    const outcomeLabel=j.status==='stopped'?'STOPPED — partial results':j.status==='error'?'ERROR — partial results':
      v===true?'k6 PASS — all thresholds met':v===false?'k6 FAIL — a threshold was breached':'INCONCLUSIVE — no final verdict';
    document.getElementById('verdictHeadline').textContent=outcomeLabel;
    const n=j.narrative||{};
    const checks=j.verdict.checks||[];
    const total=j.evidence?.total_thresholds??checks.length;
    const passed=j.evidence?.passed_count??checks.filter(check=>check.passed===true).length;
    document.getElementById('verdictSub').textContent=total?passed+' of '+total+' thresholds passed':n.headline||'';
    document.getElementById('reportSummary').textContent=j.release_readiness?.explanation||n.summary||'No explanation was recorded for this run.';
    const dropSummary=document.getElementById('reportDropsSummary');
    const dropLink=document.getElementById('reportDropsLink');
    dropSummary.hidden=!dropped&&!(s.dropped_iterations>0);
    dropLink.textContent=dropped?'First recorded dropped iterations at '+dropped.elapsed_s+' s ('+dropped.count+' cumulative).':
      'Timing is unavailable for the dropped iterations recorded in this run.';
    dropLink.onclick=event=>{
      event.preventDefault();
      const timeline=document.getElementById('reportTimeline');
      timeline.open=true;
      timeline.querySelector('summary').focus();
      if(dropped){
        const index=[...samples].filter(sample=>Number.isFinite(sample.t)).sort((a,b)=>a.t-b.t)
          .findIndex(sample=>sample.t===dropped.elapsed_s);
        const picker=document.getElementById('reportSampleIndex');
        if(index>=0){picker.value=String(index);picker.dispatchEvent(new Event('input'));}
      }
    };
    const partial=document.getElementById('reportPartial');
    partial.hidden=!(j.evidence?.partial??(j.status&&j.status!=='finished'));
    partial.textContent=partial.hidden?'':'The run ended early. Measurements are partial.';
    const samples=j.samples||[];
    document.getElementById('reportSampleNote').textContent=samples.length
      ? samples.length+' recorded samples. Values summarize traffic observed up to each sample.'
      : 'Timeline samples are unavailable for this run.';
    document.getElementById('reportTimelineData').hidden=!samples.length;
    document.getElementById('reportSampleTable').innerHTML=samples.length?
      '<table><thead><tr><th scope="col">Elapsed (s)</th><th scope="col">p95 (ms)</th><th scope="col">Requests/s</th><th scope="col">Errors (%)</th><th scope="col">Dropped iterations (cumulative)</th></tr></thead><tbody>'+
      samples.map(sample=>'<tr>'+[sample.t,sample.p95,sample.rps,sample.err,sample.dropped_iterations].map(value=>'<td>'+esc(value??'—')+'</td>').join('')+'</tr>').join('')+
      '</tbody></table>':'';
    document.getElementById('reportObs').innerHTML=(n.observations&&n.observations.length)?'<div class="mini">Observations</div><ul>'+n.observations.map(o=>`<li>${esc(o)}</li>`).join('')+'</ul>':'';
    document.getElementById('reportRecs').innerHTML=(n.recommendations&&n.recommendations.length)?'<div class="mini">Recommendations</div><ul>'+n.recommendations.map(o=>`<li>${esc(o)}</li>`).join('')+'</ul>':'';
    // baseline / regression
    const bl=j.baseline; const blEl=document.getElementById('baseline');
    if(bl){
      blEl.style.display='block';
      if(!bl.has_previous){
        blEl.innerHTML='<div class="note info" style="margin:0">'+esc(bl.headline)+'</div>';
      } else {
        const rows=bl.deltas.map(d=>{
          const up = d.pct_change>0;
          const word={better:'better',worse:'worse',same:'same','n/a':''}[d.direction]||'';
          const glyph = d.direction==='same'||d.direction==='n/a' ? '=' : (up?'↑':'↓');
          const arrow = word ? (glyph+' '+word) : '';
          const col={better:'#085041',worse:'#b4342b',same:'#6b7280','n/a':'#6b7280'}[d.direction];
          const pct=(d.pct_change>0?'+':'')+(d.pct_change*100).toFixed(0)+'%';
          return `<tr><td>${esc(d.label)}</td><td>${esc(d.previous_fmt)}</td><td>${esc(d.current_fmt)}</td>`+
                 `<td style="color:${col};font-weight:600">${d.direction==='n/a'?'':pct+' '+arrow}</td></tr>`;
        }).join('');
        const banner = bl.regressed
          ? '<div class="note warn" style="margin:0 0 8px">⚠ '+esc(bl.headline)+'</div>'
          : '<div class="note ok" style="margin:0 0 8px">✅ '+esc(bl.headline)+'</div>';
        blEl.innerHTML=banner+
          '<table><thead><tr><th>Metric</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody>'+rows+'</tbody></table>';
      }
    } else { blEl.style.display='none'; }
    // diagnostics
    const dg=j.diagnostics; const dgEl=document.getElementById('diagnostics');
    if(dg && dg.findings && dg.findings.length){
      dgEl.style.display='block';
      dgEl.innerHTML=
        dg.findings.map(f=>{
          const emoji={high:'🔴',medium:'🟠',low:'🔵',info:'🟢'}[f.severity]||'•';
          return `<div class="finding ${f.severity}"><div class="ttl">${emoji} ${esc(f.title)} <span class="sevdot ${f.severity}">${f.severity}</span></div>`+
                 `<div>${esc(f.detail)}</div>`+
                 (f.recommendation?`<div class="rec"><b>→</b> ${esc(f.recommendation)}</div>`:'')+`</div>`;
        }).join('');
    } else { dgEl.style.display='none'; }
    const ev=j.evaluation; const el=document.getElementById('reportEval');
    if(ev){ el.style.display='flex';
      if(ev.grounded){ el.className='note ok'; el.innerHTML=`✅ Report verified — all ${ev.numbers_in_text??0} figures trace to real metrics`; }
      else{ el.className='note warn'; el.innerHTML=`⚠ ${ev.hallucinated} figure(s) could not be verified: ${(ev.unsupported||[]).join(', ')}`; } }
    else el.style.display='none';
    goStep(5);
  }catch(e){showError("Could not render the complete report: "+e.message);}
}

function downloadRunLogs(){
  const logs=window._reportLogs||[];
  if(!logs.length){ alert('No logs for this run.'); return; }
  const blob=new Blob([logs.join('\n')],{type:'text/plain'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='run_logs.txt'; a.click(); URL.revokeObjectURL(a.href);
}

function downloadReport(){const id=reportContext?.savedId;if(id)downloadArtifact('/api/runs/'+encodeURIComponent(id)+'/report/download','demo-report.html');else showError('Open a report before downloading.');}



/* ---------- AI call traces ---------- */
const tableRefreshes=new WeakMap();
function beginTableRefresh(id,scope,columns){
  const table=document.getElementById(id);
  const previous=tableRefreshes.get(table);
  if(previous?.scope===scope&&previous.busy) return null;
  const state=previous?.scope===scope?previous:{scope,signature:null};
  tableRefreshes.set(table,state);
  state.busy=true;
  table.setAttribute('aria-busy','true');
  const body=table.tBodies[0];
  if(state.signature===null) body.innerHTML=Array.from({length:3},()=>
    '<tr aria-hidden="true">'+Array.from({length:columns},()=>'<td><span class="ui-skeleton skeleton-cell"></span></td>').join('')+'</tr>').join('');
  return {
    body,
    accept(data){
      if(tableRefreshes.get(table)!==state)return false;
      const signature=JSON.stringify(data);
      const changed=signature!==state.signature;
      state.signature=signature;
      return changed;
    },
    fail(message){
      if(tableRefreshes.get(table)===state&&state.signature===null)
        body.innerHTML='<tr><td colspan="'+columns+'">'+esc(message)+'</td></tr>';
    },
    finish(){
      if(tableRefreshes.get(table)!==state)return;
      state.busy=false;
      table.removeAttribute('aria-busy');
    },
  };
}

async function loadTraces(background=false){
  const loading=beginTableRefresh('tracesTable','activity',7);
  if(!loading)return;
  try{
    const response=await fetch('/api/traces?limit=100'); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    const sc={plan:'#534ab7',chat:'#2563a8',dynamize:'#9a6412',narrate:'#0f7a5f'};
    const realTraces=(j.traces||[]).filter(t=>(t.total_tokens>0)||(t.model&&t.model.trim())||t.status==='error');
    if(!loading.accept(realTraces))return;
    loading.body.innerHTML=realTraces.map(t=>{
      const stCol=t.status==='error'?'#b4342b':'#0f7a5f';
      const stepCol=sc[t.step]||'#6b7280';
      return `<tr><td>${new Date(t.created_at).toLocaleString()}</td>`+
        `<td><b style="color:${stepCol}">${esc(t.step)}</b></td>`+
        `<td>${esc(t.model||'')}</td>`+
        `<td>${(t.total_tokens||0).toLocaleString()} <span class="muted">(${t.prompt_tokens||0}+${t.completion_tokens||0})</span></td>`+
        `<td>${t.latency_ms||0} ms</td>`+
        `<td>${t.redactions||0}</td>`+
        `<td style="color:${stCol};font-weight:600">${esc(t.status)}${t.error?' — '+esc(t.error):''}</td></tr>`;
    }).join('')||'<tr><td colspan="7" class="muted">No AI calls yet.</td></tr>';
  }catch(e){
    loading.fail('AI traces could not be loaded.');
    if(!background)showError('AI traces could not be loaded: '+e.message);
  }finally{loading.finish();}
}

/* ---------- activity log ---------- */
async function loadAudit(background=false){
  const loading=beginTableRefresh('auditTable','activity',5);
  if(!loading)return;
  if(!background)refreshUsage();
  try{
    const response=await fetch('/api/audit?limit=100'); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    const colors={'plan.created':'#2563a8','plan.approved':'#9a6412','script.generated':'#0f6e56',
      'script.downloaded':'#6b7280','run.started':'#9a6412','run.finished':'#0f6e56'};
    if(!loading.accept(j.events||[]))return;
    loading.body.innerHTML=(j.events||[]).map(e=>{
      const c=colors[e.action]||'#6b7280';
      const tok = e.tokens ? (e.tokens.toLocaleString()+' tok'+(e.cost_usd?(' · $'+e.cost_usd.toFixed(4)):'')) : '';
      return `<tr><td>${new Date(e.created_at).toLocaleString()}</td>`+
             `<td><b style="color:${c}">${esc(e.action)}</b></td>`+
             `<td>${esc(e.target||'')}</td><td>${esc(e.summary||'')}</td>`+
             `<td style="color:var(--muted);white-space:nowrap">${tok}</td></tr>`;
    }).join('')||'<tr><td colspan="5" class="muted">No activity yet.</td></tr>';
  }catch(e){
    loading.fail('Activity could not be loaded.');
    if(!background)showError('Activity could not be loaded: '+e.message);
  }finally{loading.finish();}
}

/* ---------- history ---------- */

/* ---------- stakeholder dashboard ---------- */
/* Reads /api/reporting/runs (role-scoped) and /api/reporting/trend.
   Columns shown depend on the role, so switching role visibly changes
   what that stakeholder can see. Reuses .tile/.pill/table styles. */
let dashboardRequest=0, dashboardRuns=[], reportContext=null, runStarting=false, dashboardOffset=0, dashboardFilterTimer=null;
const SD_COLS=[
  ['created_at','When'],['test_name','Test'],['script_name','Script'],['endpoint_summary','Endpoints'],['target','Target'],['verdict','Verdict'],
  ['requests','Requests'],['error_rate','Errors'],['p95_ms','p95'],['p99_ms','p99'],
  ['avg_ms','Avg'],['rps','RPS'],['environment','Environment'],['release_label','Release'],['mode','Mode'],['run_id','Run'],
];
function sdFmt(k,v){
  if(v===null||v===undefined) return '';
  if(k==='created_at') return new Date(v).toLocaleString();
  if(k==='error_rate') return (v*100).toFixed(2)+'%';
  if(k.endsWith('_ms')) return (+v).toFixed(2)+' ms';
  if(k==='rps') return (+v).toFixed(2)+'/s';
  if(k==='run_id') return String(v).slice(0,8);
  return v;
}
function sdVerdict(v){
  const m={pass:['pass','PASS'],fail:['fail','FAIL'],inconclusive:['na','INCONCLUSIVE']}[v]||['ghost',(v||'?').toUpperCase()];
  return '<span class="pill '+m[0]+'">'+m[1]+'</span>';
}
let dashboardTrend=[], dashboardOutcomeDay='';
const trendMetrics={
  p50_ms:{label:'p50 latency',unit:'ms',color:'#0f6e56'},
  p95_ms:{label:'p95 latency',unit:'ms',color:'#5545bb'},
  p99_ms:{label:'p99 latency',unit:'ms',color:'#9a6412'},
  error_rate:{label:'Error rate',unit:'%',color:'#b4342b'},
  rps:{label:'Throughput',unit:'req/s',color:'#0f6e56'},
  target_rps:{label:'Target throughput',unit:'req/s',color:'#5545bb'},
};

function dashboardTrendPoints(){
  const metric=document.getElementById('sdTrendMetric').value;
  const seriesGroup=dashboardTrend.at(-1)?.series_group;
  const comparable=document.getElementById('sdInspectRun')
    ? dashboardTrend.filter(run=>run.series_group===seriesGroup):dashboardTrend;
  const points=comparable.flatMap((run,index)=>{
    if(run[metric]==null||!Number.isFinite(Number(run[metric]))) return [];
    return [{x:index,y:Number(run[metric])*(metric==='error_rate'?100:1),run}];
  });
  return {points,count:comparable.length,...trendMetrics[metric]};
}

function renderDashboardHistoryCharts(overview, role){
  const picker=document.getElementById('sdInspectRun');
  if(!picker) return;
  const latest=dashboardTrend.at(-1);
  const comparable=dashboardTrend.filter(row=>row.series_group===latest?.series_group);
  const p95Limit=latest?.p95_limit;
  const sharedLimit=Number.isFinite(p95Limit)&&comparable.every(row=>row.p95_limit===p95Limit);
  document.getElementById('sdLatencyLegend').textContent=(role==='viewer'?'p95 purple':'p50 teal · p95 purple · p99 amber')+
    (sharedLimit?' · p95 limit '+p95Limit+' ms (gray)':'');
  document.getElementById('sdWorkloadScope').textContent=latest
    ? comparable.length+' comparable runs · '+(latest.test_name||'Latest matching workload')
    : 'No matching workload measurements.';
  picker.max=String(Math.max(0,comparable.length-1));
  picker.value=picker.max;
  picker.disabled=comparable.length<2;
  picker.oninput=()=>{
    const index=Number(picker.value), run=comparable[index];
    const note=document.getElementById('sdInspectRunNote');
    const open=document.getElementById('sdInspectReport');
    open.disabled=!run?.run_id||run.has_report===false;
    open.onclick=()=>openSavedReport(run.run_id);
    const values=[['p50_ms','p50'],['p95_ms','p95'],['p99_ms','p99'],['rps','Throughput'],['target_rps','Target'],['error_rate','Errors']];
    note.textContent=run?[run.t?new Date(run.t).toLocaleString():null,...values.map(([key,label])=>
      run[key]==null?null:label+' '+sdFmt(key==='target_rps'?'rps':key,run[key]))].filter(Boolean).join(' · '):'';
    picker.setAttribute('aria-valuetext',run?.t?new Date(run.t).toLocaleString():'No runs');
    for(const [id,metrics] of [
      ['sdLatency',[['p50_ms','#0f6e56'],['p95_ms','#5545bb'],['p99_ms','#9a6412'],
        ...(sharedLimit?[['p95_limit','#575d68']]:[])]],
      ['sdThroughput',[['rps','#0f6e56'],['target_rps','#5545bb']]],
      ['sdErrors',[['error_rate','#b4342b']]],
    ]){
      const canvas=document.getElementById(id);
      canvas.closest('figure').hidden=role==='viewer'&&id!=='sdLatency';
      _lineChart(canvas,metrics.map(([key,color])=>({
        color,data:comparable.map((item,x)=>({x,y:item[key]==null?null:item[key]*(key==='error_rate'?100:1)})),
      })),{domain:[0,Math.max(0,comparable.length-1)],selected:index,axisLabels:['Oldest','Latest']});
    }
  };
  picker.oninput();
  const outcomes=overview?.outcomes||[];
  const chart=document.getElementById('sdOutcomes');
  const keys=['pass','fail','inconclusive'];
  const dayTotal=day=>keys.reduce((sum,key)=>sum+day[key],0);
  const max=Math.max(1,...outcomes.map(dayTotal));
  chart.innerHTML=outcomes.length?'<p class="hint">Pass · Fail · Inconclusive. Select a day to filter the history.</p><div class="dashboard-outcome-scroll">'+
    outcomes.map(day=>'<button type="button" class="dashboard-outcome-bar" data-outcome-day="'+esc(day.day)+
      '" aria-label="'+esc(day.day+': '+keys.map(key=>day[key]+' '+key).join(', '))+'"><span class="dashboard-outcome-stack">'+
      keys.map(key=>'<span class="'+key+'" style="height:'+day[key]/max*100+'%"></span>').join('')+
      '</span><span>'+esc(day.day.slice(5))+'</span></button>').join('')+'</div>':'<p class="hint">No outcomes in this history.</p>';
  chart.querySelectorAll('[data-outcome-day]').forEach(button=>{
    button.onclick=()=>{
      dashboardOutcomeDay=button.dataset.outcomeDay;
      document.getElementById('sdFrom').value=dashboardOutcomeDay;
      document.getElementById('sdTo').value=dashboardOutcomeDay;
      loadStakeholder();
    };
  });
}

export function refreshDashboardTrend(){
  const {points,count,label,unit,color}=dashboardTrendPoints();
  const canvas=document.getElementById('sdTrend');
  const caption=document.getElementById('sdTrendCaption');
  canvas.setAttribute('aria-label',label+' across matching runs');
  _lineChart(canvas,[{data:points,color}],{height:canvas.clientHeight});
  const isoDate=value=>value?new Date(value).toLocaleDateString():null;
  const first=isoDate(points[0]?.run.t), last=isoDate(points.at(-1)?.run.t);
  caption.textContent=points.length
    ? points.length+' of '+count+' recent runs with measurements'+(first&&last?' · '+first+' to '+last:'')
    : 'No measurements are available for this metric in the selected history.';
  document.getElementById('sdTrendData').innerHTML=points.length?'<table><thead><tr><th scope="col">Run date</th><th scope="col">'+esc(label)+' ('+esc(unit)+')</th><th scope="col">Report</th></tr></thead><tbody>'+
    points.map(({run,y})=>'<tr><td>'+esc(run.t?new Date(run.t).toLocaleString():'Unavailable')+'</td><td>'+esc(Number(y.toFixed(2)))+'</td><td>'+
      (run.has_report===false||!run.run_id?'Unavailable':'<button class="btn ghost sm" data-trend-run="'+esc(run.run_id)+'">Open report</button>')+'</td></tr>').join('')+
    '</tbody></table>':'<p class="hint">No trend data available.</p>';
  document.querySelectorAll('[data-trend-run]').forEach(button=>{
    button.onclick=()=>openSavedReport(button.dataset.trendRun);
  });
}

export function openDashboardTrendPoint(clientX){
  const {points}=dashboardTrendPoints();
  if(!points.length) return;
  const chart=document.getElementById('sdTrend').getBoundingClientRect();
  const offset=Math.max(0,Math.min(1,(clientX-chart.left-30)/Math.max(1,chart.width-42)));
  const target=points[0].x+(points.at(-1).x-points[0].x)*offset;
  const point=points.reduce((closest,current)=>Math.abs(current.x-target)<Math.abs(closest.x-target)?current:closest);
  if(point.run.run_id&&point.run.has_report!==false) openSavedReport(point.run.run_id);
}

function renderDashboardAttention(overview){
  const release=document.getElementById('sdReleaseReadiness');
  if(release){
    const decision=overview?.release_readiness;
    release.hidden=!decision;
    release.dataset.state=decision?.status||'';
    release.innerHTML=decision?releaseDecisionMarkup(decision,'dashboardReleaseTitle')+
      '<button type="button" class="btn ghost sm">Open candidate report</button>':'';
    if(decision) release.querySelector('button').onclick=()=>openSavedReport(decision.candidate_id);
  }
  renderDashboardRegression(overview?.regression);
  const panel=document.getElementById('sdAttention');
  const run=overview?.attention||overview?.latest;
  if(!run){
    panel.innerHTML='<h3>Run to review</h3><p class="muted">No matching saved runs.</p>';
    return;
  }
  const name=run.test_name||run.script_name||'Saved run';
  const measured=[run.p95_ms!=null?'p95 '+sdFmt('p95_ms',run.p95_ms):null,
    run.rps!=null?sdFmt('rps',run.rps):null, run.error_rate!=null?'Errors '+sdFmt('error_rate',run.error_rate):null]
    .filter(Boolean).join(' · ');
  panel.innerHTML='<div><h3>'+(overview.attention?'Needs attention':'Latest matching run')+'</h3><p class="dashboard-attention-title">'+
    esc(name)+' '+sdVerdict(run.verdict)+'</p>'+(measured?'<p class="muted">'+esc(measured)+'</p>':'')+'</div>'+
    (run.has_report===false?'':'<button class="btn ghost sm">Open report</button>');
  const button=panel.querySelector('button');
  if(button) button.onclick=()=>openSavedReport(run.run_id);
}

function renderDashboardRegression(regression){
  const panel=document.getElementById('sdRegression');
  panel.hidden=!regression;
  panel.innerHTML='';
  if(!regression) return;
  const {run, baseline_id, changes}=regression;
  const name=run.test_name||run.script_name||'Saved run';
  panel.innerHTML='<div><h3>Regression in recorded run comparison</h3><p class="dashboard-attention-title">'+
    esc(name)+' '+sdVerdict(run.verdict)+'</p><ul>'+changes.map(change=>
      '<li>'+esc(change.label)+' '+esc(change.previous_fmt)+' → '+esc(change.current_fmt)+'</li>'
    ).join('')+'</ul></div><div class="btnrow"><button class="btn ghost sm">Open regressed run</button>'+
    '<button class="btn ghost sm">Open comparison reference</button></div>';
  const [current, baseline]=panel.querySelectorAll('button');
  current.onclick=()=>openSavedReport(run.run_id);
  baseline.onclick=()=>openSavedReport(baseline_id);
}

let dashboardPending=false, dashboardResultKey='', dashboardResultSignature='';
async function loadStakeholder(offset=0,background=false){
  if(!currentProject||background&&dashboardPending)return;
  const projectId=currentProject.project_id;
  const role=document.getElementById('sdRole').value;
  const head=document.getElementById('sdHead');
  const body=document.querySelector('#sdTable tbody');
  const empty=document.getElementById('sdEmpty');
  const tiles=document.getElementById('sdTiles');
  let runs=[], overview=null;
  const targetField=document.getElementById('sdTarget');
  const metadataFilters=[['environment',document.getElementById('sdEnvironment')],['release_label',document.getElementById('sdRelease')]];
  for(const [,field] of metadataFilters){
    if(!field) continue;
    field.disabled=role==='viewer';
    if(field.disabled) field.value='';
  }
  targetField.disabled=role==='viewer';
  if(targetField.disabled) targetField.value='';
  const from=document.getElementById('sdFrom').value,to=document.getElementById('sdTo').value;
  if(from&&to&&from>to){if(!background)showError('From date must be before the through date.');return;}
  const request=++dashboardRequest;
  dashboardPending=true;
  dashboardOffset=offset;
  const results=tiles.closest('.dashboard-results');
  const refreshStatus=document.getElementById('sdRefreshStatus');
  results?.setAttribute('aria-busy','true');
  const initial=!dashboardResultKey.startsWith(projectId+'|');
  if(initial){
    results?.setAttribute('data-initial-load','');
    tiles.innerHTML=Array.from({length:4},()=>'<div class="tile" aria-hidden="true"><span class="ui-skeleton skeleton-value"></span><span class="ui-skeleton skeleton-cell"></span></div>').join('');
    document.getElementById('sdPage').textContent='Loading runs…';
  }
  try{
    const query=new URLSearchParams({role,limit:'50',offset:String(offset),project_id:projectId,include_overview:'true'});
    if(document.getElementById('sdTest').value)query.set('plan_id',document.getElementById('sdTest').value);
    if(targetField.value.trim())query.set('target',targetField.value.trim());
    if(document.getElementById('sdVerdict').value)query.set('verdict',document.getElementById('sdVerdict').value);
    for(const [key,field] of metadataFilters) if(field?.value.trim()) query.set(key,field.value.trim());
    const utc=Boolean(from&&from===to&&from===dashboardOutcomeDay);
    if(from)query.set('since',new Date(from+'T00:00:00'+(utc?'Z':'')).toISOString());
    if(to){const end=new Date(to+'T00:00:00'+(utc?'Z':''));if(utc)end.setUTCDate(end.getUTCDate()+1);else end.setDate(end.getDate()+1);query.set('until',end.toISOString());}
    const response=await fetch('/api/reporting/runs?'+query);
    if(!response.ok) throw new Error('Runs could not be loaded. Please refresh to try again.');
    const j=await response.json();
    if(request!==dashboardRequest||currentProject?.project_id!==projectId)return;
    const key=projectId+'|'+query.toString(), signature=JSON.stringify(j);
    if(refreshStatus)refreshStatus.textContent='Updated '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    if(key===dashboardResultKey&&signature===dashboardResultSignature)return;
    dashboardResultKey=key;
    dashboardResultSignature=signature;
    if(background)loadProjectSummary(true);
    runs=j.runs||[];
    overview=j.overview||null;
    const total=j.total??runs.length;
    document.getElementById('sdPage').textContent=total?(offset+1)+' - '+(offset+runs.length)+' of '+total+' runs':'No matching runs';
    document.getElementById('sdPrev').disabled=offset===0;
    document.getElementById('sdNext').disabled=offset+runs.length>=total;
  }catch(e){
    if(request!==dashboardRequest||currentProject?.project_id!==projectId)return;
    if(refreshStatus)refreshStatus.textContent='Refresh failed. Retrying automatically.';
    if(!initial&&background)return;
    dashboardResultKey=''; dashboardResultSignature='';
    document.getElementById('sdPage').textContent='Could not load runs'; tiles.innerHTML='';
    document.getElementById('sdComparison').textContent='Comparison unavailable. Refresh to retry.';
    dashboardRuns=[]; empty.style.display='none'; dashboardTrend=[];
    renderDashboardHistoryCharts(null,role); refreshDashboardTrend(); renderDashboardAttention(null);
    document.getElementById('sdPrev').disabled=true;document.getElementById('sdNext').disabled=true;
    body.innerHTML='<tr><td class="muted">Could not load: '+esc(e.message)+'</td></tr>';
    return;
  }finally{
    if(request===dashboardRequest){
      dashboardPending=false;
      results?.removeAttribute('aria-busy');
      results?.removeAttribute('data-initial-load');
    }
  }

  if(request!==dashboardRequest) return;
  document.getElementById('sdFilterNote').textContent=overview
    ? 'Totals include all matching saved runs. Trends show up to 120 recent matches.'
    : 'History is paginated. Full-history summary is unavailable.';
  dashboardRuns=runs;
  populateRunComparison();
  const present = runs.length ? new Set(Object.keys(runs[0])) : new Set();
  const cols = SD_COLS.filter(([k])=>present.has(k));
  head.innerHTML = cols.map(([,l])=>'<th>'+l+'</th>').join('')+'<th>Report</th>';

  if(!runs.length){ body.innerHTML=''; empty.style.display='block'; }
  else{
    empty.style.display='none';
    body.innerHTML = runs.map(r=>'<tr>'+cols.map(([k])=>
      '<td>'+(k==='verdict'?sdVerdict(r[k]):esc(sdFmt(k,r[k])))+'</td>').join('')+
      '<td><button class="btn ghost sm" data-report-id="'+esc(r.run_id)+'" '+(r.has_report===false?'disabled':'')+'>Open report</button></td></tr>').join('');
    body.querySelectorAll('[data-report-id]').forEach(button=>{
      button.addEventListener('click',async()=>{
        button.disabled=true; button.textContent='Opening…';
        try{ await openSavedReport(button.dataset.reportId); }
        finally{ button.disabled=false; button.textContent='Open report'; }
      });
    });
  }

  const total=overview?.total??0;
  const passes=overview?.passed??0;
  const worst=overview?.worst_p95_ms;
  tiles.innerHTML=
    '<div class="tile"><div class="v">'+(overview?total.toLocaleString():'—')+'</div><div class="l">Matching runs</div></div>'+
    '<div class="tile"><div class="v">'+(total?Math.round(100*passes/total)+'%':'—')+'</div><div class="l">k6 pass rate</div></div>'+
    '<div class="tile"><div class="v">'+(overview?overview.requests.toLocaleString():'—')+'</div><div class="l">Total requests</div></div>'+
    '<div class="tile"><div class="v">'+(worst!=null?worst.toFixed(2)+' ms':'—')+'</div><div class="l">Worst p95</div></div>';

  renderDashboardAttention(overview);
  const testFilter=document.getElementById('sdTest');
  const verdictFilter=document.getElementById('sdVerdict');
  document.getElementById('sdActiveScope').textContent=[
    testFilter.value?testFilter.selectedOptions[0].textContent:'All tests',
    from&&from===to&&from===dashboardOutcomeDay?from+' (UTC)':from||to?(from||'Any start')+' to '+(to||'Today'):'All saved dates',
    verdictFilter.value?verdictFilter.selectedOptions[0].textContent:null,
    targetField.value.trim()||null,
    ...metadataFilters.map(([,field])=>field?.value.trim()),
  ].filter(Boolean).join(' · ');
  dashboardTrend=overview?.trend||[];
  renderDashboardHistoryCharts(overview,role);
  const metricPicker=document.getElementById('sdTrendMetric');
  for(const option of metricPicker.options){
    option.disabled=role==='viewer'&&option.value!=='p95_ms';
  }
  if(metricPicker.selectedOptions[0]?.disabled) metricPicker.value='p95_ms';
  refreshDashboardTrend();
}
async function sdDrawTrend(){ refreshDashboardTrend(); }

function resetDashboardFilters(){
  dashboardOutcomeDay='';
  ['sdTest','sdTarget','sdVerdict','sdFrom','sdTo','sdEnvironment','sdRelease'].forEach(id=>{
    const field=document.getElementById(id);
    if(field) field.value='';
  });
  loadStakeholder();
}
function populateRunComparison(){
  ['sdCompareA','sdCompareB'].forEach((id,index)=>{
    const el=document.getElementById(id),previous=el.value;
    el.innerHTML='<option value="">Select a run</option>'+dashboardRuns.map(r=>'<option value="'+esc(r.run_id)+'">'+esc((r.test_name||r.script_name||'Test')+' | '+(r.mode||'full')+' | '+new Date(r.created_at).toLocaleString()+' | '+r.run_id.slice(0,8))+'</option>').join('');
    el.value=dashboardRuns.some(r=>r.run_id===previous)?previous:((dashboardRuns[index]||{}).run_id||'');
  });
  renderRunComparison();
}
function renderRunComparison(){
  const host=document.getElementById('sdComparison');
  const a=dashboardRuns.find(r=>r.run_id===document.getElementById('sdCompareA').value);
  const b=dashboardRuns.find(r=>r.run_id===document.getElementById('sdCompareB').value);
  if(!a||!b||a.run_id===b.run_id){host.textContent='Select two different runs to compare.';return;}
  const metrics=[['requests','Requests'],['error_rate','Errors'],['p95_ms','p95 latency'],['p99_ms','p99 latency'],['avg_ms','Average latency'],['rps','Throughput']].filter(([k])=>k in a&&k in b);
  host.innerHTML=(a.workload_version&&b.workload_version&&a.workload_version!==b.workload_version?'<p class="note warn">Different workload versions: these runs may use different loads, thresholds or data.</p>':'')+(a.target&&b.target&&a.target!==b.target?'<p class="note warn">These runs use different targets.</p>':'')+(a.environment&&b.environment&&a.environment!==b.environment?'<p class="note warn">These runs use different environments.</p>':'')+'<table><thead><tr><th>Metric</th><th>Baseline</th><th>Comparison</th><th>Change</th></tr></thead><tbody>'+metrics.map(([k,label])=>{
    let change='Unavailable';
    if(a[k]!=null&&b[k]!=null){const delta=Number(b[k])-Number(a[k]);change=(delta>0?'+':'')+(k==='error_rate'?(delta*100).toFixed(2)+' percentage points':delta.toFixed(2)+(k.endsWith('_ms')?' ms':k==='rps'?'/s':''));}
    const relative=a[k]&&b[k]!=null?(Number(b[k])-Number(a[k]))/Math.abs(a[k])*100:null;
    return '<tr><td>'+label+'</td><td>'+esc(sdFmt(k,a[k]))+'</td><td>'+esc(sdFmt(k,b[k]))+'</td><td>'+change+
      (relative==null?'':' ('+(relative>0?'+':'')+relative.toFixed(1)+'%)')+'</td></tr>';
  }).join('')+'</tbody></table><p class="muted">Lower latency and errors are better; higher throughput is better. Compare similar load profiles.</p>';
}
async function rerunReport(){
  if(!reportContext?.planId)return;
  const context=reportContext;
  const button=document.getElementById('rerunBtn');
  const note=document.getElementById('rerunNote');
  button.disabled=true;
  try{
    if(pollTimer||runStarting)throw Error('Wait for the active run to finish before preparing another.');
    if(!context.scriptId){
      await openPlan(context.planId);
      return;
    }
    note.textContent='Loading the saved script…';
    const response=await fetch('/api/scripts/'+encodeURIComponent(context.scriptId)+'/download');
    if(!response.ok)throw Error('The original script is unavailable. Open the saved test from the project workspace.');
    const content=await response.text();
    if(reportContext!==context||!document.getElementById('panel5').classList.contains('show'))return;
    currentScriptId=context.scriptId;
    currentPlanId=context.planId;
    currentDataFileId=null;
    scriptEditorSourceId=null;
    _scriptEdited=false;
    const script=document.getElementById('scriptOut');
    script.textContent=content;
    script.style.display='block';
    document.getElementById('scriptEdit').style.display='none';
    document.getElementById('editNote').style.display='none';
    document.getElementById('regenBtn').style.display='none';
    document.getElementById('editBtn').textContent='Edit script';
    for(const id of ['runBtn','preflightBtn','validateBtn','dlBtn']){
      document.getElementById(id).disabled=false;
    }
    document.getElementById('validateResult').style.display='none';
    document.getElementById('scriptMeta').textContent='Saved script from '+(context.testName||'this report');
    const release=document.getElementById('releaseLabel');
    release.value='';
    document.getElementById('verifyRerunNotice').hidden=false;
    goStep(3);
    if(context.savedId)publishRoute(projectPath()+'/runs/'+encodeURIComponent(context.savedId)+'?rerun=1');
    release.focus({preventScroll:true});
  }catch(error){
    note.textContent=error.message;
  }finally{
    button.disabled=!reportContext?.planId;
  }
}

/* ---------- runs & reports history ---------- */
async function loadRuns(background=false){
  const projectId=currentProject?.project_id;
  const loading=beginTableRefresh('runsTable',projectId,8);
  if(!loading)return;
  try{
    const response=await fetch('/api/runs?limit=50'+projectQuery()); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    if(currentProject?.project_id!==projectId)return;
    if(!loading.accept(j.runs||[]))return;
    const badge=(v)=>{const m={pass:['pass','PASS'],fail:['fail','FAIL'],inconclusive:['na','INCONCLUSIVE']}[v]||['ghost',(v||'?').toUpperCase()];
      return '<span class="pill '+m[0]+'">'+m[1]+'</span>';};
    loading.body.innerHTML=(j.runs||[]).map(r=>
      `<tr><td>${new Date(r.created_at).toLocaleString()}</td>`+
      `<td>${badge(r.verdict)}</td>`+
      `<td>${esc(r.target||'')}</td><td><b>${esc(r.test_name||r.goal||'Unnamed test')}</b><br>${esc(r.script_name||'Not recorded')}<br><span class="muted">${esc(r.mode||'full')} | ${esc(r.endpoint_summary||'')}</span></td>`+
      `<td>${(r.requests||0).toLocaleString()}</td>`+
      `<td>${((r.error_rate||0)*100).toFixed(2)}%</td>`+
      `<td>${(r.p95_ms||0)} ms</td>`+
      `<td>${r.has_report?`<button class="btn sec sm" onclick="openSavedReport('${r.run_id}')">Open report</button>`:''}</td></tr>`
    ).join('') || '<tr><td colspan="8" class="muted">No runs yet — run a test to see it here.</td></tr>';
  }catch(e){if(currentProject?.project_id===projectId){
    loading.fail('Run history could not be loaded.');
    if(!background)showError('Run history could not be loaded: '+e.message);
  }}finally{loading.finish();}
}
async function openSavedReport(id){
  try{
    const r=await fetch(`/api/runs/${id}/saved-report`); const j=await r.json();
    if(!r.ok){ alert('Could not open report: '+(j.detail||'not found')); return; }
    renderReport({...j,saved_result_id:id});
    goStep(5);
  }catch(e){ alert('Error opening report: '+e.message); }
}

async function loadPlans(background=false){
  const project=currentProject;
  if(!project)return;
  const loading=beginTableRefresh('plansTable',project.project_id,3);
  if(!loading)return;
  const status=document.getElementById('projectTestListStatus');
  try{
  if(status&&loading.body.querySelector('.ui-skeleton')){
    status.textContent='Loading project tests…';
    renderProjectFramework(project,[]);
  }
  const response=await fetch('/api/plans?project_id='+encodeURIComponent(project.project_id));if(!response.ok)throw Error('Plans could not be loaded.');
  const j=await response.json();
  if(currentProject?.project_id!==project.project_id) return;
  if(!loading.accept([j.plans||[],project.repo_url,project.branch,project.framework_name,project.ci]))return;
  if(status){
    renderProjectTests(j.plans||[]);
    renderProjectFramework(project,j.plans||[]);
    return;
  }
  loading.body.innerHTML=j.plans.map(p=>
    `<tr class="histrow"><td>${new Date(p.created_at).toLocaleString()}</td><td>${esc(p.target)}</td>
     <td>${esc(p.goal||'')}</td><td>${p.script_count}</td>
     <td><button class="btn ghost sm" onclick="openPlan('${p.plan_id}')">Open</button></td></tr>`).join('');
  }catch(e){
    if(currentProject?.project_id!==project?.project_id)return;
    loading.fail(e.message);
    if(status&&!background) status.textContent=e.message;
    else if(!status&&!background) showError(e.message);
  }finally{loading.finish();}
}

function renderProjectTests(plans){
  const search=document.getElementById('projectTestSearch');
  const status=document.getElementById('projectTestListStatus');
  const body=document.querySelector('#plansTable tbody');
  const render=()=>{
    const query=search.value.trim().toLowerCase();
    const matches=plans.filter(plan=>[plan.test_name,plan.goal,plan.target]
      .some(value=>String(value||'').toLowerCase().includes(query)));
    status.textContent=!plans.length?'No saved tests yet. Create a test or import from Git.':
      matches.length+' of '+plans.length+' saved tests';
    body.innerHTML=matches.map(plan=>'<tr><td><strong>'+esc(plan.test_name||plan.goal||'Saved test')+
      '</strong><span class="project-test-target">'+esc(plan.target||'')+'</span>'+
      (plan.goal&&plan.goal!==plan.test_name?'<small>'+esc(plan.goal)+'</small>':'')+
      '</td><td>'+(plan.script_count?'<button class="btn ghost sm" data-version-test="'+esc(plan.plan_id)+'">View history</button>':'—')+'</td><td><button class="btn ghost sm" data-open-test="'+
      esc(plan.plan_id)+'">Open</button></td></tr>').join('');
    body.querySelectorAll('[data-open-test]').forEach(button=>button.onclick=()=>openPlan(button.dataset.openTest));
    body.querySelectorAll('[data-version-test]').forEach(button=>{
      button.onclick=async()=>{
        await openPlan(button.dataset.versionTest);
        if(currentPlanId===button.dataset.versionTest&&currentScriptId){
          const history=document.getElementById('scriptVersionHistory');
          history.open=true;
          history.querySelector('summary').focus();
        }
      };
    });
  };
  search.oninput=render;
  render();
}

function frameworkTestFolder(name){
  return (name||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
}

function renderProjectFramework(project,plans){
  document.getElementById('libraryProjectName').textContent=project.name;
  document.getElementById('libraryProjectDescription').textContent=project.description||'';
  const config=[['Repository',project.repo_url||'Set a repository in Project settings'],
    ['Branch',project.branch||'main'],['Framework folder',project.framework_name||'Configure in Project settings']];
  document.getElementById('libraryFrameworkConfig').innerHTML=config.map(([label,value])=>
    '<div><dt>'+label+'</dt><dd>'+esc(value)+'</dd></div>').join('');
  const folder=project.framework_name||'perfagent-tests';
  const tests=plans.map(plan=>{
    const test=frameworkTestFolder(plan.test_name||plan.goal).slice(0,60).replace(/-$/,'');
    return test?'<li><details><summary>'+esc(test)+'/</summary><ul><li>loadtest.js</li><li>plan.json</li><li>test.json</li></ul></details></li>':'';
  }).join('');
  const ciFiles={jenkins:'Jenkinsfile',azure:'azure-pipelines.yml',gitlab:'gitlab-ci.yml'};
  const chosen=project.ci||['jenkins'];
  const ci=chosen.filter(key=>ciFiles[key]).map(key=>'<li>'+ciFiles[key]+'</li>').join('');
  document.getElementById('libraryFrameworkTree').innerHTML='<details open><summary>'+esc(folder)+
    '/</summary><ul><li><details open><summary>tests/</summary><ul>'+(tests||'<li>No saved tests</li>')+
    '</ul></details></li><li><details><summary>scripts/</summary><ul><li>run-tests.sh</li><li>run-tests.ps1</li></ul></details></li>'+
    (ci?'<li><details><summary>ci/</summary><ul>'+ci+'</ul></details></li>':'')+
    '<li>results/</li><li>perfagent.json</li><li>README.md</li></ul></details>'+
    (chosen.includes('github')?'<p>Repository workflow · .github/workflows/perf-'+esc(folder)+'.yml</p>':'');
}
async function openPlan(id){
  document.getElementById('verifyRerunNotice').hidden=true;
  document.getElementById('importNote').style.display='none';
  applyIntegrations(id);
  const j=await (await fetch(`/api/plans/${id}`)).json();
  currentPlanId=id; planModel=j.load_model; planRationale=''; setReviewSources(j.review_sources);
  renderPlanForm(); renderRawFromModel();
  document.getElementById('guardrailBadge').style.display='none';
  document.getElementById('planEval').style.display='none';
  document.getElementById('planMeta').style.display='inline-flex';
  document.getElementById('planMeta').textContent='Saved plan';

  // If this plan already has a generated script, load the latest one so the user can
  // go straight to the Script / Run steps without regenerating.
  currentScriptId=null;
  const scripts=(j.scripts||[]).filter(script=>script.mode!=='smoke');
  if(scripts.length){
    const latest=scripts[scripts.length-1];   // most recent
    try{
      const content=await (await fetch(`/api/scripts/${latest.script_id}/download`)).text();
      currentScriptId=latest.script_id; currentDataFileId=null;
      document.getElementById('scriptOut').textContent=content;
      document.getElementById('dlBtn').disabled=false;
      document.getElementById('runBtn').disabled=(latest.tool!=='k6');
      document.getElementById('validateBtn').disabled=false;
      document.getElementById('preflightBtn').disabled=false;
      setGitExport(latest.tool==='k6' && !String(j.goal||'').startsWith('Uploaded script'), String(j.goal||'').startsWith('Uploaded script')?'Uploaded scripts can\'t be saved to Git yet — only scripts generated from a plan.':'');
      document.getElementById('scriptMeta').textContent=`${latest.filename} (${latest.tool}) · Latest script version`;
      const pill=document.getElementById('scriptPill'); pill.style.display='inline-flex'; pill.textContent=latest.tool;
    }catch(e){ /* fall back to review step */ }
  }
  // land on the Script step if a script is ready, else the Review step
  goStep(currentScriptId ? 3 : 2);
}

let scriptHistoryRequest=0;
function loadScriptHistory(){
  const panel=document.getElementById('scriptVersionHistory');
  if(!panel) return;
  const list=document.getElementById('scriptVersionList');
  const preview=document.getElementById('scriptVersionPreview');
  const planId=currentPlanId;
  if(panel.dataset.planId!==planId){
    panel.open=false;
    panel.dataset.planId=planId||'';
  }
  scriptHistoryRequest++;
  const load=async()=>{
    const request=++scriptHistoryRequest;
    list.innerHTML='<p class="hint" role="status">Loading versions…</p><div aria-hidden="true"><span class="ui-skeleton skeleton-value"></span><span class="ui-skeleton skeleton-cell"></span></div>';
    preview.hidden=true;
    preview.textContent='';
    try{
      const plan=planId?await requestJson('/api/plans/'+encodeURIComponent(planId)):null;
      if(planId!==currentPlanId||request!==scriptHistoryRequest)return;
      const versions=plan?.scripts||[];
      const full=versions.filter(script=>script.mode!=='smoke');
      const latest=full.at(-1)?.script_id;
      const render=(entries,smoke)=>entries.map((script,index)=>{
        const url='/api/scripts/'+encodeURIComponent(script.script_id)+'/download';
        const kind={generated:'Generated',edited:'Edited',imported:'Imported',saved:'Saved'}[script.source]||'Saved';
        const label=smoke?'Smoke run artifact':'Version '+(entries.length-index)+(script.script_id===latest?' · Latest':'');
        const date=script.created_at?new Date(script.created_at).toLocaleString():'Date unavailable';
        return '<li><div><strong>'+esc(label)+'</strong><span>'+esc([script.filename,kind,date].join(' · '))+
          '</span></div><div class="btnrow"><button type="button" class="btn ghost sm" data-preview-script="'+esc(url)+
          '">View script</button><a class="btn ghost sm" href="'+esc(url)+'" download>Download</a></div></li>';
      }).join('');
      list.innerHTML=full.length?'<ol class="script-versions">'+render([...full].reverse(),false)+'</ol>':'<p>No saved script versions.</p>';
      const smoke=versions.filter(script=>script.mode==='smoke');
      if(smoke.length) list.innerHTML+='<details><summary>Smoke run artifacts ('+smoke.length+
        ')</summary><ul class="script-versions">'+render(smoke.reverse(),true)+'</ul></details>';
      list.querySelectorAll('[data-preview-script]').forEach(button=>button.onclick=async()=>{
        const selection=++scriptHistoryRequest;
        preview.hidden=false;
        preview.textContent='Loading script…';
        try{
          const response=await fetch(button.dataset.previewScript);
          if(!response.ok) throw Error('This script could not be loaded.');
          const content=await response.text();
          if(planId===currentPlanId&&selection===scriptHistoryRequest) preview.textContent=content;
        }catch(e){
          if(planId===currentPlanId&&selection===scriptHistoryRequest) preview.textContent=e.message;
        }
      });
    }catch(e){if(planId===currentPlanId&&request===scriptHistoryRequest) list.textContent=e.message;}
  };
  panel.ontoggle=()=>{if(panel.open) load();};
  if(panel.open) load();
}



/* ---------- import endpoints ---------- */
async function importEndpoints(){
  const input=document.getElementById('importFile'); const info=document.getElementById('importInfo');
  if(!input.files||!input.files.length) return;
  const fd=new FormData(); fd.append('file',input.files[0]);
  info.style.display='flex'; info.className='note info'; info.textContent='Importing…';
  try{
    const r=await fetch('/api/import-endpoints',{method:'POST',body:fd});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'import failed');
    // set target if we found one
    if(j.base_url){ document.getElementById('target').value=j.base_url; }
    // clear existing endpoints and add imported
    document.getElementById('endpoints').innerHTML='';
    (j.endpoints||[]).forEach(e=>addEndpoint(e.method, e.path, e.example_body?JSON.stringify(e.example_body):''));
    info.className='note ok';
    let msg=`📥 Imported <b>${j.endpoints.length}</b> endpoints from ${j.source}`;
    if(j.base_url) msg+=` · target set to <code class="k">${esc(j.base_url)}</code>`;
    if(j.warnings&&j.warnings.length) msg+=`<br><span class="muted">${j.warnings.join('; ')}</span>`;
    info.innerHTML=msg;
    document.getElementById('impdz').innerHTML='📥 '+input.files[0].name+' — click to re-import';
  }catch(e){ info.className='note err'; info.textContent='Import error: '+e.message; }
}

/* ---------- custom headers ---------- */
function addHeader(k="",v=""){
  const d=document.createElement('div'); d.className='endpoint'; d.style.gridTemplateColumns='1fr 1.3fr 34px';
  d.innerHTML=`<input aria-label="Header name" placeholder="Header name e.g. Authorization" value="${esc(k)}"/>
    <input aria-label="Header value" type="password" placeholder="Header value" value="${esc(v)}"/>
    <button class="iconbtn" onclick="this.parentElement.remove();renderConnCount()">×</button>`;
  d.addEventListener('change',renderConnCount);
  d.addEventListener('input',renderSummary);
  document.getElementById('headersList').appendChild(d);
  if(planModel) renderConnCount();
}
function readHeaders(){
  const out={};
  document.querySelectorAll('#headersList .endpoint').forEach(d=>{
    const ins=d.querySelectorAll('input'); const k=ins[0].value.trim(); const v=ins[1].value.trim();
    if(k) out[k]=v;
  });
  return out;
}





/* ---------- run an existing script ---------- */
function loadExistingFile(){
  const f=document.getElementById('exFile').files[0]; if(!f) return;
  const r=new FileReader();
  r.onload=()=>{ document.getElementById('exContent').value=r.result; };
  r.readAsText(f);
  const el=document.getElementById('exFileName');
  if(el) el.innerHTML='Loaded <b>'+f.name+'</b> — or edit below';
}
async function uploadExisting(){
  const st=document.getElementById('exStatus');
  const content=document.getElementById('exContent').value.trim();
  if(!content){ st.className='statusline err'; st.textContent='Paste or choose a script first.'; return; }
  st.className='statusline'; st.textContent='Uploading…';
  try{
    if(!currentProject){showError('Open a project before importing a script.');return;}
    const body={project_id:currentProject.project_id,filename:(document.getElementById('exFile').files[0]||{}).name||'loadtest.js',
                test_name:document.getElementById('exTestName').value.trim(),
                content, target_base_url:document.getElementById('exTarget').value.trim(), tool:'k6'};
    if(!document.getElementById('exFile').files.length&&body.test_name){body.filename=(body.test_name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,100)||'test')+'.js';}
    const r=await fetch('/api/scripts/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'upload failed');
    currentScriptId=j.script_id; currentPlanId=j.plan_id; currentDataFileId=null;
    applyIntegrations(j.plan_id);
    document.getElementById('scriptOut').textContent=j.content;
    document.getElementById('dlBtn').disabled=false;
    document.getElementById('runBtn').disabled=(j.tool!=='k6');
    document.getElementById('preflightBtn').disabled=true;   // no plan endpoints to pre-flight
    setGitExport(false, 'Uploaded scripts can\'t be saved to Git yet — only scripts generated from a plan.');
    document.getElementById('validateBtn').disabled=false;
    document.getElementById('scriptMeta').textContent=`${j.filename} (${j.tool}) — uploaded`;
    const pill=document.getElementById('scriptPill'); pill.style.display='inline-flex'; pill.textContent=j.tool;
    st.className='statusline ok'; st.textContent='Uploaded. Go to the Script step to validate & run.';
    goStep(3);
  }catch(e){ st.className='statusline err'; st.textContent='Error: '+e.message; }
}

/* ---------- validate script (syntax/configuration; no traffic) ---------- */
async function doValidate(){
  const el=document.getElementById('validateResult'); el.style.display='flex'; el.className='note info';
  el.textContent='Validating the script… (the very first time, this also sets up the load engine and can take a little longer)';
  try{
    await ensureScriptId();
    if(!currentScriptId) throw new Error('Generate or import a script first.');
    const r=await fetch(`/api/scripts/${currentScriptId}/validate`,{method:'POST'});
    const j=await r.json();
    if(!r.ok) throw new Error(j.detail||j.message||'Script validation failed');
    if(j.ok){
      el.className='note ok';
      el.innerHTML='✅ <b>Script validation passed</b> — syntax and configuration checked without sending traffic. Use Verify test to exercise the configured journeys.';
    } else if(j.status==='k6_missing'){
      el.className='note warn'; el.textContent='⚠ '+j.message;
    } else {
      el.className='note err';
      el.innerHTML='🔴 <b>Script failed validation</b> — fix this before a full run:<br><pre style="margin:6px 0 0;max-height:160px;font-size:11px">'+esc(j.detail||j.message)+'</pre>';
    }
  }catch(e){ el.className='note err'; el.textContent='Validation error: '+e.message; }
}

async function loadSavedVerification(scriptId, el){
  try{
    const response=await fetch('/api/scripts/'+encodeURIComponent(scriptId)+'/readiness');
    if(!response.ok) return;
    const {verification}=await response.json();
    if(!verification || currentScriptId!==scriptId || _scriptEdited ||
      el.dataset.scriptId===scriptId || document.getElementById('preflightBtn').disabled ||
      currentScriptText()!==document.getElementById('scriptOut').textContent) return;
    el.dataset.scriptId=scriptId;
    el.style.display='flex';
    el.className=verification.all_ok?'note ok':'note warn';
    const date=new Date(verification.verified_at*1000).toLocaleString();
    const count=verification.journeys_checked;
    el.textContent=(verification.all_ok?'Verification passed':'Verification needs review')+
      ' · '+count+(count===1?' journey':' journeys')+' · '+date;
  }catch(e){
    // A saved result is optional. The Verify test action remains available.
  }
}

/* ---------- pre-flight check ---------- */
async function doPreflight(){
  const button=document.getElementById('preflightBtn');
  if(button.disabled) return;
  button.disabled=true;
  let scriptId=currentScriptId;
  const el=document.getElementById('preflightResult'); el.style.display='flex'; el.className='note info';
  el.textContent='Verifying test…';
  try{
    await ensureScriptId();
    if(!currentScriptId) throw new Error('Generate or import a script first.');
    scriptId=currentScriptId;
    const payload={script_id:scriptId};
    const r=await fetch('/api/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'preflight failed');
    if(scriptId!==currentScriptId || _scriptEdited || currentScriptText()!==document.getElementById('scriptOut').textContent){
      el.textContent='The script changed. Verify the current version.';
      return;
    }
    el.dataset.scriptId=scriptId;
    if(j.mode==='script'){
      const verifiedAt=j.verified_at?new Date(j.verified_at*1000).toLocaleString():'';
      el.className=j.all_ok?'note ok':'note warn';
      el.innerHTML='<div><strong>'+esc(j.message)+'</strong>'+(verifiedAt?'<p>'+esc(verifiedAt)+'</p>':'')+j.journeys.map(journey=>{
        const requests=journey.requests.map((request,index)=>
          '<li>'+esc((request.method||'Request')+' '+(index+1)+' · '+(request.status||'No HTTP response'))+'</li>');
        const checks=journey.checks.map(check=>'<li>'+esc(check.name)+' · '+(check.ok?'Passed':'Failed')+'</li>');
        return '<details'+(journey.ok?'':' open')+'><summary>'+esc(journey.name.replaceAll('_',' '))+' · '+
          (journey.ok?'Passed':'Needs review')+'</summary>'+
          (journey.completed?'':'<p>Journey did not complete.</p>')+
          '<ul>'+requests.concat(checks).join('')+'</ul></details>';
      }).join('')+'</div>';
      return;
    }
    const rows=j.results.map(x=>{
      const dot = x.ok ? '🟢' : '🔴';
      const status = [x.status, x.error].filter(Boolean).join(' · ') || 'no response';
      return `${dot} <b>${esc(x.method)}</b> ${esc(x.path)} → ${esc(status)}`;
    }).join('<br>');
    el.className = j.all_ok ? 'note ok' : 'note warn';
    el.innerHTML = `<div><b>Pre-flight: ${j.ok}/${j.total} endpoints responded OK</b>` +
      (j.all_ok ? ' — endpoint requests succeeded; review authentication and response checks before running.' : ' — check the failures below before a full run.') +
      `<div style="margin-top:6px">${rows}</div></div>`;
  }catch(e){ el.className='note err'; el.textContent='Verification error: '+e.message; }
  finally{ if(currentScriptId===scriptId) button.disabled=false; }
}

/* ---------- live chart ---------- */
let chartData=[];
function resetChart(){ chartData=[]; drawChart(); }
function pushChart(elapsed, rps, p95, err){
  chartData.push({t:elapsed,rps,p95,err:err==null?null:err*100});
  if(chartData.length>300)chartData.shift();
  drawChart();
}
export function drawChart(){
  const canvas=document.getElementById('liveChart');
  if(!canvas||!canvas.clientWidth)return;
  const key=document.getElementById('liveMetric').value;
  const [label,unit]={
    rps:['Throughput','req/s'],p95:['p95 latency','ms'],err:['Error rate','%'],
  }[key];
  const data=chartData.map(sample=>({x:sample.t,y:sample[key]}));
  const last=data.at(-1);
  canvas.setAttribute('aria-label',label+' over elapsed time');
  document.getElementById('liveChartReading').textContent=last?.y==null?
    'Waiting for a measurement.':releaseNumber(last.y,unit)+' at '+last.x+' s';
  _lineChart(canvas,[{data,color:'#3448bb'}],{height:canvas.clientHeight,
    domain:[data[0]?.x||0,last?.x||0]});
}

/* ---------- sidebar navigation ---------- */
const VIEW_META={
  home:['Home','Plan, verify, and compare performance tests'],
  projects:['Projects','Create a project, open its test library, or import an existing Git framework'],
  admin:['Administrator overview','Run and workload summaries across every project'],
  create:['Test workspace','Describe, review, verify, and run your workload.'],
  dashboard:['Performance dashboard','Review workload trends, verdicts, and run comparisons.'],
  history:['Project workspace','Manage this project’s tests, Git framework, and reports.'],
  monitoring:['Monitoring','Your Grafana, Datadog and other dashboards in one place'],
  activity:['Activity','Audit log and AI call traces'],
};
export function openHomeAction(action){
  if(!currentProject){
    showView('projects');
    document.getElementById('projectSearch')?.focus();
    return;
  }
  if(action==='create')showNewTestForm();
  else if(action==='import')startProjectImport('script');
  else if(action==='dashboard')showView('dashboard');
}
function markNavigation(view){
  document.querySelectorAll('.sb-item').forEach(button=>{
    const active=button.dataset.view===view;
    button.classList.toggle('active',active);
    if(active) button.setAttribute('aria-current','page');
    else button.removeAttribute('aria-current');
  });
}
export function showView(v){
  if(['dashboard','history'].includes(v)&&!currentProject){showError('Open a project first.');v='projects';}
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('show', s.id==='view-'+v));
  markNavigation(v);
  const m=VIEW_META[v]||VIEW_META.create;
  document.getElementById('viewTitle').textContent=m[0];
  document.getElementById('viewSub').textContent=m[1];
  if(v==='projects')loadProjects();
  if(v==='dashboard'){loadProjectSummary();loadDashboardTests();loadStakeholder();}
  if(v==='history'){ loadPlans(); loadRuns(); }
  if(v==='activity'){ loadAudit(); loadTraces(); }
  if(v==='monitoring') monRender();
  closeMobNav();
  if(document.documentElement.dataset.tour!=='true')window.scrollTo({top:0,behavior:'smooth'});

publishView(v);
}

let workspaceRefreshTimer=null;
function refreshVisibleWorkspace(){
  if(document.hidden)return;
  const view=document.querySelector('.view.show');
  const focused=document.activeElement;
  if(!view||view.contains(focused)&&focused.matches('input,select,textarea,button,a,summary,[tabindex]'))return;
  if(view.id==='view-dashboard'&&currentProject){
    loadStakeholder(dashboardOffset,true);
  }else if(view.id==='view-history'&&currentProject){
    loadPlans(true);
    if(document.querySelector('.project-reports')?.open)loadRuns(true);
  }else if(view.id==='view-activity'){
    loadAudit(true);
    loadTraces(true);
  }
}
function toggleSidebar(){
  const sidebar=document.getElementById('sidebar');
  const collapsed=sidebar.classList.toggle('collapsed');
  const toggle=sidebar.querySelector('.sb-toggle');
  toggle.setAttribute('aria-expanded',String(!collapsed));
  toggle.setAttribute('aria-label',collapsed?'Expand sidebar':'Collapse sidebar');
  toggle.title=collapsed?'Expand sidebar':'Collapse sidebar';
  try{ localStorage.setItem('perfagent.sidebarCollapsed',String(collapsed)); }catch(e){}
  sidebar.querySelectorAll('.sb-item').forEach(item=>{
    if(collapsed) item.title=item.querySelector('.sb-lbl').textContent;
    else item.removeAttribute('title');
  });
}
function openMobNav(){
  document.getElementById('sidebar').classList.add('mobopen');
  document.getElementById('sbBackdrop').classList.add('show');
  document.getElementById('mobileNavButton').setAttribute('aria-expanded','true');
  document.querySelector('.sb-mobile-close').focus();
}
function closeMobNav(){
  const wasOpen=document.getElementById('sidebar').classList.contains('mobopen');
  document.getElementById('sidebar').classList.remove('mobopen');
  document.getElementById('sbBackdrop').classList.remove('show');
  const toggle=document.getElementById('mobileNavButton');
  toggle.setAttribute('aria-expanded','false');
  if(wasOpen) toggle.focus();
}

/* ---------- monitoring tools (Grafana / Datadog / etc) ---------- */
const MON_KEY='perfagent.monitors';
function monitoringUrl(value){
  try{
    const url=new URL(value);
    if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return null;
    return url;
  }catch{return null;}
}
function monLoad(){
  try{
    const saved=JSON.parse(localStorage.getItem(MON_KEY)||'[]');
    return Array.isArray(saved)?saved.filter(item=>typeof item?.tool==='string'&&monitoringUrl(item.url)):[];
  }catch{return [];}
}
function monSave(dashboards){localStorage.setItem(MON_KEY,JSON.stringify(dashboards));}
export function monAdd(){
  const tool=document.getElementById('monTool').value;
  const field=document.getElementById('monUrl');
  const url=monitoringUrl(field.value.trim());
  const status=document.getElementById('monStatus');
  status.className='statusline err';
  if(!url){status.textContent='Enter a full HTTP or HTTPS URL without embedded credentials.';return;}
  const saved=monLoad();
  if(saved.some(item=>new URL(item.url).href===url.href)){status.textContent='This dashboard is already linked.';return;}
  try{monSave([...saved,{tool,url:url.href}]);}
  catch{status.textContent='Browser storage is unavailable. The dashboard could not be saved.';return;}
  field.value='';
  status.className='statusline ok';
  status.textContent=tool+' dashboard linked.';
  monRender();
}
function monRemove(index){
  const saved=monLoad();
  const status=document.getElementById('monStatus');
  try{monSave(saved.filter((_,position)=>position!==index));}
  catch{status.className='statusline err';status.textContent='The saved dashboard could not be removed.';return;}
  status.className='statusline';
  status.textContent='Dashboard removed.';
  monRender();
  document.getElementById('monUrl').focus();
}
function monRender(){
  const host=document.getElementById('monList');
  if(!host)return;
  const saved=monLoad();
  host.innerHTML=saved.map(({tool,url},index)=>`
    <article class="monitor-card">
      <div class="monitor-head">
        <div><h4>${esc(tool)}</h4><p class="url">${esc(new URL(url).host)}</p></div>
        <div class="btnrow">
          <button type="button" class="btn ghost sm" data-monitor-preview="${index}">Preview</button>
          <a class="btn ghost sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open in new tab</a>
          <button type="button" class="btn ghost sm" data-monitor-remove="${index}">Remove</button>
        </div>
      </div>
      <div class="monitor-preview" hidden></div>
    </article>`).join('')||'<div class="monitor-empty"><strong>No dashboards linked</strong><p>Add your first monitoring dashboard to open it from this workspace.</p></div>';
  host.querySelectorAll('[data-monitor-remove]').forEach(button=>{
    button.onclick=()=>monRemove(Number(button.dataset.monitorRemove));
  });
  host.querySelectorAll('[data-monitor-preview]').forEach(button=>{
    const preview=button.closest('article').querySelector('.monitor-preview');
    button.setAttribute('aria-expanded','false');
    button.onclick=()=>{
      const open=preview.hidden;
      preview.hidden=!open;
      button.textContent=open?'Close preview':'Preview';
      button.setAttribute('aria-expanded',String(open));
      preview.replaceChildren();
      if(!open)return;
      const {tool,url}=saved[Number(button.dataset.monitorPreview)];
      const frame=document.createElement('iframe');
      frame.className='monitor-frame';
      frame.title=tool+' dashboard preview';
      frame.referrerPolicy='no-referrer';
      frame.sandbox.add('allow-scripts');
      frame.src=url;
      const notice=document.createElement('p');
      notice.className='hint';
      notice.textContent='If the dashboard requires sign-in or blocks previews, open it in a new tab.';
      preview.append(notice,frame);
    };
  });
}

/* ---------- extra dashboard charts (donut, bars, error trend) ---------- */
function _donut(canvas, segs){
  const c=canvas; if(!c) return;
  const dpr=window.devicePixelRatio||1, W=c.clientWidth||300, H=140;
  c.width=W*dpr; c.height=H*dpr; const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  const total=segs.reduce((a,s)=>a+s.v,0);
  if(!total){ x.fillStyle='#9aa'; x.font='11px system-ui'; x.fillText('no runs yet',10,20); return; }
  const cx=70, cy=H/2, r=48, rin=28; let ang=-Math.PI/2;
  segs.forEach(s=>{ if(!s.v) return; const a2=ang+(s.v/total)*Math.PI*2;
    x.beginPath(); x.moveTo(cx,cy); x.arc(cx,cy,r,ang,a2); x.closePath(); x.fillStyle=s.c; x.fill(); ang=a2; });
  x.beginPath(); x.arc(cx,cy,rin,0,Math.PI*2); x.fillStyle='#fff'; x.fill();
  x.fillStyle='#16201c'; x.font='700 15px system-ui'; x.textAlign='center'; x.fillText(total, cx, cy+5); x.textAlign='left';
  let ly=20; segs.forEach(s=>{
    x.fillStyle=s.c; x.fillRect(150, ly-9, 10, 10);
    x.fillStyle='#16201c'; x.font='11px system-ui'; x.fillText(s.l+'  '+s.v, 166, ly); ly+=18; });
}
function _bars(canvas, bars){
  const c=canvas; if(!c) return;
  const dpr=window.devicePixelRatio||1, W=c.clientWidth||300, H=140;
  c.width=W*dpr; c.height=H*dpr; const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  const max=Math.max(1,...bars.map(b=>b.v)); const pad=28, bw=(W-pad*2)/bars.length*0.6, gap=(W-pad*2)/bars.length;
  bars.forEach((b,i)=>{ const h=(b.v/max)*(H-pad*1.6); const bx=pad+i*gap+(gap-bw)/2, by=H-pad-h;
    x.fillStyle=b.c||'#0f7a5f'; x.fillRect(bx,by,bw,h);
    x.fillStyle='#16201c'; x.font='700 11px system-ui'; x.textAlign='center'; x.fillText(b.v!=null?(+b.v).toFixed(0):'—', bx+bw/2, by-5);
    x.fillStyle='#6a7570'; x.font='10px system-ui'; x.fillText(b.l, bx+bw/2, H-10); x.textAlign='left'; });
}

function projectQuery(){return currentProject?'&project_id='+encodeURIComponent(currentProject.project_id):'';}
function projectGitDefaults(){
  return currentProject?{repo_url:currentProject.repo_url||'',branch:currentProject.branch||'main',framework:currentProject.framework_name||'',ci:currentProject.ci||['jenkins'],test:frameworkTestFolder(planModel?.test_name||newTestName)}:{};
}
async function projectApi(url,options){
  return requestJson(url,options);
}
export function filterProjects(){
  const query=document.getElementById('projectSearch').value.trim().toLowerCase();
  const cards=[...document.querySelectorAll('#projectCards .project-card')];
  let matches=0;
  for(const card of cards){
    card.hidden=!card.textContent.toLowerCase().includes(query);
    if(!card.hidden)matches++;
  }
  const status=document.getElementById('projectSearchStatus');
  status.hidden=!query||!cards.length;
  status.textContent=matches?matches+' matching '+(matches===1?'project':'projects'):'No matching projects.';
}
async function loadProjects(){
  const cards=document.getElementById('projectCards');
  if(!cards.childElementCount){
    cards.setAttribute('aria-busy','true');
    cards.innerHTML=Array.from({length:3},()=>'<div class="card project-skeleton" aria-hidden="true"><span class="ui-skeleton skeleton-value"></span><span class="ui-skeleton skeleton-cell"></span><span class="ui-skeleton skeleton-cell"></span></div>').join('');
  }
  try{
    const j=await projectApi('/api/projects');projects=j.projects||[];
    if(currentProject)currentProject=projects.find(p=>p.project_id===currentProject.project_id)||null;
    document.getElementById('projectPicker').innerHTML='<option value="">Select project</option>'+projects.map(p=>'<option value="'+esc(p.project_id)+'">'+esc(p.name)+'</option>').join('');
    document.getElementById('projectPicker').value=currentProject?.project_id||'';
    cards.innerHTML=projects.map(p=>{
      const initials=p.name.trim().split(/\s+/).slice(0,2).map(word=>word[0]).join('').toUpperCase();
      return '<article class="card project-card"><div class="project-card-mark" aria-hidden="true">'+esc(initials)+'</div>'+
        '<h3>'+esc(p.name)+'</h3>'+(p.description?'<p>'+esc(p.description)+'</p>':'')+
        '<dl class="project-card-meta"><div><dt>Tests</dt><dd>'+esc(p.tests??0)+'</dd></div>'+
        '<div><dt>Environment</dt><dd>'+esc(p.environment||'Unset')+'</dd></div></dl>'+
        '<button class="btn ghost" data-project-id="'+esc(p.project_id)+'">Open project <span aria-hidden="true">→</span></button></article>';
    }).join('')||'<div class="card"><p>No projects yet. Create a project or import a framework to get started.</p></div>';
    document.querySelectorAll('#projectCards [data-project-id]').forEach(button=>button.onclick=()=>selectProject(button.dataset.projectId));
    filterProjects();
    renderProjectContext();
  }catch(e){
    if(cards.querySelector('.project-skeleton')) cards.innerHTML='<p>Projects could not be loaded. Reopen Projects to retry.</p>';
    showError(e.message);
  }finally{cards.removeAttribute('aria-busy');}
}
function renderProjectContext(){
  document.getElementById('activeProject').style.display=currentProject?'block':'none';
  document.getElementById('activeProjectName').textContent=currentProject?.name||'';
  document.getElementById('activeProjectDescription').textContent=currentProject?.description||'';
  document.getElementById('testProjectContext').textContent=currentProject?'Project: '+currentProject.name:'Open a project to organize this test.';
}
function selectProject(id){
  if(pollTimer||convBusy||document.getElementById('planBtn').disabled){showError('A test is running or planning. Wait for it to finish before switching project.');return;}
  currentProject=projects.find(p=>p.project_id===id)||null;
  document.getElementById('projectPicker').value=currentProject?.project_id||'';
  currentPlanId=null;currentScriptId=null;planModel=null;newTestName='';
  document.getElementById('newTestForm').style.display='none';
  const search=document.getElementById('projectTestSearch');
  if(search) search.value='';
  renderProjectContext();showView(currentProject&&search?'history':'projects');
}
function editProject(project=null){
  editingProjectId=project?.project_id||null;showView('projects');
  document.getElementById('projectForm').style.display='block';
  document.getElementById('projectFormTitle').textContent=project?'Project settings':'Create project';
  const fields={projectName:'name',projectDescription:'description',projectTarget:'target_url',projectEnvironment:'environment',projectRepo:'repo_url',projectBranch:'branch',projectFramework:'framework_name'};
  Object.entries(fields).forEach(([id,key])=>document.getElementById(id).value=project?.[key]??({environment:'staging',branch:'main'}[key]||''));
  document.querySelectorAll('.projectCi').forEach(c=>c.checked=(project?.ci||['jenkins']).includes(c.value));
  document.getElementById('projectSaveStatus').textContent='';

publishRoute(project ? '/projects/' + encodeURIComponent(project.project_id) + '/settings' : '/projects/new');
}
function beginFrameworkImport(){importAfterProject=true;editProject();document.getElementById('projectFormTitle').textContent='Create a project for your Git framework';}
async function saveProject(){
  const status=document.getElementById('projectSaveStatus');status.textContent='Saving project…';
  try{
    const body={name:document.getElementById('projectName').value.trim(),description:document.getElementById('projectDescription').value.trim(),target_url:document.getElementById('projectTarget').value.trim(),environment:document.getElementById('projectEnvironment').value.trim(),repo_url:document.getElementById('projectRepo').value.trim(),branch:document.getElementById('projectBranch').value.trim()||'main',framework_name:document.getElementById('projectFramework').value.trim(),ci:[...document.querySelectorAll('.projectCi:checked')].map(c=>c.value)};
    if(!body.name)throw Error('Enter a project name.');
    currentProject=await projectApi('/api/projects'+(editingProjectId?'/'+editingProjectId:''),{method:editingProjectId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    document.getElementById('projectForm').style.display='none';await loadProjects();
    if(importAfterProject){importAfterProject=false;startProjectImport('git');}
  }catch(e){status.textContent=e.message;}

if(currentProject && document.getElementById('view-projects').classList.contains('show') && document.getElementById('projectForm').style.display==='none') publishRoute('/projects/' + encodeURIComponent(currentProject.project_id));
}
function showNewTestForm(){
  if(!currentProject){showError('Create or open a project first.');showView('projects');return;}
  showView('projects');document.getElementById('newTestForm').style.display='block';
  document.getElementById('newTestName').focus();

if(currentProject) publishRoute('/projects/' + encodeURIComponent(currentProject.project_id) + '/tests/new');
}
function startNamedTest(){
  document.getElementById('verifyRerunNotice').hidden=true;
  if(!currentProject)return;
  const name=document.getElementById('newTestName').value.trim();if(!name){showError('Give this test a name first.');return;}
  if(pollTimer){showError('Wait for the current run to finish before creating another test.');return;}
  convNew();newTestName=name;currentPlanId=null;currentScriptId=null;planModel=null;currentDataFileId=null;_scriptEdited=false;
  document.getElementById('target').value=currentProject.target_url||'';
  document.getElementById('draftP95').value='';
  document.getElementById('draftErrorRate').value='';
  window.dispatchEvent(new Event('perfagent:reset-traffic'));
  delete document.getElementById('draftRequestRate').dataset.trafficRate;
  document.getElementById('draftSchedule').value='users';
  for(const id of ['draftRequestRate','draftJourneyRate','draftRampUp','draftHold','draftRampDown']) document.getElementById(id).value='';
  document.getElementById('endpoints').replaceChildren();
  addEndpoint();
  document.getElementById('goal').value=document.getElementById('newTestPurpose').value.trim();
  document.querySelector('#panel1 > .card > h2').textContent=name+' — choose how to build the test';
  document.querySelector('#panel1 .modeswitch').style.display='inline-flex';
  document.getElementById('modeScriptBtn').style.display='none';document.getElementById('modeGitBtn').style.display='none';
  setMode('manual');goStep(1);
}
function startProjectImport(mode){
  if(!currentProject){showError('Create or open the destination project first.');showView('projects');return;}
  if(pollTimer){showError('Wait for the current run to finish before importing a test.');return;}
  newTestName='';currentPlanId=null;currentScriptId=null;planModel=null;currentDataFileId=null;_scriptEdited=false;
  document.querySelector('#panel1 > .card > h2').textContent=mode==='script'?'Import an existing script':'Import or synchronize a Git framework';
  document.querySelector('#panel1 .modeswitch').style.display='none';
  if(mode==='script')document.getElementById('exTarget').value=currentProject.target_url||'http://127.0.0.1:8000';
  else{document.getElementById('impRepo').value=currentProject.repo_url||'';document.getElementById('impBranch').value=currentProject.branch||'main';}
  setMode(mode);goStep(1);

publishRoute('/projects/' + encodeURIComponent(currentProject.project_id) + '/import/' + mode);
}
async function attachCurrentTest(id,projectId,name){
  return projectApi('/api/plans/'+id+'/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:projectId,test_name:name})});
}
async function loadProjectSummary(background=false){
  const project=currentProject;
  if(!project)return;
  const summary=document.getElementById('projectDashboardSummary');
  if(summary.dataset.projectId!==project.project_id)summary.textContent='';
  summary.dataset.projectId=project.project_id;
  try{const j=await projectApi('/api/projects/'+project.project_id+'/dashboard'),s=j.summary;
    if(currentProject?.project_id===project.project_id)summary.textContent=project.name+' · '+s.tests+' tests · '+s.runs+' runs · '+Number(s.requests).toLocaleString()+' requests · k6 pass rate '+(s.pass_rate==null?'unavailable':s.pass_rate+'%');}
  catch(e){if(!background&&currentProject?.project_id===project.project_id)summary.textContent=e.message;}
}
async function loadAdminOverview(){
  const host=document.getElementById('adminOverview');host.textContent='Loading all-project overview…';
  try{const j=await projectApi('/api/admin/dashboard',{headers:{'X-Perfagent-Admin':document.getElementById('adminToken').value}});
    host.innerHTML='<p>'+j.summary.tests+' tests · '+j.summary.runs+' runs · '+Number(j.summary.requests).toLocaleString()+' requests</p><div class="table-scroll"><table><thead><tr><th>Project</th><th>Tests</th><th>Runs</th><th>Requests</th><th>Pass rate</th></tr></thead><tbody>'+j.projects.map(p=>'<tr><td>'+esc(p.name)+'</td><td>'+p.tests+'</td><td>'+p.runs+'</td><td>'+p.requests+'</td><td>'+(p.pass_rate==null?'Unavailable':p.pass_rate+'%')+'</td></tr>').join('')+'</tbody></table></div>';
  }catch(e){host.textContent=e.message;}
}
async function loadWorkloadProfiles(){
  const planId=currentPlanId;if(!planId)return;
  try{const j=await projectApi('/api/plans/'+planId+'/workloads');if(planId!==currentPlanId)return;savedWorkloads=j.workloads||[];
    document.getElementById('savedWorkload').innerHTML='<option value="">Saved workload profiles</option>'+savedWorkloads.map(w=>'<option value="'+esc(w.workload_id)+'">'+esc(w.name)+'</option>').join('');}
  catch(e){showError(e.message);}
}
async function saveWorkloadProfile(){
  if(!currentPlanId||!planModel){showError('Draft a test plan first.');return;}
  const name=document.getElementById('workloadName').value.trim();if(!name){showError('Name the workload profile.');return;}
  try{await projectApi('/api/plans/'+currentPlanId+'/workloads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,load_profile:planModel.load_profile,thresholds:planModel.thresholds||[]})});await loadWorkloadProfiles();}
  catch(e){showError(e.message);}
}
function applySavedWorkload(){
  const workload=savedWorkloads.find(w=>w.workload_id===document.getElementById('savedWorkload').value);if(!workload||!planModel)return;
  planModel.load_profile=JSON.parse(JSON.stringify(workload.load_profile));planModel.thresholds=JSON.parse(JSON.stringify(workload.thresholds));_loadAsked=null;renderPlanForm();renderRawFromModel();
}
function suggestScriptFilename(){
  if(!planModel||document.getElementById('pfScriptFilename').value.trim())return;
  const name=document.getElementById('pfTestName').value.trim();if(!name)return;
  const extension={k6:'.js',locust:'.py',jmeter:'.jmx',gatling:'.scala'}[document.getElementById('tool').value]||'.js';
  const filename=(name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,100)||'test')+extension;
  planModel.script_filename=filename;document.getElementById('pfScriptFilename').value=filename;
}
async function loadDashboardTests(){
  try{
    const response=await fetch('/api/plans?project_id='+encodeURIComponent(currentProject.project_id));if(!response.ok)throw Error('Test list could not be loaded.');
    const j=await response.json(),select=document.getElementById('sdTest'),selected=select.value;
    select.innerHTML='<option value="">All tests</option>'+(j.plans||[]).map(p=>'<option value="'+esc(p.plan_id)+'">'+esc((p.test_name||p.goal||'Test')+' | '+p.plan_id.slice(0,8))+'</option>').join('');
    select.value=selected;
  }catch(e){showError(e.message);}
}
function showError(message){
  document.getElementById('appNoticeText').textContent=message;
  document.getElementById('appNotice').style.display='flex';
}
function getSelectedBaseline(){try{return localStorage.getItem('perfagent.baseline')||null;}catch(e){return null;}}
function selectReportBaseline(){
  if(!reportContext?.savedId)return;
  try{localStorage.setItem('perfagent.baseline',reportContext.savedId);document.getElementById('baselineSelection').textContent='Selected baseline: '+reportContext.savedId.slice(0,8);}
  catch(e){showError('Baseline preference could not be saved.');}
}
function clearSelectedBaseline(){
  try{localStorage.removeItem('perfagent.baseline');document.getElementById('baselineSelection').textContent='Automatic baseline: previous matching workload.';}
  catch(e){showError('Could not clear the selected baseline.');}
}
function setTrafficRate(){
  if(!planModel||planModel.load_profile.executor_options)return;
  const raw=document.getElementById('pfArrival').value,rate=Number(raw),vus=Number(document.getElementById('pfArrivalVus').value);
  if((raw&&(!Number.isInteger(rate)||rate<1||rate>1000000))||!Number.isInteger(vus)||vus<1||vus>1000000){showError('Use positive whole numbers up to 1,000,000 for iteration rate and preallocated users.');return;}
  if(planModel.load_profile.target_request_rate!=null) planModel.load_profile.target_request_rate=raw?rate:null;
  planModel.load_profile.arrival_rate=raw?rate:null;
  planModel.load_profile.pre_allocated_vus=vus;renderRawFromModel();renderSummary();
}
function environmentPresets(){try{return JSON.parse(localStorage.getItem('perfagent.environments')||'{}');}catch(e){return {};}}
function renderEnvironmentPresets(){
  document.getElementById('environmentPreset').innerHTML='<option value="">Saved environments</option>'+Object.keys(environmentPresets()).map(name=>'<option value="'+esc(name)+'">'+esc(name)+'</option>').join('');
}
function saveEnvironmentPreset(){
  if(!planModel)return;
  const name=document.getElementById('environment').value.trim(),target=document.getElementById('pfTarget').value.trim();
  if(!name||!/^https?:\/\//.test(target)){showError('Enter an environment name and full target URL first.');return;}
  const presets=environmentPresets();presets[name]={target};
  try{localStorage.setItem('perfagent.environments',JSON.stringify(presets));renderEnvironmentPresets();}
  catch(e){showError('Could not save the environment.');}
}
function useEnvironmentPreset(){
  const name=document.getElementById('environmentPreset').value,preset=environmentPresets()[name];
  if(!preset||!planModel)return;
  planModel.environment=name;planModel.target_base_url=preset.target;renderPlanForm();
}
async function checkReadiness(){
  const el=document.getElementById('readinessResult');el.style.display='block';el.className='note info';el.textContent='Checking execution inputs…';
  try{
    await ensureScriptId();if(!currentScriptId)throw Error('Generate or import a script first.');
    const r=await fetch('/api/scripts/'+encodeURIComponent(currentScriptId)+'/readiness'),j=await r.json();if(!r.ok)throw Error(j.detail||'Readiness check failed.');
    const x=j.execution;
    el.innerHTML='<b>Before you run</b><ul>'+j.checks.map(c=>'<li>'+esc(c.name)+': '+(c.ok?'Ready':'Review')+' — '+esc(c.detail)+'</li>').join('')+'</ul><p>'+
      (x.generated&&!x.script_edited&&x.executor?esc(x.executor)+' · ':'')+esc(x.duration_seconds)+' seconds'+
      (x.planned_iterations!=null&&!x.script_edited?' max · '+esc(x.planned_iterations)+' planned iterations':'')+
      ' · '+esc(x.peak_users)+(x.executor==='ramping-arrival-rate'?' preallocated VUs':' peak users')+
      (x.arrival_rate?' · '+esc(formatJourneyRate(x.arrival_rate))+' journey starts/s':'')+
      (x.target_request_rate?' · '+esc(x.target_request_rate)+' target HTTP requests/s':'')+
      '</p><p>Verify test exercises the configured k6 journeys and checks with one virtual user. Validate checks script syntax without sending traffic.</p>';
  }catch(e){el.className='note err';el.textContent=e.message;}
}
const releaseStates={ready:'Ready',blocked:'Blocked',needs_evidence:'Needs evidence'};
function releaseNumber(value,unit){
  return Number.isFinite(value)?Number(value.toPrecision(6))+' '+unit:'Unavailable';
}

function releaseDecisionMarkup(decision,titleId){
  const state=releaseStates[decision.status]||releaseStates.needs_evidence;
  const resultClass=decision.status==='ready'?'pass':decision.status==='blocked'?'fail':'ghost';
  const rules=(decision.rules||[]).map(rule=>`<tr><th scope="row">${esc(rule.name)}</th>
    <td>${esc(releaseNumber(rule.actual,rule.unit))}</td><td>${esc(rule.op)} ${esc(releaseNumber(rule.limit,rule.unit))}</td>
    <td>${rule.passed===true?'Met':rule.passed===false?'Breached':'Unavailable'}</td></tr>`).join('');
  const metadata=decision.baseline_id?[
    ['Environment',decision.environment||'Unlabeled'],
    ['Baseline',decision.baseline_release||decision.baseline_id.slice(0,8)],
    ['Candidate',decision.candidate_id===decision.baseline_id?null:decision.candidate_release||decision.candidate_id.slice(0,8)],
    ['Average load',decision.candidate_rps==null?null:releaseNumber(decision.candidate_rps,'req/s')],
    ['Planned load',decision.target_rps==null?null:releaseNumber(decision.target_rps,'req/s')],
  ]:[];
  return `<div class="release-heading"><h2 id="${titleId}">Release readiness</h2><span class="pill ${resultClass}">${state}</span></div>
    <p class="release-headline">${esc(decision.reason)}</p>
    ${decision.summary?'<p class="release-summary">'+esc(decision.summary)+'</p>':''}
    ${metadata.length?`<dl class="release-context">${metadata.filter(([,value])=>value!==null).map(([label,value])=>
      `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>`:''}
    ${rules?`<div class="release-table"><table aria-label="Release budget results"><thead><tr><th scope="col">Budget</th><th scope="col">Actual</th><th scope="col">Limit</th><th scope="col">Result</th></tr></thead><tbody>${rules}</tbody></table></div>`:''}`;

}

function renderReleaseReport(report){
  const panel=document.getElementById('reportReleaseReadiness');
  const decision=report.release_readiness;
  panel.hidden=!decision;
  panel.dataset.state=decision?.status||'';
  if(!decision){renderReleaseComparison(document.getElementById('reportReleaseComparison'),{});return;}
  panel.querySelector('#reportReleaseDecision').innerHTML=releaseDecisionMarkup(decision,'releaseReadinessTitle');
  const details=panel.querySelector('#reportReleasePolicy'), form=panel.querySelector('form');
  const status=panel.querySelector('#releasePolicyStatus'), button=form.querySelector('button');
  const id=reportContext.savedId;
  details.open=false;
  details.hidden=!(id&&report.plan_id&&report.status==='finished'&&report.verdict?.overall_passed===true&&
    report.execution?.workload_version&&(report.execution?.mode||'full')==='full'&&report.snapshot?.requests>0&&
    !report.snapshot?.dropped_iterations);
  status.textContent='';
  button.disabled=false;
  panel.querySelector('#releasePolicyScope').textContent='Environment '+(decision.environment||'Unlabeled')+
    '. Set at least one limit. Saving replaces the current baseline and budgets for this test environment.';
  for(const field of form.querySelectorAll('input')) field.value=decision.budgets?.[field.name]??'';
  form.onsubmit=async event=>{
    event.preventDefault();
    const budgets=Object.fromEntries([...new FormData(form)].filter(([,value])=>value!=='').map(([key,value])=>[key,Number(value)]));
    if(!Object.keys(budgets).length){status.textContent='Set at least one release budget.';form.querySelector('input').focus();return;}
    button.disabled=true;
    status.textContent='Saving release policy…';
    try{
      const response=await fetch('/api/runs/'+encodeURIComponent(id)+'/release-policy',{
        method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({budgets}),
      });
      const body=await response.json();
      if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'Check the budget values and try again.');
      if(reportContext?.savedId===id){
        const updated=await fetch('/api/runs/'+encodeURIComponent(id)+'/saved-report');
        if(!updated.ok)throw Error('Policy saved. Reopen the report to see the current decision.');
        const saved=await updated.json();
        if(reportContext?.savedId===id){
          renderReleaseReport(saved);
          details.open=true;
          status.textContent='Baseline approved and budgets saved.';
          button.focus();
        }
      }
    }catch(error){if(reportContext?.savedId===id)status.textContent=error.message;}
    finally{if(reportContext?.savedId===id)button.disabled=false;}
  };
  renderReleaseComparison(document.getElementById('reportReleaseComparison'),decision);
}

let releaseChartRedraw;
const releaseChartResize=new ResizeObserver(()=>releaseChartRedraw?.());
function renderReleaseComparison(panel,decision){
  releaseChartResize.disconnect();
  releaseChartRedraw=null;
  const comparison=decision.comparison;
  panel.hidden=!comparison;
  panel.replaceChildren();
  if(!comparison)return;
  const metrics=[['Throughput','rps','rps','req/s'],['p95 latency','p95','p95_ms','ms'],['Request errors','err','error_percent','%']];
  const sampleRows=[['Baseline',comparison.baseline],['Candidate',comparison.candidate]].flatMap(([label,points])=>
    points.map(point=>`<tr><th scope="row">${label}</th><td>${esc(releaseNumber(point.t,'s'))}</td>
      <td>${esc(releaseNumber(point.rps,'req/s'))}</td><td>${esc(releaseNumber(point.p95,'ms'))}</td>
      <td>${esc(releaseNumber(point.err,'%'))}</td></tr>`)).join('');
  const endpointRows=comparison.endpoints.map(item=>`<tr><th scope="row">${esc(item.name)}</th>
    <td>${esc(releaseNumber(item.baseline_ms,'ms'))}</td><td>${esc(releaseNumber(item.candidate_ms,'ms'))}</td>
    <td>${esc(releaseNumber(item.candidate_ms-item.baseline_ms,'ms'))}</td></tr>`).join('');
  panel.innerHTML=`<div class="comparison-header">
      <div><h3>Baseline versus candidate</h3><p class="muted">Elapsed time under the same workload</p></div>
      <label for="releaseComparisonMetric">Metric <select id="releaseComparisonMetric">
        ${metrics.map(([label,key])=>`<option value="${key}"${key==='p95'?' selected':''}>${label}</option>`).join('')}
      </select></label>
    </div>
    <figure class="comparison-chart">
      <figcaption class="comparison-key"></figcaption>
      <canvas aria-hidden="true"></canvas>
      <p class="muted">${esc(comparison.phases.map(phase=>phase.label+' '+phase.start_s+'–'+phase.end_s+' s').join(' · '))}</p>
    </figure>
    ${endpointRows?`<div class="release-table"><table aria-label="Endpoint p95 changes"><thead><tr><th scope="col">Endpoint</th>
      <th scope="col">Baseline p95</th><th scope="col">Candidate p95</th><th scope="col">Change</th></tr></thead><tbody>${endpointRows}</tbody></table></div>`:''}
    ${sampleRows?`<details><summary>Comparison sample data</summary>
      <div class="release-table" tabindex="0" role="region" aria-label="Comparison sample data">
        <table><thead><tr><th scope="col">Run</th><th scope="col">Elapsed</th><th scope="col">Throughput</th>
        <th scope="col">p95 latency</th><th scope="col">Request errors</th></tr></thead>
        <tbody>${sampleRows}</tbody></table>
      </div></details>`:''}
    <div class="btnrow"><button type="button" class="btn ghost sm">Open approved baseline</button></div>`;
  panel.querySelector('button').onclick=()=>openSavedReport(decision.baseline_id);
  const metric=panel.querySelector('select');
  const canvas=panel.querySelector('canvas');
  const caption=panel.querySelector('figcaption');
  const redraw=()=>{
    if(!canvas.isConnected||!canvas.clientWidth)return;
    const key=metric.value;
    const [, , summary,unit]=metrics.find(([,option])=>option===key);
    caption.innerHTML=`<span class="comparison-baseline">Baseline ${esc(releaseNumber(comparison.baseline_metrics[summary],unit))}</span>
      <span class="comparison-candidate">Candidate ${esc(releaseNumber(comparison.candidate_metrics[summary],unit))}</span>`;
    const series=[['baseline','#637086',[5,4]],['candidate','#324ad2',[]]].map(([run,color,dash])=>({
      color,dash,data:comparison[run].filter(point=>Number.isFinite(point.t)).map(point=>({x:point.t,y:point[key]})),
    }));
    const end=Math.max(0,...series.flatMap(item=>item.data.map(point=>point.x)));
    _lineChart(canvas,series,{height:canvas.clientHeight,domain:[0,end],
      boundaries:comparison.phases.map(phase=>phase.end_s)});
  };
  metric.onchange=redraw;
  releaseChartRedraw=redraw;
  releaseChartResize.observe(canvas);
  requestAnimationFrame(redraw);

}

function renderReportDetails(j){
  const x=j.execution||{},snap=j.snapshot||{},lat=snap.latency||{};
  document.getElementById('reportContext').textContent=(x.test_name||'Unnamed test')+' | '+(x.script_name||'Script not recorded')+' | '+(x.endpoint_summary||'Endpoints not recorded')+' | '+(j.status||'Recorded')+' · '+(x.mode||'full')+' · environment: '+(x.environment||'unlabeled')+' · release: '+(x.release_label||'unlabeled')+' · workload: '+(x.workload_version?.slice(0,12)||'not recorded')+' · run comparison reference: '+(j.baseline_id?.slice(0,8)||'none')+(j.message?' · '+j.message:'');
  document.getElementById('baselineSelection').textContent=getSelectedBaseline()?'Selected baseline: '+getSelectedBaseline().slice(0,8):'Automatic baseline: previous matching workload.';
  const endpoints=[...(snap.per_endpoint||[])].sort((a,b)=>(b.p95_ms||0)-(a.p95_ms||0));
  const formatThreshold=(metric,value)=>{
    if(value==null) return 'Unavailable';
    if(metric==='error_rate') return Number((value*100).toPrecision(15))+'%';
    if(metric.endsWith('_ms')) return Number(value.toPrecision(8))+' ms';
    return value;
  };
  const thresholdList=j.evidence?.thresholds||[...(j.verdict?.checks||[])].sort((a,b)=>
    (a.passed===false?0:a.passed==null?1:2)-(b.passed===false?0:b.passed==null?1:2));
  const rules=thresholdList.map(c=>'<tr><td>'+esc(c.metric)+'</td><td>'+esc(c.target==null?'':c.op+' '+formatThreshold(c.metric,c.target))+'</td><td>'+esc(formatThreshold(c.metric,c.actual))+'</td><td>'+(c.passed===true?'Pass':c.passed===false?'Fail':'Inconclusive')+'</td></tr>').join('');
  const measurements=[
    [lat.samples,'latency samples'], [snap.iterations,'completed iterations'], [x.script_edited?null:x.planned_iterations,'planned iterations'],
    [snap.iterations_per_second,'achieved iterations/s'], [snap.dropped_iterations,'dropped iterations'],
    [x.script_edited?null:x.target_request_rate,'target requests/s'],
    [!x.script_edited&&Number.isFinite(x.planned_iteration_rate??x.arrival_rate)?
      formatJourneyRate(x.planned_iteration_rate??x.arrival_rate):null,'planned journey starts/s'],
    [snap.observed_peak_vus,'observed peak VUs'], [snap.bytes_sent,'bytes sent'], [snap.bytes_received,'bytes received'],
  ].filter(([value])=>value!=null).map(([value,label])=>esc(value)+' '+label).join(' · ');
  const executor=x.generated&&!x.script_edited&&x.executor?'<p>Planned executor <strong>'+esc(x.executor)+'</strong></p>':'';
  const throughputBasis=!x.script_edited&&x.requests_per_iteration?
    '<p>Throughput plan uses '+esc(x.requests_per_iteration)+' HTTP '+(x.requests_per_iteration===1?'request':'requests')+
    ' per completed journey.</p>':'';
  const journeyRows=(snap.per_journey||[]).map(journey=>'<tr>'+
    [journey.name,journey.requests,journey.failed,journey.iterations,journey.dropped_iterations,journey.checks_failed]
      .map(value=>'<td>'+esc(value)+'</td>').join('')+'</tr>').join('');
  const journeyTable=journeyRows?'<h3>Journey results</h3><div class="table-scroll"><table><thead><tr><th scope="col">Journey</th><th scope="col">Requests</th><th scope="col">HTTP failures</th><th scope="col">Iterations</th><th scope="col">Dropped iterations</th><th scope="col">Failed checks</th></tr></thead><tbody>'+journeyRows+'</tbody></table></div>':'';
  const endpointRows=endpoints.slice(0,10).map(endpoint=>{
    const statuses=Object.entries(endpoint.status_codes||{}).map(([status,count])=>status+' × '+count).join(', ');
    return '<tr>'+[endpoint.name,endpoint.requests,endpoint.failed,endpoint.checks_failed??'Unavailable',statuses||'Unavailable',formatThreshold('p95_ms',endpoint.p95_ms)]
      .map(value=>'<td>'+esc(value)+'</td>').join('')+'</tr>';
  }).join('');
  const phaseRows=(snap.per_endpoint||[]).flatMap(endpoint=>Object.entries(endpoint.timing_phases||{}).map(([phase,values])=>
    '<tr>'+[endpoint.name,phase.replaceAll('_',' '),values.avg_ms,values.p95_ms]
      .map(value=>'<td>'+esc(value??'Unavailable')+'</td>').join('')+'</tr>'
  )).join('');
  const timing=phaseRows?`<details class="report-timings"><summary>HTTP timing phases</summary>
    <div class="table-scroll"><table>
      <thead><tr><th scope="col">Endpoint</th><th scope="col">Phase</th><th scope="col">Average (ms)</th><th scope="col">p95 (ms)</th></tr></thead>
      <tbody>${phaseRows}</tbody>
    </table></div></details>`:'';
  document.getElementById('reportHighlights').innerHTML=`
    <h2>${thresholdList.some(check=>check.passed===false)?'Thresholds that need attention':'Threshold results'}</h2>
    <div class="table-scroll"><table>
      <thead><tr><th scope="col">Metric</th><th scope="col">Rule</th><th scope="col">Measured</th><th scope="col">Result</th></tr></thead>
      <tbody>${rules||'<tr><td colspan="4">No evaluated thresholds were recorded for this run.</td></tr>'}</tbody>
    </table></div>`;
  document.getElementById('reportDetails').innerHTML=`
    <h3>Measured workload</h3>
    ${executor}${throughputBasis}
    <p>${measurements||'No workload measurements are available for this run.'}</p>
    <h3>Endpoint ranking</h3>
    ${endpoints.length?'<label for="reportEndpointMetric">Rank by</label> <select id="reportEndpointMetric"><option value="p95_ms">p95 latency</option><option value="failed">HTTP failures</option><option value="checks_failed">Failed response checks</option></select><ol id="reportEndpointRanking" class="report-endpoint-ranking"></ol>':''}
    <h3>Endpoint measurements</h3>
    <div class="table-scroll"><table>
      <thead><tr><th scope="col">Endpoint</th><th scope="col">Requests</th><th scope="col">HTTP failures</th><th scope="col">Failed response checks</th><th scope="col">HTTP status counts</th><th scope="col">p95</th></tr></thead>
      <tbody>${endpointRows||'<tr><td colspan="6">No endpoint measurements were recorded.</td></tr>'}</tbody>
    </table></div>${journeyTable}${timing}`;
  const selector=document.getElementById('reportEndpointMetric');
  if(selector){
    const ranking=document.getElementById('reportEndpointRanking');
    const renderRanking=()=>{
      const key=selector.value;
      const ranked=endpoints.filter(endpoint=>Number.isFinite(endpoint[key]))
        .sort((a,b)=>b[key]-a[key]).slice(0,10);
      const maximum=ranked[0]?.[key]||1;
      ranking.innerHTML=ranked.map(endpoint=>'<li><div><span>'+esc(endpoint.name)+'</span><strong>'+
        esc(endpoint[key]+(key==='p95_ms'?' ms':''))+'</strong></div><meter aria-label="'+esc(endpoint.name)+
        '" min="0" max="'+maximum+'" value="'+endpoint[key]+'"></meter></li>').join('')||
        '<li>No endpoint measurements for this metric.</li>';
    };
    selector.onchange=renderRanking;
    renderRanking();
  }
}

function renderReportEvidenceSummary(report){
  const panel=document.getElementById('reportEvidenceSummary');
  if(!panel) return;
  const checks=report.evidence?.thresholds||report.verdict?.checks||[];
  const failures=checks.filter(check=>check.passed===false);
  const baseline=report.baseline?.deltas?.find(delta=>delta.direction==='worse'&&delta.previous_fmt&&delta.current_fmt);
  const endpoint=[...(report.snapshot?.per_endpoint||[])].filter(item=>item.failed>0).sort((a,b)=>b.failed-a.failed)[0];
  const items=[];
  if(failures.length) items.push({
    title:failures.length+' breached '+(failures.length===1?'threshold':'thresholds'),
    text:failures.map(check=>check.metric==='p95_ms'?'p95 latency':check.metric==='error_rate'?'Error rate':check.metric).join(', '),
    destination:'reportHighlights',
  });
  if(baseline) items.push({title:'Worse than baseline',text:baseline.label+' '+baseline.previous_fmt+' → '+baseline.current_fmt,destination:'reportDiagnosisDetails'});
  if(endpoint) items.push({title:'Most HTTP failures',text:endpoint.name+' · '+endpoint.failed,destination:'reportEndpointDetails'});
  if(!items.length&&checks.length&&checks.every(check=>check.passed===true)){
    items.push({title:checks.length+' of '+checks.length+' thresholds passed',text:'View the measured values and their limits',destination:'reportHighlights'});
  }
  panel.hidden=!items.length;
  panel.innerHTML=items.length?'<h3>Key evidence</h3>'+items.map(({title,text,destination})=>
    '<button type="button" data-report-evidence="'+destination+'"><strong>'+esc(title)+'</strong><span>'+esc(text)+'</span></button>').join(''):'';
  panel.querySelectorAll('[data-report-evidence]').forEach(button=>{
    button.onclick=()=>{
      const destination=document.getElementById(button.dataset.reportEvidence);
      if(destination instanceof HTMLDetailsElement) destination.open=true;
      destination.tabIndex=-1;
      destination.focus();
    };
  });
}

/* ---------- init ---------- */














export const handlers={h0(event){const result=(function(event){editProject()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h1(event){const result=(function(event){beginFrameworkImport()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h2(event){const result=(function(event){saveProject()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h3(event){const result=(function(event){document.getElementById('projectForm').style.display='none';importAfterProject=false
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h4(event){const result=(function(event){showNewTestForm()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h5(event){const result=(function(event){startProjectImport('script')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h6(event){const result=(function(event){startProjectImport('git')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h7(event){const result=(function(event){showView('history')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h8(event){const result=(function(event){showView('dashboard')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h9(event){const result=(function(event){editProject(currentProject)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h10(event){const result=(function(event){startNamedTest()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h11(event){const result=(function(event){loadAdminOverview()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h12(event){const result=(function(event){document.getElementById('adminToken').value='';document.getElementById('adminOverview').innerHTML=''
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h13(event){const result=(function(event){setMode('conv')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h14(event){const result=(function(event){setMode('manual')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h15(event){const result=(function(event){setMode('script')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h16(event){const result=(function(event){setMode('git')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h17(event){const result=(function(event){convPick(this.value)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h18(event){const result=(function(event){convNew()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h19(event){const result=(function(event){convSend()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h20(event){const result=(function(event){convDelete()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h21(event){const result=(function(event){convBuild()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h22(event){const result=(function(event){document.getElementById('importFile').click()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h23(event){const result=(function(event){importEndpoints()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h24(event){const result=(function(event){addEndpoint()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h25(event){const result=(function(event){doPlan()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h26(event){const result=(function(event){loadExistingFile()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h27(event){const result=(function(event){uploadExisting()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h28(event){const result=(function(event){gitBrowse()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h29(event){const result=(function(event){document.getElementById('impScriptView').style.display='none'
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h30(event){const result=(function(event){gitUseScript()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h31(event){const result=(function(event){applySavedWorkload()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h32(event){const result=(function(event){saveWorkloadProfile()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h33(event){const result=(function(event){planModel.test_name=this.value.trim()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h34(event){const result=(function(event){suggestScriptFilename()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h35(event){const result=(function(event){planModel.script_filename=this.value.trim()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h36(event){const result=(function(event){planModel.target_base_url=this.value.trim();renderSummary()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h37(event){const result=(function(event){updateLoad()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h38(event){const result=(function(event){updateLoad()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h39(event){const result=(function(event){updateLoad()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h40(event){const result=(function(event){if(planModel) renderDataCard()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h41(event){const result=(function(event){setTrafficRate()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h42(event){const result=(function(event){setTrafficRate()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h43(event){const result=(function(event){useEnvironmentPreset()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h44(event){const result=(function(event){saveEnvironmentPreset()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h45(event){const result=(function(event){planModel.environment=this.value.trim();renderConnCount()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h46(event){const result=(function(event){planModel.insecure_tls=this.checked;renderConnCount()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h47(event){const result=(function(event){addHeader()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h48(event){const result=(function(event){document.getElementById('dataFile').click()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h49(event){const result=(function(event){uploadData()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h50(event){const result=(function(event){addScenario()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h51(event){const result=(function(event){previewRequests()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h52(event){const result=(function(event){addThreshold()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h53(event){const result=(function(event){applySla()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h54(event){const result=(function(event){saveSla()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h55(event){const result=(function(event){toggleRaw()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h56(event){const result=(function(event){goStep(1)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h57(event){const result=(function(event){doGenerate()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h58(event){const result=(function(event){checkReadiness()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h59(event){const result=(function(event){runScript(true)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h60(event){const result=(function(event){goStep(2)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h61(event){const result=(function(event){toggleEditScript()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h62(event){const result=(function(event){regenScript()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h63(event){const result=(function(event){download()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h64(event){const result=(function(event){doValidate()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h65(event){const result=(function(event){doPreflight()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h66(event){const result=(function(event){runScript()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h67(event){const result=(function(event){exportZip()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h68(event){const result=(function(event){exportGit()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h69(event){const result=(function(event){jenkinsSetup()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h70(event){const result=(function(event){toggleJenkinsSetup()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h71(event){const result=(function(event){jenkinsStop()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h72(event){const result=(function(event){jenkinsRun()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h73(event){const result=(function(event){stopRun()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h74(event){const result=(function(event){downloadReport()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h75(event){const result=(function(event){rerunReport()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h76(event){const result=(function(event){selectReportBaseline()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h77(event){const result=(function(event){clearSelectedBaseline()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h78(event){const result=(function(event){downloadRunLogs()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h79(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h80(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h81(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h82(event){const result=(function(event){clearTimeout(dashboardFilterTimer);dashboardFilterTimer=setTimeout(()=>loadStakeholder(),250)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h83(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h84(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h85(event){const result=(function(event){loadStakeholder()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h86(event){const result=(function(event){resetDashboardFilters()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h87(event){const result=(function(event){renderRunComparison()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h88(event){const result=(function(event){renderRunComparison()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h89(event){const result=(function(event){loadStakeholder(Math.max(0,dashboardOffset-50))
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h90(event){const result=(function(event){loadStakeholder(dashboardOffset+50)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h91(event){const result=(function(event){loadPlans()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h92(event){const result=(function(event){loadRuns()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h93(event){const result=(function(event){monAdd()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h94(event){const result=(function(event){loadAudit()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h95(event){const result=(function(event){loadTraces()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h96(event){const result=(function(event){toggleSidebar()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h97(event){const result=(function(event){showView('projects')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h98(event){const result=(function(event){showNewTestForm()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h99(event){const result=(function(event){startProjectImport('script')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h100(event){const result=(function(event){startProjectImport('git')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h101(event){const result=(function(event){showView('dashboard')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h102(event){const result=(function(event){showView('history')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h103(event){const result=(function(event){showView('monitoring')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h104(event){const result=(function(event){showView('activity')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h105(event){const result=(function(event){showView('admin')
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h106(event){const result=(function(event){openMobNav()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h107(event){const result=(function(event){selectProject(this.value)
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h108(event){const result=(function(event){closeBodyEditor()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h109(event){const result=(function(event){dynamizeBody()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h110(event){const result=(function(event){closeBodyEditor()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h111(event){const result=(function(event){saveBodyEditor()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h112(event){const result=(function(event){closeSuggestChecks()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h113(event){const result=(function(event){runSuggestChecks()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h114(event){const result=(function(event){closeSuggestChecks()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h115(event){const result=(function(event){applySuggestedChecks()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h116(event){const result=(function(event){this.parentElement.style.display='none'
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;},
h117(event){const result=(function(event){closeMobNav()
}).call(event.currentTarget,event);if(result===false){event.preventDefault();event.stopPropagation();}return result;}};
export const actions={goStep,setMode,convApi,convRemember,convRecall,initConversation,convLoadHistory,convPick,convOpen,convNew,convDelete,convShowError,convSetBusy,convBubble,convScroll,convRender,convRenderDraft,convSend,convBuild,convOpenPlan,addEndpoint,openBodyEditor,closeBodyEditor,saveBodyEditor,dynamizeBody,toggleGenMenu,closeGenMenus,insertGen,readEndpoints,loadTools,doPlan,showGuardrail,showPlanEval,refreshUsage,showUsage,openSuggestChecks,closeSuggestChecks,runSuggestChecks,checkLabel,applySuggestedChecks,loadSlaProfiles,applySla,saveSla,renderSummary,stepKey,resetReviewState,renderPlanForm,loadOfProfile,renderLoad,updateLoad,renderConnCount,renderDataCard,uploadData,removeDataFile,scenarioCard,setThink,toggleStep,stepRow,flattenBody,pathLabel,getAt,setAt,delAt,capturedVars,classifyValue,requestDataHtml,fieldRowHtml,genArgsHtml,rdTarget,rdSet,setFieldSource,setFieldFixed,setFieldType,setFieldToken,setFieldGen,setFieldGenArgs,setFieldRaw,delBodyField,addBodyField,setBodyJson,suggestSources,undoSuggest,fetchPreview,previewRequests,setGql,addGql,removeGql,assertRowHtml,setAssert,addAssertion,removeAssertion,setExtract,addExtract,removeExtract,thresholdRow,setRuleMetric,setRuleValue,setWeight,updateWeightBadges,addScenario,forgetOpenSteps,delScenario,addStep,delStep,addThreshold,delThreshold,renderRawFromModel,toggleRaw,esc,doGenerate,attachStoredDataFile,download,setFields,applyIntegrations,showSaved,forgetIntegrations,jkVal,fillIfEmpty,syncJenkinsDefaults,jkAuth,jkCheck,toggleJenkinsSetup,jkSetPill,jenkinsSetup,jenkinsRun,jenkinsPoll,jenkinsDone,renderJenkinsResults,jenkinsStop,setGitExport,loadExportSettings,exportBody,exportReady,secretsNote,exportGit,exportZip,gitSource,gitPost,gitBrowse,renderGitScan,gitImportStart,gitImport,importWholeFramework,gitViewScript,gitUseScript,toggleEditScript,regenScript,currentScriptText,ensureScriptId,runScript,pollRun,stopRun,loadReport,_lineChart,drawTsChart,loadTrend,renderReport,downloadRunLogs,downloadReport,loadTraces,loadAudit,sdFmt,sdVerdict,loadStakeholder,sdDrawTrend,resetDashboardFilters,populateRunComparison,renderRunComparison,rerunReport,loadRuns,openSavedReport,loadPlans,openPlan,importEndpoints,addHeader,readHeaders,loadExistingFile,uploadExisting,doValidate,doPreflight,resetChart,pushChart,drawChart,showView,toggleSidebar,openMobNav,closeMobNav,monLoad,monSave,monAdd,monRemove,monRender,_donut,_bars,projectQuery,projectGitDefaults,projectApi,loadProjects,renderProjectContext,selectProject,editProject,beginFrameworkImport,saveProject,showNewTestForm,startNamedTest,startProjectImport,attachCurrentTest,loadProjectSummary,loadAdminOverview,loadWorkloadProfiles,saveWorkloadProfile,applySavedWorkload,suggestScriptFilename,loadDashboardTests,showError,getSelectedBaseline,selectReportBaseline,clearSelectedBaseline,setTrafficRate,environmentPresets,renderEnvironmentPresets,saveEnvironmentPreset,useEnvironmentPreset,checkReadiness,renderReportDetails};
let initialized=false,workspaceEvents=null;
const originalBindings=new Map();
export async function initialize(){
 if(initialized)return;
 initialized=true;
 routeMuted=true;
 workspaceEvents=new AbortController();
 workspaceRefreshTimer=setInterval(refreshVisibleWorkspace,30000);
 document.addEventListener('visibilitychange',refreshVisibleWorkspace,{signal:workspaceEvents.signal});
 const properties={"projects":{configurable:true,get:()=>projects,set:value=>{projects=value;}},
"currentProject":{configurable:true,get:()=>currentProject,set:value=>{currentProject=value;}},
"editingProjectId":{configurable:true,get:()=>editingProjectId,set:value=>{editingProjectId=value;}},
"newTestName":{configurable:true,get:()=>newTestName,set:value=>{newTestName=value;}},
"importAfterProject":{configurable:true,get:()=>importAfterProject,set:value=>{importAfterProject=value;}},
"savedWorkloads":{configurable:true,get:()=>savedWorkloads,set:value=>{savedWorkloads=value;}},
"currentPlanId":{configurable:true,get:()=>currentPlanId,set:value=>{currentPlanId=value;}},
"currentScriptId":{configurable:true,get:()=>currentScriptId,set:value=>{currentScriptId=value;}},
"currentDataFileId":{configurable:true,get:()=>currentDataFileId,set:value=>{currentDataFileId=value;}},
"currentRunId":{configurable:true,get:()=>currentRunId,set:value=>{currentRunId=value;}},
"pollTimer":{configurable:true,get:()=>pollTimer,set:value=>{pollTimer=value;}},
"planModel":{configurable:true,get:()=>planModel,set:value=>{planModel=value;}},
"dataColumns":{configurable:true,get:()=>dataColumns,set:value=>{dataColumns=value;}},
"MODES":{configurable:true,get:()=>MODES},
"convId":{configurable:true,get:()=>convId,set:value=>{convId=value;}},
"convView":{configurable:true,get:()=>convView,set:value=>{convView=value;}},
"convBusy":{configurable:true,get:()=>convBusy,set:value=>{convBusy=value;}},
"CONV_KEY":{configurable:true,get:()=>CONV_KEY},
"CONV_EXAMPLES":{configurable:true,get:()=>CONV_EXAMPLES},
"_bodyTargetInput":{configurable:true,get:()=>_bodyTargetInput,set:value=>{_bodyTargetInput=value;}},
"GENERATORS":{configurable:true,get:()=>GENERATORS},
"_suggestTarget":{configurable:true,get:()=>_suggestTarget,set:value=>{_suggestTarget=value;}},
"_suggested":{configurable:true,get:()=>_suggested,set:value=>{_suggested=value;}},
"planRationale":{configurable:true,get:()=>planRationale,set:value=>{planRationale=value;}},
"METHODS":{configurable:true,get:()=>METHODS},
"_reviewPlanId":{configurable:true,get:()=>_reviewPlanId,set:value=>{_reviewPlanId=value;}},
"openSteps":{configurable:true,get:()=>openSteps,set:value=>{openSteps=value;}},
"jsonSteps":{configurable:true,get:()=>jsonSteps,set:value=>{jsonSteps=value;}},
"advSteps":{configurable:true,get:()=>advSteps,set:value=>{advSteps=value;}},
"dynUndo":{configurable:true,get:()=>dynUndo,set:value=>{dynUndo=value;}},
"dataFileInfo":{configurable:true,get:()=>dataFileInfo,set:value=>{dataFileInfo=value;}},
"dataRowMode":{configurable:true,get:()=>dataRowMode,set:value=>{dataRowMode=value;}},
"_loadAsked":{configurable:true,get:()=>_loadAsked,set:value=>{_loadAsked=value;}},
"ROW_MODES":{configurable:true,get:()=>ROW_MODES},
"GEN_KINDS":{configurable:true,get:()=>GEN_KINDS},
"GEN_NAMES":{configurable:true,get:()=>GEN_NAMES},
"GEN_DEFAULT_ARGS":{configurable:true,get:()=>GEN_DEFAULT_ARGS},
"_rdPaths":{configurable:true,get:()=>_rdPaths,set:value=>{_rdPaths=value;}},
"CHECK_TYPES":{configurable:true,get:()=>CHECK_TYPES},
"RULES":{configurable:true,get:()=>RULES},
"GIT_FIELDS":{configurable:true,get:()=>GIT_FIELDS},
"JK_FIELDS":{configurable:true,get:()=>JK_FIELDS},
"FIELD_DEFAULTS":{configurable:true,get:()=>FIELD_DEFAULTS},
"integrationsSeq":{configurable:true,get:()=>integrationsSeq,set:value=>{integrationsSeq=value;}},
"jk":{configurable:true,get:()=>jk,set:value=>{jk=value;}},
"gitScan":{configurable:true,get:()=>gitScan,set:value=>{gitScan=value;}},
"gitViewed":{configurable:true,get:()=>gitViewed,set:value=>{gitViewed=value;}},
"_scriptEdited":{configurable:true,get:()=>_scriptEdited,set:value=>{_scriptEdited=value;}},
"dashboardRequest":{configurable:true,get:()=>dashboardRequest,set:value=>{dashboardRequest=value;}},
"dashboardRuns":{configurable:true,get:()=>dashboardRuns,set:value=>{dashboardRuns=value;}},
"reportContext":{configurable:true,get:()=>reportContext,set:value=>{reportContext=value;}},
"runStarting":{configurable:true,get:()=>runStarting,set:value=>{runStarting=value;}},
"dashboardOffset":{configurable:true,get:()=>dashboardOffset,set:value=>{dashboardOffset=value;}},
"dashboardFilterTimer":{configurable:true,get:()=>dashboardFilterTimer,set:value=>{dashboardFilterTimer=value;}},
"SD_COLS":{configurable:true,get:()=>SD_COLS},
"chartData":{configurable:true,get:()=>chartData,set:value=>{chartData=value;}},
"VIEW_META":{configurable:true,get:()=>VIEW_META},
"MON_KEY":{configurable:true,get:()=>MON_KEY}};
 for(const [name,descriptor] of Object.entries(properties)){
  originalBindings.set(name,Object.getOwnPropertyDescriptor(window,name));
  Object.defineProperty(window,name,descriptor);
 }
 for(const [name,fn] of Object.entries(actions)){
  originalBindings.set(name,Object.getOwnPropertyDescriptor(window,name));
  Object.defineProperty(window,name,{configurable:true,writable:true,value:fn});
 }
 document.querySelectorAll('.step').forEach(s=>s.addEventListener('click',()=>{
  const n=+s.dataset.step;
  if(canOpenStep(n))goStep(n);
}, {signal:workspaceEvents.signal}));
 document.querySelector('.modeswitch[role="tablist"]')?.addEventListener('keydown',event=>{
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
   const tabs=[...event.currentTarget.querySelectorAll('[role="tab"]')].filter(tab=>tab.offsetWidth>0);
   const current=tabs.indexOf(event.target);
   if(current<0)return;
   event.preventDefault();
   const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:
     (current+(event.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
   tabs[next].click();
   tabs[next].focus();
 },{signal:workspaceEvents.signal});
applyIntegrations(null);
(async()=>{ try{ const j=await (await fetch('/api/jenkins/settings')).json();
  if(j.allowed_hosts&&j.allowed_hosts.length) document.getElementById('jkHint').textContent+=' Allowed Jenkins hosts: '+j.allowed_hosts.join(', ')+'.'; }catch(e){} })();
loadExportSettings();
loadTools().catch(error=>showError('Load tools could not be loaded: '+error.message));
if(!document.getElementById('endpoints').childElementCount){
addEndpoint("GET","/products");
addEndpoint("POST","/login",'{"user":"demo","password":"x"}');
addEndpoint("POST","/cart",'{"product_id":1}');
addEndpoint("POST","/checkout",'{"pay":"card"}');
}
loadPlans();
refreshUsage();
try{ if((localStorage.getItem('perfagent.sidebarCollapsed')==='true')!==document.getElementById('sidebar').classList.contains('collapsed')) toggleSidebar(); }catch(e){}
showView('projects');
setMode('manual');
initConversation();
loadSlaProfiles();
loadTraces();
}
export function dispose(){
  releaseChartResize.disconnect();
  releaseChartRedraw=null;
 if(pollTimer)clearInterval(pollTimer);if(jk.timer)clearInterval(jk.timer);
 if(dashboardFilterTimer)clearTimeout(dashboardFilterTimer);
 if(workspaceRefreshTimer)clearInterval(workspaceRefreshTimer);
 workspaceEvents?.abort();routeMuted=true;queuedRoute='';
 for(const [name,descriptor] of originalBindings){if(descriptor)Object.defineProperty(window,name,descriptor);else delete window[name];}
 originalBindings.clear();initialized=false;
}

// Route restoration never starts traffic, clones Git, or publishes changes.
let routeMuted=true, queuedRoute='', routeNotificationPending=false;
function publishRoute(path){
  if(routeMuted)return;
  queuedRoute=path;
  if(routeNotificationPending)return;
  routeNotificationPending=true;
  queueMicrotask(()=>{
    routeNotificationPending=false;
    if(!routeMuted&&queuedRoute)window.dispatchEvent(new CustomEvent('perfagent:navigate',{detail:queuedRoute}));
  });
}
function projectPath(){return currentProject?'/projects/'+encodeURIComponent(currentProject.project_id):'/projects';}
function publishView(view){
  const path={home:'/',projects:'/projects',admin:'/admin/overview',monitoring:'/monitoring',activity:'/activity',dashboard:projectPath()+'/dashboard',history:projectPath()+'/tests'}[view];
  if(path)publishRoute(path);
}
function publishStep(step){
  if(!currentProject)return;
  if(step===5&&reportContext?.savedId){publishRoute(projectPath()+'/runs/'+encodeURIComponent(reportContext.savedId));return;}
  if(currentPlanId){publishRoute(projectPath()+'/tests/'+encodeURIComponent(currentPlanId)+'?step='+step);return;}
  try{sessionStorage.setItem('perfagent.new-test:'+currentProject.project_id,newTestName||'');}catch{}
  publishRoute(projectPath()+'/tests/new?stage=setup&step='+step);
}
export async function applyRoute(path){
  const route=resolveRoute(path);
  routeMuted=true;
  try{
    if(route.kind==='not-found')throw Error('This page does not exist.');
    if(route.projectId){
      await loadProjects();
      const project=projects.find(item=>item.project_id===route.projectId);
      if(!project)throw Error('The project was not found or is unavailable.');
      if(currentProject?.project_id!==route.projectId){
        if(pollTimer)throw Error('A test is still running. Finish or stop it before switching projects.');
        selectProject(route.projectId);
      }
    }
    switch(route.kind){
      case 'home':showView('home');break;
      case 'projects':showView('projects');break;
      case 'new-project':editProject();break;
      case 'project':showView('history');break;
      case 'settings':editProject(currentProject);break;
      case 'new-test':{
        showNewTestForm();
        if(route.setup){
          let name='';try{name=sessionStorage.getItem('perfagent.new-test:'+route.projectId)||'';}catch{}
          if(name){document.getElementById('newTestName').value=name;startNamedTest();}
        }
        break;
      }
      case 'test':{
        if(document.documentElement.dataset.tour==='true' && route.step===1){
          document.getElementById('newTestName').value='Checkout API';
          document.getElementById('newTestPurpose').value='Measure checkout under load';
          startNamedTest();
          document.getElementById('endpoints').replaceChildren();
          addEndpoint('POST','/checkout','{}');
          break;
        }
        const plan=await requestJson('/api/plans/'+encodeURIComponent(route.testId));
        if(plan.project_id!==route.projectId)throw Error('This test belongs to another project.');
        await openPlan(route.testId);
        goStep(route.step);
        break;
      }
      case 'report':{
        const report=await requestJson('/api/runs/'+encodeURIComponent(route.runId)+'/saved-report');
        if(report.project_id && report.project_id!==route.projectId)throw Error('This report belongs to another project.');
        if(!report.project_id && report.plan_id){
          const plan=await requestJson('/api/plans/'+encodeURIComponent(report.plan_id));
          if(plan.project_id!==route.projectId)throw Error('This report belongs to another project.');
        }
        renderReport({...report,saved_result_id:route.runId});
        if(route.rerun)await rerunReport();
        break;
      }
      case 'import-script':startProjectImport('script');break;
      case 'import-git':startProjectImport('git');break;
      case 'dashboard':showView('dashboard');break;
      case 'library':showView('history');break;
      case 'admin':showView('admin');break;
      case 'monitoring':showView('monitoring');break;
      case 'activity':showView('activity');break;
    }
  }finally{routeMuted=false;}
}
