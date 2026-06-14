"""Sync layer between the local SDR workers and the hosted Neon Postgres that
backs the Vercel app. Push-only for state; pull+decrypt for secrets; a command
queue for web->worker control.

Connection: set NEON_DATABASE_URL in repo-root .env (pooled -pooler Neon string).
Run health/push from cloud_agent.py.
"""

import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

import cloud_keys
from cloud_normalize import normalize_action, normalize_credit_snapshot

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

DB_URL = os.getenv("NEON_DATABASE_URL")

_conn: psycopg.Connection | None = None


def conn() -> psycopg.Connection:
    """Lazy, auto-reconnecting connection (autocommit)."""
    global _conn
    if not DB_URL:
        raise RuntimeError("NEON_DATABASE_URL not set in repo-root .env.")
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(DB_URL, autocommit=True)
    return _conn


def _tenant_dir(slug: str) -> Path:
    return REPO_ROOT / "tenants" / slug


def _load(slug: str, name: str, default):
    p = _tenant_dir(slug) / name
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return default


def get_tenant_id(slug: str) -> str | None:
    with conn().cursor() as cur:
        cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return str(row[0]) if row else None


# --------------------------------------------------------------------------- #
# Keys + heartbeat
# --------------------------------------------------------------------------- #

def publish_public_key(slug: str) -> bool:
    """Generate (if needed) and publish this tenant's worker public key. Returns
    False if the tenant row doesn't exist yet (web onboarding not done)."""
    pub = cloud_keys.ensure_keypair(slug)
    with conn().cursor() as cur:
        cur.execute(
            "UPDATE tenants SET worker_public_key = %s WHERE slug = %s", (pub, slug)
        )
        return cur.rowcount > 0


def heartbeat(slug: str) -> None:
    with conn().cursor() as cur:
        cur.execute("UPDATE tenants SET worker_last_seen_at = now() WHERE slug = %s", (slug,))


# --------------------------------------------------------------------------- #
# State push
# --------------------------------------------------------------------------- #

def push_tracker(slug: str) -> int:
    """Upsert all tracker actions + credit snapshots. Returns # actions upserted."""
    tid = get_tenant_id(slug)
    if not tid:
        return 0
    tracker = _load(slug, "outreach_tracker.json", {})
    n = 0
    with conn().cursor() as cur:
        for raw in tracker.get("actions", []):
            a = normalize_action(slug, raw)
            cur.execute(
                """
                INSERT INTO actions
                  (tenant_id, source_key, channel, company, recipient, framework,
                   subject, body, message_id, chat_id, status, dry_run, events, occurred_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id, source_key) DO UPDATE SET
                  status = EXCLUDED.status,
                  events = EXCLUDED.events,
                  message_id = EXCLUDED.message_id,
                  body = EXCLUDED.body
                """,
                (
                    tid, a["source_key"], a["channel"], a["company"], a["recipient"],
                    a["framework"], a["subject"], a["body"], a["message_id"], a["chat_id"],
                    a["status"], a["dry_run"], Jsonb(a["events"]), a["occurred_at"],
                ),
            )
            n += 1
        for raw in tracker.get("credit_snapshots", []):
            c = normalize_credit_snapshot(raw)
            cur.execute(
                """
                INSERT INTO credit_snapshots
                  (tenant_id, at, label, lead_credit_left, direct_dial_credit_left,
                   export_credit_left, cycle_start, cycle_end)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
                """,
                (
                    tid, c["at"], c["label"], c["lead_credit_left"],
                    c["direct_dial_credit_left"], c["export_credit_left"],
                    c["cycle_start"], c["cycle_end"],
                ),
            )
    return n


def _external_id(lead: dict, fallback: int) -> str:
    for k in ("id", "lead_id", "apollo_id", "apollo_contact_id", "email_id", "email"):
        if lead.get(k):
            return str(lead[k])
    return f"row-{fallback}"


def push_leads_counts(slug: str) -> dict:
    """Replace the leads set per status from the tenant JSON queues."""
    tid = get_tenant_id(slug)
    if not tid:
        return {}
    sources = {
        "queued": _load(slug, "qualified_leads.json", []),
        "blocked": _load(slug, "blocked_leads.json", []),
        "urgent": _load(slug, "urgent_followups.json", []),
    }
    counts = {}
    with conn().cursor() as cur:
        for status, rows in sources.items():
            cur.execute("DELETE FROM leads WHERE tenant_id = %s AND status = %s", (tid, status))
            for i, lead in enumerate(rows if isinstance(rows, list) else []):
                if not isinstance(lead, dict):
                    continue
                cur.execute(
                    """
                    INSERT INTO leads (tenant_id, external_id, company, email, mobile, status, payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id, external_id, status) DO UPDATE SET
                      company = EXCLUDED.company, email = EXCLUDED.email,
                      mobile = EXCLUDED.mobile, payload = EXCLUDED.payload, updated_at = now()
                    """,
                    (
                        tid, _external_id(lead, i),
                        lead.get("company") or lead.get("company_name"),
                        lead.get("email") or lead.get("email_id"),
                        lead.get("mobile") or lead.get("mobile_no"),
                        status, Jsonb(lead),
                    ),
                )
            counts[status] = len(rows) if isinstance(rows, list) else 0
    return counts


def push_cycle_run(slug, kind, status, *, run_id=None, trigger=None,
                   summary=None, log=None, command_id=None) -> str | None:
    """Insert a new cycle_run (run_id=None) or update an existing one."""
    tid = get_tenant_id(slug)
    if not tid:
        return None
    with conn().cursor() as cur:
        if run_id is None:
            cur.execute(
                """
                INSERT INTO cycle_runs (tenant_id, kind, status, trigger, command_id, started_at)
                VALUES (%s,%s,%s,%s,%s, now()) RETURNING id
                """,
                (tid, kind, status, trigger, command_id),
            )
            return str(cur.fetchone()[0])
        cur.execute(
            """
            UPDATE cycle_runs SET status=%s,
              summary=COALESCE(%s, summary), log=COALESCE(%s, log),
              finished_at = CASE WHEN %s IN ('done','error') THEN now() ELSE finished_at END
            WHERE id=%s AND tenant_id=%s
            """,
            (status, Jsonb(summary) if summary is not None else None, log, status, run_id, tid),
        )
        return run_id


def push_integration_status(slug, provider, status, detail=None) -> None:
    """Upsert ONLY non-secret status fields (never touches ciphertext/config)."""
    tid = get_tenant_id(slug)
    if not tid:
        return
    with conn().cursor() as cur:
        cur.execute(
            """
            INSERT INTO integrations (tenant_id, provider, status, status_detail, last_checked_at)
            VALUES (%s,%s,%s,%s, now())
            ON CONFLICT (tenant_id, provider) DO UPDATE SET
              status = EXCLUDED.status, status_detail = EXCLUDED.status_detail,
              last_checked_at = now(), updated_at = now()
            """,
            (tid, provider, status, Jsonb(detail or {})),
        )


# --------------------------------------------------------------------------- #
# Secrets pull + apply
# --------------------------------------------------------------------------- #

def pull_integration_secrets(slug: str) -> dict:
    """Return {provider: {field: value, ...non-secret config}} with secrets
    decrypted via the local private key."""
    tid = get_tenant_id(slug)
    if not tid:
        return {}
    out: dict[str, dict] = {}
    with conn().cursor() as cur:
        cur.execute(
            "SELECT provider, config, secrets_ciphertext FROM integrations WHERE tenant_id = %s",
            (tid,),
        )
        for provider, config, ciphertext in cur.fetchall():
            merged = dict(config or {})
            for field, ct in (ciphertext or {}).items():
                try:
                    merged[field] = cloud_keys.decrypt_secret(slug, ct)
                except Exception as exc:  # noqa: BLE001 — surface but don't crash the loop
                    merged[f"_error_{field}"] = str(exc)
            out[provider] = merged
    return out


def apply_secrets_to_env(slug: str, decrypted: dict) -> None:
    """Write decrypted integration values into tenants/<slug>/.env so the existing
    clients (which already load_dotenv that file) pick them up."""
    env_path = _tenant_dir(slug) / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    kv = {}
    for provider_vals in decrypted.values():
        for k, v in provider_vals.items():
            if k.startswith("_error_"):
                continue
            kv[k] = v
    # Update in place, then append any new keys.
    seen = set()
    for i, line in enumerate(lines):
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in kv:
                lines[i] = f"{key}={kv[key]}"
                seen.add(key)
    for k, v in kv.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    env_path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Command queue
# --------------------------------------------------------------------------- #

def claim_command(slug: str) -> dict | None:
    """Atomically claim the oldest pending command (FOR UPDATE SKIP LOCKED)."""
    tid = get_tenant_id(slug)
    if not tid:
        return None
    c = conn()
    with c.transaction(), c.cursor() as cur:
        cur.execute(
            """
            SELECT id, type, args FROM commands
            WHERE tenant_id = %s AND status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED LIMIT 1
            """,
            (tid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cmd_id = row[0]
        cur.execute(
            "UPDATE commands SET status='claimed', claimed_at=now() WHERE id=%s", (cmd_id,)
        )
        return {"id": str(cmd_id), "type": row[1], "args": row[2] or {}}


def complete_command(cmd_id: str, status: str, result: dict | None = None) -> None:
    with conn().cursor() as cur:
        cur.execute(
            "UPDATE commands SET status=%s, finished_at=now(), result=%s WHERE id=%s",
            (status, Jsonb(result or {}), cmd_id),
        )


def get_settings(slug: str) -> dict:
    tid = get_tenant_id(slug)
    if not tid:
        return {"live_send": False, "auto_loop": False}
    with conn().cursor() as cur:
        cur.execute("SELECT live_send, auto_loop FROM settings WHERE tenant_id = %s", (tid,))
        row = cur.fetchone()
        return {"live_send": bool(row[0]), "auto_loop": bool(row[1])} if row else {
            "live_send": False, "auto_loop": False
        }
