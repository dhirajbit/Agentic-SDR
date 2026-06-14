"""Unit tests for cloud_normalize against both tenants' divergent action schemas.

Run: python tests/test_normalize.py   (no pytest / DB / crypto deps required)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cloud_normalize import normalize_action, parse_timestamp  # noqa: E402


def test_parse_timestamps():
    # abhiyanta "... IST"
    dt = parse_timestamp("2026-06-02 16:12 IST")
    assert dt.year == 2026 and dt.hour == 16 and dt.minute == 12
    assert dt.utcoffset().total_seconds() == 5.5 * 3600
    # ISO (best-roadways)
    dt2 = parse_timestamp("2026-06-02T16:12:00")
    assert dt2.year == 2026 and dt2.hour == 16
    # date only
    assert parse_timestamp("2026-05-28").year == 2026
    # junk / empty -> epoch
    assert parse_timestamp(None).year == 1970
    assert parse_timestamp("not a date").year == 1970
    print("ok parse_timestamps")


def test_abhiyanta_shape():
    raw = {
        "at": "2026-06-02 16:12 IST", "lead_row_id": 1,
        "company": "Shilpa Steel", "contact": "Vijay Supare",
        "email": "vijay@shilpatl.com", "apollo_contact_id": "abc123",
        "channel": "email", "framework": "A", "subject": "SAP at Shilpa",
        "apollo_status": "completed",
    }
    a = normalize_action("abhiyanta-tech", raw)
    assert a["channel"] == "email"
    assert a["recipient"] == "vijay@shilpatl.com"
    assert a["status"] == "completed"
    assert a["message_id"] == "abc123"
    assert a["company"] == "Shilpa Steel"
    assert a["source_key"].startswith("abhiyanta-tech:1:")
    assert isinstance(a["occurred_at"], datetime)
    print("ok abhiyanta_shape")


def test_best_roadways_shape():
    raw = {
        "ts": "2026-06-02T16:12:00", "lead_id": "L-9", "company": "Acme",
        "mobile": "919876543210", "channel": "whatsapp", "framework": "WhatsApp 48h",
        "body": "hi there", "dry_run": True, "status": "drafted", "message_id": "wamid.X",
    }
    a = normalize_action("best-roadways", raw)
    assert a["channel"] == "whatsapp"
    assert a["recipient"] == "919876543210"
    assert a["status"] == "drafted"
    assert a["dry_run"] is True
    assert a["body"] == "hi there"
    assert a["message_id"] == "wamid.X"
    assert a["source_key"].startswith("best-roadways:L-9:")
    print("ok best_roadways_shape")


def test_channel_defaults_email():
    a = normalize_action("x", {"at": "2026-01-01", "lead_row_id": 2, "email": "a@b.com"})
    assert a["channel"] == "email"
    print("ok channel_defaults_email")


def test_real_tracker_files_parse():
    """Every action in the real tenant trackers must normalize without error."""
    total = 0
    for slug in ("abhiyanta-tech", "best-roadways"):
        p = REPO_ROOT / "tenants" / slug / "outreach_tracker.json"
        if not p.exists():
            continue
        tracker = json.loads(p.read_text())
        for raw in tracker.get("actions", []):
            a = normalize_action(slug, raw)
            assert a["source_key"] and a["occurred_at"] and a["channel"]
            total += 1
    print(f"ok real_tracker_files_parse ({total} actions)")


if __name__ == "__main__":
    test_parse_timestamps()
    test_abhiyanta_shape()
    test_best_roadways_shape()
    test_channel_defaults_email()
    test_real_tracker_files_parse()
    print("\nALL PASSED")
