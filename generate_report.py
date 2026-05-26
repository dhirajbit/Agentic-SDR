"""Generate SDR Dashboard Report as HTML and deploy to Netlify. Run after every SDR/Observer cycle."""

import json
import hashlib
import html as html_mod
import os
import urllib.request
from collections import defaultdict
from datetime import datetime


def generate_report():
    with open('outreach_tracker.json') as f:
        tracker = json.load(f)
    with open('strategy_playbook.md') as f:
        playbook = f.read()
    with open('blocked_leads.json') as f:
        blocked = json.load(f)

    leads = tracker["leads"]
    meta = tracker["meta"]
    stats = tracker.get("aggregate_stats", {})

    # --- Load all CRM leads for overview funnel ---
    import re as _re
    try:
        with open('leads_data.json') as f:
            all_crm_leads = json.load(f)
    except Exception:
        all_crm_leads = []

    crm_total = len(all_crm_leads)
    crm_with_email = sum(1 for l in all_crm_leads if l.get('email_id'))
    crm_with_phone = sum(1 for l in all_crm_leads if l.get('mobile_no'))
    crm_with_both = sum(1 for l in all_crm_leads if l.get('email_id') and l.get('mobile_no'))

    # B2C/D2C/Large B2B qualification
    _B2C_KW = {'retail','fmcg','pharma','bank','banking','insurance','telecom',
               'hospitality','hotel','hotels','healthcare','medical','hospital',
               'education','edtech','automotive','ecommerce','e-commerce',
               'real estate','realty','media','entertainment','food','qsr',
               'fintech','nbfc','conglomerate','consumer','appliances',
               'jewelry','jewellery','luxury','fashion','cosmetics','beauty',
               'dairy','beverages','paint','beverage','airline','airlines','aviation',
               'cement','energy','oil','gas','utilities','logistics',
               'shipping','mutual fund','broking','lending',
               'broadband','cable','jio','airtel','vodafone','idea',
               'metro','rail','bharat','state bank','kotak','axis','icici',
               'bajaj','hdfc','sbi','lic','tata','mahindra','reliance',
               'pizza','zomato','swiggy','flipkart','meesho',
               'motors','taj','ihcl','oberoi','apollo','fortis',
               'paytm','phonepe','razorpay',
               'tcs','infosys','wipro','cognizant','capgemini','accenture','hcl',
               'steel','iron','metal','mining','power','refiner',
               'chemical','petro','polymer','textile','fiber','fibre',
               'construction','infrastructure','engineering',
               'water','treatment','purif',
               'diamond','gold','precious',
               'travel','tour','cargo','freight','port','dock','shipyard',
               'defence','defense','naval','aero','space',
               'sugar','agro','agri','fertiliz','seed','crop',
               'paper','packaging','print','publish',
               'rubber','plastic','pipe','tube','wire','cable',
               'electronic','semiconductor','chip','sensor',
               'software','digital','cloud','data','cyber','tech',
               'bio','life science','diagnostic','lab',
               'legal','law firm','advocate',
               'bpo','outsourc','staffing','recruit',
               'warehouse','supply chain','distribution'}
    _LARGE_B2B = {'tata','adani','reliance','birla','mahindra','l&t','larsen',
                  'godrej','hul','hindustan unilever','itc','bajaj','jsw','vedanta',
                  'wipro','tcs','infosys','hcl','tech mahindra','jindal','aditya birla',
                  'essar','shapoorji','piramal','wockhardt','lupin','cipla','sun pharma',
                  'dr reddy','glenmark','torrent','emami','dabur','marico','colgate',
                  'nestle','siemens','bosch','schneider','abb','honeywell',
                  'samsung','sony','panasonic','hitachi','mitsubishi',
                  'fis','diebold','mastercard','visa',
                  'deloitte','kpmg','ey ','pwc','mckinsey'}
    _SENIOR_TITLES = {'cio','cto','cfo','ceo','coo','ciso','cdo','cmo','chro',
                      'president','managing director','vice president','vp ',
                      'svp','evp','avp','dvp',
                      'head of','head it','head information','head digital',
                      'head hr','head finance','head procurement','head supply',
                      'head marketing','head sales','head operations',
                      'general manager','director','chief'}

    def _is_qualified(lead):
        company = (lead.get('company_name') or '').lower()
        title = (lead.get('job_title') or '').lower()
        for brand in _LARGE_B2B:
            if brand in company:
                return True
        for kw in _B2C_KW:
            if kw in company:
                return True
        if (lead.get('annual_revenue') or 0) >= 10000:
            return True
        for t in _SENIOR_TITLES:
            if t in title:
                return True
        return False

    crm_qualified = sum(1 for l in all_crm_leads if l.get('email_id') and _is_qualified(l))

    # Touched by agent
    tracked_ids = set(leads.keys())
    agent_emailed = sum(1 for lid in tracked_ids if any(a.get('type') == 'email' for a in leads[lid].get('actions', [])))
    agent_wa = sum(1 for lid in tracked_ids if any(a.get('type') == 'whatsapp' for a in leads[lid].get('actions', [])))
    agent_both = sum(1 for lid in tracked_ids if
                     any(a.get('type') == 'email' for a in leads[lid].get('actions', [])) and
                     any(a.get('type') == 'whatsapp' for a in leads[lid].get('actions', [])))

    # --- Counts ---
    total_leads = len(leads)
    total_emails = sum(1 for l in leads.values() for a in l["actions"] if a["type"] == "email")
    total_wa = sum(1 for l in leads.values() for a in l["actions"] if a["type"] == "whatsapp" and a.get("status") == "sent")
    total_opens = meta.get("total_opens", 0)
    bounces = meta.get("total_bounces", 0)
    delivered = total_emails - bounces
    open_rate = f"{total_opens/delivered*100:.0f}%" if delivered else "0%"
    bounce_rate = f"{bounces/total_emails*100:.0f}%" if total_emails else "0%"
    total_actions = sum(len(l["actions"]) for l in leads.values())

    # --- Build flat activity list ---
    activities = []
    for lid, ld in leads.items():
        for a in ld.get("actions", []):
            # Normalize schema differences (new-schema uses sent_at/to_email/action_id)
            ts = a.get("timestamp") or a.get("sent_at") or ""
            rid = a.get("id") or a.get("action_id") or ""
            recipient = a.get("recipient") or a.get("to_email") or ""
            activities.append({
                "lead_id": lid,
                "lead_name": ld.get("lead_name", ""),
                "company": ld.get("company_name", ""),
                "role": ld.get("job_role_category", ""),
                "industry": ld.get("industry_tag", ""),
                **a,
                "timestamp": ts,
                "id": rid,
                "recipient": recipient,
            })
    activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    # --- Compute effective status from events for filter values (matches activity-row rendering) ---
    def _effective_status(a):
        ev = a.get("events") or {}
        if ev.get("replied"): return "replied"
        if ev.get("bounced"): return "bounced"
        if ev.get("clicked"): return "clicked"
        if ev.get("opened"): return "opened"
        if ev.get("delivered"): return "delivered"
        return a.get("status", "")

    # --- Collect unique filter values ---
    all_statuses = sorted(set(_effective_status(a) for a in activities if _effective_status(a)))
    all_types = sorted(set(a.get("type", "") for a in activities if a.get("type")))
    all_frameworks = sorted(set(a.get("framework", "") for a in activities if a.get("framework")))
    all_industries = sorted(set(a.get("industry", "") for a in activities if a.get("industry")))
    all_roles = sorted(set(a.get("role", "") for a in activities if a.get("role")))
    all_dates = sorted(set(a["timestamp"][:10] for a in activities), reverse=True)

    def label(s):
        return html_mod.escape(s.replace("_", " ").title()) if s else ""

    def esc(s):
        return html_mod.escape(str(s)) if s else ""

    # --- Build filter option HTML ---
    def options_html(values, use_label=True):
        return "".join(f'<option value="{esc(v)}">{label(v) if use_label else esc(v)}</option>' for v in values)

    status_options = options_html(all_statuses)
    type_options = options_html(all_types)
    framework_options = options_html(all_frameworks)
    industry_options = options_html(all_industries)
    role_options = options_html(all_roles)
    date_options = "".join(f'<option value="{d}">{datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")}</option>' for d in all_dates)

    def status_badge(status):
        colors = {
            "replied": "#16a34a", "opened": "#22c55e", "clicked": "#3b82f6",
            "bounced": "#ef4444", "delivered": "#6b7280", "sent": "#8b5cf6",
            "skipped": "#9ca3af", "failed": "#ef4444"
        }
        bg = colors.get(status, "#d4d4d4")
        return f'<span class="badge" style="background:{bg}">{esc(status).upper()}</span>'

    def crm_link(lid):
        return f'YOUR_CRM_URL/app/lead/{lid}'

    def type_icon(t):
        if t == "email":
            return '<span class="type-icon email-icon" title="Email">&#9993;</span>'
        elif t == "whatsapp":
            return '<span class="type-icon wa-icon" title="WhatsApp">&#128172;</span>'
        return ''

    # --- Build all activity rows as a flat list with data attributes ---
    activity_rows = ""
    for idx, a in enumerate(activities):
        lid = a["lead_id"]
        date_str = a["timestamp"][:10]
        time_str = a["timestamp"][11:16] if len(a["timestamp"]) > 11 else ""
        a_type = a.get("type", "")
        # Derive display-status from events (replied/bounced/opened) so observer updates
        # (which only touch events.*) reflect in the Activity Log without needing a
        # second write-pass to the action's `status` field.
        _ev = a.get("events") or {}
        if _ev.get("replied"):
            a_status = "replied"
        elif _ev.get("bounced"):
            a_status = "bounced"
        elif _ev.get("clicked"):
            a_status = "clicked"
        elif _ev.get("opened"):
            a_status = "opened"
        elif _ev.get("delivered"):
            a_status = "delivered"
        else:
            a_status = a.get("status", "")
        a_framework = a.get("framework", "")
        a_industry = a.get("industry", "")
        a_role = a.get("role", "")

        if a_type == "email":
            body = esc(a.get("body", ""))
            subject = esc(a.get("subject", ""))
            recipient = esc(a.get("recipient", ""))
            framework_label = label(a_framework)
            content_html = f'<div class="msg-subject">Sub: {subject}</div>'
            if body:
                content_html += f'<div class="msg-body collapsed" onclick="this.classList.toggle(\'collapsed\')">{body}</div>'
            else:
                content_html += '<div class="msg-body no-body">Email body not recorded</div>'
            content_html += f'<div class="msg-meta">To: {recipient} &middot; Framework: {framework_label} &middot; Words: {a.get("word_count", "?")}</div>'
        elif a_type == "whatsapp":
            message = esc(a.get("message", a.get("message_preview", "")))
            recipient = esc(a.get("recipient", ""))
            content_html = f'<div class="msg-body wa-body collapsed" onclick="this.classList.toggle(\'collapsed\')">{message}</div>'
            content_html += f'<div class="msg-meta">To: {recipient}</div>'
        else:
            content_html = f'<div class="msg-body">{esc(str(a))}</div>'

        events = a.get("events", {})
        event_tags = ""
        for evt_name in ["sent", "delivered", "opened", "clicked", "replied", "bounced", "read", "error"]:
            evt_val = events.get(evt_name)
            if evt_val:
                evt_time = str(evt_val)[:16].replace("T", " ")
                evt_cls = f"evt-{evt_name}"
                event_tags += f'<span class="evt {evt_cls}">{evt_name} {evt_time}</span> '

        # Searchable text for the search filter
        search_text = f"{a['lead_name']} {a['company']} {a.get('subject','')} {a.get('recipient','')}".lower()

        activity_rows += f'''<tr class="activity-row" data-date="{date_str}" data-type="{a_type}" data-status="{a_status}" data-framework="{a_framework}" data-industry="{a_industry}" data-role="{a_role}" data-search="{esc(search_text)}">
            <td class="col-date">{date_str}<br><span class="time-sub">{time_str}</span></td>
            <td class="col-type">{type_icon(a_type)}</td>
            <td class="col-lead">
                <a href="{crm_link(lid)}" target="_blank" class="lead-link">{esc(a["lead_name"])}</a>
                <div class="lead-company">{esc(a["company"][:40])}</div>
                <div class="lead-meta">{label(a_role)} &middot; {label(a_industry)}</div>
            </td>
            <td class="col-content">{content_html}</td>
            <td class="col-status">{status_badge(a_status)}</td>
            <td class="col-events">{event_tags}</td>
            <td class="col-crm"><a href="{crm_link(lid)}" target="_blank" class="crm-btn">CRM</a></td>
        </tr>'''

    # Helper: handle both schemas (sends/opens/bounces vs sent/opened/bounced)
    def _g(s, *keys):
        for k in keys:
            if k in s:
                return s[k]
        return 0

    # --- Framework stats ---
    fw_stats = stats.get("by_framework", {})
    fw_rows = ""
    for fw, s in sorted(fw_stats.items(), key=lambda x: x[1].get("open_rate", 0), reverse=True):
        sends = _g(s, "sends", "sent")
        opens = _g(s, "opens", "opened")
        bnc = _g(s, "bounces", "bounced")
        nb = sends - bnc
        or_pct = f"{s.get('open_rate', 0)*100:.0f}%" if nb else "—"
        fw_rows += f'<tr><td>{esc(fw.replace("_"," ").title())}</td><td>{sends}</td><td>{total_opens}</td><td>{bnc}</td><td><b>{or_pct}</b></td></tr>'

    # --- Role stats ---
    role_stats = stats.get("by_role_category", stats.get("by_role", {}))
    role_rows = ""
    for role, s in sorted(role_stats.items(), key=lambda x: x[1].get("open_rate", 0), reverse=True):
        sends = _g(s, "sends", "sent")
        opens = _g(s, "opens", "opened")
        bnc = _g(s, "bounces", "bounced")
        nb = sends - bnc
        or_pct = f"{s.get('open_rate', 0)*100:.0f}%" if nb else "—"
        role_rows += f'<tr><td>{esc(role.replace("_"," ").title())}</td><td>{sends}</td><td>{total_opens}</td><td>{bnc}</td><td><b>{or_pct}</b></td></tr>'

    # --- Industry stats ---
    ind_stats = stats.get("by_industry", stats.get("by_industry_tag", {}))
    ind_rows = ""
    for ind, s in sorted(ind_stats.items(), key=lambda x: x[1].get("open_rate", 0), reverse=True):
        sends = _g(s, "sends", "sent")
        opens = _g(s, "opens", "opened")
        bnc = _g(s, "bounces", "bounced")
        if sends >= 2:
            nb = sends - bnc
            or_pct = f"{s.get('open_rate', 0)*100:.0f}%" if nb else "—"
            ind_rows += f'<tr><td>{esc(ind.replace("_"," ").title())}</td><td>{sends}</td><td>{total_opens}</td><td>{bnc}</td><td><b>{or_pct}</b></td></tr>'

    # --- Accounts (grouped by email domain, deduped) ---
    def _domain(email):
        if not email or "@" not in email:
            return None
        d = email.split("@", 1)[1].strip().lower()
        if d.startswith("ext."):
            d = d[4:]
        if d.startswith("www."):
            d = d[4:]
        return d or None

    accounts = {}
    for lid, ld in leads.items():
        actions = ld.get("actions", [])
        if not actions:
            continue
        dom = _domain(ld.get("email_id") or "")
        if not dom:
            for a in actions:
                dom = _domain(a.get("recipient") or "")
                if dom:
                    break
        if not dom:
            continue
        acc = accounts.setdefault(dom, {
            "domain": dom,
            "companies": {},
            "contacts": {},
            "emails_sent": 0, "emails_delivered": 0, "emails_opened": 0,
            "emails_bounced": 0, "emails_replied": 0,
            "wa_sent": 0, "wa_replied": 0,
            "last_touch": "",
            "meeting_booked": False,
        })
        co = (ld.get("company_name") or "").strip()
        if co:
            acc["companies"][co] = acc["companies"].get(co, 0) + 1
        if ld.get("meeting_booked"):
            acc["meeting_booked"] = True
        contact = acc["contacts"].setdefault(lid, {
            "lead_name": ld.get("lead_name", ""),
            "job_title": ld.get("job_title") or "",
            "emails": 0, "opens": 0, "bounces": 0, "replies": 0,
            "wa": 0, "wa_replies": 0,
        })
        for a in actions:
            events = a.get("events") or {}
            ts = a.get("timestamp") or ""
            if ts > acc["last_touch"]:
                acc["last_touch"] = ts
            if a.get("type") == "email":
                acc["emails_sent"] += 1
                contact["emails"] += 1
                if events.get("delivered"):
                    acc["emails_delivered"] += 1
                if events.get("opened"):
                    acc["emails_opened"] += 1
                    contact["opens"] += 1
                if events.get("bounced"):
                    acc["emails_bounced"] += 1
                    contact["bounces"] += 1
                if events.get("replied"):
                    acc["emails_replied"] += 1
                    contact["replies"] += 1
            elif a.get("type") == "whatsapp":
                acc["wa_sent"] += 1
                contact["wa"] += 1
                if events.get("replied"):
                    acc["wa_replied"] += 1
                    contact["wa_replies"] += 1

    account_list = []
    for dom, acc in accounts.items():
        primary_co = max(acc["companies"].items(), key=lambda x: x[1])[0] if acc["companies"] else dom
        acc["primary_company"] = primary_co
        acc["contact_count"] = len(acc["contacts"])
        account_list.append(acc)
    account_list.sort(key=lambda a: (-a["emails_opened"], -a["emails_sent"]))

    # Build contact messages lookup for modal (only for contacts in accounts view)
    contact_messages = {}
    for acc in account_list:
        for lid in acc["contacts"]:
            ld = leads.get(lid, {})
            msgs = []
            for a in sorted(ld.get("actions", []), key=lambda x: x.get("timestamp", "")):
                if a.get("type") not in ("email", "whatsapp"):
                    continue
                events = a.get("events") or {}
                event_list = []
                for evt_name in ["sent", "delivered", "opened", "clicked", "replied", "bounced", "read"]:
                    v = events.get(evt_name)
                    if v:
                        event_list.append({"name": evt_name, "ts": str(v)[:16].replace("T", " ")})
                msgs.append({
                    "type": a.get("type"),
                    "timestamp": a.get("timestamp", ""),
                    "subject": a.get("subject", ""),
                    "body": a.get("body") or a.get("message") or a.get("message_preview") or "",
                    "recipient": a.get("recipient", ""),
                    "framework": a.get("framework", ""),
                    "variant": a.get("variant", ""),
                    "status": a.get("status", ""),
                    "events": event_list,
                })
            if msgs:
                contact_messages[lid] = {
                    "lead_name": ld.get("lead_name", ""),
                    "company_name": ld.get("company_name", ""),
                    "job_title": ld.get("job_title", ""),
                    "email_id": ld.get("email_id", ""),
                    "crm_link": crm_link(lid),
                    "messages": msgs,
                }
    contact_messages_json = json.dumps(contact_messages, ensure_ascii=False).replace("</", "<\\/")

    account_rows = ""
    for acc in account_list:
        dom = acc["domain"]
        nb = acc["emails_sent"] - acc["emails_bounced"]
        or_pct = f"{acc['emails_opened']/nb*100:.0f}%" if nb else "—"
        last_touch = (acc["last_touch"] or "")[:10]
        badge = ' <span class="acct-booked">MEETING BOOKED</span>' if acc["meeting_booked"] else ""

        contacts_html = ""
        sorted_contacts = sorted(acc["contacts"].items(), key=lambda x: -x[1]["emails"])
        for lid, c in sorted_contacts:
            c_flags = []
            if c["opens"]: c_flags.append(f'<span class="c-flag c-open">{c["opens"]} open</span>')
            if c["replies"]: c_flags.append(f'<span class="c-flag c-reply">{c["replies"]} reply</span>')
            if c["bounces"]: c_flags.append(f'<span class="c-flag c-bounce">{c["bounces"]} bounce</span>')
            if c["wa"]: c_flags.append(f'<span class="c-flag c-wa">{c["wa"]} WA</span>')
            if c["wa_replies"]: c_flags.append(f'<span class="c-flag c-reply">WA reply</span>')
            contacts_html += f'''<div class="acct-contact" onclick="openContactModal('{lid}')" title="Click to see all messages">
                <a href="{crm_link(lid)}" target="_blank" class="lead-link" onclick="event.stopPropagation()">{esc(c["lead_name"] or lid)}</a>
                <div class="c-title">{esc((c["job_title"] or "")[:60])}</div>
                <div class="c-email">{esc(lid)} &middot; {c["emails"]} email{"s" if c["emails"]!=1 else ""}</div>
                <div class="c-flags">{"".join(c_flags) or '<span class="c-flag c-muted">sent only</span>'}</div>
            </div>'''

        contact_search_tokens = " ".join(
            f"{c.get('lead_name','')} {c.get('job_title','')}"
            for c in acc["contacts"].values()
        )
        search_blob = f"{acc['primary_company']} {dom} {' '.join(acc['companies'].keys())} {contact_search_tokens}".lower()

        account_rows += f'''<tr class="acct-row" data-search="{esc(search_blob)}" onclick="this.classList.toggle('expanded')">
            <td class="acct-co"><div class="acct-name">{esc(acc["primary_company"])}{badge}</div><div class="acct-dom">{esc(dom)}</div></td>
            <td class="acct-num">{acc["contact_count"]}</td>
            <td class="acct-num">{acc["emails_sent"]}</td>
            <td class="acct-num">{acc["emails_opened"]}</td>
            <td class="acct-num">{acc["emails_bounced"]}</td>
            <td class="acct-num">{acc["emails_replied"]}</td>
            <td class="acct-num">{acc["wa_sent"]}</td>
            <td class="acct-num">{acc["wa_replied"]}</td>
            <td class="acct-num"><b>{or_pct}</b></td>
            <td class="acct-num">{last_touch}</td>
        </tr>
        <tr class="acct-details"><td colspan="10"><div class="acct-details-grid">{contacts_html}</div></td></tr>'''

    accounts_count = len(account_list)
    accounts_with_opens = sum(1 for a in account_list if a["emails_opened"] > 0)

    # --- Build Replies tab rows (all WA + email replies, newest first) ---
    reply_items = []
    for lid, ld in leads.items():
        for a in ld.get("actions", []):
            events = a.get("events") or {}
            if not events.get("replied"):
                continue
            reply_items.append({
                "lid": lid,
                "lead_name": ld.get("lead_name", ""),
                "company_name": ld.get("company_name", ""),
                "job_title": ld.get("job_title", ""),
                "type": a.get("type", ""),
                "subject": a.get("subject", ""),
                "body": a.get("body") or a.get("message") or a.get("message_preview") or "",
                "recipient": a.get("recipient", ""),
                "framework": a.get("framework", ""),
                "replied_at": events.get("replied", ""),
                "flags": a.get("flags") or [],
                "meeting_booked": ld.get("meeting_booked", False),
            })
    reply_items.sort(key=lambda r: r["replied_at"] or "", reverse=True)

    reply_rows = ""
    for r in reply_items:
        type_badge = (
            '<span class="rep-type rep-type-wa">WhatsApp</span>'
            if r["type"] == "whatsapp"
            else '<span class="rep-type rep-type-email">Email</span>'
        )
        meeting_badge = ' <span class="acct-booked">MEETING BOOKED</span>' if r["meeting_booked"] else ""
        flag_str = ""
        for f in r["flags"]:
            if "MEETING" in f:
                flag_str += '<span class="r-flag r-flag-booked">meeting</span>'
            elif "BUYING" in f:
                flag_str += '<span class="r-flag r-flag-buying">buying signal</span>'
            elif "SOFT" in f:
                flag_str += '<span class="r-flag r-flag-soft">soft</span>'
            else:
                flag_str += f'<span class="r-flag">{esc(f.lower())}</span>'
        body_preview = esc((r["body"] or "")[:400])
        subject_line = (
            f'<div class="rep-subject">{esc(r["subject"])}</div>'
            if r["subject"] else ""
        )
        reply_rows += f'''<div class="rep-card">
            <div class="rep-head">
                <div>
                    <a href="{crm_link(r["lid"])}" target="_blank" class="rep-name">{esc(r["lead_name"] or r["lid"])}</a>{meeting_badge}
                    <div class="rep-sub">{esc(r["job_title"] or "")} &middot; {esc(r["company_name"] or "")}</div>
                </div>
                <div class="rep-meta">
                    {type_badge}
                    <span class="rep-ts">{esc(str(r["replied_at"])[:16].replace("T"," "))}</span>
                </div>
            </div>
            {subject_line}
            <div class="rep-body">{body_preview}</div>
            <div class="rep-flags">{flag_str}</div>
        </div>'''

    total_reply_count = len(reply_items)

    # --- Hot leads (opened) ---
    hot_rows = ""
    for lid, ld in leads.items():
        for a in ld.get("actions", []):
            if a.get("status") == "opened" and a.get("type") == "email":
                hot_rows += f'''<tr>
                    <td><a href="{crm_link(lid)}" target="_blank">{esc(ld.get("lead_name",""))}</a></td>
                    <td>{esc((ld.get("company_name","") or "")[:35])}</td>
                    <td>{esc((ld.get("job_role_category","") or "").replace("_"," ").title())}</td>
                    <td>{esc((a.get("subject","") or "")[:60])}</td>
                    <td>{(a.get("events",{}).get("opened") or "")[:10]}</td>
                    <td><a href="{crm_link(lid)}" target="_blank" class="crm-btn">CRM</a></td>
                </tr>'''

    # --- Meetings Booked (Overview tab) ---
    def _fmt_ist(iso):
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%a %b %d, %Y · %I:%M %p %Z").strip().rstrip(" ·")
        except Exception:
            return iso or ""

    meetings = meta.get("meetings_booked", []) or []
    meetings_cards_html = ""
    for m in sorted(meetings, key=lambda x: x.get("scheduled_for", ""), reverse=True):
        src_lid = m.get("source_lead_id", "")
        src_lead = leads.get(src_lid, {}) if src_lid else {}
        src_actions = src_lead.get("actions", []) or []
        booked_at = m.get("booked_at", "")

        # Outreach that preceded the booking — emails + WA sent to the source contact before booked_at
        triggers = []
        for a in sorted(src_actions, key=lambda x: x.get("timestamp", "")):
            ts = a.get("timestamp", "")
            if booked_at and ts and ts > booked_at:
                continue
            t = a.get("type")
            if t == "email":
                subj = (a.get("subject") or "").strip()
                triggers.append({
                    "kind": "email",
                    "when": ts,
                    "subject": subj,
                    "body": (a.get("body") or "").strip(),
                    "framework": a.get("framework", ""),
                    "status": (a.get("events") or {}),
                })
            elif t == "whatsapp":
                triggers.append({
                    "kind": "whatsapp",
                    "when": ts,
                    "subject": "",
                    "body": (a.get("message") or a.get("body") or "").strip(),
                    "framework": "",
                    "status": (a.get("events") or {}),
                })

        triggers_html = ""
        for tr in triggers:
            ev = tr["status"]
            ev_tags = []
            if ev.get("replied"): ev_tags.append('<span class="mt-ev rep">replied</span>')
            if ev.get("opened"): ev_tags.append('<span class="mt-ev opn">opened</span>')
            if ev.get("clicked"): ev_tags.append('<span class="mt-ev clk">clicked</span>')
            if ev.get("delivered") and not ev_tags: ev_tags.append('<span class="mt-ev del">delivered</span>')
            kind_badge = '<span class="mt-kind mt-kind-em">EMAIL</span>' if tr["kind"] == "email" else '<span class="mt-kind mt-kind-wa">WHATSAPP</span>'
            when_disp = (tr["when"] or "")[:10]
            title_line = esc(tr["subject"]) if tr["subject"] else "(WhatsApp message)"
            body_preview = esc(tr["body"][:320]) + ("…" if len(tr["body"]) > 320 else "")
            triggers_html += f'''
            <div class="mt-trigger">
              <div class="mt-trigger-head">
                {kind_badge}
                <span class="mt-trigger-subj">{title_line}</span>
                <span class="mt-trigger-when">{when_disp}</span>
                {" ".join(ev_tags)}
              </div>
              <div class="mt-trigger-body">{body_preview}</div>
            </div>'''

        scheduled_disp = _fmt_ist(m.get("scheduled_for", ""))
        attendee_name = esc(m.get("attendee_name", ""))
        attendee_email = esc(m.get("attendee_email", ""))
        company = esc(m.get("company", ""))
        domain = esc(m.get("company_domain") or (m.get("blocked_scope") or {}).get("domain") or "")
        meet_link = esc(m.get("meet_link", ""))
        source_contact = esc(m.get("source_contact") or src_lead.get("lead_name", ""))
        source_lead_link = crm_link(src_lid) if src_lid else "#"
        blocked_count = (m.get("blocked_scope") or {}).get("blocked_count", 0)
        notes = esc(m.get("notes", ""))

        sched_raw = m.get("scheduled_for", "")
        sched_is_tbd = (not sched_raw) or sched_raw == "TBD" or not scheduled_disp
        scheduled_display = "⏳ Scheduled time TBD" if sched_is_tbd else esc(scheduled_disp)
        trigger_count = len(triggers)
        meetings_cards_html += f'''
        <div class="mt-card collapsed" onclick="toggleMeeting(this, event)">
          <div class="mt-head">
            <div class="mt-co">
              <div class="mt-co-name">{company} <span class="mt-chev">▸</span></div>
              <div class="mt-co-dom">{domain} &middot; {attendee_name} &lt;{attendee_email}&gt; &middot; {trigger_count} touch{"es" if trigger_count != 1 else ""}</div>
            </div>
            <div class="mt-when">
              <div class="mt-when-lbl">Scheduled</div>
              <div class="mt-when-val">{scheduled_display}</div>
            </div>
          </div>
          <div class="mt-body">
            <div class="mt-row">
              <span class="mt-lbl">Meeting with</span>
              <span class="mt-val"><strong>{attendee_name}</strong> &lt;{attendee_email}&gt;</span>
            </div>
            <div class="mt-row">
              <span class="mt-lbl">Source contact</span>
              <span class="mt-val">{source_contact} &middot; <a href="{source_lead_link}" target="_blank" class="mt-link">view lead ↗</a></span>
            </div>
            <div class="mt-row">
              <span class="mt-lbl">Meeting link</span>
              <span class="mt-val">{(f'<a href="{meet_link}" target="_blank" class="mt-link">{meet_link}</a>') if meet_link and meet_link != "TBD" else "<em style='color:#71717a'>TBD — add Meet link</em>"}</span>
            </div>
            <div class="mt-row">
              <span class="mt-lbl">Domain blocked</span>
              <span class="mt-val">{blocked_count} lead(s) on <code>@{domain}</code></span>
            </div>
            {f'<div class="mt-notes">{notes}</div>' if notes else ""}
            <div class="mt-triggers-title">Outreach that led to this booking ({len(triggers)})</div>
            <div class="mt-triggers">{triggers_html if triggers_html else '<div class="mt-empty">No outreach found on source lead.</div>'}</div>
          </div>
        </div>'''

    if meetings:
        meetings_section_html = f'''
        <div class="section mt-section">
            <h2>🎯 Meetings Booked <span class="mt-count">{len(meetings)}</span></h2>
            <div class="mt-grid">{meetings_cards_html}</div>
        </div>'''
    else:
        meetings_section_html = ""

    meetings_count = len(meetings)

    # --- Today's Schedule (Overview) ---
    try:
        with open('sdr_schedule.json') as f:
            sched = json.load(f)
    except Exception:
        sched = None

    if sched:
        try:
            from datetime import datetime as _dt
            from zoneinfo import ZoneInfo as _ZI
            _ist = _ZI("Asia/Kolkata")
            _now_ist = _dt.now(_ist)
            win_start = _dt.fromisoformat(sched['outreach_window_ist']['start'])
            win_end = _dt.fromisoformat(sched['outreach_window_ist']['end'])
            in_window = win_start <= _now_ist <= win_end
            total_elapsed = (win_end - win_start).total_seconds()
            progress_pct = max(0, min(100, (_now_ist - win_start).total_seconds() / total_elapsed * 100))
        except Exception:
            in_window = False
            progress_pct = 0

        budget = sched.get('email_budget', {})
        cap = budget.get('daily_cap', 300)
        sent = budget.get('sent_today', 0)
        budget_pct = min(100, int(sent / cap * 100)) if cap else 0

        # Build upcoming cycle rows
        sdr_rows_html = ""
        for batch in sched.get('sdr_cycles', {}).get('planned_batches', [])[:8]:
            fire = batch.get('fire_at', '')
            try:
                fire_disp = _dt.fromisoformat(fire).strftime("%I:%M %p").lstrip("0")
            except Exception:
                fire_disp = fire[:16]
            count = batch.get('planned_count', 0)
            prev = batch.get('preview', [])
            prev_html = ""
            for p in prev:
                pe = ' <span class="sch-pe">personal</span>' if p.get('personal_email') else ''
                prev_html += f'<div class="sch-lead"><span class="sch-lead-co">{esc((p.get("company") or "")[:28])}</span><span class="sch-lead-name">{esc((p.get("name") or "")[:22])}</span>{pe}</div>'
            if count > len(prev):
                prev_html += f'<div class="sch-more">+ {count - len(prev)} more</div>'
            sdr_rows_html += f'''
            <div class="sch-cycle">
              <div class="sch-cycle-head"><span class="sch-time">{fire_disp}</span><span class="sch-n">{count} sends</span></div>
              <div class="sch-cycle-body">{prev_html if prev_html else '<div class="sch-empty">— no sends planned —</div>'}</div>
            </div>'''

        obs_slots = sched.get('observer_cycles', {}).get('upcoming_today', [])
        obs_html = ""
        for s in obs_slots:
            try:
                obs_html += f'<span class="sch-obs-slot">{_dt.fromisoformat(s).strftime("%I:%M %p").lstrip("0")}</span>'
            except Exception:
                pass

        window_status_html = (
            '<span class="sch-win-active">● ACTIVE</span>' if in_window
            else '<span class="sch-win-inactive">● OUTSIDE WINDOW</span>'
        )

        schedule_html = f'''
        <div class="sch-section">
            <div class="sch-header">
                <h2>📅 Today's Schedule <span class="sch-date">{sched.get("date_ist","")}</span></h2>
                <div class="sch-meta">
                    <div class="sch-meta-item"><div class="sch-meta-lbl">Outreach Window</div><div class="sch-meta-val">11:00 AM – 7:30 PM IST {window_status_html}</div></div>
                    <div class="sch-meta-item"><div class="sch-meta-lbl">Email Budget</div><div class="sch-meta-val">{sent} / {cap} sent · <strong>{budget.get("remaining", cap - sent)} remaining</strong></div></div>
                    <div class="sch-meta-item"><div class="sch-meta-lbl">Queue</div><div class="sch-meta-val">{sched.get("queue_size_remaining", 0)} qualified leads</div></div>
                </div>
                <div class="sch-progress"><div class="sch-progress-bar" style="width:{progress_pct:.0f}%"></div></div>
            </div>
            <div class="sch-grid">
                <div class="sch-col">
                    <div class="sch-col-title">🚀 SDR Cycles (every 45 min, in window)</div>
                    <div class="sch-cycles">{sdr_rows_html if sdr_rows_html else '<div class="sch-empty">No cycles remaining today.</div>'}</div>
                </div>
                <div class="sch-col">
                    <div class="sch-col-title">👁 Observer Cycles (every 3h, 24/7)</div>
                    <div class="sch-obs-list">{obs_html if obs_html else '<div class="sch-empty">All observer slots complete today.</div>'}</div>
                </div>
            </div>
            <div class="sch-crons-section">
                <div class="sch-col-title">⚙️ Active Cron Jobs</div>
                <div class="sch-crons">
                    {"".join(
                        f'<div class="sch-cron-card"><div class="sch-cron-role">{esc(c.get("role",""))}</div>'
                        f'<div class="sch-cron-expr"><code>{esc(c.get("cron",""))}</code> <span class="sch-cron-tz">{esc(c.get("cron_tz",""))}</span></div>'
                        f'<div class="sch-cron-id">id: <code>{esc(c.get("id",""))}</code></div>'
                        f'<div class="sch-cron-meta">fires {c.get("fires_per_day","?")}/day · {esc(str(c.get("effective_cycles_per_day","?")))} effective · {esc(c.get("window_enforced",""))}</div>'
                        f'<div class="sch-cron-scope">{esc(c.get("scope",""))} · {esc(c.get("auto_expires",""))}</div></div>'
                        for c in sched.get("active_crons", [])
                    ) if sched.get("active_crons") else '<div class="sch-empty">No active crons — loops not started.</div>'}
                </div>
            </div>
        </div>'''
    else:
        schedule_html = ""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentic SDR — Activity Dashboard</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif; background:#0f1117; color:#e4e4e7; font-size:14px; }}
    a {{ color:#60a5fa; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .container {{ max-width:1500px; margin:0 auto; padding:24px; }}

    /* Header */
    .header {{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:24px; border-bottom:1px solid #27272a; padding-bottom:16px; }}
    .header h1 {{ font-size:24px; font-weight:700; color:#f4f4f5; }}
    .header h1 span {{ color:#8b5cf6; }}
    .header .updated {{ color:#71717a; font-size:13px; }}

    /* Stat cards */
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:24px; }}
    .card {{ background:#18181b; border:1px solid #27272a; border-radius:10px; padding:16px; }}
    .card .num {{ font-size:28px; font-weight:700; }}
    .card .lbl {{ color:#71717a; font-size:12px; margin-top:2px; text-transform:uppercase; letter-spacing:0.5px; }}
    .card.c-blue .num {{ color:#60a5fa; }}
    .card.c-green .num {{ color:#34d399; }}
    .card.c-purple .num {{ color:#a78bfa; }}
    .card.c-red .num {{ color:#f87171; }}
    .card.c-yellow .num {{ color:#fbbf24; }}
    .card.c-gray .num {{ color:#a1a1aa; }}

    /* Funnel */
    .funnel {{ margin:16px 0; }}
    .funnel-row {{ margin-bottom:8px; }}
    .funnel-bar {{ display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-radius:8px; min-width:200px; transition:all 0.3s; }}
    .funnel-bar:hover {{ filter:brightness(1.15); transform:translateX(4px); }}
    .funnel-label {{ font-weight:600; font-size:14px; color:#fff; }}
    .funnel-num {{ font-weight:700; font-size:20px; color:#fff; }}
    .funnel-num small {{ font-size:13px; font-weight:400; opacity:0.8; }}

    /* Overview cards */
    .overview-cards {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; margin-top:16px; }}
    .ov-card {{ background:#18181b; border:1px solid #27272a; border-radius:10px; padding:24px; text-align:center; }}
    .ov-num {{ font-size:40px; font-weight:700; }}
    .ov-lbl {{ color:#a1a1aa; font-size:13px; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px; }}
    .ov-pct {{ color:#71717a; font-size:12px; margin-top:8px; }}

    /* Tabs */
    .tabs {{ display:flex; gap:4px; margin-bottom:20px; background:#18181b; border-radius:10px; padding:4px; border:1px solid #27272a; width:fit-content; }}
    .tab {{ padding:8px 20px; border-radius:8px; cursor:pointer; font-size:13px; font-weight:500; color:#a1a1aa; transition:all 0.2s; user-select:none; }}
    .tab:hover {{ color:#e4e4e7; }}
    .tab.active {{ background:#27272a; color:#f4f4f5; }}
    .tab-content {{ display:none; }}
    .tab-content.active {{ display:block; }}

    /* Filter bar */
    .filter-bar {{ background:#18181b; border:1px solid #27272a; border-radius:10px; padding:12px 16px; margin-bottom:16px; position:sticky; top:0; z-index:100; }}
    .filter-row {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
    .filter-row label {{ font-size:11px; color:#71717a; text-transform:uppercase; letter-spacing:0.5px; margin-right:2px; }}
    .filter-group {{ display:flex; align-items:center; gap:4px; }}
    .filter-bar select, .filter-bar input {{
        background:#27272a; border:1px solid #3f3f46; border-radius:6px; color:#e4e4e7;
        font-size:12px; padding:5px 8px; outline:none; transition:border 0.2s;
    }}
    .filter-bar select:focus, .filter-bar input:focus {{ border-color:#8b5cf6; }}
    .filter-bar select {{ min-width:110px; max-width:180px; cursor:pointer; }}
    .filter-bar input {{ min-width:180px; }}
    .filter-count {{ font-size:12px; color:#a1a1aa; margin-left:auto; padding-left:12px; white-space:nowrap; }}
    .filter-count strong {{ color:#f4f4f5; }}
    .btn-clear {{ background:#3f3f46; border:1px solid #52525b; border-radius:6px; color:#a1a1aa; font-size:11px; padding:5px 10px; cursor:pointer; transition:all 0.2s; }}
    .btn-clear:hover {{ background:#52525b; color:#e4e4e7; }}

    /* Activity table */
    .activity-table {{ width:100%; border-collapse:collapse; }}
    .activity-table thead th {{
        text-align:left; padding:8px 10px; font-size:11px; text-transform:uppercase;
        letter-spacing:0.5px; color:#71717a; background:#15151a; border-bottom:1px solid #27272a;
        position:sticky; top:54px; z-index:90;
    }}
    .activity-table tbody tr {{ border-bottom:1px solid #1e1e23; transition:background 0.15s; }}
    .activity-table tbody tr:hover {{ background:#1c1c24; }}
    .activity-table tbody tr.hidden {{ display:none; }}
    .activity-table td {{ padding:10px; vertical-align:top; }}

    .col-date {{ color:#71717a; font-size:12px; font-variant-numeric:tabular-nums; white-space:nowrap; }}
    .time-sub {{ color:#52525b; font-size:11px; }}
    .type-icon {{ font-size:18px; }}
    .email-icon {{ color:#60a5fa; }}
    .wa-icon {{ color:#34d399; }}

    .lead-link {{ font-weight:600; color:#e4e4e7; }}
    .lead-link:hover {{ color:#60a5fa; }}
    .lead-company {{ color:#a1a1aa; font-size:12px; }}
    .lead-meta {{ color:#52525b; font-size:11px; margin-top:2px; }}

    .msg-subject {{ font-weight:600; color:#d4d4d8; margin-bottom:4px; font-size:13px; }}
    .msg-body {{
        color:#a1a1aa; font-size:12.5px; line-height:1.5; padding:6px 8px;
        background:#111116; border-radius:6px; border:1px solid #27272a;
        margin-bottom:4px; white-space:pre-wrap; word-break:break-word;
        transition: max-height 0.3s ease;
    }}
    .msg-body.collapsed {{ max-height:42px; overflow:hidden; cursor:pointer; position:relative; }}
    .msg-body.collapsed::after {{
        content:'click to expand'; display:block; position:absolute; bottom:0; left:0; right:0;
        height:28px; background:linear-gradient(transparent, #111116 70%);
        text-align:center; font-size:10px; color:#71717a; padding-top:14px;
        pointer-events:none;
    }}
    .msg-body:not(.collapsed) {{ max-height:none; cursor:pointer; }}
    .msg-body.no-body {{ color:#52525b; font-style:italic; background:none; border:none; padding:2px 0; max-height:none; cursor:default; }}
    .msg-body.no-body::after {{ display:none; }}
    .msg-body.wa-body {{ border-left:3px solid #34d399; }}
    .msg-meta {{ color:#52525b; font-size:11px; }}

    .badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; color:white; letter-spacing:0.5px; }}
    .evt {{ display:inline-block; font-size:10px; padding:1px 6px; border-radius:4px; margin:1px 2px; background:#27272a; color:#a1a1aa; white-space:nowrap; }}
    .evt-delivered {{ color:#34d399; }}
    .evt-opened {{ color:#fbbf24; background:#422006; }}
    .evt-clicked {{ color:#60a5fa; background:#172554; }}
    .evt-bounced {{ color:#f87171; background:#450a0a; }}
    .evt-replied {{ color:#a78bfa; background:#2e1065; }}
    .evt-error {{ color:#f87171; }}
    .evt-read {{ color:#34d399; background:#052e16; }}

    .crm-btn {{ display:inline-block; padding:3px 10px; border-radius:6px; font-size:11px; font-weight:600; background:#27272a; color:#a1a1aa; border:1px solid #3f3f46; }}
    .crm-btn:hover {{ background:#3f3f46; color:#e4e4e7; text-decoration:none; }}

    /* Stat tables */
    .section {{ background:#18181b; border:1px solid #27272a; border-radius:10px; padding:20px; margin-bottom:16px; }}
    .section h2 {{ font-size:16px; font-weight:600; margin-bottom:12px; color:#d4d4d8; }}
    .stat-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    .stat-table th {{ text-align:left; padding:6px 10px; color:#71717a; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid #27272a; }}
    .stat-table td {{ padding:6px 10px; border-bottom:1px solid #1e1e23; }}
    .stat-table tr:hover {{ background:#1c1c24; }}

    /* Accounts tab */
    .acct-hint {{ color:#71717a; font-size:12px; margin-bottom:8px; }}
    .acct-search {{ display:flex; align-items:center; gap:16px; margin-bottom:12px; }}
    .acct-search input {{ flex:1; max-width:420px; padding:8px 12px; background:#18181b; border:1px solid #27272a; border-radius:6px; color:#e4e4e7; font-size:13px; font-family:inherit; }}
    .acct-search input:focus {{ outline:none; border-color:#8b5cf6; }}
    .acct-search input::placeholder {{ color:#52525b; }}
    .acct-search .acct-count {{ color:#71717a; font-size:12px; }}
    .acct-table tr.acct-row.hidden, .acct-table tr.acct-details.hidden {{ display:none; }}
    .acct-table .acct-num {{ text-align:right; color:#e4e4e7; font-variant-numeric:tabular-nums; }}
    .acct-table .acct-row {{ cursor:pointer; }}
    .acct-table .acct-row:hover {{ background:#1c1c24; }}
    .acct-table .acct-name {{ font-weight:600; color:#f4f4f5; font-size:14px; }}
    .acct-table .acct-dom {{ color:#71717a; font-size:11px; font-family:ui-monospace,monospace; }}
    .acct-booked {{ display:inline-block; padding:1px 6px; background:#16a34a; color:#fff; font-size:10px; font-weight:700; border-radius:4px; margin-left:8px; vertical-align:middle; }}
    .acct-details {{ display:none; background:#141418; }}
    .acct-row.expanded + .acct-details {{ display:table-row; }}
    .acct-details-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:10px; padding:12px 10px; }}
    .acct-contact {{ background:#1a1a20; border:1px solid #27272a; border-radius:6px; padding:10px; }}
    .acct-contact .c-title {{ color:#a1a1aa; font-size:11px; margin-top:2px; }}
    .acct-contact .c-email {{ color:#52525b; font-size:10px; font-family:ui-monospace,monospace; margin-top:4px; }}
    .acct-contact .c-flags {{ margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; }}
    .c-flag {{ font-size:10px; padding:1px 6px; border-radius:3px; }}
    .c-flag.c-open {{ background:#1e3a8a; color:#93c5fd; }}
    .c-flag.c-reply {{ background:#166534; color:#86efac; }}
    .c-flag.c-bounce {{ background:#7f1d1d; color:#fca5a5; }}
    .c-flag.c-wa {{ background:#14532d; color:#86efac; }}
    .c-flag.c-muted {{ background:#27272a; color:#71717a; }}
    .acct-contact {{ cursor:pointer; transition:all 0.15s; }}
    .acct-contact:hover {{ border-color:#8b5cf6; background:#1f1f28; }}

    /* Replies tab */
    .rep-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:12px; margin-top:12px; }}
    .rep-card {{ background:#18181b; border:1px solid #27272a; border-radius:8px; padding:14px; }}
    .rep-card:hover {{ border-color:#8b5cf6; }}
    .rep-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:6px; }}
    .rep-name {{ font-weight:700; color:#f4f4f5; font-size:14px; text-decoration:none; }}
    .rep-name:hover {{ color:#a78bfa; }}
    .rep-sub {{ color:#a1a1aa; font-size:11px; margin-top:2px; }}
    .rep-meta {{ display:flex; flex-direction:column; align-items:flex-end; gap:4px; }}
    .rep-type {{ font-size:10px; padding:2px 8px; border-radius:4px; text-transform:uppercase; font-weight:700; letter-spacing:0.5px; }}
    .rep-type-email {{ background:#1e3a8a; color:#93c5fd; }}
    .rep-type-wa {{ background:#14532d; color:#86efac; }}
    .rep-ts {{ color:#52525b; font-size:10px; font-family:ui-monospace,monospace; }}
    .rep-subject {{ color:#d4d4d8; font-size:12px; font-style:italic; margin:6px 0 4px 0; }}
    .rep-body {{ background:#0f1117; border:1px solid #27272a; border-radius:6px; padding:10px; color:#e4e4e7; font-size:13px; line-height:1.5; white-space:pre-wrap; max-height:200px; overflow-y:auto; }}
    .rep-flags {{ margin-top:8px; display:flex; flex-wrap:wrap; gap:4px; }}
    .r-flag {{ font-size:10px; padding:2px 6px; border-radius:3px; background:#27272a; color:#a1a1aa; text-transform:lowercase; }}
    .r-flag-booked {{ background:#16a34a; color:#fff; font-weight:600; }}
    .r-flag-buying {{ background:#dc2626; color:#fff; font-weight:600; }}
    .r-flag-soft {{ background:#713f12; color:#fde68a; }}

    /* Contact messages modal */
    .modal-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:1000; align-items:flex-start; justify-content:center; padding:40px 20px; overflow-y:auto; }}
    .modal-overlay.open {{ display:flex; }}
    .modal {{ background:#18181b; border:1px solid #27272a; border-radius:12px; max-width:780px; width:100%; padding:24px; }}
    .modal-header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; border-bottom:1px solid #27272a; padding-bottom:12px; }}
    .modal-header h3 {{ font-size:18px; color:#f4f4f5; margin-bottom:4px; }}
    .modal-header .m-sub {{ color:#a1a1aa; font-size:12px; }}
    .modal-header .m-sub a {{ color:#60a5fa; }}
    .modal-close {{ background:none; border:none; color:#71717a; font-size:22px; cursor:pointer; padding:0 6px; line-height:1; }}
    .modal-close:hover {{ color:#f4f4f5; }}
    .msg-item {{ background:#1a1a20; border:1px solid #27272a; border-radius:8px; padding:14px; margin-bottom:12px; }}
    .msg-item-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:8px; }}
    .msg-item-head .m-type {{ font-size:10px; padding:2px 8px; border-radius:4px; text-transform:uppercase; font-weight:700; letter-spacing:0.5px; }}
    .msg-item-head .m-type.email {{ background:#1e3a8a; color:#93c5fd; }}
    .msg-item-head .m-type.whatsapp {{ background:#14532d; color:#86efac; }}
    .msg-item-head .m-ts {{ color:#71717a; font-size:11px; font-family:ui-monospace,monospace; }}
    .msg-item .m-subject {{ font-weight:600; color:#f4f4f5; font-size:14px; margin-bottom:6px; }}
    .msg-item .m-body {{ white-space:pre-wrap; color:#d4d4d8; font-size:13px; line-height:1.55; background:#0f1117; border:1px solid #27272a; border-radius:6px; padding:10px 12px; margin-bottom:8px; max-height:320px; overflow-y:auto; }}
    .msg-item .m-meta {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }}
    .msg-item .m-meta span {{ font-size:10px; padding:2px 6px; border-radius:3px; background:#27272a; color:#a1a1aa; }}
    .msg-item .m-meta .evt-opened {{ background:#1e3a8a; color:#93c5fd; }}
    .msg-item .m-meta .evt-replied {{ background:#166534; color:#86efac; }}
    .msg-item .m-meta .evt-bounced {{ background:#7f1d1d; color:#fca5a5; }}
    .msg-item .m-meta .evt-clicked {{ background:#713f12; color:#fde68a; }}
    .hot-badge {{ background:#422006; color:#fbbf24; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; }}
    .analytics-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(400px,1fr)); gap:16px; }}

    /* Today's Schedule */
    .sch-section {{ background:#18181b; border:1px solid #3f3f46; border-radius:12px; padding:18px 20px; margin-bottom:20px; }}
    .sch-header h2 {{ margin:0 0 12px; font-size:16px; display:flex; align-items:center; gap:10px; color:#e4e4e7; }}
    .sch-date {{ font-size:12px; color:#71717a; font-weight:400; font-family:ui-monospace,monospace; }}
    .sch-meta {{ display:flex; gap:24px; flex-wrap:wrap; margin-bottom:10px; }}
    .sch-meta-item {{ flex:1; min-width:180px; }}
    .sch-meta-lbl {{ font-size:10px; text-transform:uppercase; letter-spacing:0.5px; color:#71717a; margin-bottom:2px; }}
    .sch-meta-val {{ font-size:13px; color:#e4e4e7; }}
    .sch-meta-val strong {{ color:#34d399; }}
    .sch-win-active {{ margin-left:8px; color:#22c55e; font-weight:600; font-size:11px; }}
    .sch-win-inactive {{ margin-left:8px; color:#f87171; font-weight:600; font-size:11px; }}
    .sch-progress {{ height:4px; background:#27272a; border-radius:2px; overflow:hidden; margin-top:6px; }}
    .sch-progress-bar {{ height:100%; background:linear-gradient(90deg,#8b5cf6,#22c55e); transition:width 0.3s; }}
    .sch-grid {{ display:grid; grid-template-columns:2fr 1fr; gap:20px; margin-top:14px; }}
    .sch-col-title {{ font-size:12px; text-transform:uppercase; letter-spacing:0.5px; color:#a1a1aa; font-weight:600; margin-bottom:10px; }}
    .sch-cycles {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:8px; }}
    .sch-cycle {{ background:#0a0a0a; border:1px solid #27272a; border-radius:6px; padding:8px 10px; font-size:11px; }}
    .sch-cycle-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px dashed #27272a; padding-bottom:4px; }}
    .sch-time {{ color:#a78bfa; font-weight:700; font-family:ui-monospace,monospace; }}
    .sch-n {{ color:#71717a; font-size:10px; }}
    .sch-cycle-body {{ display:flex; flex-direction:column; gap:3px; }}
    .sch-lead {{ display:flex; justify-content:space-between; gap:6px; font-size:10px; }}
    .sch-lead-co {{ color:#e4e4e7; font-weight:500; flex:1; }}
    .sch-lead-name {{ color:#71717a; }}
    .sch-pe {{ background:#166534; color:#86efac; padding:1px 4px; border-radius:3px; font-size:9px; font-weight:600; }}
    .sch-more {{ color:#52525b; font-size:10px; font-style:italic; margin-top:2px; }}
    .sch-empty {{ color:#52525b; font-size:11px; font-style:italic; text-align:center; padding:6px; }}
    .sch-obs-list {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }}
    .sch-obs-slot {{ background:#27272a; color:#a1a1aa; padding:3px 8px; border-radius:4px; font-size:11px; font-family:ui-monospace,monospace; }}
    .sch-loop-cmd {{ font-size:11px; color:#71717a; margin-top:4px; }}
    .sch-loop-cmd code {{ background:#0a0a0a; color:#a78bfa; padding:2px 6px; border-radius:3px; font-size:10px; }}
    .sch-crons-section {{ margin-top:18px; padding-top:14px; border-top:1px solid #27272a; }}
    .sch-crons {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:10px; margin-top:8px; }}
    .sch-cron-card {{ background:#0a0a0a; border:1px solid #27272a; border-left:3px solid #8b5cf6; border-radius:6px; padding:10px 12px; }}
    .sch-cron-role {{ font-size:12px; font-weight:600; color:#e4e4e7; }}
    .sch-cron-expr {{ margin-top:4px; font-size:11px; }}
    .sch-cron-expr code {{ background:#18181b; color:#fbbf24; padding:2px 6px; border-radius:3px; font-family:ui-monospace,monospace; }}
    .sch-cron-tz {{ color:#71717a; font-size:10px; margin-left:4px; }}
    .sch-cron-id {{ font-size:10px; color:#71717a; margin-top:3px; }}
    .sch-cron-id code {{ background:#18181b; color:#86efac; padding:1px 4px; border-radius:2px; font-size:10px; }}
    .sch-cron-meta {{ font-size:10px; color:#a1a1aa; margin-top:4px; }}
    .sch-cron-scope {{ font-size:10px; color:#52525b; font-style:italic; margin-top:2px; }}

    /* Clickable KPI card */
    .card-clickable {{ cursor:pointer; transition:transform 0.15s, border-color 0.15s; }}
    .card-clickable:hover {{ transform:translateY(-2px); border-color:#22c55e; }}

    /* Meetings modal */
    .mt-modal {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.8); z-index:1000; padding:40px 20px; overflow-y:auto; backdrop-filter:blur(4px); }}
    .mt-modal.open {{ display:block; }}
    .mt-modal-inner {{ max-width:1100px; margin:0 auto; background:linear-gradient(180deg,#052e16 0%,#0a0f0b 100%); border:1px solid #22c55e; border-radius:12px; overflow:hidden; }}
    .mt-modal-head {{ display:flex; justify-content:space-between; align-items:center; padding:18px 24px; background:#0d1f14; border-bottom:1px solid #166534; position:sticky; top:0; z-index:10; }}
    .mt-modal-head h2 {{ margin:0; color:#86efac; display:flex; align-items:center; gap:10px; font-size:20px; }}
    .mt-modal-close {{ background:#27272a; border:1px solid #3f3f46; color:#e4e4e7; width:32px; height:32px; border-radius:6px; cursor:pointer; font-size:16px; transition:all 0.15s; }}
    .mt-modal-close:hover {{ background:#3f3f46; color:#fff; }}
    .mt-modal-body {{ padding:24px; }}

    /* Meetings cards (shared with modal) */
    .mt-section {{ margin-bottom:20px; border:1px solid #22c55e; background:linear-gradient(180deg,#052e16 0%,#0c1512 100%); }}
    .mt-section h2 {{ color:#86efac; display:flex; align-items:center; gap:10px; }}
    .mt-count {{ background:#16a34a; color:#fff; padding:2px 10px; border-radius:10px; font-size:13px; font-weight:700; }}
    .mt-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:16px; margin-top:14px; }}
    .mt-card {{ background:#0a0f0b; border:1px solid #166534; border-radius:10px; overflow:hidden; cursor:pointer; transition:border-color 0.2s; }}
    .mt-card:hover {{ border-color:#22c55e; }}
    .mt-card.collapsed .mt-body {{ display:none; }}
    .mt-card.collapsed .mt-head {{ border-bottom:none; }}
    .mt-chev {{ display:inline-block; margin-left:6px; color:#71717a; font-size:12px; transition:transform 0.2s; }}
    .mt-card:not(.collapsed) .mt-chev {{ transform:rotate(90deg); color:#86efac; }}
    .mt-body {{ cursor:default; }}
    .mt-head {{ display:flex; justify-content:space-between; align-items:flex-start; padding:14px 18px; background:#0d1f14; border-bottom:1px solid #166534; }}
    .mt-co-name {{ font-size:16px; font-weight:700; color:#f4f4f5; }}
    .mt-co-dom {{ font-size:12px; color:#86efac; font-family:ui-monospace,monospace; margin-top:2px; }}
    .mt-when {{ text-align:right; }}
    .mt-when-lbl {{ font-size:10px; text-transform:uppercase; letter-spacing:0.5px; color:#71717a; }}
    .mt-when-val {{ font-size:13px; font-weight:600; color:#34d399; margin-top:2px; }}
    .mt-body {{ padding:14px 18px; }}
    .mt-row {{ display:flex; gap:10px; margin-bottom:8px; font-size:13px; align-items:baseline; }}
    .mt-lbl {{ color:#71717a; min-width:110px; font-size:11px; text-transform:uppercase; letter-spacing:0.3px; }}
    .mt-val {{ color:#e4e4e7; flex:1; word-break:break-word; }}
    .mt-val code {{ background:#18181b; padding:1px 6px; border-radius:4px; font-size:12px; color:#86efac; }}
    .mt-link {{ color:#60a5fa; text-decoration:none; }}
    .mt-link:hover {{ text-decoration:underline; }}
    .mt-notes {{ margin:10px 0 4px; padding:8px 10px; background:#0d1f14; border-left:3px solid #16a34a; border-radius:4px; font-size:12px; color:#a1a1aa; font-style:italic; }}
    .mt-triggers-title {{ margin-top:14px; margin-bottom:8px; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; color:#a1a1aa; font-weight:600; }}
    .mt-triggers {{ display:flex; flex-direction:column; gap:8px; }}
    .mt-trigger {{ background:#18181b; border:1px solid #27272a; border-radius:6px; padding:10px 12px; }}
    .mt-trigger-head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
    .mt-trigger-subj {{ flex:1; font-size:13px; color:#f4f4f5; font-weight:500; min-width:200px; }}
    .mt-trigger-when {{ font-size:11px; color:#71717a; font-family:ui-monospace,monospace; }}
    .mt-trigger-body {{ font-size:12px; color:#a1a1aa; white-space:pre-wrap; line-height:1.5; max-height:120px; overflow:hidden; position:relative; }}
    .mt-kind {{ font-size:9px; font-weight:700; padding:2px 7px; border-radius:10px; letter-spacing:0.5px; }}
    .mt-kind-em {{ background:#1e3a8a; color:#93c5fd; }}
    .mt-kind-wa {{ background:#166534; color:#86efac; }}
    .mt-ev {{ font-size:9px; font-weight:600; padding:2px 6px; border-radius:8px; text-transform:uppercase; letter-spacing:0.3px; }}
    .mt-ev.opn {{ background:#1e3a8a; color:#93c5fd; }}
    .mt-ev.rep {{ background:#166534; color:#86efac; }}
    .mt-ev.clk {{ background:#713f12; color:#fde68a; }}
    .mt-ev.del {{ background:#27272a; color:#a1a1aa; }}
    .mt-empty {{ color:#71717a; font-size:12px; font-style:italic; padding:8px 0; }}

    /* No results */
    .no-results {{ text-align:center; padding:40px 20px; color:#52525b; font-size:14px; display:none; }}

    /* Scrollbar */
    ::-webkit-scrollbar {{ width:6px; height:6px; }}
    ::-webkit-scrollbar-track {{ background:#18181b; }}
    ::-webkit-scrollbar-thumb {{ background:#3f3f46; border-radius:3px; }}
</style>
</head><body>
<div class="container">

    <div class="header">
        <div>
            <h1><span>Bolti</span> SDR Activity Dashboard</h1>
            <div style="color:#71717a;font-size:13px;margin-top:4px;">Agentic Sales Development Rep &middot; Full-Stack Cloud Contact Center</div>
        </div>
        <div class="updated">Last updated: {now}</div>
    </div>

    <div class="cards">
        <div class="card c-blue"><div class="num">{total_leads}</div><div class="lbl">Leads Contacted</div></div>
        <div class="card c-purple"><div class="num">{total_actions}</div><div class="lbl">Total Actions</div></div>
        <div class="card c-gray"><div class="num">{total_emails}</div><div class="lbl">Emails Sent</div></div>
        <div class="card c-green"><div class="num">{total_wa}</div><div class="lbl">WhatsApp Sent</div></div>
        <div class="card c-yellow"><div class="num">{total_opens} <small style="font-size:14px;color:#71717a">({open_rate})</small></div><div class="lbl">Opened</div></div>
        <div class="card c-red"><div class="num">{bounces} <small style="font-size:14px;color:#71717a">({bounce_rate})</small></div><div class="lbl">Bounced</div></div>
        <div class="card"><div class="num">{len(blocked)}</div><div class="lbl">Blocked / Opted Out</div></div>
        <div class="card c-green card-clickable" onclick="openMeetingsModal()" title="Click to view meeting details">
            <div class="num">{meetings_count}</div>
            <div class="lbl">Meetings Booked {"▸" if meetings_count else ""}</div>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="showTab('overview')">Overview</div>
        <div class="tab" onclick="showTab('activity')">Activity Log</div>
        <div class="tab" onclick="showTab('accounts')">Accounts ({accounts_count})</div>
        <div class="tab" onclick="showTab('replies')">Replies ({total_reply_count})</div>
        <div class="tab" onclick="showTab('hot')">Hot Leads ({total_opens})</div>
        <div class="tab" onclick="showTab('analytics')">Analytics</div>
    </div>

    <!-- TAB: Overview -->
    <div id="tab-overview" class="tab-content active">
        {schedule_html}
        <div class="analytics-grid">
            <div class="section">
                <h2>CRM Lead Funnel</h2>
                <div class="funnel">
                    <div class="funnel-row">
                        <div class="funnel-bar" style="width:100%;background:linear-gradient(90deg,#3b82f6,#60a5fa)">
                            <span class="funnel-label">Total Leads in CRM</span>
                            <span class="funnel-num">{crm_total:,}</span>
                        </div>
                    </div>
                    <div class="funnel-row">
                        <div class="funnel-bar" style="width:{crm_with_email/max(crm_total,1)*100:.0f}%;background:linear-gradient(90deg,#8b5cf6,#a78bfa)">
                            <span class="funnel-label">With Valid Email</span>
                            <span class="funnel-num">{crm_with_email:,} <small>({crm_with_email/max(crm_total,1)*100:.0f}%)</small></span>
                        </div>
                    </div>
                    <div class="funnel-row">
                        <div class="funnel-bar" style="width:{crm_with_phone/max(crm_total,1)*100:.0f}%;background:linear-gradient(90deg,#06b6d4,#22d3ee)">
                            <span class="funnel-label">With Phone Number</span>
                            <span class="funnel-num">{crm_with_phone:,} <small>({crm_with_phone/max(crm_total,1)*100:.0f}%)</small></span>
                        </div>
                    </div>
                    <div class="funnel-row">
                        <div class="funnel-bar" style="width:{crm_with_both/max(crm_total,1)*100:.0f}%;background:linear-gradient(90deg,#10b981,#34d399)">
                            <span class="funnel-label">With Email + Phone</span>
                            <span class="funnel-num">{crm_with_both:,} <small>({crm_with_both/max(crm_total,1)*100:.0f}%)</small></span>
                        </div>
                    </div>
                    <div class="funnel-row">
                        <div class="funnel-bar qualified" style="width:{crm_qualified/max(crm_total,1)*100:.0f}%;background:linear-gradient(90deg,#f59e0b,#fbbf24)">
                            <span class="funnel-label">Qualified (B2C / D2C / Large B2B)</span>
                            <span class="funnel-num">{crm_qualified:,} <small>({crm_qualified/max(crm_total,1)*100:.0f}%)</small></span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="section">
                <h2>Agent Outreach Coverage</h2>
                <div class="overview-cards">
                    <div class="ov-card">
                        <div class="ov-num" style="color:#60a5fa">{agent_emailed}</div>
                        <div class="ov-lbl">Leads Emailed</div>
                        <div class="ov-pct">{agent_emailed/max(crm_qualified,1)*100:.0f}% of qualified</div>
                    </div>
                    <div class="ov-card">
                        <div class="ov-num" style="color:#34d399">{agent_wa}</div>
                        <div class="ov-lbl">WhatsApp Touched</div>
                        <div class="ov-pct">{agent_wa/max(agent_emailed,1)*100:.0f}% of emailed</div>
                    </div>
                    <div class="ov-card">
                        <div class="ov-num" style="color:#a78bfa">{agent_both}</div>
                        <div class="ov-lbl">Both Email + WA</div>
                        <div class="ov-pct">Multi-channel touched</div>
                    </div>
                    <div class="ov-card">
                        <div class="ov-num" style="color:#fbbf24">{total_opens}</div>
                        <div class="ov-lbl">Email Opens</div>
                        <div class="ov-pct">{open_rate} open rate</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- TAB: Activity Log -->
    <div id="tab-activity" class="tab-content">
        <div class="filter-bar">
            <div class="filter-row">
                <div class="filter-group">
                    <label>Search</label>
                    <input type="text" id="f-search" placeholder="Name, company, subject..." oninput="applyFilters()">
                </div>
                <div class="filter-group">
                    <label>Status</label>
                    <select id="f-status" onchange="applyFilters()"><option value="">All</option>{status_options}</select>
                </div>
                <div class="filter-group">
                    <label>Type</label>
                    <select id="f-type" onchange="applyFilters()"><option value="">All</option>{type_options}</select>
                </div>
                <div class="filter-group">
                    <label>Framework</label>
                    <select id="f-framework" onchange="applyFilters()"><option value="">All</option>{framework_options}</select>
                </div>
                <div class="filter-group">
                    <label>Industry</label>
                    <select id="f-industry" onchange="applyFilters()"><option value="">All</option>{industry_options}</select>
                </div>
                <div class="filter-group">
                    <label>Role</label>
                    <select id="f-role" onchange="applyFilters()"><option value="">All</option>{role_options}</select>
                </div>
                <div class="filter-group">
                    <label>Date</label>
                    <select id="f-date" onchange="applyFilters()"><option value="">All</option>{date_options}</select>
                </div>
                <button class="btn-clear" onclick="clearFilters()">Clear All</button>
                <div class="filter-count">Showing <strong id="visible-count">{len(activities)}</strong> of {len(activities)}</div>
            </div>
        </div>

        <table class="activity-table" id="activity-table">
            <thead><tr>
                <th style="width:75px">Date</th>
                <th style="width:35px">Type</th>
                <th style="width:180px">Lead</th>
                <th>Content</th>
                <th style="width:80px">Status</th>
                <th style="width:200px">Events</th>
                <th style="width:50px">CRM</th>
            </tr></thead>
            <tbody>{activity_rows}</tbody>
        </table>
        <div class="no-results" id="no-results">No activities match your filters.</div>
    </div>

    <!-- TAB: Accounts -->
    <div id="tab-accounts" class="tab-content">
        <div class="section">
            <h2>Accounts — {accounts_count} unique domains &middot; {accounts_with_opens} with opens</h2>
            <p class="acct-hint">Click a row to expand and see all contacts we've emailed at that account.</p>
            <div class="acct-search">
                <input type="text" id="acct-search-input" placeholder="Search company, domain, or contact..." oninput="filterAccounts()">
                <span class="acct-count">Showing <strong id="acct-visible">{accounts_count}</strong> of {accounts_count}</span>
            </div>
            <table class="stat-table acct-table">
                <thead><tr>
                    <th>Company / Domain</th>
                    <th>Contacts</th>
                    <th>Emails</th>
                    <th>Opens</th>
                    <th>Bounces</th>
                    <th>Replies</th>
                    <th>WA Sent</th>
                    <th>WA Replies</th>
                    <th>Open Rate</th>
                    <th>Last Touch</th>
                </tr></thead>
                <tbody>{account_rows}</tbody>
            </table>
        </div>
    </div>

    <!-- TAB: Replies -->
    <div id="tab-replies" class="tab-content">
        <div class="section">
            <h2>Replies ({total_reply_count}) — newest first</h2>
            <p class="acct-hint">All email and WhatsApp replies detected. Dhiraj handles these personally.</p>
            <div class="rep-grid">{reply_rows}</div>
        </div>
    </div>

    <!-- TAB: Hot Leads -->
    <div id="tab-hot" class="tab-content">
        <div class="section">
            <h2>Leads Who Opened Emails <span class="hot-badge">HOT</span></h2>
            <table class="stat-table">
                <thead><tr><th>Name</th><th>Company</th><th>Role</th><th>Subject</th><th>Opened</th><th>CRM</th></tr></thead>
                <tbody>{hot_rows}</tbody>
            </table>
        </div>
    </div>

    <!-- TAB: Analytics -->
    <div id="tab-analytics" class="tab-content">
        <div class="analytics-grid">
            <div class="section">
                <h2>Performance by Framework</h2>
                <table class="stat-table">
                    <thead><tr><th>Framework</th><th>Sends</th><th>Opens</th><th>Bounces</th><th>Open Rate</th></tr></thead>
                    <tbody>{fw_rows}</tbody>
                </table>
            </div>
            <div class="section">
                <h2>Performance by Role</h2>
                <table class="stat-table">
                    <thead><tr><th>Role</th><th>Sends</th><th>Opens</th><th>Bounces</th><th>Open Rate</th></tr></thead>
                    <tbody>{role_rows}</tbody>
                </table>
            </div>
            <div class="section">
                <h2>Performance by Industry</h2>
                <table class="stat-table">
                    <thead><tr><th>Industry</th><th>Sends</th><th>Opens</th><th>Bounces</th><th>Open Rate</th></tr></thead>
                    <tbody>{ind_rows}</tbody>
                </table>
            </div>
        </div>
    </div>

</div>

<div class="modal-overlay" id="contact-modal" onclick="if(event.target===this)closeContactModal()">
    <div class="modal">
        <div class="modal-header">
            <div>
                <h3 id="modal-name"></h3>
                <div class="m-sub" id="modal-sub"></div>
            </div>
            <button class="modal-close" onclick="closeContactModal()">&times;</button>
        </div>
        <div id="modal-messages"></div>
    </div>
</div>

<script>
window.CONTACT_MESSAGES = __CONTACT_MESSAGES_JSON__;

function openContactModal(lid) {{
    const data = window.CONTACT_MESSAGES[lid];
    if (!data) return;
    document.getElementById('modal-name').textContent = data.lead_name || lid;
    const subParts = [];
    if (data.job_title) subParts.push(escapeHtml(data.job_title));
    if (data.company_name) subParts.push(escapeHtml(data.company_name));
    if (data.email_id) subParts.push(escapeHtml(data.email_id));
    subParts.push('<a href="' + data.crm_link + '" target="_blank">CRM &rarr;</a>');
    document.getElementById('modal-sub').innerHTML = subParts.join(' &middot; ');

    const container = document.getElementById('modal-messages');
    container.innerHTML = '';
    (data.messages || []).forEach(m => {{
        const div = document.createElement('div');
        div.className = 'msg-item';
        const ts = (m.timestamp || '').slice(0, 16).replace('T', ' ');
        const metaBits = [];
        if (m.framework) metaBits.push('<span>' + escapeHtml(m.framework.replace(/_/g, ' ')) + '</span>');
        if (m.variant) metaBits.push('<span>variant ' + escapeHtml(m.variant) + '</span>');
        if (m.recipient) metaBits.push('<span>to ' + escapeHtml(m.recipient) + '</span>');
        (m.events || []).forEach(e => {{
            metaBits.push('<span class="evt-' + e.name + '">' + e.name + ' ' + escapeHtml(e.ts) + '</span>');
        }});
        div.innerHTML =
            '<div class="msg-item-head">' +
                '<span class="m-type ' + m.type + '">' + m.type + '</span>' +
                '<span class="m-ts">' + escapeHtml(ts) + '</span>' +
            '</div>' +
            (m.subject ? '<div class="m-subject">' + escapeHtml(m.subject) + '</div>' : '') +
            '<div class="m-body">' + escapeHtml(m.body || '(no body recorded)') + '</div>' +
            '<div class="m-meta">' + metaBits.join('') + '</div>';
        container.appendChild(div);
    }});
    document.getElementById('contact-modal').classList.add('open');
}}

function closeContactModal() {{
    document.getElementById('contact-modal').classList.remove('open');
}}

function escapeHtml(s) {{
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}}

document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeContactModal();
}});

function showTab(name) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
}}

function toggleMeeting(card, ev) {{
    // Don't toggle when clicking links/buttons inside the card body
    if (ev && ev.target && ev.target.closest('.mt-body a')) return;
    card.classList.toggle('collapsed');
}}

function filterAccounts() {{
    const q = (document.getElementById('acct-search-input').value || '').toLowerCase().trim();
    const rows = document.querySelectorAll('.acct-table tbody .acct-row');
    let visible = 0;
    rows.forEach(row => {{
        const match = !q || (row.dataset.search || '').includes(q);
        row.classList.toggle('hidden', !match);
        const details = row.nextElementSibling;
        if (details && details.classList.contains('acct-details')) {{
            details.classList.toggle('hidden', !match);
        }}
        if (match) visible++;
    }});
    const el = document.getElementById('acct-visible');
    if (el) el.textContent = visible;
}}

function applyFilters() {{
    const search = document.getElementById('f-search').value.toLowerCase();
    const status = document.getElementById('f-status').value;
    const type = document.getElementById('f-type').value;
    const framework = document.getElementById('f-framework').value;
    const industry = document.getElementById('f-industry').value;
    const role = document.getElementById('f-role').value;
    const date = document.getElementById('f-date').value;

    const rows = document.querySelectorAll('#activity-table tbody .activity-row');
    let visible = 0;

    rows.forEach(row => {{
        const match =
            (!search || row.dataset.search.includes(search)) &&
            (!status || row.dataset.status === status) &&
            (!type || row.dataset.type === type) &&
            (!framework || row.dataset.framework === framework) &&
            (!industry || row.dataset.industry === industry) &&
            (!role || row.dataset.role === role) &&
            (!date || row.dataset.date === date);

        if (match) {{
            row.classList.remove('hidden');
            visible++;
        }} else {{
            row.classList.add('hidden');
        }}
    }});

    document.getElementById('visible-count').textContent = visible;
    document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}}

function clearFilters() {{
    document.getElementById('f-search').value = '';
    document.getElementById('f-status').value = '';
    document.getElementById('f-type').value = '';
    document.getElementById('f-framework').value = '';
    document.getElementById('f-industry').value = '';
    document.getElementById('f-role').value = '';
    document.getElementById('f-date').value = '';
    applyFilters();
}}

// Keyboard shortcut: Escape clears filters
document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') {{
        if (document.getElementById('meetings-modal').classList.contains('open')) {{
            closeMeetingsModal();
        }} else {{
            clearFilters();
        }}
    }}
}});

function openMeetingsModal() {{
    const modal = document.getElementById('meetings-modal');
    if (!modal) return;
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
}}
function closeMeetingsModal() {{
    const modal = document.getElementById('meetings-modal');
    if (!modal) return;
    modal.classList.remove('open');
    document.body.style.overflow = '';
}}
</script>

<!-- Meetings modal -->
<div id="meetings-modal" class="mt-modal" onclick="if(event.target===this)closeMeetingsModal()">
  <div class="mt-modal-inner">
    <div class="mt-modal-head">
      <h2>🎯 Meetings Booked <span class="mt-count">{meetings_count}</span></h2>
      <button class="mt-modal-close" onclick="closeMeetingsModal()">✕</button>
    </div>
    <div class="mt-modal-body">
      <div class="mt-grid">{meetings_cards_html}</div>
    </div>
  </div>
</div>
</body></html>'''

    html = html.replace("__CONTACT_MESSAGES_JSON__", contact_messages_json)

    with open('sdr_dashboard.html', 'w') as f:
        f.write(html)
    print(f"Dashboard generated: sdr_dashboard.html ({total_leads} leads, {total_actions} actions, {meta.get('total_opens', 0)} opens)")

    deploy_to_cloudflare('sdr_dashboard.html')


def deploy_to_cloudflare(filepath):
    """Deploy the dashboard HTML to Cloudflare Pages via wrangler CLI."""
    import subprocess, shutil, tempfile

    account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '5884239be2dfebf228b278dbb1c42e44')
    token = os.environ.get('CLOUDFLARE_API_TOKEN')
    project = os.environ.get('CLOUDFLARE_PAGES_PROJECT', 'agentic-sdr')

    # Cloudflare Pages serves index.html as the root, so copy the dashboard there
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(filepath, os.path.join(tmpdir, 'index.html'))
        env = os.environ.copy()
        env['CLOUDFLARE_ACCOUNT_ID'] = account_id
        env['CLOUDFLARE_API_TOKEN'] = token
        try:
            result = subprocess.run(
                ['npx', '--yes', 'wrangler@latest', 'pages', 'deploy', tmpdir,
                 f'--project-name={project}', '--commit-dirty=true'],
                env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                # Extract the deployment URL from output
                for line in result.stdout.splitlines():
                    if 'pages.dev' in line and 'Deployment complete' in line:
                        print(line.strip())
                        return
                print(f"Deployed to https://{project}.pages.dev")
            else:
                print(f"Cloudflare deploy failed: {result.stderr[:200]}")
        except Exception as e:
            print(f"Cloudflare deploy error: {str(e)[:200]}")


if __name__ == "__main__":
    generate_report()
