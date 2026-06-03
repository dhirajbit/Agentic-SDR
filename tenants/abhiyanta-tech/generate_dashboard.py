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
DRAFTS = TENANT_DIR / "email_drafts.json"
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


def _render_drafts_tab() -> str:
    """Email previews tab. Reads email_drafts.json and renders each draft as a
    review card. No buttons that mutate state — the dashboard is read-only."""
    pkg = _load_json(DRAFTS, {})
    drafts = pkg.get("drafts", [])
    sender = pkg.get("sender", {})
    if not drafts:
        return '<div class="panel"><h2>Email previews</h2><p>No drafts yet.</p></div>'

    ready = [d for d in drafts if d.get("status") == "draft_awaiting_review"]
    pending = [d for d in drafts if d.get("status") == "pending_enrichment"]
    seg_counts = {"IT": 0, "Finance": 0}
    for d in ready:
        seg = d.get("segment")
        if seg in seg_counts:
            seg_counts[seg] += 1

    rules_html = "".join(f"<li>{html.escape(r)}</li>" for r in pkg.get("rules", []))
    fw_a = html.escape(pkg.get("framework_library", {}).get("A", ""))
    fw_b = html.escape(pkg.get("framework_library", {}).get("B", ""))

    cards = []
    for d in drafts:
        is_pending = d.get("status") == "pending_enrichment"
        seg = d.get("segment") or "—"
        fw = d.get("framework") or "—"
        badge_class = "tag t1" if seg == "IT" else ("tag t2" if seg == "Finance" else "tag t3")
        status_class = "status-pill warn" if is_pending else "status-pill"
        status_label = "Pending enrichment" if is_pending else "Awaiting your review"
        first = html.escape(d.get("first_name") or "")
        contact = html.escape(d.get("contact_name") or "")
        company = html.escape(d.get("company") or "")
        location = html.escape(d.get("location") or "")
        title = html.escape(d.get("title") or "—")
        industry = html.escape(d.get("industry") or "—")
        email = html.escape(d.get("email") or "—")
        linkedin = d.get("linkedin") or ""
        op_note = d.get("operator_note")
        fit = d.get("fit_data", {})
        plevel = d.get("personalization_level", "templated")
        hook_src = d.get("hook_source")
        wrong_stack = d.get("wrong_stack_flagged", False)

        # Personalization badge
        if plevel == "verified_hook":
            plevel_html = '<span class="tag verified">Verified hook ✓</span>'
        elif plevel == "pending":
            plevel_html = '<span class="tag pending-tag">Pending</span>'
        else:
            plevel_html = '<span class="tag templated">Templated</span>'

        # Fit signal line
        fit_parts = []
        if fit.get("integration_suite_capable") == "yes":
            fit_parts.append(f'<span class="fit-good">SAP {fit.get("master_sap_products","")} confirmed</span>')
        elif fit.get("integration_suite_capable") == "maybe":
            fit_parts.append(f'<span class="fit-mid">SAP {fit.get("master_sap_products","")} (no S/4 yet)</span>')
        elif fit.get("master_file_match"):
            fit_parts.append('<span class="fit-mid">In master file, product unknown</span>')
        else:
            fit_parts.append('<span class="fit-warn">Not in master file</span>')
        if fit.get("apollo_employees"):
            emp = fit["apollo_employees"]
            rev = f' · {fit["apollo_revenue_printed"]} revenue' if fit.get("apollo_revenue_printed") else ""
            fit_parts.append(f'<span>{emp:,} employees{rev}</span>')
        fit_line = ' · '.join(fit_parts)

        # Apollo-match findings for pending leads
        pending_apollo = d.get("apollo_match_result")

        if is_pending:
            note_text = op_note or "Awaiting enrichment before drafting."
            pending_html = ''
            if pending_apollo:
                stale = pending_apollo.get('stale_lead')
                stale_class = ' stale' if stale else ''
                pending_html = (
                    f'<div class="apollo-match{stale_class}">'
                    f'<b>Apollo match:</b> {html.escape(pending_apollo.get("current_title",""))} '
                    f'at {html.escape(pending_apollo.get("current_org",""))} · '
                    f'email revealed: {"yes" if pending_apollo.get("email_revealed") else "no"}'
                    f'{" · <b>⚠ Lead is stale — person moved companies</b>" if stale else ""}'
                    f'</div>'
                )
            body_html = pending_html + (
                '<div class="draft-body pending">'
                + html.escape(note_text)
                + "</div>"
            )
            subj_html = '<div class="draft-subj pending">— subject pending —</div>'
        else:
            wc = len(d.get("body", "").split())
            subj_html = (
                f'<div class="draft-subj-row">'
                f'<span class="draft-meta-lbl">Subject</span>'
                f'<span class="draft-subj">{html.escape(d.get("subject",""))}</span>'
                f'<span class="draft-wc">{wc} words</span>'
                f'</div>'
            )
            body_html = (
                f'<pre class="draft-body">{html.escape(d.get("body",""))}</pre>'
            )
            if hook_src:
                body_html += f'<div class="hook-src"><b>Hook source:</b> {html.escape(hook_src)}</div>'
            if wrong_stack:
                body_html += '<div class="callout warn" style="margin-top:8px"><b>⚠ Wrong-stack flag:</b> Per web research, this company runs Google Cloud + in-house tech, not SAP. The Multi-Tenant Integration Suite pitch may not be the right opener. Draft acknowledges this — consider dropping or repositioning before send.</div>'
            if op_note:
                body_html += f'<div class="draft-opnote">Note: {html.escape(op_note)}</div>'

        li_html = (
            f'<a href="{html.escape(linkedin)}" target="_blank" rel="noopener">LinkedIn</a>'
            if linkedin else "—"
        )

        cards.append(f"""
<div class="draft-card" data-segment="{seg}" data-plevel="{plevel}">
  <div class="draft-head">
    <div>
      <div class="draft-name">{contact}</div>
      <div class="draft-sub">{title} · {company} · {location}</div>
    </div>
    <div class="draft-tags">
      <span class="{badge_class}">{seg}</span>
      <span class="tag fw">Framework {fw}</span>
      {plevel_html}
      <span class="{status_class}">{status_label}</span>
    </div>
  </div>
  <div class="draft-meta">
    <span><b>To:</b> {first} &lt;{email}&gt;</span>
    <span><b>Profile:</b> {li_html}</span>
  </div>
  <div class="draft-fit">{fit_line}</div>
  {subj_html}
  {body_html}
</div>""")

    filter_bar = f"""
<div class="filter-bar">
  <div class="filter-stats">
    <b>{len(ready)}</b> ready for review · <b>{pending and len(pending) or 0}</b> pending enrichment ·
    <span class="tag t1">IT {seg_counts['IT']}</span>
    <span class="tag t2">Finance {seg_counts['Finance']}</span>
  </div>
  <div class="filter-buttons">
    <button class="fbtn active" data-filter="all">All</button>
    <button class="fbtn" data-filter="IT">IT only</button>
    <button class="fbtn" data-filter="Finance">Finance only</button>
  </div>
</div>"""

    sender_block = ""
    if sender:
        sender_block = (
            f'<div class="callout"><b>Sender:</b> {html.escape(sender.get("name",""))} '
            f'&lt;{html.escape(sender.get("email",""))}&gt;. Single follow-up max (+5 business days) '
            f'if no reply. Multi-tenant advisory PDF is not attached on the first touch — offered on reply.</div>'
        )

    return f"""
<div class="panel">
  <h2>Email previews — Multi-Tenant SAP Integration Suite (v1 campaign)</h2>
  {sender_block}
  <div class="row2">
    <div><b>Framework A — Mouse Trap (IT audience).</b> <span style="color:var(--muted)">{fw_a}</span></div>
    <div><b>Framework B — Finance Angle (CFO audience).</b> <span style="color:var(--muted)">{fw_b}</span></div>
  </div>
  <h3>Rules in force for this batch</h3>
  <ul>{rules_html}</ul>
</div>
<div class="panel">
  {filter_bar}
  <div id="draft-list">{''.join(cards)}</div>
</div>
"""


def render() -> str:
    tracker = _load_json(TRACKER, {})
    queue = _load_json(QUEUE, [])
    blocked = _load_json(BLOCKED, [])
    urgent = _load_json(URGENT, [])
    mailbox = _mailbox_status()
    drafts_tab_html = _render_drafts_tab()

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
.tabnav {{ display:flex; gap:4px; margin: 0 0 20px 0; border-bottom: 1px solid var(--line); }}
.tabnav button {{ background: transparent; border:0; padding: 10px 18px; font: inherit; color: var(--muted); cursor: pointer; font-weight: 600; border-bottom: 2px solid transparent; margin-bottom: -1px; }}
.tabnav button.active {{ color: var(--brand); border-bottom-color: var(--brand); }}
.tabpane {{ display: none; }}
.tabpane.active {{ display: block; }}
.tag.fw {{ background: #eef2f8; color: var(--brand); }}
.filter-bar {{ display:flex; justify-content:space-between; align-items:center; gap:14px; margin-bottom: 18px; flex-wrap: wrap; }}
.filter-stats {{ font-size: 13px; color: var(--muted); display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
.filter-buttons {{ display:flex; gap:6px; }}
.fbtn {{ background: white; border:1px solid var(--line); padding: 6px 12px; border-radius: 6px; font: inherit; font-size: 12px; cursor: pointer; color: var(--muted); font-weight: 600; }}
.fbtn.active {{ background: var(--brand); color: white; border-color: var(--brand); }}
.draft-card {{ background: var(--panel); border:1px solid var(--line); border-radius:10px; padding: 16px 18px; margin-bottom: 14px; }}
.draft-card[data-hidden="1"] {{ display: none; }}
.draft-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; }}
.draft-name {{ font-weight: 700; font-size: 15px; color: var(--ink); }}
.draft-sub {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
.draft-tags {{ display:flex; gap: 6px; flex-wrap: wrap; }}
.draft-meta {{ font-size: 12px; color: var(--muted); display:flex; gap: 16px; flex-wrap: wrap; padding: 8px 0; border-top: 1px dashed var(--line); border-bottom: 1px dashed var(--line); margin-bottom: 10px; }}
.draft-meta a {{ color: var(--teal); }}
.draft-subj-row {{ display:flex; gap: 10px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }}
.draft-meta-lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 600; }}
.draft-subj {{ font-weight: 700; color: var(--brand); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
.draft-subj.pending {{ color: var(--muted); font-style: italic; font-weight: 500; }}
.draft-wc {{ font-size: 11px; color: var(--muted); margin-left: auto; }}
.draft-body {{ background: #fafbfd; border:1px solid var(--line); border-radius: 6px; padding: 12px 14px; font: 13px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: var(--ink); white-space: pre-wrap; margin: 0; overflow-x: auto; }}
.draft-body.pending {{ background: #fdf3e3; color: var(--warn); border-color: #f2d8a9; font-style: italic; }}
.draft-opnote {{ font-size: 12px; color: var(--muted); margin-top: 8px; font-style: italic; }}
.draft-fit {{ font-size: 12px; color: var(--muted); padding: 6px 0; margin-bottom: 10px; display:flex; gap: 12px; flex-wrap: wrap; }}
.fit-good {{ color: var(--good); font-weight: 600; }}
.fit-mid {{ color: var(--warn); font-weight: 600; }}
.fit-warn {{ color: var(--muted); }}
.tag.verified {{ background: #e6f3ec; color: var(--good); }}
.tag.templated {{ background: #eef2f8; color: var(--muted); }}
.tag.pending-tag {{ background: #fdf3e3; color: var(--warn); }}
.hook-src {{ font-size: 12px; color: var(--teal); background: #f0f7f7; padding: 8px 12px; border-radius: 6px; margin-top: 8px; border-left: 3px solid var(--teal); }}
.apollo-match {{ font-size: 12px; color: var(--ink); background: #eef2f8; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; }}
.apollo-match.stale {{ background: #fdf0ee; color: var(--bad); border-left: 3px solid var(--accent); }}
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

<nav class="tabnav">
  <button data-tab="tab-status" class="active">Status</button>
  <button data-tab="tab-previews">Email previews</button>
</nav>

<div id="tab-status" class="tabpane active">

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
  <h2>CRM pipeline — T1-India top 100 (v1 campaign)</h2>
  <p>Enrichment and Zoho CRM push completed on <b>2026-06-01</b>. All 120 records owned by <b>Saurabh B</b>.</p>
  <div class="grid" style="grid-template-columns: repeat(4, 1fr); margin: 0 0 18px 0;">
    {_stat('In Zoho CRM', '120', 'Owner: Saurabh B')}
    {_stat('Decision-maker emails', '120', 'Apollo-verified')}
    {_stat('Office phone populated', '117', '97% of T1 leads')}
    {_stat('Apollo credits used', '407', 'of 17,622 cycle balance')}
  </div>
  <table>
    <thead><tr><th>Step</th><th>Action</th><th>Credit cost</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>Confirm first slice — T1-India top 100 by ICP score, plus a firmographic size gate</td><td>0</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>2</td><td>Apollo organisation enrichment for 100 accounts → 87 firmographic hits</td><td>87</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>3</td><td>Firmographic gate (employees ≥ 100 OR revenue ≥ $10M) → 82 passed, 5 too small, 13 no data</td><td>0</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>4</td><td>Decision-maker search at the 82 qualified accounts → 188 candidates</td><td>0</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>5</td><td>Apollo email reveals via /people/match → <b>120 personal emails</b> across 58 accounts</td><td>320</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>6</td><td>Push to Zoho CRM as Leads → <b>119 created</b> (1 dropped: missing last name)</td><td>0</td><td><span class="tag verified">Done</span></td></tr>
      <tr><td>7</td><td>Update Owner = Saurabh B + Phone (office switchboard) across all leads</td><td>0</td><td><span class="tag verified">Done</span> · 117/119 phones populated</td></tr>
      <tr><td>8</td><td>Personalised outreach via connected Apollo mailbox; activity logged back to Zoho</td><td>Per send</td><td><span class="tag pending-tag">Holds — mailbox warmup pending</span></td></tr>
    </tbody>
  </table>
  <div class="row2" style="margin-top: 18px;">
    <div>
      <h3 style="margin-top: 0;">What's now in each Zoho Lead</h3>
      <ul style="margin: 6px 0; padding-left: 18px;">
        <li>Verified personal email (Apollo /people/match)</li>
        <li>Designation, Company, Industry, City/State/Country</li>
        <li>Employee count + revenue (Apollo firmographics)</li>
        <li>LinkedIn URL</li>
        <li>Office switchboard phone (where Apollo had it)</li>
        <li>SAP master-file fit: Priority Tier, ICP Score, SAP Products in use</li>
        <li>Source = "SAP Leads", Status = "Not Contacted", Owner = Saurabh B</li>
      </ul>
    </div>
    <div>
      <h3 style="margin-top: 0;">Notes</h3>
      <ul style="margin: 6px 0; padding-left: 18px;">
        <li>Personal mobile numbers are not in scope this cycle — Apollo direct-dial credits are 0 on this account. Office switchboards filled where available.</li>
        <li>2 records flagged in earlier analysis (Eka Mobility, Danish Power) skipped — Eka's contact moved companies; Danish Power's email not in Apollo.</li>
        <li>Sumit Duttagupta (Haldia CIO) needs phone added manually in Zoho — workflow timing blocked one update.</li>
        <li>3 leads are at competitor SAP-services firms (Wipro / HCLTech / Tata Group). Review before outreach.</li>
      </ul>
    </div>
  </div>
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

</div><!-- /tab-status -->

<div id="tab-previews" class="tabpane">
{drafts_tab_html}
</div><!-- /tab-previews -->

<footer>
  Abhiyanta Tech — Agentic SDR program. Enrichment via Apollo · CRM via Zoho ·
  Dashboard regenerates on every outreach and observer cycle. Hosted on Cloudflare, not search-indexed.
</footer>

<script>
(function() {{
  // Tab switching
  document.querySelectorAll('.tabnav button').forEach(function(b) {{
    b.addEventListener('click', function() {{
      var target = b.getAttribute('data-tab');
      document.querySelectorAll('.tabnav button').forEach(function(x) {{ x.classList.remove('active'); }});
      document.querySelectorAll('.tabpane').forEach(function(p) {{ p.classList.remove('active'); }});
      b.classList.add('active');
      var pane = document.getElementById(target);
      if (pane) pane.classList.add('active');
      // Update hash for deep-linking
      try {{ history.replaceState(null, '', '#' + target); }} catch (e) {{}}
    }});
  }});
  // Honor hash on load
  if (location.hash) {{
    var btn = document.querySelector('.tabnav button[data-tab="' + location.hash.slice(1) + '"]');
    if (btn) btn.click();
  }}
  // Filter
  document.querySelectorAll('.fbtn').forEach(function(b) {{
    b.addEventListener('click', function() {{
      var f = b.getAttribute('data-filter');
      document.querySelectorAll('.fbtn').forEach(function(x) {{ x.classList.remove('active'); }});
      b.classList.add('active');
      document.querySelectorAll('.draft-card').forEach(function(card) {{
        var seg = card.getAttribute('data-segment') || '';
        if (f === 'all' || seg === f) {{ card.removeAttribute('data-hidden'); }}
        else {{ card.setAttribute('data-hidden', '1'); }}
      }});
    }});
  }});
}})();
</script>

</div>
</body>
</html>"""


def main() -> None:
    html_out = render()
    OUTPUT.write_text(html_out)
    print(f"Wrote {OUTPUT} ({len(html_out):,} bytes)")


if __name__ == "__main__":
    main()
