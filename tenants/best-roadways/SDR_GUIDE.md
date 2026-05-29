# Best Roadways — Agentic SDR Operating Guide

> The repo-root `CLAUDE.md` describes the **Apollo** tenant model. This tenant does **not** use Apollo.
> When `AGENTIC_SDR_TENANT=best-roadways` is active, follow THIS guide instead. Read
> `company_config.json` and `strategy_playbook.md` before drafting anything.

## Stack

| Concern | This tenant |
|---|---|
| Lead / account source | **ERPNext** (`erpnext_client.py`) and/or operator-supplied **`leads.csv`** |
| AI drafting agent | **Gemini** (`gemini_client.py`, key supplied by operator) |
| Email send + events | **Brevo** (`brevo_client.py`) |
| Follow-up channel | **WhatsApp** (local Go bridge under repo `whatsapp-mcp/`, MCP server in `.mcp.json`) |
| System of record | `outreach_tracker.json` (local) + ERPNext lead notes |
| Dashboard | `generate_dashboard.py` → Cloudflare Pages (`deploy_dashboard.sh`) |

No Apollo. No credit gate. No phone reveals.

## One-time setup (operator)

1. `cp tenants/best-roadways/.env.example tenants/best-roadways/.env` and fill in
   `ERPNEXT_*`, `BREVO_*`, `GEMINI_API_KEY`. (`CLOUDFLARE_*` are pre-filled.)
2. Verify the sending domain/sender in Brevo; set `BREVO_SENDER_NAME` / `BREVO_SENDER_EMAIL`.
3. Drop the real account list at `tenants/best-roadways/leads.csv` (keep the header), or rely on ERPNext.
4. For WhatsApp follow-ups: start the bridge (`cd whatsapp-mcp/whatsapp-bridge && go run main.go`), scan the QR. Re-auth ~every 20 days.
5. Activate the tenant: `bin/tenant best-roadways` then `export AGENTIC_SDR_TENANT=best-roadways`, and **restart Claude Code** so the WhatsApp MCP loads.
6. Build the queue:
   ```
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/sync_leads.py
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/qualify_leads.py
   AGENTIC_SDR_TENANT=best-roadways python tenants/best-roadways/merge_verdicts.py
   ```

## SDR loop (per cycle)

**Step 0 — Pre-flight.** Confirm local time is 11:00 ≤ now ≤ 19:30. Read `company_config.json`,
`strategy_playbook.md`, `outreach_tracker.json`, `blocked_leads.json`, `urgent_followups.json`,
`qualified_leads.json`. Check today's send count against `DAILY_EMAIL_CAP` / `DAILY_WHATSAPP_CAP`.

**Step 1 — Urgent follow-ups FIRST.** If `urgent_followups.json` has items (leads that replied),
draft a personal reply, send, log, remove from the list.

**Step 2 — Group by industry.** Batch from the top of `qualified_leads.json` (priority-sorted).
Group by vertical (chemical / FMCG / pharma / automotive / steel) for shared research.

**Step 3 — Research before writing.** For each lead: fetch their `website` (what they make/ship,
which regions, any freight-relevant signal — new plant, expansion, hiring logistics roles), check
LinkedIn, pick the vertical hook from `strategy_playbook.md`, note `job_title` for tone.

**Step 4 — Draft via Gemini.** Use `gemini_client.draft(prompt, system=<relevant playbook section>)`.
Pick the framework (VIC default). Keep first touches < 50 words, company name in subject, casual/unsure tone.
**Record the draft + framework + subject in `outreach_tracker.json["actions"]` BEFORE sending.**

**Step 5 — Send.**
- Lead has `email_id` → `brevo_client.send_email(...)`. Store the returned `messageId`.
- Lead has `mobile_no` (no email, or as 48h follow-up) → WhatsApp MCP `send_message`. Respect the
  10/day cap, warm-up ramp, 90–120s gaps; abort on "Not connected".
- Never contact anyone in `blocked_leads.json`.

**Step 6 — Log.** Append to `outreach_tracker.json["actions"]` (lead id, channel, framework, subject,
body, timestamp, `messageId`). Bump `aggregate_stats` and `framework_performance`. Add an ERPNext note
via `erpnext_client.add_note_to_lead(...)` if the lead came from ERPNext.

**Step 7 — Dashboard.** `python tenants/best-roadways/generate_dashboard.py` then
`bash tenants/best-roadways/deploy_dashboard.sh`.

## Observer loop (every ~3h)

1. Read `outreach_tracker.json`.
2. For recent email sends, pull events via `brevo_client.get_events(email, days=2)` — map
   delivered/opened/clicked/bounced. (Brevo can't see direct replies — those arrive in the sender inbox.)
3. For WhatsApp, check the bridge SQLite for read receipts / replies.
4. Leads that replied → write to `urgent_followups.json` and flag in the tracker.
5. Recompute `aggregate_stats` + `framework_performance`.
6. If thresholds met (≥20 sends per framework), update `strategy_playbook.md` rules / propose an A/B test.
   **Observer writes the playbook; the SDR only reads it.**
7. Regenerate + deploy the dashboard.

## Control panel (`app.py`)

For self-service operation there's a local Flask app (`run_panel.sh` → `http://127.0.0.1:8765`)
that exposes this whole workflow without Claude Code in the loop:
- **Config panel** writes Brevo/ERPNext keys to `.env` (Gemini already set).
- **CSV upload** runs `sync_leads`+`qualify_leads`+`merge_verdicts`, then `lead_analyzer.analyze_leads()` (Gemini) returns an ICP read.
- **Run SDR / Run Observer** call `sdr_cycle.run_sdr_cycle()` / `run_observer_cycle()`.
- **Live-send toggle** (off = dry-run) and **Auto-loop** (SDR hourly, Observer 3h) persist to `panel_settings.json`.
- **Logs** tail `cycle.log`; recent actions render in a table; **Publish** refreshes the Cloudflare mirror.

The cycle engine (`sdr_cycle.py`) is the Gemini-driven equivalent of the Claude `/loop` workflow above — use whichever fits. Both share the same tracker, playbook, queue, and caps.

## Guardrails
- First touches < 50 words; casual, unsure tone; company name in subject.
- Never name competitors. Never contact blocked leads. Honour opt-outs immediately.
- Email cap 300/day, WhatsApp cap 10/day, send window 11:00–19:30 local.
- Tracker is the system of record.
