"""Sync leads for Best Roadways from ERPNext and/or a local leads.csv.

No Apollo, no credit gate. Sources, in order:
  1. ERPNext (if ERPNEXT_* configured in .env) via erpnext_client.get_leads()
  2. leads.csv in this tenant folder (operator-supplied account list)

Both are merged and de-duplicated (by `name`, else by email_id) into
enriched_leads.json — the input to qualify_leads.py.

    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/sync_leads.py
"""

import csv
import json
import os
from pathlib import Path

from dotenv import load_dotenv

TENANT_DIR = Path(__file__).resolve().parent
load_dotenv(TENANT_DIR / ".env")

LEADS_CSV = TENANT_DIR / "leads.csv"
OUTPUT = TENANT_DIR / "enriched_leads.json"

FIELDS = [
    "name", "lead_name", "first_name", "middle_name", "last_name",
    "email_id", "mobile_no", "phone", "company_name", "job_title",
    "source", "status", "qualification_status", "city", "state", "country",
    "annual_revenue", "no_of_employees", "website",
    "contact1_linkedin", "company_linkedin",
    "lead_owner", "creation", "modified",
]


def _from_erpnext():
    if not (os.getenv("ERPNEXT_URL") and os.getenv("ERPNEXT_API_KEY")):
        print("ERPNext not configured — skipping ERPNext sync.")
        return []
    try:
        import erpnext_client  # tenant-local
    except Exception as e:  # pragma: no cover
        print(f"Could not import erpnext_client: {e}")
        return []
    print("Fetching leads from ERPNext...")
    leads = erpnext_client.get_leads(fields=FIELDS, limit=0)
    print(f"  ERPNext returned {len(leads)} leads")
    return leads


def _from_csv():
    if not LEADS_CSV.exists():
        print("No leads.csv found — skipping CSV import.")
        return []
    rows = []
    with open(LEADS_CSV, newline="") as f:
        for row in csv.DictReader(f):
            first = (row.get("name") or "").strip()
            # Skip the template comment / example rows.
            if not first or first.startswith("#") or first == "EXAMPLE-0001":
                continue
            rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
    print(f"  leads.csv returned {len(rows)} leads")
    return rows


def _key(lead):
    return (lead.get("name") or "").strip() or (lead.get("email_id") or "").strip().lower()


def sync():
    merged = {}
    for lead in _from_erpnext() + _from_csv():
        k = _key(lead)
        if not k:
            continue
        # ERPNext first, CSV fills gaps without clobbering populated ERPNext fields.
        if k in merged:
            for field, val in lead.items():
                if val and not merged[k].get(field):
                    merged[k][field] = val
        else:
            merged[k] = lead

    leads = list(merged.values())
    OUTPUT.write_text(json.dumps(leads, indent=2))
    print(f"\nWrote {OUTPUT} ({len(leads)} unique leads)")
    with_email = sum(1 for l in leads if (l.get("email_id") or "").strip())
    with_mobile = sum(1 for l in leads if (l.get("mobile_no") or "").strip())
    print(f"  with email_id : {with_email}")
    print(f"  with mobile_no: {with_mobile}")


if __name__ == "__main__":
    sync()
