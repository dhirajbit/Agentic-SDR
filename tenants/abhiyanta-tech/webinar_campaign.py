"""Build the SAP PI/PO-sunset → Integration Suite multi-tenant webinar campaign.

Audience: the T1-India top-100 Zoho master (_t1_india_zoho_payloads.json, 119
not-contacted IT-decision-maker leads), excluding anyone already emailed.

Generates a 3-TOUCH sequence per lead mapped to 3 webinar sessions:
  Touch 1 -> Webinar #1 "Main launch"  (invite, anchored on Oct-2025 Blueprints)
  Touch 2 -> Webinar #2 "By popular demand / additional session"
  Touch 3 -> Webinar #3 "Final session" (last chance + live Q&A reason)

Efficient: drafts ~ (3 touches x N industry buckets) Gemini TEMPLATES with
{first_name}/{company}/{webinar_date} placeholders, then mail-merges per lead.
Writes a SCHEDULED QUEUE into outreach_tracker.json (status='scheduled',
scheduled_for + webinar_session in events). Re-running re-stamps cleanly.

Dates are placeholders until confirmed — pass real ones via WEBINAR_DATES env
(JSON list of 3 ISO dates) or edit SESSIONS below; re-run to re-stamp.

    AGENTIC_SDR_TENANT=abhiyanta-tech python tenants/abhiyanta-tech/webinar_campaign.py
"""

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

TENANT_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(TENANT_DIR))
import gemini_client

ZOHO = TENANT_DIR / "_t1_india_zoho_payloads.json"
TRACKER = TENANT_DIR / "outreach_tracker.json"
DRAFTS_OUT = TENANT_DIR / "email_drafts.json"
CONFIG = TENANT_DIR / "company_config.json"
PLAYBOOK = TENANT_DIR / "strategy_playbook.md"

CAMPAIGN = "webinar_pipo_sunset_v1"
SENDER = os.getenv("WEBINAR_SENDER", "Saurabh")

# Placeholder session dates (confirm + re-run). Each touch is sent ~6 days before.
_default_dates = ["2026-07-01", "2026-07-15", "2026-07-29"]
SESSION_DATES = json.loads(os.getenv("WEBINAR_DATES", json.dumps(_default_dates)))
SESSIONS = [
    {"n": 1, "label": "Main launch", "date": SESSION_DATES[0]},
    {"n": 2, "label": "Additional session (by popular demand)", "date": SESSION_DATES[1]},
    {"n": 3, "label": "Final session", "date": SESSION_DATES[2]},
]
LEAD_TIME_DAYS = 6  # send each touch this many days before its session

WEBINAR_AGENDA = (
    "What the SAP PI/PO sunset means for your business; common migration "
    "challenges & risks; a migration approach & roadmap; a walkthrough of our "
    "process and accelerators; and a live Q&A."
)
COVERING = (
    "what happens if you delay, the common roadblocks, how long it takes, what "
    "breaks during migration, what can be reused, and realistic cost/effort."
)

INDUSTRY_BUCKETS = {
    "chemical": "chemical", "chemicals": "chemical",
    "mills and mining": "mining", "mining": "mining",
    "pharma": "pharma", "life sciences": "pharma", "pharmaceutical": "pharma",
    "automotive": "automotive", "auto": "automotive",
    "industrial": "industrial", "manufacturing": "industrial",
    "fmcg": "fmcg", "consumer": "fmcg",
}
BUCKET_HOOK = {
    "chemical": "process/chemical plants running integrated SAP estates",
    "mining": "mills & mining operations with plant-to-ERP integration",
    "pharma": "pharma/life-sciences estates where validated, audit-traceable integration matters",
    "automotive": "auto manufacturers with supplier/EDI-heavy integration",
    "industrial": "industrial manufacturers with multi-plant SAP integration",
    "fmcg": "FMCG/consumer estates with high-volume order + distribution integration",
    "other": "enterprise SAP estates",
}


def bucket_of(industry: str) -> str:
    s = (industry or "").lower()
    for key, b in INDUSTRY_BUCKETS.items():
        if key in s:
            return b
    return "other"


def _load(p, d):
    return json.load(open(p)) if p.exists() else d


def _system(config):
    pb = PLAYBOOK.read_text() if PLAYBOOK.exists() else ""
    return (
        f"You are {SENDER}, an SDR for {config.get('company_name')} "
        f"({config.get('product_name')}). Tone: casual, peer-to-peer, slightly "
        f"unsure ('not sure if this is on your radar'). No buzzwords, no 'hope "
        f"this finds you well'. You're inviting an SAP IT leader to a webinar. "
        f"Keep bodies 60-85 words. End with the sender name '{SENDER}'. "
        f"Use these merge placeholders literally: {{first_name}}, {{company}}, "
        f"{{webinar_date}}. CTA is soft reply-to-register (no links). "
        f"Playbook for context:\n{pb}"
    )


def _touch_prompt(touch: int, bucket: str) -> str:
    hook = BUCKET_HOOK[bucket]
    base = (
        "Anchor on: SAP's Oct-2025 'Blueprints for Success' guidance now treats "
        "single-tenant Integration Suite as suitable only for simpler scenarios, "
        "and PI/PO is being sunset. Audience: " + hook + ". "
        f"Webinar agenda: {WEBINAR_AGENDA} It covers {COVERING} "
        "Return EXACTLY two lines:\nSUBJECT: <short, lowercase-ish>\nBODY: <60-85 words with {first_name}, {company}, {webinar_date}>"
    )
    if touch == 1:
        intro = ("Write the FIRST invite to our live webinar (main launch) on {webinar_date}. "
                 "Frame it as a heads-up + invite. ")
    elif touch == 2:
        intro = ("Write a SECOND-touch invite: the first session filled up, so we're running an "
                 "additional session by popular demand on {webinar_date}. Lean on the practical "
                 "questions (what breaks, how long, what's reusable, cost/effort). ")
    else:
        intro = ("Write a THIRD/FINAL-touch invite: this is the FINAL session on {webinar_date}. "
                 "Last chance; emphasise the live Q&A — bring your specific PI/PO migration "
                 "questions to ask our architects live. ")
    return intro + base


def _parse(text: str):
    subject, body = "", text
    if "SUBJECT:" in text:
        after = text.split("SUBJECT:", 1)[1]
        subject = after.split("\n", 1)[0].strip()
    if "BODY:" in text:
        body = text.split("BODY:", 1)[1].strip()
    return subject or "a quick SAP integration heads-up", body.strip()


def build_templates(config):
    system = _system(config)
    templates = {}
    buckets = sorted(set(BUCKET_HOOK))
    for touch in (1, 2, 3):
        for b in buckets:
            try:
                txt = gemini_client.draft(_touch_prompt(touch, b), system=system, temperature=0.7)
                templates[(touch, b)] = _parse(txt)
            except Exception as exc:  # noqa: BLE001
                templates[(touch, b)] = (
                    f"SAP Integration Suite session for {{company}}",
                    f"Hi {{first_name}}, not sure if the SAP PI/PO sunset is on your radar at "
                    f"{{company}} — we're running a live session on {{webinar_date}} on the move to "
                    f"a multi-tenant Integration Suite. Worth a reply for the invite?\n{SENDER}",
                )
                print(f"  template ({touch},{b}) fell back: {exc}")
    return templates


def _fill(tpl, first_name, company, webinar_date):
    s, b = tpl
    repl = {"{first_name}": first_name or "there", "{company}": company or "your team",
            "{webinar_date}": webinar_date}
    for k, v in repl.items():
        s = s.replace(k, v); b = b.replace(k, v)
    return s, b


def main():
    config = _load(CONFIG, {})
    leads = _load(ZOHO, [])
    tracker = _load(TRACKER, {"actions": []})
    tracker.setdefault("actions", [])

    # Exclude anyone already emailed (by company), and any prior webinar queue.
    sent_co = {(a.get("company") or "").strip().lower()
               for a in tracker["actions"] if a.get("status") in ("sent", "completed")}
    tracker["actions"] = [a for a in tracker["actions"] if a.get("campaign") != CAMPAIGN]

    audience = [l for l in leads if l.get("Email")
                and (l.get("Company") or "").strip().lower() not in sent_co]
    print(f"audience: {len(audience)} contactable leads (of {len(leads)})")

    print("drafting industry templates via Gemini...")
    templates = build_templates(config)
    print(f"  {len(templates)} templates ready")

    now = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    queued = 0
    drafts_export = []
    for lead in audience:
        first = lead.get("First_Name") or "there"
        company = lead.get("Company")
        email = lead.get("Email")
        bucket = bucket_of(lead.get("Industry"))
        for s in SESSIONS:
            wdate = datetime.strptime(s["date"], "%Y-%m-%d")
            sched = (wdate - timedelta(days=LEAD_TIME_DAYS)).strftime("%Y-%m-%d")
            wdate_h = wdate.strftime("%A, %d %b %Y")
            subj, body = _fill(templates[(s["n"], bucket)], first, company, wdate_h)
            action = {
                "at": f"{sched} 11:00 IST",          # occurred_at = scheduled send time
                "created_at": now,
                "scheduled_for": sched,
                "lead_row_id": f"{CAMPAIGN}:{email}:{s['n']}",
                "company": company,
                "contact": f"{first} {lead.get('Last_Name','')}".strip(),
                "email": email,
                "channel": "email",
                "framework": f"Webinar T{s['n']}",
                "subject": subj,
                "body": body,
                "status": "scheduled",
                "dry_run": True,
                "campaign": CAMPAIGN,
                "events": {"scheduled": True, "webinar_session": s["n"],
                           "webinar_label": s["label"], "webinar_date": s["date"],
                           "industry_bucket": bucket},
            }
            tracker["actions"].append(action)
            drafts_export.append(action)
            queued += 1

    json.dump(tracker, open(TRACKER, "w"), indent=2, ensure_ascii=False)
    json.dump({"campaign": CAMPAIGN, "generated_at": now, "sessions": SESSIONS,
               "drafts": drafts_export}, open(DRAFTS_OUT.with_name("webinar_drafts.json"), "w"),
              indent=2, ensure_ascii=False)
    print(f"queued {queued} scheduled drafts ({len(audience)} leads x 3 touches) -> tracker")
    # quick schedule summary
    from collections import Counter
    by_sched = Counter(a["scheduled_for"] for a in drafts_export)
    for d in sorted(by_sched):
        print(f"  {d}: {by_sched[d]} sends")


if __name__ == "__main__":
    main()
