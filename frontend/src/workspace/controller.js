/**
 * Compatibility controller extracted from the former single-page script.
 * React renders the page components; this module retains the advanced editor.
 * Window bindings exist only for generated editor rows with legacy DOM handlers.
 * New UI state should use React hooks and the typed API client instead.
 */
import { requestJson } from '../api/client'
import { resolveRoute } from '../routing/routes'

let projects=[],currentProject=null,editingProjectId=null,newTestName='',importAfterProject=false,savedWorkloads=[];
let currentPlanId=null, currentScriptId=null, currentDataFileId=null, currentRunId=null, pollTimer=null;
let planModel=null;        // the editable plan object
let dataColumns=[];        // uploaded data file columns

/* ---------- stepper ---------- */
function goStep(n){
  // the 5 panels live inside the Create view; make sure it is the visible view
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('show', s.id==='view-create'));
  document.querySelectorAll('.sb-item').forEach(b=>b.classList.toggle('active', b.dataset.view==='create'));
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
  });
  window.scrollTo({top:0,behavior:'smooth'});

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
  }
  document.getElementById('modeHint').textContent=MODES[m][2];
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
        (e.example_body?' <span class="dtag">body</span>':'')+'</span></div>').join('');
  } else { h+='<div class="drow" style="border:0"><span class="dv todo">needed</span></div>'; }
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
function convOpenPlan(p){
  if(!p) return;
  if(currentPlanId!==p.plan_id){                    // don't overwrite edits made in review
    currentPlanId=p.plan_id; planModel=p.load_model;
    if(currentProject){planModel.test_name=planModel.test_name||newTestName;attachCurrentTest(p.plan_id);} planRationale=p.rationale||'';
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
    <input placeholder="/path" value="${path}" />
    <input class="bodyInput" placeholder='body JSON e.g. {"user":"demo"}' value='${body}' />
    <button class="iconbtn gbtn" title="Edit body + add dynamic data" onclick="openBodyEditor(this)">✏️</button>
    <button class="iconbtn" onclick="this.parentElement.remove()">×</button>`;
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
    if(!path) return null;
    const ep={method,path};
    if(bodyRaw){ try{ep.example_body=JSON.parse(bodyRaw)}catch(e){throw new Error(`Body for ${method} ${path} isn't valid JSON: ${e.message}`)} }
    return ep;
  }).filter(Boolean);
}

async function loadTools(){
  const j=await (await fetch('/api/tools')).json();
  document.getElementById('tool').innerHTML=j.tools.map(t=>`<option value="${t}">${t}</option>`).join('');
}

/* ---------- draft plan ---------- */
async function doPlan(){
  if(!currentProject||!newTestName){showNewTestForm();return;}
  const status=document.getElementById('planStatus');
  let eps; try{eps=readEndpoints()}catch(e){status.className='statusline err';status.textContent=e.message;return;}
  if(!eps.length){status.className='statusline err';status.textContent='Add at least one endpoint.';return;}
  status.className='statusline';status.textContent='Asking the AI to draft a plan…';
  document.getElementById('planBtn').disabled=true;
  try{
    const body={project_id:currentProject.project_id,test_name:newTestName,environment:currentProject.environment||'',target_base_url:document.getElementById('target').value.trim(),
      goal:document.getElementById('goal').value.trim(),
      max_users:parseInt(document.getElementById('maxUsers').value),
      duration_seconds:parseInt(document.getElementById('duration').value),
      profile_type:document.getElementById('profileType').value,
      endpoints:eps};
    const r=await fetch('/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'plan failed');
    currentPlanId=j.plan_id; planModel=j.load_model; planRationale=j.rationale||'';
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
  if(e.grounded){ el.className='rv-chip ok'; el.textContent='✅ Plan matches what you asked for ('+e.passed+'/'+e.total+' checks)';
    el.title='Grounding checks: the plan only uses the target and endpoints you gave.'; }
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
  if(c.kind==='json_path')     return 'Field '+c.path+' '+c.op+' '+c.value;
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
function renderSummary(){
  const el=document.getElementById('planSummary'); if(!el||!planModel) return;
  el.style.display='block';
  const scs=planModel.scenarios||[];
  const total=scs.reduce((a,s)=>a+(s.weight||0),0)||1;
  // peak users + duration from the load profile
  const stages=(planModel.load_profile&&planModel.load_profile.stages)||[];
  const peak=stages.reduce((m,s)=>Math.max(m,s.target_users||0),0);
  const dur=stages.reduce((a,s)=>a+(s.duration_seconds||0),0);
  // journeys
  const journeys=scs.map(s=>{
    const pct=Math.round((s.weight/total)*100);
    const steps=(s.steps||[]).map(st=>st.path).join(' → ');
    return `<li><b>${pct}%</b> will do <b>${esc(s.name)}</b> <span class="muted">(${esc(steps)})</span></li>`;
  }).join('');
  // thresholds in plain words
  const thr=(planModel.thresholds||[]).map(t=>{
    const m={p95_ms:'95% of responses',p99_ms:'99% of responses',p50_ms:'half of responses',
             avg_ms:'average response',error_rate:'error rate'}[t.metric]||t.metric;
    if(t.metric==='error_rate'){ const pct=(t.value*100).toFixed(t.value<0.01?1:0);
      return `the ${m} stays ${t.op.includes('<')?'under':'over'} ${pct}%`; }
    return `${m} ${t.op.includes('<')?'stay under':'exceed'} ${t.value} ms`;
  });
  const thrText = thr.length ? ('It <b>passes</b> if '+thr.join(' and ')+'.') :
    'No pass/fail thresholds are set yet — add some below so the result can be judged.';
  // auth note
  const hasAuth = Object.keys(planModel.headers||{}).some(k=>k.toLowerCase()==='authorization');
  const authNote = hasAuth ? ' It logs in first and carries the login token through the protected steps automatically.' : '';
  el.innerHTML =
    `<h4>📋 What this test will do</h4>`+
    `<p>It simulates up to <b>${peak||'?'} users</b> over <b>${dur||'?'} seconds</b> doing ${scs.length} ${scs.length===1?'journey':'journeys'}:${authNote}</p>`+
    `<ul>${journeys}</ul>`+
    `<p>${thrText}</p>`+
    (planRationale ? `<div class="why"><b>Why the AI planned it this way:</b> ${esc(planRationale)}</div>` : '');
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
  document.getElementById('pfShape').textContent = l.stages.length
    ? 'Load shape: '+l.stages.map(s=>s.target_users+' users for '+s.duration_seconds+'s').join(' → ') : '';
}
async function updateLoad(){
  const users=parseInt(document.getElementById('pfUsers').value,10);
  const duration=parseInt(document.getElementById('pfDuration').value,10);
  const status=document.getElementById('genStatus');
  if(!(users>0) || !(duration>0)){ status.className='statusline err'; status.textContent='Peak users and duration must be whole numbers above 0.'; return; }
  try{
    const r=await fetch('/api/load-profile',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({type:document.getElementById('pfType').value,max_users:users,duration_seconds:duration})});
    const j=await r.json(); if(!r.ok) throw new Error('that load size is not valid');
    const arrival=planModel.load_profile.arrival_rate, vus=planModel.load_profile.pre_allocated_vus;
    planModel.load_profile={...j.load_profile,arrival_rate:arrival,pre_allocated_vus:vus||10};
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
    dz.innerHTML='📁 Click to upload a CSV / TSV / TXT / JSON file'; return; }
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
    '<select id="rowMode" onchange="dataRowMode=this.value;renderDataCard()">'+
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
        <span class="muted" style="font-size:11px;white-space:nowrap">Traffic share<i class="infohint" data-tip="What share of virtual users run this journey. With several journeys the sliders split your users (e.g. 70% browse, 30% checkout). With one journey it is always 100%.">i</i></span>
        ${(planModel.scenarios||[]).length>1
          ? `<input type="range" min="1" max="10" step="1" value="${Math.max(1,Math.round(sc.weight*10)||1)}" oninput="setWeight(${si},this.value)" aria-label="Traffic share"/>`
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
        <input style="width:170px;margin:0;padding:5px 8px" value="${esc(ex.path)}" placeholder="${ph}" oninput="setExtract(${si},${sti},'path',this.value)"/>
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
  const opts=[['fixed','Fixed value'],['file','From data file'],['generated','Generated']];
  if(c.source==='captured') opts.push(['captured','From an earlier step']);
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
    const have=capturedVars().has(c.token);
    val=`<div class="rd-val"><code class="k">${esc(c.token)}</code>`+(have
        ? '<span class="muted" style="font-size:12px">captured from an earlier response</span>'
        : (dataFileInfo
            ? '<span style="font-size:12px;color:var(--amber)">⚠ not a column of the data file and not captured — it would be sent empty</span>'
            : '<span style="font-size:12px;color:var(--amber)">⚠ no source yet — upload a data file with this column, or choose another source</span>'))+'</div>';
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
function rdSet(fi,value,rerender){ const {t,body}=rdTarget(fi); setAt(body,t.path,value); if(rerender) renderPlanForm(); }
function setFieldSource(fi,src){
  const {t,body}=rdTarget(fi); const cur=getAt(body,t.path);
  if(src==='fixed') return rdSet(fi, typeof cur==='string'&&/\$\{/.test(cur)?'':cur, true);
  if(src==='generated') return rdSet(fi,'${uuid}',true);
  if(src==='file'){
    if(!(dataColumns||[]).length){
      const sec=document.getElementById('dz'); renderPlanForm();
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
  const ops=['eq','ne','gt','lt','contains'];
  const opOpts=ops.map(o=>`<option ${o===a.op?'selected':''}>${o}</option>`).join('');
  return `<div style="display:flex;gap:6px;align-items:center;margin-bottom:5px;flex-wrap:wrap;background:#f7faf8;padding:6px 8px;border-radius:8px">`+
    `<span style="color:var(--teal-d)">✔</span>`+
    `<select style="width:auto;padding:4px 7px" onchange="setAssert(${si},${sti},${ai},'kind',this.value);renderPlanForm()">${typeOpts}</select>`+
    (ct.path?`<input style="width:100px;padding:4px 7px" value="${esc(a.path||'')}" placeholder="field" oninput="setAssert(${si},${sti},${ai},'path',this.value)"/>`+
      `<select style="width:auto;padding:4px 7px" onchange="setAssert(${si},${sti},${ai},'op',this.value)">${opOpts}</select>`:'')+
    `<input style="width:130px;padding:4px 7px" value="${esc(a.value||'')}" placeholder="${ct.vph}" oninput="setAssert(${si},${sti},${ai},'value',this.value)"/>`+
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
function setWeight(si,v){ planModel.scenarios[si].weight=(+v)/10; updateWeightBadges(); renderSummary(); }
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
    currentScriptId=j.script_id;
    document.getElementById('scriptOut').textContent=j.content;
    document.getElementById('dlBtn').disabled=false;
    document.getElementById('runBtn').disabled=(j.tool!=='k6');
    document.getElementById('preflightBtn').disabled=false;
    document.getElementById('validateBtn').disabled=false;
    setGitExport(j.tool==='k6', '');
    document.getElementById('scriptMeta').textContent=`${j.filename} (${j.tool}) — from plan ${j.plan_id.slice(0,8)}`;
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
function download(){ if(currentScriptId) location=`/api/scripts/${currentScriptId}/download`; }

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
      r.thresholds.map(t=>`<tr><td>${esc(t.metric)}</td><td><code class="k">${esc(t.threshold)}</code></td><td><span class="pill ${t.passed?'pass':'fail'}">${t.passed?'passed':'failed'}</span></td></tr>`).join('')+'</tbody></table>':''}`).join('');
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
function toggleEditScript(){
  const pre=document.getElementById('scriptOut'); const ta=document.getElementById('scriptEdit');
  const editing = ta.style.display==='none';
  if(editing){
    ta.value=pre.textContent; ta.style.display='block'; pre.style.display='none';
    document.getElementById('editNote').style.display='block';
    document.getElementById('editBtn').textContent='✓ Done editing';
    document.getElementById('regenBtn').style.display='inline-flex';
  } else {
    pre.textContent=ta.value; ta.style.display='none'; pre.style.display='block';
    document.getElementById('editNote').style.display='none';
    document.getElementById('editBtn').textContent='✏️ Edit script';
    _scriptEdited=true;
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
  return (ta.style.display!=='none') ? ta.value : document.getElementById('scriptOut').textContent;
}
// If the script was edited, upload it as an existing script and return the new id.
async function ensureScriptId(){
  if(!_scriptEdited) return currentScriptId;
  const content=currentScriptText();
  const target=(planModel&&planModel.target_base_url)||document.getElementById('target').value||'';
  const r=await fetch('/api/scripts/upload',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content, target_base_url:target, tool:'k6'})});
  const j=await r.json(); if(!r.ok) throw new Error(j.detail||'could not save edited script');
  currentScriptId=j.script_id; _scriptEdited=false;
  return currentScriptId;
}

async function runScript(smoke=false){
  if(pollTimer||runStarting){showError("Wait for the active run to finish first.");return;}
  runStarting=true;
  try{
  if(!currentScriptId){showError('Generate or import a script before running.');return;}
  try{ await ensureScriptId(); }catch(e){ showError(e.message); return; }
  goStep(4);
  const rs=document.getElementById('runStatus'); rs.className='statusline'; rs.textContent='Starting run…';
  try{ const av=await (await fetch('/api/run/available')).json();
    if(!av.k6){ rs.className='statusline err'; rs.textContent='The load engine is not available on this platform. Ask your administrator to set PERFAGENT_K6_PATH.'; return; } }catch(e){}
  try{
    const r=await fetch(`/api/scripts/${currentScriptId}/run`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({smoke,release_label:document.getElementById('releaseLabel').value,baseline_id:smoke?null:getSelectedBaseline()})}); const j=await r.json();
    if(!r.ok) throw new Error(j.detail||'run failed');
    currentRunId=j.run_id; resetChart(); document.getElementById('runBtn').disabled=true;
    document.getElementById('stopBtn').disabled=false; pollTimer=setInterval(pollRun,500);
  }catch(e){ rs.className='statusline err'; rs.textContent='Error: '+e.message; }
  }finally{runStarting=false;}
}
async function pollRun(){
  if(!currentRunId) return;
  try{
    const response=await fetch(`/api/runs/${currentRunId}`);
    if(!response.ok)throw new Error('Unable to refresh run status.');
    const j=await response.json();
    const rs=document.getElementById('runStatus'); const pill=document.getElementById('runPill');
    pill.textContent=j.status; pill.className='pill '+(j.status==='running'?'pass':j.status==='finished'?'pass':j.status==='error'?'fail':'ghost');
    const s=j.snapshot||{}; const lat=s.latency||{}; window._lastSnap=s; window._lastElapsed=j.elapsed_s;
    document.getElementById('mElapsed').textContent=(j.elapsed_s??0)+'s';
    document.getElementById('mReqs').textContent=s.requests??0;
    document.getElementById('mRps').textContent=s.rps??0;
    document.getElementById('mErr').textContent=((s.error_rate??0)*100).toFixed(2)+'%';
    document.getElementById('mP95').textContent=(lat.p95_ms??0)+' ms';
    document.getElementById('mP99').textContent=(lat.p99_ms??0)+' ms';
    pushChart(j.elapsed_s??0, s.rps??0, lat.p95_ms??0, s.error_rate??0);
    document.querySelector('#epTable tbody').innerHTML=(s.per_endpoint||[]).map(e=>
      `<tr><td>${esc(e.name)}</td><td>${e.requests}</td><td>${e.failed}</td><td>${e.avg_ms}</td><td>${e.p95_ms}</td></tr>`).join('');
    // live logs
    const logs=j.logs||[];
    if(logs.length){
      const pre=document.getElementById('runLogs');
      const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
      pre.textContent=logs.join('\n');
      document.getElementById('logCount').textContent='('+logs.length+' lines)';
      if(atBottom) pre.scrollTop=pre.scrollHeight;   // autoscroll unless user scrolled up
    }
    if(j.status==='starting'||j.status==='preparing'){ rs.className='statusline'; rs.textContent=j.message||'Starting…'; }
    else if(j.status==='running'){ rs.className='statusline'; rs.textContent='Running against '+j.target+' …'; }
    else{
      clearInterval(pollTimer); pollTimer=null;
      document.getElementById('runBtn').disabled=false; document.getElementById('stopBtn').disabled=true;
      if(j.status==='finished'){ rs.className='statusline ok'; rs.textContent='Run finished.'; loadReport(); }
      else if(j.status==='stopped'){ rs.className='statusline'; rs.textContent='Run stopped.'; loadReport(); }
      else{ rs.className='statusline err'; rs.textContent='Run error: '+(j.message||'unknown'); }
    }
  }catch(e){const status=document.getElementById('runStatus');status.className='statusline err';status.textContent='Status update failed: '+e.message+' Retrying...';}
}
async function stopRun(){if(!currentRunId)return;try{const r=await fetch(`/api/runs/${currentRunId}/stop`,{method:'POST'});if(!r.ok)throw Error('Stop request failed.');}catch(e){showError(e.message);}}

/* ---------- report ---------- */
async function loadReport(){
  if(!currentRunId) return;
  try{
    const r=await fetch(`/api/runs/${currentRunId}/report`); const j=await r.json(); if(!r.ok)throw Error(j.detail||'Report could not be loaded.');
    renderReport(j);
  }catch(e){showError(e.message+' Reopen the run from History to retry.');}
}


/* ---------- report charts: time-series + trend ---------- */
function _lineChart(canvas, series, opts){
  // series: [{data:[{x,y}], color, label}], opts:{yLabel}
  const c=canvas; if(!c) return;
  const dpr=window.devicePixelRatio||1; const W=c.clientWidth||600, H=150;
  c.width=W*dpr; c.height=H*dpr; const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  const pad=30;
  series=series.map(s=>({...s,data:s.data.filter(p=>p.y!=null&&Number.isFinite(Number(p.y)))}));
  const allY=series.flatMap(s=>s.data.map(p=>p.y));
  const allX=series.flatMap(s=>s.data.map(p=>p.x));
  if(allY.length<1){ x.fillStyle='#9aa'; x.font='11px system-ui'; x.fillText('no data yet',10,20); return; }
  const maxY=Math.max(1,...allY), minX=Math.min(...allX), maxX=Math.max(...allX);
  const sx=v=>pad+((v-minX)/((maxX-minX)||1))*(W-pad*1.4);
  const sy=v=>H-pad-(v/maxY)*(H-pad*1.5);
  // axes
  x.strokeStyle='#e7e9e5'; x.lineWidth=1; x.beginPath(); x.moveTo(pad,8); x.lineTo(pad,H-pad); x.lineTo(W-6,H-pad); x.stroke();
  x.fillStyle='#9aa'; x.font='10px system-ui'; x.fillText(maxY.toFixed(maxY<10?1:0),4,14);
  series.forEach(s=>{
    if(s.data.length<1) return;
    x.beginPath(); x.strokeStyle=s.color; x.lineWidth=2;
    s.data.forEach((p,i)=>{ const px=sx(p.x),py=sy(p.y); i?x.lineTo(px,py):x.moveTo(px,py); });
    x.stroke();
    // dots for trend (few points)
    if(s.data.length<=12){ x.fillStyle=s.color; s.data.forEach(p=>{ x.beginPath(); x.arc(sx(p.x),sy(p.y),2.5,0,7); x.fill(); }); }
  });
}
function drawTsChart(samples){
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
  renderReportDetails(j);
  document.getElementById('rerunBtn').disabled=!reportContext.planId;
  document.getElementById('rerunNote').textContent=reportContext.scriptId?'Uses the script saved with this report.':reportContext.planId?'Older report: opens the saved plan for review before running.':'This report has no saved plan to rerun.';
  try{
    const v=j.verdict.overall_passed;
    const hero=document.getElementById('verdictHero');
    hero.className='rpt-hero '+(v===true?'pass':v===false?'fail':'na');
    document.getElementById('verdictEmoji').textContent=v===true?'✅':v===false?'❌':'⚠️';
    // Metrics belong to this report; older reports can have unavailable fields.
    const s=j.snapshot||{}; const lat=s.latency||{};
    const setK=(id,val)=>{const el=document.getElementById(id); if(el) el.textContent=val;};
    setK('kRequests', s.requests==null?'Unavailable':s.requests.toLocaleString());
    const er=s.error_rate==null?null:s.error_rate*100; const erEl=document.getElementById('kErr');
    if(erEl){ erEl.textContent=er==null?'Unavailable':er.toFixed(2)+'%'; erEl.classList.toggle('bad', er>0); }
    setK('kRps', s.rps==null?'Unavailable':s.rps.toFixed(2)+'/s');
    setK('kP95', lat.p95_ms==null?'Unavailable':lat.p95_ms+' ms');
    setK('kP99', lat.p99_ms==null?'Unavailable':lat.p99_ms+' ms');
    setK('kAvg', lat.avg_ms==null?'Unavailable':lat.avg_ms+' ms');
    drawTsChart(j.samples||[]); loadTrend(reportContext.planId);

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
        ? `<div class="note err" style="margin:0 0 8px">${failing} check${failing>1?'s':''} failing — these count as errors and fail the run.</div>`
        : `<div class="note ok" style="margin:0 0 8px">All response checks passed.</div>`;
      cb.innerHTML=head+'<table><thead><tr><th>Check</th><th>Passed</th><th>Result</th></tr></thead><tbody>'+
        chk.map(c=>{
          const ok=c.failed===0;
          return `<tr><td>${esc(c.name)}</td><td>${c.passed}/${c.total}</td>`+
            `<td style="color:${ok?'#0f7a5f':'#b4342b'};font-weight:600">${ok?'✓ pass':'✗ fail'}</td></tr>`;
        }).join('')+'</tbody></table>';
    } else if(cc){ cc.style.display='none'; }

    document.getElementById('verdictHeadline').textContent=v===true?'PASS — all thresholds met':v===false?'FAIL — a threshold was breached':'INCONCLUSIVE — a threshold could not be evaluated';
    const n=j.narrative;
    document.getElementById('verdictSub').textContent=n.headline||'';
    document.getElementById('reportSummary').textContent=n.summary||'';
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

function downloadReport(){const id=reportContext?.savedId;if(id)location='/api/runs/'+encodeURIComponent(id)+'/report/download';else showError('Open a report before downloading.');}



/* ---------- AI call traces ---------- */
async function loadTraces(){
  try{
    const response=await fetch('/api/traces?limit=100'); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    const sc={plan:'#534ab7',chat:'#2563a8',dynamize:'#9a6412',narrate:'#0f7a5f'};
    const realTraces=(j.traces||[]).filter(t=>(t.total_tokens>0)||(t.model&&t.model.trim())||t.status==='error');
    document.querySelector('#tracesTable tbody').innerHTML=realTraces.map(t=>{
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
  }catch(e){showError('AI traces could not be loaded: '+e.message);}
}

/* ---------- activity log ---------- */
async function loadAudit(){
  refreshUsage();
  try{
    const response=await fetch('/api/audit?limit=100'); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    const colors={'plan.created':'#2563a8','plan.approved':'#9a6412','script.generated':'#0f6e56',
      'script.downloaded':'#6b7280','run.started':'#9a6412','run.finished':'#0f6e56'};
    document.querySelector('#auditTable tbody').innerHTML=(j.events||[]).map(e=>{
      const c=colors[e.action]||'#6b7280';
      const tok = e.tokens ? (e.tokens.toLocaleString()+' tok'+(e.cost_usd?(' · $'+e.cost_usd.toFixed(4)):'')) : '';
      return `<tr><td>${new Date(e.created_at).toLocaleString()}</td>`+
             `<td><b style="color:${c}">${esc(e.action)}</b></td>`+
             `<td>${esc(e.target||'')}</td><td>${esc(e.summary||'')}</td>`+
             `<td style="color:var(--muted);white-space:nowrap">${tok}</td></tr>`;
    }).join('')||'<tr><td colspan="5" class="muted">No activity yet.</td></tr>';
  }catch(e){showError('Activity could not be loaded: '+e.message);}
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
  if(k==='p95_ms'||k==='p99_ms'||k==='avg_ms') return (+v).toFixed(2)+' ms';
  if(k==='rps') return (+v).toFixed(2)+'/s';
  if(k==='run_id') return String(v).slice(0,8);
  return v;
}
function sdVerdict(v){
  const m={pass:['pass','PASS'],fail:['fail','FAIL'],inconclusive:['na','INCONCLUSIVE']}[v]||['ghost',(v||'?').toUpperCase()];
  return '<span class="pill '+m[0]+'">'+m[1]+'</span>';
}
async function loadStakeholder(offset=0){
  const request=++dashboardRequest;
  const role=document.getElementById('sdRole').value;
  const head=document.getElementById('sdHead');
  const body=document.querySelector('#sdTable tbody');
  const empty=document.getElementById('sdEmpty');
  const tiles=document.getElementById('sdTiles');
  let runs=[];
  const targetField=document.getElementById('sdTarget');
  targetField.disabled=role==='viewer';
  if(targetField.disabled) targetField.value='';
  const from=document.getElementById('sdFrom').value,to=document.getElementById('sdTo').value;
  if(from&&to&&from>to){showError('From date must be before the through date.');return;}
  dashboardOffset=offset;
  document.getElementById('sdPage').textContent='Loading runs...';
  try{
    const query=new URLSearchParams({role,limit:'50',offset:String(offset),project_id:currentProject.project_id});
    if(document.getElementById('sdTest').value)query.set('plan_id',document.getElementById('sdTest').value);
    if(targetField.value.trim())query.set('target',targetField.value.trim());
    if(document.getElementById('sdVerdict').value)query.set('verdict',document.getElementById('sdVerdict').value);
    if(from)query.set('since',new Date(from+'T00:00:00').toISOString());
    if(to){const end=new Date(to+'T00:00:00');end.setDate(end.getDate()+1);query.set('until',end.toISOString());}
    const response=await fetch('/api/reporting/runs?'+query);
    if(!response.ok) throw new Error('Runs could not be loaded. Please refresh to try again.');
    const j=await response.json();
    if(request!==dashboardRequest)return;
    runs=j.runs||[];
    const total=j.total??runs.length;
    document.getElementById('sdPage').textContent=total?(offset+1)+' - '+(offset+runs.length)+' of '+total+' runs':'No matching runs';
    document.getElementById('sdPrev').disabled=offset===0;
    document.getElementById('sdNext').disabled=offset+runs.length>=total;
  }catch(e){ if(request!==dashboardRequest)return; document.getElementById('sdPage').textContent='Could not load runs'; tiles.innerHTML=''; document.getElementById('sdComparison').textContent='Comparison unavailable. Refresh to retry.'; dashboardRuns=[]; empty.style.display='none'; ['sdTrend','sdErrTrend','sdDonut','sdBars'].forEach(id=>_lineChart(document.getElementById(id),[])); document.getElementById('sdPrev').disabled=true;document.getElementById('sdNext').disabled=true; body.innerHTML='<tr><td class="muted">Could not load: '+esc(e.message)+'</td></tr>'; return; }

  if(request!==dashboardRequest) return;
  document.getElementById('sdFilterNote').textContent='Filters search all saved runs. Summaries and charts show this page.';
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

  const total=runs.length;
  const passes=runs.filter(r=>r.verdict==='pass').length;
  const p95s=runs.map(r=>r.p95_ms).filter(v=>v!=null);
  const worst=p95s.length?Math.max(...p95s):null;
  tiles.innerHTML=
    '<div class="tile"><div class="v">'+total+'</div><div class="l">Runs</div></div>'+
    '<div class="tile"><div class="v">'+(total?Math.round(100*passes/total):0)+'%</div><div class="l">Pass rate</div></div>'+
    '<div class="tile"><div class="v">'+(worst!=null?worst.toFixed(2)+' ms':'—')+'</div><div class="l">Worst p95</div></div>';

  // extra charts
  const passes2=runs.filter(r=>r.verdict==='pass').length;
  const fails=runs.filter(r=>r.verdict==='fail').length;
  const inconc=runs.filter(r=>r.verdict==='inconclusive').length;
  _donut(document.getElementById('sdDonut'),[
    {l:'Pass',v:passes2,c:'#0f7a5f'},{l:'Fail',v:fails,c:'#b4342b'},{l:'Inconc.',v:inconc,c:'#9a6412'}]);
  // latency bars from the most recent run (first row, since newest-first)
  const latest=runs[0]||{};
  _bars(document.getElementById('sdBars'),[
    {l:'p50',v:latest.p50_ms!=null?latest.p50_ms:null,c:'#2f7d5b'},
    {l:'p95',v:latest.p95_ms!=null?latest.p95_ms:null,c:'#9a6412'},
    {l:'p99',v:latest.p99_ms!=null?latest.p99_ms:null,c:'#b4342b'}]);
  const chronological=[...runs].reverse();
  _lineChart(document.getElementById('sdTrend'),[{data:chronological.map((r,i)=>({x:i,y:r.p95_ms})),color:'#9a6412'}]);
  _lineChart(document.getElementById('sdErrTrend'),[{data:chronological.map((r,i)=>({x:i,y:r.error_rate==null?null:r.error_rate*100})),color:'#b4342b'}]);
}
async function sdDrawTrend(){
  const c=document.getElementById('sdTrend');
  let p95=[], err=[];
  try{ const j=await (await fetch('/api/reporting/trend?metric=p95_ms&limit=30')).json(); p95=j.points||[]; }catch(e){}
  try{ const j=await (await fetch('/api/reporting/trend?metric=error_rate&limit=30')).json(); err=j.points||[]; }catch(e){}
  if(c) _lineChart(c,[{data:p95.map((p,i)=>({x:i,y:p.value})),color:'#9a6412'}]);
  const ce=document.getElementById('sdErrTrend');
  if(ce) _lineChart(ce,[{data:err.map((p,i)=>({x:i,y:(p.value||0)*100})),color:'#b4342b'}]);
}


function resetDashboardFilters(){
  ['sdTest','sdTarget','sdVerdict','sdFrom','sdTo'].forEach(id=>document.getElementById(id).value='');
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
  host.innerHTML=(a.workload_version&&b.workload_version&&a.workload_version!==b.workload_version?'<p class="note warn">Different workload versions: these runs may use different loads, thresholds or data.</p>':'')+(a.target&&b.target&&a.target!==b.target?'<p class="note warn">These runs use different targets.</p>':'')+'<table><thead><tr><th>Metric</th><th>Baseline</th><th>Comparison</th><th>Change</th></tr></thead><tbody>'+metrics.map(([k,label])=>{
    let change='Unavailable';
    if(a[k]!=null&&b[k]!=null){const delta=Number(b[k])-Number(a[k]);change=(delta>0?'+':'')+(k==='error_rate'?(delta*100).toFixed(2)+' percentage points':delta.toFixed(2)+(k.endsWith('_ms')?' ms':k==='rps'?'/s':''));}
    return '<tr><td>'+label+'</td><td>'+esc(sdFmt(k,a[k]))+'</td><td>'+esc(sdFmt(k,b[k]))+'</td><td>'+change+'</td></tr>';
  }).join('')+'</tbody></table><p class="muted">Lower latency and errors are better; higher throughput is better. Compare similar load profiles.</p>';
}
async function rerunReport(){
  if(!reportContext||!reportContext.planId) return;
  const context={...reportContext},button=document.getElementById('rerunBtn');
  button.disabled=true;
  try{
    if(!context.scriptId){await openPlan(context.planId);return;}
    if(pollTimer) throw new Error('Wait for the active run to finish before starting another.');
    const response=await fetch('/api/scripts/'+encodeURIComponent(context.scriptId)+'/download');
    if(!response.ok) throw new Error('The original script is no longer available. Open the saved plan in History.');
    const content=await response.text();
    currentScriptId=context.scriptId; currentPlanId=context.planId; currentDataFileId=null; _scriptEdited=false;
    document.getElementById('scriptOut').textContent=content;
    await runScript();
  }catch(e){document.getElementById('rerunNote').textContent=e.message;}
  finally{button.disabled=false;}
}

/* ---------- runs & reports history ---------- */
async function loadRuns(){
  try{
    const response=await fetch('/api/runs?limit=50'+projectQuery()); if(!response.ok)throw Error('Request failed ('+response.status+')'); const j=await response.json();
    const badge=(v)=>{const m={pass:['pass','PASS'],fail:['fail','FAIL'],inconclusive:['na','INCONCLUSIVE']}[v]||['ghost',(v||'?').toUpperCase()];
      return '<span class="pill '+m[0]+'">'+m[1]+'</span>';};
    document.querySelector('#runsTable tbody').innerHTML=(j.runs||[]).map(r=>
      `<tr><td>${new Date(r.created_at).toLocaleString()}</td>`+
      `<td>${badge(r.verdict)}</td>`+
      `<td>${esc(r.target||'')}</td><td><b>${esc(r.test_name||r.goal||'Unnamed test')}</b><br>${esc(r.script_name||'Not recorded')}<br><span class="muted">${esc(r.mode||'full')} | ${esc(r.endpoint_summary||'')}</span></td>`+
      `<td>${(r.requests||0).toLocaleString()}</td>`+
      `<td>${((r.error_rate||0)*100).toFixed(2)}%</td>`+
      `<td>${(r.p95_ms||0)} ms</td>`+
      `<td>${r.has_report?`<button class="btn sec sm" onclick="openSavedReport('${r.run_id}')">Open report</button>`:''}</td></tr>`
    ).join('') || '<tr><td colspan="8" class="muted">No runs yet — run a test to see it here.</td></tr>';
  }catch(e){showError('Run history could not be loaded: '+e.message);}
}
async function openSavedReport(id){
  try{
    const r=await fetch(`/api/runs/${id}/saved-report`); const j=await r.json();
    if(!r.ok){ alert('Could not open report: '+(j.detail||'not found')); return; }
    renderReport({...j,saved_result_id:id});
    goStep(5);
  }catch(e){ alert('Error opening report: '+e.message); }
}

async function loadPlans(){
  try{
  if(!currentProject)return;
  const response=await fetch('/api/plans?project_id='+encodeURIComponent(currentProject.project_id));if(!response.ok)throw Error('Plans could not be loaded.');
  const j=await response.json();
  document.querySelector('#plansTable tbody').innerHTML=j.plans.map(p=>
    `<tr class="histrow"><td>${new Date(p.created_at).toLocaleString()}</td><td>${esc(p.target)}</td>
     <td>${esc(p.goal||'')}</td><td>${p.script_count}</td>
     <td><button class="btn ghost sm" onclick="openPlan('${p.plan_id}')">Open</button></td></tr>`).join('');
  }catch(e){showError(e.message);}
}
async function openPlan(id){
  document.getElementById('importNote').style.display='none';
  applyIntegrations(id);
  const j=await (await fetch(`/api/plans/${id}`)).json();
  currentPlanId=id; planModel=j.load_model; planRationale=''; renderPlanForm(); renderRawFromModel();
  document.getElementById('guardrailBadge').style.display='none';
  document.getElementById('planEval').style.display='none';
  document.getElementById('planMeta').style.display='inline-flex';
  document.getElementById('planMeta').textContent='loaded · '+j.scripts.length+' script(s)';

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
      document.getElementById('scriptMeta').textContent=`${latest.filename} (${latest.tool}) — from saved plan ${id.slice(0,8)}`;
      const pill=document.getElementById('scriptPill'); pill.style.display='inline-flex'; pill.textContent=latest.tool;
    }catch(e){ /* fall back to review step */ }
  }
  // land on the Script step if a script is ready, else the Review step
  goStep(currentScriptId ? 3 : 2);
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
  d.innerHTML=`<input placeholder="Header name e.g. Authorization" value="${esc(k)}"/>
    <input placeholder="Value e.g. Bearer xxx" value="${esc(v)}"/>
    <button class="iconbtn" onclick="this.parentElement.remove();renderConnCount()">×</button>`;
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
      el.innerHTML='✅ <b>Script validation passed</b> — syntax and configuration checked without sending traffic. Use pre-flight to check endpoints.';
    } else if(j.status==='k6_missing'){
      el.className='note warn'; el.textContent='⚠ '+j.message;
    } else {
      el.className='note err';
      el.innerHTML='🔴 <b>Script failed validation</b> — fix this before a full run:<br><pre style="margin:6px 0 0;max-height:160px;font-size:11px">'+esc(j.detail||j.message)+'</pre>';
    }
  }catch(e){ el.className='note err'; el.textContent='Validation error: '+e.message; }
}

/* ---------- pre-flight check ---------- */
async function doPreflight(){
  const el=document.getElementById('preflightResult'); el.style.display='flex'; el.className='note info';
  el.textContent='Pre-flight: sending one request per endpoint…';
  try{
    await ensureScriptId();
    if(!currentScriptId) throw new Error('Generate or import a script first.');
    const payload={script_id:currentScriptId};
    const r=await fetch('/api/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'preflight failed');
    const rows=j.results.map(x=>{
      const dot = x.ok ? '🟢' : '🔴';
      const st = x.status!==null ? x.status : (x.error||'no response');
      return `${dot} <b>${x.method}</b> ${esc(x.path)} → ${st}`;
    }).join('<br>');
    el.className = j.all_ok ? 'note ok' : 'note warn';
    el.innerHTML = `<div><b>Pre-flight: ${j.ok}/${j.total} endpoints responded OK</b>` +
      (j.all_ok ? ' — endpoint requests succeeded; review authentication and response checks before running.' : ' — check the failures below before a full run.') +
      `<div style="margin-top:6px">${rows}</div></div>`;
  }catch(e){ el.className='note err'; el.textContent='Pre-flight error: '+e.message; }
}

/* ---------- live chart ---------- */
let chartData=[];  // [{t, rps, p95}]
function resetChart(){ chartData=[]; drawChart(); }
function pushChart(elapsed, rps, p95, err){ chartData.push({t:elapsed,rps:rps||0,p95:p95||0,err:(err||0)*100}); if(chartData.length>300) chartData.shift(); drawChart(); }
function drawChart(){
  const c=document.getElementById('liveChart'); if(!c) return;
  const dpr=window.devicePixelRatio||1; const W=c.clientWidth||600, H=120;
  c.width=W*dpr; c.height=H*dpr; const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  if(chartData.length<2){ x.fillStyle='#9aa'; x.font='11px system-ui'; x.fillText('waiting for data…',10,20); return; }
  const pad=24; const n=chartData.length;
  const maxRps=Math.max(1,...chartData.map(d=>d.rps));
  const maxP95=Math.max(1,...chartData.map(d=>d.p95));
  function line(key,max,color){
    x.beginPath(); x.strokeStyle=color; x.lineWidth=2;
    chartData.forEach((d,i)=>{
      const px=pad + (i/(n-1))*(W-pad*2);
      const py=H-pad - (d[key]/max)*(H-pad*1.4);
      i?x.lineTo(px,py):x.moveTo(px,py);
    }); x.stroke();
  }
  line('rps',maxRps,'#0f6e56');   // teal = RPS
  line('p95',maxP95,'#9a6412');   // amber = p95
  x.fillStyle='#6b7280'; x.font='10px system-ui';
  x.fillText('RPS (teal) · p95 ms (amber)',pad,12);
}

/* ---------- sidebar navigation ---------- */
const VIEW_META={
  projects:['Projects','Create a project, open its test library, or import an existing Git framework'],
  admin:['Administrator overview','Run and workload summaries across every project'],
  create:['Create a performance test','AI drafts the plan · you approve · code generates, runs & reports'],
  dashboard:['Stakeholder dashboard','Run history, trends and coverage — scoped to a role'],
  history:['History','Saved plans and every finished run'],
  monitoring:['Monitoring','Your Grafana, Datadog and other dashboards in one place'],
  activity:['Activity','Audit log and AI call traces'],
};
function showView(v){
  if(['dashboard','history'].includes(v)&&!currentProject){showError('Open a project first.');v='projects';}
  document.querySelectorAll('.view').forEach(s=>s.classList.toggle('show', s.id==='view-'+v));
  document.querySelectorAll('.sb-item').forEach(b=>b.classList.toggle('active', b.dataset.view===v));
  const m=VIEW_META[v]||VIEW_META.create;
  document.getElementById('viewTitle').textContent=m[0];
  document.getElementById('viewSub').textContent=m[1];
  if(v==='projects')loadProjects();
  if(v==='dashboard'){loadProjectSummary();loadDashboardTests();loadStakeholder();}
  if(v==='history'){ loadPlans(); loadRuns(); }
  if(v==='activity'){ loadAudit(); loadTraces(); }
  if(v==='monitoring') monRender();
  closeMobNav();
  window.scrollTo({top:0,behavior:'smooth'});

publishView(v);
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
function openMobNav(){ document.getElementById('sidebar').classList.add('mobopen'); document.getElementById('sbBackdrop').classList.add('show'); }
function closeMobNav(){ document.getElementById('sidebar').classList.remove('mobopen'); document.getElementById('sbBackdrop').classList.remove('show'); }

/* ---------- monitoring tools (Grafana / Datadog / etc) ---------- */
const MON_KEY='perfagent.monitors';
function monLoad(){ try{ return JSON.parse(localStorage.getItem(MON_KEY)||'[]'); }catch(e){ return []; } }
function monSave(a){ try{ localStorage.setItem(MON_KEY, JSON.stringify(a)); }catch(e){} }
function monAdd(){
  const tool=document.getElementById('monTool').value;
  const url=document.getElementById('monUrl').value.trim();
  const st=document.getElementById('monStatus');
  if(!/^https?:\/\//.test(url)){ st.className='statusline err'; st.textContent='Enter a full URL starting with http:// or https://'; return; }
  const a=monLoad(); a.push({tool,url}); monSave(a);
  document.getElementById('monUrl').value='';
  st.className='statusline ok'; st.textContent=tool+' dashboard added.';
  monRender();
}
function monRemove(i){ const a=monLoad(); a.splice(i,1); monSave(a); monRender(); }
function monRender(){
  const host=document.getElementById('monList'); if(!host) return;
  const a=monLoad();
  if(!a.length){
    host.innerHTML='<div class="monitor-card"><div class="monitor-empty">No dashboards linked yet. Add your Grafana or other monitoring URL above — it will embed right here.</div></div>';
    return;
  }
  host.innerHTML=a.map((m,i)=>
    '<div class="monitor-card"><div class="monitor-head">'+
      '<span class="tool-chip">'+esc(m.tool)+'</span>'+
      '<span class="url" title="'+esc(m.url)+'">'+esc(m.url)+'</span>'+
      '<div class="spacer"></div>'+
      '<a class="btn ghost sm" href="'+esc(m.url)+'" target="_blank" rel="noopener">Open ↗</a>'+
      '<button class="btn danger sm" onclick="monRemove('+i+')">Remove</button>'+
    '</div>'+
    '<iframe class="monitor-frame" src="'+esc(m.url)+'" loading="lazy" referrerpolicy="no-referrer"></iframe>'+
    '</div>').join('');
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
  return currentProject?{repo_url:currentProject.repo_url||'',branch:currentProject.branch||'main',framework:currentProject.framework_name||'',ci:currentProject.ci||['jenkins'],test:(planModel?.test_name||newTestName||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}:{};
}
async function projectApi(url,options){
  return requestJson(url,options);
}
async function loadProjects(){
  try{
    const j=await projectApi('/api/projects');projects=j.projects||[];
    if(currentProject)currentProject=projects.find(p=>p.project_id===currentProject.project_id)||null;
    document.getElementById('projectPicker').innerHTML='<option value="">Select project</option>'+projects.map(p=>'<option value="'+esc(p.project_id)+'">'+esc(p.name)+'</option>').join('');
    document.getElementById('projectPicker').value=currentProject?.project_id||'';
    document.getElementById('projectCards').innerHTML=projects.map(p=>'<div class="card project-card"><h3>'+esc(p.name)+'</h3><p>'+esc(p.description||'Performance test project')+'</p><p>'+esc(p.tests??0)+' tests · '+esc(p.environment||'No default environment')+'</p><button class="btn ghost" data-project-id="'+esc(p.project_id)+'">Open project</button></div>').join('')||'<div class="card"><p>No projects yet. Create a project or import a framework to get started.</p></div>';
    document.querySelectorAll('#projectCards [data-project-id]').forEach(button=>button.onclick=()=>selectProject(button.dataset.projectId));
    renderProjectContext();
  }catch(e){showError(e.message);}
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
  renderProjectContext();showView('projects');

publishRoute(currentProject ? '/projects/' + encodeURIComponent(currentProject.project_id) : '/projects');
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
  if(!currentProject)return;
  const name=document.getElementById('newTestName').value.trim();if(!name){showError('Give this test a name first.');return;}
  if(pollTimer){showError('Wait for the current run to finish before creating another test.');return;}
  convNew();newTestName=name;currentPlanId=null;currentScriptId=null;planModel=null;currentDataFileId=null;_scriptEdited=false;
  document.getElementById('target').value=currentProject.target_url||'';
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
async function attachCurrentTest(id){
  try{await projectApi('/api/plans/'+id+'/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:currentProject.project_id,test_name:planModel?.test_name||newTestName})});}
  catch(e){showError(e.message);}
}
async function loadProjectSummary(){
  if(!currentProject)return;
  try{const j=await projectApi('/api/projects/'+currentProject.project_id+'/dashboard'),s=j.summary;
    document.getElementById('projectDashboardSummary').textContent=currentProject.name+' · '+s.tests+' tests · '+s.runs+' runs · '+Number(s.requests).toLocaleString()+' requests · pass rate '+(s.pass_rate==null?'unavailable':s.pass_rate+'%');}
  catch(e){document.getElementById('projectDashboardSummary').textContent=e.message;}
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
  if(!planModel)return;
  const raw=document.getElementById('pfArrival').value,rate=Number(raw),vus=Number(document.getElementById('pfArrivalVus').value);
  if((raw&&(!Number.isInteger(rate)||rate<1||rate>1000000))||!Number.isInteger(vus)||vus<1||vus>1000000){showError('Use positive whole numbers up to 1,000,000 for iteration rate and preallocated users.');return;}
  planModel.load_profile.arrival_rate=raw?rate:null;
  planModel.load_profile.pre_allocated_vus=vus;renderRawFromModel();
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
    el.innerHTML='<b>Before you run</b><ul>'+j.checks.map(c=>'<li>'+esc(c.name)+': '+(c.ok?'Ready':'Review')+' — '+esc(c.detail)+'</li>').join('')+'</ul><p>'+esc(j.execution.duration_seconds)+' seconds · '+esc(j.execution.peak_users)+' peak users'+(j.execution.arrival_rate?' · '+esc(j.execution.arrival_rate)+' target iterations/s':'')+'</p><p>Reachability and authentication: use Pre-flight check to send one request per endpoint. Validate parses the script without traffic. Use a smoke run to exercise response assertions before full load.</p>';
  }catch(e){el.className='note err';el.textContent=e.message;}
}
function renderReportDetails(j){
  const x=j.execution||{},snap=j.snapshot||{},lat=snap.latency||{};
  document.getElementById('reportContext').textContent=(x.test_name||'Unnamed test')+' | '+(x.script_name||'Script not recorded')+' | '+(x.endpoint_summary||'Endpoints not recorded')+' | '+(j.status||'Recorded')+' · '+(x.mode||'full')+' · environment: '+(x.environment||'unlabeled')+' · release: '+(x.release_label||'unlabeled')+' · workload: '+(x.workload_version?.slice(0,12)||'not recorded')+' · baseline: '+(j.baseline_id?.slice(0,8)||'none')+(j.message?' · '+j.message:'');
  document.getElementById('baselineSelection').textContent=getSelectedBaseline()?'Selected baseline: '+getSelectedBaseline().slice(0,8):'Automatic baseline: previous matching workload.';
  const endpoints=[...(snap.per_endpoint||[])].sort((a,b)=>(b.p95_ms||0)-(a.p95_ms||0));
  const rules=(j.verdict?.checks||[]).map(c=>'<tr><td>'+esc(c.metric)+'</td><td>'+esc(c.op)+' '+esc(c.target)+'</td><td>'+esc(c.actual??'Unavailable')+'</td><td>'+(c.passed===true?'Pass':c.passed===false?'Fail':'Inconclusive')+'</td></tr>').join('');
  document.getElementById('reportDetails').innerHTML='<h2>Measured workload</h2><p>'+esc(lat.samples??'Unavailable')+' latency samples · '+esc(snap.iterations??'Unavailable')+' completed iterations · '+esc(snap.iterations_per_second??'Unavailable')+' achieved iterations/s · '+esc(snap.dropped_iterations??'Unavailable')+' dropped iterations'+(x.arrival_rate?' · '+esc(x.arrival_rate)+' requested iterations/s':'')+'</p>'+(j.status&&j.status!=='finished'?'<p class="note warn">The run did not complete. These are partial measurements, not a passing full test.</p>':'')+'<h3>Threshold results</h3><div class="table-scroll"><table><thead><tr><th>Metric</th><th>Rule</th><th>Measured</th><th>Result</th></tr></thead><tbody>'+rules+'</tbody></table></div><h3>Slowest endpoints</h3><div class="table-scroll"><table><thead><tr><th>Endpoint</th><th>Requests</th><th>Transport failures</th><th>p95</th></tr></thead><tbody>'+endpoints.slice(0,10).map(e=>'<tr><td>'+esc(e.name)+'</td><td>'+esc(e.requests)+'</td><td>'+esc(e.failed)+'</td><td>'+esc(e.p95_ms)+' ms</td></tr>').join('')+'</tbody></table></div>';
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
  // allow going back, or forward only if that step is reachable
  if(n===1) goStep(1);
  else if(n===2 && planModel) goStep(2);
  else if(n===3 && currentScriptId) goStep(3);
  else if(n===4 && currentRunId) goStep(4);
  else if(n===5 && currentRunId) goStep(5);
}, {signal:workspaceEvents.signal}));
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
 if(pollTimer)clearInterval(pollTimer);if(jk.timer)clearInterval(jk.timer);
 if(dashboardFilterTimer)clearTimeout(dashboardFilterTimer);
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
  const path={projects:'/projects',admin:'/admin/overview',monitoring:'/monitoring',activity:'/activity',dashboard:projectPath()+'/dashboard',history:projectPath()+'/tests'}[view];
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
      case 'projects':showView('projects');break;
      case 'new-project':editProject();break;
      case 'project':showView('projects');break;
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
        const plan=await requestJson('/api/plans/'+encodeURIComponent(route.testId));
        if(plan.project_id!==route.projectId)throw Error('This test belongs to another project.');
        await openPlan(route.testId);
        goStep(route.step);
        break;
      }
      case 'report':{
        const report=await requestJson('/api/runs/'+encodeURIComponent(route.runId)+'/saved-report');
        if(report.plan_id){
          const plan=await requestJson('/api/plans/'+encodeURIComponent(report.plan_id));
          if(plan.project_id!==route.projectId)throw Error('This report belongs to another project.');
        }
        renderReport({...report,saved_result_id:route.runId});
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
