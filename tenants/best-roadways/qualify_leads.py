"""Qualify Best Roadways leads against the logistics ICP.

Reads enriched_leads.json + qualification_rules.json, classifies each lead as
QUALIFIED / DISQUALIFIED / UNKNOWN, and writes qualify_buckets.json.
merge_verdicts.py then turns QUALIFIED into a prioritised qualified_leads.json.

    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/qualify_leads.py
"""

import json
import re
from pathlib import Path

TENANT_DIR = Path(__file__).resolve().parent
LEADS = TENANT_DIR / "enriched_leads.json"
RULES = TENANT_DIR / "qualification_rules.json"
OUT = TENANT_DIR / "qualify_buckets.json"


def _load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def classify(lead, rules):
    # Disqualify patterns test the COMPANY identity only (name + website) — never the
    # job title, so a target buyer like "Head of Logistics" isn't mistaken for a
    # logistics/transport COMPANY.
    company_hay = " ".join(
        str(lead.get(f) or "") for f in ("company_name", "website")
    ).lower()
    hay = " ".join(
        str(lead.get(f) or "")
        for f in ("company_name", "job_title", "website", "lead_name")
    ).lower()

    # Disqualify competitors (transporters / 3PLs / forwarders / courier).
    for pat in rules.get("disqualify_patterns", []):
        if re.search(pat, company_hay, re.IGNORECASE):
            return "DISQUALIFIED", f"matches competitor pattern: {pat}"

    emp = (lead.get("no_of_employees") or "").strip()
    if emp in rules.get("disqualify_employee_tiers", []):
        return "DISQUALIFIED", f"employee tier too small: {emp}"

    verticals = rules.get("target_verticals", [])
    keywords = rules.get("target_keywords", [])
    roles = rules.get("target_roles", [])

    if any(v in hay for v in verticals):
        return "QUALIFIED", "target vertical match"
    if emp in rules.get("qualify_employee_tiers", []):
        return "QUALIFIED", f"qualifying size tier: {emp}"
    title = (lead.get("job_title") or "").lower()
    if any(r in title for r in roles) and any(k in hay for k in keywords):
        return "QUALIFIED", "target role + logistics keyword"

    return "UNKNOWN", "no vertical/size/role signal — needs research"


def main():
    leads = _load(LEADS, [])
    rules = _load(RULES, {})
    buckets = {"qualified": [], "disqualified": [], "unknown": []}

    for l in leads:
        verdict, reason = classify(l, rules)
        rec = {
            "id": l.get("name"),
            "company": l.get("company_name"),
            "title": l.get("job_title"),
            "reason": reason,
        }
        buckets[verdict.lower()].append(rec)

    OUT.write_text(json.dumps(buckets, indent=2))
    print(f"Wrote {OUT}")
    print(f"  QUALIFIED   : {len(buckets['qualified'])}")
    print(f"  DISQUALIFIED: {len(buckets['disqualified'])}")
    print(f"  UNKNOWN     : {len(buckets['unknown'])} (research these, then re-run merge)")


if __name__ == "__main__":
    main()
