"""Sync all leads from CRM to local JSON/CSV files."""

import json
import csv
from crm_client import get_leads

FIELDS = [
    "name", "lead_name", "first_name", "middle_name", "last_name",
    "email_id", "mobile_no", "phone", "company_name", "job_title",
    "source", "status", "qualification_status", "city", "state", "country",
    "annual_revenue", "no_of_employees", "website",
    "contact1_linkedin", "company_linkedin",
    "lead_owner", "creation", "modified",
]


def sync():
    print("Fetching all leads from CRM...")
    leads = get_leads(fields=FIELDS, limit=0)
    print(f"Fetched {len(leads)} leads")

    with open("leads_data.json", "w") as f:
        json.dump(leads, f, indent=2)
    print("Saved leads_data.json")

    if leads:
        with open("leads_data.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(leads)
        print("Saved leads_data.csv")

    # Print summary
    statuses = {}
    for lead in leads:
        s = lead.get("status") or "Unknown"
        statuses[s] = statuses.get(s, 0) + 1
    print("\nStatus breakdown:")
    for k, v in sorted(statuses.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    sync()
