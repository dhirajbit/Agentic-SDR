"""OpenWA (WhatsApp) client with a hard session-readiness gate.

OpenWA is a self-hosted WhatsApp HTTP gateway (NestJS, whatsapp-web.js engine)
living at ../OpenWA. It exposes a REST API (default http://localhost:2785/api)
authenticated with an `X-API-Key` header. Every WhatsApp action rides a *session*
(one linked WhatsApp number, authorised once via QR scan).

Design contract (mirrors apollo_client.py):
- Every process must call `get_session_status()` before any send.
- Every send goes through `send_text()`, which refuses to proceed unless the
  session was checked in-process within the last 10 minutes AND is `ready`.
- Sends optionally verify the recipient is actually on WhatsApp first
  (`check_number_on_whatsapp`) — a non-WhatsApp number silently no-ops on the
  WhatsApp Web engine, so we'd otherwise log a phantom "send".
- This account uses an *unofficial* WhatsApp automation. Respect daily caps and
  the 11:00-19:30 send window in the SDR workflow; over-sending risks a ban.

Tenant resolution: set AGENTIC_SDR_TENANT=<slug> in the environment. The client
loads tenants/<slug>/.env (overriding any repo-root .env) so multi-tenant
operation never mixes credentials or sessions.

This client does NOT write outreach_tracker.json — the SDR workflow logs sends,
exactly as it does for Apollo. For pulling inbound replies into
urgent_followups.json, see whatsapp_sync_replies.py.
"""

import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent

_TENANT_SLUG = os.getenv("AGENTIC_SDR_TENANT")
if _TENANT_SLUG:
    _tenant_env = REPO_ROOT / "tenants" / _TENANT_SLUG / ".env"
    if _tenant_env.exists():
        load_dotenv(_tenant_env, override=True)
load_dotenv(REPO_ROOT / ".env")  # fallback for shared defaults

BASE_URL = os.getenv("OPENWA_BASE_URL", "http://localhost:2785/api").rstrip("/")
API_KEY = os.getenv("OPENWA_API_KEY")
SESSION_ID = os.getenv("OPENWA_SESSION_ID")
# Leads in this tenant are India numbers, often stored without a country code.
# Used to normalise bare 10-digit numbers into WhatsApp chat ids.
DEFAULT_COUNTRY_CODE = os.getenv("WHATSAPP_DEFAULT_COUNTRY_CODE", "91")

if not API_KEY:
    raise RuntimeError(
        "OPENWA_API_KEY not set. Set AGENTIC_SDR_TENANT and ensure "
        "tenants/<slug>/.env contains OPENWA_API_KEY (the operator-role API key "
        "minted by the OpenWA gateway)."
    )
if not SESSION_ID:
    raise RuntimeError(
        "OPENWA_SESSION_ID not set. Create + QR-authorise a session in OpenWA, "
        "then put its id in tenants/<slug>/.env as OPENWA_SESSION_ID."
    )

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
}


class WhatsAppError(RuntimeError):
    """Base class for OpenWA client failures."""


class SessionNotReadyError(WhatsAppError):
    """Raised when a send is attempted without a fresh session check, or the
    session is not in the `ready` state (e.g. needs QR re-scan)."""


class NumberNotOnWhatsAppError(WhatsAppError):
    """Raised when a verified send targets a number that isn't on WhatsApp."""


# Process-local cache of the last session status. Set by get_session_status().
# send_text() refuses to proceed if this is None, stale, or not `ready`.
_SESSION_TTL = 600  # 10 minutes
_last_session: dict | None = None


def _request(method: str, path: str, **kwargs):
    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = requests.request(method, url, headers=HEADERS, timeout=30, **kwargs)
    if resp.status_code >= 400:
        raise WhatsAppError(f"OpenWA {method} {path} -> {resp.status_code}: {resp.text[:500]}")
    if not resp.content:
        return {}
    return resp.json()


# --------------------------------------------------------------------------- #
# Phone / chat-id helpers
# --------------------------------------------------------------------------- #

def to_chat_id(phone: str) -> str:
    """Normalise a raw phone string into an OpenWA individual chat id.

    OpenWA expects `<countrycode><number>@c.us` with no '+', spaces or dashes.
    Rules:
      - strip everything that isn't a digit (drops '+', spaces, dashes, ()).
      - drop a single leading 0 (common local-format prefix).
      - if the result is a bare national number (<= 10 digits) and a default
        country code is configured, prepend it.
    """
    if not phone:
        raise WhatsAppError("Empty phone number; cannot build chat id.")
    if phone.endswith("@c.us") or phone.endswith("@g.us"):
        return phone  # already a chat id
    digits = re.sub(r"\D", "", phone)
    if not digits:
        raise WhatsAppError(f"No digits in phone number {phone!r}.")
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    if len(digits) <= 10 and DEFAULT_COUNTRY_CODE:
        digits = f"{DEFAULT_COUNTRY_CODE}{digits}"
    return f"{digits}@c.us"


def is_placeholder_number(phone: str) -> bool:
    """Many enriched rows carry placeholder phones like '0000000000'. Treat a
    number with fewer than 7 digits, or one made of a single repeated digit, as
    unusable."""
    digits = re.sub(r"\D", "", phone or "")
    return len(digits) < 7 or len(set(digits)) <= 1


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #

def get_session_status() -> dict:
    """Fetch the live session record. Must be called before any send.

    Returns a dict like:
      {"id": "...", "name": "...", "status": "ready", "phone": "9190...",
       "pushName": "...", "fetched_at": <epoch>}
    Status values: created | initializing | qr_ready | authenticating | ready |
    disconnected | failed.
    """
    global _last_session
    raw = _request("GET", f"sessions/{SESSION_ID}")
    raw["fetched_at"] = time.time()
    _last_session = raw
    return raw


def assert_session_ready() -> None:
    """Hard gate. Raises SessionNotReadyError if a recent session check is
    missing/stale or the session isn't `ready`."""
    if _last_session is None:
        raise SessionNotReadyError(
            "Session status not checked in this process. "
            "Call get_session_status() before sending."
        )
    age = time.time() - _last_session["fetched_at"]
    if age > _SESSION_TTL:
        raise SessionNotReadyError(
            f"Session check is stale ({age:.0f}s > {_SESSION_TTL}s). "
            "Re-call get_session_status() before sending."
        )
    status = _last_session.get("status")
    if status != "ready":
        raise SessionNotReadyError(
            f"Session {SESSION_ID} status is {status!r}, not 'ready'. "
            "If 'qr_ready', the number needs a fresh QR scan — call get_qr() and "
            "scan it in WhatsApp > Linked Devices."
        )


def start_session() -> dict:
    """Start (initialise) the session so it can produce a QR / connect."""
    return _request("POST", f"sessions/{SESSION_ID}/start")


def get_qr() -> dict:
    """Return the current QR payload ({'qrCode': 'data:image/png;base64,...'})
    for authorising the WhatsApp number. Only valid while status is qr_ready."""
    return _request("GET", f"sessions/{SESSION_ID}/qr")


# --------------------------------------------------------------------------- #
# Contacts
# --------------------------------------------------------------------------- #

def check_number_on_whatsapp(phone: str) -> dict:
    """Check whether a number is registered on WhatsApp.
    Returns the gateway response, e.g. {'number': '...', 'exists': true,
    'whatsappId': '...@c.us'}. Cheap (no message sent)."""
    digits = re.sub(r"\D", "", to_chat_id(phone).split("@")[0])
    return _request("GET", f"sessions/{SESSION_ID}/contacts/check/{digits}")


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #

def send_text(phone: str, text: str, *, verify: bool = True) -> dict:
    """Send a WhatsApp text message via OpenWA.

    Gated: caller MUST have called get_session_status() in-process within the
    last 10 minutes (passes through assert_session_ready()).

    Args:
      phone:  recipient number (any format) or a full chat id.
      text:   message body (<= 65536 chars; first touches should be < 50 words).
      verify: if True, confirm the number is on WhatsApp before sending and
              raise NumberNotOnWhatsAppError otherwise.

    Returns the gateway response, e.g. {'messageId': '...', 'timestamp': ...},
    augmented with the resolved 'chatId'.
    """
    assert_session_ready()
    if not text or not text.strip():
        raise WhatsAppError("Refusing to send an empty WhatsApp message.")
    chat_id = to_chat_id(phone)

    if verify:
        check = check_number_on_whatsapp(phone)
        if not check.get("exists"):
            raise NumberNotOnWhatsAppError(
                f"{phone} (-> {chat_id}) is not on WhatsApp; not sending."
            )
        # Prefer the canonical id the gateway resolved, if present.
        chat_id = check.get("whatsappId") or chat_id

    resp = _request(
        "POST",
        f"sessions/{SESSION_ID}/messages/send-text",
        json={"chatId": chat_id, "text": text},
    )
    resp["chatId"] = chat_id
    return resp


def reply_text(chat_id: str, quoted_message_id: str, text: str) -> dict:
    """Reply to a specific inbound message (quotes it). Gated like send_text."""
    assert_session_ready()
    return _request(
        "POST",
        f"sessions/{SESSION_ID}/messages/reply",
        json={"chatId": chat_id, "quotedMessageId": quoted_message_id, "text": text},
    )


# --------------------------------------------------------------------------- #
# Inbound (for the Observer loop)
# --------------------------------------------------------------------------- #

def list_messages(chat_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    """Pull message history for the session (newest first). Each message has at
    least: chatId, from, body, type, direction ('incoming'|'outgoing'),
    timestamp (epoch seconds)."""
    params = {"limit": limit, "offset": offset}
    if chat_id:
        params["chatId"] = chat_id
    resp = _request("GET", f"sessions/{SESSION_ID}/messages", params=params)
    if isinstance(resp, dict):
        return resp.get("messages", resp.get("data", [])) or []
    return resp or []


def fetch_replies_since(since_epoch: float, scan_limit: int = 200) -> list[dict]:
    """Return inbound (direction == 'incoming') messages newer than since_epoch.

    Used by the Observer loop to surface prospect replies into
    urgent_followups.json. `since_epoch` is in seconds; OpenWA timestamps are
    also epoch seconds (occasionally milliseconds — normalised here)."""
    out = []
    for m in list_messages(limit=scan_limit):
        if m.get("direction") != "incoming":
            continue
        ts = m.get("timestamp") or 0
        if ts > 1e12:  # milliseconds -> seconds
            ts = ts / 1000
        if ts > since_epoch:
            out.append({**m, "timestamp": ts})
    return out


def register_webhook(url: str, events: list[str] | None = None, secret: str | None = None) -> dict:
    """Register an OpenWA webhook so the gateway POSTs events to `url`.
    Default events: ['message.received', 'session.status']. Use this instead of
    polling fetch_replies_since() if you run an always-on receiver."""
    payload = {"url": url, "events": events or ["message.received", "session.status"]}
    if secret:
        payload["secret"] = secret
    return _request("POST", f"sessions/{SESSION_ID}/webhooks", json=payload)


def smoke_test() -> None:
    """Hits /health + the configured session. Safe to call anytime."""
    health = _request("GET", "health")
    print("health ->", json.dumps(health))
    sess = get_session_status()
    print(f"session {SESSION_ID} -> status={sess.get('status')} phone={sess.get('phone')}")
    if sess.get("status") != "ready":
        print("  (not ready) start_session() then scan get_qr()['qrCode'] in WhatsApp.")


if __name__ == "__main__":
    smoke_test()
