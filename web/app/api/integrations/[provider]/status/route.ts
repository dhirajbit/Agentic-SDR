import { NextResponse } from "next/server";

import { resolveTenant } from "@/lib/auth/tenant";
import { getIntegration, PROVIDERS, type Provider } from "@/lib/db/queries";

/** Poll endpoint for an integration's live status + non-secret detail (e.g. WhatsApp QR). */
export async function GET(_req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  if (!PROVIDERS.includes(provider as Provider)) {
    return NextResponse.json({ error: "unknown provider" }, { status: 404 });
  }
  const tenant = await resolveTenant();
  const row = await getIntegration(tenant.id, provider as Provider);
  return NextResponse.json({
    status: row?.status ?? "unconfigured",
    detail: row?.statusDetail ?? {},
    lastCheckedAt: row?.lastCheckedAt ?? null,
  });
}
