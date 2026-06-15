import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";

import { db } from "@/lib/db";
import { actions, integrations, leads, tenants } from "@/lib/db/schema";

/**
 * Public ingest for OpenWA `message.received` webhooks. The local worker
 * registers this URL (with ?tenant=<slug>&token=<secret>) once a WhatsApp
 * session is linked. Inbound messages become an `actions` row (channel=whatsapp)
 * and an urgent `lead`. Authenticated by the shared token (and optionally the
 * X-OpenWA-Signature HMAC).
 *
 * Note: this is a NON-secret-bearing path — it only writes message metadata, no
 * integration secrets are involved.
 */
export async function POST(req: Request) {
  const url = new URL(req.url);
  const slug = url.searchParams.get("tenant");
  const token = url.searchParams.get("token");
  if (!slug || !token || token !== process.env.WHATSAPP_WEBHOOK_SECRET) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const tenant = await db.query.tenants.findFirst({ where: eq(tenants.slug, slug) });
  if (!tenant) return NextResponse.json({ error: "unknown tenant" }, { status: 404 });

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }

  // OpenWA shape: { event, payload: { data: <message> }, signature }
  const event = body.event as string | undefined;
  const payload = (body.payload ?? {}) as Record<string, unknown>;
  const msg = (payload.data ?? body.data ?? {}) as Record<string, unknown>;
  if (event && event !== "message.received") {
    return NextResponse.json({ ok: true, ignored: event });
  }
  // Skip our own outgoing echoes.
  if (msg.fromMe === true || msg.direction === "outgoing") {
    return NextResponse.json({ ok: true, skipped: "outgoing" });
  }

  const from = String(msg.from ?? msg.chatId ?? "");
  const text = String(msg.body ?? "");
  const messageId = String(msg.id ?? msg.messageId ?? `${from}:${msg.timestamp ?? ""}`);
  const name = (msg.notifyName ?? msg.pushName ?? null) as string | null;
  let ts = Number(msg.timestamp ?? 0);
  if (ts > 1e12) ts = Math.floor(ts / 1000);
  const occurredAt = ts ? new Date(ts * 1000) : new Date();

  // Idempotent: same message id won't duplicate.
  await db
    .insert(actions)
    .values({
      tenantId: tenant.id,
      sourceKey: `wa-in:${messageId}`,
      channel: "whatsapp",
      company: name,
      recipient: from.replace(/@c\.us$/, ""),
      body: text,
      messageId,
      chatId: from,
      status: "received",
      events: { replied: true, incoming: true },
      occurredAt,
    })
    .onConflictDoNothing();

  // Surface as an urgent follow-up.
  await db
    .insert(leads)
    .values({
      tenantId: tenant.id,
      externalId: `wa:${from}`,
      company: name,
      mobile: from.replace(/@c\.us$/, ""),
      status: "urgent",
      payload: { lastMessage: text, chatId: from, at: occurredAt.toISOString() },
    })
    .onConflictDoUpdate({
      target: [leads.tenantId, leads.externalId, leads.status],
      set: { payload: { lastMessage: text, chatId: from }, updatedAt: new Date() },
    });

  // Touch last_checked so the dashboard shows recent inbound activity.
  await db
    .update(integrations)
    .set({ lastCheckedAt: new Date() })
    .where(and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, "whatsapp")));

  return NextResponse.json({ ok: true });
}
