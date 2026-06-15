import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";

import { resolveTenant } from "@/lib/auth/tenant";
import { getIntegration, PROVIDERS, type Provider } from "@/lib/db/queries";
import { db } from "@/lib/db";
import { integrations } from "@/lib/db/schema";
import * as wa from "@/lib/openwa";

/** Poll endpoint for an integration's live status + non-secret detail (e.g. WhatsApp QR). */
export async function GET(_req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  if (!PROVIDERS.includes(provider as Provider)) {
    return NextResponse.json({ error: "unknown provider" }, { status: 404 });
  }
  const tenant = await resolveTenant();
  const row = await getIntegration(tenant.id, provider as Provider);

  // Hosted OpenWA: fetch the QR/status live so the dashboard shows it on click.
  if (provider === "whatsapp" && wa.openwaEnabled()) {
    const sid = row?.config?.OPENWA_SESSION_ID as string | undefined;
    if (sid) {
      try {
        const s = await wa.getSessionStatus(sid);
        const ready = s.status === "ready";
        const detail: Record<string, unknown> = { session_status: s.status, phone: s.phone };
        if (!ready) {
          try {
            const q = await wa.getQr(sid);
            if (q.qrCode) detail.qr = q.qrCode;
          } catch {
            /* qr not ready yet */
          }
        }
        const status = ready ? "connected" : "pending_test";
        // persist (without the huge qr blob) so the overview reflects it
        await db
          .update(integrations)
          .set({
            status,
            statusDetail: { session_status: s.status, phone: s.phone },
            lastCheckedAt: new Date(),
          })
          .where(and(eq(integrations.tenantId, tenant.id), eq(integrations.provider, "whatsapp")));
        return NextResponse.json({ status, detail });
      } catch {
        /* gateway unreachable — fall through to stored status */
      }
    }
  }

  return NextResponse.json({
    status: row?.status ?? "unconfigured",
    detail: row?.statusDetail ?? {},
    lastCheckedAt: row?.lastCheckedAt ?? null,
  });
}
