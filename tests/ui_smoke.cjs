// Real Edge UI checks with fixture APIs. No external load is generated.
const http=require('http'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const spaMode=process.env.PERFAGENT_UI_MODE!=='legacy';
const webRoot=path.resolve('src/perfagent/web/spa');
const html=fs.readFileSync(spaMode?path.join(webRoot,'index.html'):'src/perfagent/web/index.html');
const projects=[{project_id:'project-a',name:'Commerce',description:'Shop tests',framework_name:'commerce',repo_url:'https://github.com/org/shop.git',branch:'performance',target_url:'http://fixture.test',environment:'staging',tests:3},{project_id:'project-b',name:'Payments',description:'Invoice tests',framework_name:'payments',branch:'main',environment:'staging',tests:1}];
const runs=[
 {run_id:'saved-a',plan_id:'plan-a',project_id:'project-a',created_at:'2026-11-18T10:00:00',target:'https://example.test',verdict:'pass',p95_ms:120,error_rate:.01,requests:100,rps:20,test_name:'Product browsing',script_name:'products.js',mode:'full',endpoint_summary:'GET /products'},
 {run_id:'saved-b',plan_id:'plan-b',project_id:'project-a',created_at:'2026-11-19T10:00:00',target:'https://second.test',verdict:'fail',p95_ms:240,error_rate:.04,requests:200,rps:25,test_name:'Checkout flow',script_name:'checkout.js',mode:'full',endpoint_summary:'POST /checkout'},
 {run_id:'saved-c',plan_id:'plan-c',project_id:'project-a',created_at:'2026-11-19T11:00:00',target:'https://example.test',verdict:'pass',p95_ms:100,error_rate:0,requests:150,rps:20,test_name:'Login flow',script_name:'login.js',mode:'full',endpoint_summary:'POST /login'},
 {run_id:'other-project-run',plan_id:'plan-d',project_id:'project-b',created_at:'2026-11-19T12:00:00',target:'https://payment.test',verdict:'pass',p95_ms:100,requests:100,test_name:'Hidden payment test'}];
const report={run_id:'original-a',plan_id:'plan-a',script_id:'script-a',target:'https://example.test',execution:{test_name:'Product browsing',script_name:'products.js',endpoint_summary:'GET /products'},verdict:{overall_passed:true,checks:[{metric:'p95_ms',op:'<=',target:150,actual:120,passed:true}]},narrative:{headline:'The run met its k6 thresholds',summary:'Product browsing sustained its request target. Tail latency rose during steady load and exceeded the release budget.',observations:[],recommendations:[]},snapshot:{requests:100,error_rate:.01,rps:20,latency:{p95_ms:120,p99_ms:149,avg_ms:81}},logs:['fixture log']};
const releaseDecision={status:'blocked',reason:'p95 change from baseline breached its release budget.',
 environment:'staging',baseline_id:'saved-b',candidate_id:'saved-a',candidate_rps:20,target_rps:20,
 baseline_release:'v1.4.0',candidate_release:'v1.5.0',summary:'p95 latency was 120 ms. The approved baseline was 100 ms.',
 budgets:{max_p95_regression_percent:10},rules:[{name:'p95 change from baseline',actual:20,limit:10,op:'≤',unit:'%',passed:false}]};
const releaseSeries=Array.from({length:12},(_,index)=>({t:(index+1)*5,
  p95:[75,85,93,95,100,98,96,99,101,97,95,94][index],rps:[6,11,17,20,20,21,19,20,21,19,19,20][index],err:0}));
const candidateSeries=releaseSeries.map((sample,index)=>({...sample,
  p95:sample.p95+[1,2,4,8,10,19,24,23,21,19,17,16][index],err:index===7?1:0}));
const releaseComparison={baseline:releaseSeries,candidate:candidateSeries,phases:[{label:'Steady state',start_s:0,end_s:60}],
 endpoints:[{name:'<img src=x onerror=alert(1)>',baseline_ms:100,candidate_ms:120}],
 baseline_metrics:{p95_ms:100,rps:20,error_percent:0},candidate_metrics:{p95_ms:120,rps:21,error_percent:0}};
let savedReleasePolicy, fixtureRunStarts=0;
const profiles={};let lastPlanRequest,browser,ws,server,send;const checks=[],errors=[],downloads=[],validationCalls=[],preflightCalls=[],pending=new Map();let sequence=0;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let showScriptHistoryFixture=false;
let dashboardRequests=0, dashboardDelay=0;
async function main(){
 server=http.createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname.startsWith('/assets/')){
   const asset=path.resolve(webRoot,'.'+pathname);
   if(!asset.startsWith(webRoot+path.sep)||!fs.existsSync(asset)){res.statusCode=404;res.end();return;}
   res.setHeader('Content-Type',asset.endsWith('.css')?'text/css':asset.endsWith('.woff2')?'font/woff2':'application/javascript');res.end(fs.readFileSync(asset));return;
  }
  if(pathname==='/fixture-dashboard'){res.setHeader('Content-Type','text/html');res.end('<title>Service dashboard</title><h1>Service dashboard</h1>');return;}
  if(!pathname.startsWith('/api/')){res.setHeader('Content-Type','text/html');res.end(pathname==='/legacy'?fs.readFileSync('src/perfagent/web/index.html'):html);return;}
  let body={};if(['POST','PUT'].includes(req.method)){let raw='';for await(const chunk of req)raw+=chunk;body=raw?JSON.parse(raw):{};}
  const url=new URL(req.url,'http://localhost'),p=url.pathname;let data={};
  if(p==='/api/projects'){
   if(req.method==='POST'){data={project_id:'project-new',...body,tests:0};projects.push(data);}else data={projects};
  }else if(p==='/api/admin/dashboard'){
   if(req.headers['x-perfagent-admin']!=='fixture-admin'){res.statusCode=403;data={detail:'Administrator access requires the configured admin token'};}
   else data={summary:{tests:4,runs:4,requests:550},projects:projects.map(project=>({...project,runs:project.tests,requests:100,pass_rate:100}))};
  }else if(p.startsWith('/api/projects/')&&p.endsWith('/dashboard'))data={project:projects[0],summary:{tests:3,runs:3,requests:450,pass_rate:67}};
  else if(p==='/api/plan'){
   const arrival=body.target_request_rate||body.target_iteration_rate;
   lastPlanRequest=body;data={plan_id:'named-plan',provider:'fixture',load_model:{test_name:body.test_name,target_base_url:body.target_base_url,scenarios:[{name:'Browse',weight:1,steps:[{name:'Products',method:'GET',path:'/products'}],think_time:{min_seconds:1,max_seconds:2}}],load_profile:arrival?{type:'ramp',arrival_rate:arrival,target_request_rate:body.target_request_rate,pre_allocated_vus:body.max_users,stages:[{duration_seconds:body.duration_seconds,target_users:body.max_users}]}:{type:'ramp',stages:[{duration_seconds:30,target_users:3}]},thresholds:[]}};
  }else if(p.endsWith('/workloads')){
   if(req.method==='POST'){data={...body,workload_id:'profile-one'};profiles[p]=[data];}else data={workloads:profiles[p]||[]};
  }else if(p.endsWith('/project'))data={plan_id:'named-plan',project_id:body.project_id};
  else if(p==='/api/tools')data={tools:['k6','locust','jmeter','gatling']};
  else if(p.startsWith('/api/plans/')){
   const planId=p.split('/')[3],run=runs.find(r=>r.plan_id===planId);
   if(run)data={plan_id:planId,project_id:run.project_id,target:run.target,goal:run.test_name,scripts:[],load_model:{test_name:run.test_name,target_base_url:run.target,scenarios:[{name:'Browse',weight:1,steps:[{name:'Products',method:'GET',path:'/products'}],think_time:{min_seconds:1,max_seconds:2}}],load_profile:{type:'ramp',stages:[{duration_seconds:30,target_users:3}]},thresholds:[]}};
   else{res.statusCode=404;data={detail:'Test not found'};}
   if(run&&planId==='plan-a'&&showScriptHistoryFixture) data.scripts=[
    {script_id:'version-first',filename:'products.js',tool:'k6',source:'generated',created_at:'2026-11-17T10:00:00'},
    {script_id:'version-latest',filename:'products.js',tool:'k6',source:'edited',created_at:'2026-11-18T10:00:00'},
   ];
  }else if(p==='/api/plans')data={plans:runs.filter(r=>!url.searchParams.get('project_id')||r.project_id===url.searchParams.get('project_id')).map(r=>({plan_id:r.plan_id,test_name:r.test_name,target:r.target,script_count:1,created_at:r.created_at}))};
  else if(p==='/api/reporting/runs'||p==='/api/runs'){
   const visible=runs.filter(r=>(!url.searchParams.get('project_id')||r.project_id===url.searchParams.get('project_id'))&&(!url.searchParams.get('plan_id')||r.plan_id===url.searchParams.get('plan_id'))&&(!url.searchParams.get('target')||r.target.includes(url.searchParams.get('target'))));
   data={runs:visible.map(r=>url.searchParams.get('role')==='viewer'?{run_id:r.run_id,created_at:r.created_at,verdict:r.verdict,p95_ms:r.p95_ms,requests:r.requests,test_name:r.test_name,script_name:r.script_name,mode:r.mode}:{...r,has_report:true}),total:visible.length};
   if(url.searchParams.get('include_overview')==='true'){
    dashboardRequests++;
    if(dashboardDelay)await pause(dashboardDelay);
    const passed=visible.filter(run=>run.verdict==='pass').length;
    const failed=visible.filter(run=>run.verdict==='fail').length;
    data.overview={total:visible.length,passed,failed,inconclusive:visible.length-passed-failed,
      requests:visible.reduce((total,run)=>total+run.requests,0),
      worst_p95_ms:visible.length?Math.max(...visible.map(run=>run.p95_ms)):null,
      latest:data.runs[0],attention:data.runs.find(run=>run.verdict==='fail'),
      release_readiness:visible.some(run=>run.run_id==='saved-a')?releaseDecision:null,
      regression:visible.length>1?{run:data.runs[0],baseline_id:data.runs[1].run_id,changes:[{label:'p95 latency',previous_fmt:'100 ms',current_fmt:'140 ms'}]}:null,
      trend:[...data.runs].reverse().map(run=>({...run,t:run.created_at})),
      outcomes:visible.length?[{day:'2026-11-19',pass:passed,fail:failed,inconclusive:visible.length-passed-failed}]:[]};
   }
  }else if(/^\/api\/scripts\/version-(first|latest)\/download$/.test(p)){
   res.setHeader('Content-Type','text/plain');res.end('// '+p.split('/')[3]);return;
  }else if(p==='/api/scripts/script-a/download'){
   res.setHeader('Content-Type','text/plain');res.end('// original report script');return;
  }else if(p==='/api/scripts/script-a/validate'){validationCalls.push(req.method);data={ok:true};}
  else if(p==='/api/scripts/script-a/run'){fixtureRunStarts++;data={run_id:'fixture-live',status:'running'};}
  else if(p==='/api/preflight'){preflightCalls.push({method:req.method,body});data={all_ok:true,ok:1,total:1,results:[{method:'GET',path:'/products',status:200,ok:true}]};}
  else if(p==='/api/runs/fixture-live')data={status:'running',mode:'full',target:'https://shop.example.test',
   elapsed_s:32,planned_load:{duration_seconds:60,requests_per_second:20,peak_users:12,iterations_per_second:10},
   snapshot:{requests:632,rps:19.8,active_vus:8,iterations:316,iterations_per_second:9.9,dropped_iterations:0,
    error_rate:.004,latency:{samples:632,p95_ms:120,p99_ms:149},
    per_endpoint:[{name:'GET /products',requests:316,failed:0,avg_ms:54,p95_ms:90},
      {name:'POST /checkout',requests:316,failed:2,avg_ms:85,p95_ms:120}]},logs:['running checkout workload']};
  else if(p.endsWith('/readiness'))data={checks:[{name:'Engine',ok:true,detail:'Ready'}],execution:{duration_seconds:30,peak_users:3},smoke_supported:true};
  else if(p.endsWith('/report/download')){downloads.push(p);res.setHeader('Content-Disposition','attachment; filename="fixture-report.html"');res.setHeader('Content-Type','text/html');res.end('<h1>Fixture report</h1>');return;}
  else if(p==='/api/runs/saved-a/release-policy'&&req.method==='PUT'){
   savedReleasePolicy=body;
   data={...releaseDecision,status:'needs_evidence',reason:'This run is the approved baseline.'};
  }else if(p.endsWith('/saved-report'))data={...report,status:'finished',
   execution:{...report.execution,environment:'staging',workload_version:'fixture-v1'},
   release_readiness:savedReleasePolicy?{...releaseDecision,status:'needs_evidence',
     reason:'This run is the approved baseline.',baseline_id:'saved-a',rules:[],budgets:savedReleasePolicy.budgets}:
     {...releaseDecision,comparison:releaseComparison}};
  else if(p==='/api/traces')data={traces:[{created_at:'2026-11-19T11:01:00Z',step:'plan',model:'fixture-model',total_tokens:820,
   prompt_tokens:600,completion_tokens:220,latency_ms:430,redactions:1,status:'ok'}]};
  else if(p==='/api/audit')data={events:[
   {created_at:'2026-11-19T11:06:00Z',action:'release.baseline_approved',target:'https://shop.example.test',summary:'Approved the staging baseline'},
   {created_at:'2026-11-19T11:04:00Z',action:'run.finished',target:'https://shop.example.test',summary:'Recorded a completed workload'},
   {created_at:'2026-11-19T11:01:00Z',action:'plan.created',target:'https://shop.example.test',summary:'Drafted the product browsing plan'}]};
  else if(p==='/api/sla')data={profiles:[]};else if(p==='/api/chat/config')data={enabled:false};else if(p.includes('trend'))data={points:[]};
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 const debugPort=await new Promise(resolve=>{const probe=http.createServer();probe.listen(0,'127.0.0.1',()=>{const value=probe.address().port;probe.close(()=>resolve(value));});});
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'perfagent-ui-check-'));
 browser=spawn(process.env.PERFAGENT_EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port='+debugPort,'--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let pages;for(let i=0;i<100;i++){try{pages=await(await fetch('http://127.0.0.1:'+debugPort+'/json')).json();break;}catch{await pause(100);}}
 if(!pages)throw Error('Browser debugging unavailable');
 ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const item=pending.get(m.id);pending.delete(m.id);if(item)m.error?item.reject(m.error):item.resolve(m.result);}else if(m.method==='Page.javascriptDialogOpening'){errors.push(m.params.message);void send('Page.handleJavaScriptDialog',{accept:false});}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);else if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')errors.push(m.params.args.map(arg=>arg.value||arg.description||'').join(' '));};
 send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 async function evaluate(expression){const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;}
 async function check(name,expression){if(process.env.PERFAGENT_UI_TRACE)console.error(name);checks.push({name,result:await evaluate(expression)});}
 async function capture(name){
   const directory=process.env.PERFAGENT_SCREENSHOT_DIR;
   if(!directory)return;
   await pause(180);
   fs.mkdirSync(directory,{recursive:true});
   fs.writeFileSync(path.join(directory,name+'.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 }
 await send('Runtime.enable');await send('Page.enable');
 if(spaMode)await send('Page.addScriptToEvaluateOnNewDocument',{source:`
   const realInterval=window.setInterval.bind(window);
   window.setInterval=(callback,delay,...args)=>{
     if(delay===30000){
       window.fireWorkspaceRefresh=callback;
       return realInterval(()=>{},delay);
     }
     return realInterval(callback,delay,...args);
   };
 `});
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/'});await pause(900);
 if(spaMode){
   await check('First-visit tour opens with an accessible title', "document.querySelector('.guided-tour').open && document.querySelector('#tour-title').textContent === 'Take a tour of PerfAgent'");
   await evaluate("document.querySelector('.guided-tour-actions button:first-child').click()");
   await pause(100);
   await check('Skipping persists and returns focus to Help', "!document.querySelector('.guided-tour').open && document.activeElement.id === 'guided-tour-help' && localStorage.getItem('perfagent:guided-tour:v2') === 'seen'");
   await evaluate("document.getElementById('guided-tour-help').click()");
   await check('Help reopens the guided tour', "document.querySelector('.guided-tour').open");
   await evaluate("document.querySelector('.guided-tour-actions button:last-child').click()");
   await pause(900);
   await check('Tour opens sample Home and focuses the highlighted controls', "document.activeElement === document.querySelector('.home-lead .btnrow.guided-tour-highlight') && document.documentElement.dataset.tour === 'true'");
   await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
   await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
   await check('Tab from the highlight goes to Skip tour', "document.activeElement.textContent === 'Skip tour'");
   const tourStops=['Home','Projects','Describe','Review plan','Verify','Run','Report','Dashboard'];
   const nextTourStop=()=>clickTourButton('last-child');
   async function clickTourButton(position){
     const point=await evaluate(`(() => {
       const button=document.querySelector('.guided-tour-actions button:${position}');
       const rect=button.getBoundingClientRect();
       return {x:rect.left+rect.width/2,y:rect.top+rect.height/2};
     })()`);
     await send('Input.dispatchMouseEvent',{...point,type:'mousePressed',button:'left',clickCount:1});
     await send('Input.dispatchMouseEvent',{...point,type:'mouseReleased',button:'left',clickCount:1});
     await pause(340);
   }
   async function checkTourPlacement(title,size,{focus=true}={}){
     await check(`${size} tour anchors beside ${title}`, `(() => {
       const target=document.querySelector('.guided-tour-highlight');
       const overlay=document.querySelector('.guided-tour-overlay');
       if (!target || !overlay || !document.querySelector('#tour-title').textContent.includes(${JSON.stringify(title)})) return false;
       const anchor=target.getBoundingClientRect(), card=overlay.getBoundingClientRect();
       const gap=Math.max(card.top-anchor.bottom,anchor.top-card.bottom,card.left-anchor.right,anchor.left-card.right);
       const width=document.documentElement.clientWidth, height=innerHeight;
       const buttons=[...overlay.querySelectorAll('button:enabled')];
       return gap>=5 && gap<=32 && anchor.bottom>0 && anchor.top<height &&
         card.left>=0 && card.right<=width+1 && card.top>=0 && card.bottom<=height+1 &&
         buttons.every(button=>{
           const rect=button.getBoundingClientRect();
           return rect.bottom<=card.bottom && document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2)===button;
         }) && ${focus ? 'document.activeElement===target' : 'true'};
     })()`);
   }
   await checkTourPlacement('Home','Desktop',{focus:false});
   await capture('guided-tour-home');
   await nextTourStop();
   await check('Tour opens actual Projects with a sample project', "location.pathname === '/projects' && document.querySelector('.project-card')?.textContent.includes('Commerce Demo')");
   await checkTourPlacement('Projects','Desktop');
   for(const title of tourStops.slice(2)){
     await nextTourStop();
     await checkTourPlacement(title,'Desktop');
     if(title==='Review plan')await capture('guided-tour-review');
   }
   const dashboardTop=await evaluate("document.querySelector('.guided-tour-overlay').getBoundingClientRect().top");
   await evaluate("window.scrollBy({top:45,behavior:'instant'})");
   await pause(120);
   await check('Tour card follows the highlight when the page scrolls', `Math.abs(document.querySelector('.guided-tour-overlay').getBoundingClientRect().top-${dashboardTop})>=40`);
   await checkTourPlacement('Dashboard','Scrolled desktop');
   await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
   await pause(340);
   await checkTourPlacement('Dashboard','Mobile');
   await capture('guided-tour-dashboard-mobile');
   for(const title of tourStops.slice(0,-1).reverse()){
     await clickTourButton('nth-child(2)');
     await checkTourPlacement(title,'Mobile Previous');
   }
   await send('Emulation.setDeviceMetricsOverride',{width:320,height:568,deviceScaleFactor:1,mobile:true});
   await pause(340);
   await checkTourPlacement('Home','Compact mobile');
   for(const title of tourStops.slice(1)){
     await nextTourStop();
     await checkTourPlacement(title,'Compact mobile Next');
   }
   await check('Tour made no API network requests', "performance.getEntriesByType('resource').every(entry => !new URL(entry.name).pathname.startsWith('/api/'))");
   await nextTourStop();
   await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
   await pause(550);
   await check('Done restores the original workspace and focuses Help', "!document.querySelector('.guided-tour-overlay') && document.activeElement.id === 'guided-tour-help' && !document.documentElement.dataset.tour");
   await check('Starts at Home with the main navigation selected', "document.getElementById('view-home').classList.contains('show')&&document.querySelector('[data-view=home]').getAttribute('aria-current')==='page'");
   await capture('home');
   await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
   await check('Home fits a narrow viewport','document.documentElement.scrollWidth<=390');
   await capture('home-mobile');
   await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
   await evaluate("document.querySelector('.home-lead button').click()");
   await pause(300);
 }
 await check('Starts at Projects','document.getElementById("view-projects").classList.contains("show")');
 if(spaMode){
 await check('App typography loads from same-origin font assets', "document.fonts.ready.then(()=>[...document.fonts].some(face=>face.family.includes('Geist')&&face.status==='loaded'))");
 await check('Project library is visible', "document.querySelector('.projects-intro h2').textContent==='Performance workspace'&&Boolean(document.querySelector('.project-card-meta'))");
 await check('Project search narrows and restores the library', `(()=>{
   const field=document.getElementById('projectSearch');field.value='Payments';field.dispatchEvent(new Event('input',{bubbles:true}));
   const filtered=[...document.querySelectorAll('#projectCards .project-card:not([hidden])')].map(card=>card.querySelector('h3').textContent);
   field.value='';field.dispatchEvent(new Event('input',{bubbles:true}));
   return filtered.join()==='Payments'&&document.querySelectorAll('#projectCards .project-card:not([hidden])').length===2;
 })()`);
 await capture('projects-redesign');
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-projects.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await check('Generated code is collapsed by default', "document.querySelector('.script-details').open===false&&document.getElementById('preflightBtn').closest('details')===null");
 }
 await evaluate("document.querySelector('#view-projects .btn').click();document.getElementById('projectName').value='New app';document.getElementById('projectTarget').value='http://fixture.test';document.querySelector('#projectForm .btn').click()");await pause(200);
 await check('Project created and selected',"currentProject?.project_id==='project-new'");
 await evaluate("document.querySelector('#activeProject .btn').click();document.getElementById('newTestName').value='Named checkout';document.getElementById('newTestPurpose').value='Verify checkout';document.querySelector('#newTestForm .btn').click()");
 await check('Test is named before planning',"newTestName==='Named checkout'&&document.getElementById('modeScriptBtn').style.display==='none'");
 if(spaMode){
   await check('Describe puts requests before workload and offers a keyboard-accessible import',
     "Boolean(document.getElementById('endpoints').compareDocumentPosition(document.getElementById('draftSchedule'))&Node.DOCUMENT_POSITION_FOLLOWING)&&document.getElementById('impdz').tagName==='BUTTON'");
   await capture('describe-redesign');
 }
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Planning receives project and test identity',result:lastPlanRequest?.project_id==='project-new'&&lastPlanRequest?.test_name==='Named checkout'});
 if(spaMode){
 await check('Review stage is exposed as the current workflow step',
   "document.querySelector('button.step[aria-current=step]').textContent.includes('Review plan')&&document.getElementById('workflowAnnouncement').textContent.includes('Step 2 of 5')");
 const accessibility=await send('Accessibility.getFullAXTree');
 checks.push({name:'Workflow navigation and Review control are named in the accessibility tree',result:
   accessibility.nodes.some(node=>node.role?.value==='navigation'&&node.name?.value==='Test workflow')&&
   accessibility.nodes.some(node=>node.role?.value==='button'&&node.name?.value.startsWith('Review plan'))});
 await evaluate("document.querySelector('button.step[data-step=\"1\"]').focus()");
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:' ',code:'Space',windowsVirtualKeyCode:32,nativeVirtualKeyCode:49});
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:' ',code:'Space',windowsVirtualKeyCode:32,nativeVirtualKeyCode:49});
 await check('Keyboard can return to Describe',"document.getElementById('panel1').classList.contains('show')");
 await evaluate("document.getElementById('planBtn').focus();goStep(2)");
 await check('Leaving a stage restores focus to the new step',"document.activeElement===document.querySelector('.step[aria-current=step]')");
 await check('Workflow step text meets normal-text contrast', `(()=>{
   const luminance=color=>color.match(/\\d+/g).slice(0,3).map(Number).map(n=>n/255).map(
     n=>n<=0.04045?n/12.92:((n+0.055)/1.055)**2.4
   ).reduce((total,n,i)=>total+n*[0.2126,0.7152,0.0722][i],0);
   return [...document.querySelectorAll('#stepper .step')].every(step=>{
     const text=luminance(getComputedStyle(step.querySelector('.sub')).color);
     const surface=luminance(getComputedStyle(step).backgroundColor);
     return (Math.max(text,surface)+0.05)/(Math.min(text,surface)+0.05)>=4.5;
   });
 })()`);
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 await check('Reduced-motion preference disables workflow animation',"getComputedStyle(document.getElementById('panel2')).animationName==='none'");
 await send('Emulation.setEmulatedMedia',{features:[]});
 await check('Review loads with every editor collapsed', "document.querySelectorAll('.review-editor[open],.review-advanced[open]').length===0");
 await evaluate("planModel.thresholds=[{metric:'p95_ms',op:'<=',value:500},{metric:'error_rate',op:'<',value:.01}]; renderPlanForm(); addHeader('Authorization','Bearer fixture-review-secret')");
 await check('Review shows exact target, requests, load, and pass rules', "document.getElementById('reviewTargetOverview').textContent.includes('http://fixture.test')&&document.getElementById('reviewRequestsOverview').textContent.includes('/products')&&document.getElementById('planSummary').textContent.includes('3 peak VUs')&&document.getElementById('planSummary').textContent.includes('< 1%')");
 await check('Review masks header values', "document.getElementById('reviewTargetOverview').textContent.includes('Authentication configured')&&!document.querySelector('.review-layout').textContent.includes('fixture-review-secret')&&document.querySelector('#headersList input[type=password]').value.includes('fixture-review-secret')");
 await check('Review plots planned traffic and keeps stage values readable', "document.querySelector('.review-load-plot > div').style.clipPath.startsWith('polygon(')&&document.querySelector('[aria-label=\"Load stages\"]').textContent.includes('3 VUs')");
 await check('Review explains dataset and response values in journey order', `(()=>{
   const steps=planModel.scenarios[0].steps;
   const original=[...steps], columns=dataColumns;
   try {
     dataColumns=['account_id'];
     steps.splice(0,steps.length,
       {method:'POST',path:'/orders',body:{account:'\${account_id}'},extract:[{var:'order_id'}]},
       {method:'POST',path:'/orders/\${order_id}',body:{reference:'fixed'},assertions:[{kind:'json_path',path:'order.status',op:'exists'}]});
     renderSummary();
     const rows=document.querySelectorAll('.review-request');
     const correct=rows.length===2&&rows[0].textContent.includes('Dataset · account_id → Body field account')&&rows[0].textContent.includes('Captures order_id')&&rows[1].textContent.includes('Earlier response · order_id → Request path')&&rows[1].textContent.includes('order.status exists');
     rows[1].querySelector('button').click();
     const source=document.querySelector('[aria-label="Where reference comes from"]');
     source.value='captured';
     source.dispatchEvent(new Event('change'));
     return correct&&steps[1].body.reference==='\${order_id}'&&document.querySelector('[aria-label="Captured response value"]').value==='order_id';
   } finally {
     steps.splice(0,steps.length,...original);
     dataColumns=columns;
     openSteps.clear();
     document.getElementById('scenarios').closest('details').open=false;
     renderPlanForm();
   }
 })()`);
 await evaluate(`window.weightingOriginal=structuredClone(planModel);
   planModel.scenarios=[
     {name:'Browse',weight:1,steps:[{method:'GET',path:'/products'}]},
     {name:'Checkout',weight:1,steps:[{method:'GET',path:'/cart'},{method:'POST',path:'/checkout'}]},
   ];
   planModel.load_profile.arrival_rate=10;
   renderPlanForm();
   const weightsInput=document.getElementById('journeyWeightCsv');
   weightsInput.closest('details').open=true;
   const weightFiles=new DataTransfer();
   weightFiles.items.add(new File([${JSON.stringify([
     'window_start,window_seconds,method,route,requests',
     '2026-01-10T12:00:00Z,60,GET,/products,800',
     '2026-01-10T12:00:00Z,60,POST,/checkout,200',
   ].join('\n'))}],'route-counts.csv',{type:'text/csv'}));
   weightsInput.files=weightFiles.files;weightsInput.dispatchEvent(new Event('change',{bubbles:true}));`);
 await pause(100);
 await check('Review previews sampled shares and expected throughput before applying',
   "document.getElementById('journeyWeightPreview').textContent.includes('80% suggested share')&&document.getElementById('journeyWeightPreview').textContent.includes('12 req/s')&&planModel.scenarios[0].weight===1");
 await evaluate("document.getElementById('journeyWeightPreview').scrollIntoView({block:'center'})");
 await capture('journey-weighting');
 await check('Applying sampled weights updates the editable plan', `(()=>{
   try {
     document.querySelector('#journeyWeightPreview button').click();
     const weights=planModel.scenarios.map(journey=>journey.weight);
     return weights[0]===.8&&weights[1]===.2&&document.getElementById('reviewRequestsOverview').textContent.includes('80%');
   } finally {
     planModel=window.weightingOriginal;delete window.weightingOriginal;
     document.querySelector('.journey-weighting').open=false;renderPlanForm();window.scrollTo(0,0);
   }
 })()`);
 await check('Review links missing values to the request editor', `(()=>{
   const step=planModel.scenarios[0].steps[0];
   const path=step.path;
   try {
     step.path='/products/\${missing_fixture}';
     renderSummary();
     const findings=document.getElementById('reviewFindings');
     const found=!findings.hidden&&findings.textContent.includes('missing_fixture');
     findings.querySelector('button').click();
     return found&&document.activeElement.id==='review-step-0:0'&&document.activeElement.getAttribute('aria-expanded')==='true';
   } finally {
     step.path=path;
     openSteps.clear();
     document.getElementById('scenarios').closest('details').open=false;
     renderPlanForm();
   }
 })()`);
 await check('Dataset shortcut opens the upload control and moves focus', `(()=>{
    const button=document.querySelector('.review-flow-links button');
    button.click();
    const details=document.getElementById('dataFile').closest('details');
    const result=details.open&&document.activeElement.id==='dz';
    details.open=false;
    return result;
 })()`);
 await evaluate("document.querySelector('.review-editor summary').click()");
 await check('Editing target opens only its section', "document.querySelectorAll('.review-editor[open]').length===1&&document.getElementById('pfTarget').offsetWidth>0");
 await evaluate("document.querySelector('.review-editor summary').click()");
 await capture('review-plan-redesign');
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-review.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await capture('review-plan-redesign-mobile');
 await check('Compact review fits mobile and puts summary first', "document.documentElement.scrollWidth<=390&&document.getElementById('planSummary').getBoundingClientRect().top<document.getElementById('planForm').getBoundingClientRect().top");
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 }
 await evaluate("document.getElementById('workloadName').value='Average';saveWorkloadProfile()");
 await check('Workload profile saved',"document.getElementById('savedWorkload').textContent.includes('Average')");
 if(spaMode){
 await evaluate(`document.getElementById('newTestName').value='Request rate';startNamedTest();
   document.getElementById('target').value='http://fixture.test/products';
   const fileInput=document.getElementById('trafficCsv');
   fileInput.closest('details').open=true;
   const files=new DataTransfer();
   files.items.add(new File([${JSON.stringify([
     'window_start,window_seconds,method,route,requests',
     '2026-01-10T12:00:00Z,60,GET,/products,720',
     '2026-01-10T12:00:00Z,60,POST,/checkout,180',
     '2026-01-10T12:01:00Z,60,GET,/products,480',
     '2026-01-10T12:01:00Z,60,POST,/checkout,120',
   ].join('\n'))}],'traffic.csv',{type:'text/csv'}));
   fileInput.files=files.files;fileInput.dispatchEvent(new Event('change',{bubbles:true}));`);
 await pause(100);
 await check('Traffic CSV shows observed route mix and rate', "document.querySelector('.traffic-import').textContent.includes('15 req/s peak window')&&document.querySelector('.traffic-import').textContent.includes('80%')");
 await evaluate("document.querySelector('.traffic-import button').click();document.querySelector('.traffic-import').scrollIntoView({block:'center'})");
 await capture('traffic-planning');
 await check('Describe shows a request-rate goal', "document.getElementById('draftRequestRate').offsetWidth>0&&document.getElementById('profileType').offsetWidth===0");
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Describe preserves the request-rate goal and page path',result:lastPlanRequest?.target_request_rate===15&&lastPlanRequest?.traffic_sample_rate===true&&lastPlanRequest?.endpoints[0]?.path==='/products'});
 await check('Review shows the request rate and request count', "document.getElementById('planSummary').textContent.includes('15 requests/s')&&document.getElementById('planSummary').textContent.includes('900 HTTP requests')");
 await evaluate("goStep(1);document.getElementById('draftSchedule').value='journey-rate';document.getElementById('draftJourneyRate').value='5'");
 await check('Describe offers a separate journey rate', "document.getElementById('draftJourneyRate').offsetWidth>0&&document.getElementById('draftRequestRate').offsetWidth===0");
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Journey-rate choice submits journey starts without an HTTP target',
  result:lastPlanRequest?.target_iteration_rate===5&&lastPlanRequest?.target_request_rate===undefined});
 await check('Review shows the journey rate in iterations per second', "document.getElementById('planSummary').textContent.includes('5 iterations/s')&&document.getElementById('planSummary').textContent.includes('Constant journey rate')");
 }
 await evaluate("selectProject('project-a');startProjectImport('script')");
 await check('Script import is separate',"document.getElementById('modeScript').style.display==='block'&&document.querySelector('#panel1 .modeswitch').style.display==='none'");
 await evaluate("startProjectImport('git')");await check('Git inherits project repository',"document.getElementById('impRepo').value==='https://github.com/org/shop.git'");
 await evaluate("showView('admin');document.getElementById('adminToken').value='wrong';loadAdminOverview()");await check('Admin denial visible',"document.getElementById('adminOverview').textContent.includes('Administrator access')");
 await evaluate("document.getElementById('adminToken').value='fixture-admin';loadAdminOverview()");await check('Admin sees other projects',"document.getElementById('adminOverview').textContent.includes('Payments')");
 await evaluate("showView('projects');toggleSidebar()");await check('Collapsed toggle remains inside sidebar',"(()=>{const a=document.querySelector('.sb-toggle').getBoundingClientRect(),b=document.querySelector('.sidebar').getBoundingClientRect();return a.width>0&&a.left>=b.left&&a.right<=b.right})()");
 await send('Page.reload');await pause(500);await check('Sidebar state survives reload',"document.getElementById('sidebar').classList.contains('collapsed')");
 if(spaMode){
   await evaluate("document.querySelector('#projectCards [data-project-id=\"project-a\"]').click()");await pause(250);
   await check('Open project lands in its workspace',"location.pathname==='/projects/project-a/tests'&&document.getElementById('view-history').classList.contains('show')");
   await check('Workspace shows scoped tests and framework folders',"document.querySelectorAll('#plansTable [data-open-test]').length===3&&document.querySelector('#plansTable').textContent.includes('Product browsing')&&document.getElementById('libraryFrameworkTree').textContent.includes('product-browsing/')&&!document.querySelector('#plansTable').textContent.includes('Hidden payment test')");
   showScriptHistoryFixture=true;
   await evaluate("document.querySelector('[data-version-test=\"plan-a\"]').click()");await pause(220);
   await check('Latest script selected and older versions are listed on demand',"currentScriptId==='version-latest'&&document.getElementById('scriptVersionHistory').open&&document.getElementById('scriptVersionList').textContent.includes('Version 2 · Latest')");
   await evaluate("document.querySelector('[data-preview-script*=\"version-first\"]').click()");await pause(100);
   await check('Viewing an older script preserves the latest execution version',"document.getElementById('scriptVersionPreview').textContent==='// version-first'&&currentScriptId==='version-latest'");
   showScriptHistoryFixture=false;
   await evaluate("showView('history')");await pause(150);
   await evaluate("document.getElementById('projectTestSearch').value='checkout';document.getElementById('projectTestSearch').dispatchEvent(new Event('input'))");
   await check('Workspace test search narrows the list',"document.querySelectorAll('#plansTable [data-open-test]').length===1&&document.querySelector('#plansTable tbody').textContent.includes('Checkout flow')");
 }
 dashboardDelay=spaMode?350:0;
 await evaluate("selectProject('project-a');toggleSidebar();showView('dashboard')");await pause(100);
 if(spaMode)await check('Dashboard shows skeletons while its first result is loading',"document.querySelectorAll('#sdTiles .ui-skeleton').length===8&&document.querySelector('.dashboard-results').getAttribute('aria-busy')==='true'");
 await pause(340);
 dashboardDelay=0;
 await check('Recent reports available',"document.querySelectorAll('#sdTable [data-report-id]').length===3");
 if(spaMode) await check('Dashboard totals come from saved history', "document.getElementById('sdTiles').textContent.includes('450Total requests')&&document.getElementById('sdFilterNote').textContent.includes('all matching saved runs')");
 if(spaMode){
 await capture('release-dashboard');
 if(process.env.PERFAGENT_SCREENSHOT_DIR){
   await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
   await capture('release-dashboard-mobile');
   await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 }
 await check('Release verdict is above run history', "!document.getElementById('sdReleaseReadiness').hidden&&document.getElementById('sdReleaseReadiness').textContent.includes('Blocked')");
 await check('Dashboard prioritizes a failed run', "document.getElementById('sdAttention').textContent.includes('Needs attention')&&document.getElementById('sdAttention').textContent.includes('Checkout flow')");
 await check('Baseline regression displays measured change and both reports', "!document.getElementById('sdRegression').hidden&&document.getElementById('sdRegression').textContent.includes('100 ms → 140 ms')&&document.querySelectorAll('#sdRegression button').length===2");
 await check('Trend has a keyboard-accessible data table', "document.querySelectorAll('#sdTrendData tbody tr').length===3&&document.querySelector('#sdTrendData button')!==null");
 await check('Dashboard shows all four historical charts', "document.querySelectorAll('.dashboard-chart-grid figure').length===4&&document.querySelector('#sdOutcomes button').getAttribute('aria-label').includes('1 fail')");
 await check('Dashboard selected run has a report action', "!document.getElementById('sdInspectReport').disabled&&Boolean(document.getElementById('sdInspectRunNote').textContent)");
 const beforeRefresh=dashboardRequests;
 await evaluate(`document.activeElement.blur();
   window.savedTrendRows=document.querySelector('#sdTable tbody').firstElementChild;
   Object.defineProperty(document,'hidden',{configurable:true,value:false});
   try{window.fireWorkspaceRefresh();}finally{delete document.hidden;}
 `);
 for(let retries=0;retries<10&&dashboardRequests===beforeRefresh;retries++)await pause(100);
 await pause(100);
 checks.push({name:'Dashboard checks for updates automatically',result:dashboardRequests===beforeRefresh+1});
 await check('Unchanged auto refresh preserves dashboard rows',"window.savedTrendRows===document.querySelector('#sdTable tbody').firstElementChild&&document.getElementById('sdRefreshStatus').textContent.startsWith('Updated ')");
 }
 await check('Dashboard scoped to project',"!document.querySelector('#sdTable tbody').textContent.includes('Hidden payment test')");
 await check('Names distinguish same-target tests',"document.querySelector('#sdTable tbody').textContent.includes('Product browsing')&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await check('Requests visible in default view',"document.getElementById('sdHead').textContent.includes('Requests')");
 await evaluate("document.getElementById('sdTest').value='plan-c';loadStakeholder()");await check('Test filter isolates a workload',"document.querySelectorAll('#sdTable tbody tr').length===1&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await evaluate('resetDashboardFilters()');await pause(150);await check('Comparison rendered',"document.querySelectorAll('#sdComparison tbody tr').length>0");
 await evaluate("document.getElementById('sdTarget').value='second';loadStakeholder()");await check('Target filter',"document.querySelectorAll('#sdTable tbody tr').length===1");
 await evaluate('resetDashboardFilters()');await pause(150);await evaluate("document.querySelector('#sdTable [data-report-id]').click()");await pause(150);
 await check('Saved report opens',"document.getElementById('panel5').classList.contains('show')&&document.getElementById('reportSummary').textContent.startsWith('Product browsing sustained')");
 if(spaMode){
 await check('Release decision, comparison, and escaped endpoint are visible',
   "document.getElementById('reportReleaseDecision').textContent.includes('Blocked')&&document.querySelectorAll('#reportReleaseComparison canvas').length===1&&document.getElementById('reportReleaseComparison').textContent.includes('<img src=x')&&!document.querySelector('#reportReleaseComparison img')");
 await check('Release comparison metric switches with the keyboard-accessible select', `(()=>{
   const select=document.getElementById('releaseComparisonMetric');
   select.value='rps';select.dispatchEvent(new Event('change'));
   const changed=document.querySelector('.comparison-key').textContent.includes('21 req/s');
   select.value='p95';select.dispatchEvent(new Event('change'));
   return changed&&document.querySelector('.comparison-key').textContent.includes('120 ms');
 })()`);
 if(process.env.PERFAGENT_SCREENSHOT_DIR){
   await evaluate("document.querySelector('#reportReleaseComparison tbody th').textContent='GET /products';window.scrollTo(0,0)");
   await capture('release-report');
   await evaluate("document.getElementById('reportReleaseComparison').scrollIntoView({block:'start'})");
   await capture('release-comparison');
   await evaluate("const ruleSetup=document.getElementById('reportReleasePolicy');ruleSetup.open=true;ruleSetup.scrollIntoView({block:'center'})");
   await capture('release-budget-setup');
   await evaluate("document.getElementById('reportReleasePolicy').open=false");
   await evaluate("window.scrollTo(0,0)");
 }
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await check('Release report fits mobile',"document.documentElement.scrollWidth<=390&&document.querySelector('.step[aria-current=step]').getBoundingClientRect().right<=390");
 await capture('release-report-mobile');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await evaluate(`document.getElementById('reportReleasePolicy').open=true;
   const releaseForm=document.getElementById('releasePolicyForm');
   releaseForm.elements.max_p95_regression_percent.value='15';
   releaseForm.querySelector('button').focus();releaseForm.requestSubmit();`);
 await pause(150);
 await check('Saving budgets refreshes the decision and restores focus',
   "document.getElementById('releasePolicyStatus').textContent.includes('Baseline approved')&&document.getElementById('reportReleaseDecision').textContent.includes('Needs evidence')&&document.activeElement===document.querySelector('#releasePolicyForm button')");
 checks.push({name:'Budget uses the selected saved report and numeric input',result:savedReleasePolicy?.budgets.max_p95_regression_percent===15});
 await check('Report summary uses the release explanation and formats measured latency', `(()=>{
   const fixture=${JSON.stringify(report)};
   fixture.saved_result_id=reportContext.savedId;
   try {
     fixture.verdict.checks[0].actual=1.4962999999999995;
     renderReport({...fixture,release_readiness:{status:'blocked',reason:'A budget was breached.',
       explanation:'The run passed its k6 thresholds. The release is blocked.'}});
     return document.getElementById('reportSummary').textContent.includes('The release is blocked.')&&
       document.getElementById('reportHighlights').textContent.includes('1.4963 ms');
   } finally { renderReport(fixture); }
 })()`);
 await check('Report explains the result before threshold details', "document.querySelector('.report-story h2').textContent==='What happened'&&Boolean(document.querySelector('.report-story').compareDocumentPosition(document.getElementById('reportHighlights'))&Node.DOCUMENT_POSITION_FOLLOWING)");
 await check('Report key evidence links to the endpoint details', `(()=>{
   const fixture=${JSON.stringify(report)};
   fixture.saved_result_id=reportContext.savedId;
   try {
     renderReport({...fixture,snapshot:{...fixture.snapshot,per_endpoint:[{name:'Checkout',requests:20,failed:3,p95_ms:120}]}});
     const evidence=document.getElementById('reportEvidenceSummary');
     evidence.querySelector('button').click();
     return !evidence.hidden&&evidence.textContent.includes('Checkout · 3')&&document.activeElement.id==='reportEndpointDetails'&&document.activeElement.open;
   } finally {
     document.getElementById('reportEndpointDetails').open=false;
     renderReport(fixture);
   }
 })()`);
 await check('Older reports disclose missing samples', "document.getElementById('reportSampleNote').textContent.includes('unavailable')");
 await check('Report charts share a selected sample and preserve missing values', `(()=>{
   drawTsChart([{t:10,rps:12,p95:135,dropped_iterations:2},{t:30,rps:15,p95:210,err:0,dropped_iterations:4}],
     [{label:'Ramp up',start_s:0,end_s:15}],{elapsed_s:10,count:2});
   try {
     const picker=document.getElementById('reportSampleIndex');
     picker.value='0';
     picker.dispatchEvent(new Event('input'));
     return document.querySelectorAll('.report-metric-charts canvas').length===3
       && picker.getAttribute('aria-valuetext')==='10 seconds'
       && document.getElementById('reportPlannedPhases').textContent.includes('Ramp up 0–15 s')
       && document.getElementById('reportDropMarker').textContent.includes('10 s (2 cumulative)')
       && document.getElementById('reportSampleReadout').textContent.includes('Errors Unavailable');
   } finally { drawTsChart([]); }
 })()`);
 await check('Report ranks endpoints by the selected metric', `(()=>{
   const report=${JSON.stringify(report)};
   try {
     renderReportDetails({...report,snapshot:{per_endpoint:[
       {name:'Browse',p95_ms:300,requests:10,failed:0,checks_failed:4},
       {name:'Checkout',p95_ms:150,requests:10,failed:3,checks_failed:1}
     ]}});
     const ranking=document.getElementById('reportEndpointRanking');
     const startsWithBrowse=ranking.firstElementChild.textContent.includes('Browse');
     const selector=document.getElementById('reportEndpointMetric');
     selector.value='failed';
     selector.dispatchEvent(new Event('change'));
     const failuresStartWithCheckout=ranking.firstElementChild.textContent.includes('Checkout');
     selector.value='checks_failed';
     selector.dispatchEvent(new Event('change'));
     return startsWithBrowse&&failuresStartWithCheckout&&ranking.firstElementChild.textContent.includes('Browse');
   } finally { renderReportDetails(report); }
 })()`);
 }
 await check('Report has own identity',"reportContext.savedId==='saved-a'&&currentRunId===null");await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:os.tmpdir()});await evaluate('downloadReport()');await pause(200);checks.push({name:'Download uses displayed report',result:downloads.includes('/api/runs/saved-a/report/download')});
 await evaluate('selectReportBaseline()');await check('Baseline saved',"getSelectedBaseline()==='saved-a'");await evaluate('clearSelectedBaseline()');await check('Baseline cleared','getSelectedBaseline()===null');
 await evaluate("currentScriptId='script-a';checkReadiness()");await check('Readiness checklist shown',"document.getElementById('readinessResult').textContent.includes('Before you run')");
 // Match the compatibility controller's native enablement after script generation.
 await evaluate("document.getElementById('validateBtn').disabled=false;document.getElementById('preflightBtn').disabled=false;document.getElementById('validateBtn').click()");await pause(150);
 checks.push({name:'Validate click sends POST',result:validationCalls.length===1&&validationCalls[0]==='POST'});
 await check('Validation result appears',"document.getElementById('validateResult').classList.contains('ok')");
 await evaluate("document.getElementById('preflightBtn').click()");await pause(150);
 checks.push({name:'Pre-flight click sends script identity',result:preflightCalls.length===1&&preflightCalls[0].method==='POST'&&preflightCalls[0].body.script_id==='script-a'});
 await check('Pre-flight endpoint result appears',"document.getElementById('preflightResult').textContent.includes('1/1 endpoints responded OK')&&document.getElementById('preflightResult').textContent.includes('/products')");
 if(spaMode){
   await evaluate("goStep(3);window.scrollTo(0,0)");
   await check('Verify separates local checks from target traffic', "document.getElementById('validateBtn').closest('section').getAttribute('aria-labelledby')==='verifyLocalHeading'&&document.getElementById('preflightBtn').closest('section').getAttribute('aria-labelledby')==='verifyTrafficHeading'&&document.getElementById('runBtn').closest('.verify-launch')!==null");
   await capture('verify-redesign');
   await evaluate(`goStep(4);resetChart();pushChart(4,6,72,0);pushChart(8,12,86,0);
      pushChart(16,19,105,.003);pushChart(24,20,119,.004);currentRunId='fixture-live';pollRun()`);
   await check('Live run shows planned duration and captured measurements', "document.getElementById('liveRunScope').textContent.includes('60 s planned')&&document.getElementById('mRps').textContent==='19.8 / 20'&&document.getElementById('epTable').textContent.includes('POST /checkout')");
   await check('Live metric picker updates the accessible reading', `(()=>{
     const metric=document.getElementById('liveMetric');
     metric.value='p95';metric.dispatchEvent(new Event('change',{bubbles:true}));
     return document.getElementById('liveChart').getAttribute('aria-label').includes('p95 latency')&&
       document.getElementById('liveChartReading').textContent.includes('120 ms');
   })()`);
   await evaluate("window.scrollTo(0,0);currentRunId=null");
   await capture('live-run-redesign');
 }
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-report.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 for(const view of ['history','monitoring','activity']){await evaluate("showView('"+view+"')");await pause(100);await check(view+' navigation',"document.getElementById('view-"+view+"').classList.contains('show')");}
 if(spaMode){
   await capture('activity-redesign');
   await evaluate("showView('history');window.scrollTo(0,0)");
   await capture('test-library-redesign');
   await evaluate("showView('monitoring');window.scrollTo(0,0)");
   await check('Monitoring rejects embedded credentials', `(()=>{
     document.getElementById('monUrl').value='https://name:secret@monitor.example.test';
     document.querySelector('.monitor-setup form').requestSubmit();
     return document.getElementById('monStatus').textContent.includes('without embedded credentials');
   })()`);
   await check('Monitoring waits for explicit preview and sandboxes the frame', `(()=>{
     document.getElementById('monUrl').value=location.origin+'/fixture-dashboard';
     document.querySelector('.monitor-setup form').requestSubmit();
     const button=document.querySelector('[data-monitor-preview]');
     const deferred=Boolean(button)&&!document.querySelector('#monList iframe');
     button.click();
     const frame=document.querySelector('#monList iframe');
     const safe=frame?.getAttribute('sandbox')==='allow-scripts'&&frame?.referrerPolicy==='no-referrer';
     button.click();
     return deferred&&safe&&!document.querySelector('#monList iframe')&&button.getAttribute('aria-expanded')==='false';
   })()`);
   await capture('monitoring-redesign');
   await evaluate("document.querySelector('[data-monitor-remove]').click()");
 }
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 if(spaMode){
   for(const [stage,label] of [[1,'Describe'],[3,'Verify'],[4,'Live Run']]){
     await evaluate('goStep('+stage+')');
     await check(label+' fits a narrow viewport','document.documentElement.scrollWidth<=390');
   }
   await evaluate("showView('history')");
   await check('Project workspace fits a narrow viewport','document.documentElement.scrollWidth<=390');
   await evaluate("showView('activity')");
   await check('Activity fits a narrow viewport','document.documentElement.scrollWidth<=390');
   await evaluate("showView('monitoring')");
   await check('Monitoring fits a narrow viewport','document.documentElement.scrollWidth<=390');
 }
 await evaluate("showView('dashboard')");await pause(150);await evaluate("document.querySelector('#sdTable [data-report-id]').click()");await pause(150);await check('Mobile report fits viewport','document.documentElement.scrollWidth<=390');
 await evaluate("showView('dashboard');document.getElementById('sdRole').value='viewer';loadStakeholder()");await check('Viewer target filter disabled',"document.getElementById('sdTarget').disabled");await check('Viewer omits unavailable error metrics',"!document.getElementById('sdHead').textContent.includes('Errors')");await check('Mobile dashboard fits','document.documentElement.scrollWidth<=390');
 await evaluate('openMobNav()');await check('Mobile navigation opens',"document.getElementById('sidebar').classList.contains('mobopen')");await evaluate("document.querySelector('[data-view=create]').click()");await check('Mobile navigation closes',"!document.getElementById('sidebar').classList.contains('mobopen')");await check('Projects fit mobile viewport','document.documentElement.scrollWidth<=390');
 if(spaMode){
 await evaluate("showError('Fixture notice');document.querySelector('#appNotice button').click()");
 await check('React event handler keeps element context',"document.getElementById('appNotice').style.display==='none'");
 await evaluate("showView('history')");await pause(100);await evaluate("showView('monitoring')");await pause(100);await evaluate('history.back()');await pause(200);
 await check('Browser Back restores project library',"location.pathname==='/projects/project-a/tests'&&document.getElementById('view-history').classList.contains('show')");
 await evaluate('history.forward()');await pause(200);await check('Browser Forward restores monitoring',"location.pathname==='/monitoring'&&document.getElementById('view-monitoring').classList.contains('show')");
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/projects/project-a/dashboard'});await pause(600);
 await check('Dashboard deep link and refresh',"currentProject?.project_id==='project-a'&&document.getElementById('view-dashboard').classList.contains('show')");
 await send('Page.reload');await pause(600);await check('Dashboard remains after refresh',"document.getElementById('view-dashboard').classList.contains('show')");
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/projects/project-a/runs/saved-a'});await pause(600);
 await check('Report opens from deep link',"reportContext?.savedId==='saved-a'&&document.getElementById('reportSummary').textContent.startsWith('Product browsing sustained')");
 await check('Run again is aligned with report content', "document.getElementById('rerunBtn').getBoundingClientRect().left>document.querySelector('.report-result').getBoundingClientRect().left+8");
 await evaluate("document.getElementById('releaseLabel').value='demo-v1';document.getElementById('rerunBtn').click()");
 await pause(200);
 await check('Run again opens Verify with exact saved script and an empty release label',
   "document.getElementById('panel3').classList.contains('show')&&currentScriptId==='script-a'&&document.getElementById('scriptOut').textContent==='// original report script'&&document.getElementById('releaseLabel').value===''&&document.activeElement.id==='releaseLabel'");
 await send('Page.reload');await pause(600);
 await check('Reload preserves the rerun script and Verify screen',
   "location.search==='?rerun=1'&&currentScriptId==='script-a'&&document.getElementById('panel3').classList.contains('show')&&!document.getElementById('runBtn').disabled");
 checks.push({name:'Preparing a rerun sends no run request',result:fixtureRunStarts===0});
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/projects/project-b/runs/saved-a'});await pause(600);
 await check('Mismatched project report is rejected',"document.querySelector('.spa-error')?.textContent.includes('another project')");
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/unknown-workspace-page'});await pause(600);
 await check('Unknown route shows recovery',"document.querySelector('.spa-error')?.textContent.includes('does not exist')");
 }
 if(checks.some(c=>c.result!==true)||errors.length)process.exitCode=1;console.log(JSON.stringify({mode:(spaMode?'React SPA':'Legacy fallback')+', real Edge, fixture APIs, no performance load',checks,errors},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(ws&&ws.readyState===1){ws.send(JSON.stringify({id:++sequence,method:'Browser.close'}));await pause(150);ws.close();}if(browser)browser.kill();if(server)server.close();});
