"""CRM API client for Lead operations."""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("CRM_URL", "https://your-crm-url.com")
API_KEY = os.getenv("CRM_API_KEY")
API_SECRET = os.getenv("CRM_API_SECRET")

HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json",
}


def get_leads(fields=None, filters=None, limit=20, offset=0, order_by="modified desc"):
    """Fetch leads from CRM.

    Args:
        fields: List of field names to return. None returns all fields.
        filters: List of filter tuples, e.g. [["status", "=", "Open"]]
        limit: Number of records to return (0 = all)
        offset: Starting record offset
        order_by: Sort order string
    """
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
    resp = requests.get(f"{BASE_URL}/api/resource/Lead/{lead_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["data"]


def update_lead(lead_id, data):
    """Update a lead. data is a dict of fields to update."""
    resp = requests.put(
        f"{BASE_URL}/api/resource/Lead/{lead_id}",
        headers=HEADERS,
        json=data,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def create_lead(data):
    """Create a new lead. data is a dict of fields."""
    resp = requests.post(
        f"{BASE_URL}/api/resource/Lead",
        headers=HEADERS,
        json=data,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def search_leads(query, limit=20):
    """Search leads using CRM search API."""
    params = {
        "doctype": "Lead",
        "txt": query,
        "page_length": limit,
    }
    resp = requests.get(f"{BASE_URL}/api/method/frappe.client.get_list", headers=HEADERS, params={
        "doctype": "Lead",
        "filters": json.dumps([["lead_name", "like", f"%{query}%"]]),
        "fields": json.dumps(["name", "lead_name", "email_id", "company_name", "status"]),
        "limit_page_length": limit,
    })
    resp.raise_for_status()
    return resp.json()["message"]


def get_lead_count(filters=None):
    """Get total count of leads matching filters."""
    params = {"doctype": "Lead"}
    if filters:
        params["filters"] = json.dumps(filters)
    resp = requests.get(f"{BASE_URL}/api/method/frappe.client.get_count", headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()["message"]


def add_note_to_lead(lead_id, note):
    """Add a note to a lead's notes field."""
    lead = get_lead(lead_id)
    existing_notes = lead.get("notes") or []
    existing_notes.append({"note": note})
    return update_lead(lead_id, {"notes": existing_notes})


# Quick test
if __name__ == "__main__":
    print(f"Total leads: {get_lead_count()}")
    leads = get_leads(
        fields=["name", "lead_name", "email_id", "company_name", "status"],
        limit=3,
    )
    for lead in leads:
        print(f"  {lead['name']}: {lead['lead_name']} ({lead.get('company_name', 'N/A')})")
