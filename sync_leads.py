"""Ingest tenants/<slug>/leads.csv and enrich it via Apollo /people/bulk_match.

Hard-gated by credit safety:
  1. Fetches live Apollo lead_credit balance.
  2. Prints worst-case spend (1 credit per CSV row).
  3. Refuses to proceed unless balance - reserve >= cost AND operator types `yes`.

Set AGENTIC_SDR_TENANT=<slug> before running. The tenant folder must exist
under tenants/<slug>/ and contain a leads.csv.

Expected CSV headers (at minimum one identifying combo per row):
  - email_id                            (best — Apollo matches on email directly)
  - first_name, last_name, domain       (or)
  - first_name, last_name, company_name
Optional: job_title, linkedin_url, mobile_no, city, state, country, annual_revenue,
no_of_employees, website, company_linkedin.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import apollo_client

REPO_ROOT = Path(__file__).resolve().parent

TENANT = os.getenv("AGENTIC_SDR_TENANT")
if not TENANT:
    sys.exit("AGENTIC_SDR_TENANT not set. Example: AGENTIC_SDR_TENANT=abhiyanta-tech python sync_leads.py")

TENANT_DIR = REPO_ROOT / "tenants" / TENANT
if not TENANT_DIR.is_dir():
    sys.exit(f"Tenant folder not found: {TENANT_DIR}")

CSV_PATH = TENANT_DIR / "leads.csv"
ENRICHED_PATH = TENANT_DIR / "enriched_leads.json"
TRACKER_PATH = TENANT_DIR / "outreach_tracker.json"


def _read_csv() -> list[dict]:
    if not CSV_PATH.exists():
        sys.exit(
            f"No leads.csv at {CSV_PATH}. Drop your source list there with at least "
            "first_name,last_name,company_name (or domain) per row."
        )
    with CSV_PATH.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{CSV_PATH} has a header but no data rows.")
    return rows


def _to_apollo_detail(row: dict) -> dict:
    """Map a CSV row to an Apollo /people/bulk_match `details[i]` entry."""
    detail = {}
    if row.get("email_id"):
        detail["email"] = row["email_id"].strip()
    if row.get("first_name"):
        detail["first_name"] = row["first_name"].strip()
    if row.get("last_name"):
        detail["last_name"] = row["last_name"].strip()
    domain = (row.get("domain") or row.get("website") or "").strip()
    if domain:
        # Apollo accepts bare domain; strip protocol if present.
        for prefix in ("https://", "http://", "www."):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        detail["domain"] = domain.split("/")[0]
    if row.get("company_name") and "domain" not in detail:
        detail["organization_name"] = row["company_name"].strip()
    if row.get("linkedin_url"):
        detail["linkedin_url"] = row["linkedin_url"].strip()
    return detail


def _confirm_or_exit(prompt: str) -> None:
    if os.getenv("AGENTIC_SDR_AUTO_CONFIRM") == "yes":
        print(f"[auto-confirm] {prompt} -> yes")
        return
    answer = input(prompt).strip().lower()
    if answer != "yes":
        sys.exit("Aborted by operator. No Apollo credits spent.")


def _append_credit_snapshot(balance: dict, label: str) -> None:
    tracker = json.loads(TRACKER_PATH.read_text())
    tracker.setdefault("credit_snapshots", []).append({
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": label,
        "lead_credit_left": balance["lead_credit"]["left_over"],
        "direct_dial_credit_left": balance["direct_dial_credit"]["left_over"],
        "export_credit_left": balance["export_credit"]["left_over"],
    })
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2))


def main() -> None:
    rows = _read_csv()
    row_count = len(rows)
    print(f"Loaded {row_count} rows from {CSV_PATH}")

    # ── Credit-safety gate ────────────────────────────────────────────────
    print("\nChecking live Apollo credit balance...")
    balance = apollo_client.get_credit_balance()
    lead_left = balance["lead_credit"]["left_over"]
    reserve = apollo_client.LEAD_CREDIT_RESERVE

    print(f"  lead_credit.left_over   : {lead_left}")
    print(f"  reserve (env)           : {reserve}")
    print(f"  cycle                   : {balance['cycle_start']} → {balance['cycle_end']}")
    print(f"  worst-case cost (1/row) : {row_count}")
    print(f"  balance after worst case: {lead_left - row_count}")

    if row_count + reserve > lead_left:
        sys.exit(
            f"\nABORT: worst-case cost {row_count} + reserve {reserve} exceeds "
            f"lead_credit.left_over={lead_left}. Reduce CSV size or top up Apollo credits."
        )

    _append_credit_snapshot(balance, f"pre-enrichment ({row_count} rows queued)")

    _confirm_or_exit(
        f"\nProceed to enrich {row_count} rows (worst case {row_count} credits)? "
        "Type 'yes' to continue: "
    )

    # ── Enrich in batches of 10 ───────────────────────────────────────────
    enriched = []
    misses = 0
    for i in range(0, row_count, 10):
        batch = rows[i:i + 10]
        details = [_to_apollo_detail(r) for r in batch]
        details = [d for d in details if d]
        if not details:
            continue
        print(f"  enrich batch {i // 10 + 1} ({len(details)} rows)...", end=" ", flush=True)
        try:
            matches = apollo_client.enrich_bulk(details)
        except Exception as exc:
            print(f"FAIL: {exc}")
            break
        for src, match in zip(batch, matches):
            if match:
                enriched.append({"source_row": src, "apollo": match})
            else:
                misses += 1
        print(f"matched {len([m for m in matches if m])}/{len(details)}")

    ENRICHED_PATH.write_text(json.dumps(enriched, indent=2))
    print(f"\nWrote {len(enriched)} enriched records to {ENRICHED_PATH} (misses: {misses})")

    # Re-check balance to log actual spend.
    print("\nRe-checking balance to record actual spend...")
    post = apollo_client.get_credit_balance()
    spent = lead_left - post["lead_credit"]["left_over"]
    print(f"  lead_credit consumed by this run: {spent}")
    _append_credit_snapshot(post, f"post-enrichment (spent {spent})")


if __name__ == "__main__":
    main()
