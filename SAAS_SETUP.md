# Agentic SDR — Hosted SaaS Setup

The SDR is now a hosted product: a **Next.js app on Vercel** (tenant console) backed by
**Neon Postgres**, with the existing **Python workers running locally** and syncing state up.
Tenants log in (Clerk), see integration status + email/WhatsApp logs + cycle status, manage
their own integration keys, and trigger cycles.

```
Vercel (web/)  ⇄  Neon Postgres  ⇄  local worker (cloud_agent.py)
 Clerk auth        ciphertext +       holds private key, runs cycles + OpenWA,
 reads/writes      non-secret status  pushes state, decrypts secrets
```

**Security invariant:** Vercel/Neon never hold a plaintext integration secret. The browser
seals each secret with the tenant's public key (`web/lib/crypto/seal.ts`); only the local
worker can decrypt (`cloud_keys.py`, private key in `tenants/<slug>/.worker_key`).

---

## 1. Provision infra (needs your hands — one-time)

### Vercel project
- Import this repo into Vercel. Set **Root Directory = `web`**.
- Framework preset: Next.js. (vercel.json already configures the cron.)

### Neon Postgres (Vercel Marketplace)
- Vercel → Storage → **Neon** → create. It injects `DATABASE_URL` (pooled, `-pooler` host)
  and `DATABASE_URL_UNPOOLED` into the project's env.

### Clerk (Vercel Marketplace)
- Vercel → Marketplace → **Clerk** → install. It injects
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`.
- In the **Clerk dashboard → Organizations**, enable Organizations (orgs = tenants).

### Extra env (set in Vercel project settings)
- `CRON_SECRET` = any long random string (used by `/api/cron/check-stale`).

---

## 2. Run migrations

```bash
cd web
npm install
vercel link            # link to the Vercel project
vercel env pull .env.local   # pulls DATABASE_URL(_UNPOOLED), Clerk keys
npm run db:migrate     # applies drizzle/0000_*.sql to Neon
```

Commit the generated `web/drizzle/` SQL — it's the migration history.

---

## 3. Local worker (one process per tenant)

The worker runs where the cycles + OpenWA Docker already run.

```bash
# repo root
pip install -r requirements.txt          # psycopg, pynacl, ...

# add the Neon connection to the repo-root .env (pooled string from Neon):
#   NEON_DATABASE_URL=postgres://...-pooler.../neondb?sslmode=require
#   SDR_DRIVER=sdr_cycle        # or 'claude' for the abhiyanta tenant

# start one agent per tenant:
AGENTIC_SDR_TENANT=best-roadways python cloud_agent.py
AGENTIC_SDR_TENANT=abhiyanta-tech SDR_DRIVER=claude python cloud_agent.py
```

On first run the agent **generates the tenant keypair**, writes the private key to
`tenants/<slug>/.worker_key` (chmod 600, gitignored), and publishes the public key to Neon.
It then heartbeats, claims web commands, and pushes tracker/leads/integration health.

Run it under launchd/systemd/tmux so it stays up. `SDR_DRIVER=sdr_cycle` enables Run-now
cycle execution (best-roadways); `claude` tenants push state only.

---

## 4. Onboard a tenant

1. Web: sign in → create a Clerk **organization**. Its slug becomes the tenant slug and
   **must match an existing `tenants/<slug>/` directory** (this is a single-operator product;
   self-serve provisioning of a brand-new local tenant is not in v1).
2. Click **Link & open console** — provisions the `tenants` row + empty integration rows.
3. Start the local worker for that slug once so it publishes its public key.
4. In the console → **Integrations**, enter each provider's keys. The worker decrypts on its
   next loop, health-checks, and flips status to "connected".

---

## 5. WhatsApp note

OpenWA QR authorization stays **local** in v1: scan the QR on the local gateway
(`AGENTIC_SDR_TENANT=<slug> python openwa_client.py` → `start_session()` → `get_qr()`).
The console shows session status/phone only; "re-auth on local gateway" when not ready.

---

## 6. Security checklist

- **Never commit** `tenants/*/.worker_key` or `tenants/*/.env` (both gitignored).
- **Back up** each `.worker_key` offline (encrypted) — losing it makes stored secrets
  unrecoverable (by design) and requires tenants to re-enter keys.
- Rotating a tenant's keypair: delete `.worker_key`, restart the agent (publishes a new
  public key), then have the tenant re-enter their keys.
- Run `/cso` against `web/lib/crypto/`, `web/lib/db/queries.ts` (tenant isolation), and
  `cloud_sync.py` before going live.

---

## 7. Verify end-to-end

- **Build/dev:** `cd web && npm run build` (passes) / `npm run dev`.
- **Isolation:** sign in as two orgs; confirm one cannot see the other's rows.
- **Sync:** start `cloud_agent.py`; confirm actions/cycles/leads/credits appear in the console,
  with abhiyanta's `"… IST"` timestamps parsed correctly (`python tests/test_normalize.py`).
- **Secrets:** enter a real Apollo key in the console → status flips to "connected, N credits"
  within a worker loop; verify the Neon `integrations` row holds only ciphertext.
- **Controls:** toggle live-send + "Run SDR now" (best-roadways) → a `cycle_runs` row goes
  running → done with a summary + log tail.
