"""Autonomous SDR + Observer cycle for Abhiyanta Tech (Gemini-drafted, Apollo-sent).

Exposes run_sdr_cycle(live_send, limit) and run_observer_cycle() so the cloud
worker / dashboard "Run SDR now" can drive it (driver = sdr_cycle).

Drafting always runs (Gemini). SENDING is gated: it only happens when
live_send=True AND APOLLO_CAMPAIGN_ID is set AND inside the send window — every
Apollo send must ride a campaign. Otherwise actions are logged as 'drafted'
(dry-run) and show up in the dashboard for review.

    AGENTIC_SDR_TENANT=abhiyanta-tech python tenants/abhiyanta-tech/sdr_cycle.py sdr
"""

import json
import os
import sys
from datetime import datetime, time as dtime
from pathlib import Path

from dotenv import load_dotenv

TENANT_DIR = Path(__file__).resolve().parent
REPO_ROOT = TENANT_DIR.parent.parent
load_dotenv(TENANT_DIR / ".env")
sys.path.insert(0, str(TENANT_DIR))   # gemini_client
sys.path.insert(0, str(REPO_ROOT))    # apollo_client

import gemini_client  # noqa: E402

TRACKER = TENANT_DIR / "outreach_tracker.json"
QUEUE = TENANT_DIR / "qualified_leads.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
PLAYBOOK = TENANT_DIR / "strategy_playbook.md"
CONFIG = TENANT_DIR / "company_config.json"
CYCLE_LOG = TENANT_DIR / "cycle.log"

DAILY_CAP = int(os.getenv("APOLLO_DAILY_SEND_CAP", "50"))
SEND_START, SEND_END = dtime(11, 0), dtime(19, 30)


def _now() -> datetime:
    return datetime.now()


def log(msg: str) -> None:
    line = f"[{_now():%Y-%m-%d %H:%M:%S}] {msg}"
    with open(CYCLE_LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def _load(path: Path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def _save(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _in_window() -> bool:
    return SEND_START <= _now().time() <= SEND_END


def _lead_id(lead: dict, i: int):
    for k in ("lead_row_id", "id", "lead_id", "apollo_id", "apollo_contact_id", "email_id", "email"):
        if lead.get(k):
            return lead[k]
    return f"row-{i}"


def _system_prompt(config: dict) -> str:
    playbook = PLAYBOOK.read_text() if PLAYBOOK.exists() else ""
    return (
        f"You are an SDR for {config.get('company_name')}, selling "
        f"{config.get('product_name')}. Write in a casual, unsure tone "
        f"('Not sure if...'). First touches MUST be under 50 words. No buzzwords, "
        f"no 'I hope this finds you well'. Follow this playbook:\n\n{playbook}"
    )


def _draft_for(lead: dict, config: dict, system: str) -> dict:
    name = lead.get("contact") or lead.get("first_name") or lead.get("lead_name") or "there"
    company = lead.get("company") or lead.get("company_name") or "your company"
    title = lead.get("job_title") or lead.get("designation") or ""
    prompt = (
        f"Draft a cold outreach EMAIL to {name}"
        f"{f' ({title})' if title else ''} at {company}.\n"
        f"Pick the right vertical hook from the playbook for an SAP buyer.\n"
        f"Return EXACTLY two lines:\nSUBJECT: <short subject>\nBODY: <under 50 words>"
    )
    text = gemini_client.draft(prompt, system=system, temperature=0.7)
    subject, body = "", text
    for line in text.splitlines():
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BODY:"):
            body = line.split(":", 1)[1].strip()
    if subject and body == text:
        body = text.split("BODY:", 1)[-1].strip() if "BODY:" in text else text
    return {"subject": subject or f"SAP at {company}", "body": body.strip()}


def _send_via_apollo(lead: dict, subject: str, body: str) -> tuple[bool, str]:
    """Push the contact into the configured Apollo campaign. Requires
    APOLLO_CAMPAIGN_ID + APOLLO_EMAIL_ACCOUNT_ID."""
    campaign = os.getenv("APOLLO_CAMPAIGN_ID")
    account = os.getenv("APOLLO_EMAIL_ACCOUNT_ID")
    if not campaign or not account:
        return False, "no APOLLO_CAMPAIGN_ID/EMAIL_ACCOUNT_ID"
    try:
        import apollo_client
        contact_id = lead.get("apollo_contact_id")
        if not contact_id:
            person = {
                "first_name": lead.get("first_name") or (lead.get("contact") or "").split(" ")[0],
                "last_name": lead.get("last_name") or "",
                "email": lead.get("email") or lead.get("email_id"),
                "organization_name": lead.get("company") or lead.get("company_name"),
            }
            contact_id = (apollo_client.create_contact(person) or {}).get("id")
        if not contact_id:
            return False, "could not resolve Apollo contact id"
        apollo_client.add_contacts_to_campaign(campaign, [contact_id], account)
        return True, contact_id
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def run_sdr_cycle(live_send: bool = False, limit: int | None = None) -> dict:
    config = _load(CONFIG, {})
    tracker = _load(TRACKER, {"actions": [], "aggregate_stats": {}})
    tracker.setdefault("actions", [])
    agg = tracker.setdefault("aggregate_stats", {})
    queue = _load(QUEUE, [])
    blocked_ids = {_lead_id(b, i) for i, b in enumerate(_load(BLOCKED, []))}
    done_ids = {a.get("lead_row_id") for a in tracker["actions"]}

    system = _system_prompt(config)
    window_ok = _in_window()
    can_send = live_send and window_ok and bool(os.getenv("APOLLO_CAMPAIGN_ID"))
    sent_today = sum(
        1 for a in tracker["actions"]
        if a.get("status") == "sent" and str(a.get("at", "")).startswith(f"{_now():%Y-%m-%d}")
    )

    summary = {"drafted": 0, "sent": 0, "skipped": 0, "queue": len(queue)}
    cap = limit if limit is not None else DAILY_CAP

    for i, lead in enumerate(queue):
        if summary["drafted"] + summary["sent"] >= cap:
            break
        lid = _lead_id(lead, i)
        if lid in done_ids or lid in blocked_ids:
            continue
        email = lead.get("email") or lead.get("email_id")
        try:
            d = _draft_for(lead, config, system)
        except Exception as exc:  # noqa: BLE001
            log(f"draft failed for {lid}: {exc}")
            summary["skipped"] += 1
            continue

        action = {
            "at": f"{_now():%Y-%m-%d %H:%M} IST",
            "lead_row_id": lid,
            "company": lead.get("company") or lead.get("company_name"),
            "contact": lead.get("contact") or lead.get("first_name"),
            "email": email,
            "channel": "email",
            "framework": "Mouse Trap",
            "subject": d["subject"],
            "body": d["body"],
            "status": "drafted",
            "dry_run": True,
        }

        if can_send and email and sent_today < DAILY_CAP:
            ok, detail = _send_via_apollo(lead, d["subject"], d["body"])
            action["status"] = "sent" if ok else "send_failed"
            action["dry_run"] = not ok
            action["apollo_note"] = detail
            if ok:
                summary["sent"] += 1
                sent_today += 1
                agg["sends"] = agg.get("sends", 0) + 1
        else:
            summary["drafted"] += 1

        tracker["actions"].append(action)
        done_ids.add(lid)
        log(f"{'SENT' if action['status']=='sent' else 'drafted'} -> {action['company']}: {d['subject']}")

    _save(TRACKER, tracker)
    log(f"SDR cycle done: {summary} (live_send={live_send}, window_ok={window_ok})")
    return summary


def run_observer_cycle() -> dict:
    """Pull live email status from Apollo, then recompute aggregate stats."""
    # First fold Apollo delivery/reply status onto each action (writes the tracker).
    apollo = {}
    try:
        import apollo_status_sync
        apollo = apollo_status_sync.sync_tracker_statuses(TENANT_DIR.name)
        log(f"Apollo status sync: {apollo}")
    except Exception as exc:  # noqa: BLE001 — observer must survive Apollo hiccups
        log(f"Apollo status sync skipped: {exc}")

    tracker = _load(TRACKER, {"actions": [], "aggregate_stats": {}})
    actions = tracker.get("actions", [])
    agg = tracker.setdefault("aggregate_stats", {})
    agg["sends"] = sum(1 for a in actions if a.get("status") == "sent")
    agg["replied"] = sum(1 for a in actions if a.get("status") == "replied")
    agg["bounced"] = sum(1 for a in actions if a.get("status") in ("bounced", "spam_blocked"))
    agg["drafted"] = sum(1 for a in actions if a.get("status") == "drafted")
    _save(TRACKER, tracker)
    summary = {"actions": len(actions), "apollo": apollo, **agg}
    log(f"Observer cycle: {summary}")
    return summary


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sdr"
    if mode == "observer":
        print(run_observer_cycle())
    else:
        print(run_sdr_cycle(live_send="--live" in sys.argv))
