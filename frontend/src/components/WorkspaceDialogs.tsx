import type { CSSProperties } from 'react'
import { handlers } from '../workspace/controller'

export function WorkspaceDialogs() {
return <>
<div id={"bodyModal"} style={{"display": "none", "position": "fixed", "inset": "0", "background": "rgba(20,30,26,.45)", "zIndex": "2000", "alignItems": "center", "justifyContent": "center"} as CSSProperties}>
<div style={{"background": "#fff", "borderRadius": "14px", "width": "min(680px,92vw)", "maxHeight": "88vh", "display": "flex", "flexDirection": "column", "boxShadow": "0 10px 40px rgba(0,0,0,.25)"} as CSSProperties}>
<div style={{"padding": "16px 20px", "borderBottom": "1px solid var(--line)", "display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<b style={{"fontSize": "15px", "color": "var(--teal-d)"} as CSSProperties}>
{"Request body"}
</b>
<span className={"muted"} id={"bodyModalPath"}>

</span>
<div style={{"flex": "1"} as CSSProperties}>

</div>
<button className={"iconbtn"} onClick={handlers.h108} style={{"fontSize": "18px"} as CSSProperties}>
{"×"}
</button>
</div>
<div style={{"padding": "16px 20px", "overflow": "auto"} as CSSProperties}>
<textarea id={"bodyModalText"} style={{"minHeight": "280px", "width": "100%", "fontFamily": "ui-monospace,Menlo,monospace", "fontSize": "12.5px"} as CSSProperties} placeholder={"{\"field\":\"value\"}"}>

</textarea>
<div className={"note"} id={"bodyModalNote"} style={{"display": "none"} as CSSProperties}>

</div>
<div className={"btnrow"} style={{"marginTop": "12px"} as CSSProperties}>
<button className={"btn"} onClick={handlers.h109} id={"dynBtn"}>
{"✨ Add dynamic data (AI)"}
</button>
<span className={"muted"} style={{"margin": "0"} as CSSProperties}>
{"AI assigns unique/random generators to the fields that should vary"}
</span>
<i className={"infohint"} data-tip={"Dynamic data = values that change per request. Unique email/id so signups don't collide; random numbers; real values from your uploaded CSV. The AI picks the right source per field."}>
{"i"}
</i>
</div>
</div>
<div style={{"padding": "14px 20px", "borderTop": "1px solid var(--line)", "display": "flex", "gap": "10px", "justifyContent": "flex-end"} as CSSProperties}>
<button className={"btn ghost"} onClick={handlers.h110}>
{"Cancel"}
</button>
<button className={"btn"} onClick={handlers.h111}>
{"Save body"}
</button>
</div>
</div>
</div>
<div id={"suggestModal"} style={{"display": "none", "position": "fixed", "inset": "0", "background": "rgba(20,30,26,.45)", "zIndex": "2000", "alignItems": "center", "justifyContent": "center"} as CSSProperties}>
<div style={{"background": "#fff", "borderRadius": "14px", "width": "min(640px,92vw)", "maxHeight": "88vh", "display": "flex", "flexDirection": "column", "boxShadow": "0 10px 40px rgba(0,0,0,.25)"} as CSSProperties}>
<div style={{"padding": "16px 20px", "borderBottom": "1px solid var(--line)", "display": "flex", "alignItems": "center", "gap": "10px"} as CSSProperties}>
<b style={{"fontSize": "15px", "color": "var(--teal-d)"} as CSSProperties}>
{"✨ Suggest checks from a response"}
</b>
<div style={{"flex": "1"} as CSSProperties}>

</div>
<button className={"iconbtn"} onClick={handlers.h112} style={{"fontSize": "18px"} as CSSProperties}>
{"×"}
</button>
</div>
<div style={{"padding": "16px 20px", "overflow": "auto"} as CSSProperties}>
<div className={"muted"} style={{"marginBottom": "8px"} as CSSProperties}>
{"Paste a "}
<b>
{"real response"}
</b>
{" you got from this endpoint (run it in Postman/curl first). The AI will suggest validation checks — which elements should be present, which errors to guard against, which numbers should be positive. You review and keep the ones you want."}
</div>
<div className={"note info"} style={{"margin": "0 0 8px"} as CSSProperties}>
{"🛡 The response is redacted (secrets/PII removed) before the AI sees it — only the structure is sent."}
</div>
<textarea id={"suggestSample"} style={{"minHeight": "160px", "width": "100%", "fontFamily": "ui-monospace,Menlo,monospace", "fontSize": "11.5px"} as CSSProperties} placeholder={"Paste the API response here (XML or JSON)..."}>

</textarea>
<div className={"note"} id={"suggestNote"} style={{"display": "none"} as CSSProperties}>

</div>
<div id={"suggestResults"} style={{"display": "none", "marginTop": "10px"} as CSSProperties}>

</div>
<div className={"btnrow"} style={{"marginTop": "12px"} as CSSProperties}>
<button className={"btn"} onClick={handlers.h113} id={"suggestBtn"}>
{"✨ Suggest checks"}
</button>
</div>
</div>
<div style={{"padding": "14px 20px", "borderTop": "1px solid var(--line)", "display": "flex", "gap": "10px", "justifyContent": "flex-end"} as CSSProperties}>
<button className={"btn ghost"} onClick={handlers.h114}>
{"Cancel"}
</button>
<button className={"btn"} onClick={handlers.h115} id={"applySuggestBtn"} style={{"display": "none"} as CSSProperties}>
{"Add selected checks"}
</button>
</div>
</div>
</div>
</>
}
