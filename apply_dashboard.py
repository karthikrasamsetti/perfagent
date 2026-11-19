"""One-shot patch: add the Stakeholder dashboard to index.html.

Run from the project root:  python apply_dashboard.py
It edits src/perfagent/web/index.html in place (idempotent: safe to run twice;
it detects if the dashboard is already present and does nothing).
A backup index.html.bak is written first if one doesn't already exist.
"""
from pathlib import Path
import shutil

INDEX = Path("src/perfagent/web/index.html")
NL = "\r\n"

CARD = (
'  <!-- STAKEHOLDER DASHBOARD -->' + NL +
'  <div class="card">' + NL +
'    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">' + NL +
'      <h2 style="margin:0;font-size:14px">\U0001F4CA Stakeholder dashboard</h2>' + NL +
'      <button class="btn ghost sm" onclick="loadStakeholder()">\u21BB Refresh</button>' + NL +
'      <span class="muted">run history &amp; p95 trend \u2014 scoped to the chosen role</span>' + NL +
'      <div class="spacer"></div>' + NL +
'      <label for="sdRole" style="margin:0;font-size:12px">View as</label>' + NL +
'      <select id="sdRole" style="width:auto;padding:5px 9px" onchange="loadStakeholder()">' + NL +
'        <option value="executive">Executive</option>' + NL +
'        <option value="qa_lead">QA lead</option>' + NL +
'        <option value="engineer">Engineer</option>' + NL +
'        <option value="viewer">Viewer</option>' + NL +
'      </select>' + NL +
'    </div>' + NL +
'' + NL +
'    <div class="tiles" id="sdTiles" style="grid-template-columns:repeat(3,1fr);margin:14px 0 8px"></div>' + NL +
'' + NL +
'    <div class="mini" style="margin-top:10px">p95 latency across runs (ms)</div>' + NL +
'    <canvas id="sdTrend" height="130" style="width:100%;margin:4px 0 14px;border:1px solid var(--line);border-radius:12px;background:#fcfcfb"></canvas>' + NL +
'' + NL +
'    <table id="sdTable" style="margin-top:4px"><thead><tr id="sdHead"></tr></thead><tbody></tbody></table>' + NL +
'    <div class="muted" id="sdEmpty" style="display:none;padding:10px 2px">No runs recorded yet. Run a plan to populate this.</div>' + NL +
'  </div>' + NL +
'' + NL
)

JS = (
'/* ---------- stakeholder dashboard ---------- */' + NL +
'/* Reads /api/reporting/runs (role-scoped) and /api/reporting/trend.' + NL +
'   Columns shown depend on the role, so switching role visibly changes' + NL +
'   what that stakeholder can see. Reuses .tile/.pill/table styles. */' + NL +
'const SD_COLS=[' + NL +
"  ['created_at','When'],['target','Target'],['goal','Goal'],['verdict','Verdict']," + NL +
"  ['requests','Requests'],['error_rate','Errors'],['p95_ms','p95'],['p99_ms','p99']," + NL +
"  ['avg_ms','Avg'],['rps','RPS'],['run_id','Run']," + NL +
'];' + NL +
'function sdFmt(k,v){' + NL +
"  if(v===null||v===undefined) return '';" + NL +
"  if(k==='created_at') return new Date(v).toLocaleString();" + NL +
"  if(k==='error_rate') return (v*100).toFixed(2)+'%';" + NL +
"  if(k==='p95_ms'||k==='p99_ms'||k==='avg_ms') return (+v).toFixed(2)+' ms';" + NL +
"  if(k==='rps') return (+v).toFixed(2)+'/s';" + NL +
"  if(k==='run_id') return String(v).slice(0,8);" + NL +
'  return v;' + NL +
'}' + NL +
'function sdVerdict(v){' + NL +
"  const m={pass:['pass','PASS'],fail:['fail','FAIL'],inconclusive:['na','INCONCLUSIVE']}[v]||['ghost',(v||'?').toUpperCase()];" + NL +
"  return '<span class=\"pill '+m[0]+'\">'+m[1]+'</span>';" + NL +
'}' + NL +
'async function loadStakeholder(){' + NL +
"  const role=document.getElementById('sdRole').value;" + NL +
"  const head=document.getElementById('sdHead');" + NL +
"  const body=document.querySelector('#sdTable tbody');" + NL +
"  const empty=document.getElementById('sdEmpty');" + NL +
"  const tiles=document.getElementById('sdTiles');" + NL +
'  let runs=[];' + NL +
'  try{' + NL +
"    const j=await (await fetch('/api/reporting/runs?role='+role+'&limit=100')).json();" + NL +
'    runs=j.runs||[];' + NL +
"  }catch(e){ body.innerHTML='<tr><td class=\"muted\">Could not load: '+esc(e.message)+'</td></tr>'; return; }" + NL +
'' + NL +
'  const present = runs.length ? new Set(Object.keys(runs[0])) : new Set();' + NL +
'  const cols = SD_COLS.filter(([k])=>present.has(k));' + NL +
"  head.innerHTML = cols.map(([,l])=>'<th>'+l+'</th>').join('');" + NL +
'' + NL +
"  if(!runs.length){ body.innerHTML=''; empty.style.display='block'; }" + NL +
'  else{' + NL +
"    empty.style.display='none';" + NL +
"    body.innerHTML = runs.map(r=>'<tr>'+cols.map(([k])=>" + NL +
"      '<td>'+(k==='verdict'?sdVerdict(r[k]):sdFmt(k,r[k]))+'</td>').join('')+'</tr>').join('');" + NL +
'  }' + NL +
'' + NL +
'  const total=runs.length;' + NL +
"  const passes=runs.filter(r=>r.verdict==='pass').length;" + NL +
'  const p95s=runs.map(r=>r.p95_ms).filter(v=>v!=null);' + NL +
'  const worst=p95s.length?Math.max(...p95s):null;' + NL +
'  tiles.innerHTML=' + NL +
"    '<div class=\"tile\"><div class=\"v\">'+total+'</div><div class=\"l\">Runs</div></div>'+" + NL +
"    '<div class=\"tile\"><div class=\"v\">'+(total?Math.round(100*passes/total):0)+'%</div><div class=\"l\">Pass rate</div></div>'+" + NL +
"    '<div class=\"tile\"><div class=\"v\">'+(worst!=null?worst.toFixed(2)+' ms':'\u2014')+'</div><div class=\"l\">Worst p95</div></div>';" + NL +
'' + NL +
'  sdDrawTrend();' + NL +
'}' + NL +
'async function sdDrawTrend(){' + NL +
"  const c=document.getElementById('sdTrend'); if(!c) return;" + NL +
'  let pts=[];' + NL +
"  try{ const j=await (await fetch('/api/reporting/trend?metric=p95_ms&limit=30')).json(); pts=j.points||[]; }catch(e){}" + NL +
"  _lineChart(c,[{data:pts.map((p,i)=>({x:i,y:p.value})),color:'#9a6412'}]);" + NL +
'}' + NL +
'' + NL
)


def main():
    if not INDEX.exists():
        raise SystemExit(f"Cannot find {INDEX} - run this from the project root.")
    with open(INDEX, "r", encoding="utf-8", newline="") as _f:
        src = _f.read()

    if "STAKEHOLDER DASHBOARD" in src:
        print("Dashboard already present - nothing to do.")
        return

    bak = INDEX.with_suffix(".html.autobak")
    if not bak.exists():
        shutil.copyfile(INDEX, bak)
        print(f"Backup written: {bak}")

    # 1. card before the Runs & reports history card
    a1 = "  <!-- RUNS / REPORTS HISTORY -->"
    if src.count(a1) != 1:
        raise SystemExit("Anchor for the card not found exactly once - aborting.")
    src = src.replace(a1, CARD + a1, 1)

    # 2. JS before the runs-history comment
    a2 = "/* ---------- runs & reports history ---------- */"
    if src.count(a2) != 1:
        raise SystemExit("Anchor for the JS not found exactly once - aborting.")
    src = src.replace(a2, JS + a2, 1)

    # 3. init call
    a3 = "loadRuns();" + NL + "loadAudit();"
    if src.count(a3) != 1:
        raise SystemExit("Anchor for the init call not found exactly once - aborting.")
    src = src.replace(a3, "loadRuns();" + NL + "loadStakeholder();" + NL + "loadAudit();", 1)

    with open(INDEX, "w", encoding="utf-8", newline="") as _f:
        _f.write(src)
    print("Done. index.html now has the Stakeholder dashboard.")
    print("Hard-refresh the browser (Ctrl+Shift+R) to see it.")


if __name__ == "__main__":
    main()
