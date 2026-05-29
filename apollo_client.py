"""Apollo.io client with a hard credit-safety gate.

Design contract:
- Every process must call `get_credit_balance()` before any enrichment call.
- Every enrichment call must pass through `enrich_bulk()`, which refuses to
  proceed unless balance was checked AND requested_count + reserve <= balance.
- Phone reveals are hard-disabled at the call site (direct_dial credits are 0
  on the configured Apollo account; we never want to be billed for them).

Tenant resolution: set AGENTIC_SDR_TENANT=<slug> in the environment. The
client loads tenants/<slug>/.env (overriding any repo-root .env) so multi-
tenant operation never mixes credentials.
"""

import json
import os
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

BASE_URL = os.getenv("APOLLO_BASE_URL", "https://api.apollo.io/api/v1").rstrip("/")
API_KEY = os.getenv("APOLLO_API_KEY")
LEAD_CREDIT_RESERVE = int(os.getenv("APOLLO_LEAD_CREDIT_RESERVE", "500"))

if not API_KEY:
    raise RuntimeError(
        "APOLLO_API_KEY not set. Set AGENTIC_SDR_TENANT and ensure "
        "tenants/<slug>/.env contains APOLLO_API_KEY."
    )

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "x-api-key": API_KEY,
}


class CreditGateError(RuntimeError):
    """Raised when an enrichment call is attempted without a fresh balance check
    or when projected cost exceeds the available balance + reserve."""


# Process-local cache of the last credit balance snapshot. Set by get_credit_balance().
# enrich_bulk() refuses to proceed if this is None or stale (> _BALANCE_TTL seconds).
_BALANCE_TTL = 600  # 10 minutes
_last_balance: dict | None = None


def _request(method: str, path: str, **kwargs):
    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = requests.request(method, url, headers=HEADERS, timeout=30, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"Apollo {method} {path} -> {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def get_credit_balance() -> dict:
    """Fetch live credit balance. Must be called before any enrichment.

    Returns a dict like:
      {
        "lead_credit": {"limit": 19290, "consumed": 1668, "left_over": 17622},
        "direct_dial_credit": {...},
        "export_credit": {...},
        "ai_credit": {...},
        "cycle_start": "...",
        "cycle_end": "...",
        "fetched_at": <epoch>,
      }
    """
    global _last_balance
    raw = _request("POST", "usage_stats/credit_usage_stats", json={})
    stats = raw["credit_usage_stats"]
    cycle = raw["current_credit_cycle"]
    snapshot = {
        **stats,
        "cycle_start": cycle["start_date"],
        "cycle_end": cycle["end_date"],
        "fetched_at": time.time(),
    }
    _last_balance = snapshot
    return snapshot


def assert_can_spend_lead_credits(n: int) -> None:
    """Hard gate. Raises CreditGateError if a recent balance check is missing
    or the projected spend would dip below the reserve."""
    if _last_balance is None:
        raise CreditGateError(
            "Credit balance not checked in this process. "
            "Call get_credit_balance() before any enrichment."
        )
    age = time.time() - _last_balance["fetched_at"]
    if age > _BALANCE_TTL:
        raise CreditGateError(
            f"Balance check is stale ({age:.0f}s > {_BALANCE_TTL}s). "
            "Re-call get_credit_balance() before enriching."
        )
    left = _last_balance["lead_credit"]["left_over"]
    if n + LEAD_CREDIT_RESERVE > left:
        raise CreditGateError(
            f"Projected cost {n} + reserve {LEAD_CREDIT_RESERVE} = {n + LEAD_CREDIT_RESERVE} "
            f"exceeds lead_credit.left_over={left}. Refusing to enrich."
        )


def enrich_bulk(rows: list[dict]) -> list[dict]:
    """Bulk-enrich up to 10 people per call via /people/bulk_match.

    Each row must include enough identifying info: email OR (first_name +
    last_name + (domain OR organization_name)). Phones are NOT requested.

    Apollo charges 1 lead_credit per successful email reveal. We gate on
    worst-case (1 credit per row).
    """
    if not rows:
        return []
    if len(rows) > 10:
        raise ValueError("Apollo bulk_match accepts at most 10 records per call. Batch upstream.")
    assert_can_spend_lead_credits(len(rows))

    payload = {
        "reveal_personal_emails": True,
        "reveal_phone_number": False,  # direct_dial credits are 0; do not request
        "details": rows,
    }
    resp = _request("POST", "people/bulk_match", json=payload)
    return resp.get("matches", []) or []


def list_email_accounts() -> list[dict]:
    """Returns mailboxes connected to this Apollo workspace. Use this to
    discover the APOLLO_EMAIL_ACCOUNT_ID value for the tenant .env."""
    resp = _request("GET", "email_accounts")
    return resp.get("email_accounts", resp) if isinstance(resp, dict) else resp


def add_contacts_to_campaign(campaign_id: str, contact_ids: list[str], email_account_id: str,
                             send_email_from_email_account_id: str | None = None) -> dict:
    """Adds Apollo contact ids to an existing emailer_campaign. Apollo doesn't
    expose stateless one-off sends — every send rides a campaign. Create one
    in the Apollo UI, drop its id in APOLLO_CAMPAIGN_ID, then push contacts in.
    """
    payload = {
        "campaign_id": campaign_id,
        "contact_ids": contact_ids,
        "send_email_from_email_account_id": send_email_from_email_account_id or email_account_id,
        "emailer_campaign_id": campaign_id,
    }
    return _request("POST", "emailer_campaigns/add_contact_ids", json=payload)


def create_contact(person: dict) -> dict:
    """Create an Apollo contact from an enriched person payload. Returns the
    created contact (with `id`) which can then be pushed into a campaign."""
    return _request("POST", "contacts", json=person)


def smoke_test() -> None:
    """Hits auth/health + credit_usage_stats. Safe to call anytime."""
    health = _request("GET", "auth/health")
    print("auth/health ->", json.dumps(health))
    balance = get_credit_balance()
    print("lead_credit.left_over ->", balance["lead_credit"]["left_over"])
    print("direct_dial_credit.left_over ->", balance["direct_dial_credit"]["left_over"])
    print("export_credit.left_over ->", balance["export_credit"]["left_over"])
    print("cycle ->", balance["cycle_start"], "→", balance["cycle_end"])


if __name__ == "__main__":
    smoke_test()
