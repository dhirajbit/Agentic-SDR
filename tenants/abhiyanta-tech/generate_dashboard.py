"""Generate the Abhiyanta Tech SDR dashboard as a single self-contained HTML.

Pulls live state from tenant JSON files. Embeds the logo so the artifact is
deployable as a single index.html with no external dependencies. Run on every
SDR / Observer cycle:

    AGENTIC_SDR_TENANT=abhiyanta-tech python tenants/abhiyanta-tech/generate_dashboard.py

Output: tenants/abhiyanta-tech/sdr_dashboard.html
"""

from __future__ import annotations

import base64
import html
import json
import time
from datetime import datetime
from pathlib import Path

TENANT_DIR = Path(__file__).resolve().parent
LOGO_PATH = TENANT_DIR / "abhiyanta_india_solutions_pvt_ltd__logo.jpeg"
TRACKER = TENANT_DIR / "outreach_tracker.json"
QUEUE = TENANT_DIR / "qualified_leads.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
URGENT = TENANT_DIR / "urgent_followups.json"
OUTPUT = TENANT_DIR / "sdr_dashboard.html"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _embed_logo() -> str:
    if not LOGO_PATH.exists():
        return ""
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _kv(label: str, value: str, mono: bool = False) -> str:
    klass = "kv-val mono" if mono else "kv-val"
    return f'<div class="kv-row"><div class="kv-lbl">{html.escape(label)}</div><div class="{klass}">{value}</div></div>'


def _stat(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="stat-sub">{html.escape(sub)}</div>' if sub else ""
    return (
        f'<div class="stat"><div class="stat-num">{value}</div>'
        f'<div class="stat-lbl">{html.escape(label)}</div>{sub_html}</div>'
    )


def _mailbox_status() -> dict:
    """Read cached mailbox status from outreach_tracker.json.
    The Observer loop refreshes it via apollo_client.list_email_accounts() (no
    credit cost). Defaults below are conservative — assume worst case if unset."""
    tracker = _load_json(TRACKER, {})
    return tracker.get("mailbox_status") or {
        "email": "saurabh.barathe@abhiyantatech.info",
        "provider": "Microsoft 365",
        "connected_on": "2026-05-27",
        "warmup_status": "not yet started",
        "warmup_score": 0,
        "daily_send_capacity": 50,
        "daily_send_used_today": 0,
        "send_start_eta": "~2 weeks after warmup begins",
    }


def render() -> str:
    tracker = _load_json(TRACKER, {})
    queue = _load_json(QUEUE, [])
    blocked = _load_json(BLOCKED, [])
    urgent = _load_json(URGENT, [])
    mailbox = _mailbox_status()

    agg = tracker.get("aggregate_stats", {})
    snaps = tracker.get("credit_snapshots", [])
    latest = snaps[-1] if snaps else {}

    sends = agg.get("sends", 0)
    delivered = agg.get("delivered", 0)
    opens = agg.get("opens", 0)
    replies = agg.get("replies", 0)
    open_rate = f"{opens * 100 / delivered:.1f}%" if delivered else "—"
    reply_rate = f"{replies * 100 / delivered:.1f}%" if delivered else "—"

    lead_left = latest.get("lead_credit_left", "—")
    dial_left = latest.get("direct_dial_credit_left", "—")
    export_left = latest.get("export_credit_left", "—")
    snap_at = latest.get("at", "—")

    logo_data = _embed_logo()
    logo_tag = f'<img src="{logo_data}" alt="Abhiyanta" class="logo" />' if logo_data else ""

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_label = "Pre-enrichment — no outreach started"
    if sends > 0:
        status_label = f"Live — {sends} sends logged"

    # Credit history mini-table
    snap_rows = ""
    for s in snaps[-8:]:
        snap_rows += (
            f"<tr><td class='mono'>{html.escape(str(s.get('at','')))}</td>"
            f"<td>{html.escape(str(s.get('label','')))}</td>"
            f"<td class='num'>{s.get('lead_credit_left','—')}</td>"
            f"<td class='num'>{s.get('direct_dial_credit_left','—')}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Abhiyanta Tech — Agentic SDR</title>
<style>
:root {{
  --bg: #f6f8fb;
  --panel: #ffffff;
  --ink: #0f1b2d;
  --muted: #5b6b80;
  --line: #e2e8f0;
  --brand: #1f3a5f;
  --teal: #2c8a8a;
  --accent: #c33a2e;
  --good: #1f7a4a;
  --warn: #b86a00;
  --bad: #b3261e;
}}
* {{ box-sizing: border-box; }}
html,body {{ margin:0; padding:0; background: var(--bg); color: var(--ink); font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 80px; }}
header {{ display:flex; align-items:center; gap:18px; padding-bottom:18px; border-bottom: 1px solid var(--line); margin-bottom: 22px; }}
.logo {{ width: 56px; height: 56px; border-radius: 8px; object-fit: contain; background: white; padding: 4px; box-shadow: 0 1px 2px rgba(15,27,45,0.06); }}
.hdr-title {{ font-size: 20px; font-weight: 700; color: var(--brand); letter-spacing: -0.01em; }}
.hdr-sub {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
.hdr-right {{ margin-left:auto; text-align:right; font-size:12px; color: var(--muted); }}
.status-pill {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; background: #eaf4ee; color: var(--good); border: 1px solid #c6e3d3; }}
.status-pill.warn {{ background: #fdf3e3; color: var(--warn); border-color: #f2d8a9; }}
.grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 0 0 26px 0; }}
.stat {{ background: var(--panel); border:1px solid var(--line); border-radius:10px; padding: 14px 16px; }}
.stat-num {{ font-size: 26px; font-weight: 700; color: var(--ink); letter-spacing: -0.02em; }}
.stat-lbl {{ font-size: 12px; color: var(--muted); margin-top: 2px; text-transform: uppercase; letter-spacing: 0.04em; }}
.stat-sub {{ font-size: 12px; color: var(--teal); margin-top: 4px; font-weight: 600; }}
.panel {{ background: var(--panel); border:1px solid var(--line); border-radius:10px; padding: 18px 20px; margin-bottom: 18px; }}
.panel h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--brand); margin: 0 0 12px 0; }}
.panel h3 {{ font-size: 14px; margin: 18px 0 6px 0; color: var(--ink); }}
.panel p {{ margin: 0 0 10px 0; }}
.panel ul {{ margin: 6px 0 14px 18px; padding: 0; }}
.panel li {{ margin: 3px 0; }}
.row2 {{ display:grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.kv-row {{ display:flex; justify-content:space-between; padding: 5px 0; border-bottom: 1px dashed var(--line); font-size: 14px; }}
.kv-row:last-child {{ border-bottom: 0; }}
.kv-lbl {{ color: var(--muted); }}
.kv-val {{ font-weight: 600; }}
.mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
table {{ width:100%; border-collapse: collapse; font-size: 13px; }}
th,td {{ text-align:left; padding: 7px 10px; border-bottom: 1px solid var(--line); }}
th {{ font-weight: 600; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
td.num {{ text-align:right; font-variant-numeric: tabular-nums; }}
.tag {{ display:inline-block; font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 600; }}
.tag.t1 {{ background: #e6f3ec; color: var(--good); }}
.tag.t2 {{ background: #fdf3e3; color: var(--warn); }}
.tag.t3 {{ background: #f0f0f0; color: var(--muted); }}
.tag.t4 {{ background: #fbe6e3; color: var(--bad); }}
.callout {{ border-left: 3px solid var(--teal); background: #f0f7f7; padding: 10px 14px; border-radius: 0 8px 8px 0; margin: 10px 0; }}
.callout.warn {{ border-left-color: var(--accent); background: #fdf0ee; }}
footer {{ margin-top: 30px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); line-height: 1.6; }}
@media (max-width: 760px) {{ .grid {{ grid-template-columns: repeat(2,1fr); }} .row2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="wrap">

<header>
  {logo_tag}
  <div>
    <div class="hdr-title">Abhiyanta Tech — Agentic SDR</div>
    <div class="hdr-sub">Outbound SDR program · Enrichment + send via Apollo · CRM via Zoho</div>
  </div>
  <div class="hdr-right">
    <span class="status-pill {'warn' if sends == 0 else ''}">{html.escape(status_label)}</span>
    <div style="margin-top:6px">Generated {html.escape(generated_at)} local</div>
  </div>
</header>

<div class="grid">
  {_stat('Sends', str(sends), f'{delivered} delivered')}
  {_stat('Open rate', open_rate, f'{opens} opens')}
  {_stat('Reply rate', reply_rate, f'{replies} replies / {len(urgent)} pending')}
  {_stat('Apollo lead credits left', str(lead_left), f'snapshot {snap_at[:16]}')}
</div>

<div class="panel">
  <h2>Apollo credit posture</h2>
  <div class="row2">
    <div>
      {_kv('Enrichment credits remaining', str(lead_left), mono=True)}
      {_kv('Direct-dial (phone) credits', str(dial_left) + ' — phone channel off this cycle', mono=True)}
      {_kv('Bulk export credits', str(export_left) + ' — bulk export not in use', mono=True)}
      {_kv('Credit cycle ends', (latest.get('cycle_end','—') or '—')[:10], mono=True)}
    </div>
    <div>
      <table>
        <thead><tr><th>When</th><th>Event</th><th class='num'>lead_left</th><th class='num'>dial_left</th></tr></thead>
        <tbody>{snap_rows or '<tr><td colspan="4" style="color:var(--muted)">No snapshots yet.</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="panel">
  <h2>Phase 0 — master file analysis (2026-05-29)</h2>
  <p>Source: <span class="mono">Zoho_CRM_Import_Master_v1.xlsx</span>. 8 sheets, 195,445 unique Global Ultimate accounts, already scored (ICP Fit Score 0–100) and tiered. ETS-sanctioned 1,322 rows pre-extracted to sheet 03.</p>

  <h3>Account distribution</h3>
  <table>
    <thead><tr><th>Tier</th><th>Definition</th><th class='num'># Accounts</th><th>Our stance</th></tr></thead>
    <tbody>
      <tr><td><span class="tag t1">T1</span></td><td>Mfg verticals × India + GCC + SEA</td><td class='num'>4,694</td><td>Starting point — Apollo replaces Lusha</td></tr>
      <tr><td><span class="tag t2">T2-Warm-Cloud</span></td><td>SAP cloud trialists (Has Tenant, no Contract)</td><td class='num'>24,752</td><td>Deferred — heavy data-quality risk</td></tr>
      <tr><td><span class="tag t2">T2-Mature-Mfg</span></td><td>12 verticals × US/UK/DE/CA etc.</td><td class='num'>31,748</td><td>Deferred until T1 traction</td></tr>
      <tr><td><span class="tag t3">T3</span></td><td>Long tail</td><td class='num'>97,014</td><td>Hold</td></tr>
      <tr><td><span class="tag t4">T4</span></td><td>Partners / Resellers / SAP Internal</td><td class='num'>37,236</td><td>DoNotMarket — never touch</td></tr>
    </tbody>
  </table>

  <h3>T1 readiness</h3>
  <div class="row2">
    <div>
      {_kv('T1 total', '4,694')}
      {_kv('T1 — India', '2,549 (54%)')}
      {_kv('T1 — SEA', '1,069 (23%)')}
      {_kv('T1 — GCC', '767 (16%)')}
      {_kv('T1 with website (Apollo can match)', '4,049 (86.3%)')}
    </div>
    <div>
      {_kv('T1 with email pre-filled', '789 (16.8%)')}
      {_kv('T1 India with email', '402 / 2,549 (15.8%)')}
      {_kv('T1 Compliance Status = Flagged-Review', '9 (skip until manual sign-off)')}
      {_kv('Enrichment Plan = Lusha-Tier1-Now', '3,569 — to remap → Apollo')}
      {_kv('Enrichment Plan = Apollo-* already', '458')}
    </div>
  </div>

  <h3>Credit budget against the 17,622 live balance</h3>
  <table>
    <thead><tr><th>Slice</th><th class='num'>Accounts</th><th>Contacts/acct</th><th class='num'>Worst-case credits</th><th>Fits?</th></tr></thead>
    <tbody>
      <tr><td>T1-India top 100 by ICP (recommended first slice)</td><td class='num'>100</td><td>3</td><td class='num'>300</td><td>✓ huge headroom</td></tr>
      <tr><td>T1-India all</td><td class='num'>2,549</td><td>3</td><td class='num'>7,647</td><td>✓</td></tr>
      <tr><td>Full T1 (India + GCC + SEA)</td><td class='num'>4,694</td><td>3</td><td class='num'>14,082</td><td>✓ — tight, leaves ~3K for T2 sampling</td></tr>
    </tbody>
  </table>

  <h3>Three risks flagged</h3>
  <div class="callout warn"><b>ICP score is vertical + geo only.</b> "Lal Ji Steel Welding Works" scores 95 same as ArcelorMittal because both are Mill Products × India. Some T1-India top-100 will be tiny shops below SAP price point. Recommended: layer an Apollo firmographic gate (employees ≥ 100 OR revenue ≥ $10M) post-enrichment before paying credits to reveal contact emails.</div>
  <div class="callout warn"><b>T2-Warm-Cloud India is full of garbage.</b> Top hits include "rwtyu", "Test", "Saffronart Mumbai", and literally <span class="mono">david.metser@sap.com</span> as an account name. Bulk-enriching all 24,752 will burn credits on junk. Skip T2-Warm-Cloud until a name-quality filter exists.</div>
  <div class="callout warn"><b>Email-only this cycle.</b> Original plan presumed Lusha for India mobile coverage. Without Lusha and with no phone-reveal credits on the Apollo account, this cycle is email-only. Phone channel can be reopened with a separate Lusha contract.</div>
</div>

<div class="panel">
  <h2>Sender mailbox</h2>
  <div class="row2">
    <div>
      {_kv('Mailbox', html.escape(mailbox['email']))}
      {_kv('Provider', html.escape(mailbox['provider']))}
      {_kv('Connected on', html.escape(mailbox['connected_on']))}
      {_kv('Daily send capacity', f"{mailbox['daily_send_used_today']} / {mailbox['daily_send_capacity']}")}
    </div>
    <div>
      {_kv('Warmup status', html.escape(str(mailbox['warmup_status'])))}
      {_kv('Warmup score', str(mailbox['warmup_score']) + ' / 100')}
      {_kv('Projected first send', html.escape(mailbox['send_start_eta']))}
    </div>
  </div>
  <div class="callout">
    <b>Why we're not sending yet.</b> The sender mailbox was connected to Apollo on
    {html.escape(mailbox['connected_on'])} and is a brand-new domain ({html.escape(mailbox['email'].split('@')[1])}).
    Sending cold outreach from an unwarmed mailbox on a new domain will land in spam and damage the domain's
    reputation for months. Apollo's built-in mailwarming service will simulate normal mailbox traffic for
    ~14–21 days to build a sending reputation. We will not send a single outreach email until warmup
    completes the open / reply / bounce thresholds.
  </div>
</div>

<div class="panel">
  <h2>Rollout plan — awaiting your go-ahead</h2>
  <table>
    <thead><tr><th>Step</th><th>Action</th><th>Credit cost</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>Confirm first slice — T1-India top 100 by ICP score, plus a firmographic size gate</td><td>0</td><td>Awaiting approval</td></tr>
      <tr><td>2</td><td>Stand up Zoho CRM fields per Sheet 04 — Field Mapping</td><td>0</td><td>Awaiting approval</td></tr>
      <tr><td>3</td><td>Import the 1,322 ETS-excluded accounts into Zoho as a suppression list (no outreach, ever)</td><td>0</td><td>Awaiting approval</td></tr>
      <tr><td>4</td><td>Import the first slice (100 accounts) into Zoho as Leads — still no enrichment</td><td>0</td><td>Awaiting approval</td></tr>
      <tr><td>5</td><td><b>Apollo enrichment</b> — organisation firmographics + size filter + decision-maker email reveals</td><td><b>≤ 300 enrichment credits, worst case</b></td><td><b>Requires explicit approval at runtime</b></td></tr>
      <tr><td>6</td><td>Personalised outreach via the connected Apollo mailbox; activity logged back to Zoho</td><td>Per send</td><td>Holds until mailbox warmup completes</td></tr>
    </tbody>
  </table>
</div>

<div class="panel">
  <h2>Live queue snapshot</h2>
  <div class="row2">
    <div>
      {_kv('Qualified queue depth', str(len(queue)))}
      {_kv('Blocked / opted-out', str(len(blocked)))}
      {_kv('Urgent followups pending', str(len(urgent)))}
    </div>
    <div>
      {_kv('Actions logged', str(len(tracker.get('actions', []))))}
      {_kv('Aggregate sends', str(sends))}
      {_kv('Aggregate replies', str(replies))}
    </div>
  </div>
</div>

<footer>
  Abhiyanta Tech — Agentic SDR program. Enrichment via Apollo · CRM via Zoho ·
  Dashboard regenerates on every outreach and observer cycle. Hosted on Cloudflare, not search-indexed.
</footer>

</div>
</body>
</html>"""


def main() -> None:
    html_out = render()
    OUTPUT.write_text(html_out)
    print(f"Wrote {OUTPUT} ({len(html_out):,} bytes)")


if __name__ == "__main__":
    main()
