"""Merge keyword-pass + 3 research-agent outputs into a final qualified queue."""
import json
from collections import defaultdict, Counter

with open("leads_data.json") as f:
    leads = json.load(f)
with open("outreach_tracker.json") as f:
    tracker = json.load(f)
with open("blocked_leads.json") as f:
    blocked = set(json.load(f))
with open("/tmp/qualify_buckets.json") as f:
    kw = json.load(f)

# Load research outputs
research_verdicts = {}  # company_name -> (verdict, reason)
for i in (1, 2, 3):
    try:
        with open(f"/tmp/research_output_{i}.json") as f:
            for item in json.load(f):
                co = (item.get("company") or "").strip()
                if co:
                    research_verdicts[co] = (item["verdict"], item.get("reason", ""))
    except FileNotFoundError:
        pass

print(f"Research verdicts: {len(research_verdicts)} unique companies classified")

touched = set(tracker.get("leads", {}).keys())

qualified_ids = set(kw["qualified_ids"])
disqualified_ids = set(kw["disqualified_ids"])

# Apply research verdicts to the UNKNOWN leads
unmatched = []
for lead_info in kw["unknown"]:
    co = (lead_info.get("company") or "").strip()
    verdict, reason = research_verdicts.get(co, (None, None))
    if verdict == "QUALIFIED":
        qualified_ids.add(lead_info["id"])
    elif verdict == "DISQUALIFIED":
        disqualified_ids.add(lead_info["id"])
    else:
        unmatched.append(lead_info)

print(f"QUALIFIED leads (final): {len(qualified_ids)}")
print(f"DISQUALIFIED leads (final): {len(disqualified_ids)}")
print(f"Still unmatched (no verdict): {len(unmatched)}")

# Build lookup
lead_by_id = {l.get("name"): l for l in leads}

# Build prioritized queue with metadata
queue = []
for lid in qualified_ids:
    l = lead_by_id.get(lid)
    if not l:
        continue
    em = (l.get("email_id") or "").strip().lower()
    dom = em.split("@", 1)[1] if "@" in em else ""
    queue.append({
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
        "linkedin": l.get("contact1_linkedin") or l.get("company_linkedin"),
    })

PERSONAL_EMAIL_DOMAINS = {
    "gmail.com","yahoo.com","yahoo.co.in","yahoo.in","hotmail.com","outlook.com",
    "live.com","rediffmail.com","icloud.com","me.com","ymail.com","aol.com",
    "protonmail.com","proton.me","zoho.com","fastmail.com","mail.com",
}

# Prioritization: score leads
def score(lead):
    s = 0
    title = (lead.get("title") or "").lower()
    if any(k in title for k in ("ceo","cio","cto","cfo","coo","chief","managing director","founder","president","vp","vice president","svp","evp")):
        s += 10
    elif any(k in title for k in ("head","director","general manager","gm ","agm","dgm","sr manager","senior manager")):
        s += 6
    elif any(k in title for k in ("manager","lead")):
        s += 3
    # Personal email domains open at higher rates → strong priority boost
    dom = (lead.get("domain") or "").lower()
    if dom in PERSONAL_EMAIL_DOMAINS:
        s += 5
        lead["personal_email"] = True
    else:
        lead["personal_email"] = False
    # Prefer major hubs (easier to close, relevant hub)
    city = (lead.get("city") or "").lower()
    if city in ("mumbai","pune","bangalore","bengaluru","new delhi","delhi","gurgaon","gurugram","noida","hyderabad", "new york", "london", "san francisco"):
        s += 3
    # Reference source beats Exhibition beats Cold Calling beats Other
    src = (lead.get("source") or "")
    s += {"Reference":5,"Exhibition":3,"Partner":3,"Cold Calling":2,"Other":1}.get(src, 0)
    # Bigger company = higher score
    emp = lead.get("employees") or ""
    s += {"10000+":6,"5000-10000":5,"1000-5000":4,"501-1000":3,"201-500":2,"51-200":1}.get(emp, 0)
    # Already "Open" status (engaged previously)
    if (lead.get("status") or "") == "Open":
        s += 2
    return s

for q in queue:
    q["priority_score"] = score(q)
queue.sort(key=lambda x: -x["priority_score"])

# Write outputs
with open("/tmp/qualified_queue.json", "w") as f:
    json.dump(queue, f, indent=2)

# Summary stats
print(f"\n=== PRIORITIZED QUEUE ({len(queue)}) ===")
ct = Counter(q["source"] for q in queue)
print(f"By source: {dict(ct)}")
ct = Counter(q.get("status") for q in queue)
print(f"By status: {dict(ct)}")
ct = Counter(q.get("employees") or "(none)" for q in queue)
print(f"By employees: {dict(ct.most_common())}")

# Top-20 by priority
print("\nTop 20 by priority score:")
for q in queue[:20]:
    pe = "✉ personal" if q.get("personal_email") else ""
    print(f"  {q['priority_score']:3d}  {q['lead_name'][:25]:25s}  {(q['title'] or '')[:28]:28s}  {(q['company'] or '')[:35]:35s}  {q['source']:12s}  {pe}")

# Personal email breakdown
personal_count = sum(1 for q in queue if q.get("personal_email"))
print(f"\nPersonal-email leads in queue: {personal_count} of {len(queue)}")

# Save a simpler CSV-style for easy scanning
with open("/tmp/qualified_queue.csv", "w") as f:
    f.write("priority,lead_id,name,title,company,email,source,city,employees,status\n")
    for q in queue:
        f.write(f"{q['priority_score']},{q['id']},\"{q['lead_name']}\",\"{q.get('title') or ''}\",\"{q['company']}\",{q['email']},{q['source']},{q.get('city') or ''},{q.get('employees') or ''},{q.get('status') or ''}\n")

print("\nSaved /tmp/qualified_queue.json and /tmp/qualified_queue.csv")
