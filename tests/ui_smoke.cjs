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
const profiles={};let lastPlanRequest,browser,ws,server,send;const checks=[],errors=[],downloads=[],pending=new Map();let sequence=0;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
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
   lastPlanRequest=body;data={plan_id:'named-plan',provider:'fixture',load_model:{test_name:body.test_name,target_base_url:body.target_base_url,scenarios:[{name:'Browse',weight:1,steps:[{name:'Products',method:'GET',path:'/products'}],think_time:{min_seconds:1,max_seconds:2}}],load_profile:{type:'ramp',stages:[{duration_seconds:30,target_users:3}]},thresholds:[]}};
  }else if(p.endsWith('/workloads')){
   if(req.method==='POST'){data={...body,workload_id:'profile-one'};profiles[p]=[data];}else data={workloads:profiles[p]||[]};
  }else if(p.endsWith('/project'))data={plan_id:'named-plan',project_id:body.project_id};
  else if(p==='/api/tools')data={tools:['k6','locust','jmeter','gatling']};
  else if(p.startsWith('/api/plans/')){
   const planId=p.split('/')[3],run=runs.find(r=>r.plan_id===planId);
   if(run)data={plan_id:planId,project_id:run.project_id,target:run.target,goal:run.test_name,scripts:[],load_model:{test_name:run.test_name,target_base_url:run.target,scenarios:[{name:'Browse',weight:1,steps:[{name:'Products',method:'GET',path:'/products'}],think_time:{min_seconds:1,max_seconds:2}}],load_profile:{type:'ramp',stages:[{duration_seconds:30,target_users:3}]},thresholds:[]}};
   else{res.statusCode=404;data={detail:'Test not found'};}
  }else if(p==='/api/plans')data={plans:runs.filter(r=>!url.searchParams.get('project_id')||r.project_id===url.searchParams.get('project_id')).map(r=>({plan_id:r.plan_id,test_name:r.test_name,target:r.target,script_count:1,created_at:r.created_at}))};
  else if(p==='/api/reporting/runs'||p==='/api/runs'){
   const visible=runs.filter(r=>(!url.searchParams.get('project_id')||r.project_id===url.searchParams.get('project_id'))&&(!url.searchParams.get('plan_id')||r.plan_id===url.searchParams.get('plan_id'))&&(!url.searchParams.get('target')||r.target.includes(url.searchParams.get('target'))));
   data={runs:visible.map(r=>url.searchParams.get('role')==='viewer'?{run_id:r.run_id,created_at:r.created_at,verdict:r.verdict,p95_ms:r.p95_ms,requests:r.requests,test_name:r.test_name,script_name:r.script_name,mode:r.mode}:{...r,has_report:true}),total:visible.length};
  }else if(p.endsWith('/readiness'))data={checks:[{name:'Engine',ok:true,detail:'Ready'}],execution:{duration_seconds:30,peak_users:3},smoke_supported:true};
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
 await evaluate("document.querySelector('#view-projects .btn').click();document.getElementById('projectName').value='New app';document.getElementById('projectTarget').value='http://fixture.test';document.querySelector('#projectForm .btn').click()");await pause(200);
 await check('Project created and selected',"currentProject?.project_id==='project-new'");
 await evaluate("document.querySelector('#activeProject .btn').click();document.getElementById('newTestName').value='Named checkout';document.getElementById('newTestPurpose').value='Verify checkout';document.querySelector('#newTestForm .btn').click()");
 await check('Test is named before planning',"newTestName==='Named checkout'&&document.getElementById('modeScriptBtn').style.display==='none'");
 await evaluate("document.getElementById('planBtn').click()");await pause(250);
 checks.push({name:'Planning receives project and test identity',result:lastPlanRequest?.project_id==='project-new'&&lastPlanRequest?.test_name==='Named checkout'});
 await evaluate("document.getElementById('workloadName').value='Average';saveWorkloadProfile()");
 await check('Workload profile saved',"document.getElementById('savedWorkload').textContent.includes('Average')");
 await evaluate("selectProject('project-a');startProjectImport('script')");
 await check('Script import is separate',"document.getElementById('modeScript').style.display==='block'&&document.querySelector('#panel1 .modeswitch').style.display==='none'");
 await evaluate("startProjectImport('git')");await check('Git inherits project repository',"document.getElementById('impRepo').value==='https://github.com/org/shop.git'");
 await evaluate("showView('admin');document.getElementById('adminToken').value='wrong';loadAdminOverview()");await check('Admin denial visible',"document.getElementById('adminOverview').textContent.includes('Administrator access')");
 await evaluate("document.getElementById('adminToken').value='fixture-admin';loadAdminOverview()");await check('Admin sees other projects',"document.getElementById('adminOverview').textContent.includes('Payments')");
 await evaluate("showView('projects');toggleSidebar()");await check('Collapsed toggle remains inside sidebar',"(()=>{const a=document.querySelector('.sb-toggle').getBoundingClientRect(),b=document.querySelector('.sidebar').getBoundingClientRect();return a.width>0&&a.left>=b.left&&a.right<=b.right})()");
 await send('Page.reload');await pause(500);await check('Sidebar state survives reload',"document.getElementById('sidebar').classList.contains('collapsed')");
 await evaluate("selectProject('project-a');toggleSidebar();showView('dashboard')");await pause(250);
 await check('Recent reports available',"document.querySelectorAll('#sdTable [data-report-id]').length===3");
 await check('Dashboard scoped to project',"!document.querySelector('#sdTable tbody').textContent.includes('Hidden payment test')");
 await check('Names distinguish same-target tests',"document.querySelector('#sdTable tbody').textContent.includes('Product browsing')&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await check('Requests visible in default view',"document.getElementById('sdHead').textContent.includes('Requests')");
 await evaluate("document.getElementById('sdTest').value='plan-c';loadStakeholder()");await check('Test filter isolates a workload',"document.querySelectorAll('#sdTable tbody tr').length===1&&document.querySelector('#sdTable tbody').textContent.includes('Login flow')");
 await evaluate('resetDashboardFilters()');await pause(150);await check('Comparison rendered',"document.querySelectorAll('#sdComparison tbody tr').length>0");
 await evaluate("document.getElementById('sdTarget').value='second';loadStakeholder()");await check('Target filter',"document.querySelectorAll('#sdTable tbody tr').length===1");
 await evaluate('resetDashboardFilters()');await pause(150);await evaluate("document.querySelector('#sdTable [data-report-id]').click()");await pause(150);
 await check('Saved report opens',"document.getElementById('panel5').classList.contains('show')&&document.getElementById('reportSummary').textContent==='Fixture report'");
 await check('Report has own identity',"reportContext.savedId==='saved-a'&&currentRunId===null");await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:os.tmpdir()});await evaluate('downloadReport()');await pause(200);checks.push({name:'Download uses displayed report',result:downloads.includes('/api/runs/saved-a/report/download')});
 await evaluate('selectReportBaseline()');await check('Baseline saved',"getSelectedBaseline()==='saved-a'");await evaluate('clearSelectedBaseline()');await check('Baseline cleared','getSelectedBaseline()===null');
 await evaluate("currentScriptId='script-a';checkReadiness()");await check('Readiness checklist shown',"document.getElementById('readinessResult').textContent.includes('Before you run')");
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
