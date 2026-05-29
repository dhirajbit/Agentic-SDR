"""WhatsApp send client for Best Roadways cycles.

Talks to the local WhatsApp Go bridge (under repo whatsapp-mcp/) over HTTP, the
same contract the kstars-sdr MCP server uses. Lets the SDR cycle send WhatsApp
follow-ups without the Claude-only MCP layer.

Bridge must be running:  cd whatsapp-mcp/whatsapp-bridge && go run main.go
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE = (os.getenv("WHATSAPP_API_BASE_URL") or "http://localhost:8080/api").rstrip("/")


def send_message(recipient, message):
    """Send a WhatsApp text. recipient = digits only (e.g. 919876543210) or JID.
    Returns (ok: bool, detail: str)."""
    if not recipient:
        return False, "Recipient must be provided"
    try:
        resp = requests.post(
            f"{BASE}/send",
            json={"recipient": recipient, "message": message},
            timeout=30,
        )
    except requests.RequestException as e:
        return False, f"Not connected: {e}"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code} - {resp.text}"
    try:
        data = resp.json()
    except ValueError:
        return False, f"Bad response: {resp.text}"
    return bool(data.get("success")), data.get("message", "")


def normalize_number(mobile):
    """Strip a mobile_no to digits for the bridge (drops +, spaces, dashes)."""
    if not mobile:
        return ""
    digits = "".join(ch for ch in str(mobile) if ch.isdigit())
    # Add India country code if a bare 10-digit number was supplied.
    if len(digits) == 10:
        digits = "91" + digits
    return digits
