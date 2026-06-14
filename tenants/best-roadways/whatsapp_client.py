"""WhatsApp send client for Best Roadways cycles.

Thin adapter over the repo-root `openwa_client` (the OpenWA gateway at ../OpenWA
is now the single WhatsApp backend; the old in-repo Go bridge was removed). Keeps
the historical `send_message(recipient, message) -> (ok, detail)` and
`normalize_number(mobile) -> digits` API so sdr_cycle.py is unchanged.

Setup: run OpenWA, mint an operator API key, QR-authorise a session, then set
OPENWA_API_KEY + OPENWA_SESSION_ID in tenants/best-roadways/.env.

Import is side-effect-free: openwa_client is imported lazily inside send_message,
so dry-run cycles work even before OpenWA is configured. A not-yet-ready/unset
session returns a "not connected" detail, which the cycle uses to abort the
WhatsApp batch cleanly.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def send_message(recipient, message):
    """Send a WhatsApp text via OpenWA. recipient = digits (e.g. 919876543210)
    or a full chat id. Returns (ok: bool, detail: str).

    A detail containing "not connected" signals the caller to abort the batch
    (gateway unreachable / unconfigured / session not ready)."""
    if not recipient:
        return False, "Recipient must be provided"

    try:
        import openwa_client as wa  # lazy: validates OPENWA_* env at import
    except Exception as e:
        return False, f"Not connected: OpenWA not configured ({e})"

    try:
        sess = wa.get_session_status()
    except Exception as e:
        return False, f"Not connected: {e}"
    if sess.get("status") != "ready":
        return False, f"Not connected: session status={sess.get('status')!r}"

    try:
        resp = wa.send_text(recipient, message, verify=True)
    except wa.NumberNotOnWhatsAppError as e:
        return False, f"Not on WhatsApp: {e}"
    except wa.SessionNotReadyError as e:
        return False, f"Not connected: {e}"
    except Exception as e:
        return False, f"Send failed: {e}"
    return True, resp.get("messageId", "sent")


def normalize_number(mobile):
    """Strip a mobile_no to digits for the gateway (drops +, spaces, dashes).
    Adds the India country code to a bare 10-digit number."""
    if not mobile:
        return ""
    digits = "".join(ch for ch in str(mobile) if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits
