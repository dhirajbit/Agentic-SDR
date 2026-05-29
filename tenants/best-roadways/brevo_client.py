"""Brevo (Sendinblue) transactional email client for Best Roadways.

Tenant-local. Reads BREVO_API_KEY / BREVO_SENDER_NAME / BREVO_SENDER_EMAIL from
this tenant's .env. Sends outreach email and pulls delivery / open / click /
bounce events for the Observer loop.

Mirrors the kstars-sdr Brevo flow (which lived inline) as a reusable client:
    send_email(...) -> POST https://api.brevo.com/v3/smtp/email
    get_events(...) -> GET  https://api.brevo.com/v3/smtp/statistics/events
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("BREVO_API_KEY")
SENDER_NAME = os.getenv("BREVO_SENDER_NAME")
SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
BASE = "https://api.brevo.com/v3"


def _headers():
    if not API_KEY:
        raise RuntimeError(
            "Brevo not configured. Set BREVO_API_KEY in tenants/best-roadways/.env"
        )
    return {"api-key": API_KEY, "Content-Type": "application/json", "Accept": "application/json"}


def send_email(to_email, subject, html_body, to_name=None, text_body=None,
               sender_name=None, sender_email=None):
    """Send a single transactional email via Brevo.

    Returns the parsed JSON response (includes `messageId`).
    """
    sender = {
        "name": sender_name or SENDER_NAME or "Best Roadways",
        "email": sender_email or SENDER_EMAIL,
    }
    if not sender["email"]:
        raise RuntimeError(
            "No verified Brevo sender. Set BREVO_SENDER_EMAIL in .env (must be "
            "verified in Brevo) or pass sender_email=."
        )
    payload = {
        "sender": sender,
        "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
        "subject": subject,
        "htmlContent": html_body,
    }
    if text_body:
        payload["textContent"] = text_body

    resp = requests.post(f"{BASE}/smtp/email", headers=_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_events(email=None, limit=50, event=None, days=2):
    """Fetch recent SMTP events (delivered / opened / clicked / hardBounce / etc.).

    Brevo rate-limits this endpoint; keep `days` small and poll on the Observer
    cycle only. Returns the list under the API's `events` key.
    """
    params = {"limit": limit, "days": days}
    if email:
        params["email"] = email
    if event:
        params["event"] = event
    resp = requests.get(
        f"{BASE}/smtp/statistics/events", headers=_headers(), params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json().get("events", [])


if __name__ == "__main__":
    print("Brevo client configured:", bool(API_KEY), "| sender:", SENDER_EMAIL)
