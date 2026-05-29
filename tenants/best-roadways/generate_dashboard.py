"""Generate the Best Roadways SDR dashboard as a single self-contained HTML.

Pulls live state from this tenant's JSON files. No external assets — deployable as
a single index.html. Brevo + WhatsApp oriented (no Apollo credit panels).

    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/generate_dashboard.py

Output: tenants/best-roadways/sdr_dashboard.html
"""

from __future__ import annotations

import base64
import html
import json
from datetime import datetime
from pathlib import Path

TENANT_DIR = Path(__file__).resolve().parent
CONFIG = TENANT_DIR / "company_config.json"
TRACKER = TENANT_DIR / "outreach_tracker.json"
QUEUE = TENANT_DIR / "qualified_leads.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
URGENT = TENANT_DIR / "urgent_followups.json"
LOGO = TENANT_DIR / "logo.png"
OUTPUT = TENANT_DIR / "sdr_dashboard.html"


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _logo_tag() -> str:
    if LOGO.exists():
        b64 = base64.b64encode(LOGO.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b64}" alt="Best Roadways" class="logo" />'
    # Wordmark fallback — no asset shipped.
    return '<div class="logo wordmark">BR</div>'


def _stat(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="stat-sub">{html.escape(sub)}</div>' if sub else ""
    return (
        f'<div class="stat"><div class="stat-num">{html.escape(str(value))}</div>'
        f'<div class="stat-lbl">{html.escape(label)}</div>{sub_html}</div>'
    )


def _kv(label: str, value: str) -> str:
    return f'<div class="kv-row"><div class="kv-lbl">{html.escape(label)}</div><div class="kv-val">{html.escape(str(value))}</div></div>'


def render() -> str:
    cfg = _load(CONFIG, {})
    tracker = _load(TRACKER, {})
    queue = _load(QUEUE, [])
    blocked = _load(BLOCKED, [])
    urgent = _load(URGENT, [])

    agg = tracker.get("aggregate_stats", {})
    sends = agg.get("sends", 0)
    delivered = agg.get("delivered", 0)
    opens = agg.get("opens", 0)
    replies = agg.get("replies", 0)
    wa_sends = agg.get("whatsapp_sends", 0)
    wa_replies = agg.get("whatsapp_replies", 0)
    open_rate = f"{opens * 100 / delivered:.1f}%" if delivered else "—"
    reply_rate = f"{replies * 100 / delivered:.1f}%" if delivered else "—"

    company = cfg.get("company_name", "Best Roadways Limited")
    tagline = cfg.get("tagline", "")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_label = f"Live — {sends} sends logged" if sends else "Configured — awaiting first send"
    status_warn = "warn" if sends == 0 else ""

    # Framework performance rows
    fperf = tracker.get("framework_performance", {})
    frows = ""
    for name, d in fperf.items():
        s, o, r = d.get("sends", 0), d.get("opens", 0), d.get("replies", 0)
        orr = f"{o*100/s:.0f}%" if s else "—"
        rrr = f"{r*100/s:.0f}%" if s else "—"
        frows += (f"<tr><td>{html.escape(name)}</td><td class='num'>{s}</td>"
                  f"<td class='num'>{o}</td><td class='num'>{r}</td>"
                  f"<td class='num'>{orr}</td><td class='num'>{rrr}</td></tr>")

    caps = [html.escape(c) for c in cfg.get("core_capabilities", [])]
    proofs = [html.escape(p) for p in cfg.get("proof_points", [])]
    caps_html = "".join(f"<li>{c}</li>" for c in caps) or "<li>—</li>"
    proofs_html = "".join(f"<li>{p}</li>" for p in proofs) or "<li>—</li>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{html.escape(company)} — Agentic SDR</title>
<style>
:root {{
  --bg:#f5f7fa; --panel:#fff; --ink:#10243a; --muted:#5c6b7e; --line:#e3e9f0;
  --brand:#0b3d62; --accent:#e8521f; --good:#1f7a4a; --warn:#b86a00;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 24px 80px}}
header{{display:flex;align-items:center;gap:16px;padding-bottom:18px;border-bottom:1px solid var(--line);margin-bottom:22px}}
.logo{{width:56px;height:56px;border-radius:10px;object-fit:contain;background:#fff}}
.wordmark{{display:flex;align-items:center;justify-content:center;background:var(--brand);color:#fff;font-weight:800;font-size:22px;letter-spacing:1px}}
.hdr-title{{font-size:20px;font-weight:800;color:var(--brand);letter-spacing:-.01em}}
.hdr-sub{{font-size:13px;color:var(--muted);margin-top:2px}}
.hdr-right{{margin-left:auto;text-align:right;font-size:12px;color:var(--muted)}}
.status-pill{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#eaf4ee;color:var(--good);border:1px solid #c6e3d3}}
.status-pill.warn{{background:#fdf3e3;color:var(--warn);border-color:#f2d8a9}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.stat-num{{font-size:26px;font-weight:800;letter-spacing:-.02em}}
.stat-lbl{{font-size:12px;color:var(--muted);margin-top:2px;text-transform:uppercase;letter-spacing:.04em}}
.stat-sub{{font-size:12px;color:var(--accent);margin-top:4px;font-weight:600}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:18px}}
.panel h2{{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--brand);margin:0 0 12px}}
.row2{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.kv-row{{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px dashed var(--line);font-size:14px}}
.kv-row:last-child{{border-bottom:0}}
.kv-lbl{{color:var(--muted)}} .kv-val{{font-weight:600}}
ul{{margin:6px 0 0 18px;padding:0}} li{{margin:3px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}}
th{{font-weight:600;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.callout{{border-left:3px solid var(--accent);background:#fdf1ec;padding:10px 14px;border-radius:0 8px 8px 0;margin-top:10px;font-size:13px}}
footer{{margin-top:30px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}}
@media(max-width:760px){{.grid{{grid-template-columns:repeat(2,1fr)}}.row2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">

<header>
  {_logo_tag()}
  <div>
    <div class="hdr-title">{html.escape(company)} — Agentic SDR</div>
    <div class="hdr-sub">{html.escape(tagline)} · Email via Brevo · Leads via ERPNext/CSV · Follow-up via WhatsApp · Drafting by Gemini</div>
  </div>
  <div class="hdr-right">
    <span class="status-pill {status_warn}">{html.escape(status_label)}</span>
    <div style="margin-top:6px">Generated {html.escape(generated_at)} local</div>
  </div>
</header>

<div class="grid">
  {_stat('Emails sent', sends, f'{delivered} delivered')}
  {_stat('Open rate', open_rate, f'{opens} opens')}
  {_stat('Reply rate', reply_rate, f'{replies} replies / {len(urgent)} pending')}
  {_stat('WhatsApp touches', wa_sends, f'{wa_replies} replies')}
</div>

<div class="panel">
  <h2>Outreach posture</h2>
  <div class="row2">
    <div>
      {_kv('Qualified queue depth', len(queue))}
      {_kv('Blocked / opted-out', len(blocked))}
      {_kv('Urgent follow-ups pending', len(urgent))}
      {_kv('Actions logged', len(tracker.get('actions', [])))}
    </div>
    <div>
      {_kv('Email sends', sends)}
      {_kv('Delivered', delivered)}
      {_kv('Bounced', agg.get('bounced', 0))}
      {_kv('Opt-outs', agg.get('opt_outs', 0))}
    </div>
  </div>
  <div class="callout">No Apollo, no credit gate in this tenant. Leads come from ERPNext and/or
  <span style="font-family:monospace">leads.csv</span>; email sends via Brevo; the 48h follow-up rides WhatsApp.</div>
</div>

<div class="panel">
  <h2>Framework performance</h2>
  <table>
    <thead><tr><th>Framework</th><th class='num'>Sends</th><th class='num'>Opens</th><th class='num'>Replies</th><th class='num'>Open %</th><th class='num'>Reply %</th></tr></thead>
    <tbody>{frows or "<tr><td colspan='6' style='color:var(--muted)'>No sends yet.</td></tr>"}</tbody>
  </table>
</div>

<div class="panel">
  <h2>What we sell</h2>
  <div class="row2">
    <div><b style="font-size:13px;color:var(--muted)">CORE CAPABILITIES</b><ul>{caps_html}</ul></div>
    <div><b style="font-size:13px;color:var(--muted)">PROOF POINTS</b><ul>{proofs_html}</ul></div>
  </div>
</div>

<footer>
  {html.escape(company)} — Agentic SDR program. Email via Brevo · CRM via ERPNext · Follow-up via WhatsApp ·
  Drafting by Gemini. Dashboard regenerates each SDR / Observer cycle. Hosted on Cloudflare, not search-indexed.
</footer>

</div>
</body>
</html>"""


def main() -> None:
    out = render()
    OUTPUT.write_text(out)
    print(f"Wrote {OUTPUT} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
