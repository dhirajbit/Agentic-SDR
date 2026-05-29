# Abhiyanta Tech — Agentic SDR tenant

Apollo-powered SDR tenant for [Abhiyanta Tech](https://abhiyantatech.com/) (SAP implementation + AMS partner).

## Activation checklist

0. From the repo root, activate this tenant (one-time per session):
   ```
   bin/tenant abhiyanta-tech
   export AGENTIC_SDR_TENANT=abhiyanta-tech
   ```
   Then **restart Claude Code** so it picks up `.mcp.json` and loads the tenant's MCP servers (currently: `zoho-crm-data-operations`). Other tenants' MCP servers will NOT load.

1. Confirm `company_config.json` → fill `sender.name` and `sender.email`. `sender.email` MUST match a mailbox that is connected inside Apollo (see `apollo_client.list_email_accounts()`).
2. Set `APOLLO_EMAIL_ACCOUNT_ID` and `APOLLO_CAMPAIGN_ID` in `.env` (one-step emailer campaign in Apollo titled "Agentic SDR - Abhiyanta Tech").
3. Drop the source list at `tenants/abhiyanta-tech/leads.csv`. Minimum columns: `first_name`, `last_name`, `company_name`, `domain` (or `website`). `email_id`, `job_title`, `linkedin_url` if you have them.
4. From the repo root, run:
   ```
   AGENTIC_SDR_TENANT=abhiyanta-tech python sync_leads.py
   ```
   This will:
   - print the current Apollo `lead_credit` balance,
   - print the worst-case credit cost for the CSV row count,
   - **refuse to proceed unless** balance ≥ cost + `APOLLO_LEAD_CREDIT_RESERVE`,
   - prompt for explicit `yes` confirmation before any /people/bulk_match call.
5. After enrichment lands in `enriched_leads.json`, run `qualify_leads.py` then `merge_verdicts.py` to produce the prioritised `qualified_leads.json` for the SDR loop.

## Live constraints (Apollo account, 2026-05-28 snapshot)

| Credit | Left |
|---|---|
| `lead_credit` (used by /people/match) | **17,622** |
| `direct_dial_credit` (phones) | **0** — phone reveals are disabled |
| `export_credit` | **0** — no /people/search exports |

Cycle resets **2026-06-03**.

## Tenant MCP servers

This tenant's `.mcp.json` registers the Zoho CRM MCP for Abhiyanta Tech. It is intentionally NOT in your global Claude Code config — it only loads when this tenant is activated via `bin/tenant abhiyanta-tech`.

The Zoho MCP URL embeds a session token, so `tenants/*/.mcp.json` is gitignored along with the root `.mcp.json` symlink. If you rotate the Zoho key, update `tenants/abhiyanta-tech/.mcp.json` directly.

## Daily caps

`.env` ships with `APOLLO_DAILY_SEND_CAP=80`. The SDR loop respects this — once 80 sends are logged in `outreach_tracker.json` for the local date, no further sends until midnight.
