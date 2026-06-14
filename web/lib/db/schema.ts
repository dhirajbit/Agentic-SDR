/**
 * Drizzle schema for the Agentic SDR SaaS.
 *
 * Multi-tenant: every table except `tenants` carries `tenantId`. The query layer
 * (lib/db/queries.ts) ALWAYS filters by a tenantId derived from the Clerk
 * session server-side — never from request input.
 *
 * Secret-handling invariant: `integrations.secretsCiphertext` holds ONLY
 * libsodium sealed-box ciphertext. Plaintext secrets never touch this DB.
 * `config` / `statusDetail` hold non-secret values only.
 *
 * `casing: "snake_case"` in drizzle.config maps these camelCase names to
 * snake_case columns automatically.
 */
import { sql } from "drizzle-orm";
import {
  boolean,
  date,
  index,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

const id = () => uuid("id").primaryKey().default(sql`gen_random_uuid()`);
const createdAt = () => timestamp("created_at", { withTimezone: true }).defaultNow().notNull();

// One row per customer. `slug` matches the on-disk tenants/<slug>/ dir so the
// local worker can find the tenant's files. `driver` decides whether Run-now
// cycle controls render (sdr_cycle tenants) or are hidden (Claude-driven).
export const tenants = pgTable("tenants", {
  id: id(),
  clerkOrgId: text("clerk_org_id").notNull().unique(),
  slug: text("slug").notNull().unique(),
  name: text("name").notNull(),
  driver: text("driver").notNull().default("sdr_cycle"), // 'sdr_cycle' | 'claude'
  // base64 libsodium box public key; the web encrypts secrets to it, only the
  // local worker holds the matching private key.
  workerPublicKey: text("worker_public_key"),
  workerLastSeenAt: timestamp("worker_last_seen_at", { withTimezone: true }),
  createdAt: createdAt(),
});

// One row per (tenant, provider). Status + non-secret detail are written by the
// worker after a health check; ciphertext is written by the web.
export const integrations = pgTable(
  "integrations",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    provider: text("provider").notNull(), // apollo|brevo|zoho|whatsapp|gemini|erpnext
    config: jsonb("config").$type<Record<string, unknown>>().default({}), // NON-secret
    secretsCiphertext: jsonb("secrets_ciphertext")
      .$type<Record<string, string>>()
      .default({}), // field -> sealed-box base64
    status: text("status").notNull().default("unconfigured"), // unconfigured|pending_test|connected|error
    statusDetail: jsonb("status_detail").$type<Record<string, unknown>>().default({}), // NON-secret
    lastCheckedAt: timestamp("last_checked_at", { withTimezone: true }),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [uniqueIndex("integrations_tenant_provider_uq").on(t.tenantId, t.provider)],
);

export const cycleRuns = pgTable(
  "cycle_runs",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    kind: text("kind").notNull(), // sdr | observer
    status: text("status").notNull().default("pending"), // pending|running|done|error
    trigger: text("trigger"), // manual | auto_loop | claude
    commandId: uuid("command_id"),
    startedAt: timestamp("started_at", { withTimezone: true }),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
    summary: jsonb("summary").$type<Record<string, unknown>>(),
    log: text("log"),
  },
  (t) => [index("cycle_runs_tenant_started_idx").on(t.tenantId, t.startedAt.desc())],
);

// Unified email + WhatsApp log feed. `sourceKey` makes the push idempotent.
export const actions = pgTable(
  "actions",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    sourceKey: text("source_key").notNull(),
    channel: text("channel").notNull(), // email | whatsapp
    company: text("company"),
    recipient: text("recipient"),
    framework: text("framework"),
    subject: text("subject"),
    body: text("body"),
    messageId: text("message_id"),
    chatId: text("chat_id"),
    status: text("status"),
    dryRun: boolean("dry_run"),
    events: jsonb("events").$type<Record<string, unknown>>().default({}),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull(),
  },
  (t) => [
    uniqueIndex("actions_tenant_sourcekey_uq").on(t.tenantId, t.sourceKey),
    index("actions_tenant_occurred_idx").on(t.tenantId, t.occurredAt.desc()),
    index("actions_tenant_channel_occurred_idx").on(t.tenantId, t.channel, t.occurredAt.desc()),
  ],
);

export const leads = pgTable(
  "leads",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    externalId: text("external_id").notNull(),
    company: text("company"),
    email: text("email"),
    mobile: text("mobile"),
    status: text("status").notNull(), // queued | blocked | urgent
    payload: jsonb("payload").$type<Record<string, unknown>>(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => [
    uniqueIndex("leads_tenant_extid_status_uq").on(t.tenantId, t.externalId, t.status),
    index("leads_tenant_status_idx").on(t.tenantId, t.status),
  ],
);

export const creditSnapshots = pgTable(
  "credit_snapshots",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    at: timestamp("at", { withTimezone: true }).notNull(),
    label: text("label"),
    leadCreditLeft: integer("lead_credit_left"),
    directDialCreditLeft: integer("direct_dial_credit_left"),
    exportCreditLeft: integer("export_credit_left"),
    cycleStart: date("cycle_start"),
    cycleEnd: date("cycle_end"),
  },
  (t) => [index("credit_snapshots_tenant_at_idx").on(t.tenantId, t.at.desc())],
);

// Mirror of panel_settings.json — written by the web (via a command) and the worker.
export const settings = pgTable("settings", {
  tenantId: uuid("tenant_id")
    .primaryKey()
    .references(() => tenants.id, { onDelete: "cascade" }),
  liveSend: boolean("live_send").notNull().default(false),
  autoLoop: boolean("auto_loop").notNull().default(false),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  updatedBy: text("updated_by"),
});

// Web -> local-worker control queue. Worker claims with FOR UPDATE SKIP LOCKED.
export const commands = pgTable(
  "commands",
  {
    id: id(),
    tenantId: uuid("tenant_id")
      .notNull()
      .references(() => tenants.id, { onDelete: "cascade" }),
    type: text("type").notNull(), // run_sdr|run_observer|apply_settings|test_connection|apply_secrets
    args: jsonb("args").$type<Record<string, unknown>>().default({}),
    status: text("status").notNull().default("pending"), // pending|claimed|done|error|expired
    requestedBy: text("requested_by"),
    createdAt: createdAt(),
    claimedAt: timestamp("claimed_at", { withTimezone: true }),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
    result: jsonb("result").$type<Record<string, unknown>>(),
  },
  (t) => [
    index("commands_tenant_status_created_idx").on(t.tenantId, t.status, t.createdAt),
    // cheap polling target for the worker
    index("commands_pending_idx").on(t.status).where(sql`${t.status} = 'pending'`),
  ],
);

export type Tenant = typeof tenants.$inferSelect;
export type Integration = typeof integrations.$inferSelect;
export type CycleRun = typeof cycleRuns.$inferSelect;
export type Action = typeof actions.$inferSelect;
export type Lead = typeof leads.$inferSelect;
export type Settings = typeof settings.$inferSelect;
export type Command = typeof commands.$inferSelect;
