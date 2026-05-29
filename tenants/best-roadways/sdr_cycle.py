"""Gemini-driven SDR + Observer cycle engine for Best Roadways.

Importable (used by app.py) and runnable from the CLI:
    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/sdr_cycle.py sdr
    AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/sdr_cycle.py observer

Dry-run by default: drafts via Gemini and logs everything, but sends nothing
unless live_send=True. Daily caps + the 11:00-19:30 send window gate LIVE sends.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

TENANT_DIR = Path(__file__).resolve().parent
load_dotenv(TENANT_DIR / ".env")

import gemini_client
import brevo_client
import whatsapp_client

TRACKER = TENANT_DIR / "outreach_tracker.json"
QUEUE = TENANT_DIR / "qualified_leads.json"
BLOCKED = TENANT_DIR / "blocked_leads.json"
URGENT = TENANT_DIR / "urgent_followups.json"
PLAYBOOK = TENANT_DIR / "strategy_playbook.md"
LOG = TENANT_DIR / "cycle.log"

DAILY_EMAIL_CAP = int(os.getenv("DAILY_EMAIL_CAP", "300"))
DAILY_WHATSAPP_CAP = int(os.getenv("DAILY_WHATSAPP_CAP", "10"))
SEND_WINDOW_START = os.getenv("SEND_WINDOW_START", "11:00")
SEND_WINDOW_END = os.getenv("SEND_WINDOW_END", "19:30")


# ----------------------------- helpers -----------------------------

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def _load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save(path, data):
    path.write_text(json.dumps(data, indent=2))


def _now():
    return datetime.now()


def in_send_window(now=None):
    now = now or _now()
    def _parse(s):
        h, m = s.split(":")
        return now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    return _parse(SEND_WINDOW_START) <= now <= _parse(SEND_WINDOW_END)


def _today():
    return _now().strftime("%Y-%m-%d")


def _sends_today(tracker, channel="email"):
    n = 0
    for a in tracker.get("actions", []):
        if a.get("channel") == channel and not a.get("dry_run") \
                and (a.get("ts", "")[:10] == _today()):
            n += 1
    return n


def _already_emailed_ids(tracker):
    return {a.get("lead_id") for a in tracker.get("actions", []) if a.get("channel") == "email"}


def _wa_sent_ids(tracker):
    return {a.get("lead_id") for a in tracker.get("actions", []) if a.get("channel") == "whatsapp"}


def _playbook_text():
    return PLAYBOOK.read_text() if PLAYBOOK.exists() else ""


SYSTEM_PERSONA = (
    "You are the SDR for Best Roadways Limited, India's trusted road-freight partner since 1985 "
    "(800+ owned GPS-tracked BS-VI trucks, 65+ branches, 500+ cities; FTL, PTL, warehousing, "
    "chemical/hazmat, project & ODC cargo). Write outreach that follows the strategy playbook "
    "below EXACTLY: first touches under 50 words, casual and a little unsure, company name in the "
    "subject, soft CTA, no banned phrases, never name competitors.\n\n--- PLAYBOOK ---\n"
)


def _draft_email(lead):
    company = lead.get("company") or "your company"
    title = lead.get("title") or "the team"
    city = lead.get("city") or ""
    website = lead.get("website") or ""
    prompt = (
        f"Draft a FIRST-TOUCH cold email using the Vanilla Ice Cream framework for:\n"
        f"- Company: {company}\n- Recipient title: {title}\n- City: {city}\n- Website: {website}\n\n"
        "Return STRICT JSON only: {\"subject\": \"...\", \"body\": \"...\", \"framework\": \"Vanilla Ice Cream\"}. "
        "Body under 50 words, plain text, casual/unsure tone, soft CTA. Subject 4-8 words including the company name."
    )
    raw = gemini_client.draft(prompt, system=SYSTEM_PERSONA + _playbook_text(), temperature=0.7)
    return _parse_json_draft(raw, fallback_subject=f"freight capacity for {company}")


def _parse_json_draft(raw, fallback_subject="quick freight question"):
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
    try:
        start, end = txt.find("{"), txt.rfind("}")
        obj = json.loads(txt[start:end + 1])
        return {
            "subject": (obj.get("subject") or fallback_subject).strip(),
            "body": (obj.get("body") or raw).strip(),
            "framework": obj.get("framework") or "Vanilla Ice Cream",
        }
    except Exception:
        return {"subject": fallback_subject, "body": raw.strip(), "framework": "Vanilla Ice Cream"}


def _bump_framework(tracker, framework, field):
    fp = tracker.setdefault("framework_performance", {})
    row = fp.setdefault(framework, {"sends": 0, "opens": 0, "replies": 0})
    row[field] = row.get(field, 0) + 1


# ----------------------------- SDR cycle -----------------------------

def run_sdr_cycle(live_send=False, limit=10):
    mode = "LIVE" if live_send else "DRY-RUN"
    log(f"=== SDR cycle start ({mode}, limit={limit}) ===")

    tracker = _load(TRACKER, {})
    tracker.setdefault("actions", [])
    agg = tracker.setdefault("aggregate_stats", {})
    queue = _load(QUEUE, [])
    blocked = set(_load(BLOCKED, []))
    urgent = _load(URGENT, [])

    window_ok = in_send_window()
    if not window_ok:
        log(f"Outside send window ({SEND_WINDOW_START}-{SEND_WINDOW_END}). "
            f"{'LIVE sends suppressed; drafting only.' if live_send else 'Dry-run continues.'}")

    brevo_ready = bool(os.getenv("BREVO_API_KEY") and (os.getenv("BREVO_SENDER_EMAIL")))
    can_send_email = live_send and window_ok and brevo_ready

    summary = {"mode": mode, "drafted": 0, "sent": 0, "whatsapp": 0, "skipped": 0,
               "urgent_handled": 0, "window_ok": window_ok, "brevo_ready": brevo_ready}

    # 1. Urgent follow-ups first
    if urgent:
        log(f"Handling {len(urgent)} urgent follow-up(s) first.")
        remaining_urgent = []
        for u in urgent:
            try:
                reply = gemini_client.draft(
                    f"A lead replied. Write a short, warm, helpful reply (under 70 words).\n"
                    f"Lead: {json.dumps(u)[:1200]}",
                    system=SYSTEM_PERSONA + _playbook_text(), temperature=0.6)
            except Exception as e:
                log(f"  Gemini error on urgent reply: {e}")
                remaining_urgent.append(u)
                continue
            tracker["actions"].append({
                "lead_id": u.get("id") or u.get("lead_id"), "company": u.get("company"),
                "email": u.get("email"), "channel": "email", "framework": "Reply",
                "subject": u.get("subject") or "Re: your note", "body": reply,
                "ts": _now().isoformat(), "dry_run": not can_send_email, "status": "drafted",
            })
            summary["urgent_handled"] += 1
            log(f"  Drafted reply to {u.get('company')}.")
        _save(URGENT, remaining_urgent)

    # 2. New first-touches from the top of the queue
    emailed = _already_emailed_ids(tracker)
    sent_today = _sends_today(tracker, "email")
    for lead in queue:
        if summary["drafted"] >= limit:
            break
        lid = lead.get("id")
        email = (lead.get("email") or "").strip().lower()
        if lid in emailed:
            continue
        if email and email in blocked:
            summary["skipped"] += 1
            continue
        if not email:
            continue  # email-channel first touch; mobile-only handled as WA follow-up later
        if can_send_email and sent_today >= DAILY_EMAIL_CAP:
            log(f"Daily email cap ({DAILY_EMAIL_CAP}) reached — stopping sends.")
            break

        try:
            draft = _draft_email(lead)
        except Exception as e:
            log(f"  Gemini draft failed for {lead.get('company')}: {e}")
            summary["skipped"] += 1
            continue

        action = {
            "lead_id": lid, "company": lead.get("company"), "email": email,
            "channel": "email", "framework": draft["framework"],
            "subject": draft["subject"], "body": draft["body"],
            "ts": _now().isoformat(), "dry_run": not can_send_email, "status": "drafted",
        }
        summary["drafted"] += 1
        _bump_framework(tracker, draft["framework"], "sends")

        if can_send_email:
            try:
                resp = brevo_client.send_email(email, draft["subject"], _to_html(draft["body"]),
                                               to_name=lead.get("lead_name"))
                action["status"] = "sent"
                action["message_id"] = resp.get("messageId")
                agg["sends"] = agg.get("sends", 0) + 1
                summary["sent"] += 1
                sent_today += 1
                log(f"  SENT  {draft['subject']!r} -> {email}")
            except Exception as e:
                action["status"] = "send_failed"
                action["error"] = str(e)
                log(f"  SEND FAILED -> {email}: {e}")
        else:
            agg["sends"] = agg.get("sends", 0) + 1  # count drafts as logged sends in dry-run
            log(f"  DRAFT {draft['subject']!r} -> {email} (dry-run)")

        tracker["actions"].append(action)

    # 3. WhatsApp 48h follow-ups
    wa_sent_ids = _wa_sent_ids(tracker)
    wa_today = _sends_today(tracker, "whatsapp")
    cutoff = _now() - timedelta(hours=48)
    by_lead_email = {}
    for a in tracker["actions"]:
        if a.get("channel") == "email":
            by_lead_email.setdefault(a.get("lead_id"), a)
    queue_by_id = {q.get("id"): q for q in queue}
    for lid, ea in by_lead_email.items():
        if summary["whatsapp"] >= DAILY_WHATSAPP_CAP or wa_today >= DAILY_WHATSAPP_CAP:
            break
        q = queue_by_id.get(lid)
        if not q or lid in wa_sent_ids:
            continue
        mobile = whatsapp_client.normalize_number(q.get("mobile"))
        if not mobile:
            continue
        try:
            ts = datetime.fromisoformat(ea.get("ts"))
        except Exception:
            continue
        if ts > cutoff:
            continue  # not yet 48h
        try:
            wa_msg = gemini_client.draft(
                f"Write a 2-3 sentence WhatsApp follow-up (rotate template) for {q.get('company')}, "
                f"contact {q.get('lead_name') or ''}. Casual, Hindi-English ok. One soft question.",
                system=SYSTEM_PERSONA + _playbook_text(), temperature=0.7)
        except Exception as e:
            log(f"  Gemini WA draft failed: {e}")
            continue
        wa_action = {
            "lead_id": lid, "company": q.get("company"), "mobile": mobile,
            "channel": "whatsapp", "framework": "WhatsApp 48h", "body": wa_msg,
            "ts": _now().isoformat(), "dry_run": not (live_send and window_ok), "status": "drafted",
        }
        if live_send and window_ok:
            ok, detail = whatsapp_client.send_message(mobile, wa_msg)
            wa_action["status"] = "sent" if ok else "send_failed"
            wa_action["detail"] = detail
            if not ok and "not connected" in detail.lower():
                log("  WhatsApp bridge not connected — aborting WhatsApp batch.")
                tracker["actions"].append(wa_action)
                break
            if ok:
                agg["whatsapp_sends"] = agg.get("whatsapp_sends", 0) + 1
                wa_today += 1
                time.sleep(1)  # (real cadence: 90-120s; shortened here)
        else:
            agg["whatsapp_sends"] = agg.get("whatsapp_sends", 0) + 1
        summary["whatsapp"] += 1
        tracker["actions"].append(wa_action)
        log(f"  WhatsApp follow-up {'sent' if wa_action['status']=='sent' else 'drafted'} -> {q.get('company')}")

    _save(TRACKER, tracker)
    log(f"=== SDR cycle done: {summary} ===")
    return summary


def _to_html(body):
    paras = "".join(f"<p>{p}</p>" for p in body.split("\n") if p.strip())
    return f"<div style=\"font-family:Arial,sans-serif;font-size:14px;color:#222\">{paras}</div>"


# ----------------------------- Observer cycle -----------------------------

def run_observer_cycle():
    log("=== Observer cycle start ===")
    tracker = _load(TRACKER, {})
    agg = tracker.setdefault("aggregate_stats", {})
    actions = tracker.get("actions", [])

    brevo_ready = bool(os.getenv("BREVO_API_KEY"))
    events_pulled = 0
    if brevo_ready:
        emails = {a.get("email") for a in actions
                  if a.get("channel") == "email" and a.get("status") == "sent" and a.get("email")}
        delivered = opens = clicks = bounced = 0
        for em in list(emails)[:100]:
            try:
                for ev in brevo_client.get_events(email=em, days=3):
                    e = (ev.get("event") or "").lower()
                    events_pulled += 1
                    if e in ("delivered",):
                        delivered += 1
                    elif e in ("opened", "uniqueopened", "open"):
                        opens += 1
                    elif e in ("click", "clicks"):
                        clicks += 1
                    elif "bounce" in e or e in ("hardbounce", "softbounce"):
                        bounced += 1
            except Exception as e:
                log(f"  Brevo events error for {em}: {e}")
        if events_pulled:
            agg["delivered"] = delivered
            agg["opens"] = opens
            agg["clicks"] = clicks
            agg["bounced"] = bounced
        log(f"  Pulled {events_pulled} Brevo events (delivered={delivered}, opens={opens}, "
            f"clicks={clicks}, bounced={bounced}).")
    else:
        log("  Brevo not configured — skipping delivery-event pull.")

    _save(TRACKER, tracker)

    # Regenerate the dashboard so the public mirror reflects the latest stats.
    try:
        import generate_dashboard
        generate_dashboard.main()
        log("  Dashboard regenerated.")
    except Exception as e:
        log(f"  Dashboard regen failed: {e}")

    log("=== Observer cycle done ===")
    return {"events_pulled": events_pulled, "brevo_ready": brevo_ready}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "sdr"
    live = "--live" in sys.argv
    if which == "observer":
        print(run_observer_cycle())
    else:
        print(run_sdr_cycle(live_send=live))
