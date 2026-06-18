"""Normalize the two tenants' divergent outreach_tracker action schemas into the
single `actions` row shape the SaaS DB expects. Pure stdlib — no DB/crypto deps,
so it's unit-testable in isolation.

best-roadways action: ts, lead_id, company, mobile, channel, framework, body,
                      dry_run, status, subject?, message_id?
abhiyanta action:     at, lead_row_id, company, contact, email, apollo_contact_id,
                      channel?, campaign_id, framework, subject, apollo_status, note
"""

import re
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

# Friendly campaign labels for the dashboard's per-campaign grouping. Known Apollo
# campaign ids / internal campaign keys map to readable names; anything else falls
# back to a cleaned version of whatever the tracker recorded.
_APOLLO_CAMPAIGN_NAMES = {
    "6a1eb142c4e6ea00202e3f45": "SAP Integration Suite – T1 India",
    "6a33a048d5fe68001c3e7e34": "PI/PO Sunset Webinar",
}
_CAMPAIGN_KEY_NAMES = {
    "webinar_pipo_sunset_v1": "PI/PO Sunset Webinar",
}


def campaign_label(raw: dict) -> str | None:
    """Resolve a stable, human-readable campaign label for an action so the
    dashboard can separate logs by campaign. Canonical id/key mappings win first
    so one logical campaign reaching the tracker via different identifiers (Apollo
    id vs internal key) still collapses to a single label."""
    cid = raw.get("apollo_campaign_id") or raw.get("campaign_id")
    if cid and cid in _APOLLO_CAMPAIGN_NAMES:
        return _APOLLO_CAMPAIGN_NAMES[cid]
    key = raw.get("campaign")
    if key and key in _CAMPAIGN_KEY_NAMES:
        return _CAMPAIGN_KEY_NAMES[key]
    name = raw.get("apollo_campaign_name")
    if name:
        return re.sub(r"^\[[^\]]*\]\s*", "", name).strip()  # drop a leading "[owner]" tag
    if key:
        return key
    if cid:
        return cid
    return None


def parse_timestamp(value: str | None) -> datetime:
    """Parse the various timestamp shapes both trackers emit. Falls back to epoch
    0 (UTC) for unparseable/missing values so a row still sorts deterministically.

    Handles:
      - ISO 8601 (best-roadways `ts`, from datetime.isoformat())
      - "YYYY-MM-DD HH:MM IST" (abhiyanta `at`)
      - "YYYY-MM-DD HH:MM" / "YYYY-MM-DD HH:MM:SS"
      - date-only "YYYY-MM-DD"
    """
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    raw = value.strip()
    # Strip a trailing timezone abbreviation like " IST" and treat as IST.
    forced_ist = False
    if raw.endswith(" IST"):
        raw = raw[: -len(" IST")].strip()
        forced_ist = True
    # Try ISO first.
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=IST if forced_ist else IST)
            return dt
        except ValueError:
            continue
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def normalize_action(slug: str, raw: dict) -> dict:
    """Map a raw tracker action (either schema) to the `actions` columns."""
    occurred = parse_timestamp(raw.get("ts") or raw.get("at"))
    lead_ref = raw.get("lead_id")
    if lead_ref is None:
        lead_ref = raw.get("lead_row_id")
    recipient = raw.get("email") or raw.get("mobile") or raw.get("recipient")
    if lead_ref is None:
        lead_ref = recipient or "?"
    # A producer can supply a stable source_key (e.g. scheduled campaigns that get
    # re-stamped) so re-pushes update in place instead of creating duplicate rows.
    source_key = raw.get("source_key") or f"{slug}:{lead_ref}:{occurred.isoformat()}"

    # Carry a campaign label into events JSONB so the dashboard can group/filter
    # by campaign without a schema migration (events already passes through).
    events = dict(raw.get("events") or {})
    label = campaign_label(raw)
    if label:
        events["campaign"] = label

    return {
        "source_key": source_key,
        "channel": (raw.get("channel") or "email"),
        "company": raw.get("company"),
        "recipient": recipient,
        "framework": raw.get("framework"),
        "subject": raw.get("subject"),
        "body": raw.get("body"),
        "message_id": raw.get("message_id") or raw.get("apollo_contact_id"),
        "chat_id": raw.get("chat_id"),
        "status": raw.get("status") or raw.get("apollo_status"),
        "dry_run": raw.get("dry_run"),
        "events": events,
        "occurred_at": occurred,
    }


def normalize_credit_snapshot(raw: dict) -> dict:
    """Map an outreach_tracker credit_snapshots[] entry to credit_snapshots cols."""
    return {
        "at": parse_timestamp(raw.get("at")),
        "label": raw.get("label"),
        "lead_credit_left": raw.get("lead_credit_left"),
        "direct_dial_credit_left": raw.get("direct_dial_credit_left"),
        "export_credit_left": raw.get("export_credit_left"),
        "cycle_start": raw.get("cycle_start"),
        "cycle_end": raw.get("cycle_end"),
    }
