// Real Edge UI checks with fixture APIs. No external load is generated.
const http=require('http'),fs=require('fs'),os=require('os'),path=require('path'),{spawn}=require('child_process');
const spaMode=process.env.PERFAGENT_UI_MODE!=='legacy';
const webRoot=path.resolve('src/perfagent/web/spa');
const html=fs.readFileSync(spaMode?path.join(webRoot,'index.html'):'src/perfagent/web/index.html');
const projects=[{project_id:'project-a',name:'Commerce',description:'Shop tests',framework_name:'commerce',repo_url:'https://github.com/org/shop.git',branch:'performance',target_url:'http://fixture.test',environment:'staging',tests:3},{project_id:'project-b',name:'Payments',description:'Invoice tests',framework_name:'payments',branch:'main',environment:'staging',tests:1}];
const runs=[
 {run_id:'saved-a',plan_id:'plan-a',project_id:'project-a',created_at:'2026-11-18T10:00:00',target:'https://example.test',verdict:'pass',p95_ms:120,error_rate:.01,requests:100,rps:20,test_name:'Product browsing',script_name:'products.smoke.js',mode:'smoke',endpoint_summary:'GET /products'},
 {run_id:'saved-b',plan_id:'plan-b',project_id:'project-a',created_at:'2026-11-19T10:00:00',target:'https://second.test',verdict:'fail',p95_ms:240,error_rate:.04,requests:200,rps:25,test_name:'Checkout flow',script_name:'checkout.js',mode:'full',endpoint_summary:'POST /checkout'},
 {run_id:'saved-c',plan_id:'plan-c',project_id:'project-a',created_at:'2026-11-19T11:00:00',target:'https://example.test',verdict:'pass',p95_ms:100,error_rate:0,requests:150,rps:20,test_name:'Login flow',script_name:'login.js',mode:'full',endpoint_summary:'POST /login'},
 {run_id:'other-project-run',plan_id:'plan-d',project_id:'project-b',created_at:'2026-11-19T12:00:00',target:'https://payment.test',verdict:'pass',p95_ms:100,requests:100,test_name:'Hidden payment test'}];
const report={run_id:'original-a',plan_id:'plan-a',script_id:'script-a',target:'https://example.test',execution:{test_name:'Product browsing',script_name:'products.smoke.js',endpoint_summary:'GET /products'},verdict:{overall_passed:true,checks:[]},narrative:{headline:'Fixture passed',summary:'Fixture report',observations:[],recommendations:[]},snapshot:{requests:100,error_rate:.01,rps:20,latency:{p95_ms:120}},logs:['fixture log']};
const profiles={};let lastPlanRequest,browser,ws,server,send;const checks=[],errors=[],downloads=[],validationCalls=[],preflightCalls=[],pending=new Map();let sequence=0;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let showScriptHistoryFixture=false;
async function main(){
 server=http.createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname.startsWith('/assets/')){
   const asset=path.resolve(webRoot,'.'+pathname);
   if(!asset.startsWith(webRoot+path.sep)||!fs.existsSync(asset)){res.statusCode=404;res.end();return;}
   res.setHeader('Content-Type',asset.endsWith('.css')?'text/css':'application/javascript');res.end(fs.readFileSync(asset));return;
  }
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
   lastPlanRequest=body;data={plan_id:'named-plan',provider:'fixture',load_model:{test_name:body.test_name,target_base_url:body.target_base_url,scenarios:[{name:'Browse',weight:1,steps:[{name:'Products',method:'GET',path:'/products'}],think_time:{min_seconds:1,max_seconds:2}}],load_profile:body.target_request_rate?{type:'ramp',arrival_rate:body.target_request_rate,target_request_rate:body.target_request_rate,pre_allocated_vus:body.max_users,stages:[{duration_seconds:body.duration_seconds,target_users:body.max_users}]}:{type:'ramp',stages:[{duration_seconds:30,target_users:3}]},thresholds:[]}};
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
    const passed=visible.filter(run=>run.verdict==='pass').length;
    const failed=visible.filter(run=>run.verdict==='fail').length;
    data.overview={total:visible.length,passed,failed,inconclusive:visible.length-passed-failed,
      requests:visible.reduce((total,run)=>total+run.requests,0),
      worst_p95_ms:visible.length?Math.max(...visible.map(run=>run.p95_ms)):null,
      latest:data.runs[0],attention:data.runs.find(run=>run.verdict==='fail'),
      regression:visible.length>1?{run:data.runs[0],baseline_id:data.runs[1].run_id,changes:[{label:'p95 latency',previous_fmt:'100 ms',current_fmt:'140 ms'}]}:null,
      trend:[...data.runs].reverse().map(run=>({...run,t:run.created_at})),
      outcomes:visible.length?[{day:'2026-11-19',pass:passed,fail:failed,inconclusive:visible.length-passed-failed}]:[]};
   }
  }else if(/^\/api\/scripts\/version-(first|latest)\/download$/.test(p)){
   res.setHeader('Content-Type','text/plain');res.end('// '+p.split('/')[3]);return;
  }else if(p==='/api/scripts/script-a/validate'){validationCalls.push(req.method);data={ok:true};}
  else if(p==='/api/preflight'){preflightCalls.push({method:req.method,body});data={all_ok:true,ok:1,total:1,results:[{method:'GET',path:'/products',status:200,ok:true}]};}
  else if(p.endsWith('/readiness'))data={checks:[{name:'Engine',ok:true,detail:'Ready'}],execution:{duration_seconds:30,peak_users:3},smoke_supported:true};
  else if(p.endsWith('/report/download')){downloads.push(p);res.setHeader('Content-Disposition','attachment; filename="fixture-report.html"');res.setHeader('Content-Type','text/html');res.end('<h1>Fixture report</h1>');return;}
  else if(p.endsWith('/saved-report'))data=report;
  else if(p==='/api/traces')data={traces:[]};else if(p==='/api/audit')data={events:[]};else if(p==='/api/sla')data={profiles:[]};else if(p==='/api/chat/config')data={enabled:false};else if(p.includes('trend'))data={points:[]};
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 const debugPort=await new Promise(resolve=>{const probe=http.createServer();probe.listen(0,'127.0.0.1',()=>{const value=probe.address().port;probe.close(()=>resolve(value));});});
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'perfagent-ui-check-'));
 browser=spawn(process.env.PERFAGENT_EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port='+debugPort,'--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let pages;for(let i=0;i<100;i++){try{pages=await(await fetch('http://127.0.0.1:'+debugPort+'/json')).json();break;}catch{await pause(100);}}
 if(!pages)throw Error('Browser debugging unavailable');
 ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const item=pending.get(m.id);pending.delete(m.id);if(item)m.error?item.reject(m.error):item.resolve(m.result);}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);else if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')errors.push(m.params.args.map(arg=>arg.value||arg.description||'').join(' '));};
 send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 async function evaluate(expression){const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;}
 async function check(name,expression){checks.push({name,result:await evaluate(expression)});}
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/'});await pause(900);
 await check('Starts at Projects','document.getElementById("view-projects").classList.contains("show")');
 if(spaMode){
 await check('Project library is visible', "document.querySelector('.projects-intro h2').textContent==='Performance workspace'&&Boolean(document.querySelector('.project-card-meta'))");
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-projects.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await check('Generated code is collapsed by default', "document.querySelector('.script-details').open===false&&document.getElementById('preflightBtn').closest('details')===null");
 }
 await evaluate("document.querySelector('#view-projects .btn').click();document.getElementById('projectName').value='New app';document.getElementById('projectTarget').value='http://fixture.test';document.querySelector('#projectForm .btn').click()");await pause(200);
 await check('Project created and selected',"currentProject?.project_id==='project-new'");
 await evaluate("document.querySelector('#activeProject .btn').click();document.getElementById('newTestName').value='Named checkout';document.getElementById('newTestPurpose').value='Verify checkout';document.querySelector('#newTestForm .btn').click()");
 await check('Test is named before planning',"newTestName==='Named checkout'&&document.getElementById('modeScriptBtn').style.display==='none'");
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Planning receives project and test identity',result:lastPlanRequest?.project_id==='project-new'&&lastPlanRequest?.test_name==='Named checkout'});
 if(spaMode){
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
     const correct=rows.length===2&&rows[0].textContent.includes('Dataset · account_id')&&rows[0].textContent.includes('Captures order_id')&&rows[1].textContent.includes('Earlier response · order_id')&&rows[1].textContent.includes('order.status exists');
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
 await evaluate("document.querySelector('.review-editor summary').click()");
 await check('Editing target opens only its section', "document.querySelectorAll('.review-editor[open]').length===1&&document.getElementById('pfTarget').offsetWidth>0");
 await evaluate("document.querySelector('.review-editor summary').click()");
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-review.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await check('Compact review fits mobile and puts summary first', "document.documentElement.scrollWidth<=390&&document.getElementById('planSummary').getBoundingClientRect().top<document.getElementById('planForm').getBoundingClientRect().top");
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 }
 await evaluate("document.getElementById('workloadName').value='Average';saveWorkloadProfile()");
 await check('Workload profile saved',"document.getElementById('savedWorkload').textContent.includes('Average')");
 if(spaMode){
 await evaluate("document.getElementById('newTestName').value='Request rate';startNamedTest();document.getElementById('target').value='http://fixture.test/products';document.getElementById('draftSchedule').value='rate';document.getElementById('draftRequestRate').value='15'");
 await check('Describe shows a request-rate goal', "document.getElementById('draftRequestRate').offsetWidth>0&&document.getElementById('profileType').offsetWidth===0");
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Describe preserves the request-rate goal and page path',result:lastPlanRequest?.target_request_rate===15&&lastPlanRequest?.endpoints[0]?.path==='/products'});
 await check('Review shows the request rate and request count', "document.getElementById('planSummary').textContent.includes('15 requests/s')&&document.getElementById('planSummary').textContent.includes('900 HTTP requests')");
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
 await evaluate("selectProject('project-a');toggleSidebar();showView('dashboard')");await pause(250);
 await check('Recent reports available',"document.querySelectorAll('#sdTable [data-report-id]').length===3");
 if(spaMode) await check('Dashboard totals come from saved history', "document.getElementById('sdTiles').textContent.includes('450Total requests')&&document.getElementById('sdFilterNote').textContent.includes('all matching saved runs')");
 if(spaMode){
 await check('Dashboard prioritizes a failed run', "document.getElementById('sdAttention').textContent.includes('Needs attention')&&document.getElementById('sdAttention').textContent.includes('Checkout flow')");
 await check('Baseline regression displays measured change and both reports', "!document.getElementById('sdRegression').hidden&&document.getElementById('sdRegression').textContent.includes('100 ms → 140 ms')&&document.querySelectorAll('#sdRegression button').length===2");
 await check('Trend has a keyboard-accessible data table', "document.querySelectorAll('#sdTrendData tbody tr').length===3&&document.querySelector('#sdTrendData button')!==null");
 await check('Dashboard shows all four historical charts', "document.querySelectorAll('.dashboard-chart-grid figure').length===4&&document.querySelector('#sdOutcomes button').getAttribute('aria-label').includes('1 fail')");
 await check('Dashboard selected run has a report action', "!document.getElementById('sdInspectReport').disabled&&Boolean(document.getElementById('sdInspectRunNote').textContent)");
 }
 await check('Dashboard scoped to project',"!document.querySelector('#sdTable tbody').textContent.includes('Hidden payment test')");
 await check('Names distinguish same-target tests',"document.querySelector('#sdTable tbody').textContent.includes('Product browsing')&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await check('Requests visible in default view',"document.getElementById('sdHead').textContent.includes('Requests')");
 await evaluate("document.getElementById('sdTest').value='plan-c';loadStakeholder()");await check('Test filter isolates a workload',"document.querySelectorAll('#sdTable tbody tr').length===1&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await evaluate('resetDashboardFilters()');await pause(150);await check('Comparison rendered',"document.querySelectorAll('#sdComparison tbody tr').length>0");
 await evaluate("document.getElementById('sdTarget').value='second';loadStakeholder()");await check('Target filter',"document.querySelectorAll('#sdTable tbody tr').length===1");
 await evaluate('resetDashboardFilters()');await pause(150);await evaluate("document.querySelector('#sdTable [data-report-id]').click()");await pause(150);
 await check('Saved report opens',"document.getElementById('panel5').classList.contains('show')&&document.getElementById('reportSummary').textContent==='Fixture report'");
 if(spaMode){
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
   drawTsChart([{t:10,rps:12,p95:135},{t:30,rps:15,p95:210,err:0}],[{label:'Ramp up',start_s:0,end_s:15}]);
   try {
     const picker=document.getElementById('reportSampleIndex');
     picker.value='0';
     picker.dispatchEvent(new Event('input'));
     return document.querySelectorAll('.report-metric-charts canvas').length===3
       && picker.getAttribute('aria-valuetext')==='10 seconds'
       && document.getElementById('reportPlannedPhases').textContent.includes('Ramp up 0–15 s')
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
 fs.writeFileSync(path.join(os.tmpdir(),'perfagent-ui-report.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 for(const view of ['history','monitoring','activity']){await evaluate("showView('"+view+"')");await pause(100);await check(view+' navigation',"document.getElementById('view-"+view+"').classList.contains('show')");}
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await evaluate("showView('dashboard')");await pause(150);await evaluate("document.querySelector('#sdTable [data-report-id]').click()");await pause(150);await check('Mobile report fits viewport','document.documentElement.scrollWidth<=390');
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
 await check('Report opens from deep link',"reportContext?.savedId==='saved-a'&&document.getElementById('reportSummary').textContent==='Fixture report'");
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/projects/project-b/runs/saved-a'});await pause(600);
 await check('Mismatched project report is rejected',"document.querySelector('.spa-error')?.textContent.includes('another project')");
 await send('Page.navigate',{url:'http://127.0.0.1:'+port+'/unknown-workspace-page'});await pause(600);
 await check('Unknown route shows recovery',"document.querySelector('.spa-error')?.textContent.includes('does not exist')");
 }
 if(checks.some(c=>c.result!==true)||errors.length)process.exitCode=1;console.log(JSON.stringify({mode:(spaMode?'React SPA':'Legacy fallback')+', real Edge, fixture APIs, no performance load',checks,errors},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(ws&&ws.readyState===1){ws.send(JSON.stringify({id:++sequence,method:'Browser.close'}));await pause(150);ws.close();}if(browser)browser.kill();if(server)server.close();});
