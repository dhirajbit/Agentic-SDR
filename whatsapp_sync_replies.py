"""Pull inbound WhatsApp replies into the tenant's urgent_followups.json.

Run from the Observer loop. Polls OpenWA for incoming messages newer than the
last watermark, matches each to a known outreach contact (by chat id seen in
outreach_tracker.json), and appends de-duplicated entries to
urgent_followups.json so the SDR loop handles them FIRST next cycle.

    AGENTIC_SDR_TENANT=<slug> python whatsapp_sync_replies.py [--lookback-hours N]

Watermark state lives at tenants/<slug>/whatsapp_sync_state.json. On the very
first run (no watermark) it looks back `--lookback-hours` (default 24h).

Alternative to polling: openwa_client.register_webhook() pushes the same events
to an always-on receiver. Polling is used here because the Observer loop is
periodic and needs no inbound HTTP server.
"""

import argparse
import json
import os
import time
from pathlib import Path

import openwa_client as wa


REPO_ROOT = Path(__file__).resolve().parent
TENANT = os.getenv("AGENTIC_SDR_TENANT")
if not TENANT:
    raise SystemExit("AGENTIC_SDR_TENANT not set.")
TENANT_DIR = REPO_ROOT / "tenants" / TENANT

STATE_FILE = TENANT_DIR / "whatsapp_sync_state.json"
FOLLOWUPS_FILE = TENANT_DIR / "urgent_followups.json"
TRACKER_FILE = TENANT_DIR / "outreach_tracker.json"


def _load_json(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def _save_json(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _build_contact_index() -> dict[str, dict]:
    """Map normalised chat id -> {company, contact, lead_row_id} from prior
    WhatsApp sends logged in the tracker, so replies can be attributed."""
    tracker = _load_json(TRACKER_FILE, {})
    index: dict[str, dict] = {}
    for a in tracker.get("actions", []):
        if a.get("channel") != "whatsapp":
            continue
        chat_id = a.get("chat_id") or a.get("whatsapp_chat_id")
        phone = a.get("phone") or a.get("phone_number")
        if not chat_id and phone:
            try:
                chat_id = wa.to_chat_id(phone)
            except wa.WhatsAppError:
                chat_id = None
        if chat_id:
            index[chat_id] = {
                "company": a.get("company"),
                "contact": a.get("contact"),
                "lead_row_id": a.get("lead_row_id"),
            }
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-hours", type=float, default=24.0,
                        help="How far back to scan on the first run (no watermark).")
    args = parser.parse_args()

    # Hard gate: confirm the session is live before trusting message history.
    sess = wa.get_session_status()
    if sess.get("status") != "ready":
        raise SystemExit(
            f"WhatsApp session {wa.SESSION_ID} status={sess.get('status')!r}, not 'ready'. "
            "Cannot sync replies — re-authorise the session first."
        )

    state = _load_json(STATE_FILE, {})
    watermark = state.get("last_sync_epoch")
    if watermark is None:
        watermark = time.time() - args.lookback_hours * 3600

    replies = wa.fetch_replies_since(watermark)
    contact_index = _build_contact_index()

    followups = _load_json(FOLLOWUPS_FILE, [])
    seen_ids = {f.get("whatsapp_message_id") for f in followups if f.get("whatsapp_message_id")}

    added = 0
    max_ts = watermark
    for m in sorted(replies, key=lambda x: x.get("timestamp", 0)):
        mid = m.get("id") or m.get("messageId") or f"{m.get('chatId')}:{m.get('timestamp')}"
        ts = m.get("timestamp", 0)
        max_ts = max(max_ts, ts)
        if mid in seen_ids:
            continue
        chat_id = m.get("chatId") or m.get("from")
        meta = contact_index.get(chat_id, {})
        followups.append({
            "channel": "whatsapp",
            "whatsapp_message_id": mid,
            "chat_id": chat_id,
            "from": m.get("from"),
            "company": meta.get("company"),
            "contact": meta.get("contact"),
            "lead_row_id": meta.get("lead_row_id"),
            "body": m.get("body"),
            "received_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else None,
            "received_epoch": ts,
            "status": "needs_reply",
        })
        seen_ids.add(mid)
        added += 1

    _save_json(FOLLOWUPS_FILE, followups)
    _save_json(STATE_FILE, {"last_sync_epoch": max_ts,
                            "last_run": time.strftime("%Y-%m-%d %H:%M:%S")})

    print(f"[whatsapp-sync] {added} new repl{'y' if added == 1 else 'ies'} -> {FOLLOWUPS_FILE.name} "
          f"({len(replies)} inbound scanned since watermark).")


if __name__ == "__main__":
    main()
