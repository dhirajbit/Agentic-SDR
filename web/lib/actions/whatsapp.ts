"use server";

import { auth } from "@clerk/nextjs/server";
import { headers } from "next/headers";
import { and, eq } from "drizzle-orm";
import { revalidatePath } from "next/cache";

import { resolveTenant } from "@/lib/auth/tenant";
import { getIntegration } from "@/lib/db/queries";
import { db } from "@/lib/db";
import { commands, integrations } from "@/lib/db/schema";
import * as wa from "@/lib/openwa";

/** Build the public reply-webhook URL for this tenant from the request host. */
async function webhookUrl(slug: string): Promise<string | null> {
  const secret = process.env.WHATSAPP_WEBHOOK_SECRET;
  if (!secret) return null;
  const h = await headers();
  const host = h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "https";
  if (!host) return null;
  return `${proto}://${host}/api/whatsapp/webhook?tenant=${slug}&token=${secret}`;
}

/** Get (or create) the tenant's OpenWA session id, stored in integrations.config. */
async function ensureSession(tenantId: string, slug: string): Promise<string> {
  const row = await getIntegration(tenantId, "whatsapp");
  const existing = (row?.config?.OPENWA_SESSION_ID as string | undefined) ?? undefined;
  if (existing) {
    try {
      const s = await wa.getSessionStatus(existing);
      if (s?.id) return existing;
    } catch {
      /* session gone — recreate */
    }
  }
  const created = await wa.createSession(slug);
  await db
    .update(integrations)
    .set({ config: { ...(row?.config ?? {}), OPENWA_SESSION_ID: created.id }, updatedAt: new Date() })
    .where(and(eq(integrations.tenantId, tenantId), eq(integrations.provider, "whatsapp")));
  return created.id;
}

/**
 * Start WhatsApp linking. With a hosted OpenWA (OPENWA_API_URL set) the web app
 * talks to it directly: create/start the session and register the reply webhook,
 * then the UI polls the status endpoint which returns the live QR. Without a
 * hosted gateway it falls back to enqueuing a command for the local worker.
 */
export async function enqueueWhatsappLink() {
  const { userId } = await auth();
  const tenant = await resolveTenant();

  if (wa.openwaEnabled()) {
    const sid = await ensureSession(tenant.id, tenant.slug);
    await wa.startSession(sid);
    const url = await webhookUrl(tenant.slug);
    if (url) {
      try {
        await wa.ensureWebhook(sid, url, process.env.WHATSAPP_WEBHOOK_SECRET!);
      } catch {
        /* webhook can also be registered once ready */
      }
    }
    await db
      .update(integrations)
      .set({ status: "pending_test", updatedAt: new Date() })
      .where(and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, "whatsapp")));
  } else {
    await db
      .update(integrations)
      .set({ status: "pending_test", updatedAt: new Date() })
      .where(and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, "whatsapp")));
    await db.insert(commands).values({
      tenantId: tenant.id,
      type: "whatsapp_link",
      requestedBy: userId ?? undefined,
    });
  }
  revalidatePath("/dashboard/integrations/whatsapp");
}
