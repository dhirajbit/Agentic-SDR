"""Pull live email status from Apollo into the tenant's outreach_tracker.

For every action that rode an Apollo campaign (`apollo_campaign_id` / `campaign_id`
with an `apollo_contact_id`), look up the matching emailer_message and fold its
delivery/reply state back onto the action: the `status` column the dashboard shows,
plus `events.{sent,replied,bounced}` flags the overview tiles aggregate.

Apollo message states seen on this account:
  drafted   -> queued    (created, awaiting the manual-email step's send)
  completed -> sent
  failed    -> bounced | spam_blocked | send_failed  (per bounce/spam flags)
  replied=true at any point -> replied

Run standalone:  AGENTIC_SDR_TENANT=<slug> python apollo_status_sync.py
Or call sync_tracker_statuses(slug) from the observer loop.
"""

import json
import os
from pathlib import Path

import apollo_client

REPO_ROOT = Path(__file__).resolve().parent


def classify(msg: dict) -> tuple[str, dict]:
    """Map a raw Apollo emailer_message to (status, events_patch)."""
    raw = msg.get("status")
    if msg.get("replied"):
        return "replied", {"replied": True}
    if raw == "completed":
        return "sent", {"sent": True}
    if raw == "failed":
        if msg.get("spam_blocked"):
            return "spam_blocked", {"bounced": True, "failure": msg.get("failure_reason")}
        if msg.get("bounce"):
            return "bounced", {"bounced": True, "failure": msg.get("failure_reason")}
        return "send_failed", {"failure": msg.get("failure_reason") or msg.get("not_sent_reason")}
    if raw == "drafted":
        return "queued", {}
    if raw == "scheduled":
        return "scheduled", {}
    return raw or "queued", {}


def _campaign_id(action: dict) -> str | None:
    return action.get("apollo_campaign_id") or action.get("campaign_id")


def sync_tracker_statuses(slug: str) -> dict:
    """Update outreach_tracker.json action statuses from Apollo. Returns a summary."""
    tracker_path = REPO_ROOT / "tenants" / slug / "outreach_tracker.json"
    tracker = json.loads(tracker_path.read_text())
    actions = tracker.get("actions", [])

    campaign_ids = sorted({
        cid for a in actions
        if (cid := _campaign_id(a)) and a.get("apollo_contact_id")
    })
    if not campaign_ids:
        return {"campaigns": 0, "messages": 0, "updated": 0}

    by_campaign = apollo_client.fetch_message_status_by_campaign(campaign_ids)
    n_msgs = sum(len(v) for v in by_campaign.values())

    updated = 0
    for a in actions:
        cid, contact = _campaign_id(a), a.get("apollo_contact_id")
        if not cid or not contact:
            continue
        msg = by_campaign.get(cid, {}).get(contact)
        if not msg:
            continue
        status, patch = classify(msg)
        a["status"] = status
        a["apollo_status_raw"] = msg.get("status")
        events = a.setdefault("events", {})
        for k, v in patch.items():
            if v is not None:
                events[k] = v
        updated += 1

    tracker_path.write_text(json.dumps(tracker, indent=2))
    return {"campaigns": len(campaign_ids), "messages": n_msgs, "updated": updated}


if __name__ == "__main__":
    slug = os.getenv("AGENTIC_SDR_TENANT")
    if not slug:
        raise SystemExit("AGENTIC_SDR_TENANT not set.")
    summary = sync_tracker_statuses(slug)
    print(f"[apollo-status-sync:{slug}] {summary}")
