# Best Roadways — Agentic SDR tenant

Outbound SDR tenant for [Best Roadways Limited](https://bestroadways.com/) — India's
trusted road-freight partner since 1985. This tenant runs on **ERPNext + Brevo +
WhatsApp + Gemini** (not Apollo). Best Roadways configures all of its own keys.

> Operating instructions live in **`SDR_GUIDE.md`** (this tenant overrides the
> Apollo-specific repo-root `CLAUDE.md`). Messaging strategy lives in
> **`strategy_playbook.md`** (Bolti email frameworks + kstars WhatsApp cadence).

## Activation checklist

1. **Activate the tenant** (one-time per session, from repo root):
   ```
   bin/tenant best-roadways
   export AGENTIC_SDR_TENANT=best-roadways
   ```
   Then **restart Claude Code** so it loads this tenant's MCP servers (WhatsApp).
2. **Configure secrets** — `cp .env.example .env` and fill in:
   - `ERPNEXT_URL`, `ERPNEXT_API_KEY`, `ERPNEXT_API_SECRET`
   - `BREVO_API_KEY`, `BREVO_SENDER_NAME`, `BREVO_SENDER_EMAIL` (sender verified in Brevo)
   - `GEMINI_API_KEY` (to be provided)
   `CLOUDFLARE_*` are pre-filled so the dashboard can already deploy.
3. **Confirm `company_config.json`** — fill `sender.name` / `sender.email`.
4. **Drop the lead list** at `leads.csv` (keep the header row), and/or connect ERPNext.
5. **Build the queue**:
   ```
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/sync_leads.py
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/qualify_leads.py
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/merge_verdicts.py
   ```
6. **WhatsApp follow-ups** — start the bridge under repo `whatsapp-mcp/whatsapp-bridge/` and scan the QR (re-auth ~every 20 days).
7. **Start the SDR + Observer loops** (see `SDR_GUIDE.md`).

## What's in this folder

| File | Role |
|---|---|
| `company_config.json` | What Best Roadways sells + sender identity (pre-filled from the website) |
| `qualification_rules.json` | Logistics ICP filter (ships goods = yes; transporters/3PLs = no) |
| `strategy_playbook.md` | Email frameworks (VIC, Mouse Trap, …) + WhatsApp cadence |
| `SDR_GUIDE.md` | Tenant operating manual (replaces root CLAUDE.md for this tenant) |
| `erpnext_client.py` / `brevo_client.py` / `gemini_client.py` | Backend clients (ready once keys are set) |
| `sync_leads.py` / `qualify_leads.py` / `merge_verdicts.py` | Lead pipeline (ERPNext + CSV → prioritised queue) |
| `outreach_tracker.json` | System of record (actions, stats) |
| `blocked_leads.json` / `qualified_leads.json` / `urgent_followups.json` | Queue + suppression state |
| `leads.csv` | Operator-supplied account/lead list (template provided) |
| `generate_dashboard.py` / `deploy_dashboard.sh` | Dashboard build + Cloudflare Pages deploy |
| `.env.example` / `.mcp.json.example` | Config templates (real `.env` / `.mcp.json` are gitignored) |

## Control panel (recommended way to operate)

A local web app that ties everything together — enter API keys, upload a CSV
(Gemini analyzes it), run the SDR/Observer cycles, and watch the logs:

```
bash tenants/best-roadways/run_panel.sh
# → http://127.0.0.1:8765
```

In the panel:
1. **API keys** — paste Brevo + ERPNext keys; saved only to the local `.env`. Gemini is already configured.
2. **Upload leads CSV** — drops into `leads.csv`, rebuilds the qualified queue, and shows a Gemini ICP analysis.
3. **Run cycles** — **Run SDR (sender)** drafts + (optionally) sends; **Run Observer** pulls Brevo events and refreshes stats. A **Live-send** toggle controls real sends (off = dry-run); an **Auto-loop** toggle runs SDR hourly / Observer every 3h while the app is open. **Publish to Cloudflare** refreshes the public mirror.
4. **Logs** — the live tail of `cycle.log`; recent actions show in a table.

Safety: the app binds to `127.0.0.1` only, secrets live in the gitignored `.env`,
live-send is off by default, and the daily caps + 11:00–19:30 window gate every live send.

## Dashboard (public mirror)

```
AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/generate_dashboard.py
bash tenants/best-roadways/deploy_dashboard.sh
```
Live at **https://best-roadways-sdr.pages.dev** (Cloudflare Pages project `best-roadways-sdr`).
The panel's **Publish to Cloudflare** button does both steps for you.

## Guardrails
- First touches < 50 words; casual/unsure tone; company name in subject.
- Email cap 300/day, WhatsApp cap 10/day, send window 11:00–19:30 local.
- Never name competitors; never contact blocked leads; honour opt-outs immediately.
- `direct_dial` / phone reveals are not used.
