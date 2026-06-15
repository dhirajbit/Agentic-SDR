/**
 * Tenant-scoped read queries. EVERY function takes tenantId as its first arg
 * and filters on it. Callers pass the tenant id resolved from the Clerk session
 * (see lib/auth/tenant.ts) — never a value from request input.
 */
import { and, desc, eq, sql } from "drizzle-orm";

import { db } from "./index";
import {
  actions,
  commands,
  creditSnapshots,
  cycleRuns,
  integrations,
  leads,
  settings,
} from "./schema";

export const PROVIDERS = [
  "apollo",
  "brevo",
  "zoho",
  "whatsapp",
  "gemini",
  "erpnext",
] as const;
export type Provider = (typeof PROVIDERS)[number];

export async function getIntegrations(tenantId: string) {
  return db.select().from(integrations).where(eq(integrations.tenantId, tenantId));
}

export async function getIntegration(tenantId: string, provider: Provider) {
  return db.query.integrations.findFirst({
    where: and(eq(integrations.tenantId, tenantId), eq(integrations.provider, provider)),
  });
}

export async function getRecentActions(
  tenantId: string,
  opts: { channel?: "email" | "whatsapp"; status?: string; limit?: number } = {},
) {
  const filters = [eq(actions.tenantId, tenantId)];
  if (opts.channel) filters.push(eq(actions.channel, opts.channel));
  if (opts.status) filters.push(eq(actions.status, opts.status));
  return db
    .select()
    .from(actions)
    .where(and(...filters))
    .orderBy(desc(actions.occurredAt))
    .limit(opts.limit ?? 50);
}

export async function getCycleRuns(tenantId: string, limit = 25) {
  return db
    .select()
    .from(cycleRuns)
    .where(eq(cycleRuns.tenantId, tenantId))
    .orderBy(desc(cycleRuns.startedAt))
    .limit(limit);
}

export async function getCycleRun(tenantId: string, runId: string) {
  return db.query.cycleRuns.findFirst({
    where: and(eq(cycleRuns.tenantId, tenantId), eq(cycleRuns.id, runId)),
  });
}

export async function getLeadCounts(tenantId: string) {
  const rows = await db
    .select({ status: leads.status, count: sql<number>`count(*)::int` })
    .from(leads)
    .where(eq(leads.tenantId, tenantId))
    .groupBy(leads.status);
  const counts: Record<string, number> = { queued: 0, blocked: 0, urgent: 0 };
  for (const r of rows) counts[r.status] = r.count;
  return counts;
}

export async function getLeadsByStatus(tenantId: string, status: string, limit = 100) {
  return db
    .select()
    .from(leads)
    .where(and(eq(leads.tenantId, tenantId), eq(leads.status, status)))
    .orderBy(desc(leads.updatedAt))
    .limit(limit);
}

export async function getLatestCredit(tenantId: string) {
  return db.query.creditSnapshots.findFirst({
    where: eq(creditSnapshots.tenantId, tenantId),
    orderBy: desc(creditSnapshots.at),
  });
}

export async function getSettings(tenantId: string) {
  return db.query.settings.findFirst({ where: eq(settings.tenantId, tenantId) });
}

export async function getPendingCommands(tenantId: string) {
  return db
    .select()
    .from(commands)
    .where(and(eq(commands.tenantId, tenantId), eq(commands.status, "pending")))
    .orderBy(desc(commands.createdAt));
}

/** Aggregate stats for the overview tiles, computed from the actions feed. */
export async function getAggregateStats(tenantId: string) {
  const [row] = await db
    .select({
      total: sql<number>`count(*)::int`,
      emails: sql<number>`count(*) filter (where ${actions.channel} = 'email' and ${actions.status} not in ('scheduled','drafted'))::int`,
      whatsapp: sql<number>`count(*) filter (where ${actions.channel} = 'whatsapp' and ${actions.status} not in ('scheduled','drafted'))::int`,
      sent: sql<number>`count(*) filter (where ${actions.status} in ('sent','completed','pushed_to_sequence'))::int`,
      scheduled: sql<number>`count(*) filter (where ${actions.status} = 'scheduled')::int`,
      drafted: sql<number>`count(*) filter (where ${actions.status} = 'drafted')::int`,
      replied: sql<number>`count(*) filter (where (${actions.events} ->> 'replied') = 'true')::int`,
      opened: sql<number>`count(*) filter (where (${actions.events} ->> 'opened') = 'true' or (${actions.events} ->> 'clicked') = 'true')::int`,
    })
    .from(actions)
    .where(eq(actions.tenantId, tenantId));
  return row ?? { total: 0, emails: 0, whatsapp: 0, sent: 0, scheduled: 0, drafted: 0, replied: 0, opened: 0 };
}
