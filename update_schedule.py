"""Compute and persist today's SDR + Observer cron schedule.

Called:
  - Once after /loop jobs are created (so the dashboard reflects the plan)
  - Every SDR cycle (to update "Next batch" preview and remaining-budget)
  - Every Observer cycle (to tick last_observer_run + recompute cycle slots)

Writes to sdr_schedule.json in the project root.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
PROJECT = "/Users/dhirajchalse/Code/Agentic-SDR"

# --- Fixed config (change here if cadence changes) ---
CONFIG = {
    "outreach_window": {"start": "11:00", "end": "19:30", "tz": "Asia/Kolkata"},
    "daily_email_cap": 300,
    "sdr_interval_min": 30,
    "observer_interval_hr": 3,
    "emails_per_cycle_target": 17,  # ~300 / 18 active cycles
    "wa_per_cycle_max": 15,
}


def ist_now():
    return datetime.now(IST)


def plan_sdr_cycles(now_ist):
    """Compute today's SDR cycle times within 11:00-19:30 IST."""
    day = now_ist.date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=11, minute=0)
    end = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=19, minute=30)
    cycles = []
    t = start
    while t <= end:
        cycles.append(t)
        t += timedelta(minutes=CONFIG["sdr_interval_min"])
    return cycles


def plan_observer_cycles(now_ist):
    """Observer: every 3h, 24/7. 8 slots per day starting at a stable offset."""
    day = now_ist.date()
    slots = []
    # Anchor at 01:30 IST, every 3h → 01:30, 04:30, 07:30, 10:30, 13:30, 16:30, 19:30, 22:30
    anchor = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=1, minute=30)
    for i in range(8):
        slots.append(anchor + timedelta(hours=3 * i))
    return slots


def compute_today_schedule():
    now = ist_now()
    try:
        with open(f"{PROJECT}/outreach_tracker.json") as f:
            tracker = json.load(f)
    except FileNotFoundError:
        tracker = {}
        
    meta = tracker.get("meta", {})

    # Reset daily counter if today rolled over
    today_str = now.strftime("%Y-%m-%d")
    if meta.get("today_date") != today_str:
        emails_sent_today = 0
    else:
        emails_sent_today = meta.get("emails_sent_today", 0)

    # Try to peek upcoming queue (top of qualified_leads.json minus already-touched)
    try:
        with open(f"{PROJECT}/qualified_leads.json") as f:
            queue = json.load(f)
    except FileNotFoundError:
        queue = []

    touched = set(tracker.get("leads", {}).keys())
    try:
        with open(f"{PROJECT}/blocked_leads.json") as f:
            blocked = set(json.load(f))
    except FileNotFoundError:
        blocked = set()

    remaining_queue = [q for q in queue if q["id"] not in touched and q["id"] not in blocked]
    remaining_budget = max(0, CONFIG["daily_email_cap"] - emails_sent_today)

    # Honor weekend pause + tracker.meta.send_pause_until — zero-out planned sends
    pause_until = meta.get("send_pause_until")
    is_weekend = now.weekday() >= 5  # Sat=5, Sun=6
    paused = is_weekend or (pause_until and today_str < pause_until)
    if paused:
        remaining_budget = 0

    # Plan cycles
    sdr_cycles = plan_sdr_cycles(now)
    obs_cycles = plan_observer_cycles(now)

    # For each upcoming SDR cycle, preview the first N leads (N = emails_per_cycle_target)
    past = [c for c in sdr_cycles if c <= now]
    future = [c for c in sdr_cycles if c > now]

    per_cycle = CONFIG["emails_per_cycle_target"]
    cycle_plan = []
    cursor = 0
    total_planned = min(remaining_budget, len(remaining_queue), len(future) * per_cycle)
    for slot in future:
        if cursor >= total_planned:
            cycle_plan.append({"fire_at": slot.isoformat(), "planned_count": 0, "preview": []})
            continue
        end = min(cursor + per_cycle, total_planned)
        batch = remaining_queue[cursor:end]
        cycle_plan.append({
            "fire_at": slot.isoformat(),
            "planned_count": len(batch),
            "preview": [
                {
                    "id": b["id"],
                    "name": b.get("lead_name"),
                    "company": b.get("company"),
                    "email": b.get("email"),
                    "personal_email": b.get("personal_email", False),
                    "priority_score": b.get("priority_score", 0),
                }
                for b in batch[:5]  # show first 5 per cycle in dashboard preview
            ],
            "full_batch_ids": [b["id"] for b in batch],
        })
        cursor = end

    schedule = {
        "generated_at": now.isoformat(),
        "date_ist": today_str,
        "config": CONFIG,
        "outreach_window_ist": {
            "start": datetime.combine(now.date(), datetime.min.time(), tzinfo=IST).replace(hour=11, minute=0).isoformat(),
            "end": datetime.combine(now.date(), datetime.min.time(), tzinfo=IST).replace(hour=19, minute=30).isoformat(),
        },
        "email_budget": {
            "daily_cap": CONFIG["daily_email_cap"],
            "sent_today": emails_sent_today,
            "remaining": remaining_budget,
        },
        "queue_size_remaining": len(remaining_queue),
        "sdr_cycles": {
            "interval_minutes": CONFIG["sdr_interval_min"],
            "past_today": [c.isoformat() for c in past],
            "upcoming_today": [c.isoformat() for c in future],
            "planned_batches": cycle_plan,
        },
        "observer_cycles": {
            "interval_hours": CONFIG["observer_interval_hr"],
            "all_slots_today": [c.isoformat() for c in obs_cycles],
            "past_today": [c.isoformat() for c in obs_cycles if c <= now],
            "upcoming_today": [c.isoformat() for c in obs_cycles if c > now],
        },
        "loop_commands": {
            "sdr": "/loop 45m sdr-cycle",
            "observer": "/loop 3h observer-cycle",
        },
        "active_crons": [
            {
                "id": "b9c369be",
                "role": "SDR cycle",
                "cron": "3,48 11-19 * * *",
                "cron_tz": "Asia/Kolkata",
                "fires_per_day": 18,
                "effective_cycles_per_day": "~13 (after 40-min dedup)",
                "window_enforced": "11:00-19:30 IST (guard inside cycle)",
                "scope": "session-only (resets when Claude Code restarts)",
                "created_at": now.isoformat(),
                "auto_expires": "7 days from creation",
            },
            {
                "id": "3813226d",
                "role": "Observer cycle",
                "cron": "17 */3 * * *",
                "cron_tz": "Asia/Kolkata",
                "fires_per_day": 8,
                "effective_cycles_per_day": 8,
                "window_enforced": "24/7 (no restriction)",
                "scope": "session-only (resets when Claude Code restarts)",
                "created_at": now.isoformat(),
                "auto_expires": "7 days from creation",
            },
        ],
    }

    with open(f"{PROJECT}/sdr_schedule.json", "w") as f:
        json.dump(schedule, f, indent=2)

    return schedule


if __name__ == "__main__":
    s = compute_today_schedule()
    print(f"Schedule written. Window: {s['outreach_window_ist']['start']} to {s['outreach_window_ist']['end']}")
    print(f"Budget: {s['email_budget']['remaining']}/{s['email_budget']['daily_cap']} remaining")
    print(f"SDR cycles today: {len(s['sdr_cycles']['past_today']) + len(s['sdr_cycles']['upcoming_today'])} total, {len(s['sdr_cycles']['upcoming_today'])} upcoming")
    print(f"Observer cycles today: {len(s['observer_cycles']['all_slots_today'])} total, {len(s['observer_cycles']['upcoming_today'])} upcoming")
    print(f"Planned sends across upcoming cycles: {sum(b['planned_count'] for b in s['sdr_cycles']['planned_batches'])}")
