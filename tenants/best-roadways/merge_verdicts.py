"""Build the prioritised qualified_leads.json for the Best Roadways SDR loop.

Reads enriched_leads.json + qualify_buckets.json (+ blocked_leads.json) and emits
a priority-sorted queue. Scoring ported from kstars-sdr: seniority, personal-email
domain, hub city, lead source, company size, prior engagement.

    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/merge_verdicts.py
"""

import json
from collections import Counter
from pathlib import Path

TENANT_DIR = Path(__file__).resolve().parent
LEADS = TENANT_DIR / "enriched_leads.json"
BUCKETS = TENANT_DIR / "qualify_buckets.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
OUT = TENANT_DIR / "qualified_leads.json"

PERSONAL_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "hotmail.com",
    "outlook.com", "live.com", "rediffmail.com", "icloud.com", "me.com",
    "ymail.com", "aol.com", "protonmail.com", "proton.me", "zoho.com",
}
HUB_CITIES = {
    "mumbai", "pune", "bangalore", "bengaluru", "new delhi", "delhi",
    "gurgaon", "gurugram", "noida", "hyderabad", "ahmedabad", "chennai",
}


def _load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def score(lead):
    s = 0
    title = (lead.get("title") or "").lower()
    if any(k in title for k in ("ceo", "cio", "cto", "cfo", "coo", "chief", "managing director", "founder", "president", "vp", "vice president")):
        s += 10
    elif any(k in title for k in ("head", "director", "general manager", "agm", "dgm", "senior manager")):
        s += 6
    elif any(k in title for k in ("manager", "lead", "incharge", "in-charge")):
        s += 3

    dom = (lead.get("domain") or "").lower()
    lead["personal_email"] = dom in PERSONAL_EMAIL_DOMAINS
    if lead["personal_email"]:
        s += 5

    if (lead.get("city") or "").lower() in HUB_CITIES:
        s += 3

    s += {"Reference": 5, "Exhibition": 3, "Partner": 3, "Cold Calling": 2, "Other": 1}.get(lead.get("source") or "", 0)
    s += {"10001+": 6, "5001-10000": 5, "1001-5000": 4, "501-1000": 3, "201-500": 2, "51-200": 1}.get(lead.get("employees") or "", 0)
    if (lead.get("status") or "") == "Open":
        s += 2
    return s


def main():
    leads = _load(LEADS, [])
    buckets = _load(BUCKETS, {"qualified": []})
    blocked = set(_load(BLOCKED, []))

    by_id = {l.get("name"): l for l in leads}
    qualified_ids = {b["id"] for b in buckets.get("qualified", []) if b.get("id")}

    queue = []
    for lid in qualified_ids:
        l = by_id.get(lid)
        if not l:
            continue
        em = (l.get("email_id") or "").strip().lower()
        if em and em in blocked:
            continue
        dom = em.split("@", 1)[1] if "@" in em else ""
        item = {
            "id": lid,
            "lead_name": l.get("lead_name"),
            "company": l.get("company_name"),
            "title": l.get("job_title"),
            "email": em,
            "domain": dom,
            "mobile": l.get("mobile_no"),
            "city": l.get("city"),
            "state": l.get("state"),
            "source": l.get("source"),
            "employees": l.get("no_of_employees"),
            "revenue": l.get("annual_revenue"),
            "status": l.get("status"),
            "website": l.get("website"),
            "linkedin": l.get("contact1_linkedin") or l.get("company_linkedin"),
            # Email leads first; mobile-only leads still queue (WhatsApp-first cadence).
            "channel": "email" if em else ("whatsapp" if (l.get("mobile_no") or "").strip() else "none"),
        }
        item["priority_score"] = score(item)
        queue.append(item)

    queue.sort(key=lambda x: -x["priority_score"])
    OUT.write_text(json.dumps(queue, indent=2))

    print(f"Wrote {OUT} ({len(queue)} leads)")
    print(f"  by channel: {dict(Counter(q['channel'] for q in queue))}")
    print(f"  personal-email leads: {sum(1 for q in queue if q.get('personal_email'))}")
    for q in queue[:15]:
        print(f"  {q['priority_score']:3d}  {(q.get('lead_name') or '')[:24]:24s}  {(q.get('company') or '')[:30]:30s}  {q['channel']}")


if __name__ == "__main__":
    main()
