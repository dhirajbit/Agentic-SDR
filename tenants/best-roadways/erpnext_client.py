"""ERPNext (Frappe) API client for Best Roadways Lead operations.

Tenant-local. Reads ERPNEXT_URL / ERPNEXT_API_KEY / ERPNEXT_API_SECRET from this
tenant's .env (sitting next to this file). Best Roadways supplies these values.

API surface mirrors the kstars-sdr client (generic Frappe REST), so the SDR loop
can pull leads, update status, and append outreach notes to the CRM.
"""

import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_URL = (os.getenv("ERPNEXT_URL") or "").rstrip("/")
API_KEY = os.getenv("ERPNEXT_API_KEY")
API_SECRET = os.getenv("ERPNEXT_API_SECRET")

HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json",
}


def _require_config():
    if not (BASE_URL and API_KEY and API_SECRET):
        raise RuntimeError(
            "ERPNext not configured. Set ERPNEXT_URL, ERPNEXT_API_KEY and "
            "ERPNEXT_API_SECRET in tenants/best-roadways/.env"
        )


def get_leads(fields=None, filters=None, limit=20, offset=0, order_by="modified desc"):
    """Fetch leads from ERPNext.

    Args:
        fields: List of field names to return. None returns all fields.
        filters: List of filter tuples, e.g. [["status", "=", "Open"]]
        limit: Number of records (0 = all)
        offset: Starting record offset
        order_by: Sort order string
    """
    _require_config()
    params = {
        "limit_page_length": limit,
        "limit_start": offset,
        "order_by": order_by,
    }
    if fields:
        params["fields"] = json.dumps(fields)
    if filters:
        params["filters"] = json.dumps(filters)

    resp = requests.get(f"{BASE_URL}/api/resource/Lead", headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()["data"]


def get_lead(lead_id):
    """Fetch a single lead by ID."""
    _require_config()
    resp = requests.get(f"{BASE_URL}/api/resource/Lead/{lead_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["data"]


def update_lead(lead_id, data):
    """Update a lead. data is a dict of fields to update.

    Example: update_lead("CRM-LEAD-2026-00002", {"status": "Open"})
    """
    _require_config()
    resp = requests.put(
        f"{BASE_URL}/api/resource/Lead/{lead_id}", headers=HEADERS, json=data
    )
    resp.raise_for_status()
    return resp.json()["data"]


def create_lead(data):
    """Create a new lead. data is a dict of fields."""
    _require_config()
    resp = requests.post(f"{BASE_URL}/api/resource/Lead", headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()["data"]


def search_leads(query, limit=20):
    """Search leads by lead_name substring."""
    _require_config()
    resp = requests.get(
        f"{BASE_URL}/api/method/frappe.client.get_list",
        headers=HEADERS,
        params={
            "doctype": "Lead",
            "filters": json.dumps([["lead_name", "like", f"%{query}%"]]),
            "fields": json.dumps(
                ["name", "lead_name", "email_id", "company_name", "status"]
            ),
            "limit_page_length": limit,
        },
    )
    resp.raise_for_status()
    return resp.json()["message"]


def get_lead_count(filters=None):
    """Count leads matching filters."""
    _require_config()
    params = {"doctype": "Lead"}
    if filters:
        params["filters"] = json.dumps(filters)
    resp = requests.get(
        f"{BASE_URL}/api/method/frappe.client.get_count", headers=HEADERS, params=params
    )
    resp.raise_for_status()
    return resp.json()["message"]


def add_note_to_lead(lead_id, note):
    """Append an outreach note to a lead's notes field (the CRM audit trail)."""
    _require_config()
    lead = get_lead(lead_id)
    existing_notes = lead.get("notes") or []
    existing_notes.append({"note": note})
    return update_lead(lead_id, {"notes": existing_notes})


if __name__ == "__main__":
    print(f"Total leads: {get_lead_count()}")
