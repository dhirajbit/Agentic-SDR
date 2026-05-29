"""Best Roadways SDR — local control panel (Flask).

Runs on http://127.0.0.1:8765. Lets Best Roadways enter their Brevo + ERPNext
keys, upload a leads CSV (analyzed by Gemini), run the SDR (sender) + Observer
cycles, and watch the logs. Dry-run by default; a Live-send toggle enables real
Brevo/WhatsApp sends. The Cloudflare page is the public read-only mirror.

    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/app.py
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv, set_key
from flask import Flask, jsonify, request, Response

TENANT_DIR = Path(__file__).resolve().parent
ENV_PATH = TENANT_DIR / ".env"
load_dotenv(ENV_PATH)

import sdr_cycle
import lead_analyzer

TRACKER = TENANT_DIR / "outreach_tracker.json"
QUEUE = TENANT_DIR / "qualified_leads.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
URGENT = TENANT_DIR / "urgent_followups.json"
LEADS_CSV = TENANT_DIR / "leads.csv"
SETTINGS = TENANT_DIR / "panel_settings.json"
LOG = TENANT_DIR / "cycle.log"

app = Flask(__name__)

_run_lock = threading.Lock()
_running = {"cycle": None}  # name of in-flight cycle, or None
_last_run = {"sdr": 0.0, "observer": 0.0}

CONFIG_KEYS = [
    "BREVO_API_KEY", "BREVO_SENDER_NAME", "BREVO_SENDER_EMAIL",
    "ERPNEXT_URL", "ERPNEXT_API_KEY", "ERPNEXT_API_SECRET",
]


# ----------------------------- helpers -----------------------------

def _load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _settings():
    return _load(SETTINGS, {"live_send": False, "auto_loop": False})


def _save_settings(s):
    SETTINGS.write_text(json.dumps(s, indent=2))


def _mask(val):
    if not val:
        return ""
    return ("*" * max(0, len(val) - 4)) + val[-4:] if len(val) > 4 else "****"


def _busy():
    return _running["cycle"] is not None


# ----------------------------- API -----------------------------

@app.get("/api/config")
def get_config():
    load_dotenv(ENV_PATH, override=True)
    out = {}
    for k in CONFIG_KEYS:
        v = os.getenv(k) or ""
        # Non-secret fields echo plainly; secrets are masked.
        if k in ("BREVO_SENDER_NAME", "BREVO_SENDER_EMAIL", "ERPNEXT_URL"):
            out[k] = {"set": bool(v), "value": v}
        else:
            out[k] = {"set": bool(v), "value": _mask(v)}
    out["GEMINI_API_KEY"] = {"set": bool(os.getenv("GEMINI_API_KEY")), "value": "configured"}
    return jsonify(out)


@app.post("/api/config")
def save_config():
    data = request.get_json(force=True) or {}
    saved = []
    for k in CONFIG_KEYS:
        if k in data and data[k] is not None:
            val = str(data[k]).strip()
            # Skip masked placeholders so re-saving the form doesn't overwrite real keys.
            if val and set(val[:-4]) == {"*"}:
                continue
            set_key(str(ENV_PATH), k, val, quote_mode="never")
            saved.append(k)
    load_dotenv(ENV_PATH, override=True)
    return jsonify({"ok": True, "saved": saved})


@app.post("/api/upload")
def upload_csv():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith(".csv"):
        return jsonify({"ok": False, "error": "Please upload a .csv file."}), 400
    f.save(str(LEADS_CSV))
    steps = {}
    try:
        import importlib
        for mod_name, fn in (("sync_leads", "sync"), ("qualify_leads", "main"), ("merge_verdicts", "main")):
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            getattr(mod, fn)()
            steps[mod_name] = "ok"
    except Exception as e:
        return jsonify({"ok": False, "error": f"Pipeline failed: {e}", "steps": steps}), 500

    queue = _load(QUEUE, [])
    try:
        analysis = lead_analyzer.analyze_leads(queue)
    except Exception as e:
        analysis = f"(analysis unavailable: {e})"
    sdr_cycle.log(f"CSV uploaded ({f.filename}); queue rebuilt -> {len(queue)} qualified leads.")
    return jsonify({"ok": True, "queue_depth": len(queue), "analysis": analysis, "steps": steps})


def _run_cycle(name, fn, *args, **kwargs):
    with _run_lock:
        if _busy():
            return {"ok": False, "error": f"A {_running['cycle']} cycle is already running."}
        _running["cycle"] = name
    try:
        result = fn(*args, **kwargs)
        _last_run[name] = time.time()
        return {"ok": True, "result": result}
    except Exception as e:
        sdr_cycle.log(f"{name} cycle error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        _running["cycle"] = None


@app.post("/api/run/sdr")
def run_sdr():
    s = _settings()
    limit = int((request.get_json(silent=True) or {}).get("limit", 10))
    return jsonify(_run_cycle("sdr", sdr_cycle.run_sdr_cycle, live_send=s.get("live_send", False), limit=limit))


@app.post("/api/run/observer")
def run_observer():
    return jsonify(_run_cycle("observer", sdr_cycle.run_observer_cycle))


@app.get("/api/state")
def state():
    tracker = _load(TRACKER, {})
    agg = tracker.get("aggregate_stats", {})
    s = _settings()
    return jsonify({
        "stats": agg,
        "framework_performance": tracker.get("framework_performance", {}),
        "queue_depth": len(_load(QUEUE, [])),
        "blocked": len(_load(BLOCKED, [])),
        "urgent": len(_load(URGENT, [])),
        "actions": len(tracker.get("actions", [])),
        "recent_actions": tracker.get("actions", [])[-12:][::-1],
        "live_send": s.get("live_send", False),
        "auto_loop": s.get("auto_loop", False),
        "in_window": sdr_cycle.in_send_window(),
        "send_window": f"{sdr_cycle.SEND_WINDOW_START}-{sdr_cycle.SEND_WINDOW_END}",
        "running": _running["cycle"],
        "brevo_ready": bool(os.getenv("BREVO_API_KEY") and os.getenv("BREVO_SENDER_EMAIL")),
        "erpnext_ready": bool(os.getenv("ERPNEXT_URL") and os.getenv("ERPNEXT_API_KEY")),
        "gemini_ready": bool(os.getenv("GEMINI_API_KEY")),
    })


@app.get("/api/logs")
def logs():
    tail = int(request.args.get("tail", 200))
    if not LOG.exists():
        return jsonify({"lines": []})
    lines = LOG.read_text().splitlines()[-tail:]
    return jsonify({"lines": lines})


@app.post("/api/settings")
def settings_post():
    data = request.get_json(force=True) or {}
    s = _settings()
    for k in ("live_send", "auto_loop"):
        if k in data:
            s[k] = bool(data[k])
    _save_settings(s)
    sdr_cycle.log(f"Settings updated: {s}")
    return jsonify({"ok": True, "settings": s})


@app.post("/api/publish")
def publish():
    try:
        import generate_dashboard
        generate_dashboard.main()
    except Exception as e:
        return jsonify({"ok": False, "error": f"dashboard gen failed: {e}"}), 500
    try:
        proc = subprocess.run(
            ["bash", str(TENANT_DIR / "deploy_dashboard.sh")],
            cwd=str(TENANT_DIR.parents[1]), capture_output=True, text=True, timeout=180,
        )
        ok = proc.returncode == 0
        out = (proc.stdout + proc.stderr)[-1500:]
        sdr_cycle.log(f"Publish to Cloudflare: {'ok' if ok else 'FAILED'}")
        return jsonify({"ok": ok, "output": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


# ----------------------------- auto-loop -----------------------------

def _auto_loop():
    while True:
        time.sleep(30)
        try:
            s = _settings()
            if not s.get("auto_loop") or _busy() or not sdr_cycle.in_send_window():
                continue
            now = time.time()
            if now - _last_run["sdr"] >= 3600:
                _run_cycle("sdr", sdr_cycle.run_sdr_cycle, live_send=s.get("live_send", False), limit=10)
            elif now - _last_run["observer"] >= 3 * 3600:
                _run_cycle("observer", sdr_cycle.run_observer_cycle)
        except Exception as e:
            sdr_cycle.log(f"auto-loop error: {e}")


# ----------------------------- page -----------------------------

PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best Roadways — SDR Control Panel</title>
<style>
:root{--bg:#f5f7fa;--panel:#fff;--ink:#10243a;--muted:#5c6b7e;--line:#e3e9f0;--brand:#0b3d62;--accent:#e8521f;--good:#1f7a4a;--warn:#b86a00}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 22px 80px}
header{display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px}
.logo{width:48px;height:48px;border-radius:9px;background:var(--brand);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px}
h1{font-size:19px;margin:0;color:var(--brand)}.sub{font-size:13px;color:var(--muted)}
.right{margin-left:auto;text-align:right;font-size:12px;color:var(--muted)}
.pill{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:700}
.pill.on{background:#eaf4ee;color:var(--good)}.pill.off{background:#fdf3e3;color:var(--warn)}.pill.live{background:#fdecea;color:#b3261e}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.stat .n{font-size:24px;font-weight:800}.stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:16px}
.panel h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--brand);margin:0 0 12px}
label{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
input[type=text],input[type=password]{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:7px;font-size:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
button{background:var(--brand);color:#fff;border:0;border-radius:7px;padding:9px 14px;font-size:14px;font-weight:600;cursor:pointer}
button.alt{background:#eef2f7;color:var(--ink)}button.go{background:var(--accent)}button:disabled{opacity:.5;cursor:not-allowed}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:10px}
.toggle{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600}
.note{font-size:12px;color:var(--muted);margin-top:6px}
pre{background:#0c1622;color:#cfe3f5;border-radius:8px;padding:12px;font-size:12px;line-height:1.5;max-height:320px;overflow:auto;white-space:pre-wrap}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{font-size:11px;text-transform:uppercase;color:var(--muted)}
.tag{font-size:11px;padding:1px 7px;border-radius:999px;background:#eef2f7}.tag.dry{background:#fdf3e3;color:var(--warn)}.tag.sent{background:#eaf4ee;color:var(--good)}
.md{font-size:14px;line-height:1.6;white-space:pre-wrap;background:#f8fafc;border:1px solid var(--line);border-radius:8px;padding:12px;margin-top:10px}
@media(max-width:720px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<header>
  <div class="logo">BR</div>
  <div><h1>Best Roadways — SDR Control Panel</h1>
  <div class="sub">Leads via ERPNext/CSV · Drafting by Gemini · Email via Brevo · Follow-up via WhatsApp</div></div>
  <div class="right">
    <span id="mode" class="pill off">—</span>
    <div style="margin-top:5px"><a href="https://best-roadways-sdr.pages.dev" target="_blank">public dashboard ↗</a></div>
  </div>
</header>

<div class="grid">
  <div class="stat"><div class="n" id="s_sends">0</div><div class="l">Emails sent/drafted</div></div>
  <div class="stat"><div class="n" id="s_open">—</div><div class="l">Open rate</div></div>
  <div class="stat"><div class="n" id="s_queue">0</div><div class="l">Queue depth</div></div>
  <div class="stat"><div class="n" id="s_wa">0</div><div class="l">WhatsApp touches</div></div>
</div>

<div class="panel">
  <h2>1 · API keys</h2>
  <div class="note">Saved only to this machine's local <code>.env</code> (never committed, never sent anywhere). Gemini is <b id="gem">checking…</b>.</div>
  <div class="two">
    <div><label>Brevo API key</label><input id="BREVO_API_KEY" type="password" placeholder="xkeysib-…"></div>
    <div><label>Brevo sender email (verified in Brevo)</label><input id="BREVO_SENDER_EMAIL" type="text" placeholder="sdr@bestroadways.com"></div>
    <div><label>Brevo sender name</label><input id="BREVO_SENDER_NAME" type="text" placeholder="Best Roadways"></div>
    <div><label>ERPNext URL</label><input id="ERPNEXT_URL" type="text" placeholder="https://erp.bestroadways.com"></div>
    <div><label>ERPNext API key</label><input id="ERPNEXT_API_KEY" type="password"></div>
    <div><label>ERPNext API secret</label><input id="ERPNEXT_API_SECRET" type="password"></div>
  </div>
  <div class="row"><button onclick="saveConfig()">Save keys</button><span id="cfgmsg" class="note"></span></div>
</div>

<div class="panel">
  <h2>2 · Upload leads CSV — Gemini analyzes</h2>
  <div class="note">Drops your list into <code>leads.csv</code>, rebuilds the qualified queue, and asks Gemini for an ICP read.</div>
  <div class="row"><input id="csv" type="file" accept=".csv"><button class="alt" onclick="upload()">Upload &amp; analyze</button><span id="upmsg" class="note"></span></div>
  <div id="analysis" class="md" style="display:none"></div>
</div>

<div class="panel">
  <h2>3 · Run cycles</h2>
  <div class="row">
    <span class="toggle"><input type="checkbox" id="live" onchange="setToggle('live_send',this.checked)"> Live send (off = dry-run)</span>
    <span class="toggle"><input type="checkbox" id="auto" onchange="setToggle('auto_loop',this.checked)"> Auto-loop (SDR hourly, Observer 3h)</span>
  </div>
  <div class="row">
    <button class="go" id="btnSdr" onclick="run('sdr')">▶ Run SDR (sender) cycle</button>
    <button class="alt" id="btnObs" onclick="run('observer')">Run Observer cycle</button>
    <button class="alt" onclick="publish()">Publish to Cloudflare</button>
    <span id="runmsg" class="note"></span>
  </div>
  <div class="note" id="windownote"></div>
</div>

<div class="panel">
  <h2>Recent actions</h2>
  <table><thead><tr><th>When</th><th>Company</th><th>Channel</th><th>Framework</th><th>Subject</th><th>Status</th></tr></thead>
  <tbody id="actions"><tr><td colspan="6" class="note">No actions yet.</td></tr></tbody></table>
</div>

<div class="panel">
  <h2>Logs <span class="note">(live)</span></h2>
  <pre id="log">…</pre>
</div>

</div>
<script>
const $=id=>document.getElementById(id);
async function jget(u){return (await fetch(u)).json()}
async function jpost(u,b){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})).json()}

async function loadConfig(){
  const c=await jget('/api/config');
  $('gem').textContent=c.GEMINI_API_KEY.set?'configured ✓':'NOT set';
  for(const k of ['BREVO_API_KEY','BREVO_SENDER_EMAIL','BREVO_SENDER_NAME','ERPNEXT_URL','ERPNEXT_API_KEY','ERPNEXT_API_SECRET']){
    if(c[k] && c[k].set && c[k].value && $(k)) $(k).placeholder=c[k].value;
  }
}
async function saveConfig(){
  const body={};
  for(const k of ['BREVO_API_KEY','BREVO_SENDER_EMAIL','BREVO_SENDER_NAME','ERPNEXT_URL','ERPNEXT_API_KEY','ERPNEXT_API_SECRET']){
    if($(k).value.trim()) body[k]=$(k).value.trim();
  }
  $('cfgmsg').textContent='saving…';
  const r=await jpost('/api/config',body);
  $('cfgmsg').textContent=r.ok?('saved: '+(r.saved.join(', ')||'(nothing)')):('error');
  for(const k of Object.keys(body)) $(k).value='';
  loadConfig();
}
async function upload(){
  const f=$('csv').files[0]; if(!f){$('upmsg').textContent='pick a .csv first';return}
  $('upmsg').textContent='uploading + analyzing…';
  const fd=new FormData(); fd.append('file',f);
  const r=await (await fetch('/api/upload',{method:'POST',body:fd})).json();
  if(!r.ok){$('upmsg').textContent='error: '+(r.error||'failed');return}
  $('upmsg').textContent='queue depth: '+r.queue_depth;
  $('analysis').style.display='block'; $('analysis').textContent=r.analysis;
  refresh();
}
async function setToggle(key,val){await jpost('/api/settings',{[key]:val}); refresh();}
async function run(which){
  $('btnSdr').disabled=true; $('btnObs').disabled=true; $('runmsg').textContent=which+' cycle running…';
  const r=await jpost('/api/run/'+which,{});
  $('runmsg').textContent=r.ok?(which+' done: '+JSON.stringify(r.result)):('error: '+r.error);
  $('btnSdr').disabled=false; $('btnObs').disabled=false; refresh();
}
async function publish(){
  $('runmsg').textContent='publishing to Cloudflare…';
  const r=await jpost('/api/publish',{});
  $('runmsg').textContent=r.ok?'published ✓':('publish error: '+(r.error||''));
}
function pct(o,d){return d? (100*o/d).toFixed(1)+'%':'—'}
async function refresh(){
  const s=await jget('/api/state');
  $('s_sends').textContent=s.stats.sends||0;
  $('s_open').textContent=pct(s.stats.opens||0,s.stats.delivered||0);
  $('s_queue').textContent=s.queue_depth||0;
  $('s_wa').textContent=s.stats.whatsapp_sends||0;
  $('live').checked=s.live_send; $('auto').checked=s.auto_loop;
  const m=$('mode'); if(s.live_send){m.className='pill live';m.textContent='LIVE SEND'}else{m.className='pill off';m.textContent='DRY-RUN'}
  $('windownote').textContent=(s.in_window?'✓ inside':'✗ outside')+' send window '+s.send_window
    +' · Brevo '+(s.brevo_ready?'ready':'not set')+' · ERPNext '+(s.erpnext_ready?'ready':'not set')
    +(s.running?(' · running: '+s.running):'');
  const tb=$('actions');
  if(s.recent_actions && s.recent_actions.length){
    tb.innerHTML=s.recent_actions.map(a=>{
      const st=a.status==='sent'?'<span class="tag sent">sent</span>':(a.dry_run?'<span class="tag dry">dry-run</span>':'<span class="tag">'+(a.status||'')+'</span>');
      return '<tr><td>'+(a.ts||'').slice(5,16)+'</td><td>'+(a.company||'')+'</td><td>'+(a.channel||'')+'</td><td>'+(a.framework||'')+'</td><td>'+((a.subject||'').slice(0,42))+'</td><td>'+st+'</td></tr>';
    }).join('');
  }
}
async function refreshLogs(){
  const r=await jget('/api/logs?tail=200');
  const el=$('log'); el.textContent=(r.lines||[]).join('\n')||'(no logs yet)'; el.scrollTop=el.scrollHeight;
}
loadConfig(); refresh(); refreshLogs();
setInterval(refresh,4000); setInterval(refreshLogs,4000);
</script>
</body></html>"""


def main():
    port = int(os.getenv("PANEL_PORT", "8765"))
    threading.Thread(target=_auto_loop, daemon=True).start()
    print(f"\n  Best Roadways SDR control panel → http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
