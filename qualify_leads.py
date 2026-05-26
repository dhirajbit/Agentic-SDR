"""Generic qualifier for leads based on customizable rules.

Three buckets:
- QUALIFIED   : clear match (target brand, target vertical, or size/revenue threshold)
- DISQUALIFIED: clear negative patterns (small, wrong industry)
- UNKNOWN    : needs web research
"""
import json
import re
import os
from collections import defaultdict, Counter

def load_json_if_exists(filepath, default):
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return default

leads = load_json_if_exists("leads_data.json", [])
tracker = load_json_if_exists("outreach_tracker.json", {})
blocked = set(load_json_if_exists("blocked_leads.json", []))

# Load qualification rules, default to template if not exist
rules_file = "qualification_rules.json"
if not os.path.exists(rules_file):
    rules_file = "qualification_rules_template.json"
    
rules = load_json_if_exists(rules_file, {})

TARGET_BRANDS = rules.get("target_brands", [])
TARGET_VERTICALS = rules.get("target_verticals", [])
DISQUALIFY_PATTERNS = rules.get("disqualify_patterns", [])
QUALIFY_REVENUE_MIN = rules.get("qualify_revenue_min", 100000000)
QUALIFY_EMPLOYEES = set(rules.get("qualify_employee_tiers", ["501-1000", "1000-5000", "5000-10000", "10000+"]))
DISQUALIFY_EMPLOYEES = set(rules.get("disqualify_employee_tiers", ["1-10"]))

DISQUALIFY_RE = re.compile("|".join(DISQUALIFY_PATTERNS), re.I) if DISQUALIFY_PATTERNS else None

touched = set(tracker.get("leads", {}).keys())

candidates = [
    l for l in leads
    if (l.get("email_id") or "").strip()
    and l.get("name") not in touched
    and l.get("name") not in blocked
]

def classify(lead):
    company = (lead.get("company_name") or "").lower().strip()
    industry = (lead.get("industry") or "").lower()
    revenue = lead.get("annual_revenue") or 0
    employees = lead.get("no_of_employees") or ""

    if not company:
        return ("UNKNOWN", "no_company_name")

    if revenue and revenue >= QUALIFY_REVENUE_MIN:
        return ("QUALIFIED", f"revenue_min_met")
    if employees in QUALIFY_EMPLOYEES:
        return ("QUALIFIED", f"employees={employees}")

    for brand in TARGET_BRANDS:
        pat = r"\b" + re.escape(brand.strip()) + r"\b"
        if re.search(pat, company):
            return ("QUALIFIED", f"brand:{brand.strip()}")

    for vert in TARGET_VERTICALS:
        pat = r"\b" + re.escape(vert.strip())
        if re.search(pat, company) or (industry and re.search(pat, industry)):
            return ("QUALIFIED", f"vertical:{vert.strip()}")

    is_dq_pattern = bool(DISQUALIFY_RE.search(company)) if DISQUALIFY_RE else False
    is_tiny = employees in DISQUALIFY_EMPLOYEES

    if is_dq_pattern and is_tiny:
        return ("DISQUALIFIED", "dq_pattern+small_size")

    return ("UNKNOWN", "needs_research")


buckets = defaultdict(list)
for l in candidates:
    verdict, reason = classify(l)
    buckets[verdict].append((l, reason))

for k in ("QUALIFIED", "DISQUALIFIED", "UNKNOWN"):
    print(f"{k}: {len(buckets[k])}")

print("\n--- QUALIFIED reasons (top 15) ---")
ctr = Counter(r for _,r in buckets["QUALIFIED"])
for r,c in ctr.most_common(15):
    print(f"  {c:4d}  {r}")

print("\n--- DISQUALIFIED reasons ---")
ctr = Counter(r for _,r in buckets["DISQUALIFIED"])
for r,c in ctr.most_common():
    print(f"  {c:4d}  {r}")

print("\n--- UNKNOWN reasons ---")
ctr = Counter(r for _,r in buckets["UNKNOWN"])
for r,c in ctr.most_common():
    print(f"  {c:4d}  {r}")

out = {
    "qualified_ids": [l.get("name") for l,_ in buckets["QUALIFIED"]],
    "disqualified_ids": [l.get("name") for l,_ in buckets["DISQUALIFIED"]],
    "unknown": [
        {
            "id": l.get("name"),
            "company": l.get("company_name"),
            "email": l.get("email_id"),
            "website": l.get("website"),
            "title": l.get("job_title"),
            "industry": l.get("industry"),
            "employees": l.get("no_of_employees"),
            "revenue": l.get("annual_revenue"),
            "city": l.get("city"),
        }
        for l,_ in buckets["UNKNOWN"]
    ],
}
with open("/tmp/qualify_buckets.json", "w") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved /tmp/qualify_buckets.json")
